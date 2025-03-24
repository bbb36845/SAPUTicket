-- Opret en tabel til at håndtere relationen mellem håndværkere og udlejere
CREATE TABLE IF NOT EXISTS craftsman_landlord_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    craftsman_id INTEGER NOT NULL,
    landlord_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (craftsman_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (landlord_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(craftsman_id, landlord_id)
);

-- Opret indeks for hurtigere søgning
CREATE INDEX IF NOT EXISTS idx_craftsman_landlord_craftsman_id ON craftsman_landlord_relations(craftsman_id);
CREATE INDEX IF NOT EXISTS idx_craftsman_landlord_landlord_id ON craftsman_landlord_relations(landlord_id); 