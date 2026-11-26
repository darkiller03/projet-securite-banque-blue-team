"""Fonctions métier bancaires — PARTIE BACK (Youssef).

Version minimale fonctionnelle pour que le front et la démo marchent.
Youssef : tu peux réécrire l'intérieur librement, garde juste les
signatures (le front appelle uniquement ces fonctions).
"""
import random
from decimal import Decimal, InvalidOperation

from werkzeug.security import generate_password_hash

from db import get_db, query

SOLDE_INITIAL = Decimal("1000.00")


class ErreurBancaire(Exception):
    """Erreur métier affichable à l'utilisateur."""


def _nouveau_numero():
    # Numéro fictif façon IBAN FR (pas un vrai IBAN valide)
    while True:
        numero = "FR76" + "".join(random.choices("0123456789", k=23))
        if not query("SELECT 1 FROM comptes WHERE numero = %s", (numero,), one=True):
            return numero


def creer_client_et_compte(nom, prenom, email, mot_de_passe):
    """Inscrit un client et lui ouvre un compte avec un solde initial.
    Retourne l'id du client."""
    email = email.strip().lower()
    if query("SELECT 1 FROM clients WHERE email = %s", (email,), one=True):
        raise ErreurBancaire("Un compte existe déjà avec cet e-mail.")

    conseiller = query("SELECT id FROM conseillers ORDER BY id LIMIT 1", one=True)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO clients (nom, prenom, email, mot_de_passe, conseiller_id)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (nom.strip(), prenom.strip(), email,
             generate_password_hash(mot_de_passe),
             conseiller["id"] if conseiller else None),
        )
        client_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO comptes (numero, client_id, solde) VALUES (%s, %s, %s)",
            (_nouveau_numero(), client_id, SOLDE_INITIAL),
        )
    db.commit()
    return client_id


def compte_du_client(client_id):
    return query("SELECT * FROM comptes WHERE client_id = %s ORDER BY id LIMIT 1",
                 (client_id,), one=True)


def historique(compte_id, limite=20):
    """Opérations du compte, signe + pour un crédit, - pour un débit."""
    return query(
        """SELECT o.date_operation, o.libelle,
                  CASE WHEN o.compte_source = %s THEN -o.montant ELSE o.montant END AS montant,
                  CASE WHEN o.compte_source = %s THEN cd.numero ELSE cs.numero END AS autre_compte
           FROM operations o
           LEFT JOIN comptes cs ON cs.id = o.compte_source
           LEFT JOIN comptes cd ON cd.id = o.compte_dest
           WHERE o.compte_source = %s OR o.compte_dest = %s
           ORDER BY o.date_operation DESC LIMIT %s""",
        (compte_id, compte_id, compte_id, compte_id, limite),
    )


def virement(compte_source_id, numero_dest, montant, libelle=""):
    """Débite la source, crédite la destination et enregistre l'opération,
    le tout dans une seule transaction."""
    try:
        montant = Decimal(str(montant).replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ErreurBancaire("Montant invalide.")
    if montant <= 0:
        raise ErreurBancaire("Le montant doit être positif.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM comptes WHERE numero = %s",
                        (numero_dest.strip().replace(" ", ""),))
            dest = cur.fetchone()
            if not dest:
                raise ErreurBancaire("Compte destinataire introuvable.")
            if dest["id"] == compte_source_id:
                raise ErreurBancaire("Impossible de virer vers le même compte.")

            # Verrouille les deux comptes (ordre fixe pour éviter les interblocages)
            cur.execute("SELECT id, solde FROM comptes WHERE id IN (%s, %s) ORDER BY id FOR UPDATE",
                        (compte_source_id, dest["id"]))
            soldes = {r["id"]: r["solde"] for r in cur.fetchall()}
            if soldes[compte_source_id] < montant:
                raise ErreurBancaire("Solde insuffisant.")

            cur.execute("UPDATE comptes SET solde = solde - %s WHERE id = %s",
                        (montant, compte_source_id))
            cur.execute("UPDATE comptes SET solde = solde + %s WHERE id = %s",
                        (montant, dest["id"]))
            cur.execute(
                """INSERT INTO operations (compte_source, compte_dest, montant, libelle)
                   VALUES (%s, %s, %s, %s)""",
                (compte_source_id, dest["id"], montant, (libelle or "Virement")[:140]),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
