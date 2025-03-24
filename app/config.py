import os
from datetime import timedelta

class Config:
    # Basisopsætning
    SECRET_KEY = 'en_super_hemmelig_nøgle'  # Skift dette i produktion!
    DEBUG = True
    
    # Database konfiguration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    DATABASE_NAME = 'tickets.db'
    DATABASE_PATH = os.path.join(PARENT_DIR, DATABASE_NAME)
    SCHEMA_PATH = os.path.join(PARENT_DIR, 'schema.sql')
    
    # Upload konfiguration
    UPLOAD_FOLDER = os.path.join(PARENT_DIR, 'app', 'static', 'uploads')
    IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, 'images')
    DOCUMENTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'documents')
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max filstørrelse
    
    # Session konfiguration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Email konfiguration (skal opdateres med aktuelle værdier)
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'  # SendGrid bruger altid 'apikey' som brugernavn
    MAIL_PASSWORD = os.getenv('SENDGRID_API_KEY', '')  # Hentes fra miljøvariable
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'no-reply@saputicket.dk')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY', Config.SECRET_KEY)
    
    # I produktion kan man overveje at bruge en anden database
    DATABASE_PATH = os.getenv('DATABASE_URL', Config.DATABASE_PATH)

# Vælg den aktive konfiguration baseret på miljøvariable
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Returnerer den aktive konfiguration baseret på miljøvariable."""
    config_name = os.getenv('FLASK_ENV', 'default')
    return config.get(config_name, config['default'])
