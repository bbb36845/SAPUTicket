import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, flash, url_for
import flask_login
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'en_super_hemmelig_nøgle'  # Skift dette i produktion!

# Brug absolut sti til databasen OG schema.sql
DATABASE = os.path.join(app.root_path, 'tickets.db')
SCHEMA = os.path.join(app.root_path, 'schema.sql')

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
        return User(user['id'], user['username'], user['password_hash'], user['role'], user['invitation_token'], user['invited_by'], user['unit_id'])
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
    print(f"--- DEBUG: get_db_connection() ---")  # Tilføjet debugging
    print(f"  DATABASE: {DATABASE}")  # Tilføjet debugging
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    print(f"  Forbindelse oprettet: {conn}")  # Tilføj debugging
    return conn

def init_db():
    print("INIT_DB: START")  # Ekstra debugging
    try:
        conn = get_db_connection()
        print(f"INIT_DB: Forbindelse oprettet: {conn}")
        with open(SCHEMA, 'r') as f:
            print(f"INIT_DB: Åbner schemafil: {SCHEMA}")
            sql_script = f.read()
            print(f"INIT_DB: SQL script læst. Længde: {len(sql_script)}")
            # print(f"INIT_DB: SQL script:\n{sql_script}") # Fjern denne, hvis schema.sql er ok
            conn.executescript(sql_script)
        conn.commit()
        conn.close()
        print("INIT_DB: Afsluttet uden fejl (forhåbentlig).")

        # --- EKSTRA DEBUGGING: List tabeller EFTER init_db() ---
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        print(f"INIT_DB: Tabeller efter initialisering: {tables}")
        # --- SLUT på ekstra debugging ---

    except Exception as e:
        print(f"Fejl i init_db(): {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("INIT_DB: Forbindelse lukket (finally).")

# TVING init_db() til at køre - fjern betingelsen.
init_db()

def get_user(username):
    print(f"--- DEBUG: get_user({username}) ---")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        print(f"  SQL: SELECT * FROM users WHERE username = '{username}'")
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()

        print(f"  SQL-forespørgsel udført.")

        if user_data:
            print(f"  Bruger fundet i DB (rå data): {user_data}")
            # --- DEBUG: Vis dataene som dictionary ---
            print("  Brugerdata som dictionary:")
            for key, value in user_data.items():
                print(f"    {key}: {value!r}")
            # --- SLUT på DEBUG ---
            user = User(user_data['id'], user_data['username'], user_data['password_hash'], user_data['role'], user_data['invitation_token'], user_data['invited_by'], user_data['unit_id'])
            print(f"  User objekt oprettet: {user.username}")
            return user
        else:
            print("  Bruger ikke fundet i DB.")
            return None
    except Exception as e:
        print(f"--- DEBUG: Fejl i get_user(): {e}")
        import traceback
        traceback.print_exc()
        return None  # Vigtigt: Returner None ved fejl
    finally:
        conn.close()
        print("--- DEBUG: get_user() afsluttes ---")

@app.route("/")
def index():
    conn = get_db_connection()
    try:
        tickets = conn.execute('SELECT * FROM tickets').fetchall()
    except sqlite3.OperationalError as e:
        print(f"Fejl ved hentning af tickets: {e}")
        tickets = []
    finally:
        conn.close()
    return render_template("index.html", tickets=tickets)


@app.route("/create", methods=["POST"])
@flask_login.login_required
def create_ticket():
    lejer = request.form["lejer"]
    beskrivelse = request.form["beskrivelse"]
    udlejer = request.form["udlejer"]

    #Hent unit_id fra den bruger der er logget ind:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT unit_id FROM users WHERE id = ?", (flask_login.current_user.id,)
    )
    unit_id = cur.fetchone()[0]
    conn.close()

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO tickets (lejer, beskrivelse, status, udlejer, user_id, unit_id) VALUES (?, ?, ?, ?, ?, ?)",
            (lejer, beskrivelse, "Oprettet", udlejer, flask_login.current_user.id, unit_id),
        )
        conn.commit()
        flash('Ticket oprettet!', 'success')
    except Exception as e:
        print(f"Fejl ved oprettelse af ticket: {e}")
        flash(f'Fejl ved oprettelse af ticket: {e}', 'error')
        # Overvej at rulle transaktionen tilbage: conn.rollback()
    finally:
        conn.close()
    return redirect("/")

@app.route("/admin")
@flask_login.login_required
def admin():
    conn = get_db_connection()
    tickets = conn.execute('SELECT * FROM tickets').fetchall()
    conn.close()
    return render_template("admin.html", tickets=tickets)

@app.route("/delete/<int:ticket_id>", methods=["POST"])
@flask_login.login_required
def delete_ticket(ticket_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
        flash('Ticket slettet!', 'success')
    except Exception as e:
        print(f"Fejl ved sletning af ticket: {e}")
        flash(f'Fejl ved sletning af ticket: {e}', 'error')
    finally:
        conn.close()
    return redirect("/admin")

@app.route("/edit/<int:ticket_id>", methods=["GET"])
@flask_login.login_required
def edit_ticket(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    conn.close()

    if ticket is None:
        flash('Ticket findes ikke!', 'error')
        return redirect('/admin')  # Eller vis en 404-side

    return render_template("edit.html", ticket=ticket)


@app.route("/edit/<int:ticket_id>", methods=["POST"])
@flask_login.login_required
def update_ticket(ticket_id):
    lejer = request.form["lejer"]
    beskrivelse = request.form["beskrivelse"]
    status = request.form["status"]
    udlejer = request.form["udlejer"]
    håndværker = request.form["håndværker"]


    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE tickets SET lejer = ?, beskrivelse = ?, status = ?, udlejer = ?, håndværker = ? WHERE id = ?",
            (lejer, beskrivelse, status, udlejer, håndværker, ticket_id),
        )
        conn.commit()
        flash('Ticket opdateret!', 'success')
    except Exception as e:
        print(f"Fejl ved opdatering af ticket: {e}")
        flash(f'Fejl ved opdatering af ticket: {e}', 'error')
        # Evt. conn.rollback()
    finally:
        conn.close()
    return redirect("/admin")

@app.route("/ticket/<int:ticket_id>")
@flask_login.login_required
def ticket_detail(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    conn.close()

    if ticket is None:
        flash('Ticket findes ikke!', 'error')
        return redirect('/admin')  # Eller vis en 404-side

    return render_template("ticket.html", ticket=ticket)

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("--- DEBUG: login() START ---")
    if request.method == 'POST':
        print("--- DEBUG: POST request ---")
        username = request.form['username']
        password = request.form['password']
        print(f"  Indtastet brugernavn: {username}")
        print(f"  Indtastet adgangskode: {password}")

        user = get_user(username)

        if user:
            print(f"  Bruger fundet: {user.username}")
            print(f"  Hashed password fra DB: {user.password_hash}")  # Rå bytes
            is_valid = check_password_hash(user.password_hash, password)
            print(f"  Password check resultat: {is_valid}")

            if is_valid:
                print("  Logger ind...")
                flask_login.login_user(user)
                flash('Du er nu logget ind!', 'success')
                return redirect('/admin')  # Eller en anden beskyttet side
            else:
                print("  Password forkert.")
                flash('Forkert brugernavn eller adgangskode.', 'error')
                return redirect('/login')
        else:
            print("  Bruger IKKE fundet.")
            flash('Forkert brugernavn eller adgangskode.', 'error')
            return redirect('/login')

    else:
        print("--- DEBUG: login() GET request ---")
        return render_template('login.html')

@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    flash('Du er nu logget ud!', 'success')
    return redirect(url_for('index')) # omdiriger til index

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
        unit_id = 1 #Hardcoded, skal ændres.

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
            return render_template('register.html', username=username, role=role)  # Send evt. eksisterende input tilbage
        # --- Validering (slut) ---

        # Hash adgangskoden
        hashed_password = generate_password_hash(password)

        # Opret bruger i databasen
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, unit_id) VALUES (?, ?, ?, ?)",
                (username, hashed_password, role, unit_id)
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