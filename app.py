import sqlite3
import os  # Importer os modulet
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

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
        print("Ticket oprettet (forhåbentlig!)")  # Debugging
    except Exception as e:
        print(f"Fejl ved oprettelse af ticket: {e}") #Mere debugging.
    finally:
        conn.close()
    return redirect("/")
@app.route("/admin")
def admin():
    # MEGET SIMPEL adgangskontrol (IKKE til produktion!)
    if request.authorization and request.authorization.username == 'admin' and request.authorization.password == 'hemmeligt':
        conn = get_db_connection()
        tickets = conn.execute('SELECT * FROM tickets').fetchall()
        conn.close()
        return render_template("admin.html", tickets=tickets)
    else:
        return "Adgang nægtet", 401  # 401 Unauthorized
@app.route("/delete/<int:ticket_id>", methods=["POST"])
def delete_ticket(ticket_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return redirect("/admin")