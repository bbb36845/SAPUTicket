from flask import Flask, render_template

app = Flask(__name__)

# Simpel "database" (en liste i Python - midlertidig!)
tickets = [
    {"id": 1, "lejer": "Lejer A", "beskrivelse": "Vandskade i badeværelset", "status": "Oprettet", "udlejer": "Poseidon Ejendomme", "håndværker": None},
    {"id": 2, "lejer": "Lejer B", "beskrivelse": "Ødelagt vindue", "status": "Tildelt", "udlejer": "Andreasen Ejendomme", "håndværker": "Håndværker X"},
]

@app.route("/")
def index():
    return render_template("index.html", tickets=tickets)

if __name__ == "__main__":
    app.run(debug=True)