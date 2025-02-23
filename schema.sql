DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT
);

DROP TABLE IF EXISTS tickets;

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lejer TEXT NOT NULL,
    beskrivelse TEXT NOT NULL,
    status TEXT NOT NULL,
    udlejer TEXT NOT NULL,
    håndværker TEXT,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);