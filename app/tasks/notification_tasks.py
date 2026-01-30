from celery import shared_task
import logging
from datetime import datetime, timedelta

from app import db
from app.models import User, Task, TaskStatus
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

@shared_task
def check_overdue_tasks():
    """Verifica tarefas atrasadas e envia notificações"""
    try:
        overdue_tasks = Task.query.filter(
            Task.is_overdue == True,
            Task.status != TaskStatus.COMPLETED
        ).all()
        
        notification_service = NotificationService()
        
        notified = 0
        for task in overdue_tasks:
            try:
                if notification_service.send_task_overdue_notification(task):
                    notified += 1
            except Exception as e:
                logger.error(f"Erro ao notificar tarefa atrasada {task.id}: {str(e)}")
        
        logger.info(f"Notificações de atraso enviadas: {notified}/{len(overdue_tasks)}")
        return notified
        
    except Exception as e:
        logger.error(f"Erro ao verificar tarefas atrasadas: {str(e)}")
        return 0

@shared_task
def check_upcoming_due_dates():
    """Verifica tarefas com vencimento próximo"""
    try:
        # Tarefas que vencem nas próximas 24h
        tomorrow = datetime.utcnow() + timedelta(hours=24)
        
        upcoming_tasks = Task.query.filter(
            Task.due_date.between(datetime.utcnow(), tomorrow),
            Task.status != TaskStatus.COMPLETED,
            Task.is_overdue == False
        ).all()
        
        notification_service = NotificationService()
        
        notified = 0
        for task in upcoming_tasks:
            try:
                if notification_service.send_task_due_notification(task, hours_before=24):
                    notified += 1
            except Exception as e:
                logger.error(f"Erro ao notificar vencimento próximo {task.id}: {str(e)}")
        
        logger.info(f"Notificações de vencimento enviadas: {notified}/{len(upcoming_tasks)}")
        return notified
        
    except Exception as e:
        logger.error(f"Erro ao verificar vencimentos próximos: {str(e)}")
        return 0

@shared_task
def send_daily_digests():
    """Envia resumos diários para todos os usuários"""
    try:
        users = User.query.filter_by(
            is_active=True,
            email_notifications=True
        ).all()
        
        email_service = EmailService()
        notification_service = NotificationService()
        
        sent = 0
        for user in users:
            try:
                if notification_service.send_daily_digest(user):
                    sent += 1
            except Exception as e:
                logger.error(f"Erro ao enviar resumo diário para {user.email}: {str(e)}")
        
        logger.info(f"Resumos diários enviados: {sent}/{len(users)}")
        return sent
        
    except Exception as e:
        logger.error(f"Erro ao enviar resumos diários: {str(e)}")
        return 0

@shared_task
def cleanup_old_notifications(days: int = 30):
    """Limpa notificações antigas"""
    try:
        from app.models import Notification
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Arquivar notificações antigas lidas
        archived = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).update({'is_archived': True})
        
        # Excluir notificações arquivadas muito antigas
        old_cutoff = datetime.utcnow() - timedelta(days=days * 2)
        deleted = Notification.query.filter(
            Notification.created_at < old_cutoff,
            Notification.is_archived == True
        ).delete()
        
        db.session.commit()
        
        logger.info(f"Notificações arquivadas: {archived}, excluídas: {deleted}")
        return {'archived': archived, 'deleted': deleted}
        
    except Exception as e:
        logger.error(f"Erro ao limpar notificações antigas: {str(e)}")
        return {'archived': 0, 'deleted': 0}