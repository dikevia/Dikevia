# Runbook exploitation — sauvegarde, restauration, santé et livraison

## Pré-requis

- Docker Engine et Docker Compose v2 sur l'hôte.
- Dépôt cloné sur l'hôte de déploiement.
- `.env` à la racine, créé à partir de `deploy/.env.example`, protégé (`chmod 600 .env`).
- Secrets uniques et forts ; TLS terminé par un reverse proxy correctement configuré.
- Répertoire de sauvegarde sur un volume distinct si possible.

## Configuration

```bash
cp deploy/.env.example .env
chmod 600 .env
# Renseigner tous les secrets et URL adaptés à l'environnement.
set -a; . ./.env; set +a
python scripts/render_keycloak_config.py
```

Ne jamais committer `.env`, les exports SQL, les clés PISTE, les secrets Keycloak ou les clés LLM. Stocker les secrets de production dans un gestionnaire de secrets lorsque disponible.

## Déploiement manuel

```bash
docker compose --env-file .env -f deploy/docker-compose.yml config --quiet
docker compose --env-file .env -f deploy/docker-compose.yml build api
docker compose --env-file .env -f deploy/docker-compose.yml up -d
docker compose --env-file .env -f deploy/docker-compose.yml ps
./scripts/check_health.sh https://juris.example.org
```

`/health` est une sonde de vie du processus. `/ready` vérifie la connexion PostgreSQL et renvoie 503 si la base n'est pas disponible. Le healthcheck Compose de l'API utilise `/ready`. Le statut `healthy` ne remplace pas une vérification des services externes (IdP, PISTE, fournisseur IA, SMTP, Stripe).

## Sauvegarde PostgreSQL

Depuis la racine du dépôt :

```bash
BACKUP_DIR=/srv/backups/cfdt-juris ./scripts/backup_postgres.sh
```

Le script produit un dump PostgreSQL custom-format et un fichier SHA-256. Le dump contient des données potentiellement personnelles : accès restreint, chiffrement au repos et transfert chiffré hors hôte sont obligatoires pour la production. La rétention, le chiffrement, la copie distante et la surveillance des échecs doivent être configurés au niveau de l'infrastructure. La sauvegarde PostgreSQL ne couvre pas les fichiers du volume `document_data` ni les données Keycloak ; les sauvegarder séparément avec une procédure cohérente.

## Restauration — opération destructive

Effectuer d'abord une sauvegarde de l'état actuel, isoler le service applicatif et valider l'intégrité du dump. Puis :

```bash
docker compose --env-file .env -f deploy/docker-compose.yml stop api
./scripts/restore_postgres.sh /srv/backups/cfdt-juris/cfdt_juris_YYYYMMDDTHHMMSSZ.dump
docker compose --env-file .env -f deploy/docker-compose.yml up -d api
./scripts/check_health.sh http://127.0.0.1:8000
```

Le script demande de saisir `RESTORE`, puis détruit/recrée la base cible. N'utiliser que sur la bonne instance, après vérification du fichier et de son empreinte. La restauration peut nécessiter de réappliquer les droits runtime (`database/grant_runtime_permissions.sql`) et de vérifier les extensions, rôles et propriétaires. Effectuer un test de connexion, un contrôle des organisations, un contrôle des documents et les tests d'isolation multi-tenant après restauration.

Les documents et la base doivent être sauvegardés/restaurés de façon coordonnée ; sinon les métadonnées peuvent pointer vers des fichiers absents ou inversement. Prévoir également une sauvegarde/restauration de la base Keycloak pour préserver les comptes et configurations.

## CI et déploiement continu

- `.github/workflows/ci.yml` : compilation, Ruff, Bandit, pip-audit, tests, validation shell et configuration Compose sur push/PR.
- `.github/workflows/deploy.yml` : déploiement de production manuel uniquement, après saisie de `DEPLOY`. Configurer dans GitHub Environment `production` les secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH` et éventuellement `DEPLOY_PORT`. L'utilisateur SSH doit être limité au strict nécessaire pour le répertoire et Docker. Protéger la branche `main`, exiger la réussite de CI et une approbation d'environnement avant déploiement.

Ce pipeline est un modèle d'intégration. Il doit être adapté à l'hébergeur, aux stratégies de migration et au mécanisme de rollback avant usage réel. Il ne lance pas de migrations automatiquement, par prudence.

## Exercices de reprise

Au minimum chaque trimestre : restaurer une sauvegarde sur un environnement isolé, vérifier les données et les documents, exécuter les tests RLS avec un rôle runtime non privilégié, mesurer le temps de reprise et consigner le résultat. Une sauvegarde non restaurée/testée n'est pas une stratégie de reprise validée.
