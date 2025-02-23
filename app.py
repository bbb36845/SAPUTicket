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
        return User(user['id'], user['username'], user['password_hash'], user['role'])
    return None

# --- User model (til Flask-Login) ---
class User(flask_login.UserMixin):
    def __init__(self, id, username, password_hash, role=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        with open(SCHEMA, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        print("init_db() afsluttet uden fejl.") # VIGTIGT: Behold denne!
    except Exception as e:
        print(f"Fejl i init_db(): {e}")  # VIGTIGT: Fang og print evt. fejl

def get_user(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['password_hash'], user['role'])
    return None

# Kør init_db() HVIS databasen ikke eksisterer.
if not os.path.exists(DATABASE):
    init_db()

# --- Midlertidig kode til at oprette en testbruger ---
conn = get_db_connection()
if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
    hashed_password = generate_password_hash('hemmeligt')
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ('admin', hashed_password, 'admin')
    )
    conn.commit()
conn.close()
# --- Slut på midlertidig kode ---

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
@flask_login.login_required #Tilføjet login_required decorator.
def create_ticket():
    lejer = request.form["lejer"]
    beskrivelse = request.form["beskrivelse"]
    udlejer = request.form["udlejer"]

    #Hent user_id fra den bruger der er logget ind:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE username = ?", (flask_login.current_user.username,)
    )
    user_id = cur.fetchone()[0]
    conn.close()

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO tickets (lejer, beskrivelse, status, udlejer, user_id) VALUES (?, ?, ?, ?, ?)",
            (lejer, beskrivelse, "Oprettet", udlejer, user_id),
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
@flask_login.login_required #Tilføjet login_required decorator
def delete_ticket(ticket_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
        flash('Ticket slettet!', 'success')
    except Exception as e:
        print(f"Fejl ved sletning af ticket {e}")
        flash(f'Fejl ved sletning af ticket {e}', 'error')
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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user(username)

        if user and check_password_hash(user.password_hash, password):
            flask_login.login_user(user)
            flash('Du er nu logget ind!', 'success')
            return redirect('/admin')  # Eller en anden beskyttet side
        else:
            flash('Forkert brugernavn eller adgangskode.', 'error')
            return redirect('/login')

    return render_template('login.html')

@app.route('/logout')
@flask_login.login_required #Tilføjet login_required decorator
def logout():
    flask_login.logout_user()
    flash('Du er nu logget ud!', 'success')
    return redirect(url_for('index')) # omdiriger til index