#!/usr/bin/env bash
# Démo à lancer sur les postes clients (PC-CONS01, PC-CONS02).
#
#   Publier : ./demo-post.sh conseiller1 "Bonjour depuis PC-CONS01"
#   Lire    : ./demo-post.sh conseiller2 --lire
#
# MM_URL doit pointer vers MM01, ex. : export MM_URL=http://10.X.20.10:8065
# (X = numéro du range Ludus, visible avec "ludus range status")
set -euo pipefail

: "${MM_URL:?Définir MM_URL, ex. export MM_URL=http://10.X.20.10:8065}"
API="$MM_URL/api/v4"
PASS="${USER_PASS:-Conseil2026!}"
TEAM="banque"
CHANNEL="town-square"   # canal "Town Square", présent dans toute équipe

[[ $# -eq 2 ]] || { echo "Usage : $0 <utilisateur> \"message\" | --lire" >&2; exit 1; }
USER_NAME=$1
ACTION=$2

command -v jq >/dev/null || { echo "Installer jq : sudo apt install -y jq" >&2; exit 1; }

TOKEN=$(curl -sS -i -X POST "$API/users/login" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg l "$USER_NAME" --arg p "$PASS" '{login_id: $l, password: $p}')" \
  | awk 'tolower($1) == "token:" {print $2}' | tr -d '\r')
[[ -n "$TOKEN" ]] || { echo "Connexion impossible pour $USER_NAME" >&2; exit 1; }

api() {
  local args=(-fsS -X "$1" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' "$API$2")
  [[ $# -ge 3 ]] && args+=(-d "$3")
  curl "${args[@]}"
}

CHANNEL_ID=$(api GET "/teams/name/$TEAM/channels/name/$CHANNEL" | jq -r '.id')

if [[ "$ACTION" == "--lire" ]]; then
  posts=$(api GET "/channels/$CHANNEL_ID/posts?per_page=10")
  ids=$(jq -c '[.posts[].user_id] | unique' <<<"$posts")
  users=$(api POST /users/ids "$ids")
  echo "Derniers messages de ~$CHANNEL (heure UTC) :"
  jq -rn --argjson p "$posts" --argjson u "$users" '
    ($u | map({(.id): .username}) | add) as $names
    | ($p.order | reverse)[] as $id
    | $p.posts[$id]
    | select(.type == "")
    | "[\(.create_at / 1000 | floor | strftime("%H:%M:%S"))] \($names[.user_id] // .user_id) : \(.message)"'
else
  api POST /posts "$(jq -n --arg c "$CHANNEL_ID" --arg m "$ACTION" '{channel_id: $c, message: $m}')" >/dev/null
  echo "Message publié par $USER_NAME sur ~$CHANNEL"
fi
