# Portail bancaire — Banque Coopérative du Sillon (fictive)

Application web Flask + PostgreSQL. Elle joue le rôle du portail client (WEB01) et de l'appli métier des conseillers (CORE01) décrits dans `docs/architecture.md`.

| Fichier | Contenu | Responsable |
|---|---|---|
| `banque.py` | Création de compte, virement, historique (fonctions métier) | Youssef |
| `app.py`, `templates/`, `static/` | Pages web + messagerie client / conseiller | Rayane |
| `schema.sql` | Tables `clients`, `comptes`, `operations` (back) + `conseillers`, `messages` (messagerie) | Youssef / Rayane |

`banque.py` contient une version minimale qui marche. Youssef peut la réécrire librement tant que les signatures restent les mêmes (`creer_client_et_compte`, `compte_du_client`, `historique`, `virement`).

## Pages

| URL | Qui | Rôle |
|---|---|---|
| `/inscription` | client | Crée le client et un compte avec 1 000 € |
| `/connexion` | client | Connexion |
| `/compte` | client | Solde, historique, nombre de messages non lus |
| `/virement` | client | Virement vers un autre numéro de compte |
| `/conseiller-contact` | client | Fil de discussion avec son conseiller |
| `/conseiller/connexion` | conseiller | Connexion |
| `/conseiller` | conseiller | Liste de ses clients, messages non lus en premier |
| `/conseiller/client/<id>` | conseiller | Conversation + solde du client, réponse |

## Lancer en local

```bash
cd app
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Base PostgreSQL
sudo -u postgres psql -c "CREATE USER banque WITH PASSWORD 'banque_dev';"
sudo -u postgres psql -c "CREATE DATABASE banque OWNER banque;"

export FLASK_APP=app.py
export DATABASE_URL=postgresql://banque:banque_dev@localhost:5432/banque
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

flask init-db
flask creer-conseiller "Mme Martin" martin@banque.local   # demande le mot de passe
flask run
```

Puis ouvrir http://127.0.0.1:5000.

## Mise en ligne sur la VM Debian (Med Aziz)

```bash
sudo apt install -y python3-venv postgresql
# mêmes étapes que ci-dessus, puis :
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

Les variables `DATABASE_URL` et `SECRET_KEY` ne doivent **jamais** être commitées. On les met dans un `.env` (déjà ignoré par git) ou dans l'unité systemd.

## Scénario de démo

1. Client : `/inscription` → compte ouvert avec 1 000 €.
2. Client : « Mon conseiller » → envoie un message.
3. Conseiller : `/conseiller/connexion` → voit la pastille rouge, ouvre la conversation et répond.
4. Client : le compte affiche « 1 nouveau message », il lit la réponse.
5. Client : « Virement » vers le numéro de compte d'un second client → les deux soldes changent et l'opération apparaît dans les deux historiques.

Astuce : créer le second client avant la démo, dans une fenêtre de navigation privée, et copier son numéro de compte.

## Sécurité déjà en place (utile pour la partie blue team)

- Mots de passe hachés (`werkzeug`, PBKDF2 / scrypt)
- Requêtes SQL paramétrées partout (pas d'injection SQL)
- Jeton CSRF sur tous les formulaires
- Échappement automatique Jinja (pas d'XSS dans la messagerie)
- Un conseiller ne voit que ses propres clients (contrôle d'accès)
- Virement en transaction avec `SELECT … FOR UPDATE` et contrôle du solde
- Échecs de connexion journalisés (pour le SIEM)

Le scénario B de `docs/scenario-attaque.md` prévoit une faille volontaire sur WEB01 : elle sera ajoutée plus tard, sur une branche à part, et documentée dans le dossier animateur.
