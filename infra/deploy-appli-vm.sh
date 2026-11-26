#!/usr/bin/env bash
# Prépare une VM Debian 12 ou 13 pour héberger l'appli bancaire (Flask + PostgreSQL).
# À lancer sur la VM, en root. Rejouable : relancer ne casse rien.
#
# Étape A (sans le code de l'appli) : installe PostgreSQL, Python, crée la base.
#   ./deploy-appli-vm.sh
#
# Étape B (code prêt) : récupère le dépôt, installe les dépendances, lance l'appli en service.
#   REPO_URL=https://github.com/<compte>/<depot>.git BRANCH=<branche> APP_SUBDIR=<dossier> \
#   APP_MODULE=app:app ./deploy-appli-vm.sh
#
# Variables (toutes optionnelles) :
#   REPO_URL    dépôt git de l'appli. Dépôt privé : clé de déploiement ou jeton saisi à la main
#               (jamais écrit dans ce script ni dans git).
#   BRANCH      branche à déployer (défaut : branche par défaut du dépôt)
#   APP_SUBDIR  dossier de l'appli dans le dépôt (défaut : la racine)
#   APP_MODULE  fichier:objet Flask pour gunicorn, défaut app:app
#   APP_INIT    code Python lancé avant chaque démarrage (ex. création des tables), défaut : aucun
#   PORT        port d'écoute, défaut 5000
#   APP_DIR     dossier d'installation, défaut /opt/banque
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Lancer ce script en root." >&2
  exit 1
fi

REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-}"
APP_SUBDIR="${APP_SUBDIR:-}"
APP_MODULE="${APP_MODULE:-app:app}"
APP_INIT="${APP_INIT:-}"
PORT="${PORT:-5000}"
APP_DIR="${APP_DIR:-/opt/banque}"
WORK_DIR="$APP_DIR${APP_SUBDIR:+/$APP_SUBDIR}"
APP_USER="banque"
DB_NAME="banque"
DB_USER="banque"
ENV_FILE="/etc/banque.env"   # secrets de l'appli : jamais dans git

export DEBIAN_FRONTEND=noninteractive

echo "[1/7] Paquets : PostgreSQL, Python, git"
apt-get update -q
apt-get install -y -q postgresql python3 python3-venv python3-pip git curl openssl
systemctl enable --now postgresql >/dev/null

echo "[2/7] Utilisateur système \"$APP_USER\""
id "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"

echo "[3/7] Fichier de secrets $ENV_FILE"
NEW_PASS=0
if [[ ! -f "$ENV_FILE" ]]; then
  DB_PASS=$(openssl rand -hex 16)
  SECRET_KEY=$(openssl rand -hex 32)
  umask 077
  cat >"$ENV_FILE" <<EOF
DB_PASSWORD=$DB_PASS
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
SECRET_KEY=$SECRET_KEY
EOF
  chown root:"$APP_USER" "$ENV_FILE"
  chmod 640 "$ENV_FILE"
  NEW_PASS=1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

echo "[4/7] Base PostgreSQL \"$DB_NAME\" et utilisateur \"$DB_USER\""
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  printf "CREATE ROLE %s LOGIN PASSWORD :'pass';\n" "$DB_USER" \
    | runuser -u postgres -- psql -v ON_ERROR_STOP=1 -v pass="$DB_PASSWORD" >/dev/null
  echo "  utilisateur créé"
elif [[ $NEW_PASS -eq 1 ]]; then
  printf "ALTER ROLE %s PASSWORD :'pass';\n" "$DB_USER" \
    | runuser -u postgres -- psql -v ON_ERROR_STOP=1 -v pass="$DB_PASSWORD" >/dev/null
  echo "  mot de passe de l'utilisateur renouvelé"
else
  echo "  utilisateur déjà présent"
fi
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  runuser -u postgres -- createdb -O "$DB_USER" "$DB_NAME"
  echo "  base créée"
else
  echo "  base déjà présente"
fi

echo "[5/7] Test de connexion avec le compte de l'appli"
PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 'connexion OK'"

if [[ -z "$REPO_URL" ]]; then
  echo
  echo "VM prête : PostgreSQL et Python installés, base \"$DB_NAME\" créée."
  echo "Quand le code est prêt, relancer avec REPO_URL=<url> (et BRANCH, APP_SUBDIR, APP_MODULE si besoin)."
  echo "L'appli doit lire sa connexion dans la variable DATABASE_URL (définie dans $ENV_FILE)."
  exit 0
fi

echo "[6/7] Code de l'appli ($REPO_URL${BRANCH:+, branche $BRANCH})"
if [[ -d "$APP_DIR/.git" ]]; then
  if [[ -n "$BRANCH" ]]; then
    git -c safe.directory="$APP_DIR" -C "$APP_DIR" fetch -q origin "$BRANCH"
    git -c safe.directory="$APP_DIR" -C "$APP_DIR" checkout -q -B "$BRANCH" "origin/$BRANCH"
  else
    git -c safe.directory="$APP_DIR" -C "$APP_DIR" pull -q --ff-only
  fi
else
  git clone -q ${BRANCH:+--branch "$BRANCH"} "$REPO_URL" "$APP_DIR"
fi
[[ -d "$WORK_DIR" ]] || { echo "Dossier introuvable : $WORK_DIR" >&2; exit 1; }
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

runuser -u "$APP_USER" -- python3 -m venv "$APP_DIR/venv"
if [[ -f "$WORK_DIR/requirements.txt" ]]; then
  # psycopg2-binary < 2.9.10 n'a pas de version précompilée pour Python 3.13 (Debian 13) :
  # on relâche cette seule contrainte pour l'installation, sans toucher au fichier du dépôt.
  REQ_TMP=$(mktemp /tmp/requirements.XXXXXX)
  sed -E 's/^psycopg2(-binary)?[=<>~]=?[0-9.]+.*/psycopg2-binary>=2.9.10/I' "$WORK_DIR/requirements.txt" >"$REQ_TMP"
  chmod 644 "$REQ_TMP"
  runuser -u "$APP_USER" -- "$APP_DIR/venv/bin/pip" install -q -r "$REQ_TMP"
  rm -f "$REQ_TMP"
else
  echo "  pas de requirements.txt : installation de flask et psycopg2-binary par défaut"
  runuser -u "$APP_USER" -- "$APP_DIR/venv/bin/pip" install -q flask psycopg2-binary
fi
runuser -u "$APP_USER" -- "$APP_DIR/venv/bin/pip" install -q gunicorn

# Tables : appliquées une seule fois, seulement si le dépôt fournit schema.sql et que "clients" n'existe pas.
if [[ -f "$WORK_DIR/schema.sql" ]]; then
  HAS_TABLE=$(PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT to_regclass('public.clients') IS NOT NULL")
  if [[ "$HAS_TABLE" == "f" ]]; then
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$WORK_DIR/schema.sql" >/dev/null
    echo "  schema.sql appliqué"
  else
    echo "  tables déjà présentes, schema.sql non rejoué"
  fi
fi

echo "[7/7] Service systemd \"banque\" (port $PORT)"
PRESTART=""
if [[ -n "$APP_INIT" ]]; then
  # Script d'initialisation lancé avant chaque démarrage (écrit avec un quotage sûr)
  printf '#!/bin/bash\ncd %q\nexec %q -c %q\n' "$WORK_DIR" "$APP_DIR/venv/bin/python" "$APP_INIT" >"$APP_DIR/init-appli.sh"
  chmod 755 "$APP_DIR/init-appli.sh"
  chown "$APP_USER":"$APP_USER" "$APP_DIR/init-appli.sh"
  PRESTART="ExecStartPre=$APP_DIR/init-appli.sh"
fi
cat >/etc/systemd/system/banque.service <<EOF
[Unit]
Description=Appli bancaire (Flask + gunicorn)
After=network.target postgresql.service

[Service]
User=$APP_USER
WorkingDirectory=$WORK_DIR
EnvironmentFile=$ENV_FILE
$PRESTART
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:$PORT $APP_MODULE
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable banque >/dev/null
systemctl restart banque
sleep 4

IP=$(hostname -I | awk '{print $1}')
if systemctl is-active --quiet banque; then
  echo
  echo "Appli lancée : http://$IP:$PORT"
  curl -s -o /dev/null -w "Réponse HTTP locale : %{http_code}\n" "http://localhost:$PORT/" || true
else
  echo "Le service ne démarre pas. Voir : journalctl -u banque -n 50 --no-pager" >&2
  exit 1
fi
