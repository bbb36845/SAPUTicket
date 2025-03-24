import os
import sqlite3
import glob
from flask import current_app, g
import click
from flask.cli import with_appcontext

def get_db():
    """Henter en databaseforbindelse og gemmer den i g-objektet"""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE_PATH'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def get_db_connection():
    """Etablerer forbindelse til databasen uden kontekst
    Bruges i model-lag når ingen app-kontekst findes
    """
    import os
    from app.config import get_config
    
    config = get_config()
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def close_db(e=None):
    """Lukker databaseforbindelsen hvis den eksisterer"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialiserer databasen med skema fra schema.sql"""
    db = get_db()
    
    try:
        with open(current_app.config['SCHEMA_PATH'], 'r') as f:
            db.executescript(f.read())
        
        print("Database initialiseret med skema.")
        return True
    except Exception as e:
        print(f"Fejl ved initialisering af database: {e}")
        return False

def run_migrations():
    """Kører alle migrations-scripts i migrations-mappen i rækkefølge"""
    db = get_db()
    migrations_dir = os.path.join(current_app.root_path, '..', 'migrations')
    
    # Kontrollér at migrations-mappen eksisterer
    if not os.path.exists(migrations_dir):
        print(f"Migrations-mappen ikke fundet: {migrations_dir}")
        return False
    
    # Hent alle .sql filer sorteret efter navn
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))
    
    if not migration_files:
        print("Ingen migrations-scripts fundet.")
        return True
    
    # Tabel til at holde styr på kørte migrations
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
    except Exception as e:
        print(f"Fejl ved oprettelse af migrations-tabel: {e}")
        return False
    
    # Hent allerede kørte migrations
    applied_migrations = db.execute('SELECT filename FROM migrations').fetchall()
    applied_filenames = [row['filename'] for row in applied_migrations]
    
    # Kør migrations der ikke allerede er kørt
    success = True
    for migration_file in migration_files:
        filename = os.path.basename(migration_file)
        
        if filename in applied_filenames:
            print(f"Migration allerede kørt: {filename}")
            continue
        
        print(f"Kører migration: {filename}")
        
        try:
            with open(migration_file, 'r') as f:
                script = f.read()
                db.executescript(script)
                
            # Marker migration som kørt
            db.execute('INSERT INTO migrations (filename) VALUES (?)', (filename,))
            db.commit()
            print(f"Migration fuldført: {filename}")
        except Exception as e:
            print(f"Fejl ved kørsel af migration {filename}: {e}")
            success = False
            db.rollback()
            break
    
    return success

def init_app(app):
    """Registrerer database-funktioner med Flask-app"""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(run_migrations_command)

# CLI-kommandoer for database-operationer
@click.command('init-db')
@with_appcontext
def init_db_command():
    """CLI-kommando til at initialisere databasen"""
    init_db()
    click.echo('Database initialiseret.')

@click.command('run-migrations')
@with_appcontext
def run_migrations_command():
    """CLI-kommando til at køre migrations"""
    if run_migrations():
        click.echo('Migrations fuldført.')
    else:
        click.echo('Fejl ved kørsel af migrations.') 