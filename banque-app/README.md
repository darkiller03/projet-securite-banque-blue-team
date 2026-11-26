# Banque de Proximité du Centre (BPC) — appli de démonstration

Appli web de la banque fictive du projet sécurité INSA (groupe Hassini).
Elle sert à **démontrer les fonctions métier** de la banque :

- création de compte client (numéro unique `BPC…`, 100 € offerts à l'ouverture) ;
- connexion / déconnexion (mots de passe stockés hachés) ;
- consultation du numéro de compte, du solde et de l'historique ;
- **virement** d'un compte BPC à un autre ;
- **messagerie** entre le client et son conseiller, affichée comme une conversation.

C'est volontairement une appli **simple**, pour la démonstration.

## Lancer en local (sur son PC, pour développer)

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python3 app.py
```

Puis ouvrir http://localhost:5000

Sans configuration, l'appli utilise un fichier **SQLite** (`banque.db`) créé
automatiquement : aucune base à installer pour tester.

Pour activer le mode debug pendant le développement : `FLASK_DEBUG=1 venv/bin/python3 app.py`.
**Ne jamais l'activer sur la VM** : il ouvre une console Python dans le
navigateur à la moindre erreur.

**Compte conseiller par défaut** (pour la démo) :
- email : `conseiller@banque.local`
- mot de passe : `conseiller`

## Lancer sur la VM, avec PostgreSQL

Sur la VM, une fois PostgreSQL installé et une base `banque` créée :

```bash
export DATABASE_URL="postgresql://user:motdepasse@127.0.0.1/banque"
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python3 app.py
```

L'appli détecte `DATABASE_URL` et utilise PostgreSQL au lieu de SQLite.
Elle écoute sur `0.0.0.0:5000`, donc elle est joignable depuis le réseau
(par le client « Internet » de la démo) : `http://<IP de la VM>:5000`.

Sans `SECRET_KEY`, une clé aléatoire est générée à chaque démarrage : l'appli
marche, mais les clients sont déconnectés à chaque redémarrage.

## Test automatique du parcours complet

```bash
venv/bin/python3 -m unittest -v test_parcours
```

Le test crée deux clients, vérifie le hachage des mots de passe, la connexion,
les soldes de départ, les virements refusés (solde insuffisant, destinataire
inexistant, montant nul, négatif, invalide ou à plus de 2 décimales, virement
vers soi-même, débit du compte d'un autre), un virement valide de 30 € avec les
soldes et l'historique des deux côtés, l'échange client / conseiller et la
déconnexion. Il utilise une base SQLite temporaire et ne touche pas à `banque.db`.

Pour le jouer contre PostgreSQL sur la VM, définir `DATABASE_URL` avant de le lancer.

## Scénario de démonstration (à jouer devant l'enseignant)

Durée : environ 10 minutes. Le serveur tourne sur la VM ; les clients se
connectent **depuis une autre machine** (le poste « Internet »), avec deux
navigateurs différents (ou une fenêtre normale + une fenêtre privée).

**Préparation** : lancer l'appli sur la VM, ouvrir `http://<IP de la VM>:5000`
sur le poste client et vérifier que la page d'accueil s'affiche.

1. **Ouverture du compte A.** Navigateur 1 → « Ouvrir un compte » →
   nom « Alice Martin », un email, un mot de passe. → *Attendu* : message
   « Compte créé », redirection vers la connexion.
2. **Connexion de A.** Se connecter. → *Attendu* : page « Mon compte » avec
   un numéro `BPC…` et un solde de **100,00 €**, aucune opération.
   *Option* : montrer d'abord qu'un mauvais mot de passe est refusé.
3. **Ouverture et connexion du compte B.** Navigateur 2 → même chose avec
   « Bob Durand ». → *Attendu* : un **autre** numéro `BPC…`, 100,00 €.
   Noter ce numéro.
4. **Virements refusés** (depuis A, page « Virement ») :
   - 150 € vers B → « Solde insuffisant » ;
   - 10 € vers `BPC00000000` → « Le compte destinataire n'existe pas » ;
   - 10 € vers son propre numéro → refusé.
   → *Attendu* : le solde de A est toujours de 100,00 €.
5. **Virement valide.** A vire **30 €** vers le numéro de B.
   → *Attendu* : message de confirmation, solde de A à **70,00 €**,
   ligne **-30,00 €** dans l'historique de A.
6. **Côté B.** Recharger « Mon compte » dans le navigateur 2.
   → *Attendu* : solde de B à **130,00 €**, ligne **+30,00 €** dans son historique.
7. **Message au conseiller.** A → « Mon conseiller » → écrire
   « Bonjour, pouvez-vous confirmer mon virement ? ».
8. **Réponse du conseiller.** Navigateur 2 → « Déconnexion », puis connexion
   avec `conseiller@banque.local` / `conseiller`. → *Attendu* : la messagerie
   conseiller liste **Alice Martin** (et pas Bob, qui n'a pas écrit).
   Ouvrir l'échange, lire le message, répondre « Votre virement est bien passé ».
9. **Conversation.** Navigateur 1 → recharger « Mon conseiller ».
   → *Attendu* : les deux messages s'affichent dans l'ordre, comme une conversation.
10. **Déconnexion.** A → « Déconnexion », puis essayer d'ouvrir `/mon-compte`.
    → *Attendu* : renvoi vers la page de connexion.

## Répartition du code (groupe)

- `app.py` : routes et logique métier (Youssef).
- `templates/` : pages HTML (Rayane).
- `static/style.css` : mise en forme (Rayane).
- Déploiement sur la VM + PostgreSQL (Med Aziz).

## Structure

```
banque-app/
├── app.py              # l'application (routes + base)
├── test_parcours.py    # test automatique du parcours complet
├── requirements.txt    # dépendances Python
├── templates/          # pages HTML
├── static/style.css    # style
└── README.md
```
