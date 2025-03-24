-- Databaseudvidelse for SAPUTicket-systemet

-- Tilføj tidsstempler til tickets-tabellen (uden CURRENT_TIMESTAMP som standardværdi)
ALTER TABLE tickets ADD COLUMN created_at TIMESTAMP;
ALTER TABLE tickets ADD COLUMN updated_at TIMESTAMP;
ALTER TABLE tickets ADD COLUMN requires_bid BOOLEAN DEFAULT 0; -- 0 = nej, 1 = ja
ALTER TABLE tickets ADD COLUMN bid_accepted BOOLEAN DEFAULT 0; -- 0 = nej, 1 = ja
ALTER TABLE tickets ADD COLUMN craftsman_id INTEGER; -- Håndværker ID (hvis tildelt)
ALTER TABLE tickets ADD COLUMN craftsman_status TEXT DEFAULT 'pending'; -- pending, approved, rejected

-- Opret tabel til kommentarer
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    visible_to_tenant BOOLEAN DEFAULT 1, -- 0 = nej, 1 = ja (om lejer kan se kommentaren)
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Opret tabel til ticket-historik
CREATE TABLE IF NOT EXISTS ticket_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL, -- f.eks. 'created', 'status_changed', 'comment_added', 'bid_requested', 'bid_accepted'
    old_value TEXT, -- gammel værdi (hvis relevant)
    new_value TEXT, -- ny værdi (hvis relevant)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Opret tabel til tilbud
CREATE TABLE IF NOT EXISTS bids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    craftsman_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL, -- beløb
    description TEXT NOT NULL, -- beskrivelse af tilbuddet
    status TEXT DEFAULT 'pending', -- pending, accepted, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (craftsman_id) REFERENCES users(id)
);

-- Opdater users-tabellen med håndværker-information
ALTER TABLE users ADD COLUMN company_name TEXT; -- Firmanavn (for håndværkere)
ALTER TABLE users ADD COLUMN phone TEXT; -- Telefonnummer
ALTER TABLE users ADD COLUMN address TEXT; -- Adresse
ALTER TABLE users ADD COLUMN cvr TEXT; -- CVR-nummer (for håndværkere)
ALTER TABLE users ADD COLUMN speciality TEXT; -- Specialitet (for håndværkere, f.eks. 'VVS', 'Elektriker', 'Tømrer')

-- Opret indeks for hurtigere søgning
CREATE INDEX IF NOT EXISTS idx_tickets_unit_id ON tickets(unit_id);
CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_ticket_id ON comments(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_history_ticket_id ON ticket_history(ticket_id);
CREATE INDEX IF NOT EXISTS idx_bids_ticket_id ON bids(ticket_id);
CREATE INDEX IF NOT EXISTS idx_bids_craftsman_id ON bids(craftsman_id); 