# V3.33 — preuve de validation CI du kit développeur

Date de validation : 17 novembre 2026

## Révision contrôlée

- Dépôt : `dikevia/Dikevia`
- Branche : `cfdt-juris-v3-30-developer-ready`
- Commit contrôlé : `1bcf515a6256b81da93dccc326d2681d8e99e893`
- Pull request : [#1](https://github.com/dikevia/Dikevia/pull/1), vers `main`, laissée ouverte et non fusionnée.
- Exécution GitHub Actions : [run 44056185761](https://github.com/dikevia/Dikevia/actions/runs/44054893375)

## Résultats observés

L'exécution complète du workflow `test-and-audit` s'est terminée avec succès.

- **189 tests réussis**, aucun échec.
- Ruff : réussi.
- Bandit : réussi.
- `pip-audit` : réussi.
- Compilation Python et audit du modèle d'environnement : réussis.
- Migrations SQL 001 à 018, création des rôles dédiés et tests d'intégration sur PostgreSQL 16 éphémère : réussis.
- Vérification syntaxique des scripts shell : réussie.
- Validation des configurations Docker Compose et construction des images : réussies.
- Construction et téléversement du kit développeur : réussis.

Un avertissement non bloquant subsiste : Starlette signale que l'utilisation de `httpx` avec `TestClient` est dépréciée et recommande `httpx2`.

## Évolutions validées

- Migration 017 : limitation atomique des requêtes chat à 10/minute par utilisateur et organisation par défaut, configurable de 1 à 120, avec HTTP 429 et `Retry-After`.
- Migration 018 : journal de consommation IA par organisation et utilisateur. Les tokens réellement renvoyés par le fournisseur sont enregistrés lorsqu'ils sont disponibles ; les valeurs inconnues restent NULL.
- Le journal ne contient aucun prompt, réponse, message, extrait documentaire ou identifiant de conversation. Le rôle runtime ne peut qu'insérer les colonnes de métadonnées autorisées ; aucune lecture n'est accordée.
- Les appels IA réussis, les réponses rejetées pour référence non sourcée et les erreurs fournisseur sont distingués.
- Les métadonnées de comptabilisation sont exclues de la sérialisation API et ne sont pas exposées au navigateur.
- Le parcours de revue de cohérence des règles locales extrait désormais correctement le texte de `AIAnalysisResult` avant le contrôle des références ; ses appels IA sont également comptabilisés, y compris les réponses rejetées et les erreurs fournisseur.
- La version API est 3.33.0.
- Le quota PostgreSQL est partagé entre le chat et la revue de cohérence des règles locales. Le refus 429 intervient avant la lecture du document et la recherche du corpus national ; l'alternance des deux routes ne permet plus de contourner la limite.
- Aucun coût en euros ni quota mensuel n'est calculé ou appliqué à ce stade : il faudra d'abord définir les tarifs fournisseurs et les budgets par offre.

## Artefact généré

- Nom : `CFDT-JURIS-V3.30-Kit-Developpeur`
- Identifiant : `14316236830`
- Taille : 4 663 369 octets
- SHA-256 : `2d0784cabae4953aee4891410b2998f2edaae83f082fb3b10e35d1083261b61e`
- Conservation GitHub jusqu'au 17 décembre 2026.

L'archive contient le code, les migrations, les tests et la documentation révisés. Le fichier `SHA256SUMS_KIT.txt` permet de contrôler les fichiers contenus.

## Portée et limites

Cette validation prouve que les contrôles automatisés et les tests sur la base PostgreSQL jetable passent sur la révision indiquée. Elle ne prouve pas :
- la connexion à un fournisseur OIDC réel ;
- la disponibilité d'identifiants PISTE/Légifrance ou d'un fournisseur IA réel ;
- la recette sur l'instance Neon du propriétaire ;
- la restauration effective d'une sauvegarde de l'instance cible ;
- un audit d'intrusion indépendant ou une certification juridique.

Aucune migration n'a été appliquée à la base Neon du propriétaire et aucun déploiement de production n'a été effectué.


# V3.34 — preuve de validation CI des connecteurs PISTE

Date de validation : 17 novembre 2026

- Commit contrôlé : `4506bfb7a330fafa32060e1e6c4008b6a76498c2`.
- GitHub Actions : [run 44060023429](https://github.com/dikevia/Dikevia/actions/runs/44060023429) — succès.
- **192 tests réussis, aucun échec**, un avertissement non bloquant lié à l'utilisation de `httpx` avec `TestClient` dans Starlette.
- Ruff, Bandit, `pip-audit`, compilation, audit des variables, migrations 001 à 018, tests PostgreSQL 16/RLS, scripts shell, configurations Docker Compose, construction et téléversement du kit : réussis.
- Les tests V3.34 vérifient que les routes de contrôle PISTE, recherche Légifrance, recherche CETAT et consultation CETAT passent par le quota partagé avant tout appel externe ; les entrées invalides ne consomment pas le quota ; le refus renvoie HTTP 429 avec `Retry-After`.
- Aucun changement de schéma SQL ou migration supplémentaire n'est requis.
- Cette preuve ne remplace pas la recette avec les identifiants PISTE réels, ni la validation des quotas contractuels du fournisseur.


## V3.35 — Bornage des imports PISTE et validation du kit

Date de validation : 17 novembre 2026

- Commit contrôlé : `372a0ea4ea9a7a5123c74935bb8aea714ed23317`.
- GitHub Actions : [run 44061778862](https://github.com/dikevia/Dikevia/actions/runs/44061778862) — terminé avec succès.
- Le job `test-and-audit` et chacune de ses étapes ont réussi : compilation et audit de l'environnement, Ruff, Bandit, `pip-audit`, PostgreSQL 16 jetable avec rôles à privilèges minimaux, tests unitaires/contrat/RLS (**193 tests réussis, aucun échec**), scripts shell, configurations Docker Compose, construction et téléversement du kit.
- Un avertissement de dépréciation Starlette/httpx subsiste dans les tests ; il n'a pas fait échouer la CI. Des avertissements de dépréciation Node.js 20 concernent les actions GitHub utilisées par le workflow.
- Les validations V3.35 vérifient que les routes d'ingestion PISTE réglementaire et CETAT rejettent les recherches hors limites (2 à 500 caractères) et les nombres de résultats hors limites (1 à 20) avant tout effet de bord. Pour CETAT, la borne limite également les consultations de textes intégraux.
- Version API : 3.35.0. Aucun changement de schéma SQL ni migration supplémentaire.
- Artefact : `CFDT-JURIS-V3.30-Kit-Developpeur`, identifiant `14319075913`, taille 4 666 924 octets, SHA-256 `1433779885341600771c952ba7e2b3428aa19aac92e28a0cd64d4632fb32715e`.
- Conservation annoncée par GitHub jusqu'au 17 décembre 2026.

Cette preuve concerne uniquement le commit indiqué et l'environnement PostgreSQL éphémère de la CI. Elle ne vaut pas recette sur Neon, validation des identifiants réels PISTE/OIDC/IA, test de restauration sur l'instance cible, audit indépendant ni autorisation de mise en production. Aucune migration Neon et aucun déploiement de production n'ont été effectués ; la branche `main` reste inchangée et la PR #1 demeure ouverte, non fusionnée.


## Vérification complémentaire — isolation des conversations et dossiers

Date de validation : 17 novembre 2026

- Commit contrôlé : `366adc0e7d185077ea3c7e8082912b0b9189d5cc`.
- GitHub Actions : [run 44065407804](https://github.com/dikevia/Dikevia/actions/runs/44065407804) — terminé avec succès.
- **193 tests réussis, aucun échec** ; un avertissement non bloquant Starlette/httpx.
- Les tests d'intégration exécutés sur PostgreSQL 16 vérifient désormais qu'un autre utilisateur de la même organisation ne peut pas lire les conversations, messages ou dossiers d'un propriétaire différent ; les tentatives de modification et de suppression de ses conversations/messages n'affectent aucune ligne ; le propriétaire peut supprimer sa conversation et les messages ainsi que le dossier associé sont supprimés en cascade.
- Toutes les étapes du job CI ont réussi : compilation, audit de configuration, Ruff, Bandit, `pip-audit`, migrations 001–018 sur PostgreSQL jetable, tests unitaires/contrat/RLS, scripts shell, Docker Compose et construction/téléversement du kit.
- Artefact reconstruit : `CFDT-JURIS-V3.30-Kit-Developpeur`, identifiant `14320835091`, taille 4 669 745 octets, SHA-256 `3a013e6046af725c3a12b0363bdbc19ac3a80f4295250ee19f229333333dfe8c`.
- Conservation GitHub annoncée jusqu'au 17 décembre 2026.

Cette validation porte sur les tests automatisés de l'environnement éphémère. Elle ne constitue pas une recette sur Neon ni une preuve de conformité RGPD ou de sécurité exhaustive. La durée de conservation et la purge automatique des conversations restent notamment à définir et à mettre en œuvre avant la production. La PR #1 reste ouverte et non fusionnée ; `main`, Neon et la production n'ont pas été modifiés.


## V3.36 — contrats API de propriété des conversations et dossiers

Date de validation : 17 novembre 2026

- Commit contrôlé : `c19b109d7ce76c64113dd5fb2e4bce57181dc05a`.
- GitHub Actions : [run 44066187124](https://github.com/dikevia/Dikevia/actions/runs/44066187124) — terminé avec succès.
- **199 tests réussis, aucun échec**.
- Les tests V3.36 couvrent les contrats des gestionnaires de routes : une conversation étrangère ou invisible n'est pas listée/lue ; sa suppression renvoie 404 ; la création, la lecture et la modification d'un dossier associé à une conversation invisible sont refusées ; les routes attendues sont présentes et rattachées au contexte d'organisation authentifié.
- Ces tests de gestionnaires utilisent une connexion simulant le masquage des lignes par RLS. Les tests PostgreSQL réels de la suite séparée couvrent les politiques RLS elles-mêmes. Cette distinction est importante : les nouveaux tests V3.36 ne sont pas une recette HTTP complète avec un fournisseur OIDC réel.
- Toutes les étapes CI ont réussi : compilation, audit de configuration, Ruff, Bandit, `pip-audit`, migrations 001–018 sur PostgreSQL 16 jetable avec rôles à privilèges minimaux, tests unitaires/contrat/RLS, scripts shell, Docker Compose, construction et téléversement du kit.
- Artefact : `CFDT-JURIS-V3.30-Kit-Developpeur`, identifiant `14319513979`, taille 4 671 597 octets, SHA-256 `406878453791efc89f3dfe9c42e5161b6cf82f267ab6e08ff2514293e4397b59`.
- Conservation GitHub annoncée jusqu'au 17 décembre 2026.

La réussite de cette CI ne clôt pas les points bloquants de préproduction : politique et purge de conservation, validation RGPD/DPO, recette réelle OIDC/PISTE/fournisseur IA, base Neon de préproduction distincte, sauvegarde/restauration et audit indépendant. Aucune migration n'a été appliquée à Neon, aucun déploiement de production n'a été effectué et la branche `main` reste inchangée. La PR #1 demeure ouverte et non fusionnée.


## V3.37 — préparation sécurisée de la purge des conversations privées

Date de validation : 17 novembre 2026

- Commit contrôlé : `172a7fd3c0dad3d1a6956e1cb273f75a4e362007`.
- GitHub Actions : [run 44067647029](https://github.com/dikevia/Dikevia/actions/runs/44067647029) — terminé avec succès.
- **205 tests réussis, aucun échec** ; un avertissement non bloquant dans la suite de tests.
- Toutes les étapes du job `test-and-audit` ont réussi : compilation et audit de configuration, Ruff, Bandit, `pip-audit`, migrations 001–018 sur PostgreSQL 16 jetable avec rôles à privilèges minimaux, tests unitaires/contrat/RLS, scripts shell, configurations Docker Compose, construction et téléversement du kit.
- Le nouvel outil `scripts/purge_private_conversations.py` exige une date limite explicite avec fuseau horaire. Il fonctionne en simulation par défaut ; l'exécution réelle exige les deux options `--execute` et `--confirm-delete`, ainsi qu'une connexion dont le rôle dispose de privilèges élevés (`rolsuper` ou `rolbypassrls`). Les suppressions des conversations entraînent les suppressions en cascade prévues par le schéma pour les messages et dossiers liés.
- Les tests vérifient notamment le refus d'un rôle runtime ordinaire, l'absence de suppression en simulation, le respect de la date limite et les suppressions en cascade sur PostgreSQL de test.
- **Aucune purge automatique n'est activée et aucune donnée réelle n'a été supprimée.** Aucun calendrier ni durée de conservation par défaut n'est défini.
- Le critère technique utilisé est `updated_at`. Il doit être validé par le responsable de traitement/DPO avant tout usage réel. Les exceptions, gels juridiques, fichiers téléversés, journaux, métriques et sauvegardes ne sont pas couverts par cet outil.
- Artefact : `CFDT-JURIS-V3.30-Kit-Developpeur`, identifiant `14321286322`, taille 4 677 655 octets, SHA-256 `b9aa8f09109a5f995d33557831b6b76a212703d6b806b30893d0b96bc8249838`.
- Conservation GitHub annoncée jusqu'au 17 décembre 2026.

Cette validation porte sur le commit indiqué et l'environnement PostgreSQL éphémère de la CI. Elle ne constitue pas une validation de la politique de conservation, une recette sur Neon, ni une autorisation d'exécuter la purge en production. Aucune migration Neon, aucun déploiement de production et aucune modification de la branche `main` n'ont été effectués. La PR #1 reste ouverte et non fusionnée.
