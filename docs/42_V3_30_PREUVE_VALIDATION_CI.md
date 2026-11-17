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
