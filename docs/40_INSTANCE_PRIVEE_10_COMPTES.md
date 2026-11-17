# Instance privée CFDT JURIS — V3.30

## Règles fonctionnelles
- `PRIVATE_INSTANCE_MODE=true` active le mode privé.
- Une seule organisation syndicale est autorisée sur cette instance. Dix adhésions `ACTIVE` maximum au total, compte administrateur membre inclus ; les invitations non acceptées ne consomment pas de place.
- L'acceptation technique d'une invitation crée une adhésion `INVITED` : elle ne donne aucun accès applicatif.
- Seul un compte présent dans `platform_admins` peut consulter les comptes en attente et modifier leur statut.
- L'administrateur approuve avec `ACTIVE`, suspend avec `SUSPENDED`, ou refuse/révoque avec `REVOKED`.
- Une suspension libère une place ; les données et l'identité globale ne sont pas supprimées.
- Les comptes invités ne peuvent pas devenir `ORG_ADMIN`. Les rôles `LEGAL_EDITOR` et `MEMBER` restent disponibles.
- Les routes de paiement, portail, catalogue public et webhook Stripe sont désactivées.
- `PRIVATE_INSTANCE_MAX_USERS` est volontairement verrouillé à 10.

## API d'administration privée
Toutes les routes requièrent un jeton OIDC valide et l'appartenance à `platform_admins`.
- `GET /api/v1/platform/private-members` : comptes en attente (`INVITED`), actifs (`ACTIVE`) et suspendus (`SUSPENDED`) afin que l'administrateur puisse aussi suspendre un compte actif.
- `PATCH /api/v1/platform/private-members/{organization_id}/{user_id}` avec `{"status":"ACTIVE"}` : approuver/réactiver.
- Le même endpoint avec `{"status":"SUSPENDED"}` : suspendre en conservant les données.
- Le même endpoint avec `{"status":"REVOKED"}` : refuser/révoquer.

La limite globale est contrôlée par une fonction SQL transactionnelle qui prend un verrou consultatif global avant de compter les adhésions actives ; deux validations concurrentes ne peuvent donc pas dépasser dix.

## Déploiement
1. Vérifier que la base cible contient au plus une organisation. La migration 015 s'arrête si plusieurs organisations existent; ne pas supprimer ni fusionner des données sans décision explicite du propriétaire.
2. Faire une sauvegarde et vérifier qu'elle peut être restaurée.
3. Appliquer les migrations manquantes jusqu'à 015 avec le rôle DBA prévu pour les migrations. La migration 015 doit être testée en staging avant production.
4. Vérifier que le compte du commanditaire est bien dans `platform_admins` via le processus d'amorçage sécurisé.
5. Amorcer le compte commanditaire dans `platform_admins` avec `database/bootstrap_platform_admin.sql`, en utilisant l'issuer et le subject OIDC vérifiés du compte réel.
6. Déployer le code avec `PRIVATE_INSTANCE_MODE=true` et `PRIVATE_INSTANCE_MAX_USERS=10`; ne pas définir `STRIPE_SECRET_KEY` ni `STRIPE_WEBHOOK_SECRET`.
7. Sur une base de recette, tester invitation, acceptation, approbation, refus, suspension, réactivation, deux approbations concurrentes et tentative d'activation au-delà du dixième compte.
8. Vérifier les événements d'audit, la connexion d'un compte suspendu et le fonctionnement des routes de facturation désactivées avant toute ouverture en production.

La migration est accompagnée de `database/migrations/rollback/015_private_instance_10_seats.down.sql`. Le rollback restaure la contrainte de statuts historique et retire les fonctions privées ; il ne supprime aucune donnée métier.

## Limites de cette livraison
La configuration du serveur, l'identité OIDC du commanditaire, l'amorçage réel de `platform_admins`, l'application de la migration sur la base cible et les tests PostgreSQL réels nécessitent les accès et secrets de l'organisation. Le code ne doit pas être considéré comme déployé en production avant cette recette.
