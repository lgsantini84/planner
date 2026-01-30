# app.py - VERSÃO FINAL
import os
import sys
import logging
from app import create_app, db

def setup_logging():
    """Configuração do sistema de logging"""
    # Criar diretórios necessários
    directories = ['logs', 'reports', 'uploads', 'backups', 'static/themes']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # Configurar logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configurar handlers
    handlers = [
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configurado com sucesso")
    return logger

def init_database(app):
    """Inicializa o banco de dados com dados padrão"""
    with app.app_context():
        try:
            # Criar todas as tabelas
            db.create_all()
            logging.info("Tabelas do banco criadas/verificadas")
        except Exception as e:
            logging.error(f"Erro ao criar tabelas: {str(e)}")
            return
        
        from app.models import SystemSetting
        
        # Criar configurações padrão do sistema
        default_settings = [
            {'key': 'app_name', 'value': 'Microsoft Planner Dashboard PRO', 'value_type': 'string', 'category': 'general'},
            {'key': 'enable_registration', 'value': 'false', 'value_type': 'boolean', 'category': 'security'},
            {'key': 'maintenance_mode', 'value': 'false', 'value_type': 'boolean', 'category': 'system'},
            {'key': 'default_theme', 'value': 'light', 'value_type': 'string', 'category': 'ui'},
            {'key': 'session_timeout', 'value': '3600', 'value_type': 'integer', 'category': 'security'},
        ]
        
        for setting in default_settings:
            if not SystemSetting.query.filter_by(key=setting['key']).first():
                sys_setting = SystemSetting(**setting)
                db.session.add(sys_setting)
        
        try:
            db.session.commit()
            logging.info("Configurações padrão inicializadas")
        except Exception as e:
            logging.error(f"Erro ao inicializar configurações: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    # Configurar logging primeiro
    logger = setup_logging()
    
    try:
        # Criar aplicação usando a factory
        app = create_app()
        
        # Inicializar banco de dados
        init_database(app)
        
        print("=" * 60)
        print(f"{app.config.get('APP_NAME', 'Planner Dashboard')}")
        print("=" * 60)
        print(f"Servidor: http://localhost:5000")
        print(f"Modo: {'Development' if app.config['DEBUG'] else 'Production'}")
        print(f"Banco: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Tema padrão: {app.config.get('DEFAULT_THEME', 'light')}")
        print("-" * 60)
        print("Recursos disponíveis:")
        print("  • Dashboard com gráficos e KPIs")
        print("  • Filtros avançados e salvos")
        print("  • Relatórios personalizados")
        print("  • Notificações por email")
        print("  • Temas claro/escuro/corporativo")
        print("  • Sincronização automática")
        print("=" * 60)
        
        # Executar aplicação
        app.run(
            debug=app.config.get('DEBUG', True),
            host='0.0.0.0',
            port=5000,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Erro ao iniciar aplicação: {str(e)}", exc_info=True)
        print(f"❌ Erro crítico: {str(e)}")
        sys.exit(1)