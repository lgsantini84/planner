from celery import shared_task
import logging
from datetime import datetime

from app import db
from app.models import User
from app.services.microsoft_api import MicrosoftPlannerAPI
from app.services.planner_sync import PlannerSync

logger = logging.getLogger(__name__)

@shared_task
def sync_user_data(user_id: int):
    """Tarefa para sincronizar dados do usuário"""
    try:
        user = User.query.get(user_id)
        if not user or not user.access_token:
            logger.warning(f"Usuário {user_id} não encontrado ou sem token")
            return False
        
        api = MicrosoftPlannerAPI(user.access_token)
        sync = PlannerSync(api, user_id)
        
        result = sync.sync_all_data(force=False)
        return result['success']
        
    except Exception as e:
        logger.error(f"Erro na sincronização do usuário {user_id}: {str(e)}")
        return False

@shared_task
def sync_all_active_users():
    """Sincroniza dados de todos os usuários ativos"""
    try:
        active_users = User.query.filter_by(is_active=True).all()
        
        results = []
        for user in active_users:
            result = sync_user_data.delay(user.id)
            results.append(result)
        
        logger.info(f"Iniciada sincronização para {len(results)} usuários")
        return len(results)
        
    except Exception as e:
        logger.error(f"Erro na sincronização global: {str(e)}")
        return 0

@shared_task
def refresh_tokens():
    """Atualiza tokens de acesso expirados"""
    try:
        from app.services.microsoft_api import refresh_access_token
        
        users = User.query.filter(
            User.token_expires < datetime.utcnow()
        ).all()
        
        refreshed = 0
        for user in users:
            try:
                new_token = refresh_access_token(user.refresh_token)
                if new_token:
                    user.access_token = new_token['access_token']
                    user.token_expires = datetime.utcnow() + timedelta(
                        seconds=new_token['expires_in']
                    )
                    refreshed += 1
            except Exception as e:
                logger.error(f"Erro ao atualizar token do usuário {user.id}: {str(e)}")
        
        db.session.commit()
        logger.info(f"Tokens atualizados: {refreshed}/{len(users)}")
        return refreshed
        
    except Exception as e:
        logger.error(f"Erro ao atualizar tokens: {str(e)}")
        return 0