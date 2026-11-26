#!/usr/bin/env bash
# Joue le scénario de démonstration de banque-app (les 10 étapes du README) avec curl.
#
# Usage :   BASE=http://localhost:5000 ./demo-parcours.sh
#
# ATTENTION : le script crée deux clients (Alice et Bob) et un message dans la base visée.
# Le lancer contre une instance de test (base jetable), pas contre la base de la vraie démo.
set -uo pipefail

BASE="${BASE:-http://localhost:5000}"
SUF="$(date +%s)"
A_MAIL="alice.$SUF@demo.local"
B_MAIL="bob.$SUF@demo.local"
MDP="demo-$SUF"
CONSEILLER_MAIL="${CONSEILLER_MAIL:-conseiller@banque.local}"
CONSEILLER_MDP="${CONSEILLER_MDP:-conseiller}"

CJ_A=$(mktemp); CJ_B=$(mktemp); CJ_C=$(mktemp)
trap 'rm -f "$CJ_A" "$CJ_B" "$CJ_C"' EXIT
OK=0; KO=0

get()  { curl -s -L -b "$1" -c "$1" "$BASE$2"; }
post() { local jar=$1 path=$2; shift 2; curl -s -L -b "$jar" -c "$jar" "$BASE$path" "$@"; }

# check "libellé" "contenu de la page" "regex attendue"
check() {
  if grep -qiE -- "$3" <<<"$2"; then
    echo "  [OK] $1"; OK=$((OK + 1))
  else
    echo "  [KO] $1  (attendu : $3)"; KO=$((KO + 1))
  fi
}
# refuse "libellé" "contenu" "regex qui ne doit PAS apparaître"
absent() {
  if grep -qiE -- "$3" <<<"$2"; then
    echo "  [KO] $1  (présent : $3)"; KO=$((KO + 1))
  else
    echo "  [OK] $1"; OK=$((OK + 1))
  fi
}
numero() { grep -oE 'BPC[0-9A-F]{8}' <<<"$1" | head -1; }

echo "Démo contre $BASE"

echo "Étape 0 : l'appli répond"
check "page d'accueil" "$(get "$CJ_A" /)" "<html|<!DOCTYPE"

echo "Étape 1 : ouverture du compte A (Alice Martin)"
R=$(post "$CJ_A" /inscription --data-urlencode "nom=Alice Martin" --data-urlencode "email=$A_MAIL" --data-urlencode "mot_de_passe=$MDP")
check "compte créé" "$R" "Compte créé"

echo "Étape 2 : connexion de A"
R=$(post "$CJ_A" /connexion --data-urlencode "email=$A_MAIL" --data-urlencode "mot_de_passe=mauvais")
check "mauvais mot de passe refusé" "$R" "incorrect"
R=$(post "$CJ_A" /connexion --data-urlencode "email=$A_MAIL" --data-urlencode "mot_de_passe=$MDP")
NUM_A=$(numero "$R")
check "numéro de compte BPC affiché" "$R" "BPC[0-9A-F]{8}"
check "solde de départ de 100,00 €" "$R" "100\.00"

echo "Étape 3 : ouverture et connexion de B (Bob Durand)"
post "$CJ_B" /inscription --data-urlencode "nom=Bob Durand" --data-urlencode "email=$B_MAIL" --data-urlencode "mot_de_passe=$MDP" >/dev/null
R=$(post "$CJ_B" /connexion --data-urlencode "email=$B_MAIL" --data-urlencode "mot_de_passe=$MDP")
NUM_B=$(numero "$R")
check "B a un numéro différent de A" "$NUM_A/$NUM_B" "^BPC[0-9A-F]{8}/BPC[0-9A-F]{8}$"
[[ -n "$NUM_A" && "$NUM_A" != "$NUM_B" ]] && { echo "  [OK] numéros distincts ($NUM_A, $NUM_B)"; OK=$((OK + 1)); } || { echo "  [KO] numéros identiques ou vides"; KO=$((KO + 1)); }
check "solde de départ de B de 100,00 €" "$R" "100\.00"

echo "Étape 4 : virements refusés (depuis A)"
R=$(post "$CJ_A" /virement --data-urlencode "source=$NUM_A" --data-urlencode "dest=$NUM_B" --data-urlencode "montant=150")
check "150 € refusé : solde insuffisant" "$R" "Solde insuffisant"
R=$(post "$CJ_A" /virement --data-urlencode "source=$NUM_A" --data-urlencode "dest=BPC00000000" --data-urlencode "montant=10")
check "compte destinataire inexistant refusé" "$R" "destinataire n(.|&#39;|&#x27;)existe pas"
R=$(post "$CJ_A" /virement --data-urlencode "source=$NUM_A" --data-urlencode "dest=$NUM_A" --data-urlencode "montant=10")
check "virement vers soi-même refusé" "$R" "même compte"
R=$(get "$CJ_A" /mon-compte)
check "solde de A toujours à 100,00 €" "$R" "100\.00"

echo "Étape 5 : virement valide de 30 € (A vers B)"
R=$(post "$CJ_A" /virement --data-urlencode "source=$NUM_A" --data-urlencode "dest=$NUM_B" --data-urlencode "montant=30")
check "confirmation du virement" "$R" "Virement de 30\.00"
R=$(get "$CJ_A" /mon-compte)
check "solde de A à 70,00 €" "$R" "70\.00"
check "ligne -30,00 € dans l'historique de A" "$R" "-30\.00"

echo "Étape 6 : côté B"
R=$(get "$CJ_B" /mon-compte)
check "solde de B à 130,00 €" "$R" "130\.00"
check "ligne +30,00 € dans l'historique de B" "$R" "\+30\.00"

echo "Étape 7 : message de A à son conseiller"
post "$CJ_A" /messages --data-urlencode "contenu=Bonjour, pouvez-vous confirmer mon virement ?" >/dev/null
R=$(get "$CJ_A" /messages)
check "message visible côté A" "$R" "pouvez-vous confirmer mon virement"

echo "Étape 8 : réponse du conseiller"
post "$CJ_C" /connexion --data-urlencode "email=$CONSEILLER_MAIL" --data-urlencode "mot_de_passe=$CONSEILLER_MDP" >/dev/null
R=$(get "$CJ_C" /conseiller)
check "la liste conseiller contient Alice Martin" "$R" "Alice Martin"
absent "Bob Durand n'a pas écrit : absent de la liste" "$R" "Bob Durand"
FIL=$(grep -oE '/conseiller/[0-9]+' <<<"$R" | head -1)
for f in $(grep -oE '/conseiller/[0-9]+' <<<"$R"); do
  if grep -q "Alice Martin" <<<"$(get "$CJ_C" "$f")"; then FIL=$f; fi
done
R=$(get "$CJ_C" "$FIL")
check "le conseiller lit le message d'Alice" "$R" "pouvez-vous confirmer mon virement"
post "$CJ_C" "$FIL" --data-urlencode "contenu=Votre virement est bien passé" >/dev/null

echo "Étape 9 : conversation côté client"
R=$(get "$CJ_A" /messages)
check "message de A présent" "$R" "pouvez-vous confirmer mon virement"
check "réponse du conseiller présente" "$R" "Votre virement est bien pass"

echo "Étape 10 : déconnexion de A"
get "$CJ_A" /deconnexion >/dev/null
R=$(get "$CJ_A" /mon-compte)
check "accès à /mon-compte renvoyé vers la connexion" "$R" 'name="mot_de_passe"'

echo
echo "Résultat : $OK contrôles OK, $KO KO"
[[ $KO -eq 0 ]]
