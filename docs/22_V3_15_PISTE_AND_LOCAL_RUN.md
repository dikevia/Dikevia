# V3.15 — Connecteur PISTE/Légifrance et démarrage local

## Connecteur Légifrance

Le connecteur utilise les URL et exemples de la FAQ officielle Légifrance : OAuth2 Client Credentials, `GET /list/ping`, `POST /search` et `POST /consult/getArticle`. La recherche utilise le fonds `CODE_DATE`, le nom officiel du CGFP et un filtre `DATE_VERSION` à la date des faits. Les résultats ne sont retenus qu'après une récupération de l'article dont l'identifiant `LEGIARTI` correspond à celui retourné par la recherche et dont un champ de texte est exploitable.

Références officielles consultées le 16/11/2026 :
- https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api
- https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api
- https://piste.gouv.fr/

La documentation DILA indique que sandbox et production ont des URL, applications et identifiants distincts. Les CGU de l'API doivent être acceptées et l'API Légifrance activée dans l'application PISTE. Les secrets doivent rester dans l'environnement serveur.

Variables : `LEGIFRANCE_ENVIRONMENT`, `LEGIFRANCE_CLIENT_ID`, `LEGIFRANCE_CLIENT_SECRET`, `LEGIFRANCE_SCOPE`, `LEGIFRANCE_TIMEOUT_SECONDS`, `LEGIFRANCE_CODE_NAME`.

Routes authentifiées :
- `GET /api/v1/integrations/legifrance/status` : état de configuration, sans secret.
- `POST /api/v1/integrations/legifrance/check` : test OAuth et ping API.
- `GET /api/v1/legal/legifrance/search?q=...&effective_date=AAAA-MM-JJ` : recherche et récupération des articles du CGFP à une date.

La réponse reste `PARTIELLEMENT_VERIFIE`. Le connecteur ne prétend pas valider les textes réglementaires complémentaires, la jurisprudence, les actes locaux ni l'analyse de toutes les dispositions transitoires. Une recherche sans résultat ne prouve jamais l'absence de droit. Les réponses JSON de l'API peuvent évoluer : si leur forme n'est pas reconnue, le connecteur refuse la citation.

## Démarrage local sur installation neuve

Prérequis : Docker Engine et Docker Compose plugin.

Depuis la racine du projet :

```bash
python scripts/prepare_dev_env.py
docker compose -f deploy/docker-compose.yml up --build -d
docker compose -f deploy/docker-compose.yml ps
```

Le script crée un `.env` local avec secrets aléatoires et permissions restreintes. Ne pas le committer.

Pour une base neuve, le conteneur PostgreSQL exécute dans l'ordre :
1. création du rôle runtime non privilégié ;
2. schéma consolidé `database/schema.sql` ;
3. droits minimaux `database/grant_runtime_permissions.sql`.

**Important :** les scripts `/docker-entrypoint-initdb.d` ne s'exécutent qu'à l'initialisation d'un volume PostgreSQL vide. Ils ne migrent pas une base existante. Ne jamais supprimer le volume de production pour relancer l'initialisation. Une base existante doit être migrée séparément selon la procédure du README.

Pour une URL de déploiement différente de localhost, charger les variables avant de régénérer la configuration OIDC navigateur et l'import Keycloak :

```bash
set -a; . ./.env; set +a
python scripts/render_keycloak_config.py
```

Vérifications de base :

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready
```

Keycloak est exposé localement sur `http://localhost:8081`. L'application est sur `http://localhost:8000`. Le premier utilisateur et la première organisation doivent être provisionnés selon les scripts SQL de bootstrap et les procédures d'administration documentées.

## Limites connues

- Les identifiants PISTE et l'acceptation des CGU restent à fournir par le porteur.
- L'adaptateur IA nécessite les identifiants d'un fournisseur choisi et une validation RGPD/contractuelle.
- La constitution et validation du corpus Ville de Saint-Étienne et Métropole restent à faire.
- La recherche de jurisprudence n'est pas encore raccordée.
- Les tests HTTP sont simulés ; aucune connexion réelle PISTE n'est possible sans secrets utilisateur.
- Le déploiement, le reverse proxy HTTPS, les sauvegardes, la restauration et les tests d'isolation sur PostgreSQL réel restent à effectuer.
