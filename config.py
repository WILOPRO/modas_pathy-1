import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'WCY9521721wcy6373629465318769wcy'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'modas_pathy.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Para subir imágenes
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    # Aumentamos el límite general de subida para permitir varias imágenes
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
