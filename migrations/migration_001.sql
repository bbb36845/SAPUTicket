-- Migration 001: Tilføjer nye tabeller for dokumenter, beskeder, notifikationer og invitationer

-- Dokument-tabel
CREATE TABLE IF NOT EXISTS ticket_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Besked-system
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id TEXT NOT NULL,
    receiver_id TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read INTEGER DEFAULT 0,  -- 0: ulæst, 1: læst
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Notifikationssystem
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL,  -- fx: 'ticket', 'message', 'comment'
    reference_id TEXT,  -- ID på den relaterede entitet
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read INTEGER DEFAULT 0,  -- 0: ulæst, 1: læst
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Tilføj nye felter til users-tabellen for invitationer, hvis de ikke allerede findes
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS invitation_expires_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;

-- Tilføj nye felter til bids-tabellen for vedhæftninger af tilbudsdokumenter
ALTER TABLE bids ADD COLUMN IF NOT EXISTS document_id INTEGER;
ALTER TABLE bids ADD COLUMN IF NOT EXISTS document_filename TEXT;
ALTER TABLE bids ADD COLUMN IF NOT EXISTS document_path TEXT;

-- Opdater eksisterende tabeller med created_at og updated_at, hvis de ikke allerede findes
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE units ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE units ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE bids ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP; 