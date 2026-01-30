# app/routes/tasks.py - VERSÃO CORRIGIDA
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app.models import db, Task, Planner, Group, SavedFilter, TaskComment, TaskChange, User
from app.services.report_service import ReportService
from app.utils.task_filters import TaskFilter
from app.services.email_service import EmailService
from app.services.analytics_service import AnalyticsService
import json

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@tasks_bp.route('/')
@login_required
def list_tasks():
    """Lista de tarefas com filtros"""
    try:
        # Obter parâmetros de filtro
        filter_params = request.args.to_dict()
        
        # Converter para dict e remover parâmetros de paginação
        query_params = filter_params.copy()
        query_params.pop('page', None)
        query_params.pop('per_page', None)
        
        # Aplicar filtros
        query = Task.query.join(Planner, Planner.id == Task.planner_id)
        query = TaskFilter.apply_filters(query, query_params)
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        tasks = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Enriquecer tarefas com informações dos responsáveis
        # IMPORTANTE: Adicionar como atributo temporário, não converter para dict
        for task in tasks.items:
            # Obter nomes reais dos responsáveis
            assignments = task.get_assignments()
            assignees = []
            for user_id, assignment in assignments.items():
                user = User.query.filter_by(azure_id=user_id).first()
                if user:
                    assignees.append({
                        'id': user_id,
                        'name': user.display_name,
                        'email': user.email
                    })
                else:
                    # Fallback para informações do JSON
                    assignees.append({
                        'id': user_id,
                        'name': assignment.get('userDisplayName', 'Usuário'),
                        'email': assignment.get('userEmail', '')
                    })
            
            # Adicionar como atributo temporário ao objeto Task
            task.assignees_info = assignees
        
        # Obter planners e grupos para filtros
        planners = Planner.query.all()
        groups = Group.query.filter_by(is_active=True).all()
        
        # Filtros salvos
        saved_filters = SavedFilter.query.filter_by(user_id=current_user.id).all()
        
        # CORREÇÃO: Usar datetime com timezone aware
        now_date = datetime.now(timezone.utc)
        
        return render_template('tasks/list.html',
                             tasks=tasks,
                             planners=planners,
                             groups=groups,
                             saved_filters=saved_filters,
                             filter_params=query_params,
                             now_date=now_date,
                             request_args=request.args)
        
    except Exception as e:
        current_app.logger.error(f'Erro ao carregar tarefas: {str(e)}', exc_info=True)
        flash(f'Erro ao carregar tarefas: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@tasks_bp.route('/<task_id>')
@login_required
def task_detail(task_id):
    """Detalhes da tarefa"""
    try:
        task = Task.query.get_or_404(task_id)
        comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_date.desc()).all()
        changes = TaskChange.query.filter_by(task_id=task_id).order_by(TaskChange.changed_at.desc()).all()
        
        # Enriquecer responsáveis com informações dos usuários
        assignments = task.get_assignments()
        assignees = []
        for user_id, assignment in assignments.items():
            user = User.query.filter_by(azure_id=user_id).first()
            if user:
                assignees.append({
                    'id': user_id,
                    'name': user.display_name,
                    'email': user.email,
                    'job_title': user.job_title,
                    'department': user.department
                })
            else:
                assignees.append({
                    'id': user_id,
                    'name': assignment.get('userDisplayName', 'Usuário'),
                    'email': assignment.get('userEmail', '')
                })
        
        return render_template('tasks/detail.html',
                             task=task,
                             assignees=assignees,
                             comments=comments,
                             changes=changes)
        
    except Exception as e:
        current_app.logger.error(f'Erro ao carregar tarefa {task_id}: {str(e)}', exc_info=True)
        flash(f'Erro ao carregar tarefa: {str(e)}', 'error')
        return redirect(url_for('tasks.list_tasks'))

@tasks_bp.route('/api/save-filter', methods=['POST'])
@login_required
def save_filter():
    """Salva um filtro"""
    try:
        data = request.get_json()
        
        filter_obj = TaskFilter.save_filter(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            filters=data.get('filters'),
            is_global=data.get('is_global', False)
        )
        
        return jsonify({
            'success': True,
            'filter': {
                'id': filter_obj.id,
                'name': filter_obj.name,
                'description': filter_obj.description
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Erro ao salvar filtro: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@tasks_bp.route('/api/export', methods=['POST'])
@login_required
def export_tasks():
    """Exporta tarefas"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        format = data.get('format', 'excel')
        
        report_service = ReportService(current_user)
        report_data = report_service.generate_task_report(filters)
        
        # Implementar exportação conforme o formato
        # Por enquanto, retornar JSON de exemplo
        return jsonify({
            'success': True,
            'message': 'Exportação em desenvolvimento',
            'data_count': len(report_data.get('dataframe', [])) if 'dataframe' in report_data else 0
        })
        
    except Exception as e:
        current_app.logger.error(f'Erro ao exportar tarefas: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@tasks_bp.route('/api/bulk-update', methods=['POST'])
@login_required
def bulk_update():
    """Atualização em massa de tarefas"""
    try:
        from app.models import TaskStatus, TaskPriority
        
        data = request.get_json()
        task_ids = data.get('task_ids', [])
        updates = data.get('updates', {})
        
        if not task_ids:
            return jsonify({'success': False, 'error': 'Nenhuma tarefa selecionada'}), 400
        
        # Atualizar cada tarefa
        for task_id in task_ids:
            task = Task.query.get(task_id)
            if task:
                # Registrar mudança
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
                    task.status = TaskStatus(updates['status'])  # Converter string para enum
                if 'priority' in updates:
                    task.priority = TaskPriority(int(updates['priority']))  # Converter para enum
                if 'percent_complete' in updates:
                    task.percent_complete = updates['percent_complete']
                
                task.last_modified = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({'success': True, 'updated': len(task_ids)})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro na atualização em massa: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500