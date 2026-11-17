# V3.32 — preuve de validation CI du kit développeur

Date de validation : 17 novembre 2026

## Révision contrôlée

- Dépôt : `dikevia/Dikevia`
- Branche : `cfdt-juris-v3-30-developer-ready`
- Commit contrôlé : `758c26cc6aa7f92a8ec6496176ef2c98bc357bbe`
- Pull request : [#1](https://github.com/dikevia/Dikevia/pull/1), vers `main`, laissée ouverte et non fusionnée.
- Exécution GitHub Actions : [run 44052463498](https://github.com/dikevia/Dikevia/actions/runs/44052463498)

## Résultats observés

L'exécution complète du workflow `test-and-audit` s'est terminée avec succès.

- **184 tests réussis**, aucun échec.
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
- Le journal ne contient aucun prompt, réponse, message, extrait documentaire ou identifiant de conversation. Le rôle runtime peut uniquement insérer les colonnes de métadonnées autorisées ; aucune lecture n'est accordée.
- Les appels IA réussis, les réponses rejetées pour référence non sourcée et les erreurs fournisseur sont distingués.
- La version API est 3.32.0.
- Aucun coût en euros ni quota mensuel n'est calculé ou appliqué à ce stade : il faudra d'abord définir les tarifs fournisseurs et les budgets par offre.

## Artefact généré

- Nom : `CFDT-JURIS-V3.30-Kit-Developpeur`
- Identifiant : `14315090842`
- Taille : 4 660 687 octets
- SHA-256 : `73d6f9fb31aee2ec7f5308298ba2a9377dacccdd8509a11f692d94f5d5bc068d`
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
