# CFDT JURIS V3.22 — validation d'exploitation, migrations et préproduction

## 1. Périmètre de cette livraison

La V3.22 part de l'archive V3.21. Elle consolide quatre points de l'audit :

- validation automatisée des dépendances et des variables d'environnement ;
- registre de migrations PostgreSQL avec checksum, verrou advisory et rollback contrôlé ;
- exécution réelle des tests d'isolation RLS dans la CI sur un service PostgreSQL éphémère ;
- bootstrap local/staging et supervision Prometheus, Blackbox Exporter, PostgreSQL Exporter, Alertmanager et Grafana.

`asyncpg` était déjà une dépendance runtime dans `backend/requirements.txt`. Le problème précédent était l'absence d'un PostgreSQL de test et l'absence de configuration des URL de test, pas l'absence de déclaration de la dépendance.

## 2. Variables d'environnement

Le script `python scripts/audit_env_example.py` compare les champs de `backend/app/config.py` à toutes les variables documentées dans `deploy/.env.example`, y compris les variables facultatives commentées.

- `.env.example` : environnement local.
- `.env.staging.example` : modèle staging isolé ; remplacer les domaines `example.org`, puis renseigner les identifiants PISTE sandbox et Stripe test.
- Pour une installation existante, `python3 scripts/upgrade_env_file.py` (ou `--staging`) ajoute les variables nouvelles sans écraser les valeurs déjà présentes. Les secrets manquants sont générés aléatoirement ; vérifier les URLs de connexion avant redémarrage.
- **Attention aux volumes existants :** renseigner `COMPOSE_PROJECT_NAME` avec le nom exact du projet Compose qui possède déjà la base. Le script refuse de choisir un nom automatiquement si cette variable manque, car un nom différent créerait un nouveau volume PostgreSQL vide.
- Les fichiers `.env` et `.env.staging` sont locaux, chmod 0600, et ignorés par Git.
- Les mots de passe PostgreSQL/Keycloak/Grafana sont générés localement par `scripts/prepare_dev_env.py`. `scripts/render_runtime_env.py` construit `.env.runtime` (ou `.env.staging.runtime`) à partir des seuls champs `Settings` : les mots de passe DBA, Keycloak DB, Grafana et monitoring ne sont pas transmis au conteneur API. Le rôle DBA n'est injecté que dans le conteneur ponctuel `migrator`.

Les clés de fournisseur IA, PISTE et Stripe ne sont jamais générées : elles doivent provenir des comptes réels du fournisseur.

## 3. Migrations PostgreSQL

Le fichier `database/schema.sql` est le schéma consolidé de référence de la V3.21 (baseline 009). Le registre `schema_migrations` est créé/administré par `scripts/db_migrate.py`.

### Première adoption d'une base déjà initialisée

Après démarrage des services et application du schéma consolidé :

```bash
docker compose -p cfdt-juris --env-file .env -f deploy/docker-compose.yml \
  run --rm migrator python /srv/scripts/db_migrate.py baseline
```

La commande vérifie la présence des tables principales et des fonctions d'administration avant d'enregistrer la baseline. Une base V3.20 sans tables du corpus est enregistrée en V8, puis la migration 009 est appliquée par `upgrade`; une base déjà V3.21 est enregistrée en V9. Elle est idempotente si la baseline est déjà présente.

### État et application

```bash
docker compose -p cfdt-juris --env-file .env -f deploy/docker-compose.yml \
  run --rm migrator python /srv/scripts/db_migrate.py status

scripts/upgrade_with_backup.sh
```

`upgrade_with_backup.sh` crée/met à niveau les rôles d'ingestion et de supervision, produit ensuite une sauvegarde PostgreSQL avec empreinte SHA-256, puis exécute le runner dans le conteneur ponctuel `migrator`, qui seul reçoit l'URL DBA. Chaque migration future `010_*.sql` ou supérieure est exécutée avec l'enregistrement du checksum dans la même transaction PostgreSQL. Un verrou advisory empêche deux déploiements de migrer simultanément.

### Rollback

Toute nouvelle migration doit fournir un fichier correspondant dans `database/migrations/rollback/` avant de pouvoir être appliquée, par exemple :

- `database/migrations/010_feature.sql`
- `database/migrations/rollback/010_feature.down.sql`

Le rollback est limité à la dernière migration. Le wrapper demande de retaper `ROLLBACK-VERSION`, réalise une sauvegarde, puis transmet les confirmations explicites au runner :

```bash
ENV_FILE=.env COMPOSE_PROJECT_NAME=cfdt-juris scripts/rollback_with_backup.sh 10
```

Les migrations 001 à 008 sont le socle historique non réversible automatiquement : revenir avant elles nécessite une restauration de sauvegarde. Pour une base V3.20 (baseline V8), la migration 009 est appliquée séparément et dispose d'un `down.sql` destructif ; pour une base déjà V3.21, elle est incluse dans le baseline V9 et ne peut pas être annulée par SQL. Le rollback exige une sauvegarde vérifiée et une confirmation interactive ; il supprime le corpus juridique national.

## 4. CI et test RLS multi-tenant

Le workflow `.github/workflows/ci.yml` démarre maintenant PostgreSQL 16, crée quatre rôles distincts (migration, runtime, ingestion et monitoring), applique `database/schema.sql` et `database/grant_runtime_permissions.sql`, puis exécute `backend/tests/test_postgres_rls_integration.py` avec :

- une connexion administrateur pour préparer/nettoyer les fixtures ;
- une connexion réelle `cfdt_juris_app`, non propriétaire et sans `BYPASSRLS`, pour les assertions d'isolation.

Le test vérifie deux organisations, la visibilité des documents, memberships, invitations, paramètres et journaux, les écritures inter-tenant forgées, l'absence de contexte tenant et l'accès à l'identité vérifiée. Un second test ouvre simultanément 12 connexions runtime (une par organisation) et vérifie qu'aucune lecture ne traverse les frontières tenant. La restauration PostgreSQL réapplique aussi les droits runtime et les droits d'ingestion du corpus après `pg_restore`.

Ce test est une preuve d'intégration ciblée, pas un test de charge. Avant production, compléter par un test de charge multi-organisations et une revue indépendante des politiques RLS.

## 5. Installation guidée

Installation locale :

```bash
bash scripts/bootstrap.sh
```

Préparation du staging :

```bash
bash scripts/bootstrap.sh --staging
```

Le script prépare un fichier de secrets s'il n'existe pas, génère la configuration Keycloak et un fichier d'environnement runtime limité aux variables applicatives, démarre les conteneurs, attend `/ready`, puis enregistre la baseline via le service ponctuel `migrator`. En staging, il utilise un projet Compose, des ports et des volumes séparés (`cfdt-juris-staging`, API 18000, Keycloak 18081).

Le staging nécessite un reverse proxy HTTPS et des DNS valides pour les domaines définis dans `.env.staging`. Le compose de staging n'est pas à lui seul un reverse proxy Internet.

## 6. Supervision et alertes

Créer la configuration locale Alertmanager à partir du modèle :

```bash
cp deploy/monitoring/alertmanager.yml.example deploy/monitoring/alertmanager.yml
```

Modifier le serveur SMTP, l'expéditeur, le compte et le destinataire. Ne pas committer le fichier rempli.

Pour un déploiement local/prod dont le projet Compose s'appelle `cfdt-juris` :

```bash
docker compose -p cfdt-juris --env-file .env \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.monitoring.yml \
  --profile monitoring up -d
```

Composants :

- Blackbox Exporter : sonde `/ready` de l'API et `/health/ready` de Keycloak ;
- PostgreSQL Exporter : métriques PostgreSQL via un rôle `cfdt_juris_monitor` membre de `pg_monitor` ;
- Prometheus : collecte et règles d'alerte ;
- Alertmanager : notifications e-mail configurées par SMTP ;
- Grafana : datasource Prometheus préconfigurée et tableau de bord `CFDT JURIS — Supervision` provisionné.

Les interfaces Prometheus, Alertmanager et Grafana sont liées à `127.0.0.1`. Y accéder par tunnel SSH/VPN, ne pas les exposer directement sur Internet. Les alertes e-mail ne sont opérationnelles qu'après configuration du SMTP dans `alertmanager.yml`. Pour le staging, reprendre la même commande avec `-p cfdt-juris-staging --env-file .env.staging` ; le nom de projet distinct garantit des volumes de supervision séparés.

Sur une base PostgreSQL déjà existante, les scripts `docker-entrypoint-initdb.d` ne sont pas rejoués automatiquement. Le script `scripts/ensure_operational_roles.sh` crée ou met à jour de façon idempotente les rôles d'ingestion et de supervision ; les workflows de déploiement et le bootstrap l'exécutent. Pour un lancement manuel :

```bash
ENV_FILE=.env COMPOSE_PROJECT_NAME=cfdt-juris scripts/ensure_operational_roles.sh
```

## 7. Préproduction et recette obligatoire avant ouverture

La CI exécute des tests RLS réels sur PostgreSQL. Elle ne valide pas à elle seule les identifiants PISTE, Stripe, SMTP, les domaines publics ou les certificats TLS du futur hébergeur.

Recette staging à effectuer manuellement :

1. login/logout Keycloak avec un compte test de chaque organisation ;
2. invitation et révocation d'un utilisateur ;
3. preuve qu'un utilisateur du syndicat A ne peut lire/écrire aucune donnée du syndicat B ;
4. parcours Stripe en mode test et traitement des webhooks signés ;
5. appel PISTE sandbox, gestion des quotas et des erreurs ;
6. import juridique et contrôle de provenance/version ;
7. test de sauvegarde puis restauration sur une base isolée ;
8. vérification des alertes e-mail et de la reprise après redémarrage.

**La V3.22 améliore l'industrialisation ; elle ne constitue pas une certification de sécurité ni une validation de production.** La mise en production reste conditionnée à la recette staging et à la revue des secrets, du réseau, des sauvegardes et des droits.
