"""
Banque de Proximité du Centre (BPC) — appli de démonstration.

Projet sécurité INSA — groupe Hassini.
Appli volontairement SIMPLE : elle sert à montrer que les fonctions métier
de la banque marchent (créer un compte, se connecter, faire un virement,
écrire à son conseiller).

Lancer en local :
    pip install -r requirements.txt
    python app.py
Puis ouvrir http://localhost:5000

Base de données : PostgreSQL si la variable DATABASE_URL est définie,
sinon un fichier SQLite local (banque.db) pour pouvoir tester sans rien installer.
"""
import os
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Flask, g, redirect, render_template, request, session, url_for, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Sans SECRET_KEY, une clé aléatoire est générée à chaque démarrage (les sessions
# sont alors perdues au redémarrage). Une clé connue de tous permettrait de
# fabriquer de faux cookies de session : ne jamais en mettre une en dur.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# --- Choix de la base : PostgreSQL (prod sur la VM) ou SQLite (test local) ---
DATABASE_URL = os.environ.get("DATABASE_URL")  # ex: postgresql://user:pass@10.x.x.x/banque
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    def get_db():
        if "db" not in g:
            g.db = psycopg2.connect(DATABASE_URL)
        return g.db

    def query(sql, params=(), one=False, commit=False):
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), params)
        result = None
        if not commit:
            rows = cur.fetchall()
            result = (rows[0] if rows else None) if one else rows
        else:
            db.commit()
        cur.close()
        return result

    def execute(sql, params=()):
        """Exécute sans valider la transaction ; renvoie le nombre de lignes touchées."""
        cur = get_db().cursor()
        cur.execute(sql.replace("?", "%s"), params)
        n = cur.rowcount
        cur.close()
        return n
else:
    import sqlite3

    SQLITE_PATH = os.environ.get("SQLITE_PATH", "banque.db")

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(SQLITE_PATH)
            g.db.row_factory = sqlite3.Row
        return g.db

    def _sqlite_params(params):
        # SQLite ne connaît pas le type Decimal : on convertit en float.
        return tuple(float(p) if isinstance(p, Decimal) else p for p in params)

    def execute(sql, params=()):
        """Exécute sans valider la transaction ; renvoie le nombre de lignes touchées."""
        return get_db().execute(sql, _sqlite_params(params)).rowcount

    def query(sql, params=(), one=False, commit=False):
        db = get_db()
        params = _sqlite_params(params)
        cur = db.execute(sql, params)
        result = None
        if not commit:
            rows = cur.fetchall()
            result = (rows[0] if rows else None) if one else rows
        else:
            db.commit()
        cur.close()
        return result


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --- Création des tables au premier lancement ---
def init_db():
    serial = "SERIAL" if USE_POSTGRES else "INTEGER"
    pk = f"id {serial} PRIMARY KEY" if USE_POSTGRES else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    query(f"""
        CREATE TABLE IF NOT EXISTS clients (
            {pk},
            email TEXT UNIQUE NOT NULL,
            nom TEXT NOT NULL,
            mot_de_passe TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'client'
        )
    """, commit=True)
    query(f"""
        CREATE TABLE IF NOT EXISTS comptes (
            {pk},
            client_id INTEGER NOT NULL,
            numero TEXT UNIQUE NOT NULL,
            solde NUMERIC NOT NULL DEFAULT 0
        )
    """, commit=True)
    query(f"""
        CREATE TABLE IF NOT EXISTS operations (
            {pk},
            compte_source TEXT,
            compte_dest TEXT,
            montant NUMERIC NOT NULL,
            date_op TEXT NOT NULL,
            libelle TEXT
        )
    """, commit=True)
    query(f"""
        CREATE TABLE IF NOT EXISTS messages (
            {pk},
            client_id INTEGER NOT NULL,
            auteur TEXT NOT NULL,
            contenu TEXT NOT NULL,
            date_msg TEXT NOT NULL
        )
    """, commit=True)
    # Un conseiller par défaut pour la démo
    existe = query("SELECT id FROM clients WHERE email = ?", ("conseiller@banque.local",), one=True)
    if not existe:
        query(
            "INSERT INTO clients (email, nom, mot_de_passe, role) VALUES (?, ?, ?, ?)",
            ("conseiller@banque.local", "Conseiller BPC",
             generate_password_hash("conseiller"), "conseiller"),
            commit=True,
        )


def nouveau_numero():
    return "BPC" + secrets.token_hex(4).upper()


CENTIME = Decimal("0.01")


def lire_montant(texte):
    """Convertit la saisie en Decimal. Renvoie None si ce n'est pas un nombre fini."""
    try:
        montant = Decimal(texte.strip().replace(",", "."))
    except InvalidOperation:
        return None
    return montant if montant.is_finite() else None


def a_plus_de_deux_decimales(montant):
    try:
        return montant != montant.quantize(CENTIME)
    except InvalidOperation:  # nombre démesuré
        return True


def faire_virement(client_id, source, dest, montant):
    """Débit + crédit + historique dans UNE transaction.

    Le débit n'a lieu que si le solde suffit, vérifié dans la même requête
    UPDATE : deux virements simultanés ne peuvent pas rendre le solde négatif.
    Renvoie True si le virement est passé, False si le solde est insuffisant.
    """
    db = get_db()
    try:
        debite = execute(
            "UPDATE comptes SET solde = ROUND(solde - ?, 2) "
            "WHERE numero = ? AND client_id = ? AND solde >= ?",
            (montant, source, client_id, montant),
        )
        if debite != 1:
            db.rollback()
            return False
        execute("UPDATE comptes SET solde = ROUND(solde + ?, 2) WHERE numero = ?", (montant, dest))
        execute(
            "INSERT INTO operations (compte_source, compte_dest, montant, date_op, libelle) "
            "VALUES (?, ?, ?, ?, ?)",
            (source, dest, montant, datetime.now().strftime("%Y-%m-%d %H:%M"), "Virement"),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# --- Authentification ---
def utilisateur_courant():
    uid = session.get("uid")
    if uid is None:
        return None
    return query("SELECT * FROM clients WHERE id = ?", (uid,), one=True)


@app.route("/")
def accueil():
    return render_template("accueil.html", user=utilisateur_courant())


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip().lower()
        mdp = request.form.get("mot_de_passe", "")
        if not nom or not email or not mdp:
            flash("Tous les champs sont obligatoires.", "erreur")
            return render_template("inscription.html")
        if query("SELECT id FROM clients WHERE email = ?", (email,), one=True):
            flash("Un compte existe déjà avec cet email.", "erreur")
            return render_template("inscription.html")
        # Création du client
        query(
            "INSERT INTO clients (email, nom, mot_de_passe, role) VALUES (?, ?, ?, ?)",
            (email, nom, generate_password_hash(mdp), "client"),
            commit=True,
        )
        client = query("SELECT id FROM clients WHERE email = ?", (email,), one=True)
        # Création de son compte avec 100 € de bienvenue
        query(
            "INSERT INTO comptes (client_id, numero, solde) VALUES (?, ?, ?)",
            (client["id"], nouveau_numero(), Decimal("100.00")),
            commit=True,
        )
        flash("Compte créé ! Vous pouvez vous connecter.", "ok")
        return redirect(url_for("connexion"))
    return render_template("inscription.html")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        mdp = request.form.get("mot_de_passe", "")
        client = query("SELECT * FROM clients WHERE email = ?", (email,), one=True)
        if client and check_password_hash(client["mot_de_passe"], mdp):
            session.clear()  # repart d'une session neuve à chaque connexion
            session["uid"] = client["id"]
            return redirect(url_for("espace_conseiller") if client["role"] == "conseiller"
                            else url_for("mon_compte"))
        flash("Email ou mot de passe incorrect.", "erreur")
    return render_template("connexion.html")


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("accueil"))


@app.route("/mon-compte")
def mon_compte():
    user = utilisateur_courant()
    if not user:
        return redirect(url_for("connexion"))
    comptes = query("SELECT * FROM comptes WHERE client_id = ?", (user["id"],))
    numeros = [c["numero"] for c in comptes]
    operations = []
    if numeros:
        placeholders = ",".join("?" for _ in numeros)
        operations = query(
            f"""SELECT * FROM operations
                WHERE compte_source IN ({placeholders}) OR compte_dest IN ({placeholders})
                ORDER BY id DESC""",
            numeros + numeros,
        )
    return render_template("mon_compte.html", user=user, comptes=comptes,
                           operations=operations, mes_numeros=numeros)


@app.route("/virement", methods=["GET", "POST"])
def virement():
    user = utilisateur_courant()
    if not user:
        return redirect(url_for("connexion"))
    comptes = query("SELECT * FROM comptes WHERE client_id = ?", (user["id"],))
    if request.method == "POST":
        source = request.form.get("source", "")
        dest = request.form.get("dest", "").strip()
        montant = lire_montant(request.form.get("montant", ""))

        compte_src = query("SELECT * FROM comptes WHERE numero = ? AND client_id = ?",
                           (source, user["id"]), one=True)
        compte_dst = query("SELECT * FROM comptes WHERE numero = ?", (dest,), one=True)

        if not compte_src:
            flash("Compte source invalide.", "erreur")
        elif not compte_dst:
            flash("Le compte destinataire n'existe pas.", "erreur")
        elif source == dest:
            flash("Impossible de faire un virement vers le même compte.", "erreur")
        elif montant is None:
            flash("Montant invalide.", "erreur")
        elif montant <= 0:
            flash("Le montant doit être positif.", "erreur")
        elif a_plus_de_deux_decimales(montant):
            flash("Le montant ne peut pas dépasser les centimes (2 décimales).", "erreur")
        elif not faire_virement(user["id"], source, dest, montant):
            flash("Solde insuffisant.", "erreur")
        else:
            flash(f"Virement de {montant:.2f} € effectué vers {dest}.", "ok")
            return redirect(url_for("mon_compte"))
        comptes = query("SELECT * FROM comptes WHERE client_id = ?", (user["id"],))
    return render_template("virement.html", user=user, comptes=comptes)


@app.route("/messages", methods=["GET", "POST"])
def messages():
    user = utilisateur_courant()
    if not user or user["role"] != "client":
        return redirect(url_for("connexion"))
    if request.method == "POST":
        contenu = request.form.get("contenu", "").strip()
        if contenu:
            query(
                "INSERT INTO messages (client_id, auteur, contenu, date_msg) VALUES (?, ?, ?, ?)",
                (user["id"], "client", contenu, datetime.now().strftime("%Y-%m-%d %H:%M")),
                commit=True,
            )
        return redirect(url_for("messages"))
    fils = query("SELECT * FROM messages WHERE client_id = ? ORDER BY id", (user["id"],))
    return render_template("messages.html", user=user, fils=fils)


@app.route("/conseiller")
def espace_conseiller():
    user = utilisateur_courant()
    if not user or user["role"] != "conseiller":
        return redirect(url_for("connexion"))
    # Liste des clients ayant écrit
    clients = query("""
        SELECT DISTINCT c.id, c.nom, c.email
        FROM clients c JOIN messages m ON m.client_id = c.id
        ORDER BY c.nom
    """)
    return render_template("conseiller.html", user=user, clients=clients)


@app.route("/conseiller/<int:client_id>", methods=["GET", "POST"])
def conseiller_fil(client_id):
    user = utilisateur_courant()
    if not user or user["role"] != "conseiller":
        return redirect(url_for("connexion"))
    client = query("SELECT * FROM clients WHERE id = ?", (client_id,), one=True)
    if not client:
        abort(404)
    if request.method == "POST":
        contenu = request.form.get("contenu", "").strip()
        if contenu:
            query(
                "INSERT INTO messages (client_id, auteur, contenu, date_msg) VALUES (?, ?, ?, ?)",
                (client_id, "conseiller", contenu, datetime.now().strftime("%Y-%m-%d %H:%M")),
                commit=True,
            )
        return redirect(url_for("conseiller_fil", client_id=client_id))
    fils = query("SELECT * FROM messages WHERE client_id = ? ORDER BY id", (client_id,))
    return render_template("conseiller_fil.html", user=user, client=client, fils=fils)


if __name__ == "__main__":
    with app.app_context():
        init_db()
    # host=0.0.0.0 pour que la VM soit joignable depuis le réseau.
    # Le mode debug (console Python dans le navigateur en cas d'erreur) n'est
    # activé que sur demande : FLASK_DEBUG=1, et jamais sur la VM de démo.
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
