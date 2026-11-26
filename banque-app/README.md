# Banque de Proximité du Centre (BPC) — appli de démonstration

Appli web de la banque fictive du projet sécurité INSA (groupe Hassini).
Elle sert à **démontrer les fonctions métier** de la banque :

- création de compte client (100 € offerts à l'ouverture) ;
- connexion ;
- consultation du solde et de l'historique ;
- **virement** d'un compte BPC à un autre ;
- **messagerie** entre le client et son conseiller.

C'est volontairement une appli **simple**, pour la démonstration.

## Lancer en local (sur son PC, pour développer)

```bash
pip install -r requirements.txt
python app.py
```

Puis ouvrir http://localhost:5000

Sans configuration, l'appli utilise un fichier **SQLite** (`banque.db`) créé
automatiquement : aucune base à installer pour tester.

**Compte conseiller par défaut** (pour la démo) :
- email : `conseiller@banque.local`
- mot de passe : `conseiller`

## Lancer sur la VM, avec PostgreSQL

Sur la VM, une fois PostgreSQL installé et une base `banque` créée :

```bash
export DATABASE_URL="postgresql://user:motdepasse@127.0.0.1/banque"
export SECRET_KEY="une-chaine-aleatoire"
pip install -r requirements.txt
python app.py
```

L'appli détecte `DATABASE_URL` et utilise PostgreSQL au lieu de SQLite.
Elle écoute sur `0.0.0.0:5000`, donc elle est joignable depuis le réseau
(par le client « Internet » de la démo).

## Scénario de démonstration (à jouer devant le prof)

1. Un visiteur ouvre un compte (**Client A**) → 100 € de solde.
2. Il ouvre un deuxième compte (**Client B**) depuis un autre navigateur.
   Noter les deux numéros de compte (BPC...).
3. Client A écrit à son conseiller (page « Mon conseiller »).
4. Se connecter en conseiller → lire le message → répondre.
5. Client A fait un **virement** de 30 € vers le compte de Client B.
6. Montrer que le solde de A passe à 70 € et celui de B à 130 €.

## Répartition du code (groupe)

- `app.py` : routes et logique métier (Youssef).
- `templates/` : pages HTML (Rayane).
- `static/style.css` : mise en forme (Rayane).
- Déploiement sur la VM + PostgreSQL (Med Aziz).

## Structure

```
banque-app/
├── app.py              # l'application (routes + base)
├── requirements.txt    # dépendances Python
├── templates/          # pages HTML
├── static/style.css    # style
└── README.md
```
