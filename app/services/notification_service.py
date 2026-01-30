import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import or_, and_

from app.models import db, Notification, User, Task, TaskStatus, NotificationType
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, app=None):
        self.app = app
        self.email_service = EmailService(app) if app else None
    
    def send_task_assignment_notification(self, task: Task, assignee_id: str):
        """Envia notificação quando uma tarefa é atribuída"""
        try:
            # Obter informações do responsável
            assignments = task.get_assignments()
            assignment_info = assignments.get(assignee_id)
            
            if not assignment_info:
                return False
            
            user = User.query.filter_by(azure_id=assignee_id).first()
            if not user or not user.email:
                return False
            
            # Criar notificação no banco
            notification = Notification(
                user_id=user.id,
                title='Nova tarefa atribuída',
                message=f'Você foi atribuído à tarefa: {task.title}',
                notification_type=NotificationType.TASK_ASSIGNED,
                action_url=f'/tasks/{task.id}',
                action_text='Ver Tarefa',
                entity_type='task',
                entity_id=task.id
            )
            db.session.add(notification)
            
            # Enviar email se configurado
            if user.email_notifications and self.email_service:
                self.email_service.send_task_notification(
                    task=task,
                    notification_type='assigned',
                    recipients=[user.email]
                )
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de atribuição: {str(e)}")
            return False
    
    def send_task_due_notification(self, task: Task, hours_before: int = 24):
        """Envia notificação antes do vencimento da tarefa"""
        try:
            if not task.due_date or task.status == TaskStatus.COMPLETED:
                return False
            
            # Verificar se a tarefa está próxima do vencimento
            time_until_due = task.due_date - datetime.utcnow()
            if timedelta(hours=0) < time_until_due <= timedelta(hours=hours_before):
                
                # Notificar todos os responsáveis
                assignments = task.get_assignments()
                for user_id, assignment_info in assignments.items():
                    user = User.query.filter_by(azure_id=user_id).first()
                    if user:
                        # Criar notificação
                        notification = Notification(
                            user_id=user.id,
                            title='Tarefa próxima do vencimento',
                            message=f'A tarefa "{task.title}" vence em {hours_before}h',
                            notification_type=NotificationType.WARNING,
                            action_url=f'/tasks/{task.id}',
                            action_text='Ver Tarefa',
                            entity_type='task',
                            entity_id=task.id
                        )
                        db.session.add(notification)
                        
                        # Enviar email
                        if user.email_notifications and self.email_service:
                            self.email_service.send_task_notification(
                                task=task,
                                notification_type='due_reminder',
                                recipients=[user.email]
                            )
                
                db.session.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de vencimento: {str(e)}")
            return False
    
    def send_task_overdue_notification(self, task: Task):
        """Envia notificação quando uma tarefa está atrasada"""
        try:
            if not task.is_overdue or task.status == TaskStatus.COMPLETED:
                return False
            
            assignments = task.get_assignments()
            for user_id, assignment_info in assignments.items():
                user = User.query.filter_by(azure_id=user_id).first()
                if user:
                    # Criar notificação
                    notification = Notification(
                        user_id=user.id,
                        title='Tarefa atrasada',
                        message=f'A tarefa "{task.title}" está atrasada',
                        notification_type=NotificationType.ERROR,
                        action_url=f'/tasks/{task.id}',
                        action_text='Ver Tarefa',
                        entity_type='task',
                        entity_id=task.id
                    )
                    db.session.add(notification)
                    
                    # Enviar email
                    if user.email_notifications and self.email_service:
                        self.email_service.send_task_notification(
                            task=task,
                            notification_type='overdue',
                            recipients=[user.email]
                        )
            
            # Notificar também o gerente/administrador
            self._notify_managers_about_overdue_task(task)
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de atraso: {str(e)}")
            return False
    
    def send_task_completion_notification(self, task: Task, completed_by: User):
        """Envia notificação quando uma tarefa é concluída"""
        try:
            if task.status != TaskStatus.COMPLETED:
                return False
            
            # Notificar todos os responsáveis
            assignments = task.get_assignments()
            for user_id, assignment_info in assignments.items():
                user = User.query.filter_by(azure_id=user_id).first()
                if user and user.id != completed_by.id:
                    notification = Notification(
                        user_id=user.id,
                        title='Tarefa concluída',
                        message=f'A tarefa "{task.title}" foi concluída por {completed_by.display_name}',
                        notification_type=NotificationType.SUCCESS,
                        action_url=f'/tasks/{task.id}',
                        action_text='Ver Tarefa',
                        entity_type='task',
                        entity_id=task.id
                    )
                    db.session.add(notification)
            
            # Notificar criador da tarefa (se diferente)
            # Implementar conforme necessário
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de conclusão: {str(e)}")
            return False
    
    def send_daily_digest(self, user: User):
        """Envia resumo diário para o usuário"""
        try:
            if not user.email or not user.email_notifications:
                return False
            
            # Obter tarefas do dia
            today = datetime.utcnow().date()
            
            # Tarefas vencendo hoje
            due_today = Task.query.filter(
                Task.assignments_json.like(f'%"userId": "{user.azure_id}"%'),
                Task.status != TaskStatus.COMPLETED,
                db.func.date(Task.due_date) == today
            ).all()
            
            # Tarefas atrasadas
            overdue_tasks = Task.query.filter(
                Task.assignments_json.like(f'%"userId": "{user.azure_id}"%'),
                Task.is_overdue == True,
                Task.status != TaskStatus.COMPLETED
            ).all()
            
            # Tarefas concluídas recentemente
            recent_completed = Task.query.filter(
                Task.assignments_json.like(f'%"userId": "{user.azure_id}"%'),
                Task.status == TaskStatus.COMPLETED,
                db.func.date(Task.completed_date) == today
            ).all()
            
            if self.email_service:
                return self.email_service.send_daily_digest(
                    user=user,
                    tasks_due=due_today,
                    tasks_overdue=overdue_tasks,
                    tasks_completed=recent_completed
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao enviar resumo diário: {str(e)}")
            return False
    
    def send_system_notification(self, users: List[User], title: str, message: str, 
                               notification_type: NotificationType = NotificationType.INFO,
                               action_url: str = None):
        """Envia notificação do sistema para múltiplos usuários"""
        try:
            for user in users:
                notification = Notification(
                    user_id=user.id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    action_url=action_url,
                    entity_type='system'
                )
                db.session.add(notification)
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação do sistema: {str(e)}")
            return False
    
    def mark_as_read(self, notification_id: int, user_id: int):
        """Marca uma notificação como lida"""
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                user_id=user_id
            ).first()
            
            if notification:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
                db.session.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao marcar notificação como lida: {str(e)}")
            return False
    
    def mark_all_as_read(self, user_id: int):
        """Marca todas as notificações do usuário como lidas"""
        try:
            Notification.query.filter_by(
                user_id=user_id,
                is_read=False
            ).update({'is_read': True, 'read_at': datetime.utcnow()})
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao marcar todas as notificações como lidas: {str(e)}")
            return False
    
    def get_unread_count(self, user_id: int) -> int:
        """Retorna contagem de notificações não lidas"""
        return Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).count()
    
    def get_recent_notifications(self, user_id: int, limit: int = 10) -> List[Notification]:
        """Retorna notificações recentes"""
        return Notification.query.filter_by(
            user_id=user_id
        ).order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    def cleanup_old_notifications(self, days: int = 30):
        """Remove notificações antigas"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Arquivar notificações antigas lidas
            Notification.query.filter(
                Notification.created_at < cutoff_date,
                Notification.is_read == True
            ).update({'is_archived': True})
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao limpar notificações antigas: {str(e)}")
            return False
    
    def _notify_managers_about_overdue_task(self, task: Task):
        """Notifica gerentes sobre tarefas atrasadas"""
        try:
            # Buscar usuários com papel de gerente/admin
            managers = User.query.filter(
                or_(
                    User.is_admin == True,
                    User.department == 'Management'
                )
            ).all()
            
            for manager in managers:
                if manager.email_notifications and self.email_service:
                    self.email_service.send_task_notification(
                        task=task,
                        notification_type='manager_overdue_alert',
                        recipients=[manager.email]
                    )
            
        except Exception as e:
            logger.error(f"Erro ao notificar gerentes: {str(e)}")