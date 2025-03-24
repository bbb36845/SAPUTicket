import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, flash, url_for
import flask_login
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import socket
import uuid
from werkzeug.utils import secure_filename
import image_helpers

app = Flask(__name__)
app.secret_key = 'en_super_hemmelig_nøgle'  # Skift dette i produktion!

# Brug absolut sti til databasen OG schema.sql.
DATABASE = os.path.join(app.root_path, 'tickets.db')
SCHEMA = os.path.join(app.root_path, 'schema.sql')
SCHEMA_UPDATE = os.path.join(app.root_path, 'schema_update.sql')
SCHEMA_UPDATE_BASIC = os.path.join(app.root_path, 'schema_update_basic.sql')
SCHEMA_UPDATE_IMAGES = os.path.join(app.root_path, 'schema_update_images.sql')

# Konfiguration for billedupload
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max filstørrelse

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Sørg for at upload-mappen eksisterer
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Flask-Login opsætning ---
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Fortæl Flask-Login, hvor login-siden er


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['password_hash'], user['role'], user['invitation_token'],
                    user['invited_by'], user['unit_id'])
    return None

# --- Context Processor ---
@app.context_processor
def inject_login():
    return dict(flask_login=flask_login)

# --- User model (til Flask-Login) ---
class User(flask_login.UserMixin):
     def __init__(self, id, username, password_hash, role=None, invitation_token=None, invited_by=None, unit_id=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.invitation_token = invitation_token
        self.invited_by = invited_by
        self.unit_id = unit_id

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialiserer databasen ved at køre schema.sql."""
    try:
        print("init_db() starter...")

        conn = get_db_connection()
        with open(SCHEMA, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        print("init_db() afsluttet uden fejl.")
    except Exception as e:
        print("init_db() fejlede.")
        print(f"Fejl i init_db(): {e}")

def update_db():
    """Opdaterer databasen ved at køre schema_update.sql."""
    try:
        print("update_db() starter...")

        conn = get_db_connection()
        
        # Prøv først med den grundlæggende opdatering
        try:
            print("Forsøger med grundlæggende opdatering...")
            with open(SCHEMA_UPDATE_BASIC, 'r') as f:
                sql_script = f.read()
                print(f"SQL script indlæst: {len(sql_script)} tegn")
                
                # Kør hver SQL-kommando separat for at identificere problemer
                for command in sql_script.split(';'):
                    if command.strip():
                        try:
                            print(f"Udfører SQL-kommando: {command.strip()[:100]}...")
                            conn.execute(command)
                        except Exception as cmd_error:
                            print(f"Fejl ved udførelse af SQL-kommando: {cmd_error}")
                            print(f"Problematisk kommando: {command.strip()}")
                            raise
            
            # Opdater eksisterende rækker med den aktuelle tidsstempel
            print("Opdaterer eksisterende rækker med den aktuelle tidsstempel...")
            conn.execute("UPDATE tickets SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP")
            
            print("Grundlæggende opdatering gennemført.")
        except Exception as e:
            print(f"Fejl ved grundlæggende opdatering: {e}")
            conn.rollback()
            raise
        
        # Prøv derefter med den fulde opdatering
        try:
            print("Forsøger med fuld opdatering...")
            with open(SCHEMA_UPDATE, 'r') as f:
                sql_script = f.read()
                
                # Kør hver SQL-kommando separat for at identificere problemer
                for command in sql_script.split(';'):
                    if command.strip():
                        # Spring over kommandoer, der allerede er kørt i den grundlæggende opdatering
                        if "ADD COLUMN created_at" in command or "ADD COLUMN updated_at" in command or "CREATE TABLE IF NOT EXISTS comments" in command or "CREATE TABLE IF NOT EXISTS ticket_history" in command:
                            print(f"Springer over allerede kørt kommando: {command.strip()[:100]}...")
                            continue
                        
                        try:
                            print(f"Udfører SQL-kommando: {command.strip()[:100]}...")
                            conn.execute(command)
                        except Exception as cmd_error:
                            print(f"Fejl ved udførelse af SQL-kommando: {cmd_error}")
                            print(f"Problematisk kommando: {command.strip()}")
                            # Fortsæt med næste kommando i stedet for at afbryde
                            continue
            
            print("Fuld opdatering gennemført.")
        except Exception as e:
            print(f"Fejl ved fuld opdatering: {e}")
            # Fortsæt alligevel, da den grundlæggende opdatering er gennemført
        
        conn.commit()
        conn.close()
        print("update_db() afsluttet uden fejl.")
        return True
    except Exception as e:
        print("update_db() fejlede.")
        print(f"Fejl i update_db(): {e}")
        return False

def get_user(username):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()

        if user_data:
            user = User(user_data['id'], user_data['username'], user_data['password_hash'], user_data['role'], user_data['invitation_token'], user_data['invited_by'], user_data['unit_id'])
            return user
        else:
            return None
    except Exception as e:
        print(f"Fejl i get_user(): {e}")
        return None
    finally:
        conn.close()

# Kør init_db() HVIS databasen ikke eksisterer.
if not os.path.exists(DATABASE):
    init_db()
else:
    # Tjek om databasen har de nødvendige tabeller
    conn = get_db_connection()
    try:
        # Prøv at hente en række fra comments-tabellen
        conn.execute("SELECT 1 FROM comments LIMIT 1")
    except sqlite3.OperationalError:
        # Hvis tabellen ikke findes, kør update_db()
        print("Opdaterer databasen med nye tabeller...")
        update_db()
    finally:
        conn.close()

@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()  # Opret en cursor
    try:
        # Hent den valgte udlejer (hvis nogen)
        selected_udlejer_id = request.args.get('selected_udlejer_id')
        print(f"DEBUG: selected_udlejer_id: {selected_udlejer_id}")  # DEBUG

        # Hent ALLE udlejere (til dropdown menuen)
        udlejere = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()

        # Initialiser tom liste for tickets og lejere
        tickets = []
        lejere = []
        units = [] #Tilføjet
        properties = [] #Tilføjet

        # Filtrer tickets og lejere baseret på rolle og evt. valgt udlejer
        if flask_login.current_user.is_authenticated:
            if flask_login.current_user.role == 'admin':
                # Admin: Vis alle tickets, og alle lejere (filtreret efter valgt udlejer)
                properties = conn.execute("SELECT * FROM properties").fetchall() #Tilføjet
                units = conn.execute("SELECT units.*, properties.name as property_name FROM units JOIN properties ON units.property_id = properties.id").fetchall() #Tilføjet
                if selected_udlejer_id:
                    # Filtrer tickets baseret på valgt udlejer
                    cur.execute("""
                        SELECT tickets.*, u.username as udlejer_name
                        FROM tickets
                        INNER JOIN units ON tickets.unit_id = units.id
                        INNER JOIN properties ON units.property_id = properties.id
                        LEFT JOIN users u ON tickets.udlejer = u.id
                        WHERE properties.owner_id = ?
                    """, (selected_udlejer_id,))
                    tickets = cur.fetchall()

                    # Filtrer lejere baseret på valgt udlejer.
                    lejere = conn.execute("""
                        SELECT DISTINCT users.*
                        FROM users
                        INNER JOIN units ON users.unit_id = units.id
                        INNER JOIN properties ON units.property_id = properties.id
                        WHERE users.role = 'lejer' AND properties.owner_id = ?
                    """, (selected_udlejer_id,)).fetchall()
                    print(f"DEBUG: Lejere (filtreret): {lejere}")  # DEBUG
                else:
                    #Hvis der ikke er valgt en udlejer, vises alle tickets.
                    tickets = conn.execute('''
                        SELECT t.*, u.username as udlejer_name
                        FROM tickets t
                        LEFT JOIN users u ON t.udlejer = u.id
                    ''').fetchall()
                    lejere = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall() #Og alle lejere.
                    print(f"DEBUG: Lejere (alle): {lejere}")  # DEBUG

            elif flask_login.current_user.role == 'udlejer':
                # Udlejer: Vis kun tickets for egne ejendomme
                cur.execute("""
                    SELECT tickets.*, u.username as udlejer_name
                    FROM tickets
                    INNER JOIN units ON tickets.unit_id = units.id
                    INNER JOIN properties ON units.property_id = properties.id
                    LEFT JOIN users u ON tickets.udlejer = u.id
                    WHERE properties.owner_id = ?
                """, (flask_login.current_user.id,))
                tickets = cur.fetchall()

                #Vis kun tickets, og lejere, der hører under udlejerens ejendomme.
                lejere = conn.execute("""
                    SELECT DISTINCT users.*
                    FROM users
                    JOIN units ON users.unit_id = units.id
                    JOIN properties ON units.property_id = properties.id
                    WHERE users.role = 'lejer' AND properties.owner_id = ?
                """, (flask_login.current_user.id,)).fetchall()
                print(f"DEBUG: Lejere (for udlejer): {lejere}")  # DEBUG
                #Vis alle properties og units, som tilhører den indloggede udlejer.
                properties = conn.execute("SELECT * FROM properties WHERE owner_id = ?", (flask_login.current_user.id,)).fetchall() #Tilføjet
                units = conn.execute("""
                    SELECT units.*, properties.name as property_name
                    FROM units
                    JOIN properties ON units.property_id = properties.id
                    WHERE properties.owner_id = ?
                """, (flask_login.current_user.id,)).fetchall() #Tilføjet

            elif flask_login.current_user.role == 'lejer':
                # Lejer: Vis kun tickets for eget lejemål
                cur.execute('''
                    SELECT t.*, u.username as udlejer_name
                    FROM tickets t
                    LEFT JOIN users u ON t.udlejer = u.id
                    WHERE t.unit_id = ?
                ''', (flask_login.current_user.unit_id,))
                tickets = cur.fetchall()
                #Ingen lejer-dropdown.
                print(f"DEBUG: Lejere (ingen - lejerrolle): {lejere}")  # DEBUG

            #Håndværker kan ikke se noget her.
            else:
                tickets = []
                lejere = []
                udlejere = []
                properties = [] #Tilføjet
                units = [] #Tilføjet
        else:
            flash('Du skal være logget ind for at se tickets.', 'error')
            return redirect(url_for('login')) #Hvis ikke logget ind, redirect til login.
    except sqlite3.OperationalError as e:
        print(f"Fejl ved hentning af tickets: {e}")
        tickets = []
        lejere = [] #Husk at definere users, hvis der opstår fejl.
        udlejere = []
        properties = [] #Tilføjet
        units = [] #Tilføjet
    finally:
        conn.close()
    # Send tickets, lejere, udlejere og selected_udlejer_id med til skabelonen
    return render_template("index.html", tickets=tickets, users=lejere, udlejere=udlejere, properties=properties, units=units, selected_udlejer_id=selected_udlejer_id)

@app.route("/create", methods=["POST"])
@flask_login.login_required
def create_ticket():
    conn = get_db_connection()
    # --- Hent properties, units og users (lejere) til dropdown menuer ---
    try:
        #Hvis det er admin, skal *alle* properties og units hentes.
        if flask_login.current_user.role == 'admin':
            properties = conn.execute("SELECT * FROM properties").fetchall()
            # JOIN for at få ejendommens navn med.
            units = conn.execute("SELECT units.*, properties.name as property_name FROM units JOIN properties ON units.property_id = properties.id").fetchall()
            users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall()
            udlejere = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()  # Hent udlejere

        #Hvis det er en udlejer, skal kun udlejerens egne properties og units hentes.
        elif flask_login.current_user.role == 'udlejer':
            properties = conn.execute("SELECT * FROM properties WHERE owner_id = ?", (flask_login.current_user.id,)).fetchall()
            units = conn.execute("""
                SELECT units.*, properties.name as property_name
                FROM units
                JOIN properties ON units.property_id = properties.id
                WHERE properties.owner_id = ?
            """, (flask_login.current_user.id,)).fetchall()

            # Filtrer lejere baseret på valgt udlejer (hvis nogen)
            selected_udlejer_id = request.form.get('selected_udlejer_id')
            if selected_udlejer_id:
                users = conn.execute("""
                    SELECT DISTINCT users.*
                    FROM users
                    JOIN units ON users.unit_id = units.id
                    JOIN properties ON units.property_id = properties.id
                    WHERE users.role = 'lejer' AND properties.owner_id = ?
                """, (selected_udlejer_id,)).fetchall()
            else:
                users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall() #Vis alle lejere.
            udlejere = [] #Skal defineres.
        #Hvis det er en lejer, skal unit_id hentes fra brugeren, og properties/units er tomme.
        elif flask_login.current_user.role == 'lejer':
            properties = []
            units = []
            users = []
            udlejere = []  # Ingen udlejer-dropdown
        #Hvis det er en håndværker, skal de slet ikke have adgang.
        else:
            flash('Du har ikke tilladelse til at oprette tickets.', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        print(f"Fejl ved hentning af data til create_ticket: {e}")
        flash("Fejl ved hentning af data.", "error")
        return redirect(url_for('index'))  # Or some other error handling
    finally:
        conn.close()

    if request.method == 'POST':
        # --- Modtag data fra form (altid) ---
        # selected_udlejer_id = request.form.get('selected_udlejer_id') #Hent den valgte udlejers ID.
        beskrivelse = request.form["beskrivelse"]
        # udlejer = request.form["udlejer"] #Ikke længere relevant.
        status = "Oprettet"  # Hardcoded for now

        conn = get_db_connection()
        try:
            if flask_login.current_user.role == 'lejer':
                # --- Lejer opretter ticket ---
                lejer = flask_login.current_user.username #Lejers brugernavn.
                unit_id = flask_login.current_user.unit_id #Lejerens unit_id.
                user_id = flask_login.current_user.id #Lejerens user_id
                udlejer = None #Ingen værdi.
                
                # Opret timestamp for oprettelse og opdatering
                import datetime
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if not unit_id:
                    flash('Du er ikke tilknyttet et lejemål og kan ikke oprette en ticket.', 'error')
                    return redirect(url_for('index'))

                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO tickets (lejer, beskrivelse, status, udlejer, user_id, unit_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (lejer, beskrivelse, status, udlejer, user_id, unit_id, current_time, current_time),
                )
                ticket_id = cursor.lastrowid
                
                # Registrer handlingen i ticket-historikken
                add_ticket_history(ticket_id, user_id, 'created', existing_conn=conn)
                
                conn.commit()
                flash('Ticket oprettet!', 'success')

            elif flask_login.current_user.role == 'admin' or flask_login.current_user.role == 'udlejer':
                # --- Admin/udlejer opretter ticket ---
                lejer = request.form['lejer'] #Værdi fra lejer dropdown.
                unit_id_str = request.form.get("unit_id") #Hent unit_id, via get().
                # udlejer = None #Ikke relevant.

                if not unit_id_str:
                    flash('Lejemål skal vælges.', 'error')
                    return render_template("index.html", properties=properties, units=units, users=users, udlejere=udlejere) # selected_udlejer_id=selected_udlejer_id)
                try:
                    unit_id = int(unit_id_str) #Konverter til int.
                except ValueError:
                    flash('Ugyldigt lejemål ID.', 'error')
                    return render_template("index.html", properties=properties, units=units, users=users, udlejere=udlejere) # selected_udlejer_id=selected_udlejer_id)

                #Find udlejer ud fra unit_id:
                cur = conn.cursor()
                cur.execute("SELECT properties.owner_id FROM units JOIN properties ON units.property_id = properties.id WHERE units.id = ?", (unit_id,))
                udlejer_id = cur.fetchone()
                if udlejer_id:
                    udlejer_id = udlejer_id[0]
                else:
                    flash('Kunne ikke finde udlejer for det valgte lejemål.', 'error')
                    return render_template("index.html", properties=properties, units=units, users=users, udlejere=udlejere) # selected_udlejer_id=selected_udlejer_id)

                # Opret timestamp for oprettelse og opdatering
                import datetime
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                user_id = flask_login.current_user.id #Hent user_id for den indloggede bruger.
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO tickets (lejer, beskrivelse, status, udlejer, user_id, unit_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (lejer, beskrivelse, status, udlejer_id, user_id, unit_id, current_time, current_time),
                )
                ticket_id = cursor.lastrowid
                
                # Registrer handlingen i ticket-historikken
                add_ticket_history(ticket_id, user_id, 'created', existing_conn=conn)
                
                conn.commit()
                flash('Ticket oprettet!', 'success')

            else: #hvis det er en håndværker.
                flash('Du har ikke tilladelse til at oprette tickets.', 'error')
                return redirect(url_for('index'))

        except Exception as e:
            print(f"Fejl ved oprettelse af ticket: {e}")
            flash('Fejl ved oprettelse af ticket.', 'error')
            conn.rollback()
        finally:
            conn.close()
        return redirect(url_for('index'))

    else:  # GET request
        # Forbered data til dropdowns, hvis det er en GET request
        # Hent properties, units, users (lejere) og udlejere, afhængigt af rollen
        # (logikken er allerede implementeret ovenfor)
        selected_udlejer_id = request.args.get('selected_udlejer_id') #Tilføjet
        return render_template("index.html", properties=properties, units=units, users=users, udlejere=udlejere, selected_udlejer_id=selected_udlejer_id) #Tilføjet

@app.route("/admin")
@flask_login.login_required
def admin():
    # Kontroller at brugeren er administrator
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        if flask_login.current_user.role == 'udlejer':
            return redirect(url_for('udlejer_dashboard'))
        else:
            return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent filtre fra URL-parametre
        udlejer_filter = request.args.get('udlejer', '')
        status_filter = request.args.get('status', '')
        
        # Hent sorteringsparametre
        sort_by = request.args.get('sort', 'id')  # Standard: Sortér efter ID
        sort_dir = request.args.get('dir', 'desc')  # Standard: Faldende (nyeste først)
        
        # Validér sorteringsparametre for at undgå SQL-injektion
        valid_sort_columns = ['id', 'lejer', 'udlejer', 'status', 'created_at', 'updated_at']
        valid_sort_dirs = ['asc', 'desc']
        
        if sort_by not in valid_sort_columns:
            sort_by = 'id'
        if sort_dir not in valid_sort_dirs:
            sort_dir = 'desc'
        
        # Hent alle unikke udlejere til dropdown
        udlejere = conn.execute('''
            SELECT DISTINCT t.udlejer, u.username 
            FROM tickets t
            LEFT JOIN users u ON t.udlejer = u.id
            ORDER BY u.username
        ''').fetchall()

        # Konverter udlejere til en liste af dictionaries med id og navn
        udlejere_list = []
        for udlejer in udlejere:
            if udlejer['udlejer'] is not None:
                try:
                    # Hvis udlejer er et ID (heltal), hent brugernavnet
                    udlejer_id = int(udlejer['udlejer'])
                    udlejer_user = conn.execute('SELECT username FROM users WHERE id = ?', (udlejer_id,)).fetchone()
                    if udlejer_user:
                        udlejere_list.append({
                            'id': udlejer_id,
                            'name': udlejer_user['username']
                        })
                except (ValueError, TypeError):
                    # Hvis udlejer ikke er et ID, brug værdien direkte
                    udlejere_list.append({
                        'id': udlejer['udlejer'],
                        'name': udlejer['udlejer']
                    })
        
        # Hent alle unikke status-værdier til dropdown
        statuses = conn.execute('SELECT DISTINCT status FROM tickets ORDER BY status').fetchall()

        # Byg SQL-forespørgsel baseret på filtre
        query = '''
            SELECT 
                t.*,
                u.username as creator_name,
                un.address as unit_address,
                p.name as property_name,
                o.username as udlejer_name
            FROM 
                tickets t
            LEFT JOIN 
                users u ON t.user_id = u.id
            LEFT JOIN 
                units un ON t.unit_id = un.id
            LEFT JOIN 
                properties p ON un.property_id = p.id
            LEFT JOIN
                users o ON t.udlejer = o.id
            WHERE 1=1
        '''
        params = []
        
        if udlejer_filter:
            query += ' AND t.udlejer = ?'
            params.append(udlejer_filter)
            
        if status_filter:
            query += ' AND t.status = ?'
            params.append(status_filter)
        
        # Tilføj sortering
        query += f' ORDER BY t.{sort_by} {sort_dir}'
            
        # Udfør forespørgslen
        tickets = conn.execute(query, params).fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af tickets til admin: {e}")
        tickets = []
        udlejere = []
        statuses = []
    finally:
        conn.close()
    
    # Find udlejerens navn, hvis der er valgt en udlejer
    current_udlejer_name = None
    if udlejer_filter:
        for udlejer in udlejere_list:
            if str(udlejer['id']) == str(udlejer_filter):
                current_udlejer_name = udlejer['name']
                break
    
    return render_template("admin.html", tickets=tickets, udlejere=udlejere_list, statuses=statuses, 
                          current_udlejer=udlejer_filter, current_udlejer_name=current_udlejer_name, current_status=status_filter,
                          sort_by=sort_by, sort_dir=sort_dir)

@app.route("/delete/<int:ticket_id>", methods=["POST"])
@flask_login.login_required
def delete_ticket(ticket_id):
    conn = get_db_connection()
    try:
        # Hent ticket
        ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'admin':
            # Admin har adgang til alle tickets
            pass
        elif flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun slette tickets på deres egne ejendomme
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at slette denne ticket.', 'error')
                return redirect(url_for('index'))
        else:
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))
        
        # Slet ticket
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
        flash('Ticket slettet!', 'success')
    except Exception as e:
        print(f"Fejl ved sletning af ticket: {e}")
        flash(f'Fejl ved sletning af ticket: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    if flask_login.current_user.role == 'admin':
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('udlejer_dashboard'))

@app.route("/edit/<int:ticket_id>", methods=["GET", "POST"])
@flask_login.login_required
def edit_ticket(ticket_id):
    conn = get_db_connection()
    # Definer variabler uden for try-blokken, så de er tilgængelige i except-blokken
    udlejere = []
    users = []
    craftsmen = []
    comments = []
    history = []
    images = []
    ticket = None
    
    try:
        # Hent ticket
        ticket = conn.execute('''
            SELECT t.*, u.username as udlejer_name, c.username as craftsman_name
            FROM tickets t
            LEFT JOIN users u ON t.udlejer = u.id
            LEFT JOIN users c ON t.craftsman_id = c.id
            WHERE t.id = ?
        ''', (ticket_id,)).fetchone()
        
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'admin':
            # Admin har adgang til alle tickets
            pass
        elif flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun redigere tickets på deres egne ejendomme
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at redigere denne ticket.', 'error')
                return redirect(url_for('index'))
        else:
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))

        if request.method == 'POST':
            # Hent den gamle ticket for at sammenligne værdier
            old_ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
            
            lejer = request.form["lejer"]
            beskrivelse = request.form["beskrivelse"]
            status = request.form["status"]
            udlejer = request.form["udlejer"]
            craftsman_id = request.form.get("craftsman_id", "")
            
            # Hvis craftsman_id er en tom streng, sæt den til None
            if craftsman_id == "":
                craftsman_id = None
            else:
                # Konverter craftsman_id til et heltal, hvis det ikke er None
                try:
                    craftsman_id = int(craftsman_id)
                except (ValueError, TypeError):
                    craftsman_id = None
                    
            print(f"DEBUG: craftsman_id = {craftsman_id}, type = {type(craftsman_id)}")

            # Opdater ticket med craftsman_id
            try:
                conn.execute(
                    "UPDATE tickets SET lejer = ?, beskrivelse = ?, status = ?, udlejer = ?, craftsman_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (lejer, beskrivelse, status, udlejer, craftsman_id, ticket_id),
                )
                
                # Registrer ændringer i ticket-historikken
                if old_ticket['status'] != status:
                    add_ticket_history(ticket_id, flask_login.current_user.id, 'status_changed', old_ticket['status'], status, existing_conn=conn)
                
                if old_ticket['beskrivelse'] != beskrivelse:
                    add_ticket_history(ticket_id, flask_login.current_user.id, 'description_changed', None, None, existing_conn=conn)
                    
                if old_ticket['lejer'] != lejer:
                    add_ticket_history(ticket_id, flask_login.current_user.id, 'tenant_changed', old_ticket['lejer'], lejer, existing_conn=conn)
                    
                if old_ticket['udlejer'] != udlejer:
                    add_ticket_history(ticket_id, flask_login.current_user.id, 'landlord_changed', old_ticket['udlejer'], udlejer, existing_conn=conn)
                    
                # Registrer ændring af håndværker
                old_craftsman_id = old_ticket['craftsman_id'] if 'craftsman_id' in old_ticket.keys() else None
                if old_craftsman_id != craftsman_id:
                    # Hent navne på gamle og nye håndværkere til historikken
                    old_craftsman_name = None
                    new_craftsman_name = None
                    
                    if old_craftsman_id:
                        old_craftsman = conn.execute('SELECT username FROM users WHERE id = ?', (old_craftsman_id,)).fetchone()
                        if old_craftsman:
                            old_craftsman_name = old_craftsman['username']
                    
                    if craftsman_id:
                        new_craftsman = conn.execute('SELECT username FROM users WHERE id = ?', (craftsman_id,)).fetchone()
                        if new_craftsman:
                            new_craftsman_name = new_craftsman['username']
                    
                    add_ticket_history(ticket_id, flask_login.current_user.id, 'craftsman_changed', old_craftsman_name, new_craftsman_name, existing_conn=conn)
                
                conn.commit()
                flash('Ticket opdateret!', 'success')
                
                if flask_login.current_user.role == 'admin':
                    return redirect(url_for('admin'))
                else:
                    return redirect(url_for('udlejer_dashboard'))
            except Exception as e:
                print(f"Fejl ved opdatering af ticket: {e}")
                conn.rollback()
                flash('Fejl ved opdatering af ticket.', 'error')
                
                # Hent data igen til visning af formularen
                udlejere = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()
                users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall()
                craftsmen = conn.execute('''
                    SELECT id, username, company_name, speciality, phone
                    FROM users
                    WHERE role = 'craftsman'
                    ORDER BY username
                ''').fetchall()
                comments = get_comments(ticket_id, flask_login.current_user)
                history = get_ticket_history(ticket_id)
                
                # Hent billeder tilknyttet ticketen
                images = image_helpers.get_ticket_images(ticket_id, get_db_connection)
                
                return render_template("edit.html", ticket=ticket, udlejere=udlejere, users=users, craftsmen=craftsmen, comments=comments, history=history, images=images)
        else:  # GET request
            print(f"--- DEBUG: edit_ticket({ticket_id}) - GET request ---")  # DEBUG

            # Hent *alle* udlejere og *alle* brugere med rollen 'lejer'
            udlejere = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()
            users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall()
            
            # Hent håndværkere
            craftsmen = conn.execute('''
                SELECT id, username, company_name, speciality, phone
                FROM users
                WHERE role = 'craftsman'
                ORDER BY username
            ''').fetchall()
            
            # Hent kommentarer og historik
            comments = get_comments(ticket_id, flask_login.current_user)
            history = get_ticket_history(ticket_id)

            print(f"  DEBUG: Udlejere: {udlejere}")  # DEBUG
            print(f"  DEBUG: Lejere: {users}")  # DEBUG
            print(f"  DEBUG: Håndværkere: {craftsmen}")  # DEBUG
            print(f"  DEBUG: Ticket: {ticket}")  # DEBUG

            return render_template("edit.html", ticket=ticket, udlejere=udlejere, users=users, craftsmen=craftsmen, comments=comments, history=history)
    except Exception as e:
        print(f"Fejl ved redigering/hentning af ticket: {e}")
        flash('Fejl ved redigering af ticket.', 'error')
        conn.rollback()
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route("/edit/<int:ticket_id>", methods=["POST"])
@flask_login.login_required
def update_ticket(ticket_id):
    print(f"--- DEBUG: update_ticket({ticket_id}) ---")  # DEBUG
    
    conn = get_db_connection()
    try:
        # Hent den gamle ticket for at sammenligne værdier
        old_ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        lejer = request.form["lejer"]
        beskrivelse = request.form["beskrivelse"]
        status = request.form["status"]
        udlejer_input = request.form["udlejer"]
        craftsman_id = request.form.get("craftsman_id", "")
        
        # Konverter udlejer til ID, hvis det ikke allerede er et ID
        try:
            udlejer = int(udlejer_input)
        except (ValueError, TypeError):
            # Hvis udlejer_input ikke er et tal, antager vi, at det er et brugernavn
            # og forsøger at finde det tilsvarende ID
            udlejer_user = conn.execute('SELECT id FROM users WHERE username = ? AND role = "udlejer"', (udlejer_input,)).fetchone()
            if udlejer_user:
                udlejer = udlejer_user['id']
            else:
                # Hvis vi ikke kan finde en bruger med det angivne brugernavn, beholder vi den oprindelige værdi
                udlejer = udlejer_input
        
        # Hvis craftsman_id er en tom streng, sæt den til None
        if craftsman_id == "":
            craftsman_id = None
        else:
            # Konverter craftsman_id til et heltal, hvis det ikke er None
            try:
                craftsman_id = int(craftsman_id)
            except (ValueError, TypeError):
                craftsman_id = None

        print(f"  Lejer: {lejer}")  # DEBUG
        print(f"  Beskrivelse: {beskrivelse}")  # DEBUG
        print(f"  Status: {status}")  # DEBUG
        print(f"  Udlejer (input): {udlejer_input}")  # DEBUG
        print(f"  Udlejer (gemt): {udlejer}, Type: {type(udlejer)}")  # DEBUG
        print(f"  Håndværker ID: {craftsman_id}, Type: {type(craftsman_id)}")  # DEBUG

        conn.execute(
            "UPDATE tickets SET lejer = ?, beskrivelse = ?, status = ?, udlejer = ?, craftsman_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (lejer, beskrivelse, status, udlejer, craftsman_id, ticket_id),
        )
        
        # Registrer ændringer i ticket-historikken
        if old_ticket['status'] != status:
            add_ticket_history(ticket_id, flask_login.current_user.id, 'status_changed', old_ticket['status'], status, existing_conn=conn)
        
        if old_ticket['beskrivelse'] != beskrivelse:
            add_ticket_history(ticket_id, flask_login.current_user.id, 'description_changed', None, None, existing_conn=conn)
            
        if old_ticket['lejer'] != lejer:
            add_ticket_history(ticket_id, flask_login.current_user.id, 'tenant_changed', old_ticket['lejer'], lejer, existing_conn=conn)
            
        # Konverter old_ticket['udlejer'] til string for at sikre korrekt sammenligning
        old_udlejer_str = str(old_ticket['udlejer']) if old_ticket['udlejer'] is not None else None
        udlejer_str = str(udlejer) if udlejer is not None else None
        
        if old_udlejer_str != udlejer_str:
            # Hent navne på gamle og nye udlejere til historikken
            old_udlejer_name = None
            new_udlejer_name = None
            
            if old_ticket['udlejer']:
                try:
                    # Forsøg at konvertere til int for at se, om det er et ID
                    old_udlejer_id = int(old_ticket['udlejer'])
                    old_udlejer_user = conn.execute('SELECT username FROM users WHERE id = ?', (old_udlejer_id,)).fetchone()
                    if old_udlejer_user:
                        old_udlejer_name = old_udlejer_user['username']
                    else:
                        old_udlejer_name = old_ticket['udlejer']
                except (ValueError, TypeError):
                    # Hvis det ikke er et ID, brug værdien direkte
                    old_udlejer_name = old_ticket['udlejer']
            
            if udlejer:
                try:
                    # Forsøg at konvertere til int for at se, om det er et ID
                    new_udlejer_id = int(udlejer)
                    new_udlejer_user = conn.execute('SELECT username FROM users WHERE id = ?', (new_udlejer_id,)).fetchone()
                    if new_udlejer_user:
                        new_udlejer_name = new_udlejer_user['username']
                    else:
                        new_udlejer_name = udlejer
                except (ValueError, TypeError):
                    # Hvis det ikke er et ID, brug værdien direkte
                    new_udlejer_name = udlejer
            
            add_ticket_history(ticket_id, flask_login.current_user.id, 'landlord_changed', old_udlejer_name, new_udlejer_name, existing_conn=conn)
            
        # Registrer ændring af håndværker
        old_craftsman_id = old_ticket['craftsman_id'] if 'craftsman_id' in old_ticket.keys() else None
        if old_craftsman_id != craftsman_id:
            # Hent navne på gamle og nye håndværkere til historikken
            old_craftsman_name = None
            new_craftsman_name = None
            
            if old_craftsman_id:
                old_craftsman = conn.execute('SELECT username FROM users WHERE id = ?', (old_craftsman_id,)).fetchone()
                if old_craftsman:
                    old_craftsman_name = old_craftsman['username']
            
            if craftsman_id:
                new_craftsman = conn.execute('SELECT username FROM users WHERE id = ?', (craftsman_id,)).fetchone()
                if new_craftsman:
                    new_craftsman_name = new_craftsman['username']
            
            add_ticket_history(ticket_id, flask_login.current_user.id, 'craftsman_changed', old_craftsman_name, new_craftsman_name, existing_conn=conn)
        
        conn.commit()
        flash('Ticket opdateret!', 'success')
        return redirect(url_for('ticket', ticket_id=ticket_id))
    except Exception as e:
        print(f"Fejl ved opdatering af ticket: {e}")
        flash('Fejl ved opdatering af ticket.', 'error')
        conn.rollback()
        return redirect(url_for('ticket', ticket_id=ticket_id))
    finally:
        conn.close()

@app.route("/ticket/<int:ticket_id>")
@flask_login.login_required
def ticket_detail(ticket_id):
    conn = get_db_connection()
    try:
        # Hent ticket med udlejer_name og craftsman_name
        ticket = conn.execute('''
            SELECT t.*, 
                   u.username as udlejer_name,
                   c.username as craftsman_name,
                   c.company_name,
                   c.speciality,
                   c.phone as craftsman_phone
            FROM tickets t
            LEFT JOIN users u ON t.udlejer = u.id
            LEFT JOIN users c ON t.craftsman_id = c.id
            WHERE t.id = ?
        ''', (ticket_id,)).fetchone()
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect('/admin')
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'lejer':
            # Lejere kan kun se tickets på deres eget lejemål
            if flask_login.current_user.unit_id != ticket['unit_id'] and flask_login.current_user.username != ticket['lejer']:
                flash('Du har ikke adgang til denne ticket.', 'error')
                return redirect(url_for('index'))
        elif flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun se tickets på deres egne ejendomme
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if property_owner and property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til denne ticket.', 'error')
                return redirect(url_for('index'))
        elif flask_login.current_user.role == 'craftsman':
            # Håndværkere kan kun se tickets, der er tildelt dem
            if str(flask_login.current_user.id) != str(ticket['craftsman_id']):
                # Tjek om håndværkeren har afgivet tilbud på denne ticket
                bid = conn.execute('''
                    SELECT * FROM bids 
                    WHERE ticket_id = ? AND craftsman_id = ?
                ''', (ticket_id, flask_login.current_user.id)).fetchone()
                
                if not bid:
                    flash('Du har ikke adgang til denne ticket.', 'error')
                    return redirect(url_for('index'))
        # Admin har adgang til alle tickets
        
        # Hent kommentarer og historik
        comments = get_comments(ticket_id, flask_login.current_user)
        history = get_ticket_history(ticket_id)
        
        print(f"Ticket detail for ticket {ticket_id}:")
        print(f"  - Kommentarer: {len(comments)}")
        print(f"  - Historik: {history is not None}")
        print(f"  - Historik længde: {len(history) if history else 0}")
        print(f"  - Historik type: {type(history)}")
        if history:
            print(f"  - Første historik-post: {history[0]}")
            print(f"  - Historik-post keys: {history[0].keys() if hasattr(history[0], 'keys') else 'No keys'}")
        
        # Hent information om lejemålet
        unit = conn.execute('SELECT * FROM units WHERE id = ?', (ticket['unit_id'],)).fetchone()
        
        # Hent information om ejendommen
        property_info = None
        if unit:
            property_info = conn.execute('SELECT * FROM properties WHERE id = ?', (unit['property_id'],)).fetchone()
        
        # Hent billeder tilknyttet ticketen
        images = image_helpers.get_ticket_images(ticket_id, get_db_connection)
        
        # Hent tilbud, hvis brugeren har adgang
        bids = []
        if flask_login.current_user.role in ['admin', 'udlejer']:
            # Admin og udlejer kan se alle tilbud
            bids = get_bids(ticket_id)
        elif flask_login.current_user.role == 'craftsman':
            # Håndværkere kan kun se deres egne tilbud
            bids = conn.execute('''
                SELECT b.*, u.username, u.company_name
                FROM bids b
                LEFT JOIN users u ON b.craftsman_id = u.id
                WHERE b.ticket_id = ? AND b.craftsman_id = ?
                ORDER BY b.created_at DESC
            ''', (ticket_id, flask_login.current_user.id)).fetchall()
        
        # Tjek om den aktuelle håndværker kan afgive tilbud
        can_add_bid = False
        if flask_login.current_user.role == 'craftsman':
            if str(flask_login.current_user.id) == str(ticket['craftsman_id']) and ticket['requires_bid'] and ticket['craftsman_status'] == 'pending':
                can_add_bid = True
        
        # Tjek om håndværkeren kan opdatere status
        can_update_status = False
        if flask_login.current_user.role == 'craftsman':
            if str(flask_login.current_user.id) == str(ticket['craftsman_id']) and ticket['craftsman_status'] == 'approved':
                can_update_status = True
        
        # Tjek om udlejer/admin kan godkende håndværker
        can_approve_craftsman = False
        if flask_login.current_user.role in ['admin', 'udlejer'] and ticket['craftsman_id'] and ticket['craftsman_status'] == 'pending':
            can_approve_craftsman = True
        
        # Tjek om brugeren kan uploade billeder
        can_upload_images = False
        if flask_login.current_user.role in ['admin', 'udlejer']:
            can_upload_images = True
        elif flask_login.current_user.role == 'craftsman':
            if str(flask_login.current_user.id) == str(ticket['craftsman_id']) and ticket['craftsman_status'] == 'approved':
                can_upload_images = True
        
        # Tjek om brugeren kan slette billeder
        can_delete_images = flask_login.current_user.role in ['admin', 'udlejer']
        
        return render_template(
            "ticket.html", 
            ticket=ticket, 
            comments=comments, 
            history=history, 
            unit=unit, 
            property=property_info,
            bids=bids,
            images=images,
            user=flask_login.current_user,
            can_add_bid=can_add_bid,
            can_update_status=can_update_status,
            can_approve_craftsman=can_approve_craftsman,
            can_upload_images=can_upload_images,
            can_delete_images=can_delete_images
        )
    except Exception as e:
        print(f"Fejl ved hentning af ticket detaljer: {e}")
        flash(f'Fejl ved hentning af ticket detaljer', 'error')
        return redirect('/admin')
    finally:
        conn.close()

@app.route("/ticket/<int:ticket_id>/comment", methods=["POST"])
@flask_login.login_required
def add_ticket_comment(ticket_id):
    content = request.form.get("content")
    visible_to_tenant = request.form.get("visible_to_tenant") == "on"
    
    if not content:
        flash('Kommentar kan ikke være tom.', 'error')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    # Kontroller adgang
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    conn.close()
    
    if not ticket:
        flash('Ticket findes ikke!', 'error')
        return redirect(url_for('index'))
    
    # Kontroller adgang baseret på brugerrolle (samme logik som i ticket_detail)
    if flask_login.current_user.role == 'lejer':
        if flask_login.current_user.unit_id != ticket['unit_id'] and flask_login.current_user.username != ticket['lejer']:
            flash('Du har ikke adgang til denne ticket.', 'error')
            return redirect(url_for('index'))
    elif flask_login.current_user.role == 'udlejer':
        conn = get_db_connection()
        property_owner = conn.execute('''
            SELECT p.owner_id 
            FROM properties p 
            JOIN units u ON p.id = u.property_id 
            WHERE u.id = ?
        ''', (ticket['unit_id'],)).fetchone()
        conn.close()
        
        if property_owner and property_owner['owner_id'] != flask_login.current_user.id:
            flash('Du har ikke adgang til denne ticket.', 'error')
            return redirect(url_for('index'))
    elif flask_login.current_user.role == 'craftsman':
        if str(flask_login.current_user.id) != str(ticket['craftsman_id']):
            flash('Du har ikke adgang til denne ticket.', 'error')
            return redirect(url_for('index'))
    
    # Tilføj kommentaren
    success = add_comment(ticket_id, flask_login.current_user.id, content, visible_to_tenant)
    
    if success:
        flash('Kommentar tilføjet!', 'success')
    else:
        flash('Fejl ved tilføjelse af kommentar.', 'error')
    
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = get_user(username)

        if user and check_password_hash(user.password_hash, password):
            flask_login.login_user(user)
            flash(f'Velkommen {user.username}!', 'success')
            
            # Omdiriger baseret på brugerrolle
            if user.role == 'udlejer':
                return redirect(url_for('udlejer_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Forkert brugernavn eller adgangskode.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    flash('Du er nu logget ud!', 'success')
    return redirect(url_for('index')) # omdiriger til index

  # ---USERS Section ---

@app.route('/admin/users/create', methods=['GET', 'POST'])
@flask_login.login_required
def admin_create_user(user_id=None):
    conn = get_db_connection()
    try:
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun administrere lejere
            if user_id:
                # Hvis det er en redigering, tjek om brugeren er en lejer i udlejerens ejendom
                user = conn.execute('SELECT users.*, units.property_id FROM users LEFT JOIN units ON users.unit_id = units.id WHERE users.id = ?', (user_id,)).fetchone()
                
                if not user:
                    flash('Brugeren blev ikke fundet.', 'error')
                    return redirect(url_for('udlejer_kontrolpanel'))
                
                # Hvis brugeren ikke er en lejer, eller hvis lejemålet ikke er tilknyttet en ejendom
                if user['role'] != 'lejer' or not user['property_id']:
                    flash('Du har ikke adgang til at redigere denne bruger.', 'error')
                    return redirect(url_for('udlejer_kontrolpanel'))
                
                # Tjek om ejendommen tilhører udlejeren
                property_check = conn.execute('SELECT * FROM properties WHERE id = ? AND owner_id = ?', 
                                             (user['property_id'], flask_login.current_user.id)).fetchone()
                
                if not property_check:
                    flash('Du har ikke adgang til at redigere denne bruger.', 'error')
                    return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))

        # Hent properties og units til dropdown menuer baseret på brugerrolle
        if flask_login.current_user.role == 'admin':
            properties = conn.execute("SELECT * FROM properties").fetchall()
            units = conn.execute("SELECT units.*, properties.name as property_name FROM units JOIN properties ON units.property_id = properties.id").fetchall()
        else:  # Udlejer
            properties = conn.execute("SELECT * FROM properties WHERE owner_id = ?", (flask_login.current_user.id,)).fetchall()
            units = conn.execute("""
                SELECT units.*, properties.name as property_name 
                FROM units 
                JOIN properties ON units.property_id = properties.id 
                WHERE properties.owner_id = ?
            """, (flask_login.current_user.id,)).fetchall()

        user = None  # Definer user som None, som default.
        if user_id:  # Hvis user_id er angivet, hent brugeren
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if user is None:  # Hvis brugeren ikke findes.
                flash('Bruger findes ikke.', 'error')
                if flask_login.current_user.role == 'admin':
                    return redirect(url_for('admin_users'))
                else:
                    return redirect(url_for('udlejer_kontrolpanel'))

        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            confirm_password = request.form['confirm_password']
            email = request.form.get('email', '')
            phone = request.form.get('phone', '')
            
            # Udlejere kan kun oprette/redigere lejere
            if flask_login.current_user.role == 'udlejer':
                role = 'lejer'
            else:
                role = request.form['role']

            errors = []
            if not username:
                errors.append('Brugernavn er påkrævet.')
            # Valider password kun ved oprettelse (ikke redigering)
            if not user_id:  # Hvis det er en ny bruger (user_id er None)
                if not password:
                    errors.append('Adgangskode er påkrævet.')
                if not confirm_password:
                    errors.append('Bekræft adgangskode er påkrævet.')
                if password and confirm_password and password != confirm_password:  # Tjek kun hvis de findes.
                    errors.append('Adgangskoderne stemmer ikke overens.')

            # Tjek om brugernavn eksisterer (kun ved oprettelse, eller hvis brugernavnet ændres)
            if not user_id or (user and username != user['username']):  # Hvis det er en ny bruger, ELLER hvis brugernavnet er ændret
                existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
                if existing_user:
                    errors.append('Brugernavnet er allerede i brug.')

            # --- Lejemål validering og hentning (KUN for lejere) ---
            unit_id = None  # Initialiser unit_id
            if role == 'lejer':
                unit_id_str = request.form.get('unit_id')  # Hent som string
                if not unit_id_str:
                    errors.append('Lejemål skal vælges for lejere.')
                else:
                    try:
                        unit_id = int(unit_id_str)  # Konverter til int
                            
                        # For udlejere, tjek om lejemålet tilhører en af deres ejendomme
                        if flask_login.current_user.role == 'udlejer':
                            unit_check = conn.execute("""
                                    SELECT units.id 
                                    FROM units 
                                    JOIN properties ON units.property_id = properties.id 
                                    WHERE units.id = ? AND properties.owner_id = ?
                                """, (unit_id, flask_login.current_user.id)).fetchone()
                        else:
                            unit_check = conn.execute("SELECT id FROM units WHERE id = ?", (unit_id,)).fetchone()
                                
                        if not unit_check:
                            errors.append('Ugyldigt lejemål.')
                    except ValueError:
                        errors.append('Ugyldigt lejemål ID.')
                        unit_id = None  # Nulstil, hvis konvertering fejler

            if errors:
                for error in errors:
                    flash(error, 'error')
                # Send alt med.
                return render_template('admin_create_user.html', username=username, role=role, properties=properties, units=units, user=user)

            # --- Opret/opdater bruger ---
            try:
                if user_id:  # Hvis user_id er angivet, er det en opdatering
                        # Hvis brugeren er en lejer og har et tidligere lejemål, fjern tenant_id fra det tidligere lejemål
                        if role == 'lejer':
                            # Hent brugerens nuværende lejemål
                            old_unit_id = None
                            if user:
                                old_unit_id = user['unit_id']
                            
                            # Hvis brugeren havde et andet lejemål før, nulstil tenant_id for det gamle lejemål
                            if old_unit_id and old_unit_id != unit_id:
                                conn.execute("UPDATE units SET tenant_id = NULL WHERE id = ?", (old_unit_id,))
                            
                            # Opdater tenant_id for det nye lejemål
                            if unit_id:
                                conn.execute("UPDATE units SET tenant_id = ? WHERE id = ?", (user_id, unit_id))
                        
                        # Opdater brugeroplysninger
                        if password:  # Kun hvis der er indtastet et kodeord, opdateres det.
                            hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
                            conn.execute(
                                "UPDATE users SET username = ?, password_hash = ?, role = ?, unit_id = ?, email = ?, phone = ? WHERE id = ?",
                                (username, hashed_password, role, unit_id, email, phone, user_id)
                        )
                        else:  # Hvis intet kodeord, så opdateres kun de andre felter.
                            conn.execute(
                              "UPDATE users SET username = ?, role = ?, unit_id = ?, email = ?, phone = ? WHERE id = ?",
                              (username, role, unit_id, email, phone, user_id)
                        )
                        
                        # Hvis brugeren ikke længere er en lejer, fjern tenant_id fra alle lejemål, der peger på denne bruger
                        if role != 'lejer':
                            conn.execute("UPDATE units SET tenant_id = NULL WHERE tenant_id = ?", (user_id,))
                        
                        conn.commit()
                        flash('Bruger opdateret!', 'success')
                else:  # Ellers er det en ny bruger
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
                    cursor = conn.cursor()  # Opret cursor objekt.
                    if role == 'lejer':
                        cursor.execute(
                                "INSERT INTO users (username, password_hash, role, unit_id, email, phone) VALUES (?, ?, ?, ?, ?, ?)",
                                (username, hashed_password, role, unit_id, email, phone)  # Indsæt alle parametre, da det er en lejer.
                        )
                        new_user_id = cursor.lastrowid  # Hent ID på den indsatte række (lejer)

                        # Opdater tenant_id i units tabellen
                        cursor.execute("UPDATE units SET tenant_id = ? WHERE id = ?", (new_user_id, unit_id))
                    else:  # Hvis ikke lejer, unit_id = NULL
                        cursor.execute(
                        "INSERT INTO users (username, password_hash, role, unit_id, email, phone) VALUES (?, ?, ?, NULL, ?, ?)",
                        (username, hashed_password, role, email, phone)
                    )
                    conn.commit()
                    flash('Bruger oprettet!', 'success')

                    if flask_login.current_user.role == 'admin':
                        return redirect(url_for('admin_users'))  # Omdiriger til admin_users
                    else:
                        return redirect(url_for('udlejer_kontrolpanel'))  # Omdiriger til udlejer_kontrolpanel
            except Exception as e:
                print(f"Fejl ved oprettelse/redigering af bruger: {e}")
                flash(f'Fejl ved oprettelse/redigering af bruger.', 'error')
                conn.rollback()
                if flask_login.current_user.role == 'admin':
                    return redirect(url_for('admin_users'))
                else:
                    return redirect(url_for('udlejer_kontrolpanel'))
        
        # GET request, eller efter succesfuld oprettelse/redigering
        return render_template('admin_create_user.html', properties=properties, units=units, user=user)  # Send properties og units med.
    except Exception as e:
        print(f"Fejl i admin_create_user: {e}")
        flash('Der opstod en fejl.', 'error')
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_users'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()  # Husk at lukke forbindelsen.

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@flask_login.login_required
def admin_edit_user(user_id):
    conn = get_db_connection()
    try:
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun administrere lejere
            if user_id:
                # Hvis det er en redigering, tjek om brugeren er en lejer i udlejerens ejendom
                user = conn.execute('SELECT users.*, units.property_id FROM users LEFT JOIN units ON users.unit_id = units.id WHERE users.id = ?', (user_id,)).fetchone()
                
                if not user:
                    flash('Brugeren blev ikke fundet.', 'error')
                    return redirect(url_for('udlejer_kontrolpanel'))
                
                # Hvis brugeren ikke er en lejer, eller hvis lejemålet ikke er tilknyttet en ejendom
                if user['role'] != 'lejer' or not user['property_id']:
                    flash('Du har ikke adgang til at redigere denne bruger.', 'error')
                    return redirect(url_for('udlejer_kontrolpanel'))
                
                # Tjek om ejendommen tilhører udlejeren
                property_check = conn.execute('SELECT * FROM properties WHERE id = ? AND owner_id = ?', 
                                             (user['property_id'], flask_login.current_user.id)).fetchone()
                
                if not property_check:
                    flash('Du har ikke adgang til at redigere denne bruger.', 'error')
                    return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))

        # Hent properties og units til dropdown menuer baseret på brugerrolle
        if flask_login.current_user.role == 'admin':
            properties = conn.execute("SELECT * FROM properties").fetchall()
            units = conn.execute("SELECT units.*, properties.name as property_name FROM units JOIN properties ON units.property_id = properties.id").fetchall()
        else:  # Udlejer
            properties = conn.execute("SELECT * FROM properties WHERE owner_id = ?", (flask_login.current_user.id,)).fetchall()
            units = conn.execute("""
                SELECT units.*, properties.name as property_name 
                FROM units 
                JOIN properties ON units.property_id = properties.id 
                WHERE properties.owner_id = ?
            """, (flask_login.current_user.id,)).fetchall()

        user = None  # Definer user som None, som default.
        if user_id:  # Hvis user_id er angivet, hent brugeren
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if user is None:  # Hvis brugeren ikke findes.
                flash('Bruger findes ikke.', 'error')
                if flask_login.current_user.role == 'admin':
                    return redirect(url_for('admin_users'))
                else:
                    return redirect(url_for('udlejer_kontrolpanel'))

        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            confirm_password = request.form['confirm_password']
            email = request.form.get('email', '')
            phone = request.form.get('phone', '')
            
            # Udlejere kan kun oprette/redigere lejere
            if flask_login.current_user.role == 'udlejer':
                role = 'lejer'
            else:
                role = request.form['role']

            errors = []
            if not username:
                errors.append('Brugernavn er påkrævet.')
            # Valider password kun ved oprettelse (ikke redigering)
            if not user_id:  # Hvis det er en ny bruger (user_id er None)
                if not password:
                    errors.append('Adgangskode er påkrævet.')
                if not confirm_password:
                    errors.append('Bekræft adgangskode er påkrævet.')
                if password and confirm_password and password != confirm_password:  # Tjek kun hvis de findes.
                    errors.append('Adgangskoderne stemmer ikke overens.')

            # Tjek om brugernavn eksisterer (kun ved oprettelse, eller hvis brugernavnet ændres)
            if not user_id or (user and username != user['username']):  # Hvis det er en ny bruger, ELLER hvis brugernavnet er ændret
                existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
                if existing_user:
                    errors.append('Brugernavnet er allerede i brug.')

            # --- Lejemål validering og hentning (KUN for lejere) ---
            unit_id = None  # Initialiser unit_id
            if role == 'lejer':
                unit_id_str = request.form.get('unit_id')  # Hent som string
                if not unit_id_str:
                    errors.append('Lejemål skal vælges for lejere.')
                else:
                    try:
                        unit_id = int(unit_id_str)  # Konverter til int
                            
                        # For udlejere, tjek om lejemålet tilhører en af deres ejendomme
                        if flask_login.current_user.role == 'udlejer':
                            unit_check = conn.execute("""
                                    SELECT units.id 
                                    FROM units 
                                    JOIN properties ON units.property_id = properties.id 
                                    WHERE units.id = ? AND properties.owner_id = ?
                                """, (unit_id, flask_login.current_user.id)).fetchone()
                        else:
                            unit_check = conn.execute("SELECT id FROM units WHERE id = ?", (unit_id,)).fetchone()
                                
                        if not unit_check:
                            errors.append('Ugyldigt lejemål.')
                    except ValueError:
                        errors.append('Ugyldigt lejemål ID.')
                        unit_id = None  # Nulstil, hvis konvertering fejler

            if errors:
                for error in errors:
                    flash(error, 'error')
                    # Send alt med.
                return render_template('admin_create_user.html', username=username, role=role, properties=properties, units=units, user=user)

            # --- Opret/opdater bruger ---
            try:
                if user_id:  # Hvis user_id er angivet, er det en opdatering
                        # Hvis brugeren er en lejer og har et tidligere lejemål, fjern tenant_id fra det tidligere lejemål
                        if role == 'lejer':
                            # Hent brugerens nuværende lejemål
                            old_unit_id = None
                            if user:
                                old_unit_id = user['unit_id']
                            
                            # Hvis brugeren havde et andet lejemål før, nulstil tenant_id for det gamle lejemål
                            if old_unit_id and old_unit_id != unit_id:
                                conn.execute("UPDATE units SET tenant_id = NULL WHERE id = ?", (old_unit_id,))
                            
                            # Opdater tenant_id for det nye lejemål
                            if unit_id:
                                conn.execute("UPDATE units SET tenant_id = ? WHERE id = ?", (user_id, unit_id))
                        
                        # Opdater brugeroplysninger
                        if password:  # Kun hvis der er indtastet et kodeord, opdateres det.
                            hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
                            conn.execute(
                                "UPDATE users SET username = ?, password_hash = ?, role = ?, unit_id = ?, email = ?, phone = ? WHERE id = ?",
                                (username, hashed_password, role, unit_id, email, phone, user_id)
                        )
                        else:  # Hvis intet kodeord, så opdateres kun de andre felter.
                            conn.execute(
                              "UPDATE users SET username = ?, role = ?, unit_id = ?, email = ?, phone = ? WHERE id = ?",
                              (username, role, unit_id, email, phone, user_id)
                        )
                        
                        # Hvis brugeren ikke længere er en lejer, fjern tenant_id fra alle lejemål, der peger på denne bruger
                        if role != 'lejer':
                            conn.execute("UPDATE units SET tenant_id = NULL WHERE tenant_id = ?", (user_id,))
                        
                        conn.commit()
                        flash('Bruger opdateret!', 'success')
                else:  # Ellers er det en ny bruger
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
                    cursor = conn.cursor()  # Opret cursor objekt.
                    if role == 'lejer':
                        cursor.execute(
                                "INSERT INTO users (username, password_hash, role, unit_id, email, phone) VALUES (?, ?, ?, ?, ?, ?)",
                                (username, hashed_password, role, unit_id, email, phone)  # Indsæt alle parametre, da det er en lejer.
                        )
                        new_user_id = cursor.lastrowid  # Hent ID på den indsatte række (lejer)

                        # Opdater tenant_id i units tabellen
                        cursor.execute("UPDATE units SET tenant_id = ? WHERE id = ?", (new_user_id, unit_id))
                    else:  # Hvis ikke lejer, unit_id = NULL
                        cursor.execute(
                        "INSERT INTO users (username, password_hash, role, unit_id, email, phone) VALUES (?, ?, ?, NULL, ?, ?)",
                        (username, hashed_password, role, email, phone)
                    )
                    conn.commit()
                    flash('Bruger oprettet!', 'success')

                    if flask_login.current_user.role == 'admin':
                        return redirect(url_for('admin_users'))  # Omdiriger til admin_users
                    else:
                        return redirect(url_for('udlejer_kontrolpanel'))  # Omdiriger til udlejer_kontrolpanel
            except Exception as e:
                print(f"Fejl ved oprettelse/redigering af bruger: {e}")
                flash(f'Fejl ved oprettelse/redigering af bruger.', 'error')
                conn.rollback()
                if flask_login.current_user.role == 'admin':
                    return redirect(url_for('admin_users'))
                else:
                    return redirect(url_for('udlejer_kontrolpanel'))
        
        # GET request, eller efter succesfuld oprettelse/redigering
        return render_template('admin_create_user.html', properties=properties, units=units, user=user)  # Send properties og units med.
    except Exception as e:
        print(f"Fejl i admin_create_user: {e}")
        flash('Der opstod en fejl.', 'error')
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_users'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()  # Husk at lukke forbindelsen.

@app.route("/admin/users")
@flask_login.login_required
def admin_users():
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        # --- Filtrering (start) ---
        role = request.args.get('role')
        search_term = request.args.get('search', '').lower() #Hent søgeterm, og lav til lowercase.

        sql = "SELECT users.*, units.address, properties.name as property_name FROM users LEFT JOIN units ON users.unit_id = units.id LEFT JOIN properties on units.property_id = properties.id"
        params = []

        if role:
            sql += " WHERE users.role = ?"
            params.append(role)

        if search_term:
              if "WHERE" in sql: #Hvis der allerede er et where statement
                sql += " AND (users.username LIKE ? OR users.role LIKE ?)"
              else: #Hvis der ikke findes et WHERE statement.
                sql += " WHERE (users.username LIKE ? OR users.role LIKE ?)"
              params.extend(['%' + search_term + '%', '%' + search_term + '%']) #Tilføjer % foran og bagved, for delvis søgning.

        #Udfør, og hent alle.
        users = conn.execute(sql, params).fetchall()
        # --- Filtrering (slut) ---

        #Hent properties og units, så vi kan vise property_name.
        properties = conn.execute("SELECT * FROM properties").fetchall()
        units = conn.execute("SELECT units.*, properties.name as property_name from units JOIN properties on units.property_id = properties.id").fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af brugere: {e}")
        users = []
        properties = []  # Sørg for at properties er defineret
        units = [] #Sørg for at units er defineret.
    finally:
        conn.close()

    return render_template("admin_users.html", users=users, selected_role=role, search_term=search_term, properties=properties, units=units) # properties og units er defineret



@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@flask_login.login_required
def admin_delete_user(user_id):
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne handling.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        flash('Bruger slettet!', 'success')
    except Exception as e:
        print(f"Fejl ved sletning af bruger: {e}")
        flash('Fejl ved sletning af bruger.', 'error')
        conn.rollback()
    finally:
        conn.close()
    return redirect(url_for('admin_users'))

# --- UNITS (START) ---
@app.route('/admin/units')
@flask_login.login_required
def admin_units():
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        # Hent filter-parametre
        property_id = request.args.get('property_id', '')
        owner_id = request.args.get('owner_id', '')
        
        # Hvis vi filtrerer efter udlejer, skal vi først finde ejendomme, der tilhører denne udlejer
        if owner_id and not property_id:
            # Hent alle ejendomme for den valgte udlejer
            owner_properties = conn.execute(
                'SELECT id FROM properties WHERE owner_id = ?', 
                (owner_id,)
            ).fetchall()
            
            # Hvis udlejeren har ejendomme, filtrerer vi lejemål baseret på disse
            if owner_properties:
                property_ids = [p['id'] for p in owner_properties]
                placeholders = ', '.join(['?'] * len(property_ids))
                query = f'SELECT * FROM units WHERE property_id IN ({placeholders})'
                params = property_ids
            else:
                # Hvis udlejeren ikke har ejendomme, returnerer vi ingen lejemål
                query = 'SELECT * FROM units WHERE 0'
                params = []
        else:
            # Byg SQL-forespørgsel baseret på ejendoms-filter
            query = 'SELECT * FROM units'
            params = []
            
            if property_id:
                query += ' WHERE property_id = ?'
                params.append(property_id)
        
        # Hent lejemål
        units = conn.execute(query, params).fetchall()
        
        # Hent alle ejendomme
        properties = conn.execute('SELECT * FROM properties').fetchall()
        
        # Hent alle udlejere
        owners = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()
        
        # Hent alle lejere
        users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af lejemål/ejendomme/brugere: {e}")
        units = []
        properties = []
        users = []
        owners = []
        property_id = ''
        owner_id = ''
    finally:
        conn.close()
    
    return render_template(
        "admin_units.html", 
        units=units, 
        properties=properties, 
        users=users,
        owners=owners,
        selected_property_id=property_id,
        selected_owner_id=owner_id
    )

@app.route('/admin/units/create', methods=['GET', 'POST'])
@flask_login.login_required
def admin_create_unit():
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    properties = conn.execute('SELECT * FROM properties').fetchall()
    users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall()  # Kun lejere
    conn.close()

    if request.method == 'POST':
        address = request.form['address']
        property_id = int(request.form['property_id'])
        tenant_id_str = request.form.get('tenant_id')

        # --- Validering ---
        errors = []
        if not address:
            errors.append('Adresse er påkrævet.')
        # Tjek at property_id er gyldig:
        conn = get_db_connection()
        property_check = conn.execute('SELECT id FROM properties WHERE id = ?', (property_id,)).fetchone()
        conn.close()
        if not property_check:
          errors.append('Ugyldig værdi for ejendom.')

        # --- Tenant ID Validering og konvertering ---
        tenant_id = None
        if tenant_id_str:
            try:
                tenant_id = int(tenant_id_str)
                #Tjek at tenant_id findes:
                conn = get_db_connection()
                tenant_check = conn.execute("SELECT * FROM users WHERE id = ?", (tenant_id,)).fetchone()
                conn.close()
                if not tenant_check:
                  errors.append('Ugyldigt lejer id')
            except ValueError:
                errors.append('Ugyldigt lejer-ID (ikke et heltal).')
                tenant_id = None #Nulstil.

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('admin_create_unit.html', properties=properties, users=users)

        conn = get_db_connection()
        try:
            # Indsæt det nye lejemål (med tenant_id, som kan være None)
            cursor = conn.execute(
                "INSERT INTO units (address, property_id, tenant_id) VALUES (?, ?, ?)",
                (address, property_id, tenant_id)
            )
            
            # Hent ID på det nyoprettede lejemål
            unit_id = cursor.lastrowid
            
            # Hvis der er en lejer tilknyttet, opdater unit_id i users tabellen
            if tenant_id:
                # Tjek om lejeren allerede har et lejemål
                current_unit = conn.execute("SELECT unit_id FROM users WHERE id = ?", (tenant_id,)).fetchone()
                if current_unit and current_unit['unit_id']:
                    # Fjern tenant_id fra det gamle lejemål
                    conn.execute("UPDATE units SET tenant_id = NULL WHERE id = ?", (current_unit['unit_id'],))
                
                # Opdater unit_id for lejeren
                conn.execute("UPDATE users SET unit_id = ? WHERE id = ?", (unit_id, tenant_id))
            
            conn.commit()
            flash('Lejemål oprettet!', 'success')
            return redirect(url_for('admin_units')) #Ret til admin_units
        except Exception as e:
            print(f"Fejl ved oprettelse af lejemål: {e}")
            flash('Fejl ved oprettelse af lejemål.', 'error')
            conn.rollback()
        finally:
            conn.close()

    # --- GET request ---
    return render_template('admin_create_unit.html', properties=properties, users=users)

@app.route("/admin/units/edit/<int:unit_id>", methods=["GET", "POST"])
@flask_login.login_required
def edit_unit(unit_id):
    conn = get_db_connection()
    try:
        # Hent lejemålsoplysninger
        unit = conn.execute('SELECT * FROM units WHERE id = ?', (unit_id,)).fetchone()
        
        if not unit:
            flash('Lejemålet blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Hent ejendomsoplysninger for at kontrollere ejerskab
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (unit['property_id'],)).fetchone()
        
        if not property_data:
            flash('Ejendommen blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun redigere lejemål i deres egne ejendomme
            if property_data['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at redigere dette lejemål.', 'error')
                return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))

        if request.method == 'POST':
            address = request.form["address"]
            
            # Hvis det er en udlejer, kan de ikke ændre ejendommen
            if flask_login.current_user.role == 'udlejer':
                property_id = unit['property_id']  # Bevar den nuværende ejendom
            else:
                property_id = request.form["property_id"]
                
            tenant_id_str = request.form["tenant_id"]
            tenant_id = int(tenant_id_str) if tenant_id_str else None

            # Hent det nuværende lejemål for at få den nuværende lejer
            current_tenant_id = unit['tenant_id']

            # Hvis der er en ny lejer, og den er forskellig fra den nuværende
            if tenant_id and tenant_id != current_tenant_id:
                # Opdater unit_id for den nye lejer
                conn.execute("UPDATE users SET unit_id = ? WHERE id = ?", (unit_id, tenant_id))
                
                # Hvis der var en tidligere lejer, fjern unit_id fra den tidligere lejer
                if current_tenant_id:
                    conn.execute("UPDATE users SET unit_id = NULL WHERE id = ?", (current_tenant_id,))
            
            # Hvis lejeren er fjernet (tenant_id er NULL), fjern unit_id fra den tidligere lejer
            if not tenant_id and current_tenant_id:
                conn.execute("UPDATE users SET unit_id = NULL WHERE id = ?", (current_tenant_id,))

            # Opdater lejemålet
            conn.execute(
                "UPDATE units SET address = ?, property_id = ?, tenant_id = ? WHERE id = ?",
                (address, property_id, tenant_id, unit_id),
            )
            
            conn.commit()
            flash('Lejemål opdateret!', 'success')
            
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        else:
            # Hent data til formularen
            if flask_login.current_user.role == 'admin':
                properties = conn.execute('SELECT * FROM properties').fetchall()  # Hent alle ejendomme
            else:
                # For udlejere, hent kun deres egne ejendomme
                properties = conn.execute('SELECT * FROM properties WHERE owner_id = ?', 
                                         (flask_login.current_user.id,)).fetchall()
                
            users = conn.execute("SELECT * FROM users WHERE role = 'lejer'").fetchall()  # Hent kun lejere
            
            return render_template("edit_unit.html", unit=unit, properties=properties, users=users)
    except Exception as e:
        print(f"Fejl ved redigering/hentning af lejemål: {e}")
        flash('Der opstod en fejl ved redigering af lejemål.', 'error')
        conn.rollback()
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_units'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()


@app.route("/admin/units/delete/<int:unit_id>", methods=["POST"])
@flask_login.login_required
def delete_unit(unit_id):
    conn = get_db_connection()
    try:
        # Hent lejemålsoplysninger
        unit = conn.execute('SELECT * FROM units WHERE id = ?', (unit_id,)).fetchone()
        
        if not unit:
            flash('Lejemålet blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Hent ejendomsoplysninger for at kontrollere ejerskab
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (unit['property_id'],)).fetchone()
        
        if not property_data:
            flash('Ejendommen blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun slette lejemål i deres egne ejendomme
            if property_data['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at slette dette lejemål.', 'error')
                return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne handling.', 'error')
            return redirect(url_for('index'))

        # Tjek om der er tickets tilknyttet lejemålet
        tickets = conn.execute('SELECT COUNT(*) as count FROM tickets WHERE unit_id = ?', (unit_id,)).fetchone()
        if tickets['count'] > 0:
            flash('Lejemålet kan ikke slettes, da der er tickets tilknyttet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))

        # Hvis der er en lejer tilknyttet, fjern unit_id fra lejeren
        if unit['tenant_id']:
            conn.execute('UPDATE users SET unit_id = NULL WHERE id = ?', (unit['tenant_id'],))

        # Slet lejemålet
        conn.execute('DELETE FROM units WHERE id = ?', (unit_id,))
        conn.commit()
        flash('Lejemål slettet!', 'success')
        
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_units'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    except Exception as e:
        print(f"Fejl ved sletning af lejemål: {e}")
        flash('Der opstod en fejl ved sletning af lejemålet.', 'error')
        conn.rollback()
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_units'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()
# --- UNITS (SLUT) ---

@app.route('/register', methods=['GET', 'POST'])
#@flask_login.login_required # Fjern midlertidigt, for test.
def register():
    # Tjek om brugeren er admin
    #if flask_login.current_user.role != 'admin':
    #    flash('Du har ikke tilladelse til at oprette brugere.', 'error')
    #    return redirect(url_for('index'))  # Eller en anden passende side

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        #role = request.form['role'] #Ikke længere del af formular.
        role = "lejer"  # Sæt rollen automatisk til "lejer" - vi ændrer dette senere!
        # unit_id = 1 #Hardcoded, skal ændres.

        # --- Validering (start) ---
        errors = []  # Opret en liste til at holde styr på fejl

        if not username:
            errors.append('Brugernavn er påkrævet.')
        if not password:
            errors.append('Adgangskode er påkrævet.')
        if not confirm_password:
            errors.append('Bekræft adgangskode er påkrævet.')  # Lidt overflødig, da HTML har 'required', men god praksis
        if password != confirm_password:
            errors.append('Adgangskoderne stemmer ikke overens.')

        # Tjek om brugernavn eksisterer (mere effektiv forespørgsel)
        conn = get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if existing_user:
            errors.append('Brugernavnet er allerede i brug.')

        # Hvis der er fejl, vis formularen igen med fejlbeskeder
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html', username=username)  # <--- Fjernet role

        # Hash adgangskoden
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        # Opret bruger i databasen
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, unit_id) VALUES (?, ?, ?, NULL)",  # unit_id er NULL
                (username, hashed_password, role)
            )
            conn.commit()
            flash('Bruger oprettet!', 'success')
            return redirect(url_for('login'))  # Eller en anden passende side (f.eks. en liste over brugere)
        except Exception as e:
            print(f"Fejl ved oprettelse af bruger: {e}")
            flash(f'Fejl ved oprettelse af bruger. Se server log for detaljer.', 'error')  # Mere generel fejlbesked til brugeren
            conn.rollback()  # Rul tilbage, hvis der sker en fejl
        finally:
            conn.close()

    return render_template('register.html')  # Vis formularen (GET request)
# --- NYE ROUTES TIL PROPERTIES (START) ---
@app.route("/admin/properties")
@flask_login.login_required
def admin_properties():
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        # Hent filter-parameter
        owner_id = request.args.get('owner_id', '')
        
        # Byg SQL-forespørgsel baseret på filter
        query = 'SELECT * FROM properties'
        params = []
        
        if owner_id:
            query += ' WHERE owner_id = ?'
            params.append(owner_id)
        
        # Hent ejendomme
        properties = conn.execute(query, params).fetchall()
        
        # Hent alle udlejere
        users = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af ejendomme: {e}")
        properties = []
        users = []
        owner_id = ''
    finally:
        conn.close()
    
    return render_template(
        "admin_properties.html", 
        properties=properties, 
        users=users,
        selected_owner_id=owner_id
    )


@app.route("/admin/properties/create", methods=["POST"])
@flask_login.login_required
def create_property():
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    name = request.form.get('name')
    owner_id = request.form.get('owner_id')
    adresse = request.form.get('adresse')
    postnummer = request.form.get('postnummer')
    by = request.form.get('by')

    if not name or not owner_id or not adresse or not postnummer or not by:
        flash('Alle felter skal udfyldes.', 'error')
        return redirect(url_for('admin_properties'))

    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO properties (name, owner_id, adresse, postnummer, by) VALUES (?, ?, ?, ?, ?)',
            (name, owner_id, adresse, postnummer, by)
        )
        conn.commit()
        flash('Ejendommen blev oprettet.', 'success')
    except Exception as e:
        print(f"Fejl ved oprettelse af ejendom: {e}")
        flash('Der opstod en fejl ved oprettelse af ejendommen.', 'error')
    finally:
        conn.close()

    return redirect(url_for('admin_properties'))

@app.route("/admin/properties/create", methods=["GET"])
@flask_login.login_required
def admin_create_property():
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        users = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af udlejere: {e}")
        users = []
    finally:
        conn.close()

    return render_template("admin_create_property.html", users=users)

@app.route("/admin/properties/edit/<int:property_id>", methods=["GET", "POST"])
@flask_login.login_required
def edit_property(property_id):
    conn = get_db_connection()
    try:
        # Hent ejendomsoplysninger
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (property_id,)).fetchone()
        
        if not property_data:
            flash('Ejendommen blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_properties'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun redigere deres egne ejendomme
            if property_data['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at redigere denne ejendom.', 'error')
                return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            # Hvis det er en udlejer, kan de ikke ændre ejeren
            if flask_login.current_user.role == 'udlejer':
                owner_id = property_data['owner_id']  # Bevar den nuværende ejer
            else:
                owner_id = request.form["owner_id"]
                
            name = request.form["name"]
            adresse = request.form["adresse"]
            postnummer = request.form["postnummer"]
            by = request.form["by"]

            conn.execute(
                "UPDATE properties SET name = ?, owner_id = ?, adresse = ?, postnummer = ?, by = ? WHERE id = ?",
                (name, owner_id, adresse, postnummer, by, property_id),
            )
            conn.commit()
            flash('Ejendom opdateret!', 'success')
            
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_properties'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        else:
            users = conn.execute("SELECT * FROM users WHERE role = 'udlejer'").fetchall()  # Hent kun udlejere
            if property_data is None:
                flash('Ejendom findes ikke.', 'error')
                if flask_login.current_user.role == 'admin':
                    return redirect(url_for('admin_properties'))
                else:
                    return redirect(url_for('udlejer_kontrolpanel'))
            return render_template("edit_property.html", property=property_data, users=users)
    except Exception as e:
        print(f"Fejl ved redigering af ejendom: {e}")
        flash('Der opstod en fejl ved redigering af ejendommen.', 'error')
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_properties'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()

@app.route("/udlejer/kontrolpanel")
@flask_login.login_required
def udlejer_kontrolpanel():
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent udlejerens ID
        udlejer_id = flask_login.current_user.id
        
        # Hent udlejerens ejendomme
        properties = conn.execute('''
            SELECT * FROM properties 
            WHERE owner_id = ? 
            ORDER BY name
        ''', (udlejer_id,)).fetchall()
        
        # Hent udlejerens lejemål
        units = conn.execute('''
            SELECT u.*, p.name as property_name 
            FROM units u
            JOIN properties p ON u.property_id = p.id
            WHERE p.owner_id = ?
            ORDER BY p.name, u.address
        ''', (udlejer_id,)).fetchall()
        
        # Hent lejere tilknyttet udlejerens lejemål
        tenants = conn.execute('''
            SELECT u.* 
            FROM users u
            JOIN units un ON u.unit_id = un.id
            JOIN properties p ON un.property_id = p.id
            WHERE p.owner_id = ? AND u.role = 'lejer'
            ORDER BY u.username
        ''', (udlejer_id,)).fetchall()
        
        # Hent håndværkere tilknyttet udlejeren via craftsman_landlord_relations tabellen
        craftsmen = conn.execute('''
            SELECT u.* 
            FROM users u
            JOIN craftsman_landlord_relations clr ON u.id = clr.craftsman_id
            WHERE clr.landlord_id = ? AND u.role = 'craftsman'
            ORDER BY u.username
        ''', (udlejer_id,)).fetchall()
        
    except Exception as e:
        print(f"Fejl ved hentning af data til udlejer kontrolpanel: {e}")
        flash('Der opstod en fejl ved hentning af data.', 'error')
        return redirect(url_for('udlejer_dashboard'))
    finally:
        conn.close()
    
    return render_template(
        "udlejer_kontrolpanel.html",
        properties=properties,
        units=units,
        tenants=tenants,
        craftsmen=craftsmen
    )

@app.route("/admin/properties/delete/<int:property_id>", methods=["POST"])
@flask_login.login_required
def delete_property(property_id):
    conn = get_db_connection()
    try:
        # Hent ejendomsoplysninger
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (property_id,)).fetchone()
        
        if not property_data:
            flash('Ejendommen blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_properties'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun slette deres egne ejendomme
            if property_data['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at slette denne ejendom.', 'error')
                return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne handling.', 'error')
            return redirect(url_for('index'))

        # Tjek om der er lejemål tilknyttet ejendommen
        units = conn.execute('SELECT * FROM units WHERE property_id = ?', (property_id,)).fetchall()
        if units:
            flash('Ejendommen kan ikke slettes, da der er lejemål tilknyttet. Slet venligst lejemålene først.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_properties'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))

        # Slet ejendommen
        conn.execute('DELETE FROM properties WHERE id = ?', (property_id,))
        conn.commit()
        flash('Ejendom slettet!', 'success')
        
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_properties'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    except Exception as e:
        print(f"Fejl ved sletning af ejendom: {e}")
        flash('Der opstod en fejl ved sletning af ejendommen.', 'error')
        conn.rollback()
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_properties'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()

# --- Hjælpefunktioner til tickets ---

def add_ticket_history(ticket_id, user_id, action_type, old_value=None, new_value=None, existing_conn=None):
    """
    Tilføjer en handling til ticket-historikken.
    
    Args:
        ticket_id: ID på den ticket, handlingen vedrører
        user_id: ID på den bruger, der udførte handlingen
        action_type: Type af handling (f.eks. 'created', 'status_changed', osv.)
        old_value: Tidligere værdi (hvis relevant)
        new_value: Ny værdi (hvis relevant)
        existing_conn: Eksisterende databaseforbindelse (hvis tilgængelig)
    """
    conn = None
    should_close_conn = False
    try:
        # Brug den eksisterende forbindelse, hvis den er givet, ellers opret en ny
        if existing_conn:
            conn = existing_conn
        else:
            conn = sqlite3.connect('tickets.db')
            conn.row_factory = sqlite3.Row
            should_close_conn = True
        
        # Indsæt handlingen i historikken (created_at sættes automatisk til CURRENT_TIMESTAMP)
        conn.execute(
            "INSERT INTO ticket_history (ticket_id, user_id, action, old_value, new_value) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, user_id, action_type, old_value, new_value)
        )
        
        # Kun commit, hvis vi har oprettet en ny forbindelse
        if should_close_conn:
            conn.commit()
            
        return True
    except Exception as e:
        print(f"Fejl ved tilføjelse af ticket-historik: {e}")
        if conn and should_close_conn:
            conn.rollback()
        return False
    finally:
        if conn and should_close_conn:
            conn.close()

def get_ticket_history(ticket_id):
    """
    Henter historikken for en bestemt ticket.
    
    Args:
        ticket_id: ID på den ticket, hvis historik skal hentes
    
    Returns:
        En liste med historik-poster for den pågældende ticket
    """
    try:
        conn = get_db_connection()
        
        # Tjek om ticket_history-tabellen eksisterer
        table_exists = conn.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ticket_history'
        ''').fetchone()
        
        if not table_exists:
            print(f"ticket_history-tabellen eksisterer ikke i databasen")
            return []
        
        history = conn.execute('''
            SELECT h.*, u.username, u.role
            FROM ticket_history h
            LEFT JOIN users u ON h.user_id = u.id
            WHERE h.ticket_id = ?
            ORDER BY h.created_at DESC
        ''', (ticket_id,)).fetchall()
        print(f"Historik hentet for ticket {ticket_id}: {len(history)} poster")
        for entry in history:
            print(f"  - {entry['action']} af {entry['username']} ({entry['created_at']})")
        return history
    except Exception as e:
        print(f"Fejl ved hentning af ticket-historik: {e}")
        return []
    finally:
        conn.close()

def add_comment(ticket_id, user_id, content, visible_to_tenant=True):
    """
    Tilføjer en kommentar til en ticket.
    
    Args:
        ticket_id: ID på den ticket, kommentaren vedrører
        user_id: ID på den bruger, der tilføjer kommentaren
        content: Indholdet af kommentaren
        visible_to_tenant: Om kommentaren skal være synlig for lejeren
    
    Returns:
        True hvis kommentaren blev tilføjet, False ellers
    """
    try:
        conn = get_db_connection()
        # Indsæt kommentaren (created_at sættes automatisk til CURRENT_TIMESTAMP)
        conn.execute(
            "INSERT INTO comments (ticket_id, user_id, content, visible_to_tenant) VALUES (?, ?, ?, ?)",
            (ticket_id, user_id, content, visible_to_tenant)
        )
        conn.commit()
        
        # Tilføj handling til ticket-historikken
        add_ticket_history(ticket_id, user_id, 'comment_added', existing_conn=conn)
        
        return True
    except Exception as e:
        print(f"Fejl ved tilføjelse af kommentar: {e}")
        return False
    finally:
        conn.close()

def get_comments(ticket_id, current_user):
    """
    Henter kommentarer for en bestemt ticket.
    
    Args:
        ticket_id: ID på den ticket, hvis kommentarer skal hentes
        current_user: Den aktuelt indloggede bruger
    
    Returns:
        En liste med kommentarer for den pågældende ticket
    """
    try:
        conn = get_db_connection()
        
        # Hvis brugeren er lejer, vis kun kommentarer, der er synlige for lejere
        if current_user.role == 'lejer':
            comments = conn.execute('''
                SELECT c.*, u.username 
                FROM comments c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.ticket_id = ? AND c.visible_to_tenant = 1
                ORDER BY c.created_at DESC
            ''', (ticket_id,)).fetchall()
        else:
            # For admin, udlejer og håndværker, vis alle kommentarer
            comments = conn.execute('''
                SELECT c.*, u.username 
                FROM comments c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.ticket_id = ?
                ORDER BY c.created_at DESC
            ''', (ticket_id,)).fetchall()
        
        return comments
    except Exception as e:
        print(f"Fejl ved hentning af kommentarer: {e}")
        return []
    finally:
        conn.close()

def get_bids(ticket_id):
    """
    Henter tilbud for en bestemt ticket.
    
    Args:
        ticket_id: ID på den ticket, hvis tilbud skal hentes
    
    Returns:
        En liste med tilbud for den pågældende ticket
    """
    try:
        conn = get_db_connection()
        bids = conn.execute('''
            SELECT b.*, u.username, u.company_name
            FROM bids b
            LEFT JOIN users u ON b.craftsman_id = u.id
            WHERE b.ticket_id = ?
            ORDER BY b.created_at DESC
        ''', (ticket_id,)).fetchall()
        return bids
    except Exception as e:
        print(f"Fejl ved hentning af tilbud: {e}")
        return []
    finally:
        conn.close()

# --- Slut på hjælpefunktioner ---

def find_free_port(start_port=5000, max_port=5050):
    """
    Finder en ledig port i det angivne interval.
    
    Args:
        start_port: Startporten at tjekke fra
        max_port: Maksimal port at tjekke til
    
    Returns:
        En ledig port eller None, hvis ingen ledige porte blev fundet
    """
    import socket
    
    for port in range(start_port, max_port + 1):
        try:
            # Prøv at oprette en socket på porten
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            return port
        except socket.error:
            # Porten er i brug, prøv den næste
            continue
    
    return None

@app.route("/udlejer/dashboard")
@flask_login.login_required
def udlejer_dashboard():
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent filtre fra URL-parametre
        status_filter = request.args.get('status', '')
        property_filter = request.args.get('property', '')
        
        # Hent sorteringsparametre
        sort_by = request.args.get('sort', 'created_at')  # Standard: Sortér efter oprettelsesdato
        sort_dir = request.args.get('dir', 'desc')  # Standard: Faldende (nyeste først)
        
        # Validér sorteringsparametre for at undgå SQL-injektion
        valid_sort_columns = ['id', 'lejer', 'status', 'created_at', 'updated_at']
        valid_sort_dirs = ['asc', 'desc']
        
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        if sort_dir not in valid_sort_dirs:
            sort_dir = 'desc'
        
        # Hent alle unikke status-værdier til dropdown
        statuses = conn.execute('SELECT DISTINCT status FROM tickets ORDER BY status').fetchall()
        
        # Hent ALLE tickets for udlejeren (til statistik)
        all_tickets_query = '''
            SELECT 
                t.*,
                u.username as creator_name,
                un.address as unit_address,
                p.name as property_name,
                o.username as udlejer_name
            FROM 
                tickets t
            LEFT JOIN 
                users u ON t.user_id = u.id
            LEFT JOIN 
                units un ON t.unit_id = un.id
            LEFT JOIN 
                properties p ON un.property_id = p.id
            LEFT JOIN
                users o ON t.udlejer = o.id
            WHERE 
                p.owner_id = ?
        '''
        all_tickets = conn.execute(all_tickets_query, [flask_login.current_user.id]).fetchall()
        
        # Byg SQL-forespørgsel baseret på filtre for visning af tickets
        filtered_query = all_tickets_query
        params = [flask_login.current_user.id]
        
        if status_filter:
            filtered_query += ' AND t.status = ?'
            params.append(status_filter)
            
        if property_filter:
            filtered_query += ' AND p.name = ?'
            params.append(property_filter)
        
        # Tilføj sortering
        filtered_query += f' ORDER BY t.{sort_by} {sort_dir}'
            
        # Udfør forespørgslen for filtrerede tickets
        tickets = conn.execute(filtered_query, params).fetchall()
        
        # Hent statistik for ALLE udlejerens tickets (uanset filtre)
        stats = {}
        
        # Antal tickets i alt
        stats['total_tickets'] = len(all_tickets)
        
        # Antal aktive tickets (ikke lukket eller afsluttet)
        stats['open_tickets'] = len([t for t in all_tickets if t['status'].lower() not in ['lukket', 'afsluttet']])
        
        # Antal lukkede/afsluttede tickets
        stats['closed_tickets'] = len([t for t in all_tickets if t['status'].lower() in ['lukket', 'afsluttet']])
        
        # Gennemsnitlig behandlingstid for lukkede tickets (i dage)
        closed_tickets = [t for t in all_tickets if t['status'].lower() in ['lukket', 'afsluttet'] and 'created_at' in t.keys() and 'updated_at' in t.keys() and t['created_at'] and t['updated_at']]
        if closed_tickets:
            total_days = 0
            valid_tickets = 0
            for t in closed_tickets:
                try:
                    created = datetime.strptime(t['created_at'], '%Y-%m-%d %H:%M:%S')
                    updated = datetime.strptime(t['updated_at'], '%Y-%m-%d %H:%M:%S')
                    days = (updated - created).days
                    total_days += days
                    valid_tickets += 1
                except (ValueError, TypeError, AttributeError):
                    continue
            stats['avg_resolution_days'] = total_days / valid_tickets if valid_tickets > 0 else 0
        else:
            stats['avg_resolution_days'] = 0
        
        # Status fordeling
        status_counts = {}
        for ticket in all_tickets:
            status = ticket['status']
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts[status] = 1
        stats['status_counts'] = status_counts
        
        # Ejendomsfordeling - Hent alle ejendomme for udlejeren, ikke kun dem med tickets
        all_properties = conn.execute('''
            SELECT name FROM properties 
            WHERE owner_id = ? 
            ORDER BY name
        ''', (flask_login.current_user.id,)).fetchall()
        
        property_counts = {}
        # Initialiser alle ejendomme med 0 tickets
        for prop in all_properties:
            property_counts[prop['name']] = 0
            
        # Tæl tickets for hver ejendom
        for ticket in all_tickets:
            property_name = ticket['property_name'] or 'Ukendt'
            if property_name in property_counts:
                property_counts[property_name] += 1
            else:
                property_counts[property_name] = 1
        stats['property_counts'] = property_counts
        
    except Exception as e:
        print(f"Fejl ved hentning af tickets til udlejer dashboard: {e}")
        tickets = []
        statuses = []
        stats = {
            'total_tickets': 0, 
            'open_tickets': 0, 
            'closed_tickets': 0, 
            'avg_resolution_days': 0,
            'status_counts': {},
            'property_counts': {}
        }
    finally:
        conn.close()
    
    return render_template(
        "udlejer_dashboard.html", 
        tickets=tickets, 
        statuses=statuses, 
        current_status=status_filter,
        current_property=property_filter,
        sort_by=sort_by, 
        sort_dir=sort_dir,
        stats=stats
    )

@app.route("/admin/update_database", methods=["GET", "POST"])
@flask_login.login_required
def admin_update_database():
    # Kontroller at brugeren er administrator
    if flask_login.current_user.role != 'admin':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    success = False
    message = ""
    
    if request.method == "POST":
        try:
            # Kør databaseopdateringen
            if update_db():
                success = True
                message = "Databasen blev opdateret succesfuldt!"
            else:
                message = "Der opstod en fejl under opdateringen af databasen."
        except Exception as e:
            message = f"Der opstod en fejl: {str(e)}"
    
    return render_template("admin_update_database.html", success=success, message=message)

@app.route("/admin/properties/view/<int:property_id>")
@flask_login.login_required
def view_property(property_id):
    conn = get_db_connection()
    try:
        # Hent ejendomsoplysninger
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (property_id,)).fetchone()
        
        if not property_data:
            flash('Ejendommen blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_properties'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun se deres egne ejendomme
            if property_data['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at se denne ejendom.', 'error')
                return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))
        
        # Hent ejer-information
        owner = conn.execute('SELECT * FROM users WHERE id = ?', (property_data['owner_id'],)).fetchone()
        
        # Hent lejemål for denne ejendom
        units = conn.execute('''
            SELECT u.*, t.username as tenant_name 
            FROM units u 
            LEFT JOIN users t ON u.tenant_id = t.id
            WHERE u.property_id = ?
        ''', (property_id,)).fetchall()
        
        # Hent alle tickets for denne ejendom
        tickets = conn.execute('''
            SELECT t.*, u.username as creator_name, un.address as unit_address
            FROM tickets t
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN units un ON t.unit_id = un.id
            WHERE un.property_id = ?
            ORDER BY t.created_at DESC
        ''', (property_id,)).fetchall()
        
        # Opdel tickets i aktive og lukkede
        active_tickets = [t for t in tickets if t['status'].lower() != 'lukket']
        closed_tickets = [t for t in tickets if t['status'].lower() == 'lukket']
        
        return render_template(
            "admin_view_property.html", 
            property=property_data,
            owner=owner,
            units=units,
            tickets=tickets,
            active_tickets=active_tickets,
            closed_tickets=closed_tickets
        )
    except Exception as e:
        print(f"Fejl ved hentning af ejendomsdetaljer: {e}")
        flash('Der opstod en fejl ved hentning af ejendomsdetaljer.', 'error')
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_properties'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()

@app.route("/admin/units/view/<int:unit_id>")
@flask_login.login_required
def view_unit(unit_id):
    conn = get_db_connection()
    try:
        # Hent lejemålsoplysninger
        unit = conn.execute('SELECT * FROM units WHERE id = ?', (unit_id,)).fetchone()
        
        if not unit:
            flash('Lejemålet blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Hent ejendomsoplysninger
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (unit['property_id'],)).fetchone()
        
        if not property_data:
            flash('Ejendommen blev ikke fundet.', 'error')
            if flask_login.current_user.role == 'admin':
                return redirect(url_for('admin_units'))
            else:
                return redirect(url_for('udlejer_kontrolpanel'))
        
        # Kontroller adgang baseret på brugerrolle
        if flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun se lejemål i deres egne ejendomme
            if property_data['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at se dette lejemål.', 'error')
                return redirect(url_for('udlejer_kontrolpanel'))
        elif flask_login.current_user.role != 'admin':
            flash('Du har ikke adgang til denne side.', 'error')
            return redirect(url_for('index'))
        
        # Hent udlejer-information
        owner = conn.execute('SELECT * FROM users WHERE id = ?', (property_data['owner_id'],)).fetchone()
        
        # Hent lejer-information (hvis der er en lejer tilknyttet)
        tenant = None
        if unit['tenant_id']:
            tenant = conn.execute('SELECT * FROM users WHERE id = ?', (unit['tenant_id'],)).fetchone()
        
        # Hent alle tickets for dette lejemål
        tickets = conn.execute('''
            SELECT t.*, u.username as creator_name
            FROM tickets t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.unit_id = ?
            ORDER BY t.created_at DESC
        ''', (unit_id,)).fetchall()
        
        # Opdel tickets i aktive og lukkede
        active_tickets = [t for t in tickets if t['status'].lower() != 'lukket']
        closed_tickets = [t for t in tickets if t['status'].lower() == 'lukket']
        
        return render_template(
            "admin_view_unit.html", 
            unit=unit,
            property=property_data,
            owner=owner,
            tenant=tenant,
            active_tickets=active_tickets,
            closed_tickets=closed_tickets
        )
    except Exception as e:
        print(f"Fejl ved hentning af lejemålsdetaljer: {e}")
        flash('Der opstod en fejl ved hentning af lejemålsdetaljer.', 'error')
        if flask_login.current_user.role == 'admin':
            return redirect(url_for('admin_units'))
        else:
            return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()

@app.route("/udlejer/create_property", methods=["GET", "POST"])
@flask_login.login_required
def udlejer_create_property():
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form["name"]
        adresse = request.form["adresse"]
        postnummer = request.form["postnummer"]
        by = request.form["by"]
        owner_id = flask_login.current_user.id  # Udlejeren er altid ejeren

        # Validering
        errors = []
        if not name:
            errors.append('Navn er påkrævet.')
        if not adresse:
            errors.append('Adresse er påkrævet.')
        if not postnummer:
            errors.append('Postnummer er påkrævet.')
        if not by:
            errors.append('By er påkrævet.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template("create_property.html")

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO properties (name, owner_id, adresse, postnummer, by) VALUES (?, ?, ?, ?, ?)",
                (name, owner_id, adresse, postnummer, by),
            )
            conn.commit()
            flash('Ejendom oprettet!', 'success')
            return redirect(url_for('udlejer_kontrolpanel'))
        except Exception as e:
            print(f"Fejl ved oprettelse af ejendom: {e}")
            flash('Der opstod en fejl ved oprettelse af ejendommen.', 'error')
        finally:
            conn.close()

    return render_template("create_property.html")

@app.route("/udlejer/create_unit", methods=["GET", "POST"])
@flask_login.login_required
def create_unit():
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        # Hent kun ejendomme, der tilhører den aktuelle udlejer
        properties = conn.execute('SELECT * FROM properties WHERE owner_id = ?', (flask_login.current_user.id,)).fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af ejendomme: {e}")
        properties = []
    finally:
        conn.close()

    if request.method == 'POST':
        address = request.form['address']
        property_id = int(request.form['property_id'])

        # Validering
        errors = []
        if not address:
            errors.append('Adresse er påkrævet.')
        
        # Tjek at property_id er gyldig og tilhører udlejeren
        conn = get_db_connection()
        property_check = conn.execute('SELECT id FROM properties WHERE id = ? AND owner_id = ?', 
                                     (property_id, flask_login.current_user.id)).fetchone()
        conn.close()
        
        if not property_check:
            errors.append('Ugyldig værdi for ejendom eller ejendommen tilhører ikke dig.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('create_unit.html', properties=properties)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO units (address, property_id) VALUES (?, ?)",
                (address, property_id),
            )
            conn.commit()
            flash('Lejemål oprettet!', 'success')
            return redirect(url_for('udlejer_kontrolpanel'))
        except Exception as e:
            print(f"Fejl ved oprettelse af lejemål: {e}")
            flash('Der opstod en fejl ved oprettelse af lejemålet.', 'error')
        finally:
            conn.close()

    return render_template("create_unit.html", properties=properties)

@app.route("/udlejer/create_tenant", methods=["GET", "POST"])
@flask_login.login_required
def create_tenant():
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        # Hent kun lejemål, der tilhører ejendomme ejet af den aktuelle udlejer
        units = conn.execute("""
            SELECT units.*, properties.name as property_name 
            FROM units 
            JOIN properties ON units.property_id = properties.id 
            WHERE properties.owner_id = ?
        """, (flask_login.current_user.id,)).fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af lejemål: {e}")
        units = []
    finally:
        conn.close()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        unit_id_str = request.form.get('unit_id')
        
        # Validering
        errors = []
        if not username:
            errors.append('Brugernavn er påkrævet.')
        if not password:
            errors.append('Adgangskode er påkrævet.')
        if not confirm_password:
            errors.append('Bekræft adgangskode er påkrævet.')
        if password and confirm_password and password != confirm_password:
            errors.append('Adgangskoderne stemmer ikke overens.')

        # Tjek om brugernavn eksisterer
        conn = get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if existing_user:
            errors.append('Brugernavnet er allerede i brug.')

        # Lejemål validering
        unit_id = None
        if unit_id_str:
            try:
                unit_id = int(unit_id_str)
                # Tjek at lejemålet tilhører en ejendom ejet af udlejeren
                conn = get_db_connection()
                unit_check = conn.execute("""
                    SELECT units.id 
                    FROM units 
                    JOIN properties ON units.property_id = properties.id 
                    WHERE units.id = ? AND properties.owner_id = ?
                """, (unit_id, flask_login.current_user.id)).fetchone()
                conn.close()
                
                if not unit_check:
                    errors.append('Ugyldigt lejemål eller lejemålet tilhører ikke dig.')
            except ValueError:
                errors.append('Ugyldigt lejemål-ID (ikke et heltal).')
                unit_id = None

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('create_tenant.html', units=units)

        conn = get_db_connection()
        try:
            # Hash adgangskoden
            hashed_password = generate_password_hash(password)
            
            # Indsæt den nye bruger
            conn.execute(
                "INSERT INTO users (username, password, role, unit_id) VALUES (?, ?, ?, ?)",
                (username, hashed_password, 'lejer', unit_id),
            )
            conn.commit()
            flash('Lejer oprettet!', 'success')
            return redirect(url_for('udlejer_kontrolpanel'))
        except Exception as e:
            print(f"Fejl ved oprettelse af lejer: {e}")
            flash('Der opstod en fejl ved oprettelse af lejeren.', 'error')
        finally:
            conn.close()

    return render_template("create_tenant.html", units=units)

@app.route("/udlejer/edit_tenant/<int:user_id>", methods=["GET", "POST"])
@flask_login.login_required
def edit_tenant(user_id):
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        # Tjek om brugeren er en lejer i udlejerens ejendom
        user = conn.execute('''
            SELECT users.*, units.property_id 
            FROM users 
            LEFT JOIN units ON users.unit_id = units.id 
            WHERE users.id = ?
        ''', (user_id,)).fetchone()
        
        if not user:
            flash('Brugeren blev ikke fundet.', 'error')
            return redirect(url_for('udlejer_kontrolpanel'))
        
        # Hvis brugeren ikke er en lejer, eller hvis lejemålet ikke er tilknyttet en ejendom
        if user['role'] != 'lejer' or not user['property_id']:
            flash('Du har ikke adgang til at redigere denne bruger.', 'error')
            return redirect(url_for('udlejer_kontrolpanel'))
        
        # Tjek om ejendommen tilhører udlejeren
        property_check = conn.execute('SELECT * FROM properties WHERE id = ? AND owner_id = ?', 
                                     (user['property_id'], flask_login.current_user.id)).fetchone()
        
        if not property_check:
            flash('Du har ikke adgang til at redigere denne bruger.', 'error')
            return redirect(url_for('udlejer_kontrolpanel'))
        
        # Hent lejemål til dropdown menuer
        units = conn.execute("""
            SELECT units.*, properties.name as property_name 
            FROM units 
            JOIN properties ON units.property_id = properties.id 
            WHERE properties.owner_id = ?
        """, (flask_login.current_user.id,)).fetchall()
        
        if request.method == 'POST':
            username = request.form['username']
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            unit_id_str = request.form.get('unit_id')
            
            # Validering
            errors = []
            if not username:
                errors.append('Brugernavn er påkrævet.')
            
            # Tjek om brugernavn eksisterer (kun hvis brugernavnet ændres)
            if username != user['username']:
                existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
                if existing_user:
                    errors.append('Brugernavnet er allerede i brug.')
            
            # Valider password kun hvis det er angivet
            if password or confirm_password:
                if password != confirm_password:
                    errors.append('Adgangskoderne stemmer ikke overens.')
            
            # Lejemål validering
            unit_id = None
            if unit_id_str:
                try:
                    unit_id = int(unit_id_str)
                    # Tjek at lejemålet tilhører en ejendom ejet af udlejeren
                    unit_check = conn.execute("""
                        SELECT units.id 
                        FROM units 
                        JOIN properties ON units.property_id = properties.id 
                        WHERE units.id = ? AND properties.owner_id = ?
                    """, (unit_id, flask_login.current_user.id)).fetchone()
                    
                    if not unit_check:
                        errors.append('Ugyldigt lejemål eller lejemålet tilhører ikke dig.')
                except ValueError:
                    errors.append('Ugyldigt lejemål-ID (ikke et heltal).')
                    unit_id = None
            
            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('edit_tenant.html', user=user, units=units)
            
            # Opdater brugeren
            if password:
                # Hash adgangskoden
                hashed_password = generate_password_hash(password)
                conn.execute(
                    "UPDATE users SET username = ?, password = ?, unit_id = ? WHERE id = ?",
                    (username, hashed_password, unit_id, user_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET username = ?, unit_id = ? WHERE id = ?",
                    (username, unit_id, user_id),
                )
            
            conn.commit()
            flash('Lejer opdateret!', 'success')
            return redirect(url_for('udlejer_kontrolpanel'))
    except Exception as e:
        print(f"Fejl ved redigering af lejer: {e}")
        flash('Der opstod en fejl ved redigering af lejeren.', 'error')
    finally:
        conn.close()
    
    return render_template("edit_tenant.html", user=user, units=units)

@app.route("/ticket/<int:ticket_id>/update_status", methods=["POST"])
@flask_login.login_required
def update_ticket_status(ticket_id):
    conn = get_db_connection()
    try:
        # Hent den gamle ticket for at sammenligne værdier
        old_ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if old_ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Tjek om brugeren har tilladelse til at opdatere status
        has_permission = False
        
        # Admin og udlejer har altid tilladelse
        if flask_login.current_user.role in ['admin', 'udlejer']:
            has_permission = True
            
            # Hvis brugeren er udlejer, kontroller at de har adgang til denne ticket
            if flask_login.current_user.role == 'udlejer':
                property_owner = conn.execute('''
                    SELECT p.owner_id 
                    FROM properties p 
                    JOIN units u ON p.id = u.property_id 
                    WHERE u.id = ?
                ''', (old_ticket['unit_id'],)).fetchone()
                
                if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                    has_permission = False
        
        # Håndværkere kan opdatere status, hvis de er godkendt til denne ticket
        elif flask_login.current_user.role == 'craftsman':
            if str(flask_login.current_user.id) == str(old_ticket['craftsman_id']) and old_ticket['craftsman_status'] == 'approved':
                has_permission = True
        
        if not has_permission:
            flash('Du har ikke tilladelse til at ændre status på denne ticket.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Hent den nye status fra formularen
        new_status = request.form.get('status')
        
        if new_status not in ['Oprettet', 'Igangsat', 'Afventer', 'Afsluttet']:
            flash('Ugyldig status.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Opdater status
        conn.execute(
            "UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, ticket_id)
        )
        
        # Registrer ændringen i ticket-historikken
        if old_ticket['status'] != new_status:
            add_ticket_history(ticket_id, flask_login.current_user.id, 'status_changed', old_ticket['status'], new_status, existing_conn=conn)
        
        conn.commit()
        flash('Status opdateret!', 'success')
        
    except Exception as e:
        print(f"Fejl ved opdatering af status: {e}")
        flash('Fejl ved opdatering af status.', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))

@app.route("/craftsman/dashboard")
@flask_login.login_required
def craftsman_dashboard():
    # Kontroller at brugeren er håndværker
    if flask_login.current_user.role != 'craftsman':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent tickets tildelt til denne håndværker
        assigned_tickets = conn.execute('''
            SELECT 
                t.*,
                u.username as lejer_name,
                o.username as udlejer_name,
                un.address as unit_address,
                p.name as property_name,
                CASE
                    WHEN t.craftsman_status = 'approved' THEN 'grøn'
                    ELSE 'gul'
                END as status_color
            FROM 
                tickets t
            LEFT JOIN 
                users u ON t.lejer = u.username
            LEFT JOIN 
                users o ON t.udlejer = o.id
            LEFT JOIN 
                units un ON t.unit_id = un.id
            LEFT JOIN 
                properties p ON un.property_id = p.id
            WHERE 
                t.craftsman_id = ? 
            ORDER BY 
                t.updated_at DESC
        ''', (flask_login.current_user.id,)).fetchall()
        
        # Hent tickets med krav om tilbud, som denne håndværker har afgivet tilbud på
        bid_tickets = conn.execute('''
            SELECT 
                t.*,
                u.username as lejer_name,
                o.username as udlejer_name,
                un.address as unit_address,
                p.name as property_name,
                b.status as bid_status,
                b.amount as bid_amount,
                b.id as bid_id
            FROM 
                tickets t
            JOIN 
                bids b ON t.id = b.ticket_id
            LEFT JOIN 
                users u ON t.lejer = u.username
            LEFT JOIN 
                users o ON t.udlejer = o.id
            LEFT JOIN 
                units un ON t.unit_id = un.id
            LEFT JOIN 
                properties p ON un.property_id = p.id
            WHERE 
                b.craftsman_id = ? AND
                t.craftsman_id IS NULL
            ORDER BY 
                b.created_at DESC
        ''', (flask_login.current_user.id,)).fetchall()
        
        # Hent statistik
        stats = {
            'assigned_count': len(assigned_tickets),
            'bid_count': len(bid_tickets),
            'approved_count': sum(1 for t in assigned_tickets if t['craftsman_status'] == 'approved'),
            'pending_count': sum(1 for t in assigned_tickets if t['craftsman_status'] == 'pending'),
            'completed_count': sum(1 for t in assigned_tickets if t['status'] == 'Afsluttet')
        }
        
        return render_template(
            "craftsman_dashboard.html", 
            assigned_tickets=assigned_tickets,
            bid_tickets=bid_tickets,
            stats=stats
        )
    except Exception as e:
        print(f"Fejl ved hentning af håndværker dashboard data: {e}")
        flash('Der opstod en fejl ved indlæsning af dashboardet.', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route("/craftsman_dashboard")
@flask_login.login_required
def craftsman_dashboard_redirect():
    # Omdirigerer til craftsman_dashboard
    return redirect(url_for('craftsman_dashboard'))

@app.route("/ticket/<int:ticket_id>/bid", methods=["GET", "POST"])
@flask_login.login_required
def add_bid(ticket_id):
    # Kontroller at brugeren er håndværker
    if flask_login.current_user.role != 'craftsman':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent ticket
        ticket = conn.execute('''
            SELECT t.*, u.username as udlejer_name
            FROM tickets t
            LEFT JOIN users u ON t.udlejer = u.id
            WHERE t.id = ?
        ''', (ticket_id,)).fetchone()
        
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller om der allerede er afgivet et tilbud fra denne håndværker
        existing_bid = conn.execute('''
            SELECT * FROM bids 
            WHERE ticket_id = ? AND craftsman_id = ?
        ''', (ticket_id, flask_login.current_user.id)).fetchone()
        
        if request.method == 'POST':
            amount = request.form.get('amount', '').strip()
            description = request.form.get('description', '').strip()
            
            # Validering
            errors = []
            if not amount:
                errors.append('Beløb er påkrævet.')
            else:
                try:
                    # Konverter til float og tjek om det er et positivt tal
                    amount_float = float(amount.replace(',', '.'))
                    if amount_float <= 0:
                        errors.append('Beløb skal være større end 0.')
                except ValueError:
                    errors.append('Beløb skal være et tal.')
            
            if not description:
                errors.append('Beskrivelse er påkrævet.')
            
            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('add_bid.html', ticket=ticket, existing_bid=existing_bid)
            
            # Konverter beløb til float
            amount_float = float(amount.replace(',', '.'))
            
            if existing_bid:
                # Opdater eksisterende tilbud
                conn.execute('''
                    UPDATE bids 
                    SET amount = ?, description = ?, updated_at = CURRENT_TIMESTAMP, status = 'pending'
                    WHERE id = ?
                ''', (amount_float, description, existing_bid['id']))
                
                # Tilføj til ticket-historik
                add_ticket_history(ticket_id, flask_login.current_user.id, 'bid_updated', str(existing_bid['amount']), str(amount_float), existing_conn=conn)
                
                flash('Dit tilbud er blevet opdateret.', 'success')
            else:
                # Opret nyt tilbud
                conn.execute('''
                    INSERT INTO bids (ticket_id, craftsman_id, amount, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (ticket_id, flask_login.current_user.id, amount_float, description))
                
                # Tilføj til ticket-historik
                add_ticket_history(ticket_id, flask_login.current_user.id, 'bid_added', None, str(amount_float), existing_conn=conn)
                
                flash('Dit tilbud er blevet afgivet.', 'success')
            
            conn.commit()
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        return render_template('add_bid.html', ticket=ticket, existing_bid=existing_bid)
    except Exception as e:
        print(f"Fejl ved afgivelse af tilbud: {e}")
        flash('Der opstod en fejl ved afgivelse af tilbud.', 'error')
        conn.rollback()
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    finally:
        conn.close()

@app.route("/bid/<int:bid_id>/edit", methods=["GET", "POST"])
@flask_login.login_required
def edit_bid(bid_id):
    # Kontroller at brugeren er håndværker
    if flask_login.current_user.role != 'craftsman':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent tilbud
        bid = conn.execute('''
            SELECT b.*, t.id as ticket_id, t.beskrivelse as ticket_beskrivelse, t.status as ticket_status,
                   u.username as udlejer_name
            FROM bids b
            JOIN tickets t ON b.ticket_id = t.id
            LEFT JOIN users u ON t.udlejer = u.id
            WHERE b.id = ?
        ''', (bid_id,)).fetchone()
        
        if bid is None:
            flash('Tilbud findes ikke!', 'error')
            return redirect(url_for('craftsman_dashboard'))
        
        # Kontroller at tilbuddet tilhører den aktuelle håndværker
        if bid['craftsman_id'] != flask_login.current_user.id:
            flash('Du har ikke adgang til at redigere dette tilbud.', 'error')
            return redirect(url_for('håndværker_dashboard'))
        
        # Kontroller at tilbuddet ikke allerede er accepteret eller afvist
        if bid['status'] != 'pending':
            flash('Dette tilbud kan ikke længere redigeres.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=bid['ticket_id']))
        
        if request.method == 'POST':
            amount = request.form.get('amount', '').strip()
            description = request.form.get('description', '').strip()
            
            # Validering
            errors = []
            if not amount:
                errors.append('Beløb er påkrævet.')
            else:
                try:
                    # Konverter til float og tjek om det er et positivt tal
                    amount_float = float(amount.replace(',', '.'))
                    if amount_float <= 0:
                        errors.append('Beløb skal være større end 0.')
                except ValueError:
                    errors.append('Beløb skal være et tal.')
            
            if not description:
                errors.append('Beskrivelse er påkrævet.')
            
            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('edit_bid.html', bid=bid)
            
            # Konverter beløb til float
            amount_float = float(amount.replace(',', '.'))
            
            # Opdater tilbud
            conn.execute('''
                UPDATE bids 
                SET amount = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (amount_float, description, bid_id))
            
            # Tilføj til ticket-historik
            add_ticket_history(bid['ticket_id'], flask_login.current_user.id, 'bid_updated', str(bid['amount']), str(amount_float), existing_conn=conn)
            
            conn.commit()
            flash('Dit tilbud er blevet opdateret.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=bid['ticket_id']))
        
        return render_template('edit_bid.html', bid=bid)
    except Exception as e:
        print(f"Fejl ved redigering af tilbud: {e}")
        flash('Der opstod en fejl ved redigering af tilbud.', 'error')
        conn.rollback()
        return redirect(url_for('craftsman_dashboard'))
    finally:
        conn.close()

@app.route("/ticket/<int:ticket_id>/assign_craftsman", methods=["GET", "POST"])
@flask_login.login_required
def assign_craftsman(ticket_id):
    # Kontroller at brugeren er admin eller udlejer
    if flask_login.current_user.role not in ['admin', 'udlejer']:
        flash('Du har ikke adgang til at tildele håndværkere.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent ticket
        ticket = conn.execute('''
            SELECT t.*, u.username as udlejer_name, c.username as craftsman_name
            FROM tickets t
            LEFT JOIN users u ON t.udlejer = u.id
            LEFT JOIN users c ON t.craftsman_id = c.id
            WHERE t.id = ?
        ''', (ticket_id,)).fetchone()
        
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang for udlejer
        if flask_login.current_user.role == 'udlejer':
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at tildele håndværkere til denne ticket.', 'error')
                return redirect(url_for('index'))
        
        # Hent håndværkere baseret på brugerrolle
        if flask_login.current_user.role == 'admin':
            # Admin kan se alle håndværkere
            craftsmen = conn.execute('''
                SELECT id, username, company_name, speciality, phone
                FROM users
                WHERE role = 'craftsman'
                ORDER BY username
            ''').fetchall()
        else:
            # Udlejere kan kun se håndværkere tilknyttet dem
            craftsmen = conn.execute('''
                SELECT u.id, u.username, u.company_name, u.speciality, u.phone
                FROM users u
                JOIN craftsman_landlord_relations clr ON u.id = clr.craftsman_id
                WHERE clr.landlord_id = ? AND u.role = 'craftsman'
                ORDER BY u.username
            ''', (flask_login.current_user.id,)).fetchall()
        
        if request.method == 'POST':
            craftsman_id = request.form.get('craftsman_id', '')
            requires_bid = request.form.get('requires_bid', 'off') == 'on'
            approve_immediately = request.form.get('approve_immediately', 'off') == 'on'
            
            # Validering
            if craftsman_id == '':
                flash('Du skal vælge en håndværker.', 'error')
                return render_template('assign_craftsman.html', ticket=ticket, craftsmen=craftsmen)
            
            # Konverter craftsman_id til int
            craftsman_id = int(craftsman_id)
            
            # Hvis udlejer, tjek om håndværkeren er tilknyttet udlejeren
            if flask_login.current_user.role == 'udlejer':
                relation = conn.execute('''
                    SELECT * FROM craftsman_landlord_relations
                    WHERE craftsman_id = ? AND landlord_id = ?
                ''', (craftsman_id, flask_login.current_user.id)).fetchone()
                
                if not relation:
                    # Tilføj relationen, da udlejeren nu tildeler denne håndværker
                    conn.execute('''
                        INSERT OR IGNORE INTO craftsman_landlord_relations (craftsman_id, landlord_id)
                        VALUES (?, ?)
                    ''', (craftsman_id, flask_login.current_user.id))
            
            # Opdater ticket
            old_craftsman_id = ticket['craftsman_id']
            old_craftsman_status = ticket['craftsman_status'] if 'craftsman_status' in ticket.keys() else 'pending'
            
            # Sæt craftsman_status baseret på om håndværkeren skal godkendes med det samme
            craftsman_status = 'approved' if approve_immediately else 'pending'
            
            conn.execute('''
                UPDATE tickets 
                SET craftsman_id = ?, requires_bid = ?, craftsman_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (craftsman_id, requires_bid, craftsman_status, ticket_id))
            
            # Hent håndværkerens navn
            craftsman = conn.execute('SELECT username FROM users WHERE id = ?', (craftsman_id,)).fetchone()
            craftsman_name = craftsman['username'] if craftsman else 'Ukendt håndværker'
            
            # Tilføj til ticket-historik
            if old_craftsman_id != craftsman_id:
                old_craftsman = None
                if old_craftsman_id:
                    old_craftsman_user = conn.execute('SELECT username FROM users WHERE id = ?', (old_craftsman_id,)).fetchone()
                    if old_craftsman_user:
                        old_craftsman = old_craftsman_user['username']
                
                add_ticket_history(ticket_id, flask_login.current_user.id, 'craftsman_changed', old_craftsman, craftsman_name, existing_conn=conn)
            
            # Hvis håndværkeren godkendes med det samme, tilføj det til historikken
            if approve_immediately and old_craftsman_status != 'approved':
                add_ticket_history(ticket_id, flask_login.current_user.id, 'craftsman_approved', None, craftsman_name, existing_conn=conn)
            
            conn.commit()
            
            if approve_immediately:
                flash(f'Håndværker {craftsman_name} er blevet tildelt og godkendt til denne ticket.', 'success')
            else:
                if requires_bid:
                    flash(f'Håndværker {craftsman_name} er blevet tildelt til denne ticket og skal afgive tilbud.', 'success')
                else:
                    flash(f'Håndværker {craftsman_name} er blevet tildelt til denne ticket og afventer godkendelse.', 'success')
            
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        return render_template('assign_craftsman.html', ticket=ticket, craftsmen=craftsmen)
    except Exception as e:
        print(f"Fejl ved tildeling af håndværker: {e}")
        flash('Der opstod en fejl ved tildeling af håndværker.', 'error')
        conn.rollback()
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    finally:
        conn.close()

@app.route("/ticket/<int:ticket_id>/approve_craftsman", methods=["POST"])
@flask_login.login_required
def approve_craftsman(ticket_id):
    # Kontroller at brugeren er admin eller udlejer
    if flask_login.current_user.role not in ['admin', 'udlejer']:
        flash('Du har ikke adgang til at godkende håndværkere.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent ticket
        ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang for udlejer
        if flask_login.current_user.role == 'udlejer':
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at godkende håndværkere til denne ticket.', 'error')
                return redirect(url_for('index'))
        
        # Kontroller at der er en håndværker tildelt
        if not ticket['craftsman_id']:
            flash('Der er ingen håndværker tildelt denne ticket.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Opdater ticket
        conn.execute('''
            UPDATE tickets 
            SET craftsman_status = 'approved', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (ticket_id,))
        
        # Hent håndværkerens navn
        craftsman = conn.execute('SELECT username FROM users WHERE id = ?', (ticket['craftsman_id'],)).fetchone()
        craftsman_name = craftsman['username'] if craftsman else 'Ukendt håndværker'
        
        # Tilføj til ticket-historik
        add_ticket_history(ticket_id, flask_login.current_user.id, 'craftsman_approved', None, craftsman_name, existing_conn=conn)
        
        conn.commit()
        flash(f'Håndværker {craftsman_name} er blevet godkendt til denne ticket.', 'success')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    except Exception as e:
        print(f"Fejl ved godkendelse af håndværker: {e}")
        flash('Der opstod en fejl ved godkendelse af håndværker.', 'error')
        conn.rollback()
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    finally:
        conn.close()

@app.route("/bid/<int:bid_id>/accept", methods=["POST"])
@flask_login.login_required
def accept_bid(bid_id):
    # Kontroller at brugeren er admin eller udlejer
    if flask_login.current_user.role not in ['admin', 'udlejer']:
        flash('Du har ikke adgang til at acceptere tilbud.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent tilbud
        bid = conn.execute('''
            SELECT b.*, t.id as ticket_id, t.unit_id, u.username as craftsman_name
            FROM bids b
            JOIN tickets t ON b.ticket_id = t.id
            LEFT JOIN users u ON b.craftsman_id = u.id
            WHERE b.id = ?
        ''', (bid_id,)).fetchone()
        
        if bid is None:
            flash('Tilbud findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang for udlejer
        if flask_login.current_user.role == 'udlejer':
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (bid['unit_id'],)).fetchone()
            
            if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at acceptere tilbud til denne ticket.', 'error')
                return redirect(url_for('index'))
        
        # Opdater tilbud
        conn.execute('''
            UPDATE bids 
            SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (bid_id,))
        
        # Afvis alle andre tilbud for denne ticket
        conn.execute('''
            UPDATE bids 
            SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
            WHERE ticket_id = ? AND id != ?
        ''', (bid['ticket_id'], bid_id))
        
        # Tildel håndværkeren til ticket'en og godkend med det samme
        conn.execute('''
            UPDATE tickets 
            SET craftsman_id = ?, craftsman_status = 'approved', bid_accepted = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (bid['craftsman_id'], bid['ticket_id']))
        
        # Tilføj til ticket-historik
        add_ticket_history(bid['ticket_id'], flask_login.current_user.id, 'bid_accepted', None, str(bid['amount']), existing_conn=conn)
        add_ticket_history(bid['ticket_id'], flask_login.current_user.id, 'craftsman_approved', None, bid['craftsman_name'], existing_conn=conn)
        
        conn.commit()
        flash(f'Tilbud på {bid["amount"]} kr. fra {bid["craftsman_name"]} er blevet accepteret.', 'success')
        return redirect(url_for('ticket_detail', ticket_id=bid['ticket_id']))
    except Exception as e:
        print(f"Fejl ved accept af tilbud: {e}")
        flash('Der opstod en fejl ved accept af tilbud.', 'error')
        conn.rollback()
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route("/bid/<int:bid_id>/reject", methods=["POST"])
@flask_login.login_required
def reject_bid(bid_id):
    # Kontroller at brugeren er admin eller udlejer
    if flask_login.current_user.role not in ['admin', 'udlejer']:
        flash('Du har ikke adgang til at afvise tilbud.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent tilbud
        bid = conn.execute('''
            SELECT b.*, t.id as ticket_id, t.unit_id, u.username as craftsman_name
            FROM bids b
            JOIN tickets t ON b.ticket_id = t.id
            LEFT JOIN users u ON b.craftsman_id = u.id
            WHERE b.id = ?
        ''', (bid_id,)).fetchone()
        
        if bid is None:
            flash('Tilbud findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang for udlejer
        if flask_login.current_user.role == 'udlejer':
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (bid['unit_id'],)).fetchone()
            
            if not property_owner or property_owner['owner_id'] != flask_login.current_user.id:
                flash('Du har ikke adgang til at afvise tilbud til denne ticket.', 'error')
                return redirect(url_for('index'))
        
        # Opdater tilbud
        conn.execute('''
            UPDATE bids 
            SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (bid_id,))
        
        # Tilføj til ticket-historik
        add_ticket_history(bid['ticket_id'], flask_login.current_user.id, 'bid_rejected', None, str(bid['amount']), existing_conn=conn)
        
        conn.commit()
        flash(f'Tilbud på {bid["amount"]} kr. fra {bid["craftsman_name"]} er blevet afvist.', 'success')
        return redirect(url_for('ticket_detail', ticket_id=bid['ticket_id']))
    except Exception as e:
        print(f"Fejl ved afvisning af tilbud: {e}")
        flash('Der opstod en fejl ved afvisning af tilbud.', 'error')
        conn.rollback()
        return redirect(url_for('index'))
    finally:
        conn.close()

# --- Routes til billeder ---

@app.route("/ticket/<int:ticket_id>/upload_image", methods=["POST"])
@flask_login.login_required
def upload_image(ticket_id):
    """
    Route til at uploade et billede til en ticket.
    """
    conn = get_db_connection()
    try:
        # Hent ticket
        ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang baseret på brugerrolle
        has_permission = False
        
        if flask_login.current_user.role == 'admin':
            # Admin har altid adgang
            has_permission = True
        elif flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun uploade billeder til tickets på deres egne ejendomme
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if property_owner and property_owner['owner_id'] == flask_login.current_user.id:
                has_permission = True
        elif flask_login.current_user.role == 'craftsman':
            # Håndværkere kan kun uploade billeder, hvis de er godkendt til denne ticket
            if str(flask_login.current_user.id) == str(ticket['craftsman_id']) and ticket['craftsman_status'] == 'approved':
                has_permission = True
        
        if not has_permission:
            flash('Du har ikke tilladelse til at uploade billeder til denne ticket.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Kontroller om der er uploadet en fil
        if 'image' not in request.files:
            flash('Ingen fil valgt.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        file = request.files['image']
        
        # Hvis brugeren ikke har valgt en fil
        if file.filename == '':
            flash('Ingen fil valgt.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Valider at filen er et billede
        if not image_helpers.allowed_file(file.filename):
            flash('Ugyldig filtype. Tilladte filtyper: png, jpg, jpeg, gif.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Gem billedet
        image_id = image_helpers.save_image(
            file, 
            ticket_id, 
            flask_login.current_user.id, 
            app.config, 
            add_ticket_history, 
            get_db_connection
        )
        
        if image_id:
            flash('Billede uploadet!', 'success')
        else:
            flash('Fejl ved upload af billede.', 'error')
        
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    except Exception as e:
        print(f"Fejl ved upload af billede: {e}")
        flash('Der opstod en fejl ved upload af billede.', 'error')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    finally:
        conn.close()

@app.route("/ticket/image/<int:image_id>/delete", methods=["POST"])
@flask_login.login_required
def delete_ticket_image(image_id):
    """
    Route til at slette et billede fra en ticket.
    """
    conn = get_db_connection()
    try:
        # Hent billedinformation
        image = conn.execute("SELECT * FROM ticket_images WHERE id = ?", (image_id,)).fetchone()
        
        if not image:
            flash('Billede findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Hent ticket
        ticket_id = image['ticket_id']
        ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if not ticket:
            flash('Ticket findes ikke!', 'error')
            return redirect(url_for('index'))
        
        # Kontroller adgang baseret på brugerrolle
        has_permission = False
        
        if flask_login.current_user.role == 'admin':
            # Admin har altid adgang
            has_permission = True
        elif flask_login.current_user.role == 'udlejer':
            # Udlejere kan kun slette billeder fra tickets på deres egne ejendomme
            property_owner = conn.execute('''
                SELECT p.owner_id 
                FROM properties p 
                JOIN units u ON p.id = u.property_id 
                WHERE u.id = ?
            ''', (ticket['unit_id'],)).fetchone()
            
            if property_owner and property_owner['owner_id'] == flask_login.current_user.id:
                has_permission = True
        
        if not has_permission:
            flash('Du har ikke tilladelse til at slette billeder fra denne ticket.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Slet billedet
        success = image_helpers.delete_image(
            image_id, 
            flask_login.current_user.id, 
            get_db_connection, 
            add_ticket_history
        )
        
        if success:
            flash('Billede slettet!', 'success')
        else:
            flash('Fejl ved sletning af billede.', 'error')
        
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    except Exception as e:
        print(f"Fejl ved sletning af billede: {e}")
        flash('Der opstod en fejl ved sletning af billede.', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route("/udlejer/manage_craftsmen", methods=["GET", "POST"])
@flask_login.login_required
def udlejer_manage_craftsmen():
    # Kontroller at brugeren er udlejer
    if flask_login.current_user.role != 'udlejer':
        flash('Du har ikke adgang til denne side.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    try:
        # Hent udlejerens ID
        udlejer_id = flask_login.current_user.id
        
        # Hent håndværkere tilknyttet udlejeren
        craftsmen = conn.execute('''
            SELECT u.* 
            FROM users u
            JOIN craftsman_landlord_relations clr ON u.id = clr.craftsman_id
            WHERE clr.landlord_id = ? AND u.role = 'craftsman'
            ORDER BY u.username
        ''', (udlejer_id,)).fetchall()
        
        # Hent alle håndværkere der ikke er tilknyttet udlejeren
        available_craftsmen = conn.execute('''
            SELECT u.* 
            FROM users u
            WHERE u.role = 'craftsman'
            AND u.id NOT IN (
                SELECT craftsman_id 
                FROM craftsman_landlord_relations 
                WHERE landlord_id = ?
            )
            ORDER BY u.username
        ''', (udlejer_id,)).fetchall()
        
        if request.method == 'POST':
            action = request.form.get('action')
            craftsman_id = request.form.get('craftsman_id')
            
            if not craftsman_id:
                flash('Ingen håndværker valgt.', 'error')
                return redirect(url_for('udlejer_manage_craftsmen'))
            
            try:
                craftsman_id = int(craftsman_id)
            except ValueError:
                flash('Ugyldigt håndværker-ID.', 'error')
                return redirect(url_for('udlejer_manage_craftsmen'))
            
            # Tjek om håndværkeren eksisterer
            craftsman = conn.execute('SELECT * FROM users WHERE id = ? AND role = "craftsman"', (craftsman_id,)).fetchone()
            if not craftsman:
                flash('Håndværkeren findes ikke.', 'error')
                return redirect(url_for('udlejer_manage_craftsmen'))
            
            if action == 'add':
                # Tilføj håndværker til udlejerens liste
                conn.execute('''
                    INSERT OR IGNORE INTO craftsman_landlord_relations (craftsman_id, landlord_id)
                    VALUES (?, ?)
                ''', (craftsman_id, udlejer_id))
                conn.commit()
                flash(f'Håndværker {craftsman["username"]} er blevet tilføjet til din liste.', 'success')
            
            elif action == 'remove':
                # Fjern håndværker fra udlejerens liste
                conn.execute('''
                    DELETE FROM craftsman_landlord_relations
                    WHERE craftsman_id = ? AND landlord_id = ?
                ''', (craftsman_id, udlejer_id))
                conn.commit()
                flash(f'Håndværker {craftsman["username"]} er blevet fjernet fra din liste.', 'success')
            
            return redirect(url_for('udlejer_manage_craftsmen'))
        
        return render_template(
            "udlejer_manage_craftsmen.html",
            craftsmen=craftsmen,
            available_craftsmen=available_craftsmen
        )
    except Exception as e:
        print(f"Fejl ved håndtering af håndværkere: {e}")
        flash('Der opstod en fejl ved håndtering af håndværkere.', 'error')
        conn.rollback()
        return redirect(url_for('udlejer_kontrolpanel'))
    finally:
        conn.close()

if __name__ == '__main__':
    # Brug fast port 5001
    app.run(debug=True, port=5001)
