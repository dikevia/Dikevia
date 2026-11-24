# Auth0 — intégration et migration contrôlée

## Objectif et périmètre

Auth0 remplace le fournisseur d'identité, pas le modèle d'autorisation de Dikévia. Les rôles (ORG_ADMIN, LEGAL_EDITOR, MEMBER), les appartenances, les administrateurs plateforme et les droits par organisation restent dans PostgreSQL. Dikévia ne dépend donc pas du RBAC Auth0 payant ni des fonctionnalités Organizations d'Auth0.

Le navigateur reste un client public OIDC Authorization Code + PKCE. Aucun secret Auth0 ne doit être embarqué dans le frontend. L'API vérifie les jetons d'accès signés en RS256, avec un émetteur, une audience et un JWKS exacts.

## Configuration du tenant Auth0

Le tenant de développement créé est `dev-brlgaz1yh2de3mjo` (région US-5), émetteur `https://dev-brlgaz1yh2de3mjo.us.auth0.com/`. Il contient deux objets :

1. Une application **Single Page Application** nommée **Dikévia Web SPA - Development** (Client ID `BSpBdDO3IUyG2g5JcHYH29e80JRbnW41`).
2. Une API nommée **Dikévia API - Development**, identifiant **https://dikevia-commercial-api-l2r8.onrender.com**, algorithme de signature RS256.

Pour l'API, la durée de vie maximale des access tokens et des tokens implicit/hybrid est configurée à **900 secondes**. Le backend Dikévia rejette volontairement les jetons dont la durée dépasse 15 minutes.

Dans l'application SPA, autoriser explicitement les URL de callback, logout et origines réellement utilisées. Pour les environnements Render actuellement identifiés :

- Production : https://dikevia-commercial-api-l2r8.onrender.com/
- Staging : https://dikevia-vector-beta-staging.onrender.com/

Ne pas utiliser de wildcard d'origine. Vérifier ces URL dans Render avant de les enregistrer dans Auth0.

Activer la connexion par base de données Auth0 et l'inscription via Universal Login. Exiger la vérification de l'adresse e-mail. Ne pas activer de connexion sociale pendant la migration initiale : elle compliquerait la correspondance des identités historiques.

## Claims et identité OIDC

Le navigateur utilise Authorization Code + PKCE et reçoit un access token pour l'API ainsi qu'un ID token OIDC. Le frontend vérifie le nonce, l'émetteur et l'audience de l'ID token, puis transmet ce dernier à l'API dans l'en-tête `X-OIDC-ID-Token`. L'API vérifie à nouveau sa signature, son émetteur, son audience et l'identité `sub` identique à celle de l'access token. L'adresse e-mail et `email_verified` proviennent de cet ID token signé.

Aucune Action Auth0 personnalisée n'est nécessaire pour les claims standard `email` et `email_verified`. Le flux n'accorde aucun rôle ni droit dans Auth0 : les autorisations restent exclusivement dans PostgreSQL.

## Variables Render

Les variables publiques et privées sont séparées. Les variables suivantes sont nécessaires :

- OIDC_PROVIDER=auth0
- OIDC_ISSUER=https://dev-brlgaz1yh2de3mjo.us.auth0.com/ — conserver la barre oblique finale exacte.
- OIDC_AUDIENCE=https://dikevia-commercial-api-l2r8.onrender.com
- OIDC_JWKS_URL=https://dev-brlgaz1yh2de3mjo.us.auth0.com/.well-known/jwks.json
- OIDC_CLIENT_ID=BSpBdDO3IUyG2g5JcHYH29e80JRbnW41 — identifiant public de l'application SPA.
- OIDC_SCOPES=openid profile email
- OIDC_AUTHORIZATION_AUDIENCE=https://dikevia-commercial-api-l2r8.onrender.com
- OIDC_EMAIL_CLAIM=https://dikevia.invalid/claims/email
- OIDC_EMAIL_VERIFIED_CLAIM=https://dikevia.invalid/claims/email_verified

Le frontend charge /auth-config.js, généré côté serveur à partir de ces variables. Seuls l'émetteur, le client ID public, les scopes et l'audience sont transmis au navigateur. Aucun secret client ou Management API ne doit être publié.

## Préservation des comptes et des droits existants

**Ne pas basculer le fournisseur avant d'avoir importé et vérifié les identités.** La base Dikévia associe les utilisateurs à (oidc_issuer, oidc_subject). Le préfixe Auth0 `auth0|` est retiré uniquement pour un contrôle de correspondance sous RLS. Une migration qui créerait de nouveaux sujets sans correspondance ferait perdre l'accès aux espaces, même si les adresses e-mail sont identiques.

La correspondance historique est résolue côté API par une recherche PostgreSQL sous RLS : pour un sujet Auth0 de la connexion base de données commençant par `auth0|`, le backend retire ce préfixe uniquement pour vérifier si le couple exact (ancien émetteur Keycloak, ancien sujet) existe encore et correspond à un compte actif. Si le compte historique existe, le backend réutilise cette identité ; sinon, il conserve intégralement l'identité Auth0 native. Aucun rapprochement par adresse e-mail, aucune revendication fournie par l'utilisateur et aucune Action Auth0 ne sont utilisés. Le lookup est limité au sujet signé du jeton et à la politique RLS PostgreSQL.

La reprise des mots de passe n'est pas présumée. Les hashes Keycloak doivent être comparés aux formats acceptés par Auth0 ; si le format n'est pas importable, prévoir une réinitialisation sécurisée des mots de passe. Un échantillon d'utilisateurs doit être testé avant tout import global. Contrôler également les comptes sans e-mail, les doublons et les adresses non vérifiées.

## Invitations

En mode Auth0, le backend n'essaie plus de créer les comptes via l'API d'administration Keycloak. Il envoie l'invitation d'organisation par SMTP ; l'utilisateur crée ou ouvre son compte via Universal Login, puis le backend valide le jeton d'invitation et le claim d'e-mail vérifié.

Les variables SMTP_HOST, SMTP_FROM et INVITATION_BASE_URL sont donc suffisantes pour l'envoi des invitations Auth0. Aucun secret Management API n'est requis pour ce parcours.

## Plan de recette avant bascule

1. Créer et configurer le tenant Auth0, l'application SPA et l'API.
2. Importer un compte pilote en conservant son ancien oidc_subject.
3. Vérifier découverte OIDC, exactitude de iss, audience, JWKS, signature, nonce, expiration et ID token.
4. Vérifier qu'un compte historique retrouve exactement ses organisations et ses rôles.
5. Tester un nouveau compte, l'acceptation d'une invitation, un compte non vérifié, un compte désactivé et un compte sans adhésion.
6. Tester déconnexion, retour de session, APK Android, console d'administration et accès fondateur.
7. Tester le parcours complet sur staging. Garder Keycloak disponible pour le retour arrière.
8. Ne changer les variables de production qu'après validation documentée du staging.

## État actuel

Le tenant Auth0 de développement, la SPA et l'API sont créés. Les connexions de la SPA sont limitées à la base de données Auth0 ; Google OAuth2 est désactivé pour cette application. La vérification de l'adresse e-mail à l'inscription par lien est activée. Le code Auth0 est préparé dans la branche feat/auth0-oidc-foundation. Aucun compte n'a été importé, aucune variable Render n'a été modifiée, aucun déploiement ni changement de base n'a été effectué. La migration des comptes et la recette réelle restent bloquantes avant la bascule.
