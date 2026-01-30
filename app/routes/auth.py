# app/routes/auth.py - VERSÃO CORRIGIDA
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone, timedelta
import requests
import msal
import os

from app import db
from app.models import User, ActivityLog

auth_bp = Blueprint('auth', __name__)

def init_auth_app(app):
    """Inicializa o blueprint auth com a aplicação Flask"""
    # Esta função pode ser removida se usar a abordagem factory
    return auth_bp

def build_msal_app(cache=None, authority=None):
    """Constroi a aplicação MSAL"""
    return msal.ConfidentialClientApplication(
        current_app.config['AZURE_CLIENT_ID'],
        authority=authority or current_app.config['AZURE_AUTHORITY'],
        client_credential=current_app.config['AZURE_CLIENT_SECRET'],
        token_cache=cache,
    )

@auth_bp.route('/login')
def login():
    """Inicia o fluxo de autenticação OAuth2"""
    session["state"] = str(os.urandom(16))
    
    auth_url = build_msal_app().get_authorization_request_url(
        scopes=current_app.config['AZURE_SCOPES'],
        state=session["state"],
        redirect_uri=url_for("auth.authorized", _external=True)
    )
    
    return redirect(auth_url)

@auth_bp.route('/getAToken')
def authorized():
    """Processa a resposta do Azure AD após autenticação"""
    if request.args.get('state') != session.get("state"):
        flash('Erro de segurança: estado inválido', 'error')
        return redirect(url_for('auth.login'))
    
    if "error" in request.args:
        flash(f"Erro de autenticação: {request.args.get('error_description')}", 'error')
        return redirect(url_for('auth.login'))
    
    app_msal = build_msal_app()
    
    result = app_msal.acquire_token_by_authorization_code(
        request.args['code'],
        scopes=current_app.config['AZURE_SCOPES'],
        redirect_uri=url_for("auth.authorized", _external=True)
    )
    
    if "error" in result:
        flash(f"Erro ao obter token: {result.get('error_description')}", 'error')
        return redirect(url_for('auth.login'))
    
    access_token = result.get("access_token")
    
    # Obter informações do usuário
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        azure_id = user_data.get('id')
        email = user_data.get('mail') or user_data.get('userPrincipalName')
        
        # Buscar ou criar usuário
        user = User.query.filter_by(azure_id=azure_id).first()
        
        now_utc = datetime.now(timezone.utc)
        
        if not user:
            user = User(
                azure_id=azure_id,
                email=email,
                display_name=user_data.get('displayName', 'Usuário'),
                access_token=access_token,
                refresh_token=result.get('refresh_token'),
                token_expires=now_utc + timedelta(seconds=result.get('expires_in', 3600)),
                last_login=now_utc
            )
            db.session.add(user)
        else:
            # Atualizar dados do usuário existente
            user.access_token = access_token
            user.refresh_token = result.get('refresh_token')
            user.token_expires = now_utc + timedelta(seconds=result.get('expires_in', 3600))
            user.last_login = now_utc
            user.display_name = user_data.get('displayName', user.display_name)
        
        db.session.commit()
        
        # Registrar atividade
        activity = ActivityLog(
            user_id=user.id,
            activity_type='login',
            description='Login realizado via Microsoft Azure AD',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(activity)
        db.session.commit()
        
        # Login do usuário
        login_user(user, remember=True)
        
        flash('Login realizado com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    
    flash('Erro ao obter informações do usuário', 'error')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout do usuário"""
    
    # Registrar atividade
    if current_user.is_authenticated:
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type='logout',
            description='Logout realizado',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(activity)
        db.session.commit()
    
    logout_user()
    session.clear()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('auth.login'))