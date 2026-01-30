from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
import json
from io import BytesIO

from app.models import db, Task, Planner, Group, User, Notification, Report, TaskStatus, TaskPriority
from app.services.report_service import ReportService
from app.services.analytics_service import AnalyticsService
from app.services.microsoft_api import MicrosoftPlannerAPI
from app.utils.decorators import admin_required, rate_limit
from app.services.planner_sync import PlannerSync

api_bp = Blueprint('api', __name__, url_prefix='/api')

# ===== TASKS API =====
@api_bp.route('/tasks', methods=['GET'])
@login_required
@rate_limit(60, 60)  # 60 requisições por minuto
def get_tasks():
    """API para listar tarefas com filtros"""
    try:
        from app.utils.task_filters import TaskFilter
        
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Aplicar filtros
        query = Task.query.join(Planner).join(Group)
        query = TaskFilter.apply_filters(query, request.args.to_dict())
        
        # Executar query paginada
        paginated_tasks = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Preparar resposta
        tasks_data = []
        for task in paginated_tasks.items:
            # Obter nomes reais dos responsáveis
            assignments = task.get_assignments()
            assignee_info = []
            for user_id, assignment in assignments.items():
                # Buscar usuário no banco de dados
                user = User.query.filter_by(azure_id=user_id).first()
                if user:
                    assignee_info.append({
                        'id': user_id,
                        'name': user.display_name,
                        'email': user.email
                    })
                else:
                    # Se não encontrou, usar informações do assignment JSON
                    assignee_info.append({
                        'id': user_id,
                        'name': assignment.get('userDisplayName', 'Usuário'),
                        'email': assignment.get('userEmail', '')
                    })
            
            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status.value if task.status else None,
                'priority': task.priority.value if task.priority else None,
                'percent_complete': task.percent_complete,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'start_date': task.start_date.isoformat() if task.start_date else None,
                'completed_date': task.completed_date.isoformat() if task.completed_date else None,
                'is_overdue': task.is_overdue,
                'is_blocked': task.is_blocked,
                'planner': {
                    'id': task.planner.id,
                    'title': task.planner.title
                } if task.planner else None,
                'bucket': task.bucket.name if task.bucket else None,
                'assignments': task.get_assignments(),
                'assignees': assignee_info,  # NOVO: incluir informações dos responsáveis
                'created_date': task.created_date.isoformat() if task.created_date else None,
                'last_modified': task.last_modified.isoformat() if task.last_modified else None
            })
        
        return jsonify({
            'success': True,
            'tasks': tasks_data,
            'pagination': {
                'page': paginated_tasks.page,
                'per_page': paginated_tasks.per_page,
                'total': paginated_tasks.total,
                'pages': paginated_tasks.pages
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Erro ao buscar tarefas: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/tasks/<task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    """API para obter detalhes de uma tarefa"""
    try:
        task = Task.query.get_or_404(task_id)
        
        # Obter histórico de mudanças
        from app.models import TaskChange
        changes = TaskChange.query.filter_by(task_id=task_id).order_by(TaskChange.changed_at.desc()).limit(20).all()
        
        # Obter comentários
        from app.models import TaskComment
        comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_date.desc()).all()
        
        # Obter nomes reais dos responsáveis
        assignments = task.get_assignments()
        assignee_info = []
        for user_id, assignment in assignments.items():
            user = User.query.filter_by(azure_id=user_id).first()
            if user:
                assignee_info.append({
                    'id': user_id,
                    'name': user.display_name,
                    'email': user.email,
                    'jobTitle': user.job_title
                })
            else:
                assignee_info.append({
                    'id': user_id,
                    'name': assignment.get('userDisplayName', 'Usuário'),
                    'email': assignment.get('userEmail', '')
                })
        
        return jsonify({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status.value if task.status else None,
                'priority': task.priority.value if task.priority else None,
                'percent_complete': task.percent_complete,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'start_date': task.start_date.isoformat() if task.start_date else None,
                'completed_date': task.completed_date.isoformat() if task.completed_date else None,
                'created_date': task.created_date.isoformat() if task.created_date else None,
                'last_modified': task.last_modified.isoformat() if task.last_modified else None,
                'is_overdue': task.is_overdue,
                'is_blocked': task.is_blocked,
                'blocked_reason': task.blocked_reason,
                'planner': {
                    'id': task.planner.id,
                    'title': task.planner.title,
                    'group_name': task.planner.group.name if task.planner.group else None
                } if task.planner else None,
                'bucket': {
                    'id': task.bucket.id,
                    'name': task.bucket.name
                } if task.bucket else None,
                'assignments': task.get_assignments(),
                'assignees': assignee_info,  # NOVO
                'labels': task.get_labels(),
                'category': task.category,
                'effort': task.effort,
                'business_value': task.business_value,
                'checklists': {
                    'total': task.checklists_total,
                    'completed': task.checklists_completed
                },
                'comments_count': task.comments_count,
                'attachments_count': task.attachments_count
            },
            'changes': [{
                'id': c.id,
                'field_changed': c.field_changed,
                'old_value': c.old_value,
                'new_value': c.new_value,
                'changed_by': c.changed_by_name,
                'changed_at': c.changed_at.isoformat() if c.changed_at else None
            } for c in changes],
            'comments': [{
                'id': c.id,
                'user_name': c.user_name,
                'comment': c.comment,
                'created_date': c.created_date.isoformat() if c.created_date else None,
                'is_edited': c.is_edited
            } for c in comments]
        })
        
    except Exception as e:
        current_app.logger.error(f'Erro ao buscar tarefa {task_id}: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/tasks/<task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """API para atualizar status da tarefa"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'success': False, 'error': 'Status é obrigatório'}), 400
        
        task = Task.query.get_or_404(task_id)
        old_status = task.status
        
        # Atualizar status
        task.status = TaskStatus(new_status)
        
        # Se marcada como concluída, atualizar data de conclusão
        if new_status == 'completed' and not task.completed_date:
            task.completed_date = datetime.now(timezone.utc)
            task.percent_complete = 100
        elif new_status != 'completed':
            task.completed_date = None
        
        task.last_modified = datetime.now(timezone.utc)
        
        # Registrar mudança
        from app.models import TaskChange
        change = TaskChange(
            task_id=task_id,
            field_changed='status',
            old_value=old_status.value if old_status else None,
            new_value=new_status,
            changed_by=current_user.azure_id,
            changed_by_name=current_user.display_name,
            change_type='status_change'
        )
        db.session.add(change)
        db.session.commit()
        
        # Enviar notificação se necessário
        try:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService(current_app)
            if new_status == 'completed':
                notification_service.send_task_completion_notification(task, current_user)
        except Exception as notif_error:
            current_app.logger.warning(f'Erro ao enviar notificação: {str(notif_error)}')
        
        return jsonify({
            'success': True,
            'message': 'Status atualizado com sucesso',
            'task': {
                'id': task.id,
                'status': task.status.value,
                'percent_complete': task.percent_complete,
                'completed_date': task.completed_date.isoformat() if task.completed_date else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao atualizar status da tarefa {task_id}: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/tasks/bulk-update', methods=['POST'])
@login_required
def bulk_update_tasks():
    """API para atualização em massa de tarefas"""
    try:
        if not current_app.config.get('ENABLE_BULK_OPERATIONS', True):
            return jsonify({'success': False, 'error': 'Operações em massa desabilitadas'}), 403
        
        data = request.get_json()
        task_ids = data.get('task_ids', [])
        updates = data.get('updates', {})
        
        if not task_ids:
            return jsonify({'success': False, 'error': 'Nenhuma tarefa selecionada'}), 400
        
        updated_count = 0
        
        # Atualizar cada tarefa
        for task_id in task_ids:
            task = Task.query.get(task_id)
            if task:
                # Registrar mudança
                from app.models import TaskChange
                change = TaskChange(
                    task_id=task_id,
                    field_changed='bulk_update',
                    old_value=json.dumps(task.to_dict()),
                    new_value=json.dumps(updates),
                    changed_by=current_user.azure_id,
                    changed_by_name=current_user.display_name,
                    change_type='bulk_update'
                )
                db.session.add(change)
                
                # Aplicar atualizações
                if 'status' in updates:
                    task.status = TaskStatus(updates['status'])
                if 'priority' in updates:
                    task.priority = TaskPriority(int(updates['priority']))
                if 'percent_complete' in updates:
                    task.percent_complete = updates['percent_complete']
                
                task.last_modified = datetime.now(timezone.utc)
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({'success': True, 'updated': updated_count})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro na atualização em massa: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== PLANNERS API =====
@api_bp.route('/planners', methods=['GET'])
@login_required
def get_planners():
    """API para listar planners"""
    try:
        planners = Planner.query.all()
        
        planners_data = []
        for planner in planners:
            planners_data.append({
                'id': planner.id,
                'title': planner.title,
                'description': planner.description,
                'created_date': planner.created_date.isoformat() if planner.created_date else None,
                'last_sync': planner.last_sync.isoformat() if planner.last_sync else None,
                'total_tasks': planner.total_tasks,
                'completed_tasks': planner.completed_tasks,
                'in_progress_tasks': planner.in_progress_tasks,
                'overdue_tasks': planner.overdue_tasks,
                'completion_rate': planner.completion_rate,
                'overdue_rate': planner.overdue_rate,
                'group': {
                    'id': planner.group.id,
                    'name': planner.group.name
                } if planner.group else None,
                'is_favorite': planner.is_favorite,
                'color': planner.color
            })
        
        return jsonify({
            'success': True,
            'planners': planners_data,
            'total': len(planners_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/planners/<planner_id>/tasks', methods=['GET'])
@login_required
def get_planner_tasks(planner_id):
    """API para listar tarefas de um planner específico"""
    try:
        planner = Planner.query.get_or_404(planner_id)
        
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        
        # Filtros
        status = request.args.get('status')
        priority = request.args.get('priority')
        
        query = Task.query.filter_by(planner_id=planner_id)
        
        if status:
            query = query.filter_by(status=TaskStatus(status))
        if priority:
            query = query.filter_by(priority=TaskPriority(priority))
        
        paginated_tasks = query.paginate(page=page, per_page=per_page, error_out=False)
        
        tasks_data = []
        for task in paginated_tasks.items:
            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'status': task.status.value if task.status else None,
                'priority': task.priority.value if task.priority else None,
                'percent_complete': task.percent_complete,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'is_overdue': task.is_overdue,
                'assignments': task.get_assignments()
            })
        
        return jsonify({
            'success': True,
            'planner': {
                'id': planner.id,
                'title': planner.title
            },
            'tasks': tasks_data,
            'pagination': {
                'page': paginated_tasks.page,
                'per_page': paginated_tasks.per_page,
                'total': paginated_tasks.total,
                'pages': paginated_tasks.pages
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/planners/<planner_id>/stats', methods=['GET'])
@login_required
def get_planner_stats(planner_id):
    """API para obter estatísticas de um planner"""
    try:
        planner = Planner.query.get_or_404(planner_id)
        
        # Estatísticas por status
        from sqlalchemy import func
        status_stats = db.session.query(
            Task.status,
            func.count(Task.id).label('count')
        ).filter_by(planner_id=planner_id).group_by(Task.status).all()
        
        # Estatísticas por prioridade
        priority_stats = db.session.query(
            Task.priority,
            func.count(Task.id).label('count')
        ).filter_by(planner_id=planner_id).group_by(Task.priority).all()
        
        # Tarefas por responsável
        assignments_stats = {}
        tasks = Task.query.filter_by(planner_id=planner_id).all()
        for task in tasks:
            assignments = task.get_assignments()
            for user_id, assignment in assignments.items():
                if user_id not in assignments_stats:
                    assignments_stats[user_id] = {
                        'name': assignment.get('userDisplayName', user_id),
                        'email': assignment.get('userEmail'),
                        'total': 0,
                        'completed': 0
                    }
                assignments_stats[user_id]['total'] += 1
                if task.status == TaskStatus.COMPLETED:
                    assignments_stats[user_id]['completed'] += 1
        
        return jsonify({
            'success': True,
            'planner': {
                'id': planner.id,
                'title': planner.title,
                'total_tasks': planner.total_tasks,
                'completed_tasks': planner.completed_tasks,
                'in_progress_tasks': planner.in_progress_tasks,
                'overdue_tasks': planner.overdue_tasks,
                'completion_rate': planner.completion_rate,
                'overdue_rate': planner.overdue_rate
            },
            'status_stats': [
                {
                    'status': status.value if status else None,
                    'count': count
                } for status, count in status_stats
            ],
            'priority_stats': [
                {
                    'priority': priority.value if priority else None,
                    'count': count
                } for priority, count in priority_stats
            ],
            'assignments_stats': list(assignments_stats.values())
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== GROUPS API =====
@api_bp.route('/groups', methods=['GET'])
@login_required
def get_groups():
    """API para listar grupos"""
    try:
        groups = Group.query.filter_by(is_active=True).all()
        
        groups_data = []
        for group in groups:
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'email': group.email,
                'description': group.description,
                'total_planners': group.total_planners,
                'total_tasks': group.total_tasks,
                'active_tasks': group.active_tasks,
                'last_sync': group.last_sync.isoformat() if group.last_sync else None,
                'is_favorite': group.is_favorite
            })
        
        return jsonify({
            'success': True,
            'groups': groups_data,
            'total': len(groups_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== USERS API =====
@api_bp.route('/users/me', methods=['GET'])
@login_required
def get_current_user():
    """API para obter informações do usuário atual"""
    try:
        return jsonify({
            'success': True,
            'user': {
                'id': current_user.id,
                'azure_id': current_user.azure_id,
                'email': current_user.email,
                'display_name': current_user.display_name,
                'job_title': current_user.job_title,
                'department': current_user.department,
                'phone': current_user.phone,
                'is_admin': current_user.is_admin,
                'theme': current_user.theme,
                'language': current_user.language,
                'timezone': current_user.timezone,
                'email_notifications': current_user.email_notifications,
                'push_notifications': current_user.push_notifications,
                'total_tasks_assigned': current_user.total_tasks_assigned,
                'completed_tasks': current_user.completed_tasks,
                'overdue_tasks': current_user.overdue_tasks,
                'task_completion_rate': current_user.task_completion_rate,
                'last_login': current_user.last_login.isoformat() if current_user.last_login else None,
                'created_at': current_user.created_at.isoformat() if current_user.created_at else None
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/users/me/preferences', methods=['GET', 'POST'])
@login_required
def user_preferences():
    """API para gerenciar preferências do usuário"""
    try:
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'preferences': current_user.get_preferences()
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            preferences = current_user.get_preferences()
            
            # Atualizar preferências
            for key, value in data.items():
                preferences[key] = value
            
            current_user.set_preferences(preferences)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Preferências atualizadas',
                'preferences': preferences
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/users/stats', methods=['GET'])
@login_required
def get_user_stats():
    """API para obter estatísticas do usuário"""
    try:
        # Tarefas por status
        from sqlalchemy import func
        status_stats = db.session.query(
            Task.status,
            func.count(Task.id).label('count')
        ).filter(
            Task.assignments_json.like(f'%"userId": "{current_user.azure_id}"%')
        ).group_by(Task.status).all()
        
        # Tarefas vencendo esta semana
        week_start = datetime.utcnow().date()
        week_end = week_start + timedelta(days=7)
        
        due_this_week = Task.query.filter(
            Task.assignments_json.like(f'%"userId": "{current_user.azure_id}"%'),
            Task.due_date.between(week_start, week_end),
            Task.status != TaskStatus.COMPLETED
        ).count()
        
        # Tarefas atrasadas
        overdue_tasks = Task.query.filter(
            Task.assignments_json.like(f'%"userId": "{current_user.azure_id}"%'),
            Task.is_overdue == True,
            Task.status != TaskStatus.COMPLETED
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_assigned': current_user.total_tasks_assigned,
                'completed': current_user.completed_tasks,
                'overdue': overdue_tasks,
                'due_this_week': due_this_week,
                'completion_rate': current_user.task_completion_rate,
                'status_distribution': [
                    {
                        'status': status.value if status else None,
                        'count': count
                    } for status, count in status_stats
                ]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== NOTIFICATIONS API =====
@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """API para listar notificações"""
    try:
        # Parâmetros
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        query = Notification.query.filter_by(user_id=current_user.id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        paginated_notifications = query.order_by(
            Notification.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        notifications_data = []
        for notification in paginated_notifications.items:
            notifications_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type.value if notification.notification_type else None,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'action_url': notification.action_url,
                'action_text': notification.action_text,
                'entity_type': notification.entity_type,
                'entity_id': notification.entity_id
            })
        
        # Contagem de não lidas
        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
        
        return jsonify({
            'success': True,
            'notifications': notifications_data,
            'unread_count': unread_count,
            'pagination': {
                'page': paginated_notifications.page,
                'per_page': paginated_notifications.per_page,
                'total': paginated_notifications.total,
                'pages': paginated_notifications.pages
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/notifications/unread', methods=['GET'])
@login_required
def get_unread_notifications():
    """API para listar notificações não lidas"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
        
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type.value if notification.notification_type else None,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'action_url': notification.action_url,
                'action_text': notification.action_text
            })
        
        return jsonify({
            'success': True,
            'notifications': notifications_data,
            'count': len(notifications_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """API para marcar notificação como lida"""
    try:
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first()
        
        if not notification:
            return jsonify({'success': False, 'error': 'Notificação não encontrada'}), 404
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notificação marcada como lida'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """API para marcar todas as notificações como lidas"""
    try:
        Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Todas as notificações marcadas como lidas'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== DASHBOARD API =====
@api_bp.route('/dashboard/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    """API para obter estatísticas do dashboard"""
    try:
        analytics = AnalyticsService(db)
        kpis = analytics.get_kpis()
        
        # Tarefas recentes
        recent_tasks = Task.query.order_by(
            Task.last_modified.desc()
        ).limit(10).all()
        
        recent_tasks_data = []
        for task in recent_tasks:
            recent_tasks_data.append({
                'id': task.id,
                'title': task.title,
                'status': task.status.value if task.status else None,
                'priority': task.priority.value if task.priority else None,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'planner': task.planner.title if task.planner else None,
                'last_modified': task.last_modified.isoformat() if task.last_modified else None
            })
        
        # Planners com mais tarefas
        from sqlalchemy import func, desc
        busy_planners = db.session.query(
            Planner,
            func.count(Task.id).label('task_count')
        ).join(Task).group_by(Planner.id).order_by(
            desc('task_count')
        ).limit(5).all()
        
        busy_planners_data = []
        for planner, count in busy_planners:
            busy_planners_data.append({
                'id': planner.id,
                'title': planner.title,
                'task_count': count,
                'completion_rate': planner.completion_rate
            })
        
        return jsonify({
            'success': True,
            'kpis': kpis,
            'recent_tasks': recent_tasks_data,
            'busy_planners': busy_planners_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/dashboard/charts', methods=['GET'])
@login_required
def get_dashboard_charts():
    """API para obter dados dos gráficos do dashboard"""
    try:
        analytics = AnalyticsService(db)
        
        # Gráfico de distribuição
        distribution_chart = analytics.get_task_distribution_chart()
        
        # Gráfico de tendência
        trend_chart = analytics.get_completion_trend_chart(days=30)
        
        # Gráfico de workload
        workload_chart = analytics.get_workload_chart()
        
        return jsonify({
            'success': True,
            'charts': {
                'distribution': json.loads(distribution_chart),
                'trend': json.loads(trend_chart),
                'workload': json.loads(workload_chart)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== SYNC API =====
@api_bp.route('/sync', methods=['POST'])
@login_required
def sync_data():
    """API para sincronizar dados com Microsoft Planner"""
    try:
        api = MicrosoftPlannerAPI(current_user.access_token)
        sync = PlannerSync(api, current_user.id)
        
        result = sync.sync_all_data(force=True)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Sincronização completada com sucesso',
                'result': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro na sincronização')
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/sync/status', methods=['GET'])
@login_required
def sync_status():
    """API para verificar status da sincronização"""
    try:
        # Verificar última sincronização
        from app.models import ActivityLog
        last_sync = ActivityLog.query.filter_by(
            user_id=current_user.id,
            activity_type='auto_sync'
        ).order_by(ActivityLog.created_at.desc()).first()
        
        # Verificar se token está válido
        api = MicrosoftPlannerAPI(current_user.access_token)
        token_valid = api.make_request('/me') is not None
        
        return jsonify({
            'success': True,
            'token_valid': token_valid,
            'last_sync': last_sync.created_at.isoformat() if last_sync else None,
            'needs_sync': not last_sync or (datetime.utcnow() - last_sync.created_at).total_seconds() > 3600
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== EXPORT API =====
@api_bp.route('/export/tasks', methods=['POST'])
@login_required
def export_tasks():
    """API para exportar tarefas"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        format = data.get('format', 'excel')
        
        report_service = ReportService(current_user)
        report_data = report_service.generate_task_report(filters)
        
        if format == 'excel':
            output = report_service.export_to_excel(report_data, 'tarefas.xlsx')
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='tarefas.xlsx'
            )
        
        elif format == 'csv':
            # Exportar para CSV
            import csv
            from io import StringIO
            
            si = StringIO()
            writer = csv.writer(si)
            
            # Escrever cabeçalho
            if report_data['dataframe'].columns.any():
                writer.writerow(report_data['dataframe'].columns.tolist())
            
            # Escrever dados
            for row in report_data['dataframe'].itertuples(index=False):
                writer.writerow(row)
            
            output = BytesIO()
            output.write(si.getvalue().encode('utf-8-sig'))
            output.seek(0)
            
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name='tarefas.csv'
            )
        
        else:
            return jsonify({'success': False, 'error': 'Formato não suportado'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== SYSTEM API =====
@api_bp.route('/system/health', methods=['GET'])
def system_health():
    """API de health check"""
    try:
        # Verificar banco de dados
        db.session.execute('SELECT 1')
        
        # Verificar Redis se configurado
        cache_ok = True
        if current_app.config['CACHE_TYPE'] == 'RedisCache':
            try:
                from app import cache
                cache.set('health_check', 'ok', timeout=10)
                cache_ok = cache.get('health_check') == 'ok'
            except:
                cache_ok = False
        
        # Verificar Microsoft Graph API
        api_ok = True
        if current_user and current_user.is_authenticated:
            try:
                api = MicrosoftPlannerAPI(current_user.access_token)
                api_ok = api.make_request('/me') is not None
            except:
                api_ok = False
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'database': 'ok',
                'cache': 'ok' if cache_ok else 'unavailable',
                'microsoft_api': 'ok' if api_ok else 'unavailable'
            },
            'version': current_app.config.get('APP_VERSION', '1.0.0')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/system/stats', methods=['GET'])
@admin_required
def system_stats():
    """API para estatísticas do sistema (admin)"""
    try:
        # Estatísticas gerais
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_tasks = Task.query.count()
        total_planners = Planner.query.count()
        total_groups = Group.query.count()
        
        # Estatísticas de uso
        from sqlalchemy import func
        tasks_per_day = db.session.query(
            func.date(Task.created_date).label('date'),
            func.count(Task.id).label('count')
        ).group_by(func.date(Task.created_date)).order_by(
            func.date(Task.created_date).desc()
        ).limit(30).all()
        
        # Espaço em disco
        import os
        import shutil
        
        total_space, used_space, free_space = shutil.disk_usage("/")
        
        return jsonify({
            'success': True,
            'stats': {
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'admins': User.query.filter_by(is_admin=True).count()
                },
                'tasks': {
                    'total': total_tasks,
                    'completed': Task.query.filter_by(status=TaskStatus.COMPLETED).count(),
                    'overdue': Task.query.filter_by(is_overdue=True).count(),
                    'today': Task.query.filter(
                        func.date(Task.created_date) == datetime.utcnow().date()
                    ).count()
                },
                'planners': total_planners,
                'groups': total_groups,
                'tasks_per_day': [
                    {'date': date.isoformat(), 'count': count} 
                    for date, count in tasks_per_day
                ],
                'storage': {
                    'total_gb': total_space / (1024**3),
                    'used_gb': used_space / (1024**3),
                    'free_gb': free_space / (1024**3),
                    'used_percent': (used_space / total_space) * 100
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== UTILITY API =====
@api_bp.route('/search', methods=['GET'])
@login_required
def search():
    """API de busca global"""
    try:
        query = request.args.get('q', '')
        if not query or len(query) < 2:
            return jsonify({'success': True, 'results': []})
        
        results = {
            'tasks': [],
            'planners': [],
            'groups': [],
            'users': []
        }
        
        # Buscar tarefas
        tasks = Task.query.filter(
            db.or_(
                Task.title.ilike(f'%{query}%'),
                Task.description.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        for task in tasks:
            results['tasks'].append({
                'id': task.id,
                'title': task.title,
                'type': 'task',
                'planner': task.planner.title if task.planner else None,
                'status': task.status.value if task.status else None
            })
        
        # Buscar planners
        planners = Planner.query.filter(
            Planner.title.ilike(f'%{query}%')
        ).limit(10).all()
        
        for planner in planners:
            results['planners'].append({
                'id': planner.id,
                'title': planner.title,
                'type': 'planner',
                'group': planner.group.name if planner.group else None
            })
        
        # Buscar grupos
        groups = Group.query.filter(
            Group.name.ilike(f'%{query}%')
        ).limit(10).all()
        
        for group in groups:
            results['groups'].append({
                'id': group.id,
                'name': group.name,
                'type': 'group'
            })
        
        # Buscar usuários (na base local)
        users = User.query.filter(
            db.or_(
                User.display_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        for user in users:
            results['users'].append({
                'id': user.id,
                'name': user.display_name,
                'email': user.email,
                'type': 'user'
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/lookup/users', methods=['GET'])
@login_required
def lookup_users():
    """API para buscar usuários no Azure AD"""
    try:
        search_term = request.args.get('q', '')
        
        if not search_term or len(search_term) < 2:
            return jsonify({'success': True, 'users': []})
        
        api = MicrosoftPlannerAPI(current_user.access_token)
        
        # Buscar usuários no Azure AD
        result = api.make_request('/users', {
            '$search': f'"displayName:{search_term}" OR "mail:{search_term}"',
            '$select': 'id,displayName,mail,userPrincipalName',
            '$top': 20
        })
        
        if result and 'value' in result:
            users = []
            for user in result['value']:
                users.append({
                    'id': user.get('id'),
                    'display_name': user.get('displayName'),
                    'email': user.get('mail') or user.get('userPrincipalName'),
                    'user_principal_name': user.get('userPrincipalName')
                })
            
            return jsonify({
                'success': True,
                'users': users
            })
        else:
            return jsonify({'success': True, 'users': []})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500