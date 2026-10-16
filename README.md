# Banque Coopérative du Sillon — Exercice blue team sur SI simulé

> Projet sécurité — INSA Centre Val de Loire — 4ᵉ année STI
> Dépôt **privé** : il contient des éléments du dossier animateur.

## 1. Contexte métier

- **Organisation simulée** : Banque Coopérative du Sillon (nom fictif, à modifier librement)
- **Type** : petite banque de proximité, agence principale et une agence distante
- **Taille fictive** : environ 120 collaborateurs, quelques milliers de clients fictifs
- **Activité critique** : gestion des comptes clients (application « cœur bancaire » fictive), portail clients en ligne, virements et paiements simulés
- **Contraintes de continuité** : portail clients et application de gestion à rétablir en priorité, traçabilité des opérations à préserver

> Toutes les données sont fictives. Aucune donnée réelle, aucun équipement de production.

## 2. Équipe

| Membre | Rôle principal | Rôle de relecture |
|---|---|---|
| m1 | Range / infra (Ludus, OPNsense) | Supervision |
| M2 | Supervision / détection | Scénario |
| M3 | Scénario / OpenAEV, tests atomiques | Recherche |
| M4 | Recherche / animation / documentation | Range |

## 3. Choix techniques

| Sujet | Choix | Date | Justification |
|---|---|---|---|
| Thème | Petite banque fictive | 16/10/2026 | Scénarios riches (hameçonnage, fraude, rançongiciel) ; validation de l'enseignant à obtenir |
| Supervision | [Wazuh / ELK] | [à décider] | [..] |
| Plan VLAN / IP | voir `docs/01-si-simule/` | | |

Détail et historique des décisions : [`docs/decisions.md`](docs/decisions.md).

## 4. Architecture cible (rappel)

- **Sur l'hôte Proxmox** : Proxmox + Ludus
- **VM permanentes** (hors range) : OPNsense, Wazuh ou ELK, OpenAEV
- **VM du range** : routeur + environ 10 cibles reproduisant le SI choisi
- Administration via WireGuard (accès individuels), secours Proxmox indépendant d'OPNsense
- Capacité disque du nœud : 500 Go, services et exercices compris

## 5. Avancement (7 étapes)

| # | Étape | Livrable | Statut |
|---|---|---|---|
| 1 | Définir le SI simulé | Schéma, inventaire, usages métier, critères de disponibilité | ☐ |
| 2 | Construire et déployer le range | YAML Ludus, rôles, recréation testée | ☐ |
| 3 | Étudier des attaques réelles | 2 incidents, ≥ 3 sources primaires, fiches d'analyse | ☐ |
| 4 | Configurer OpenAEV | Scénario, injects, assets, attentes, dossier animateur | ☐ |
| 5 | Valider les stimuli | Recette atomique (exécution, traces, collecte, détection) | ☐ |
| 6 | Répétition du scénario complet | Chronologie de référence, écarts corrigés | ☐ |
| 7 | Organiser l'exercice blue team | Dossiers joueur / animateur, règles, débriefing | ☐ |

## 6. Organisation du dépôt

```
docs/
  01-si-simule/        schéma, inventaire, usages métier
  02-recherche/        fiches d'incidents, bibliographie
  03-scenario/         chronologie, injects, correspondances ATT&CK
  04-exercice/
    dossier-joueur/
    dossier-animateur/ ne jamais partager avec le groupe joueur
ludus/                 configuration du range, variables, versions
supervision/           configuration Wazuh ou ELK, règles, recherches
openaev/               exports du scénario, nettoyés des secrets
tests/                 recette atomique (ID, attendu, observé, preuve)
```

## 7. Règles de travail

- **Aucun secret dans git** (mots de passe, clés WireGuard, tokens, `.env`). Voir `.gitignore`.
- Une branche par tâche (`etape2/role-ad`, `etape4/injects-phishing`), fusion par pull request relue par un autre membre.
- Messages de commit clairs, en français ou en anglais, mais de façon cohérente.
- Toute décision structurante est notée dans `docs/decisions.md`.
- Sources : conserver URL, date de publication, date de consultation. Distinguer faits, hypothèses et simplifications de laboratoire.
- Exports OpenAEV nettoyés des secrets avant commit.

## 8. Références

- Architecture cible CyberINSA, 28/09/2026 (document de l'enseignant)
- Supports « Déroulé du projet » et « Architecture cible », 15/10/2026
- Bibliographie complète : `docs/02-recherche/`
