# Cadrage du SI simulé — Banque Coopérative du Sillon

> Brouillon de départ (étape 1 du déroulé). À valider et ajuster par l'équipe et l'enseignant.
> Tout est fictif : aucune donnée réelle, aucun système bancaire réel (pas de SWIFT, HSM, DAB).

## 1. Organisation

- Petite banque de proximité, environ 120 collaborateurs
- 2 sites : agence principale (siège) et agence distante
- Clients et comptes fictifs, générés pour l'exercice

## 2. Services métier à simuler

| Service | Simulation | Criticité |
|---|---|---|
| Gestion des comptes (« cœur bancaire ») | Application web + base de données fictives | Haute |
| Portail clients en ligne | Site web fictif (consultation, virements simulés) | Haute |
| Annuaire et authentification | Active Directory | Haute |
| Partage de fichiers | Serveur de fichiers (dossiers clients, conformité) | Moyenne |
| Postes conseillers et back-office | Windows 11 | Moyenne |
| Administration | Poste d'administration | Haute |

## 3. Inventaire proposé (≈ 10 cibles, à adapter)

| # | Rôle | Modèle | Remarque |
|---|---|---|---|
| 1 | Contrôleur de domaine (AD / DNS) | Windows Server 2022 | |
| 2 | Serveur de fichiers | Windows Server 2022 | Peut être fusionné avec le DC si capacité limitée |
| 3 | Application « cœur bancaire » fictive | Debian 13 serveur | Web + base de données |
| 4 | Portail clients | Debian 13 serveur | Exposé via OPNsense |
| 5-8 | Postes conseillers / back-office (×4) | Windows 11 | |
| 9 | Poste d'administration | Windows 11 | Cible à fort enjeu |
| 10 | Poste Linux | Debian 13 XFCE | |
| + | Routeur du range | À déclarer explicitement | Géré par Ludus |

Services permanents (hors range) : OPNsense, supervision (Wazuh ou ELK), OpenAEV.
Kali XFCE sert pour les stimuli et tests d'attaque, hors du périmètre métier.

## 4. Critères de disponibilité

- Portail clients et cœur bancaire : à rétablir en priorité après incident
- Traçabilité : journaux d'authentification et d'accès aux comptes conservés
- Capacité : disque du nœud limité à 500 Go, à vérifier avec les 5 modèles (220 Gio de disques logiques)

## 5. À compléter

- [ ] Schéma du SI (zones, flux, dépendances)
- [ ] Plan VLAN / IP
- [ ] Rôles Ludus retenus
- [ ] Choix Wazuh ou ELK
