import sqlite3
import os  # Importer os modulet
from flask import Flask, render_template, request, redirect, flash
from functools import wraps


app = Flask(__name__)
app.secret_key = 'en_super_hemmelig_nøgle'  # VIGTIGT: Skift dette i produktion!

# Brug absolut sti til databasen OG schema.sql
DATABASE = os.path.join(app.root_path, 'tickets.db')
SCHEMA = os.path.join(app.root_path, 'schema.sql')
print(f"DATABASE sti: {DATABASE}")  # Debugging
print(f"SCHEMA sti: {SCHEMA}")  # Debugging


def get_db_connection():
    print(f"Forsøger at forbinde til: {DATABASE}")  # Debugging
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    print("init_db() kaldt")  # Debugging
    try:
        conn = get_db_connection()
        with open(SCHEMA, 'r') as f:
            print(f"Åbner schemafil: {SCHEMA}") #Mere debugging
            sql_script = f.read()
            print(f"SQL script:\n{sql_script}") # Mere debugging
            conn.executescript(sql_script)
        conn.commit()
        conn.close()
        print("init_db() afsluttet (forhåbentlig uden fejl)")  # Debugging
    except Exception as e:
        print(f"Fejl i init_db(): {e}")  # VIGTIGT: Fang og print evt. fejl


# Kør init_db() HVIS databasen ikke eksisterer.
if not os.path.exists(DATABASE):
    print(f"Databasefilen findes ikke: {DATABASE}") # Debugging
    init_db()
else:
    print(f"Databasefilen findes: {DATABASE}") # Debugging
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == 'admin' and auth.password == 'hemmeligt'):
            return "Adgang nægtet", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
        return f(*args, **kwargs)
    return decorated
@app.route("/")
def index():
    conn = get_db_connection()
    try:
        tickets = conn.execute('SELECT * FROM tickets').fetchall()
        print(f"Hentede tickets: {tickets}") # Debugging
    except sqlite3.OperationalError as e:
        print(f"Fejl ved hentning af tickets: {e}") #Mere debugging.
        tickets = []
    finally:
        conn.close()
    return render_template("index.html", tickets=tickets)


@app.route("/create", methods=["POST"])
def create_ticket():
    lejer = request.form["lejer"]
    beskrivelse = request.form["beskrivelse"]
    udlejer = request.form["udlejer"]

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO tickets (lejer, beskrivelse, status, udlejer) VALUES (?, ?, ?, ?)",
            (lejer, beskrivelse, "Oprettet", udlejer),
        )
        conn.commit()
        flash('Ticket oprettet!', 'success')  # Tilføjet flash-besked
    except Exception as e:
        print(f"Fejl ved oprettelse af ticket: {e}")  # Behold denne
        flash(f'Fejl ved oprettelse af ticket: {e}', 'error')  # Tilføjet flash-besked
        # Overvej at rulle transaktionen tilbage: conn.rollback()
    finally:
        conn.close()
    return redirect("/")
@app.route("/admin")
@requires_auth  # Tilføj denne linje!
def admin():
    conn = get_db_connection()
    tickets = conn.execute('SELECT * FROM tickets').fetchall()
    conn.close()
    return render_template("admin.html", tickets=tickets)
@app.route("/delete/<int:ticket_id>", methods=["POST"])
def delete_ticket(ticket_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        conn.commit()
        flash('Ticket slettet!', 'success') #Tilføjet flash besked.
    except Exception as e:
        print(f"Fejl ved sletning af ticket {e}") #Behold denne.
        flash(f'Fejl ved sletning af ticket {e}', 'error') #Tilføjet flash besked.
    finally:
        conn.close()
    return redirect("/admin")
@app.route("/edit/<int:ticket_id>", methods=["GET"])
def edit_ticket(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    conn.close()

    if ticket is None:
        flash('Ticket findes ikke!', 'error')
        return redirect('/admin')

    return render_template("edit.html", ticket=ticket)


@app.route("/edit/<int:ticket_id>", methods=["POST"])
def update_ticket(ticket_id):
    lejer = request.form["lejer"]
    beskrivelse = request.form["beskrivelse"]
    status = request.form["status"]  # Hentet fra formularen
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