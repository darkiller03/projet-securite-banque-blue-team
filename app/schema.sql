-- Schéma de l'appli bancaire fictive (Banque Coopérative du Sillon)
-- Tables clients / comptes / operations : partie back (Youssef)
-- Tables conseillers / messages : messagerie client-conseiller (Rayane)

CREATE TABLE IF NOT EXISTS conseillers (
    id            SERIAL PRIMARY KEY,
    nom           VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    mot_de_passe  VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id            SERIAL PRIMARY KEY,
    nom           VARCHAR(100) NOT NULL,
    prenom        VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    mot_de_passe  VARCHAR(255) NOT NULL,
    conseiller_id INTEGER REFERENCES conseillers(id),
    cree_le       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comptes (
    id        SERIAL PRIMARY KEY,
    numero    VARCHAR(34) NOT NULL UNIQUE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    solde     NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (solde >= 0),
    ouvert_le TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operations (
    id             SERIAL PRIMARY KEY,
    compte_source  INTEGER REFERENCES comptes(id),
    compte_dest    INTEGER REFERENCES comptes(id),
    montant        NUMERIC(12, 2) NOT NULL CHECK (montant > 0),
    libelle        VARCHAR(140),
    date_operation TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id         SERIAL PRIMARY KEY,
    client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    auteur     VARCHAR(10) NOT NULL CHECK (auteur IN ('client', 'conseiller')),
    contenu    TEXT NOT NULL,
    envoye_le  TIMESTAMP NOT NULL DEFAULT NOW(),
    lu         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_messages_client ON messages(client_id, envoye_le);
CREATE INDEX IF NOT EXISTS idx_operations_source ON operations(compte_source);
CREATE INDEX IF NOT EXISTS idx_operations_dest ON operations(compte_dest);
