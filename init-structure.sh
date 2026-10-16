#!/usr/bin/env bash
# À lancer une fois à la racine du dépôt cloné : crée l'arborescence avec des .gitkeep
set -euo pipefail
for d in \
  docs/01-si-simule \
  docs/02-recherche \
  docs/03-scenario \
  docs/04-exercice/dossier-joueur \
  docs/04-exercice/dossier-animateur \
  ludus supervision openaev tests; do
  mkdir -p "$d"
  touch "$d/.gitkeep"
done
echo "Arborescence créée."
