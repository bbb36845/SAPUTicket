import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, flash, url_for
import flask_login
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'en_super_hemmelig_nøgle'  # Skift dette i produktion!

# Brug absolut sti til databasen OG schema.sql.
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

    conn = get_db_connection()
    try:
        #Hent unit_id fra den bruger der er logget ind:
        cur = conn.cursor()
        cur.execute(
            "SELECT unit_id FROM users WHERE id = ?", (flask_login.current_user.id,)
        )
        unit_id = cur.fetchone()[0]


        conn.execute(
            "INSERT INTO tickets (lejer, beskrivelse, status, udlejer, user_id, unit_id) VALUES (?, ?, ?, ?, ?, ?)",
            (lejer, beskrivelse, "Oprettet", udlejer, flask_login.current_user.id, unit_id),
        )
        conn.commit()
        flash('Ticket oprettet!', 'success')
    except Exception as e:
        print(f"Fejl ved oprettelse af ticket: {e}")
        flash(f'Fejl ved oprettelse af ticket: {e}', 'error')
        conn.rollback()  # Tilføjet rollback
    finally:
        conn.close()
    return redirect("/")

@app.route("/admin")
@flask_login.login_required
def admin():
    conn = get_db_connection()
    try:
        tickets = conn.execute('SELECT * FROM tickets').fetchall()
    except Exception as e:
        print(f"Fejl ved hentning af tickets til admin: {e}")  # Opdateret print statement
        tickets = []
    finally:
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
    try:
        ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect('/admin')
        return render_template("edit.html", ticket=ticket)
    except Exception as e:
        print(f"Fejl ved hentning af ticket for redigering: {e}")
        flash('Fejl ved hentning af ticket til redigering', 'error')
        return redirect('/admin')
    finally:
        conn.close()

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
        conn.rollback()
    finally:
        conn.close()
    return redirect("/admin")

@app.route("/ticket/<int:ticket_id>")
@flask_login.login_required
def ticket_detail(ticket_id):
    conn = get_db_connection()
    try:
        ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if ticket is None:
            flash('Ticket findes ikke!', 'error')
            return redirect('/admin')
        return render_template("ticket.html", ticket=ticket)
    except Exception as e:
        print(f"Fejl ved hentning af ticket detaljer: {e}")
        flash(f'Fejl ved hentning af ticket detaljer', 'error')
        return redirect('/admin')
    finally:
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = get_user(username)

        if user and check_password_hash(user.password_hash, password):
            flask_login.login_user(user)
            flash(f'Velkommen {user.username}!', 'success')
            return redirect('/admin')  # Eller en anden beskyttet side
        else:
            flash('Forkert brugernavn eller adgangskode.', 'error')
            return redirect('/login')

    return render_template('login.html')

@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    flash('Du er nu logget ud!', 'success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = "lejer"
        unit_id = 1

        errors = []

        if not username:
            errors.append('Brugernavn er påkrævet.')
        if not password:
            errors.append('Adgangskode er påkrævet.')
        if not confirm_password:
            errors.append('Bekræft adgangskode er påkrævet.')
        if password != confirm_password:
            errors.append('Adgangskoderne stemmer ikke overens.')

        conn = get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if existing_user:
            errors.append('Brugernavnet er allerede i brug.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html', username=username, role=role)

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, unit_id) VALUES (?, ?, ?, ?)",
                (username, hashed_password, role, unit_id)
            )
            conn.commit()
            flash('Bruger oprettet!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Fejl ved oprettelse af bruger: {e}")
            flash(f'Fejl ved oprettelse af bruger. Se server log for detaljer.', 'error')
            conn.rollback()
        finally:
            conn.close()

    return render_template('register.html')

if __name__ == '__main__':
     app.run(debug=True, port=5001)