# V3.25 — Sécurité et validation de production

## Contrôles automatiques

Avant tout déploiement production ou staging, `scripts/audit_production_env.py --env-file .env` vérifie le mode production, `DEBUG=false`, les secrets obligatoires (32 caractères minimum et non réutilisés), les identifiants PostgreSQL cohérents, les URL HTTPS, l'audience/algorithme OIDC, les origines CORS et la clé publique age. Le contrôle est bloquant dans les workflows GitHub. Il ne lit ni n'affiche les secrets.

`APP_ENV=production` désactive déjà Swagger, ReDoc et OpenAPI. `DEBUG` est désormais explicitement désactivé et validé au démarrage.

## Keycloak / OIDC

Les exports de realm définissent `accessTokenLifespan=900` (15 minutes), `ssoSessionIdleTimeout=1800` et `ssoSessionMaxLifespan=28800`. Le client web conserve le flux Authorization Code + PKCE S256 ; les flux implicite et Direct Access Grants restent désactivés. La rotation des refresh tokens est activée (`revokeRefreshToken=true`, réutilisation maximale nulle). L'API valide signature JWKS, RS256/ES256 autorisés, issuer, audience, exp, iat et sub. Le frontend conserve le jeton d'accès en mémoire et ne stocke pas de refresh token persistant : l'utilisateur devra se reconnecter à l'expiration.

**Realm Keycloak déjà existant :** l'import `--import-realm` n'écrase généralement pas un realm déjà créé. Appliquer les paramètres du realm existant via la console d'administration Keycloak ou `kcadm.sh`, puis vérifier dans `Realm settings > Tokens` que Access Token Lifespan vaut 15 minutes. Vérifier également les paramètres de session SSO. Ne pas considérer la seule modification du JSON comme une modification du realm déjà en service.

## PostgreSQL RLS

Les tests `backend/tests/test_postgres_rls_integration.py` doivent tourner sur une base jetable, après `database/schema.sql` et `database/grant_runtime_permissions.sql`, avec deux URLs distinctes : `TEST_DATABASE_ADMIN_URL` (compte propriétaire/superuser de test) et `TEST_DATABASE_URL` (rôle runtime `cfdt_juris_app`). Le test vérifie explicitement `rolsuper=false` et `rolbypassrls=false`, l'invisibilité des documents et index de l'organisation B depuis A, les écritures inter-tenant et 12 connexions simultanées. La CI utilise un service PostgreSQL dédié et exécute cette suite ; un résultat local sans ces variables ne valide pas RLS.

Commande locale sur une base jetable uniquement :

```bash
TEST_DATABASE_ADMIN_URL=postgresql://... TEST_DATABASE_URL=postgresql://... \
  scripts/run_postgres_security_tests.sh
```

## Sauvegardes et migrations

`upgrade_with_backup.sh` crée une sauvegarde logique avant les migrations de schéma. En production/recette, `BACKUP_AGE_RECIPIENT` est obligatoire et le binaire `age` doit être installé sur l'hôte : le dump est chiffré avant conservation locale. Pour créer une paire : `age-keygen -o age-key.txt`, puis renseigner la clé publique `age1...` dans `BACKUP_AGE_RECIPIENT`. La clé privée age doit être conservée hors du serveur. Vérifier la somme SHA-256, copier le fichier chiffré vers un stockage hors site et tester périodiquement une restauration sur une base isolée.

Les migrations applicatives sont exécutées par le service `migrator` avant le redémarrage de l'API. Les migrations restent transactionnelles et checksumées. La baseline peut inscrire le registre de migrations avant le dump ; elle n'applique pas de changement fonctionnel de schéma.

## Limites de cette livraison

Les contrôles de code et la CI ne prouvent pas que les secrets de l'instance réelle sont correctement renseignés, que le realm Keycloak déjà déployé a été mis à jour, que Stripe fonctionne en live, ni qu'une restauration complète a été testée sur l'infrastructure cible. Ces opérations nécessitent les accès et une fenêtre de recette du propriétaire de l'environnement.
