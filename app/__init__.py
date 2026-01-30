# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_caching import Cache

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
cache = Cache()

def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Inicializar extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    
    # Configurar login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    
    # Configurar user_loader
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Registrar filtros customizados (com fallback seguro)
    try:
        from app.utils.filters import register_filters
        register_filters(app)
    except ImportError as e:
        print(f"Warning: Custom filters not found: {e}")
        # Create a simple current_year filter if the module doesn't exist
        @app.template_global()
        def current_year():
            from datetime import datetime
            return datetime.now().year
    
    # Importar e registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.tasks import tasks_bp
    from app.routes.planners import planners_bp
    from app.routes.reports import reports_bp
    from app.routes.settings import settings_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(planners_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    
    # Importar modelos
    from app import models
    
    return app