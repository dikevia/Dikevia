# 13 — V3.1 Administration et invitations

## Autorités distinctes
- `platform_admins` est le seul registre des administrateurs plateforme.
- `memberships.role` ne contient que `ORG_ADMIN`, `LEGAL_EDITOR` et `MEMBER`.
- La création d'une organisation passe par `POST /api/v1/platform/organizations`, protégé par une lecture du registre `platform_admins`.
- Le rôle PostgreSQL runtime peut lire `platform_admins`, mais ne peut ni y insérer ni y modifier des lignes.
- Le premier administrateur plateforme est provisionné hors API par `database/bootstrap_platform_admin.sql`, exécuté par un rôle DBA/migration.

## Cycle d'invitation
1. Un `ORG_ADMIN` crée une invitation pour une adresse e-mail et un rôle local.
2. L'API génère un jeton aléatoire à usage unique, ne stocke que son SHA-256 et le retourne une seule fois.
3. Le jeton doit être transmis manuellement par un canal sûr ; aucun service e-mail n'est configuré dans cette version.
4. Le destinataire se connecte via OIDC avec un e-mail marqué `email_verified=true`.
5. `POST /api/v1/invitations/accept` compare l'adresse vérifiée, verrouille l'invitation, vérifie l'expiration et active l'adhésion dans la même transaction.
6. Le statut passe à `ACCEPTED`, empêchant la réutilisation. L'opération est journalisée.

Les réponses de création et d'acceptation portent `Cache-Control: no-store`. Le jeton brut ne doit jamais être écrit dans les journaux, traces ou outils d'analytique. Le lien n'est pas encore envoyé automatiquement.

## Routes V3.1
- `POST /api/v1/platform/organizations` : création plateforme et adhésion du créateur comme `ORG_ADMIN`.
- `POST /api/v1/organizations/me/invitations` : création d'une invitation locale.
- `POST /api/v1/invitations/accept` : acceptation authentifiée d'une invitation.
- `DELETE /api/v1/organizations/me/invitations/{id}` : révocation d'une invitation encore en attente.
- Les routes de membres restent limitées à l'organisation sélectionnée et à un rôle local autorisé.

## Déploiement SQL
Après la migration, exécuter `database/grant_runtime_permissions.sql` avec le compte DBA/migration. Provisionner ensuite le premier administrateur avec `database/bootstrap_platform_admin.sql`. Le rôle runtime ne doit jamais être propriétaire des tables ni disposer de `BYPASSRLS`.

## Limites
- La remise du jeton est manuelle ; aucun e-mail n'est envoyé.
- Le bootstrap initial plateforme est une opération DBA hors bande.
- Les tests PostgreSQL réels (RLS, concurrence, révocation et invitations) doivent être passés avant production.

La migration additive V3.1 est `database/migrations/002_v31_invitations.sql` ; elle remplace la politique RLS initiale des invitations sans réécrire la migration historique 001.

Les permissions runtime sont accordées au niveau des colonnes lorsque cela est possible : l'API ne peut pas réécrire les identifiants OIDC, les clés de tenant, ni modifier les événements d'audit. Les tables documentaires restent en lecture seule tant que les routes de dépôt/versionnement ne sont pas livrées.
