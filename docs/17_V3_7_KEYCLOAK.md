> **DOCUMENT HISTORIQUE — KEYCLOAK N'EST PLUS LE FOURNISSEUR PAR DÉFAUT.** Auth0 est le fournisseur retenu et validé sur staging. Le Compose normal ne démarre plus Keycloak ; ne pas suivre les étapes de démarrage ou de migration de ce document. Voir `docs/57`.

# V3.7 — Fournisseur d'identité Keycloak

## Objectif et périmètre
La V3.7 fournit une configuration de départ Keycloak pour l'authentification OIDC de CFDT JURIS. Le realm `cfdt` contient le client navigateur public `cfdt-juris-web`, Authorization Code + PKCE S256, sans secret client, et un mapper qui ajoute l'audience `cfdt-juris-api` aux jetons d'accès. L'API continue de valider signature, issuer, audience, expiration et JWKS ; les rôles métier et les appartenances restent dans PostgreSQL, pas dans des rôles Keycloak.

Keycloak utilise sa propre base PostgreSQL `keycloak-db`, séparée de la base métier `db`. Aucun utilisateur final, mot de passe utilisateur ou compte administrateur précréé n'est inclus dans l'archive.

## Démarrage local
1. Depuis la racine `CFDT_JURIS_V3`, copier `deploy/.env.example` vers `.env`.
2. Remplacer tous les `CHANGE_ME_*` par des secrets longs et distincts. Ne pas réutiliser le mot de passe PostgreSQL métier pour Keycloak.
3. Garder en local `KEYCLOAK_PUBLIC_URL=http://localhost:8081` et `PUBLIC_APP_URL=http://localhost:8000`.
4. Générer le realm et la configuration du navigateur :
   ```bash
   set -a
   . ./.env
   set +a
   python scripts/render_keycloak_config.py
   ```
   Le script crée `deploy/keycloak/import/realm-cfdt.json` et met à jour `frontend/auth-config.js` à partir des deux URL publiques.
5. Démarrer les services : `docker compose -f deploy/docker-compose.yml up -d --build`.
6. Vérifier `http://localhost:8081/realms/cfdt/.well-known/openid-configuration` et `http://localhost:8000/health`.
7. Ouvrir la console Keycloak sur `http://localhost:8081/admin/` et utiliser uniquement le compte bootstrap défini par `KEYCLOAK_ADMIN_USERNAME` et `KEYCLOAK_ADMIN_PASSWORD`.

Le realm est importé au premier démarrage si le realm `cfdt` n'existe pas déjà. L'import au démarrage n'écrase pas un realm existant : après une première initialisation, les changements doivent être appliqués explicitement depuis la console ou via une procédure d'administration contrôlée.

## Paramètres API
- `OIDC_ISSUER` doit correspondre exactement à l'issuer public annoncé dans le jeton, par exemple `http://localhost:8081/realms/cfdt` en local.
- `OIDC_AUDIENCE=cfdt-juris-api` correspond à l'audience ajoutée par le client scope `cfdt-juris-api-audience`.
- `OIDC_JWKS_URL` peut utiliser l'adresse interne Docker `http://keycloak:8080/realms/cfdt/protocol/openid-connect/certs`. Le JWKS est public ; l'issuer du jeton reste l'URL publique.
- `OIDC_ALGORITHMS=RS256`.
- L'email vérifié est nécessaire au parcours d'acceptation d'invitation.

## Déploiement derrière un reverse proxy
- Utiliser des noms DNS publics et HTTPS pour `KEYCLOAK_PUBLIC_URL` et `PUBLIC_APP_URL`.
- Terminer TLS au reverse proxy, transmettre les en-têtes `X-Forwarded-*` fiables, et ajouter le fichier de surcharge `deploy/docker-compose.proxy.yml` uniquement si le proxy écrase ces en-têtes entrants.
- Conserver le port Keycloak lié à `127.0.0.1:8081` : il n'est pas publié directement sur Internet. Le reverse proxy local peut joindre le port 8081 sur l'hôte ; s'il est conteneurisé, le connecter au réseau Compose et joindre `keycloak:8080`. Dans ce cas, utiliser aussi `-f deploy/docker-compose.proxy.yml` pour activer les en-têtes transférés.
- Générer à nouveau le realm et `auth-config.js` avec les URL publiques avant le build de l'API.
- Renseigner les mêmes URLs publiques dans `OIDC_ISSUER`, `OIDC_JWKS_URL` (l'URL JWKS interne peut rester interne) et `CORS_ORIGINS`.
- Mettre en place des sauvegardes chiffrées de `keycloak_data`, une rotation des secrets, une supervision, une politique de mise à jour et un test de restauration.

## Provisionnement des utilisateurs
L'inscription libre est désactivée. Les utilisateurs doivent être créés/invités par un administrateur Keycloak selon la procédure opérationnelle retenue, puis disposer d'une invitation CFDT JURIS en base pour rejoindre leur organisation. Le compte Keycloak seul ne donne aucun accès métier. Le lien d'invitation CFDT JURIS doit être accepté avec une identité dont l'adresse e-mail est vérifiée.

La V3.7 ne met pas en place l'envoi automatique d'e-mails ni l'administration Keycloak via Admin REST API. Le jeton d'invitation métier reste remis par un canal sûr comme dans la V3.6.

## Limites et essais obligatoires
Cette livraison ne prouve pas que le conteneur Keycloak a démarré dans l'environnement cible : Docker n'est pas disponible dans l'environnement de génération. Avant production, tester réellement le démarrage, l'import du realm, la connexion navigateur, le contenu des claims `iss`, `aud`, `sub`, `email`, `email_verified`, la rotation JWKS, la déconnexion, le reset de mot de passe, le SMTP, la révocation de session et les parcours d'invitation. Le realm importé est un point de départ à auditer et durcir selon l'infrastructure réelle.
