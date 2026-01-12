import os
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'radius')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'radius')
    
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # LDAP Configuration
    LDAP_SERVER = os.environ.get('LDAP_SERVER', '')
    LDAP_IDENTITY = os.environ.get('LDAP_IDENTITY', '')
    LDAP_PASSWORD = os.environ.get('LDAP_PASSWORD', '')
    LDAP_BASE_DN = os.environ.get('LDAP_BASE_DN', '')
    LDAP_USER_FILTER = os.environ.get('LDAP_USER_FILTER', '(sAMAccountName=%{User-Name})')
    
    # OpenVPN Configuration
    VPN_SUBNET = os.environ.get('VPN_SUBNET', '10.8.0.0/24')
    VPN_SERVER_IP = os.environ.get('VPN_SERVER_IP', '192.168.28.70')
    
    # Application Settings
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 25))
    SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', 3600))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # System User (for sudo commands)
    SYSTEM_USER = os.environ.get('SYSTEM_USER', 'dipakc')
    
    # WTForms CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = SESSION_TIMEOUT
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
