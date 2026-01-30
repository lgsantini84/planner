# refresh_tokens.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User
from datetime import datetime, timedelta
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh_user_token(user):
    """Atualiza token de um usuário específico"""
    try:
        from msal import ConfidentialClientApplication
        
        # Configurações do Azure AD
        client_id = os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('AZURE_CLIENT_SECRET')
        tenant_id = os.environ.get('AZURE_TENANT_ID', 'common')
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        
        if not user.refresh_token:
            logger.error(f"Usuário {user.email} não tem refresh token")
            return False
        
        # Criar aplicativo MSAL
        app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority
        )
        
        # Tentar atualizar o token
        result = app.acquire_token_by_refresh_token(
            refresh_token=user.refresh_token,
            scopes=["https://graph.microsoft.com/.default"]
        )
        
        if "access_token" in result:
            user.access_token = result["access_token"]
            user.refresh_token = result.get("refresh_token", user.refresh_token)
            user.token_expires = datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600))
            
            db.session.commit()
            logger.info(f"Token atualizado para usuário {user.email}")
            return True
        else:
            logger.error(f"Erro ao atualizar token: {result.get('error_description', 'Erro desconhecido')}")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao atualizar token do usuário {user.id}: {str(e)}")
        return False

def refresh_all_tokens():
    """Atualiza tokens de todos os usuários"""
    app = create_app()
    
    with app.app_context():
        users = User.query.filter(
            User.refresh_token.isnot(None),
            User.is_active == True
        ).all()
        
        updated = 0
        total = len(users)
        
        for user in users:
            if refresh_user_token(user):
                updated += 1
        
        logger.info(f"Tokens atualizados: {updated}/{total}")
        return updated

if __name__ == '__main__':
    print("Atualizando tokens de acesso...")
    updated = refresh_all_tokens()
    print(f"Concluído! {updated} tokens atualizados.")