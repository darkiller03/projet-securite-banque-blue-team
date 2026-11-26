"""Connexion PostgreSQL (une connexion par requête HTTP)."""
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from flask import g

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://banque:banque_dev@localhost:5432/banque"
)


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
        )
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    """SELECT simple. Toujours des requêtes paramétrées (%s), jamais de f-string."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=(), returning=False):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone() if returning else None
    db.commit()
    return row


def init_db():
    """Crée les tables (idempotent)."""
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(schema)
