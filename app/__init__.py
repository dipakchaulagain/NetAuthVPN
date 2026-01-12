from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config
import logging
from logging.handlers import RotatingFileHandler
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # Setup logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/vpn_webui.log', maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('VPN WebUI startup')
    
    # Register blueprints
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.users import users_bp
    from app.security import security_bp
    from app.dns import dns_bp
    from app.accounting import accounting_bp
    from app.services import services_bp
    from app.admin import admin_bp
    from app.settings import settings_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(security_bp, url_prefix='/security')
    app.register_blueprint(dns_bp, url_prefix='/dns')
    app.register_blueprint(accounting_bp, url_prefix='/accounting')
    app.register_blueprint(services_bp, url_prefix='/services')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Context processor for site settings
    @app.context_processor
    def inject_site_settings():
        from app.models import SiteSettings
        settings = SiteSettings.query.first()
        if not settings:
            settings = SiteSettings(site_title='NetAuthVPN', theme_color='#667eea', theme_color_secondary='#764ba2')
        return dict(site_settings=settings)
    
    return app
