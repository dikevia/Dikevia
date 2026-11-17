# 03 — Modèle de données et cloisonnement (V3)

## Modèle
- `organizations` : espace syndical.
- `users` : registre d'identité OIDC minimal, global car une même identité peut appartenir à plusieurs organisations. Il ne contient aucune donnée documentaire ou métier.
- `memberships` : adhésion, rôle et statut par organisation.
- `platform_admins` : attribution plateforme distincte des rôles locaux ; accès SQL à restreindre strictement.
- `collectivities`, `documents`, `document_versions`, `document_relations`, `invitations`, `organization_settings`, `subscriptions`, `audit_events` : données privées propres à une organisation.

## Règles d'accès
Chaque table métier privée porte `organization_id NOT NULL` (la table `organizations` utilise son `id` comme identifiant de tenant). Le registre `users` est l'unique exception : identité OIDC minimale partagée, sans données métier. Les données nationales publiques devront rester dans un schéma global distinct.

La V3 vérifie le JWT OIDC, puis vérifie en base l'identité, l'adhésion ACTIVE et l'organisation ACTIVE. `X-Organization-ID` n'est jamais cru : il ne fait que sélectionner un espace, dont l'appartenance est revérifiée côté serveur.

Après validation, l'API définit `app.current_org_id` dans la transaction avec `set_config(..., true)`. Le paramètre est local à la transaction et disparaît au COMMIT/ROLLBACK.

## RLS
La migration `database/migrations/001_initial_multi_tenant.sql` active RLS et `FORCE ROW LEVEL SECURITY` sur toutes les tables privées. Les politiques utilisent `NULLIF(current_setting(...),'')::uuid` pour que l'absence de contexte ne donne aucun accès. Les opérations d'adhésion préalables à la sélection d'un tenant utilisent l'identité OIDC validée pour ne rendre visibles que les adhésions de l'utilisateur.

Le compte runtime PostgreSQL doit être distinct du compte de migration, ne pas être propriétaire des tables, et ne disposer ni de `BYPASSRLS` ni de `SUPERUSER`. Les droits SQL exacts doivent être finalisés avant déploiement.

## Conversations
Aucune table `messages`, `conversations` ou `chat_history`. Ne pas enregistrer les questions/réponses dans logs, traces, analytics, Redis ou stockage navigateur.

## Limites V3
Les migrations et les tests d'intégration doivent encore être exécutés sur PostgreSQL réel avec deux organisations. Les politiques RLS du dépôt ne remplacent pas une revue DBA ni des tests d'intrusion.
