"""Banque Coopérative du Sillon — appli bancaire fictive (partie back)."""
import logging
import os
import re
import secrets
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

DATABASE_URL = os.environ["DATABASE_URL"]
SOLDE_INITIAL = Decimal(os.environ.get("SOLDE_INITIAL", "500.00"))
MONTANT_MAX = Decimal("50000.00")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

sec_log = logging.getLogger("banque.security")
sec_log.setLevel(logging.INFO)
_handler = logging.FileHandler(os.environ.get("SECURITY_LOG", "banque-security.log"))
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
sec_log.addHandler(_handler)


def log_event(event, **fields):
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    sec_log.info("event=%s ip=%s %s", event, request.remote_addr, extra)


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.cli.command("init-db")
def init_db():
    """Crée les tables : flask --app app init-db"""
    schema = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema, encoding="utf-8") as f, get_db() as db, db.cursor() as cur:
        cur.execute(f.read())
    print("Base initialisée.")


def erreur(message, code=400):
    return jsonify({"erreur": message}), code


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "client_id" not in session:
            return erreur("Authentification requise", 401)
        return fn(*args, **kwargs)
    return wrapper


def parse_montant(valeur):
    try:
        m = Decimal(str(valeur)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    if m <= 0 or m > MONTANT_MAX:
        return None
    return m


def generer_numero(cur):
    while True:
        numero = "FR76" + "".join(str(secrets.randbelow(10)) for _ in range(12))
        cur.execute("SELECT 1 FROM comptes WHERE numero = %s", (numero,))
        if cur.fetchone() is None:
            return numero


@app.get("/api/health")
def health():
    return jsonify({"statut": "ok"})


@app.post("/api/inscription")
def inscription():
    d = request.get_json(silent=True) or {}
    nom = (d.get("nom") or "").strip()
    prenom = (d.get("prenom") or "").strip()
    email = (d.get("email") or "").strip().lower()
    mdp = d.get("mot_de_passe") or ""

    if not nom or not prenom or not EMAIL_RE.match(email):
        return erreur("nom, prenom et email valides requis")
    if len(mdp) < 8:
        return erreur("Mot de passe : 8 caractères minimum")

    db = get_db()
    try:
        with db, db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO clients (nom, prenom, email, mot_de_passe) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (nom, prenom, email, generate_password_hash(mdp)),
            )
            client_id = cur.fetchone()["id"]
            numero = generer_numero(cur)
            cur.execute(
                "INSERT INTO comptes (client_id, numero, solde) VALUES (%s, %s, %s)",
                (client_id, numero, SOLDE_INITIAL),
            )
    except psycopg2.errors.UniqueViolation:
        log_event("inscription_refusee", email=email, raison="email_existant")
        return erreur("Un compte existe déjà avec cet email", 409)

    log_event("inscription", client_id=client_id, compte=numero)
    return jsonify({"client_id": client_id, "numero": numero,
                    "solde": str(SOLDE_INITIAL)}), 201


@app.post("/api/connexion")
def connexion():
    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    mdp = d.get("mot_de_passe") or ""

    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, mot_de_passe, role FROM clients WHERE email = %s", (email,))
        c = cur.fetchone()

    if not c or not check_password_hash(c["mot_de_passe"], mdp):
        log_event("connexion_echec", email=email)
        return erreur("Identifiants invalides", 401)

    session.clear()
    session["client_id"] = c["id"]
    session["role"] = c["role"]
    log_event("connexion_ok", client_id=c["id"])
    return jsonify({"client_id": c["id"], "role": c["role"]})


@app.post("/api/deconnexion")
@login_required
def deconnexion():
    log_event("deconnexion", client_id=session["client_id"])
    session.clear()
    return jsonify({"statut": "deconnecte"})


@app.get("/api/compte")
@login_required
def compte():
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT c.nom, c.prenom, c.email, k.numero, k.solde "
            "FROM clients c JOIN comptes k ON k.client_id = c.id WHERE c.id = %s",
            (session["client_id"],),
        )
        row = cur.fetchone()
    row["solde"] = str(row["solde"])
    return jsonify(row)


@app.post("/api/virement")
@login_required
def virement():
    d = request.get_json(silent=True) or {}
    dest_numero = (d.get("numero_destinataire") or "").strip().replace(" ", "")
    libelle = (d.get("libelle") or "").strip()[:140]
    montant = parse_montant(d.get("montant"))

    if montant is None:
        return erreur(f"Montant invalide (0.01 à {MONTANT_MAX})")
    if not dest_numero:
        return erreur("numero_destinataire requis")

    db = get_db()
    with db, db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, numero FROM comptes WHERE client_id = %s",
                    (session["client_id"],))
        src = cur.fetchone()
        cur.execute("SELECT id FROM comptes WHERE numero = %s", (dest_numero,))
        dst = cur.fetchone()

        if dst is None:
            log_event("virement_refuse", client_id=session["client_id"],
                      raison="destinataire_inconnu", dest=dest_numero)
            return erreur("Compte destinataire introuvable", 404)
        if dst["id"] == src["id"]:
            return erreur("Virement vers son propre compte impossible")

        cur.execute("SELECT id, solde FROM comptes WHERE id IN (%s, %s) "
                    "ORDER BY id FOR UPDATE", (src["id"], dst["id"]))
        soldes = {r["id"]: r["solde"] for r in cur.fetchall()}

        if soldes[src["id"]] < montant:
            log_event("virement_refuse", client_id=session["client_id"],
                      raison="solde_insuffisant", montant=montant)
            return erreur("Solde insuffisant", 422)

        cur.execute("UPDATE comptes SET solde = solde - %s WHERE id = %s",
                    (montant, src["id"]))
        cur.execute("UPDATE comptes SET solde = solde + %s WHERE id = %s",
                    (montant, dst["id"]))
        cur.execute(
            "INSERT INTO operations (compte_source_id, compte_dest_id, montant, libelle) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (src["id"], dst["id"], montant, libelle),
        )
        op_id = cur.fetchone()["id"]
        nouveau_solde = soldes[src["id"]] - montant

    log_event("virement_ok", client_id=session["client_id"], operation=op_id,
              source=src["numero"], dest=dest_numero, montant=montant)
    return jsonify({"operation_id": op_id, "nouveau_solde": str(nouveau_solde)}), 201


@app.get("/api/operations")
@login_required
def operations():
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT o.id, o.montant, o.libelle, o.created_at,
                   s.numero AS source, d.numero AS destinataire,
                   CASE WHEN s.client_id = %(c)s THEN 'debit' ELSE 'credit' END AS sens
            FROM operations o
            JOIN comptes s ON s.id = o.compte_source_id
            JOIN comptes d ON d.id = o.compte_dest_id
            WHERE s.client_id = %(c)s OR d.client_id = %(c)s
            ORDER BY o.created_at DESC
            """,
            {"c": session["client_id"]},
        )
        rows = cur.fetchall()
    for r in rows:
        r["montant"] = str(r["montant"])
        r["created_at"] = r["created_at"].isoformat()
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)