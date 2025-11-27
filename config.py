import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Seguridad
    SECRET_KEY = os.environ.get('WCY9521721wcy9521721WCYwcy') or os.urandom(32).hex()
    
    # Base de datos
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'modas_pathy.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Archivos
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    PROFILE_FOLDER = os.path.join(basedir, 'static', 'perfiles')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Sesión
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Paginación
    PRODUCTS_PER_PAGE = 12
    
    # Información de la tienda
    STORE_NAME = 'Modas Pathy'
    STORE_DESCRIPTION = 'Elegancia de la cholita boliviana'


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
