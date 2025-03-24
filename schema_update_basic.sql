-- Grundlæggende databaseudvidelse for SAPUTicket-systemet

-- Tilføj tidsstempler til tickets-tabellen (uden CURRENT_TIMESTAMP som standardværdi)
ALTER TABLE tickets ADD COLUMN created_at TIMESTAMP;
ALTER TABLE tickets ADD COLUMN updated_at TIMESTAMP;

-- Opdater eksisterende rækker med den aktuelle tidsstempel
-- Dette gøres i app.py efter at kolonnerne er tilføjet

-- Opret tabel til kommentarer
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    visible_to_tenant BOOLEAN DEFAULT 1,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Opret tabel til ticket-historik
CREATE TABLE IF NOT EXISTS ticket_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
); 