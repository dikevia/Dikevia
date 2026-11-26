# Dikévia Android — éditions standard et administration

Les deux applications Android sont des enveloppes natives distinctes de l'application web Dikévia. Elles partagent le frontend et l'API, mais conservent des parcours d'interface distincts : l'application standard porte l'assistant juridique ; l'application Administration est réservée au pilotage et ne contient pas le chatbot utilisateur.

## Éditions bêta

- **Dikévia standard** — package bêta `fr.dikevia.commercial.beta`. Ouvre l'espace de travail des agents, avec l'assistant juridique et les fonctions de leur organisation.
- **Dikévia Administration** — package bêta `fr.dikevia.admin.beta`. Ouvre l'administration générale. L'accès aux fonctions d'administration reste contrôlé côté API par les droits plateforme.

Les APK bêta construites par le workflow pointent vers le staging Render `https://dikevia-vector-beta-staging.onrender.com`. Le staging est préparé pour Auth0 avec le tenant de développement documenté dans [la procédure Auth0](../docs/47_AUTH0_MIGRATION.md). **Le parcours complet de connexion Auth0 dans la WebView Android n'est pas encore validé sur appareil réel.** Ne pas présenter ces APK comme une version de production.

La production n'a pas été migrée par ce chantier : son fournisseur d'identité et ses services restent hors périmètre. Aucun mot de passe, secret client ou jeton d'accès n'est embarqué dans les APK.

## Construction et livraison de test

Le workflow GitHub Actions **Dikévia — APK standard et administration** construit les deux variantes debug et publie deux artefacts distincts :

- `dikevia-standard-beta-apk`
- `dikevia-administration-beta-apk`

Les APK bêta sont signées avec la clé debug Android du pipeline et leur téléchargement est temporaire (14 jours). Elles sont destinées aux tests contrôlés, pas à une diffusion publique ni au Play Store.

## Recette obligatoire avant livraison publique

- Valider les connexions Auth0 et les retours OIDC sur appareils Android réels, pour les deux éditions.
- Vérifier les liens profonds, le retour après authentification et la conservation du mode standard/administration.
- Vérifier que l'application Administration n'expose aucun écran de conversation.
- Vérifier les rôles et les autorisations côté API, sans se fier au seul masquage de l'interface.
- Préparer une clé de signature dédiée et conservée hors du dépôt, une stratégie de mise à jour/versionnement et une publication séparée.

Ne jamais ajouter de secret de signature, de mot de passe ou de jeton au dépôt ou aux artefacts.
