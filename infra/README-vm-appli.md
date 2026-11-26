# VM de l'appli bancaire (PostgreSQL + Flask)

Travail de Med Aziz : la VM qui héberge la base de données et l'appli Flask du groupe.

## État au 26/11/2026

- VM `vm-base-de-donnees-postg` (VMID 4000), Debian 13, IP `10.0.0.125` (réseau `vmbr1`, LAN d'OPNsense).
- Déployée par CYO-Infra (infra « Appli banque - VM base de données », brique « VM base de données PostgreSQL »).
- PostgreSQL 17, base `banque` et utilisateur `banque`, Python 3.13 et git.
- Les secrets (mot de passe de la base, clé secrète) sont dans `/etc/banque.env` sur la VM. Ils ne sont **pas** dans git.
- L'appli déployée est `banque-app` (branche `ajout-banque-app`). URL de démo : `http://10.0.0.125:5000`.

## Ce que l'appli doit faire pour fonctionner ici

1. Lire sa connexion dans la variable `DATABASE_URL` (définie dans `/etc/banque.env`) et la clé dans `SECRET_KEY`.
2. Fournir un `requirements.txt`.
3. Créer ses tables : soit un `schema.sql` à la racine du dossier de l'appli, soit une commande passée en `APP_INIT` (exécutée avant chaque démarrage).
4. Exposer un objet Flask pour gunicorn (`APP_MODULE`, par exemple `app:app`).

## Déploiement

`deploy-appli-vm.sh` s'exécute en root sur la VM. Il est rejouable.

Sans le code (installe PostgreSQL et Python, crée la base) :

    ./deploy-appli-vm.sh

Avec le code (clone, installe les dépendances, lance le service `banque` sur le port 5000) :

    REPO_URL=https://github.com/darkiller03/projet-securite-banque-blue-team.git \
    BRANCH=ajout-banque-app APP_SUBDIR=banque-app APP_MODULE=app:app \
    APP_INIT='import app as m; c = m.app.app_context(); c.push(); m.init_db()' \
    ./deploy-appli-vm.sh

Pour redéployer une nouvelle version : relancer la même commande (git fetch + redémarrage du service).

Dépôt privé : clé de déploiement ou jeton saisi à la main, jamais écrit dans le script.

## Accès à la VM

SSH refuse root par mot de passe (`PermitRootLogin without-password`). Depuis le shell du Proxmox, on exécute des commandes avec l'agent invité :

    qm guest exec 4000 -- bash -c 'commande'

Pour envoyer un script : `qm guest exec 4000 --pass-stdin 1 --timeout 900 -- bash < script.sh`.

Journaux de l'appli : `journalctl -u banque -n 50 --no-pager`.
