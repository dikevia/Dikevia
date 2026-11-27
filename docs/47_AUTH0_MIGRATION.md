> **DOSSIER HISTORIQUE DE MIGRATION AUTH0.** L'intégration Auth0 est terminée sur staging. Ne pas recréer de tenant, réimporter des utilisateurs ou relancer cette migration. La production reste un chantier séparé qui nécessite une autorisation explicite. Voir `docs/57`.

# Auth0 — intégration et migration contrôlée

## Objectif et périmètre

Auth0 remplace le fournisseur d'identité, pas le modèle d'autorisation de Dikévia. Les rôles (ORG_ADMIN, LEGAL_EDITOR, MEMBER), les appartenances, les administrateurs plateforme et les droits par organisation restent dans PostgreSQL. Dikévia ne dépend donc pas du RBAC Auth0 payant ni des fonctionnalités Organizations d'Auth0.

Le navigateur reste un client public OIDC Authorization Code + PKCE. Aucun secret Auth0 ne doit être embarqué dans le frontend. L'API vérifie les jetons d'accès signés en RS256, avec un émetteur, une audience et un JWKS exacts.

## Configuration du tenant Auth0

Le tenant de développement créé est `dev-brlgaz1yh2de3mjo` (région US-5), émetteur `https://dev-brlgaz1yh2de3mjo.us.auth0.com/`. Il contient deux objets :

1. Une application **Single Page Application** nommée **Dikévia Web SPA - Development** (Client ID `BSpBdDO3IUyG2g5JcHYH29e80JRbnW41`).
2. Une API nommée **Dikévia Backend API**, identifiant **https://api.dikevia.fr**, algorithme de signature RS256.

Pour l'API, la durée de vie maximale des access tokens et des tokens implicit/hybrid est configurée à **900 secondes**. Le backend Dikévia rejette volontairement les jetons dont la durée dépasse 15 minutes.

Dans l'application SPA de développement, autoriser uniquement l'origine de staging. Une application Auth0 de développement ne doit pas accepter les callbacks de production ; la production devra utiliser un client Auth0 distinct, configuré dans un environnement/tenant de production séparé. Les callback URLs de staging doivent comprendre `/` et `/static/silent-check-sso.html`.

Configuration effectivement enregistrée pour la SPA de développement :

- État confirmé le 25 novembre 2026 : les quatre listes ont été enregistrées avec uniquement l’origine `https://dikevia-vector-beta-staging.onrender.com` ; les callbacks autorisés sont `/` et `/static/silent-check-sso.html`. Les origines de production ont été retirées.
- Cette SPA reste réservée au staging. La production nécessitera un client Auth0 distinct.

Ne pas utiliser de wildcard d'origine. Vérifier ces URL dans Render avant de les enregistrer dans Auth0.

La connexion `Username-Password-Authentication` est activée pour la SPA ; `google-oauth2` est désactivée. Les inscriptions restent autorisées. La vérification de l'e-mail à l'inscription par lien est activée, l'adresse e-mail est obligatoire et la protection anti-brute-force améliorée est active. La politique de mot de passe impose au minimum 15 caractères ; la sélection de politique Strong/Good/Excellent est indisponible sur le niveau d'essai actuel. Aucune mise à niveau payante n'a été effectuée.

## Claims et identité OIDC

Le navigateur utilise Authorization Code + PKCE et reçoit un access token pour l'API ainsi qu'un ID token OIDC. Le frontend vérifie le nonce, l'émetteur et l'audience de l'ID token, puis transmet ce dernier à l'API dans l'en-tête `X-OIDC-ID-Token`. L'API vérifie à nouveau sa signature, son émetteur, son audience et l'identité `sub` identique à celle de l'access token. L'adresse e-mail et `email_verified` proviennent de cet ID token signé.

Aucune Action Auth0 personnalisée n'est nécessaire pour les claims standard `email` et `email_verified`. Le flux n'accorde aucun rôle ni droit dans Auth0 : les autorisations restent exclusivement dans PostgreSQL. L'API refuse les appels authentifiés si l'ID token ne contient pas une adresse e-mail et `email_verified=true` ; l'utilisateur doit ouvrir le lien de vérification puis se reconnecter.

## Variables Render

Les variables publiques et privées sont séparées. Les valeurs de l'audience ci-dessous doivent correspondre exactement à l'identifiant de ressource de l'API créé dans Auth0 — il ne faut pas utiliser un identifiant de développement différent.

- `OIDC_PROVIDER=auth0`
- `OIDC_ISSUER=https://dev-brlgaz1yh2de3mjo.us.auth0.com/` — conserver la barre oblique finale exacte.
- `OIDC_AUDIENCE=https://api.dikevia.fr` — identifiant exact de l'API déclaré dans Auth0.
- `OIDC_JWKS_URL=https://dev-brlgaz1yh2de3mjo.us.auth0.com/.well-known/jwks.json`
- `OIDC_CLIENT_ID=BSpBdDO3IUyG2g5JcHYH29e80JRbnW41` — identifiant public de l'application SPA.
- `OIDC_SCOPES=openid profile email`
- `OIDC_AUTHORIZATION_AUDIENCE=https://api.dikevia.fr` — strictement identique à `OIDC_AUDIENCE`.
- `OIDC_EMAIL_CLAIM=email`
- `OIDC_EMAIL_VERIFIED_CLAIM=email_verified`

Le frontend charge `/auth-config.js`, généré côté serveur à partir de ces variables. Seuls l'émetteur, le client ID public, les scopes et l'audience sont transmis au navigateur. Aucun secret client ou Management API ne doit être publié.

## Préservation des comptes et des droits existants

**Ne pas basculer le fournisseur avant d'avoir importé et vérifié les identités.** La base Dikévia associe les utilisateurs à (`oidc_issuer`, `oidc_subject`). Le préfixe Auth0 `auth0|` est retiré uniquement pour un contrôle de correspondance sous RLS. Une migration qui créerait de nouveaux sujets sans correspondance ferait perdre l'accès aux espaces, même si les adresses e-mail sont identiques.

La correspondance historique est résolue côté API par une recherche PostgreSQL sous RLS : pour un sujet Auth0 de la connexion base de données commençant par `auth0|`, le backend retire ce préfixe uniquement pour vérifier si le couple exact (ancien émetteur Keycloak, ancien sujet) existe encore et correspond à un compte actif. Si le compte historique existe, le backend réutilise cette identité ; sinon, il conserve intégralement l'identité Auth0 native. Aucun rapprochement par adresse e-mail, aucune revendication fournie par l'utilisateur et aucune Action Auth0 ne sont utilisés. Le lookup est limité au sujet signé du jeton et à la politique RLS PostgreSQL.

Pour l'import Auth0, le champ `user_id` doit contenir l'ancien `oidc_subject` Keycloak **sans** préfixe `auth0|`. Auth0 ajoute lui-même le préfixe de la connexion base de données dans le sujet final du jeton (`auth0|<user_id>`). Ne jamais fournir `auth0|<ancien-sujet>` dans le fichier d'import, sous peine d'obtenir un double préfixe et de perdre la correspondance. Le pilote doit vérifier le `sub` réellement émis avant tout import massif.

La reprise des mots de passe n'est pas présumée. Les hashes Keycloak doivent être comparés aux formats acceptés par Auth0 ; si le format n'est pas importable, prévoir une réinitialisation sécurisée des mots de passe. Un échantillon d'utilisateurs doit être testé avant tout import global. Contrôler également les comptes sans e-mail, les doublons et les adresses non vérifiées.

## Invitations

En mode Auth0, le backend n'essaie plus de créer les comptes via l'API d'administration Keycloak. Il envoie l'invitation d'organisation par SMTP ; l'utilisateur crée ou ouvre son compte via Universal Login, puis le backend valide le jeton d'invitation et le claim d'e-mail vérifié.

Les variables `SMTP_HOST`, `SMTP_FROM` et `INVITATION_BASE_URL` sont nécessaires pour l'envoi des invitations d'organisation par Dikévia. Auth0 gère séparément le lien de vérification d'e-mail de son compte. Aucun secret Management API n'est requis pour ce parcours.

## Plan de recette avant bascule

1. Restreindre les quatre allowlists de la SPA Auth0 de développement au seul domaine staging, avec les deux callbacks exacts.
2. Configurer les variables OIDC uniquement sur le service Render staging.
3. Vérifier découverte OIDC, exactitude de `iss`, audience, JWKS, signature, nonce, expiration et ID token.
4. Importer un seul compte pilote en conservant son ancien `oidc_subject`, après validation de la méthode d'import.
5. Vérifier que ce compte retrouve exactement ses organisations, ses rôles et ses droits.
6. Tester un nouveau compte, l'acceptation d'une invitation, un compte non vérifié, un compte désactivé et un compte sans adhésion.
7. Tester déconnexion, retour de session, APK Android, console d'administration et accès fondateur.
8. Tester le parcours complet sur staging. Garder Keycloak disponible pour le retour arrière.
9. Ne changer les variables de production qu'après validation documentée du staging et préparation d'un client Auth0 distinct pour la production.

## État actuel

Le tenant Auth0 de développement, la SPA et l'API sont créés. Les connexions de la SPA sont limitées à la base de données Auth0 ; Google OAuth2 est désactivé pour cette application. La vérification de l'adresse e-mail à l'inscription par lien est activée. Le token API et le token implicit/hybrid ont une durée maximale de 900 secondes. Le code Auth0 a été intégré à `main` via la PR #74 ; la branche historique `feat/auth0-oidc-foundation` contient des commits ultérieurs et ne doit pas être fusionnée directement dans `main`. Aucun compte n'a été importé, aucune variable Render n'a été modifiée, aucun déploiement ni changement de base n'a été effectué. La migration des comptes et la recette réelle restent bloquantes avant la bascule.


## Vérifications complémentaires — 26 novembre 2026

### Autorisation de la SPA sur l'API

La dernière vérification connue signalait que l'application SPA n'était pas autorisée à obtenir un jeton d'accès pour l'API. Aucune preuve récente de correction n'est disponible. Avant toute recette Auth0, vérifier qu'une connexion PKCE retourne bien un access token dont l'audience est exactement `https://api.dikevia.fr`, puis que l'API accepte ce jeton. Ne pas confondre l'ID token destiné au client SPA et l'access token destiné à l'API.

### Sessions persistantes côté serveur

Le BFF de sessions OIDC est désormais présent dans `main` et dans la branche commerciale historique. Il reste explicitement désactivé par défaut (`OIDC_SERVER_SESSIONS_ENABLED=false`) ; le parcours actuellement configuré n'utilise donc pas les sessions HttpOnly côté serveur. La table `oidc_sessions` existe dans la base applicative de production et ne contient aucune session au contrôle du 26 novembre 2026. La branche Neon de test du corpus ne possède pas cette table.

L'activation du BFF exige une clé AES-256 de 32 octets (64 caractères hexadécimaux ou base64url), une URI HTTPS autorisée et un flux Auth0 renvoyant un refresh token. La branche commerciale historique conserve `OIDC_SCOPES=openid`, tandis que `main` prévoit `openid profile email`. Dans les deux cas, le BFF Auth0 exige explicitement `offline_access` lorsqu'il est activé. Il faut également activer la rotation des refresh tokens dans la SPA Auth0.

**Configuration requise avant activation, uniquement sur staging :**

- `OIDC_SERVER_SESSIONS_ENABLED=true`
- `OIDC_SESSION_ENCRYPTION_KEY` : clé aléatoire de 32 octets, stockée comme secret Render
- `OIDC_REDIRECT_URI` : origine HTTPS exacte de l'application, terminée par `/`, autorisée dans Auth0 et dans les origines CORS
- `OIDC_SCOPES=openid profile email offline_access`

La migration `029_oidc_server_sessions.sql` doit être présente sur la branche de base utilisée par le service avant activation. Le fichier de rollback correspondant invalide et supprime toutes les sessions : il ne doit être exécuté qu'en cas de décision explicite de retour arrière. Aucune migration ni modification de secret Render n'a été effectuée pendant cette intervention.

Avant toute activation, tester le cycle complet PKCE, callback, création de cookie HttpOnly/Secure, vérification de session, renouvellement avec rotation, déconnexion/révocation et protection CSRF. Ne pas activer cette option en production par simple changement de drapeau.

### Règles de bascule

- Le tenant US-5 reste un tenant de développement/staging ; il ne doit pas servir de tenant de production pour des données réelles sans validation juridique et contractuelle de la résidence des données.
- Aucun import global d'utilisateurs ni aucune bascule définitive des comptes Keycloak ne sont réputés réalisés.
- Les comptes, appartenances, rôles et droits PostgreSQL doivent rester la source d'autorité ; aucun rapprochement par adresse e-mail seule n'est acceptable.
- Le service Render commercial déploie encore la branche `feature/dikevia-v3.38.5-cgfp-chat`. La branche `main` n'est pas encore la source de déploiement de ce service.
