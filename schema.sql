DROP TABLE IF EXISTS tickets;

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lejer TEXT NOT NULL,
    beskrivelse TEXT NOT NULL,
    status TEXT NOT NULL,
    udlejer TEXT NOT NULL,
    håndværker TEXT
);