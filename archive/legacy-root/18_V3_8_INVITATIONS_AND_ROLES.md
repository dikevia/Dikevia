# V3.8 — Invitations automatisées et rôles

## Parcours d'invitation

Quand `KEYCLOAK_ADMIN_BASE_URL`, `KEYCLOAK_ADMIN_CLIENT_SECRET`, `SMTP_HOST` et `SMTP_FROM` sont configurés, la création d'une invitation :

1. génère un jeton aléatoire à usage unique ; seule son empreinte SHA-256 est stockée en base ;
2. utilise un client confidentiel de service pour rechercher ou créer le compte Keycloak ;
3. pour un nouveau compte, impose `VERIFY_EMAIL` et `UPDATE_PASSWORD` ; un compte existant est réutilisé sans toucher à son mot de passe ;
4. demande à Keycloak de vérifier l'adresse si elle ne l'est pas encore (et, pour un nouveau compte, de définir le mot de passe) ;
5. envoie par SMTP applicatif un lien contenant le jeton d'invitation CFDT JURIS ;
6. l'utilisateur se connecte via OIDC, puis accepte l'invitation avec le jeton ; le serveur vérifie l'adresse e-mail vérifiée et l'usage unique.

Si le provisionnement ou l'envoi échoue, l'invitation en attente est révoquée et l'API renvoie une erreur 503. Si les paramètres automatiques ne sont pas renseignés, le mode manuel existant est conservé : l'API retourne le jeton une seule fois, avec `Cache-Control: no-store`.

## Compte de service Keycloak

Créer dans le realm `cfdt` un client confidentiel nommé `cfdt-juris-provisioner`, activer Service accounts, puis attribuer au compte de service uniquement le rôle realm-management `manage-users`. Générer un secret distinct, le placer dans `KEYCLOAK_ADMIN_CLIENT_SECRET`, et ne jamais le mettre dans un fichier frontend, un dépôt public ou un navigateur. Ne pas utiliser le compte bootstrap administrateur pour l'API.

Configurer le serveur SMTP de Keycloak séparément pour ses e-mails de vérification et de changement de mot de passe. CFDT JURIS utilise aussi son propre SMTP applicatif pour le lien d'invitation contenant le jeton métier. Les deux canaux doivent être testés et délivrables avant activation. Les deux canaux doivent être testés et délivrables avant activation.

## Changement et révocation des rôles

`PATCH /api/v1/organizations/me/members/{user_id}/role` accepte `ORG_ADMIN`, `LEGAL_EDITOR` ou `MEMBER`. Seul un administrateur de l'organisation peut l'utiliser. Le changement est limité à l'organisation active et journalisé. Le serveur verrouille la ligne organisation et refuse de retirer le rôle du dernier administrateur actif.

La révocation d'un membre demeure limitée à son adhésion dans l'organisation courante. Elle ne désactive jamais globalement le compte Keycloak : un utilisateur peut être membre de plusieurs organisations indépendantes.

## Variables

Voir `deploy/.env.example` : `KEYCLOAK_ADMIN_*`, `SMTP_*` et `INVITATION_BASE_URL`. Utiliser SMTP TLS (port 465 SSL ou 587 STARTTLS), des secrets distincts, et HTTPS en production. `INVITATION_BASE_URL` doit être l'origine publique de l'application, sans chemin final.

## Limites et validation de production

La V3.8 fournit le code d'intégration mais ne peut pas prouver l'envoi d'un vrai e-mail ni le provisionnement réel sans un realm Keycloak, un client de service configuré et un serveur SMTP accessibles. Avant production, tester : compte neuf, compte déjà existant, e-mail non vérifié, lien expiré, jeton réutilisé, panne SMTP, panne Keycloak, invitation révoquée, rôle refusé, dernier administrateur, et révocation d'un membre appartenant aussi à une autre organisation.
