"""Portail de la Banque Coopérative du Sillon (fictive).

Front + messagerie client/conseiller : Rayane
Fonctions bancaires (banque.py) : Youssef
"""
import os
import secrets
from functools import wraps

import click
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import banque
from db import close_db, execute, init_db, query

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.teardown_appcontext(close_db)


# ---------------------------------------------------------------- sécurité

@app.before_request
def csrf_protect():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST":
        if request.form.get("csrf") != session["csrf"]:
            abort(400, "Jeton CSRF invalide")


@app.context_processor
def inject_globals():
    return {"csrf": session.get("csrf", "")}


def client_requis(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "client":
            return redirect(url_for("connexion"))
        g.client = query("SELECT * FROM clients WHERE id = %s", (session["uid"],), one=True)
        if not g.client:
            session.clear()
            return redirect(url_for("connexion"))
        return f(*a, **kw)
    return wrapper


def conseiller_requis(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "conseiller":
            return redirect(url_for("conseiller_connexion"))
        g.conseiller = query("SELECT id, nom, email FROM conseillers WHERE id = %s",
                             (session["uid"],), one=True)
        if not g.conseiller:
            session.clear()
            return redirect(url_for("conseiller_connexion"))
        return f(*a, **kw)
    return wrapper


def ouvrir_session(role, uid):
    session.clear()
    session["role"], session["uid"] = role, uid
    session["csrf"] = secrets.token_hex(16)


# ---------------------------------------------------------------- client

@app.route("/")
def accueil():
    if session.get("role") == "client":
        return redirect(url_for("mon_compte"))
    if session.get("role") == "conseiller":
        return redirect(url_for("conseiller_messages"))
    return render_template("accueil.html")


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if request.method == "POST":
        f = request.form
        champs = [f.get(k, "").strip() for k in ("nom", "prenom", "email", "mot_de_passe")]
        if not all(champs):
            flash("Tous les champs sont obligatoires.", "erreur")
        elif len(champs[3]) < 8:
            flash("Le mot de passe doit faire au moins 8 caractères.", "erreur")
        elif champs[3] != f.get("confirmation"):
            flash("Les mots de passe ne correspondent pas.", "erreur")
        else:
            try:
                client_id = banque.creer_client_et_compte(*champs)
            except banque.ErreurBancaire as e:
                flash(str(e), "erreur")
            else:
                ouvrir_session("client", client_id)
                flash(f"Bienvenue ! Votre compte est ouvert avec {banque.SOLDE_INITIAL} €.", "ok")
                return redirect(url_for("mon_compte"))
    return render_template("inscription.html")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        client = query("SELECT id, mot_de_passe FROM clients WHERE email = %s", (email,), one=True)
        if client and check_password_hash(client["mot_de_passe"], request.form.get("mot_de_passe", "")):
            ouvrir_session("client", client["id"])
            return redirect(url_for("mon_compte"))
        app.logger.warning("Echec de connexion client pour %s depuis %s", email, request.remote_addr)
        flash("E-mail ou mot de passe incorrect.", "erreur")
    return render_template("connexion.html", titre="Espace client", action=url_for("connexion"))


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("accueil"))


@app.route("/compte")
@client_requis
def mon_compte():
    compte = banque.compte_du_client(g.client["id"])
    ops = banque.historique(compte["id"]) if compte else []
    non_lus = query("""SELECT COUNT(*) AS n FROM messages
                       WHERE client_id = %s AND auteur = 'conseiller' AND NOT lu""",
                    (g.client["id"],), one=True)["n"]
    return render_template("compte.html", compte=compte, operations=ops, non_lus=non_lus)


@app.route("/virement", methods=["GET", "POST"])
@client_requis
def faire_virement():
    compte = banque.compte_du_client(g.client["id"])
    if request.method == "POST":
        try:
            banque.virement(compte["id"], request.form.get("numero_dest", ""),
                            request.form.get("montant", ""), request.form.get("libelle", "").strip())
        except banque.ErreurBancaire as e:
            flash(str(e), "erreur")
        else:
            flash("Virement effectué.", "ok")
            return redirect(url_for("mon_compte"))
    return render_template("virement.html", compte=compte)


@app.route("/conseiller-contact", methods=["GET", "POST"])
@client_requis
def contacter_conseiller():
    cid = g.client["id"]
    if request.method == "POST":
        contenu = request.form.get("contenu", "").strip()
        if contenu:
            execute("INSERT INTO messages (client_id, auteur, contenu) VALUES (%s, 'client', %s)",
                    (cid, contenu[:2000]))
            flash("Message envoyé à votre conseiller.", "ok")
        return redirect(url_for("contacter_conseiller"))
    execute("UPDATE messages SET lu = TRUE WHERE client_id = %s AND auteur = 'conseiller'", (cid,))
    conseiller = query("SELECT nom FROM conseillers WHERE id = %s",
                       (g.client["conseiller_id"],), one=True)
    msgs = query("SELECT * FROM messages WHERE client_id = %s ORDER BY envoye_le", (cid,))
    return render_template("messages_client.html", messages=msgs, conseiller=conseiller)


# ---------------------------------------------------------------- conseiller

@app.route("/conseiller/connexion", methods=["GET", "POST"])
def conseiller_connexion():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        c = query("SELECT id, mot_de_passe FROM conseillers WHERE email = %s", (email,), one=True)
        if c and check_password_hash(c["mot_de_passe"], request.form.get("mot_de_passe", "")):
            ouvrir_session("conseiller", c["id"])
            return redirect(url_for("conseiller_messages"))
        app.logger.warning("Echec de connexion conseiller pour %s depuis %s", email, request.remote_addr)
        flash("E-mail ou mot de passe incorrect.", "erreur")
    return render_template("connexion.html", titre="Espace conseiller",
                           action=url_for("conseiller_connexion"))


@app.route("/conseiller")
@conseiller_requis
def conseiller_messages():
    clients = query(
        """SELECT c.id, c.prenom, c.nom, c.email,
                  COUNT(m.id) FILTER (WHERE m.auteur = 'client' AND NOT m.lu) AS non_lus,
                  MAX(m.envoye_le) AS dernier
           FROM clients c LEFT JOIN messages m ON m.client_id = c.id
           WHERE c.conseiller_id = %s
           GROUP BY c.id ORDER BY non_lus DESC, dernier DESC NULLS LAST""",
        (g.conseiller["id"],))
    return render_template("conseiller_liste.html", clients=clients)


@app.route("/conseiller/client/<int:client_id>", methods=["GET", "POST"])
@conseiller_requis
def conseiller_conversation(client_id):
    client = query("SELECT id, prenom, nom, email FROM clients WHERE id = %s AND conseiller_id = %s",
                   (client_id, g.conseiller["id"]), one=True)
    if not client:
        abort(404)
    if request.method == "POST":
        contenu = request.form.get("contenu", "").strip()
        if contenu:
            execute("INSERT INTO messages (client_id, auteur, contenu) VALUES (%s, 'conseiller', %s)",
                    (client_id, contenu[:2000]))
        return redirect(url_for("conseiller_conversation", client_id=client_id))
    execute("UPDATE messages SET lu = TRUE WHERE client_id = %s AND auteur = 'client'", (client_id,))
    compte = banque.compte_du_client(client_id)
    msgs = query("SELECT * FROM messages WHERE client_id = %s ORDER BY envoye_le", (client_id,))
    return render_template("conseiller_conversation.html", client=client, compte=compte, messages=msgs)


# ---------------------------------------------------------------- commandes

@app.cli.command("init-db")
def init_db_cmd():
    """Crée les tables."""
    init_db()
    click.echo("Tables créées.")


@app.cli.command("creer-conseiller")
@click.argument("nom")
@click.argument("email")
@click.password_option()
def creer_conseiller(nom, email, password):
    """Crée un compte conseiller : flask creer-conseiller "Mme Martin" martin@banque.local"""
    execute("INSERT INTO conseillers (nom, email, mot_de_passe) VALUES (%s, %s, %s)",
            (nom, email.lower(), generate_password_hash(password)))
    click.echo(f"Conseiller {nom} créé.")


@app.template_filter("iban")
def iban(v):
    return " ".join(v[i:i + 4] for i in range(0, len(v or ""), 4))


@app.template_filter("euros")
def euros(v):
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",")


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
