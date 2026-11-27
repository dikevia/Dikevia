# V3.9 — Intégrité des invitations et sécurité du provisionnement

## Corrections

- Une seule invitation `PENDING` est autorisée par adresse et organisation. L'index unique partiel est insensible à la casse et conserve l'historique des invitations révoquées.
- La création concurrente d'invitations identiques renvoie HTTP 409 sans créer de doublon.
- Les acceptations simultanées pour un même couple organisation/utilisateur sont sérialisées par verrou transactionnel PostgreSQL, y compris lorsqu'aucune adhésion n'existe encore.
- L'acceptation d'une invitation ne peut plus remplacer le rôle d'une adhésion déjà active. Le rôle existant ne peut être modifié que par le parcours d'administration dédié, audité et protégé contre le retrait du dernier administrateur.
- En production, l'URL du client Keycloak Admin doit être HTTPS et limitée à une origine (pas de chemin, query ou fragment), afin de réduire les risques de mauvaise configuration et de fuite de secrets.
- La migration 006 révoque les doublons pendants historiques en conservant l'invitation la plus récente, puis crée l'index d'unicité.

## Migration

Exécuter les migrations dans l'ordre jusqu'à `006_invitation_integrity.sql`, puis réappliquer `database/grant_runtime_permissions.sql` si le processus de déploiement le prévoit. Aucun nouveau droit SQL n'est requis.

## Recette obligatoire

1. Créer deux invitations concurrentes pour la même adresse et organisation : une seule doit être créée.
2. Créer des invitations pour la même adresse dans deux organisations différentes : les deux doivent être autorisées.
3. Accepter une invitation alors qu'une adhésion active existe déjà : HTTP 409, rôle inchangé.
4. Vérifier que les invitations révoquées/acceptées n'empêchent pas une nouvelle invitation.
5. En production, refuser une URL Keycloak Admin en HTTP ou contenant un chemin.
6. Exécuter la migration sur une copie de base avec doublons historiques et vérifier qu'ils sont révoqués sans suppression de l'historique.

Les tests contractuels ne remplacent pas les tests PostgreSQL réels ni la recette Keycloak/SMTP.
