import logging
from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models import db, Group, Planner, Task, Bucket, User, ActivityLog, TaskStatus, TaskPriority
from app.services.microsoft_api import MicrosoftPlannerAPI

logger = logging.getLogger(__name__)

class PlannerSync:
    def __init__(self, api: MicrosoftPlannerAPI, user_id: int):
        self.api = api
        self.user_id = user_id
        self.sync_stats = {
            'groups': 0,
            'planners': 0,
            'tasks': 0,
            'errors': 0,
            'users_enriched': 0
        }
    
    def sync_all_data(self, force: bool = False) -> Dict:
        """Sincroniza todos os dados"""
        try:
            logger.info(f"Iniciando sincronização completa para usuário {self.user_id}")
            
            # Sincronizar grupos
            groups_result = self.sync_groups(force)
            if not groups_result['success']:
                return groups_result
            
            # Sincronizar planners de cada grupo
            for group in Group.query.filter_by(is_active=True).all():
                self.sync_group_planners(group.id, force)
            
            # Registrar atividade
            activity = ActivityLog(
                user_id=self.user_id,
                activity_type='auto_sync',
                description=f'Sincronização completada: {self.sync_stats}',
                severity='info'
            )
            db.session.add(activity)
            db.session.commit()
            
            return {
                'success': True,
                'stats': self.sync_stats,
                'message': 'Sincronização completada com sucesso'
            }
            
        except Exception as e:
            logger.error(f"Erro na sincronização completa: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'stats': self.sync_stats
            }
    
    def sync_groups(self, force: bool = False) -> Dict:
        """Sincroniza grupos do Azure AD"""
        try:
            groups_data = self.api.get_groups(limit=100)
            
            if not groups_data or 'value' not in groups_data:
                return {'success': False, 'error': 'Nenhum grupo encontrado'}
            
            for group_data in groups_data['value']:
                try:
                    group = Group.query.get(group_data['id'])
                    
                    if group:
                        # Atualizar grupo existente
                        group.name = group_data.get('displayName', group.name)
                        group.email = group_data.get('mail', group.email)
                        group.description = group_data.get('description', group.description)
                        group.group_type = group_data.get('groupTypes', [None])[0] if group_data.get('groupTypes') else None
                        group.visibility = group_data.get('visibility', group.visibility)
                        
                        if group_data.get('createdDateTime'):
                            group.created_date = datetime.fromisoformat(
                                group_data['createdDateTime'].replace('Z', '+00:00')
                            )
                    else:
                        # Criar novo grupo
                        group = Group(
                            id=group_data['id'],
                            name=group_data.get('displayName', ''),
                            email=group_data.get('mail', ''),
                            description=group_data.get('description', ''),
                            group_type=group_data.get('groupTypes', [None])[0] if group_data.get('groupTypes') else None,
                            visibility=group_data.get('visibility', ''),
                            created_date=datetime.fromisoformat(
                                group_data['createdDateTime'].replace('Z', '+00:00')
                            ) if group_data.get('createdDateTime') else None
                        )
                        db.session.add(group)
                    
                    group.last_sync = datetime.now(timezone.utc)
                    self.sync_stats['groups'] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao sincronizar grupo {group_data.get('id')}: {str(e)}")
                    self.sync_stats['errors'] += 1
            
            db.session.commit()
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar grupos: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_group_planners(self, group_id: str, force: bool = False) -> Dict:
        """Sincroniza planners de um grupo"""
        try:
            planners_data = self.api.get_planners(group_id)
            
            if not planners_data or 'value' not in planners_data:
                logger.warning(f"Nenhum planner encontrado ou erro ao buscar planners do grupo {group_id}")
                return {'success': True, 'planners': 0}
            
            for planner_data in planners_data['value']:
                try:
                    self._sync_planner(planner_data, group_id)
                    self.sync_stats['planners'] += 1
                except Exception as e:
                    logger.error(f"Erro ao sincronizar planner {planner_data.get('id')}: {str(e)}")
                    self.sync_stats['errors'] += 1
            
            db.session.commit()
            return {'success': True, 'planners': len(planners_data['value'])}
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar planners do grupo {group_id}: {str(e)}")
            # Não falhar toda a sincronização por causa de um grupo
            self.sync_stats['errors'] += 1
            return {'success': False, 'error': str(e), 'planners': 0}
    
    def sync_planner_tasks(self, planner_id: str, force: bool = False) -> Dict:
        """Sincroniza tarefas de um planner"""
        try:
            tasks_data = self.api.get_planner_tasks(planner_id)
            
            if not tasks_data or 'value' not in tasks_data:
                return {'success': True, 'tasks': 0}
            
            for task_data in tasks_data['value']:
                try:
                    task = Task.query.get(task_data['id'])
                    
                    if task:
                        self._update_task_from_data(task, task_data)
                    else:
                        task = self._create_task_from_data(task_data, planner_id)
                        db.session.add(task)
                    
                    # NOVO: Enriquecer informações dos responsáveis
                    self._enrich_task_assignees(task, task_data)
                    
                    self.sync_stats['tasks'] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao sincronizar tarefa {task_data.get('id')}: {str(e)}")
                    self.sync_stats['errors'] += 1
            
            # Atualizar métricas do planner
            planner = Planner.query.get(planner_id)
            if planner:
                self._update_planner_metrics(planner)
            
            db.session.commit()
            return {'success': True, 'tasks': len(tasks_data['value'])}
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar tarefas do planner {planner_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _sync_planner(self, planner_data: Dict, group_id: str):
        """Sincroniza um planner específico"""
        planner = Planner.query.get(planner_data['id'])
        
        if planner:
            # Atualizar planner existente
            planner.title = planner_data.get('title', planner.title)
            
            if planner_data.get('createdDateTime'):
                planner.created_date = datetime.fromisoformat(
                    planner_data['createdDateTime'].replace('Z', '+00:00')
                )
        else:
            # Criar novo planner
            planner = Planner(
                id=planner_data['id'],
                group_id=group_id,
                title=planner_data.get('title', ''),
                created_date=datetime.fromisoformat(
                    planner_data['createdDateTime'].replace('Z', '+00:00')
                ) if planner_data.get('createdDateTime') else None
            )
            db.session.add(planner)
        
        planner.last_sync = datetime.now(timezone.utc)
        
        # Sincronizar buckets do planner
        self._sync_planner_buckets(planner.id)
        
        # Sincronizar tarefas do planner
        self.sync_planner_tasks(planner.id)
    
    def _sync_planner_buckets(self, planner_id: str):
        """Sincroniza buckets de um planner"""
        try:
            buckets_data = self.api.get_buckets(planner_id)
            
            if not buckets_data or 'value' not in buckets_data:
                return
            
            for bucket_data in buckets_data['value']:
                bucket = Bucket.query.get(bucket_data['id'])
                
                if bucket:
                    bucket.name = bucket_data.get('name', bucket.name)
                    bucket.order_hint = bucket_data.get('orderHint', bucket.order_hint)
                else:
                    bucket = Bucket(
                        id=bucket_data['id'],
                        planner_id=planner_id,
                        name=bucket_data.get('name', ''),
                        order_hint=bucket_data.get('orderHint', '')
                    )
                    db.session.add(bucket)
        
        except Exception as e:
            logger.error(f"Erro ao sincronizar buckets do planner {planner_id}: {str(e)}")
    
    def _update_task_from_data(self, task: Task, task_data: Dict):
        """Atualiza tarefa existente com dados da API"""
        # Informações básicas
        task.title = task_data.get('title', task.title)
        
        # Datas
        if task_data.get('startDateTime'):
            task.start_date = datetime.fromisoformat(
                task_data['startDateTime'].replace('Z', '+00:00')
            )
        
        if task_data.get('dueDateTime'):
            task.due_date = datetime.fromisoformat(
                task_data['dueDateTime'].replace('Z', '+00:00')
            )
        
        # Progresso
        task.percent_complete = task_data.get('percentComplete', 0)
        
        # Bucket
        if task_data.get('bucketId'):
            task.bucket_id = task_data['bucketId']
        
        # Status baseado no completedDateTime e percentComplete
        if task_data.get('completedDateTime'):
            task.completed_date = datetime.fromisoformat(
                task_data['completedDateTime'].replace('Z', '+00:00')
            )
            task.status = TaskStatus.COMPLETED
        else:
            task.completed_date = None
        
        # Determinar status baseado no percentComplete
        if task.percent_complete == 100 and not task.completed_date:
            task.status = TaskStatus.COMPLETED
        elif task.percent_complete > 0:
            task.status = TaskStatus.IN_PROGRESS
        else:
            task.status = TaskStatus.NOT_STARTED
        
        # Verificar se está atrasada
        if task.due_date and task.due_date < datetime.now(timezone.utc) and task.status != TaskStatus.COMPLETED:
            task.is_overdue = True
            # Se está atrasada e não está concluída, marcar como OVERDUE
            if task.status != TaskStatus.COMPLETED:
                task.status = TaskStatus.OVERDUE
        else:
            task.is_overdue = False
        
        # Assignments
        if task_data.get('assignments'):
            task.set_assignments(task_data['assignments'])
        
        # Labels (categorias aplicadas)
        if task_data.get('appliedCategories'):
            labels = []
            for category, applied in task_data['appliedCategories'].items():
                if applied:
                    labels.append(category)
            task.set_labels(labels)
        
        # Priority do Microsoft Planner (0=low, 10=high) para nosso sistema (TaskPriority enum)
        ms_priority = task_data.get('priority', 0)
        if ms_priority >= 9:
            task.priority = TaskPriority.URGENT
        elif ms_priority >= 7:
            task.priority = TaskPriority.HIGH
        elif ms_priority >= 4:
            task.priority = TaskPriority.MEDIUM
        else:
            task.priority = TaskPriority.LOW
    
    def _create_task_from_data(self, task_data: Dict, planner_id: str) -> Task:
        """Cria nova tarefa a partir dos dados da API"""
        # Determinar status inicial
        initial_status = TaskStatus.NOT_STARTED
        if task_data.get('completedDateTime'):
            initial_status = TaskStatus.COMPLETED
        elif task_data.get('percentComplete', 0) == 100:
            initial_status = TaskStatus.COMPLETED
        elif task_data.get('percentComplete', 0) > 0:
            initial_status = TaskStatus.IN_PROGRESS
        
        # Determinar prioridade
        ms_priority = task_data.get('priority', 0)
        if ms_priority >= 9:
            priority = TaskPriority.URGENT
        elif ms_priority >= 7:
            priority = TaskPriority.HIGH
        elif ms_priority >= 4:
            priority = TaskPriority.MEDIUM
        else:
            priority = TaskPriority.LOW
        
        task = Task(
            id=task_data['id'],
            planner_id=planner_id,
            bucket_id=task_data.get('bucketId'),
            title=task_data.get('title', ''),
            percent_complete=task_data.get('percentComplete', 0),
            status=initial_status,
            priority=priority,
            start_date=datetime.fromisoformat(
                task_data['startDateTime'].replace('Z', '+00:00')
            ) if task_data.get('startDateTime') else None,
            due_date=datetime.fromisoformat(
                task_data['dueDateTime'].replace('Z', '+00:00')
            ) if task_data.get('dueDateTime') else None,
            completed_date=datetime.fromisoformat(
                task_data['completedDateTime'].replace('Z', '+00:00')
            ) if task_data.get('completedDateTime') else None,
            created_date=datetime.fromisoformat(
                task_data['createdDateTime'].replace('Z', '+00:00')
            ) if task_data.get('createdDateTime') else datetime.now(timezone.utc)
        )
        
        # Assignments
        if task_data.get('assignments'):
            task.set_assignments(task_data['assignments'])
        
        # Labels
        if task_data.get('appliedCategories'):
            labels = []
            for category, applied in task_data['appliedCategories'].items():
                if applied:
                    labels.append(category)
            task.set_labels(labels)
        
        # Verificar se está atrasada
        if task.due_date and task.due_date < datetime.now(timezone.utc) and task.status != TaskStatus.COMPLETED:
            task.is_overdue = True
            task.status = TaskStatus.OVERDUE
        
        return task
    
    def _enrich_task_assignees(self, task: Task, task_data: Dict):
        """
        NOVO: Enriquece as informações dos responsáveis da tarefa
        buscando dados completos dos usuários no Azure AD e salvando no banco local
        """
        try:
            assignments = task_data.get('assignments', {})
            enriched_assignments = {}
            
            for user_id, assignment_info in assignments.items():
                # Verificar se o usuário já existe no banco
                user = User.query.filter_by(azure_id=user_id).first()
                
                if not user:
                    # Buscar informações completas do usuário no Azure AD
                    try:
                        user_data = self.api.get_user_details(user_id)
                        
                        if user_data:
                            # Obter telefone com fallback seguro
                            phone = user_data.get('mobilePhone')
                            if not phone:
                                business_phones = user_data.get('businessPhones', [])
                                phone = business_phones[0] if business_phones else None
                            
                            # Criar ou atualizar usuário no banco
                            user = User(
                                azure_id=user_id,
                                email=user_data.get('mail') or user_data.get('userPrincipalName'),
                                display_name=user_data.get('displayName', 'Usuário'),
                                job_title=user_data.get('jobTitle'),
                                department=user_data.get('department'),
                                phone=phone,
                                is_active=False  # Usuários sincronizados começam inativos até fazerem login
                            )
                            db.session.add(user)
                            self.sync_stats['users_enriched'] += 1
                            logger.info(f"Usuário {user_id} adicionado ao banco: {user.display_name}")
                        else:
                            # NOVO: Usuário não encontrado (404), usar dados do assignment
                            logger.warning(f"Usuário {user_id} não encontrado no Azure AD, usando dados do assignment")
                    
                    except Exception as e:
                        # NOVO: Se for 404, é esperado - usuário foi removido do Azure AD
                        error_msg = str(e)
                        if "404" in error_msg or "Not Found" in error_msg:
                            logger.info(f"Usuário {user_id} não existe mais no Azure AD (removido ou inativado)")
                        else:
                            logger.warning(f"Não foi possível buscar detalhes do usuário {user_id}: {error_msg}")
                
                # Adicionar informações ao assignment
                enriched_assignments[user_id] = {
                    'assignedDateTime': assignment_info.get('assignedDateTime', ''),
                    'orderHint': assignment_info.get('orderHint', ''),
                    'userDisplayName': user.display_name if user else 'Usuário (Removido)',
                    'userEmail': user.email if user else ''
                }
            
            # Atualizar assignments da tarefa com informações enriquecidas
            if enriched_assignments:
                task.set_assignments(enriched_assignments)
        
        except Exception as e:
            logger.error(f"Erro ao enriquecer responsáveis da tarefa {task.id}: {str(e)}")
    
    def _update_planner_metrics(self, planner: Planner):
        """Atualiza métricas calculadas do planner"""
        try:
            tasks = Task.query.filter_by(planner_id=planner.id).all()
            
            planner.total_tasks = len(tasks)
            planner.completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
            planner.in_progress_tasks = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
            planner.not_started_tasks = sum(1 for t in tasks if t.status == TaskStatus.NOT_STARTED)
            planner.overdue_tasks = sum(1 for t in tasks if t.is_overdue)
            planner.blocked_tasks = sum(1 for t in tasks if t.is_blocked)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar métricas do planner {planner.id}: {str(e)}")