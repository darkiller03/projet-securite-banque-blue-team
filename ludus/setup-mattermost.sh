#!/usr/bin/env bash
# Crée l'équipe "banque" et les comptes de démo via l'API Mattermost.
# Le premier compte créé sur un serveur vierge devient administrateur système.
# Le script est rejouable : ce qui existe déjà est conservé.
#
# Usage (sur MM01) : ./setup-mattermost.sh
# Variables modifiables : MM_URL, ADMIN_PASS, USER_PASS
set -euo pipefail

MM_URL="${MM_URL:-http://localhost:8065}"
API="$MM_URL/api/v4"
TEAM="banque"
ADMIN_USER="admin.banque"
ADMIN_PASS="${ADMIN_PASS:-AdminBanque2026!}"
USER_PASS="${USER_PASS:-Conseil2026!}"
DEMO_USERS=(conseiller1 conseiller2)

for bin in curl jq; do
  command -v "$bin" >/dev/null || { echo "Installer $bin : sudo apt install -y $bin" >&2; exit 1; }
done

AUTH=()
api() { # api METHODE CHEMIN [données JSON]
  local args=(-fsS -X "$1" "${AUTH[@]}" -H 'Content-Type: application/json' "$API$2")
  [[ $# -ge 3 ]] && args+=(-d "$3")
  curl "${args[@]}"
}

create_user() { # create_user NOM MOT_DE_PASSE
  local body
  body=$(jq -n --arg u "$1" --arg p "$2" \
    '{username: $u, email: ($u + "@banque.local"), password: $p}')
  if api POST /users "$body" >/dev/null 2>&1; then
    echo "  compte créé : $1"
  else
    echo "  compte déjà existant : $1"
  fi
}

echo "[1/4] Compte administrateur"
create_user "$ADMIN_USER" "$ADMIN_PASS"

echo "[2/4] Connexion en administrateur"
TOKEN=$(curl -sS -i -X POST "$API/users/login" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg l "$ADMIN_USER" --arg p "$ADMIN_PASS" '{login_id: $l, password: $p}')" \
  | awk 'tolower($1) == "token:" {print $2}' | tr -d '\r')
[[ -n "$TOKEN" ]] || { echo "Connexion admin impossible (mot de passe ?)" >&2; exit 1; }
AUTH=(-H "Authorization: Bearer $TOKEN")

echo "[3/4] Équipe \"$TEAM\""
TEAM_ID=$(api GET "/teams/name/$TEAM" 2>/dev/null | jq -r '.id // empty') || true
if [[ -z "${TEAM_ID:-}" ]]; then
  TEAM_ID=$(api POST /teams \
    "$(jq -n --arg n "$TEAM" '{name: $n, display_name: "Banque de Proximité du Centre", type: "O"}')" \
    | jq -r '.id')
  echo "  équipe créée"
else
  echo "  équipe déjà existante"
fi

echo "[4/4] Comptes de démo"
for u in "${DEMO_USERS[@]}"; do
  create_user "$u" "$USER_PASS"
  user_id=$(api GET "/users/username/$u" | jq -r '.id')
  api POST "/teams/$TEAM_ID/members" \
    "$(jq -n --arg t "$TEAM_ID" --arg u "$user_id" '{team_id: $t, user_id: $u}')" >/dev/null 2>&1 || true
done

echo
echo "Terminé. Comptes : ${DEMO_USERS[*]} (mot de passe : $USER_PASS)"
echo "Admin : $ADMIN_USER (mot de passe : $ADMIN_PASS)"
