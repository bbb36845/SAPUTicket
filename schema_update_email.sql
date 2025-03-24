-- Tilføj email-felt til users-tabellen
ALTER TABLE users ADD COLUMN email TEXT;

-- Opdater eksisterende brugere med dummy email-adresser baseret på deres brugernavne
UPDATE users SET email = LOWER(REPLACE(username, ' ', '.')) || '@example.com' WHERE email IS NULL;

-- Opdater app.py til at inkludere email-feltet i brugeroprettelse og -redigering
-- Dette skal gøres manuelt i app.py

-- Opdater skabeloner til at vise og redigere email-feltet
-- Dette skal gøres manuelt i de relevante skabeloner

-- Tilføj indeks på email-feltet for hurtigere søgning
CREATE INDEX idx_users_email ON users(email);

-- Tilføj en UNIQUE constraint på email-feltet (valgfrit, afhængigt af om du vil tillade flere brugere med samme email)
-- ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE(email); 