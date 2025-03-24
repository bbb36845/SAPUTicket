import os
import sqlite3
from flask import Flask
from flask_login import LoginManager
from PIL import Image

from app.config import get_config

# Opret en global variabel til login_manager
login_manager = LoginManager()

def create_app(config_name='default'):
    """Opret og konfigurer Flask-applikationen."""
    
    # Indlæs konfiguration
    config = get_config()
    
    # Opret Flask-app
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config)
    
    # Sørg for at uploads-mapper eksisterer
    os.makedirs(config.IMAGES_FOLDER, exist_ok=True)
    os.makedirs(config.DOCUMENTS_FOLDER, exist_ok=True)
    
    # Initialiser login manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Initialiser database
    from app.db import init_app as init_db_app
    init_db_app(app)
    
    # Registrer blueprints (vil blive implementeret senere)
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.landlord import landlord_bp
    from app.routes.tenant import tenant_bp
    from app.routes.craftsman import craftsman_bp
    from app.routes.common import common_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(landlord_bp, url_prefix='/udlejer')
    app.register_blueprint(tenant_bp, url_prefix='/lejer')
    app.register_blueprint(craftsman_bp, url_prefix='/craftsman')
    app.register_blueprint(common_bp)
    
    # Konfigurer bruger-loader for login manager
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)
    
    # Tilføj context processor for brugertypen
    @app.context_processor
    def inject_login():
        from flask_login import current_user
        return dict(flask_login=current_user)
    
    # Initialiser databasen hvis den ikke eksisterer
    with app.app_context():
        initialize_database(app)
    
    return app

def initialize_database(app):
    """Initialiser databasen hvis den ikke eksisterer og kør migrationer."""
    from app.db import init_db, run_migrations
    
    # Kontroller om databasefilen eksisterer
    if not os.path.exists(app.config['DATABASE_PATH']):
        # Opret database og kør schema
        init_db()
        print("Database initialiseret.")
    else:
        print("Database eksisterer allerede.")
    
    # Kør migrationer
    if run_migrations():
        print("Database migrationer fuldført.")
    else:
        print("Fejl ved kørsel af database migrationer.")
