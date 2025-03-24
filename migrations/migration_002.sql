-- Migration 002: Tilføjer felter til nulstilling af kodeord til users tabellen

-- Tilføj felter til users tabellen for reset token
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires_at TIMESTAMP; 