# 11 — Exploitation et privilèges SQL

## Séparation des rôles PostgreSQL
Le rôle qui exécute les migrations est différent du rôle utilisé par FastAPI. Exemple à adapter par l'administrateur DBA :

```sql
CREATE ROLE cfdt_juris_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE cfdt_juris TO cfdt_juris_app;
GRANT USAGE ON SCHEMA public TO cfdt_juris_app;
GRANT SELECT ON organizations, users, memberships, collectivities, documents,
  document_versions, document_relations, invitations, organization_settings,
  subscriptions, audit_events TO cfdt_juris_app;
REVOKE ALL ON platform_admins FROM PUBLIC;
REVOKE ALL ON platform_admins FROM cfdt_juris_app;
```

Le mot de passe du rôle runtime est défini via un canal secret, jamais dans ce fichier. Les droits d'écriture sont à ajouter table par table uniquement lorsque les routes correspondantes existent. Le rôle runtime ne doit jamais être propriétaire des tables ni recevoir `BYPASSRLS`.

## Provisionnement initial
Le provisionnement du premier administrateur CFDT doit être réalisé par une procédure contrôlée : créer l'identité OIDC dans `users`, créer l'organisation, puis créer une adhésion `ORG_ADMIN` avec statut `ACTIVE`. Ces opérations nécessitent un rôle d'administration distinct et une transaction qui définit le contexte tenant avant les INSERT soumis à RLS. Ne pas ouvrir un endpoint de provisionnement public avant d'avoir implémenté et testé le contrôle `PLATFORM_ADMIN`.

## Recette de sécurité non négociable
Créer deux organisations A et B, deux utilisateurs distincts, deux documents distincts. Avec le rôle runtime, vérifier que :
- A ne lit pas les documents de B ;
- A ne peut pas insérer ou déplacer une ligne sous l'identifiant de B ;
- une adhésion REVOKED bloque immédiatement l'accès API ;
- un compte DISABLED et une organisation SUSPENDED sont refusés ;
- le changement arbitraire de `X-Organization-ID` ne donne aucun droit ;
- le contexte RLS est absent après la fin de transaction ;
- les journaux ne contiennent ni question, ni réponse, ni extrait de document.

Ces essais doivent être réalisés sur une vraie instance PostgreSQL et un IdP de test avant toute ouverture.
