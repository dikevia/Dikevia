# V3.32 — preuve de validation CI du kit développeur

Date de validation : 17 novembre 2026

## Révision contrôlée

- Dépôt : `dikevia/Dikevia`
- Branche : `cfdt-juris-v3-30-developer-ready`
- Commit contrôlé : `eb70ef692d3b00eb2fc4cae855fff29f2e778a80`
- Pull request : [#1](https://github.com/dikevia/Dikevia/pull/1), vers `main`, laissée ouverte et non fusionnée.
- Exécution GitHub Actions : [run 44053022900](https://github.com/dikevia/Dikevia/actions/runs/44053022900)

## Résultats observés

L'exécution complète du workflow `test-and-audit` s'est terminée avec succès.

- **185 tests réussis**, aucun échec.
- Ruff : réussi.
- Bandit : réussi.
- `pip-audit` : réussi.
- Compilation Python et audit du modèle d'environnement : réussis.
- Migrations SQL 001 à 018, création des rôles dédiés et tests d'intégration sur PostgreSQL 16 éphémère : réussis.
- Vérification syntaxique des scripts shell : réussie.
- Validation des configurations Docker Compose et construction des images : réussies.
- Construction et téléversement du kit développeur : réussis.

Un avertissement non bloquant subsiste : dépréciation Starlette liée à l'utilisation de `httpx` dans `TestClient`.

## Évolutions validées

- Migration 017 : limitation atomique des requêtes chat à 10/minute par utilisateur et organisation par défaut, configurable de 1 à 120, avec HTTP 429 et `Retry-After`.
- Migration 018 : journal de consommation IA par organisation et utilisateur. Les tokens réellement renvoyés par le fournisseur sont enregistrés lorsqu'ils sont disponibles ; les valeurs inconnues restent NULL.
- Le journal ne contient aucun prompt, réponse, message, extrait documentaire ou identifiant de conversation. Le rôle runtime ne peut qu'insérer les colonnes de métadonnées autorisées ; aucune lecture n'est accordée.
- Les appels IA réussis, les réponses rejetées pour référence non sourcée et les erreurs fournisseur sont distingués.
- Les métadonnées de comptabilisation sont exclues de la sérialisation API et ne sont pas exposées au navigateur.
- La version API est 3.32.0.
- Aucun coût en euros ni quota mensuel n'est calculé ou appliqué à ce stade : il faudra d'abord définir les tarifs fournisseurs et les budgets par offre.

## Artefact généré

- Nom : `CFDT-JURIS-V3.30-Kit-Developpeur`
- Identifiant : `14313509415`
- Taille : 4 661 212 octets
- SHA-256 : `0c17c4296db04c6ea8f44df521b71e50e2e58041774ad27317ce8f4211fd5f2a`
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
