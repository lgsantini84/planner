# config.py - VERSÃO CORRIGIDA
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Configurações básicas
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Banco de dados - USANDO SQLITE POR PADRÃO
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///planner_dashboard.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Se usar PostgreSQL, configure estas opções
    if SQLALCHEMY_DATABASE_URI.startswith('postgresql'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(os.environ.get('DATABASE_POOL_SIZE', 10)),
            'max_overflow': int(os.environ.get('DATABASE_MAX_OVERFLOW', 20)),
            'pool_recycle': int(os.environ.get('DATABASE_POOL_RECYCLE', 3600)),
            'pool_pre_ping': True
        }
    
    # Microsoft Graph API
    MS_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    
    # Azure AD
    AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID') or ''
    AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET') or ''
    AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID') or 'common'
    AZURE_AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    AZURE_REDIRECT_PATH = "/getAToken"
    AZURE_SCOPES = [
        "User.Read",
        "User.Read.All",
        "Directory.Read.All",
        "Group.Read.All",
        "GroupMember.Read.All",
        "Tasks.ReadWrite",
        "Tasks.ReadWrite.Shared",
        "Calendars.ReadWrite",
    ]
    
    # URL base
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')
    APP_NAME = os.environ.get('APP_NAME', 'Microsoft Planner Dashboard PRO')
    
    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@planner-dashboard.com')
    
    # Cache
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache')
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Limites
    MAX_GROUPS_TO_PROCESS = int(os.environ.get('MAX_GROUPS_TO_PROCESS', 100))
    MAX_TASKS_PER_PLANNER = int(os.environ.get('MAX_TASKS_PER_PLANNER', 1000))
    
    # Features
    ENABLE_CREATE_TASKS = os.environ.get('ENABLE_CREATE_TASKS', 'True').lower() == 'true'
    ENABLE_EDIT_TASKS = os.environ.get('ENABLE_EDIT_TASKS', 'True').lower() == 'true'
    ENABLE_DELETE_TASKS = os.environ.get('ENABLE_DELETE_TASKS', 'True').lower() == 'true'
    ENABLE_BULK_OPERATIONS = os.environ.get('ENABLE_BULK_OPERATIONS', 'True').lower() == 'true'
    ENABLE_EMAIL_NOTIFICATIONS = os.environ.get('ENABLE_EMAIL_NOTIFICATIONS', 'True').lower() == 'true'
    
    # UI/UX
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 50))
    DEFAULT_THEME = os.environ.get('DEFAULT_THEME', 'light')
    AVAILABLE_THEMES = ['light', 'dark', 'corporate']
    
    # Notificações
    NOTIFICATION_CHECK_INTERVAL = int(os.environ.get('NOTIFICATION_CHECK_INTERVAL', 300))
    OVERDUE_TASK_REMINDER_HOURS = int(os.environ.get('OVERDUE_TASK_REMINDER_HOURS', 24))
    
    # Relatórios
    REPORT_FORMATS = ['excel', 'csv', 'pdf']
    REPORT_SCHEDULES = ['daily', 'weekly', 'monthly', 'quarterly', 'custom']
    
    # Internacionalização
    DEFAULT_LANGUAGE = os.environ.get('DEFAULT_LANGUAGE', 'pt-BR')
    SUPPORTED_LANGUAGES = ['pt-BR', 'en-US', 'es-ES']
    
    # Segurança
    RATE_LIMIT = os.environ.get('RATE_LIMIT', '100 per hour')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    
    # Admin
    ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', '').split(',')