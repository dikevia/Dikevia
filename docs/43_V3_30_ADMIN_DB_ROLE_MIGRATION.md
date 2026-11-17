# V3.30 — Migration vers le rôle PostgreSQL administrateur dédié

## Objectif

À partir de la migration 016, les opérations d'administration plateforme (lecture globale des organisations, suspension, approbation des membres privés et gestion des accès gratuits) ne sont plus exécutables avec les identifiants PostgreSQL ordinaires de l'API.

Trois connexions distinctes sont utilisées :

- `cfdt_juris_app` : API courante et accès tenant.
- `cfdt_juris_ingest` : ingestion du corpus juridique.
- `cfdt_juris_platform_admin` : fonctions et écritures d'administration plateforme uniquement.

Le rôle administrateur n'est ni superutilisateur, ni propriétaire des tables, ni titulaire de BYPASSRLS.

## Installation neuve avec Docker Compose

Le rôle est créé automatiquement au premier démarrage de PostgreSQL par :

`deploy/init/04-create-platform-admin-role.sh`

Le fichier `.env` doit contenir `POSTGRES_PLATFORM_ADMIN_PASSWORD` et `PLATFORM_ADMIN_DATABASE_URL`. Utiliser `python scripts/prepare_dev_env.py` pour générer les secrets.

## Base Docker existante

Les scripts d'initialisation PostgreSQL ne sont pas rejoués sur un volume déjà initialisé. Après avoir mis à niveau le fichier `.env` avec `python scripts/upgrade_env_file.py`, exécuter :

```bash
docker compose --env-file .env exec db bash /docker-entrypoint-initdb.d/04-create-platform-admin-role.sh
```

Puis mettre à niveau le registre des migrations avec le compte de migration :

```bash
docker compose --env-file .env run --rm migrator python /srv/scripts/db_migrate.py upgrade
```

Enfin régénérer le fichier d'environnement de l'API et redémarrer le service :

```bash
python scripts/render_runtime_env.py --source .env --output .env.runtime
docker compose --env-file .env up -d api
```

## PostgreSQL managé (ex. Neon)

1. Générer un secret aléatoire dédié et le conserver dans le gestionnaire de secrets.
2. Dans le SQL Editor de la base concernée, créer le rôle de connexion `cfdt_juris_platform_admin` avec ce secret, les attributs `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS`, puis lui accorder uniquement `CONNECT` sur la base et `USAGE` sur le schéma `public`.
3. Définir `PLATFORM_ADMIN_DATABASE_URL` avec ce rôle et ce secret dans l'environnement serveur de l'API.
4. Exécuter la migration 016 avec le compte de migration propriétaire des objets, jamais avec le compte runtime.
5. Vérifier que l'API démarre avec les trois connexions et que les tests de droits runtime/admin passent.

Ne jamais utiliser le compte propriétaire de la base comme `PLATFORM_ADMIN_DATABASE_URL`. Ne pas exécuter ces étapes sur une base de production sans sauvegarde vérifiée et procédure de retour arrière.

## Contrôles automatisés

La CI crée les trois rôles, applique les migrations jusqu'à 016 et vérifie que le rôle runtime reçoit une erreur `InsufficientPrivilege` lorsqu'il tente d'appeler les fonctions d'administration des membres privés. Le rôle dédié doit, lui, pouvoir les appeler après vérification OIDC par l'API.
