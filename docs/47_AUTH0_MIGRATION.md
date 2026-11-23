# Auth0 — intégration et migration contrôlée

## Objectif et périmètre

Auth0 remplace le fournisseur d'identité, pas le modèle d'autorisation de Dikévia. Les rôles (ORG_ADMIN, LEGAL_EDITOR, MEMBER), les appartenances, les administrateurs plateforme et les droits par organisation restent dans PostgreSQL. Dikévia ne dépend donc pas du RBAC Auth0 payant ni des fonctionnalités Organizations d'Auth0.

Le navigateur reste un client public OIDC Authorization Code + PKCE. Aucun secret Auth0 ne doit être embarqué dans le frontend. L'API vérifie les jetons d'accès signés en RS256, avec un émetteur, une audience et un JWKS exacts.

## Configuration du tenant Auth0

Créer un tenant Auth0 et deux objets :

1. Une application **Single Page Application** nommée **Dikévia Web**.
2. Une API nommée **Dikévia API**, identifiant **urn:dikevia:api**, algorithme de signature RS256.

Pour l'API, limiter la durée de vie des access tokens à **900 secondes**. Le backend Dikévia rejette volontairement les jetons dont la durée dépasse 15 minutes.

Dans l'application SPA, autoriser explicitement les URL de callback, logout et origines réellement utilisées. Pour les environnements Render actuellement identifiés :

- Production : https://dikevia-commercial-api-l2r8.onrender.com/
- Staging : https://dikevia-vector-beta-staging.onrender.com/

Ne pas utiliser de wildcard d'origine. Vérifier ces URL dans Render avant de les enregistrer dans Auth0.

Activer la connexion par base de données Auth0 et l'inscription via Universal Login. Exiger la vérification de l'adresse e-mail. Ne pas activer de connexion sociale pendant la migration initiale : elle compliquerait la correspondance des identités historiques.

## Claims nécessaires

L'API a besoin de l'adresse e-mail et de son état de vérification dans l'access token, notamment pour accepter une invitation. Auth0 recommande les claims personnalisés namespacés. Créer une Action **Post Login**, puis la déployer et l'ajouter au flux :

~~~javascript
exports.onExecutePostLogin = async (event, api) => {
  if (!event.authorization) return;

  const namespace = "https://dikevia.invalid/claims";

  if (typeof event.user.email === "string") {
    api.accessToken.setCustomClaim(
      `${namespace}/email`,
      event.user.email
    );
  }

  api.accessToken.setCustomClaim(
    `${namespace}/email_verified`,
    event.user.email_verified === true
  );
};
~~~

Le namespace .invalid est volontairement non résolvable : il identifie les claims sans dépendre d'un domaine tiers. Les noms configurés dans OIDC_EMAIL_CLAIM et OIDC_EMAIL_VERIFIED_CLAIM doivent correspondre exactement.

## Variables Render

Les variables publiques et privées sont séparées. Les variables suivantes sont nécessaires :

- OIDC_PROVIDER=auth0
- OIDC_ISSUER=https://TENANT.eu.auth0.com/ — conserver la barre oblique finale exacte.
- OIDC_AUDIENCE=urn:dikevia:api
- OIDC_JWKS_URL=https://TENANT.eu.auth0.com/.well-known/jwks.json
- OIDC_CLIENT_ID — identifiant public de l'application SPA.
- OIDC_SCOPES=openid profile email
- OIDC_AUTHORIZATION_AUDIENCE=urn:dikevia:api
- OIDC_EMAIL_CLAIM=https://dikevia.invalid/claims/email
- OIDC_EMAIL_VERIFIED_CLAIM=https://dikevia.invalid/claims/email_verified

Le frontend charge /auth-config.js, généré côté serveur à partir de ces variables. Seuls l'émetteur, le client ID public, les scopes et l'audience sont transmis au navigateur. Aucun secret client ou Management API ne doit être publié.

## Préservation des comptes et des droits existants

**Ne pas basculer le fournisseur avant d'avoir importé et vérifié les identités.** La base Dikévia associe les utilisateurs à (oidc_issuer, oidc_subject). Une migration qui créerait de nouveaux sujets sans correspondance ferait perdre l'accès aux espaces, même si les adresses e-mail sont identiques.

La compatibilité préparée dans le backend repose sur une importation Auth0 conservant comme user_id la valeur exacte de l'ancien oidc_subject Keycloak. Auth0 préfixe l'identifiant de connexion base de données dans le claim sub (par exemple auth0|<ancien-sujet>). Les variables :

- OIDC_IDENTITY_COMPAT_ISSUER = ancien émetteur Keycloak exact ;
- OIDC_IDENTITY_SUBJECT_PREFIX=auth0|.

permettent au backend de vérifier le jeton avec l'émetteur Auth0, puis de retrouver l'identité interne historique attendue par PostgreSQL. Cette compatibilité ne fonctionne que si l'import Auth0 a réellement conservé les anciens identifiants. Elle ne doit jamais être activée sur la seule base d'une adresse e-mail.

La reprise des mots de passe n'est pas présumée. Les hashes Keycloak doivent être comparés aux formats acceptés par Auth0 ; si le format n'est pas importable, prévoir une réinitialisation sécurisée des mots de passe. Un échantillon d'utilisateurs doit être testé avant tout import global. Contrôler également les comptes sans e-mail, les doublons et les adresses non vérifiées.

## Invitations

En mode Auth0, le backend n'essaie plus de créer les comptes via l'API d'administration Keycloak. Il envoie l'invitation d'organisation par SMTP ; l'utilisateur crée ou ouvre son compte via Universal Login, puis le backend valide le jeton d'invitation et le claim d'e-mail vérifié.

Les variables SMTP_HOST, SMTP_FROM et INVITATION_BASE_URL sont donc suffisantes pour l'envoi des invitations Auth0. Aucun secret Management API n'est requis pour ce parcours.

## Plan de recette avant bascule

1. Créer et configurer le tenant Auth0, l'application SPA, l'API et l'Action Post Login.
2. Importer un compte pilote en conservant son ancien oidc_subject.
3. Vérifier découverte OIDC, exactitude de iss, audience, JWKS, signature, expiration et claims d'e-mail.
4. Vérifier qu'un compte historique retrouve exactement ses organisations et ses rôles.
5. Tester un nouveau compte, l'acceptation d'une invitation, un compte non vérifié, un compte désactivé et un compte sans adhésion.
6. Tester déconnexion, retour de session, APK Android, console d'administration et accès fondateur.
7. Tester le parcours complet sur staging. Garder Keycloak disponible pour le retour arrière.
8. Ne changer les variables de production qu'après validation documentée du staging.

## État actuel

Le code de base Auth0 est préparé dans la branche feat/auth0-oidc-foundation. Aucun tenant Auth0 n'a été créé ou configuré, aucun compte n'a été importé, aucune variable Render n'a été modifiée et aucun déploiement ni changement de base n'a été effectué. La migration des comptes et la recette réelle restent bloquantes avant la bascule.
