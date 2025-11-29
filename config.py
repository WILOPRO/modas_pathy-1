import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Seguridad

    SECRET_KEY = os.environ.get('SECRET_KEY', 'CLAVE_INSEGURA_SOLO_DESARROLLO')

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
    
    # Integraciones
    PAYPAL_CLIENT_ID = os.environ.get(
        'PAYPAL_CLIENT_ID',
        'AeO1E5aHgJEqwrOrMUaKnbs1oggmhrStFM_-nfqk6XxdZ_yR-5p9k6k5hnQvmZo41Q0FIU4bIxN5RZPr'
    )
    PAYPAL_SECRET = os.environ.get(
        'PAYPAL_SECRET',
        'EKNs8k2OKUWI7qeG7lJ-bS2V-MKXfbSL-S3UrzmIA07H7VrE7xhIzmuHsTFKNyX83BH7-jH1DCSWgBIP'
    )
    PAYPAL_RATE = float(os.environ.get('PAYPAL_RATE', 10.5))
    PAYPAL_PERCENT_FEE = float(os.environ.get('PAYPAL_PERCENT_FEE', 0.0349))
    PAYPAL_FIXED_FEE = float(os.environ.get('PAYPAL_FIXED_FEE', 0.30))
    PAYPAL_ENVIRONMENT = os.environ.get('PAYPAL_ENVIRONMENT', 'sandbox')
    
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
