# Dikévia Android — éditions standard et administration

Les deux applications Android sont des enveloppes natives distinctes de l'application web Dikévia. Elles utilisent la même API commerciale, le même realm Auth0 et les mêmes comptes ; chaque connexion reste soumise aux droits contrôlés par le serveur.

## Éditions beta

- **Dikévia standard** — package beta `fr.dikevia.commercial.beta`. Ouvre l'espace de travail des agents, avec l'assistant juridique, les documents et les fonctions de leur organisation.
- **Dikévia Administration** — package beta `fr.dikevia.admin.beta`. Ouvre l'administration générale, sans interface de conversation. L'accès est refusé par l'API si le compte ne possède pas les droits d'administrateur plateforme.

Les deux éditions partagent l'authentification Auth0 (`Dikévia Auth0 OIDC`) et l'URI de retour OIDC déjà configurée. Le mode d'interface est mémorisé temporairement dans la session WebView pendant le retour d'authentification. Aucun mot de passe ni jeton n'est embarqué dans les APK.

## Construction et livraison de test

Le workflow GitHub Actions **Dikévia — APK standard et administration** construit les deux variantes debug et publie deux artefacts distincts :

- `dikevia-standard-beta-apk`
- `dikevia-administration-beta-apk`

Les APK beta sont signés avec la clé debug Android du pipeline et leur téléchargement est temporaire (14 jours). Ils sont destinés aux tests contrôlés, pas à une diffusion publique ni au Play Store.

## Avant une livraison publique

Une version de production nécessite une clé de signature dédiée et conservée hors du dépôt, une stratégie de mise à jour/versionnement, des tests sur appareils réels, la validation de l'accès administrateur par l'API, et une publication séparée. Ne jamais ajouter de secret de signature, de mot de passe ou de jeton au dépôt ou aux artefacts.
