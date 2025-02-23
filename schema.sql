-- Slet tabeller, hvis de findes (i omvendt rækkefølge af oprettelse)
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS units;
DROP TABLE IF EXISTS properties;
DROP TABLE IF EXISTS users;


CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT,
    invitation_token TEXT,
    invited_by INTEGER,
    unit_id INTEGER,
    FOREIGN KEY (invited_by) REFERENCES users(id),
    FOREIGN KEY (unit_id) REFERENCES units(id)
);

CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    property_id INTEGER NOT NULL,
    tenant_id INTEGER,
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (tenant_id) REFERENCES users(id)
);

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lejer TEXT NOT NULL,
    beskrivelse TEXT NOT NULL,
    status TEXT NOT NULL,
    udlejer TEXT NOT NULL,
    håndværker TEXT,
    user_id INTEGER,
    unit_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (unit_id) REFERENCES units(id)
);