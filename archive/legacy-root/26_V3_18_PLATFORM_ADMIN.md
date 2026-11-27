# V3.18 — Console d'administration plateforme

## Objectif

Donner à l'administrateur plateforme un espace séparé de l'espace de travail des syndicats, y compris lorsqu'il ne possède aucune adhésion tenant.

## Fonctions livrées

- Annuaire transversal des organisations : état, formule, statut d'abonnement, membres actifs, invitations en attente et date de création.
- Création d'un espace syndical depuis la console.
- Attribution d'un accès gratuit avec motif obligatoire (route existante V3.17).
- Suspension et réactivation d'un espace syndical, avec journalisation d'audit.
- Console masquée aux utilisateurs ordinaires ; les routes sont protégées par `require_platform_admin`.

## Routes

- `GET /api/v1/platform/organizations`
- `POST /api/v1/platform/organizations`
- `POST /api/v1/platform/organizations/{organization_id}/grant-free`
- `PATCH /api/v1/platform/organizations/{organization_id}/status` avec `{"status":"ACTIVE"}` ou `{"status":"SUSPENDED"}`.

## Sécurité SQL

Les deux opérations transversales utilisent `platform_admin_list_organizations(uuid)` et `platform_admin_set_organization_status(uuid,uuid,text)`. Ce sont des fonctions `SECURITY DEFINER`, avec `search_path` fixé, `row_security=off`, vérification interne de l'identifiant dans `platform_admins`, révocation des droits `PUBLIC` et `EXECUTE` accordé au seul rôle runtime. La migration vérifie que son rôle courant est `SUPERUSER` ou `BYPASSRLS`.

Le rôle applicatif n'obtient aucun `SELECT` général supplémentaire sur les tables multi-tenant. Le statut `SUSPENDED` est déjà refusé par la dépendance `get_tenant_context`.

## Déploiement

- Nouvelle installation : les fonctions sont incluses dans `database/schema.sql`.
- Base V3.17 existante : sauvegarder puis appliquer `database/migrations/008_platform_admin_console.sql` avec le rôle DBA `cfdt_migration`.
- Redémarrer l'API et tester les opérations avec un compte administrateur plateforme et un compte ordinaire.

## Limites et recette

La livraison ajoute la console de gestion opérationnelle mais ne constitue pas une recette de production. Il faut encore tester la migration et les fonctions sur PostgreSQL réel, contrôler les privilèges effectifs, vérifier les journaux d'audit et exécuter les scénarios de suspension/réactivation sur un environnement de préproduction. La console ne gère pas encore l'envoi automatique d'une invitation au premier administrateur du syndicat nouvellement créé : celui-ci peut être invité depuis l'espace créé en utilisant le mécanisme d'invitation existant.
