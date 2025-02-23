CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT,
        invitation_token TEXT,  -- Tilføjet
        invited_by INTEGER,      -- Tilføjet
        unit_id INTEGER,       -- Tilføjet
        FOREIGN KEY (invited_by) REFERENCES users(id),
        FOREIGN KEY (unit_id) REFERENCES units(id)
    );

    -- Husk at have oprettet properties og units tabeller.
    DROP TABLE IF EXISTS properties;

    CREATE TABLE properties(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users(id)
    );

    DROP TABLE IF EXISTS units;

    CREATE TABLE units(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        address TEXT NOT NULL,
        property_id INTEGER NOT NULL,
        tenant_id INTEGER,
        FOREIGN KEY (property_id) REFERENCES properties(id)
        FOREIGN KEY (tenant_id) REFERENCES users(id)
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
        unit_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (unit_id) REFERENCES units(id)
    );
    ```