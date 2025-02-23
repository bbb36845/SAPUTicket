from flask import Flask, render_template, request, redirect

app = Flask(__name__)

# Simpel "database" (en liste i Python - midlertidig!)
tickets = [
    {"id": 1, "lejer": "Lejer A", "beskrivelse": "Vandskade i badeværelset", "status": "Oprettet", "udlejer": "Poseidon Ejendomme", "håndværker": None},
    {"id": 2, "lejer": "Lejer B", "beskrivelse": "Ødelagt vindue", "status": "Tildelt", "udlejer": "Andreasen Ejendomme", "håndværker": "Håndværker X"},
]

@app.route("/")
def index():
    return render_template("index.html", tickets=tickets)


@app.route("/create", methods=["POST"])
def create_ticket():
    lejer = request.form["lejer"]
    beskrivelse = request.form["beskrivelse"]
    udlejer = request.form["udlejer"]

    # Find næste ledige ID (simpel løsning - bedre med database!)
    next_id = max(ticket["id"] for ticket in tickets) + 1

    new_ticket = {
        "id": next_id,
        "lejer": lejer,
        "beskrivelse": beskrivelse,
        "status": "Oprettet",  # Standardstatus
        "udlejer": udlejer,
        "håndværker": None,  # Ingen håndværker tildelt endnu
    }

    tickets.append(new_ticket)
    return redirect("/")

# Fjern denne blok - den er ikke nødvendig på PythonAnywhere, og kan give problemer:
# if __name__ == "__main__":
#     app.run(debug=True)