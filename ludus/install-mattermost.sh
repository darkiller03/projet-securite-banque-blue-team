#!/usr/bin/env bash
# Installe Mattermost sur MM01 (Debian 12) pour la démo.
# Utilise l'image "preview" (Mattermost + base intégrée dans un seul conteneur) :
# parfaite pour une démo, à remplacer par l'installation Docker complète
# (github.com/mattermost/docker) pour le SI final.
#
# Usage (sur MM01) : sudo ./install-mattermost.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Lancer ce script en root : sudo $0" >&2
  exit 1
fi

echo "[1/3] Installation des dépendances et de Docker"
apt-get update -q
apt-get install -y -q ca-certificates curl jq
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

echo "[2/3] Lancement du conteneur Mattermost"
if docker ps -a --format '{{.Names}}' | grep -qx mattermost; then
  docker start mattermost >/dev/null
else
  docker run -d --name mattermost --restart unless-stopped \
    -p 8065:8065 mattermost/mattermost-preview
fi

echo "[3/3] Attente du démarrage (1 à 2 minutes au premier lancement)"
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8065/api/v4/system/ping >/dev/null 2>&1; then
    IP=$(hostname -I | awk '{print $1}')
    echo "Mattermost est prêt : http://${IP}:8065"
    echo "Étape suivante : ./setup-mattermost.sh pour créer l'équipe et les comptes."
    exit 0
  fi
  sleep 5
done

echo "Mattermost ne répond pas après 5 minutes. Voir : docker logs mattermost" >&2
exit 1
