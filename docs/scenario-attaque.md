# Scénario d'attaque : « Opération Guichet » (premier jet)

## Source d'inspiration

Le scénario s'inspire du mode opératoire des groupes **Carbanak (MITRE ATT&CK G0008)** et **FIN7 (G0046)**, documentés dans ATT&CK et disponibles dans OpenCTI. Carbanak ciblait spécifiquement des banques. Il obtenait un premier accès par des mails piégés envoyés à des employés, observait longtemps le réseau interne, puis prenait la main sur les systèmes métier pour déclencher des transferts frauduleux. C'est cohérent avec notre thème et ça produit des traces variées pour la blue team.

À faire avant la prochaine séance : parcourir les fiches de ces deux groupes dans OpenCTI (techniques, outils, rapports liés) et ajuster les étapes ci-dessous.

## Scénario principal A : du phishing au virement frauduleux

| Étape | Phase | Technique ATT&CK | Action dans notre SI | Machine | Traces attendues (blue team) |
|---|---|---|---|---|---|
| 1 | Reconnaissance | T1589 (infos sur les victimes) | Collecte des noms et adresses mail des conseillers sur le site WEB01 | WEB01 | Logs nginx : parcours systématique du site |
| 2 | Accès initial | T1566.001 (pièce jointe piégée) | Mail à un conseiller avec un document à macro | MAIL01 → PC-CONS01 | Logs Postfix ; Sysmon 1 : Word lance PowerShell |
| 3 | Exécution | T1059.001 (PowerShell) | Téléchargement et lancement d'un agent C2 (agent OpenAEV) | PC-CONS01 | Sysmon 1/3, événement 4104 (script block) |
| 4 | Persistance | T1053.005 (tâche planifiée) | Tâche planifiée qui relance l'agent | PC-CONS01 | Événement 4698, Sysmon 1 |
| 5 | Découverte | T1087.002, T1018 | `net user /domain`, `nltest`, scan des serveurs | PC-CONS01 → DC01 | 4688, requêtes LDAP, logs refusés d'OPNsense |
| 6 | Phishing interne | T1534 (spearphishing interne) | Depuis la session Mattermost du conseiller, message à l'admin : « procédure urgente », lien vers un faux portail de connexion | MM01 → ADM01 | Logs Mattermost, flux sortant vers un domaine inconnu |
| 7 | Accès aux identifiants | T1056.003 (capture via portail web) | L'admin saisit ses identifiants sur le faux portail | ADM01 | Logs du pare-feu (connexion sortante) |
| 8 | Mouvement latéral | T1021.001 / T1021.004 (RDP / SSH), T1078 | Connexion à FS01 puis CORE01 avec le compte admin volé | ADM01 → FS01, CORE01 | 4624 type 10 inhabituel, `auth.log` sur CORE01 |
| 9 | Collecte | T1005 | Export de la base clients PostgreSQL | CORE01 | Logs PostgreSQL : gros `SELECT` / `COPY` |
| 10 | Impact | T1565.001 (manipulation de données) | Insertion d'un virement frauduleux en base | CORE01 | Logs PostgreSQL : `INSERT` hors application |
| 11 | Exfiltration | T1041 (via le canal C2) | Envoi de l'export vers l'extérieur | CORE01 → Internet | Volume sortant anormal dans les logs du pare-feu |

## Scénario B (alternative ou complément) : par le portail web

Une vulnérabilité volontaire dans l'application de WEB01, par exemple une injection SQL (T1190), permet de déposer un webshell (T1505.003). Depuis la DMZ, l'attaquant rebondit sur CORE01 via le seul flux autorisé (tcp/8443). Ce scénario montre l'intérêt de la segmentation : l'attaquant est bloqué partout sauf sur ce flux, et il laisse beaucoup de traces de flux refusés.

## Mise en œuvre dans OpenAEV

Chaque étape devient un **inject** du scénario OpenAEV, exécuté par un agent sur la machine concernée. Pour chaque inject, on définit une **attente de détection** : quel log ou quelle alerte la blue team doit voir dans ELK. Cela permettra de mesurer objectivement ce que la blue team a détecté ou manqué.

## Questions à poser à l'enseignant

1. Macro Office ou simple lien : quel niveau de réalisme pour l'accès initial ?
2. Faut-il désactiver Defender sur les postes, ou le garder et contourner (plus réaliste, mais plus long) ?
3. Comment sera évaluée la blue team : temps de détection, nombre d'étapes détectées, qualité du rapport ?
