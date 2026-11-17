# V3.5 — Durcissement de l'authentification et du démarrage

## Objectif
Réduire les erreurs de configuration avant déploiement et durcir la validation des jetons d'accès OIDC, sans prétendre remplacer les essais avec le fournisseur d'identité retenu.

## Contrôles ajoutés
- Configuration OIDC partielle refusée ; configuration OIDC complète obligatoire en production.
- PostgreSQL obligatoire en production.
- HTTPS obligatoire pour l'émetteur OIDC, l'URL JWKS et chaque origine CORS en production.
- Origines CORS explicites, sans joker `*`.
- Algorithmes JWT autorisés : RS256 et ES256 uniquement.
- Claims obligatoires : `exp`, `iat`, `iss`, `sub`, `aud` ; vérification signature, issuer et audience ; tolérance d'horloge de 30 secondes.
- Jetons Bearer limités à 16 Kio ; délai de récupération JWKS limité à 5 secondes.
- En-têtes de sécurité ; HSTS uniquement en production ; réponses `/api/` non mises en cache.
- `/health` = vivacité ; `/ready` = accès PostgreSQL ; OpenAPI désactivé en production.

## Paramétrage production
Exemple indicatif, à remplacer par les valeurs exactes du fournisseur retenu :

```dotenv
APP_ENV=production
DATABASE_URL=postgresql://... 
OIDC_ISSUER=https://identite.exemple.fr/realm/cfdt
OIDC_AUDIENCE=cfdt-juris-api
OIDC_JWKS_URL=https://identite.exemple.fr/realm/cfdt/protocol/openid-connect/certs
OIDC_ALGORITHMS=RS256
CORS_ORIGINS=https://juris.exemple.fr
```

Ne jamais réutiliser les valeurs d'exemple en production. Protéger les secrets et utiliser un certificat TLS valide.

## Limites et vérifications à effectuer
- Le fournisseur OIDC n'est pas encore sélectionné ni connecté dans ce kit.
- Aucun test réel de découverte OIDC/JWKS, de rotation de clés, de révocation de session ou de parcours navigateur n'est revendiqué.
- `/ready` vérifie PostgreSQL seulement ; il ne teste pas ClamAV, le fournisseur OIDC ni le moteur IA.
- Les en-têtes HTTP ne remplacent pas une politique CSP adaptée à l'interface finale, ni la configuration TLS du reverse proxy.
- Les migrations et tests RLS doivent encore être exécutés sur une instance PostgreSQL dédiée.
