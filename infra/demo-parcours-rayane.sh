#!/usr/bin/env bash
# Joue le scénario de démonstration de l'appli de la branche « rayane » (dossier app/) avec curl.
#
# Usage :
#   BASE=http://localhost:5000 CONSEILLER_MAIL=martin@banque.local CONSEILLER_MDP='...' ./demo-parcours-rayane.sh
#
# ATTENTION : le script crée deux clients (Alice et Bob) et des messages dans la base visée.
# Le lancer contre une instance de test (base jetable), pas contre la base de la vraie démo.
set -uo pipefail

BASE="${BASE:-http://localhost:5000}"
CONSEILLER_MAIL="${CONSEILLER_MAIL:-}"
CONSEILLER_MDP="${CONSEILLER_MDP:-}"
if [[ -z "$CONSEILLER_MAIL" || -z "$CONSEILLER_MDP" ]]; then
  echo "Définir CONSEILLER_MAIL et CONSEILLER_MDP (compte conseiller créé avec : flask creer-conseiller)." >&2
  exit 2
fi

SUF="$(date +%s)"
A_MAIL="alice.$SUF@demo.local"
B_MAIL="bob.$SUF@demo.local"
MDP="demo-$SUF-xyz"

CJ_A=$(mktemp); CJ_B=$(mktemp); CJ_C=$(mktemp)
trap 'rm -f "$CJ_A" "$CJ_B" "$CJ_C"' EXIT
OK=0; KO=0

get() { curl -s -L -b "$1" -c "$1" "$BASE$2"; }
# jeton CSRF de la session : lu dans le formulaire de la page $2
csrf() { get "$1" "$2" | grep -oE 'name="csrf" value="[^"]+"' | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'; }
# postf jar page_du_formulaire chemin_du_post données... : récupère le jeton puis envoie
postf() {
  local jar=$1 page=$2 path=$3; shift 3
  local tok; tok=$(csrf "$jar" "$page")
  curl -s -L -b "$jar" -c "$jar" "$BASE$path" --data-urlencode "csrf=$tok" "$@"
}

check() {
  if grep -qiE -- "$3" <<<"$2"; then echo "  [OK] $1"; OK=$((OK + 1)); else echo "  [KO] $1  (attendu : $3)"; KO=$((KO + 1)); fi
}
absent() {
  if grep -qiE -- "$3" <<<"$2"; then echo "  [KO] $1  (présent : $3)"; KO=$((KO + 1)); else echo "  [OK] $1"; OK=$((OK + 1)); fi
}
numero() { grep -oE 'FR76( [0-9]{4}){5} [0-9]{3}' <<<"$1" | head -1 | tr -d ' '; }

echo "Démo (appli de Rayane) contre $BASE"

echo "Étape 0 : l'appli répond"
check "page d'accueil" "$(get "$CJ_A" /)" "<html|<!DOCTYPE"

echo "Étape 1 : ouverture du compte A (Alice Martin)"
R=$(postf "$CJ_A" /inscription /inscription --data-urlencode "prenom=Alice" --data-urlencode "nom=Martin" \
      --data-urlencode "email=$A_MAIL" --data-urlencode "mot_de_passe=$MDP" --data-urlencode "confirmation=$MDP")
check "compte ouvert (message de bienvenue)" "$R" "Bienvenue"
check "solde de départ de 1 000,00 €" "$R" "1 000,00"
NUM_A=$(numero "$R")
[[ -n "$NUM_A" ]] && { echo "  [OK] numéro de compte lu ($NUM_A)"; OK=$((OK + 1)); } || { echo "  [KO] numéro de compte introuvable"; KO=$((KO + 1)); }

echo "Étape 2 : déconnexion puis connexion de A"
get "$CJ_A" /deconnexion >/dev/null
R=$(postf "$CJ_A" /connexion /connexion --data-urlencode "email=$A_MAIL" --data-urlencode "mot_de_passe=mauvais-mdp")
check "mauvais mot de passe refusé" "$R" "incorrect"
R=$(postf "$CJ_A" /connexion /connexion --data-urlencode "email=$A_MAIL" --data-urlencode "mot_de_passe=$MDP")
check "connexion réussie : page du compte" "$R" "Faire un virement"

echo "Étape 3 : ouverture et connexion du compte B (Bob Durand)"
R=$(postf "$CJ_B" /inscription /inscription --data-urlencode "prenom=Bob" --data-urlencode "nom=Durand" \
      --data-urlencode "email=$B_MAIL" --data-urlencode "mot_de_passe=$MDP" --data-urlencode "confirmation=$MDP")
NUM_B=$(numero "$R")
[[ -n "$NUM_B" && "$NUM_B" != "$NUM_A" ]] && { echo "  [OK] B a un autre numéro de compte"; OK=$((OK + 1)); } || { echo "  [KO] numéro de B vide ou identique à A"; KO=$((KO + 1)); }
check "solde de départ de B de 1 000,00 €" "$R" "1 000,00"

echo "Étape 4 : virements refusés (depuis A)"
R=$(postf "$CJ_A" /virement /virement --data-urlencode "numero_dest=$NUM_B" --data-urlencode "montant=5000")
check "5 000 € refusé : solde insuffisant" "$R" "Solde insuffisant"
R=$(postf "$CJ_A" /virement /virement --data-urlencode "numero_dest=FR7600000000000000000000000" --data-urlencode "montant=10")
check "compte destinataire inexistant refusé" "$R" "introuvable"
R=$(postf "$CJ_A" /virement /virement --data-urlencode "numero_dest=$NUM_A" --data-urlencode "montant=10")
check "virement vers soi-même refusé" "$R" "même compte"
R=$(postf "$CJ_A" /virement /virement --data-urlencode "numero_dest=$NUM_B" --data-urlencode "montant=-5")
check "montant négatif refusé" "$R" "positif|invalide"
R=$(get "$CJ_A" /compte)
check "solde de A toujours à 1 000,00 €" "$R" "1 000,00"

echo "Étape 5 : virement valide de 30 € (A vers B)"
R=$(postf "$CJ_A" /virement /virement --data-urlencode "numero_dest=$NUM_B" --data-urlencode "montant=30" --data-urlencode "libelle=Démo")
check "confirmation du virement" "$R" "Virement effectué"
R=$(get "$CJ_A" /compte)
check "solde de A à 970,00 €" "$R" "970,00"
check "ligne -30,00 € dans l'historique de A" "$R" "-30,00"

echo "Étape 6 : côté B"
R=$(get "$CJ_B" /compte)
check "solde de B à 1 030,00 €" "$R" "1 030,00"
check "ligne +30,00 € dans l'historique de B" "$R" "\+30,00"

echo "Étape 7 : message de A à son conseiller"
R=$(postf "$CJ_A" /conseiller-contact /conseiller-contact --data-urlencode "contenu=Bonjour, pouvez-vous confirmer mon virement ?")
check "message envoyé" "$R" "pouvez-vous confirmer mon virement"

echo "Étape 8 : réponse du conseiller"
R=$(postf "$CJ_C" /conseiller/connexion /conseiller/connexion --data-urlencode "email=$CONSEILLER_MAIL" --data-urlencode "mot_de_passe=$CONSEILLER_MDP")
check "connexion du conseiller (liste des clients)" "$R" "Alice Martin"
check "Alice a un message non lu (pastille)" "$R" "pastille"
FIL=""
for f in $(grep -oE '/conseiller/client/[0-9]+' <<<"$R" | sort -u); do
  if grep -q "Alice" <<<"$(get "$CJ_C" "$f")"; then FIL=$f; fi
done
[[ -n "$FIL" ]] && { echo "  [OK] conversation d'Alice trouvée ($FIL)"; OK=$((OK + 1)); } || { echo "  [KO] conversation d'Alice introuvable"; KO=$((KO + 1)); }
R=$(get "$CJ_C" "$FIL")
check "le conseiller lit le message d'Alice" "$R" "pouvez-vous confirmer mon virement"
R=$(postf "$CJ_C" "$FIL" "$FIL" --data-urlencode "contenu=Votre virement est bien passé")
check "réponse envoyée" "$R" "Votre virement est bien pass"

echo "Étape 9 : côté client"
R=$(get "$CJ_A" /compte)
check "A voit « 1 nouveau message »" "$R" "1 nouveau message"
R=$(get "$CJ_A" /conseiller-contact)
check "A lit la réponse du conseiller" "$R" "Votre virement est bien pass"
R=$(get "$CJ_A" /compte)
absent "le compteur de messages non lus est retombé" "$R" "nouveau message"

echo "Étape 10 : déconnexion de A"
get "$CJ_A" /deconnexion >/dev/null
R=$(get "$CJ_A" /compte)
check "accès à /compte renvoyé vers la connexion" "$R" 'name="mot_de_passe"'

echo
echo "Résultat : $OK contrôles OK, $KO KO"
[[ $KO -eq 0 ]]
