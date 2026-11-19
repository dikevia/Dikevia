# Dikevia — Kit développeur V3.38.5

La V3.30 renforce le moteur juridique : import préparé du CGFP, recherche des textes réglementaires complémentaires sur Légifrance et interrogation sécurisée des documents propres à l’employeur.

## Diagnostics externes au démarrage

Les diagnostics Légifrance/PISTE et la vérification du catalogue du fournisseur IA sont **désactivés par défaut**. Ils ne sont lancés en production que si la variable `ENABLE_EXTERNAL_STARTUP_DIAGNOSTICS=true` est explicitement définie. Ces contrôles peuvent consommer des quotas d'API ou entraîner des coûts selon les fournisseurs ; laissez cette option désactivée pour la bêta privée et tout environnement soumis à une contrainte de dépense nulle.

## État réel de cette livraison
- Code FastAPI versionné `3.38.5`.
- Console plateforme : annuaire des syndicats, création d’espaces, attribution d’accès offerts, suspension et réactivation journalisées.
- Validation de JWT OIDC via JWKS, issuer, audience, expiration et algorithmes configurés.
- Appartenance active vérifiée en base pour chaque requête tenant.
- En-tête `X-Organization-ID` traité comme une sélection non fiable et vérifié contre l'adhésion.
- `SET LOCAL` via `set_config(..., true)` dans la transaction de requête.
- Migration PostgreSQL avec RLS et FORCE RLS sur les tables privées.
- Création d’organisation réservée au registre `platform_admins`.
- Invitations à jeton aléatoire à usage unique, stocké sous forme de SHA-256 et lié à l’e-mail OIDC vérifié.
- Acceptation d’invitation transactionnelle et journalisée.
- Conversations persistées dans PostgreSQL, privées à l’utilisateur OIDC et à l’organisation active via RLS FORCE.
- Le CGFP constitue la référence nationale de base de Dikevia. Son index article/page alimente le contexte du chat ; le snapshot seul ne suffit jamais à certifier la version applicable. Les textes officiels Légifrance/PISTE contrôlent la rédaction et la temporalité des dispositions.

Le dossier de transfert développeur, avec les seules opérations restantes côté environnement, est décrit dans `docs/39_LIVRAISON_DEVELOPPEUR_V3_30.md`.

Cette livraison n'est pas certifiée production. Le démarrage local est préparé pour une base neuve, mais l'identité du premier administrateur, les identifiants PISTE, le fournisseur IA, les tests d'isolation sur PostgreSQL réel et la recette de sécurité restent à configurer et tester dans l'environnement de déploiement.

## Installation locale
Depuis `backend/` :
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=.
uvicorn app.main:app --reload
```
Sans `DATABASE_URL` et paramètres OIDC, les endpoints privés échouent volontairement en 503 ; `/health` reste disponible.

## Migration
Pour une installation neuve, `database/schema.sql` fournit le baseline jusqu’à la V3.21 (migration 009), puis appliquer les migrations 010 à 018 dans l'ordre. Pour une base existante, appliquer uniquement les migrations manquantes dans l'ordre : `001_initial_multi_tenant.sql` à `018_ai_usage_metering.sql` (créer le rôle `cfdt_juris_ingest` avant la migration 009, puis `cfdt_juris_platform_admin` avant la migration 016), avec un rôle de migration distinct. Créer les rôles runtime, ingestion et administrateur plateforme avec `deploy/init/01-create-app-role.sh`, `deploy/init/02-create-corpus-ingest-role.sh` et `deploy/init/04-create-platform-admin-role.sh`, puis exécuter `database/grant_runtime_permissions.sql` comme DBA après les migrations. La migration 018 ajoute le journal de consommation IA ; le rôle runtime peut seulement y insérer des compteurs sans contenu conversationnel. Les migrations 010, 011, 012 et 013 ajoutent leurs propres droits applicatifs. Provisionner le premier administrateur plateforme hors API avec `database/bootstrap_platform_admin.sql`. Les rôles runtime, ingestion et administrateur plateforme ne sont pas propriétaires des tables et n’ont ni `SUPERUSER` ni `BYPASSRLS`. Le rôle API est en lecture seule sur le corpus national ; seul le pool d’ingestion séparé peut l’alimenter. Les opérations transversales de plateforme utilisent `PLATFORM_ADMIN_DATABASE_URL` avec le rôle restreint `cfdt_juris_platform_admin`. Ne jamais utiliser le compte de migration comme compte API.

Pour une instance privée, appliquer aussi la migration `015_private_instance_10_seats.sql` après la 014, puis la migration `016_platform_admin_database_role.sql`. Elle refuse désormais une base qui contient déjà plusieurs organisations : examiner et isoler les données avant de relancer. Pour une base existante, le rôle `cfdt_juris_platform_admin` doit être créé avant la migration 016. Suivre `docs/40_INSTANCE_PRIVEE_10_COMPTES.md` et `docs/43_V3_30_ADMIN_DB_ROLE_MIGRATION.md` pour l'ordre de recette et l'activation du paramètre privé.

## Variables
Copier `deploy/.env.example` vers `.env` à la racine du projet, ou utiliser `bash scripts/bootstrap.sh`. Renseigner les paramètres OIDC et les secrets fournisseurs. Docker Compose lit `.env` pour l'infrastructure ; `scripts/render_runtime_env.py` génère `.env.runtime`, transmis à l'API avec les champs applicatifs et les URL des trois pools PostgreSQL (runtime, ingestion et administration restreinte). Les secrets DBA, Keycloak DB, Grafana et supervision ne sont pas exposés au conteneur API. Ne jamais committer les fichiers `.env*` générés.

## Tests
```bash
cd backend
PYTHONPATH=. pytest -q
```
La CI V3.30 exécute la suite complète sur PostgreSQL 16 éphémère. Dernier résultat validé : **187 tests réussis, aucun échec** ; voir `docs/42_V3_30_PREUVE_VALIDATION_CI.md`. Les tests OIDC avec un IdP réel, les tests de révocation, les tests de concurrence des invitations et la recette de restauration restent à réaliser en staging. Les fonctions SQL `SECURITY DEFINER` d'administration sont réservées au rôle `cfdt_juris_platform_admin` distinct du rôle runtime.


## V3.2 — renforcement RLS du registre d'identité

La migration `database/migrations/003_global_identity_rls.sql` active RLS et FORCE RLS sur `users` et `platform_admins`. Le rôle runtime ne peut consulter que l'identité OIDC correspondant au contexte établi côté serveur. Les hashes d'invitation deviennent uniques.

### Ordre des migrations

1. `database/migrations/001_initial_multi_tenant.sql`
2. `database/migrations/002_v31_invitations.sql`
3. `database/migrations/003_global_identity_rls.sql`
4. `database/grant_runtime_permissions.sql` (à exécuter par le rôle DBA après les migrations)

### Tests PostgreSQL réels

Les tests `backend/tests/test_postgres_rls_integration.py` vérifient avec deux organisations que les documents d'un autre espace sont invisibles, qu'une écriture avec un `organization_id` falsifié est rejetée, que le registre d'identité est limité à l'identité authentifiée et que le hash d'invitation n'ouvre qu'une invitation. Ils nécessitent une base PostgreSQL de test jetable, les migrations ci-dessus et deux URL : `TEST_DATABASE_ADMIN_URL` (rôle DBA/superuser de test) et `TEST_DATABASE_URL` (rôle runtime `cfdt_juris_app`).

Exécution : `./scripts/run_postgres_security_tests.sh`. Si ces variables ne sont pas définies, le test d'intégration est ignoré. Les tests statiques ne remplacent pas ce test réel.

Dans GitHub Actions, le workflow crée sa propre base PostgreSQL éphémère, applique le schéma et les migrations, puis fournit ces deux URL locales au test. Aucun secret GitHub ni URL Neon n'est nécessaire pour la CI.


`database/schema.sql` est le schéma consolidé de référence pour une installation neuve. Pour une base déjà créée en V3/V3.1, appliquer uniquement les migrations 002 puis 003 qui manquent ; ne pas rejouer le schéma consolidé par-dessus une base existante.


## V3.3 — Gestion documentaire
Appliquer `database/migrations/004_document_management.sql` après les migrations 001 à 003, puis exécuter `database/grant_runtime_permissions.sql` en DBA pour appliquer les droits. Configurer `DOCUMENT_STORAGE_PATH` (par défaut `/var/lib/cfdt-juris/documents`) et monter un volume privé persistant. L'API accepte les PDF et DOCX jusqu'à 20 Mo par défaut.

Les routes de gestion documentaire sont décrites dans `docs/14_V3_3_DOCUMENT_MANAGEMENT.md`. Les fichiers sont accessibles uniquement par les routes authentifiées et cloisonnées par organisation. Dans la livraison V3.3 seule, la vérification de format ne constituait pas un antivirus ; le lot V3.4 ajoute le contrôle ClamAV et l'indexation plein texte.


## V3.4 — antivirus et recherche documentaire
Appliquer `database/migrations/005_document_scanning_and_search.sql` après 001 à 004, puis réexécuter `database/grant_runtime_permissions.sql` en DBA. Le service Docker Compose `clamav` est obligatoire : les imports échouent en mode fermé si le scanner n'est pas joignable. Les fichiers importés ne sont téléchargeables qu'après un résultat antivirus `CLEAN`.

Le texte PDF/DOCX est extrait et stocké dans `document_text`, avec RLS/FORCE RLS et index plein texte français. La route `GET /api/v1/documents/search?q=...` effectue une recherche dans l'espace courant. L'OCR n'est pas inclus ; les documents scannés sans couche texte sont signalés `NO_TEXT`. Les versions historiques peuvent être réindexées via `POST /api/v1/documents/{id}/reindex`, après scan `CLEAN`. Les résultats ne sont pas automatiquement considérés comme juridiquement applicables et ne sont pas encore injectés dans le moteur IA.

### V3.5 — Préparation sécurisée de l'environnement

Le démarrage valide maintenant la configuration. En `APP_ENV=production`, il faut obligatoirement renseigner `DATABASE_URL`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` et `CORS_ORIGINS`. Les URL OIDC et les origines CORS doivent être en HTTPS ; `CORS_ORIGINS` doit contenir les origines exactes autorisées, séparées par des virgules (jamais `*`). Les algorithmes acceptés sont RS256 et ES256.

`GET /health` vérifie uniquement que le processus répond. `GET /ready` vérifie aussi l'accès à PostgreSQL et renvoie HTTP 503 si la base est indisponible. En production, les routes de documentation OpenAPI sont désactivées.

Avant une mise en production, il reste nécessaire de configurer le fournisseur OIDC réel, de vérifier ses claims et son JWKS, d'appliquer les migrations PostgreSQL et de réaliser les tests d'intégration dans l'environnement cible.

## Interface utilisateur V3.6
Le dossier `frontend/` contient désormais l'espace de travail responsive et le module OIDC navigateur PKCE. Avant connexion, renseigner `frontend/auth-config.js` à partir du modèle `frontend/auth-config.example.js`. Consulter `docs/16_V3_6_USER_WORKSPACE.md` pour le raccordement et les tests obligatoires. Le fichier `auth-config.js` réel n'est volontairement pas livré.

## V3.7 — Fournisseur d'identité Keycloak
La V3.7 ajoute un déploiement Keycloak 26.8.2 avec base PostgreSQL dédiée, import du realm `cfdt`, client navigateur public `cfdt-juris-web` en Authorization Code + PKCE S256 et audience `cfdt-juris-api` pour l'API. Les appartenances et rôles métier restent gérés par PostgreSQL et les contrôles API existants.

Avant `docker compose up`, copier `.env.example` en `.env`, remplacer tous les secrets `CHANGE_ME_*`, puis exécuter `set -a; . ./.env; set +a; python scripts/render_keycloak_config.py`. Ce script génère le realm à importer et le fichier OIDC du navigateur selon `KEYCLOAK_PUBLIC_URL` et `PUBLIC_APP_URL`. La procédure complète, le reverse proxy et les limites sont dans `docs/17_V3_7_KEYCLOAK.md`.

La version V3.7 fournit la configuration et les fichiers d'intégration ; elle n'a pas été démarrée avec Docker dans l'environnement de génération. Les essais Keycloak réels, SMTP, provisionnement et parcours de connexion doivent être réalisés dans l'environnement de déploiement.

## V3.8 — Invitations automatisées
Voir `docs/18_V3_8_INVITATIONS_AND_ROLES.md`. Pour activer l'envoi automatique, configurer le client de service Keycloak (rôle `manage-users` uniquement), son secret, le SMTP applicatif et `INVITATION_BASE_URL`. Configurer également le SMTP de Keycloak pour la vérification des adresses et les actions de mot de passe. Sans ces paramètres, le flux manuel sécurisé reste disponible.


Historique des évolutions : voir `CHANGELOG_V3.md` ; dernière livraison : **V3.30**. Voir `docs/19_V3_9_INVITATION_INTEGRITY.md`.

## V3.10 — Corpus national : Code général de la fonction publique
Le kit contient désormais `corpus_national/legislation/CGFP_snapshot_2026-10-31.pdf`, copie du PDF transmis pour le projet (1 024 pages ; dernière modification indiquée : 31/10/2026 ; génération : 13/11/2026). Les métadonnées et règles d'exploitation figurent dans le fichier `.metadata.json` associé et dans `docs/20_CORPUS_NATIONAL_CGFP.md`.

**État à la livraison V3.10 :** le PDF était fourni comme source documentaire à ingérer, sans chargement dans une base active. La V3.30 ajoute le script d'import article par article, mais aucun import dans la base de production n'est revendiqué ici. Le snapshot ne constitue pas une vérification historique des textes ; la version applicable à la date des faits doit être contrôlée sur les sources officielles.

### V3.11 — recherche dans le CGFP
Le backend embarque désormais un index article/page du snapshot CGFP. La recherche est disponible via `GET /api/v1/legal/cgfp/search?q=...` et intégrée à `POST /api/v1/chat/ask`. Les résultats citent l'article et les pages du PDF. Ils restent des pistes documentaires `PARTIELLEMENT_VERIFIE` : aucune vérification de version historique ni connexion Légifrance n'est incluse.

Pour reconstruire l'index après remplacement du PDF : `python scripts/build_cgfp_index.py`.


### V3.12 — Recherche CGFP améliorée et consultation d'article
La recherche utilise désormais un classement lexical BM25 (fréquence des termes et rareté dans le corpus), avec prise en compte des expressions et des références exactes. Deux routes authentifiées supplémentaires permettent de consulter les métadonnées du snapshot (`GET /api/v1/legal/cgfp/source`) et le texte intégral extrait d'un article (`GET /api/v1/legal/cgfp/articles/{article_ref}`). La route de recherche contrôle aussi la limite de résultats.

Les résultats restent documentaires : l'API ne certifie ni la version en vigueur à la date des faits, ni la complétude des textes d'application. La vérification officielle Légifrance/PISTE reste le prochain lot.


### V3.13 — Contrôle déterministe de l'intégrité des citations CGFP

- Chaque citation issue du moteur est contrôlée côté serveur : identifiant de source, référence d'article, pages PDF et présence exacte de l'extrait dans le texte intégral indexé.
- Une citation qui échoue à l'un des contrôles est écartée. Si aucune citation ne passe, la réponse est `NON_VERIFIE`.
- La date des faits est désormais interprétée strictement au format ISO `AAAA-MM-JJ` ; une date ambiguë ne déclenche pas d'analyse.
- Le contrôle indique explicitement son périmètre : intégrité du snapshot uniquement. Il ne certifie ni l'authenticité officielle ni l'applicabilité historique.

Cette version ne comprend toujours pas le connecteur Légifrance/PISTE ni un modèle IA connecté.


### V3.14 — Analyse assistée par IA (facultative)
Un adaptateur serveur compatible OpenAI Chat Completions est disponible. Configurer `AI_API_BASE_URL`, `AI_API_KEY` et `AI_MODEL` dans `.env`. Sans configuration, le service conserve le mode documentaire. Seuls les extraits CGFP dont les citations ont passé les contrôles backend sont transmis au modèle. Les références affichées restent issues du backend. Le statut reste `PARTIELLEMENT_VERIFIE` : le modèle ne vérifie pas les versions historiques ni les sources locales. Voir `docs/21_V3_14_ASSISTED_ANALYSIS.md`.

## V3.15 — Connecteur PISTE et installation locale

Le kit contient désormais un connecteur OAuth2 PISTE/Légifrance fondé sur les exemples officiels de la FAQ DILA. Configurer les variables `LEGIFRANCE_*` dans `.env` pour activer la recherche du CGFP à la date demandée. Routes de diagnostic : `GET /api/v1/integrations/legifrance/status`, `POST /api/v1/integrations/legifrance/check`, et `GET /api/v1/legal/legifrance/search`.

Pour une installation locale neuve : `python scripts/prepare_dev_env.py`, puis `docker compose -f deploy/docker-compose.yml up --build -d`. PostgreSQL applique automatiquement le schéma consolidé et les droits minimaux uniquement à la création d'un volume neuf. Ne pas utiliser cette initialisation pour une base existante.

Voir `docs/22_V3_15_PISTE_AND_LOCAL_RUN.md` pour les conditions PISTE, les limites, les tests et les étapes restantes. L'application n'est pas certifiée production : identifiants PISTE, IA, corpus territorial, jurisprudence, tests réels et validation sécurité restent à traiter.

## V3.16 — Recherche de jurisprudence administrative

La recherche juridique interroge désormais également le fonds `CETAT` de Légifrance, avec un filtre de date et une liste de résultats identifiés. Les résultats sont affichés comme pistes documentaires ; le texte intégral des décisions n'est pas encore récupéré et ces résultats ne sont pas injectés dans l'analyse IA. Voir `docs/23_V3_16_ADMINISTRATIVE_CASELAW.md`.


## V3.17 — Abonnements et commercialisation
La V3.17 ajoute les offres `ESSENTIAL_3` (15 €/mois, 3 utilisateurs), `SYNDICAT_10` (50 €/mois, 10 utilisateurs) et `FOUNDING_FREE` (accès offert attribué par l'administrateur plateforme, 10 utilisateurs). Le backend propose Stripe Checkout, le portail client, un webhook signé et idempotent, la consultation de formule et le contrôle des plafonds avant invitation. L'interface dispose d'une rubrique Abonnement.

Pour une base V3.16 existante, appliquer `database/migrations/007_saas_billing.sql`, puis réexécuter `database/grant_runtime_permissions.sql` en DBA. Pour une base neuve, `database/schema.sql` est à jour. Configurer `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `BILLING_SUCCESS_URL` et `BILLING_CANCEL_URL` dans `.env`. La procédure de recette et les événements webhook à activer sont décrits dans `docs/24_V3_17_SAAS_BILLING.md`.

**Attention :** cette livraison constitue une base de facturation SaaS, pas une certification de production. Les paiements et webhooks doivent être testés en mode Stripe test, et les obligations fiscales, contractuelles, RGPD et de facturation doivent être validées avant la commercialisation.

## Parcours de mise en service
Consulter `docs/25_GO_LIVE_CHECKLIST.md` pour les étapes d'installation, de migration, de configuration Stripe, de recette et les conditions avant commercialisation. Ne pas considérer le projet comme prêt pour une ouverture publique tant que la recette réelle PostgreSQL, Keycloak, ClamAV, Stripe, sauvegarde/restauration et la validation RGPD/contractuelle ne sont pas achevées.


## V3.18 — Console d'administration plateforme

La V3.18 ajoute une console réservée aux administrateurs plateforme : annuaire des organisations, création d'espaces, attribution d'accès offerts et suspension/réactivation. Les opérations transversales de lecture et de changement d'état passent par deux fonctions SQL `SECURITY DEFINER` à périmètre étroit, qui vérifient à nouveau le registre `platform_admins`. Leur propriétaire doit être le rôle DBA/BYPASSRLS de migration ; le rôle applicatif reçoit uniquement `EXECUTE`.

Pour une base existante V3.17, appliquer `database/migrations/008_platform_admin_console.sql` avec le rôle `cfdt_migration` (qui doit avoir `BYPASSRLS`), puis redémarrer l'API. Pour une nouvelle installation, les fonctions sont incluses dans `database/schema.sql`. La console est visible uniquement pour les identités inscrites dans `platform_admins`.

## V3.19 — Consultation du texte intégral des décisions administratives

La recherche CETAT conserve son statut de résultat de recherche : métadonnées et extraits éventuels ne sont jamais présentés comme un arrêt intégral. Une nouvelle méthode de consultation appelle l'API Légifrance/PISTE `POST /consult/juri` avec l'identifiant officiel de décision (`textId`). Le backend ne marque le texte comme intégral que si la réponse contient un identifiant correspondant exactement à celui demandé et un contenu textuel substantiel. Les identifiants CETATEXT et JURITEXT sont acceptés par le validateur ; les identifiants mal formés ou les réponses sans correspondance sont rejetés.

Nouvelle route authentifiée et limitée à l'organisation courante : `GET /api/v1/legal/jurisprudence/administrative/{decision_id}`. Elle renvoie `TEXTE_INTEGRAL_OFFICIEL_ID_VERIFIE` lorsque la consultation passe les contrôles techniques. Ce statut ne signifie pas que la portée de l'arrêt, son éventuel revirement, son caractère définitif ou l'état actuel du droit ont été analysés. L'absence de résultat reste non concluante. Aucun texte n'est encore persisté dans une base de jurisprudence ni automatiquement injecté dans l'IA.

Recette V3.19 : `PYTHONPATH=backend pytest -q backend/tests/test_administrative_jurisprudence.py backend/tests/test_legifrance_connector.py`. Les tests utilisent un transport HTTP simulé ; la connexion PISTE réelle, les identifiants de production et les quotas doivent être validés dans l'environnement de déploiement.


## V3.20 — Industrialisation et exploitation

Cette livraison ajoute :
- CI GitHub Actions : compilation, Ruff, Bandit, audit des dépendances, tests, validation shell et Docker Compose (`.github/workflows/ci.yml`).
- Déploiement de production manuel et protégé par confirmation (`.github/workflows/deploy.yml`), à configurer avec les secrets GitHub de l'hébergeur.
- Sonde Docker de disponibilité API basée sur `/ready` ; `/health` reste la sonde de vie.
- Scripts de sauvegarde/restauration PostgreSQL (`scripts/backup_postgres.sh`, `scripts/restore_postgres.sh`) et contrôle de santé (`scripts/check_health.sh`).
- Guide utilisateur (`docs/28_USER_GUIDE.md`), manuel administrateur (`docs/29_ADMIN_GUIDE.md`) et runbook d'exploitation (`docs/30_OPERATIONS_RUNBOOK.md`).

Le fichier `deploy/.env.example` existait déjà en V3.19 et documente les variables de configuration connues. Le compléter avec les valeurs de l'environnement réel, ne jamais versionner `.env` et ne jamais mettre de secrets dans le dépôt. Les sauvegardes produites par les scripts contiennent des données potentiellement personnelles : chiffrer et transférer vers un stockage distant protégé. La base PostgreSQL ne sauvegarde pas les volumes documentaires ni Keycloak.

La CI doit être exécutée sur GitHub avant fusion. Le workflow de déploiement est un modèle SSH manuel, non activé tant que les secrets, l'environnement protégé, l'accès serveur et la procédure de retour arrière ne sont pas configurés. Les migrations DB restent manuelles dans cette livraison. Aucun déploiement réel ni test de restauration sur infrastructure de production n'est revendiqué.


## V3.21 — Référentiel juridique permanent

La V3.21 ajoute un corpus national commun aux organisations : textes LEGI/LODA consultés via PISTE, jurisprudence administrative CETAT consultée en texte intégral lorsque possible, métadonnées CIRCULAIRES importées depuis XML DILA, historique des versions, empreintes SHA-256, recherche plein texte et liens vers les sources officielles. Voir `docs/31_V3_21_PERMANENT_LEGAL_KNOWLEDGE.md`.

Le corpus national est partagé et en lecture seule pour le rôle API. Les imports utilisent un rôle PostgreSQL dédié (`cfdt_juris_ingest`) et la variable `LEGAL_CORPUS_INGEST_DATABASE_URL`. Les imports CIRCULAIRES sont explicitement marqués `IMPORTED_UNVERIFIED` tant que l'origine et l'exhaustivité du fichier n'ont pas été contrôlées. Les sources dont le texte ou la temporalité ne sont pas suffisamment vérifiés sont exclues du contexte IA.


## V3.22 — Industrialisation, staging et migrations PostgreSQL

La V3.22 prend la V3.21 comme base et ajoute : registre PostgreSQL `schema_migrations` avec checksums et verrou advisory ; baseline détectée V8 (base V3.20) ou V9 (base V3.21) ; rollback explicite et limité aux migrations munies d'un `down.sql` ; test RLS réel configuré dans la CI avec un service PostgreSQL ; audit automatique des variables `Settings` par rapport à `.env.example` ; génération d'un `.env.runtime` de moindre privilège (le conteneur API ne reçoit pas les mots de passe DBA/Keycloak DB/Grafana) ; script d'installation `scripts/bootstrap.sh` ; environnement staging isolé par nom de projet Compose et ports dédiés ; supervision optionnelle Prometheus, Blackbox Exporter, PostgreSQL Exporter, Alertmanager et Grafana.

Pour une nouvelle installation locale : `bash scripts/bootstrap.sh`. Pour initialiser le staging : `bash scripts/bootstrap.sh --staging`, puis remplacer les domaines `example.org` et renseigner les identifiants PISTE sandbox/Stripe test dans `.env.staging`. Pour mettre à niveau une configuration existante : `python3 scripts/upgrade_env_file.py` (ou `--staging`) après avoir renseigné `COMPOSE_PROJECT_NAME` avec le nom exact du projet existant afin de conserver les volumes PostgreSQL. Les migrations doivent être appliquées avec `scripts/upgrade_with_backup.sh`, qui sauvegarde PostgreSQL avant de lancer le service ponctuel `migrator`. Voir `docs/32_V3_22_PRODUCTION_READINESS.md`.

Limites : l'environnement de travail courant ne possède pas Docker ni un serveur PostgreSQL, donc la validation Docker Compose et le test RLS réel doivent être exécutés par la CI ou sur un hôte de recette. Les tests Python locaux ne remplacent pas la recette staging, le test de restauration, la vérification des webhooks Stripe/PISTE, ni un audit de sécurité indépendant.


## V3.23 — Tarification TTC et accès gratuits individuels

Le catalogue public est désormais : 15 € TTC/mois pour 1 utilisateur, 80 € TTC/mois pour 10 utilisateurs et 300 € TTC/mois pour 50 utilisateurs. Les anciens contrats sont conservés sous des codes `LEGACY_*` afin de ne pas modifier leur quota ni leur prix Stripe existant. L'administrateur plateforme peut gérer une liste d'adresses e-mail gratuites ; ces personnes ne consomment pas de place payante, mais doivent toujours être invitées dans l'espace syndical concerné. Stripe Checkout utilise des montants en centimes, un comportement fiscal inclusif et Stripe Tax. La configuration fiscale de l'entreprise doit être finalisée dans Stripe avant la mise en production. Voir `docs/32_V3_23_TARIFICATION_TTC_ET_ACCES_GRATUITS.md`.


## V3.24 — Espace commercial et client
- Console commerciale réservée aux administrateurs plateforme : chiffre d'affaires encaissé mensuel, abonnements actifs/en impayé, organisations, licences payantes utilisées/capacité et accès gratuits.
- Suivi des organisations clientes avec séparation des licences payantes, utilisateurs gratuits et invitations en attente.
- Registre de factures alimenté par les événements Stripe `invoice.*`, avec montants dus, encaissés, restants, échéances, statuts et liens de facture/PDF.
- Historique des factures visible dans l'espace de facturation du syndicat courant uniquement.
- Les événements de facturation sont idempotents via le registre webhook ; les écritures de factures sont protégées par une variable de transaction activée uniquement après validation de la signature Stripe.
- Migration `011_commercial_customer_console.sql` et rollback associé.
- Limites : les factures antérieures à l'activation de cette version ne sont pas importées automatiquement ; le tableau de bord ne montre que les factures reçues via webhook après migration. Les paiements réels, événements Stripe et droits d'accès doivent être testés en préproduction. Le chiffre d'affaires présenté est le montant encaissé déclaré par Stripe, pas une comptabilité certifiée.


## V3.25 — Sécurité et validation de production

Voir `docs/33_V3_25_PRODUCTION_SECURITY.md` : audit bloquant des secrets et variables, DEBUG, durées de vie Keycloak, sauvegardes age chiffrées et procédure de tests RLS PostgreSQL.


## V3.27 — Conversations juridiques multi-tours persistantes

- Historique de conversations enregistré côté serveur dans PostgreSQL, sans stockage local des échanges ni des jetons.
- Chaque conversation est cloisonnée à la fois par organisation et par utilisateur authentifié (RLS PostgreSQL FORCE).
- Les questions de suivi reçoivent les derniers échanges comme contexte de compréhension ; les réponses précédentes ne sont jamais considérées comme des sources juridiques.
- Les recherches documentaires utilisent les questions précédentes de l'utilisateur et la question courante pour mieux résoudre les références implicites.
- Consultation, reprise et suppression des conversations depuis l'interface ; suppression en cascade des messages.
- Migrations `012_persistent_chat_conversations.sql` et `013_legal_dossiers.sql` et leurs rollbacks associés.
- La conversation fournit un contexte limité aux 12 derniers messages ; elle ne remplace pas la vérification des textes, dates d'effet, sources et actes locaux.


## V3.28 — Dossiers juridiques constitués à partir des échanges

- Un dossier de travail peut être constitué depuis une conversation privée. Il reprend les éléments rapportés/questions de l'utilisateur, les réponses de JURIS avec leur statut de vérification, les sources enregistrées et les points restant à vérifier.
- Les champs objet, éléments rapportés, chronologie, pièces à vérifier, conclusion provisoire et plan d'action sont modifiables et persistés dans PostgreSQL.
- Impression navigateur / export PDF via la fonction d'impression.
- Migration `013_legal_dossiers.sql`, RLS FORCE et cloisonnement simultané par organisation et utilisateur ; suppression en cascade avec la conversation.
- Le dossier reste un brouillon : aucune conclusion n'est validée automatiquement. Les pièces jointes ne sont pas extraites automatiquement de ce module et doivent être référencées/ajoutées par l'utilisateur.
- Déploiement : sauvegarder puis exécuter `scripts/upgrade_with_backup.sh` ; le migrateur applique la migration 013 dans l'ordre.


## V3.29 — Sécurisation juridique avancée

Voir `docs/37_V3_29_SECURISATION_JURIDIQUE_AVANCEE.md`. La V3.29 ajoute une qualification indicative des familles de sources et de leur statut temporel, une route de revue de cohérence entre un document local et des sources nationales, une trace d'audit, un endpoint de fraîcheur du corpus réservé à l'administration plateforme et un script de veille ciblée à planifier par l'exploitant. Le contrôle local signale des points à examiner et ne déclare jamais automatiquement un acte légal ou illégal. Le classement des sources n'est pas un moteur complet de résolution des conflits de normes. La veille fournie n'est pas exhaustive et ne démarre pas sans planification explicite.


### V3.30 — import du CGFP dans le corpus national

Le script `scripts/import_cgfp_to_legal_corpus.py` valide les 4 242 articles et l'empreinte du PDF, puis peut les importer dans le corpus national partagé. Il fonctionne par défaut en contrôle à blanc. Pour écrire, configurer `LEGAL_CORPUS_INGEST_DATABASE_URL` avec le rôle dédié `cfdt_juris_ingest`, puis exécuter `python scripts/import_cgfp_to_legal_corpus.py --apply`. Le compte API et le compte DBA sont refusés. Les entrées restent `IMPORTED_UNVERIFIED` et de temporalité `UNKNOWN` jusqu'à vérification sur les sources officielles.


### V3.30 — renforcement du moteur juridique

Le parcours de questionnement interroge désormais, en plus du CGFP local et du fonds CETAT, les textes consolidés Légifrance du fonds `LODA_DATE` (lois, décrets, arrêtés) à la date demandée. Les textes ne sont utilisables dans l'analyse assistée qu'après récupération par `POST /consult/legiPart` et correspondance de l'identifiant officiel. La recherche CETAT reste signalée comme recherche documentaire tant que le texte intégral n'est pas validé dans l'environnement PISTE réel. Les recherches PISTE utilisent la question actuelle tronquée à 500 caractères, sans perdre la priorité de celle-ci au profit de l'historique.


### Recherche des documents propres à l'employeur

Pour les employeurs locaux proposés par l'interface, le moteur recherche également les délibérations et pièces locales de l'organisation courante. Les résultats ne sont transmis à l'IA que si le document et sa version sont propres (scan CLEAN), le texte est extrait, les empreintes correspondent, la validation humaine est positive et la période d'effet couvre la date des faits. Voir `docs/38_RECHERCHE_DOCUMENTS_LOCAUX.md`.


## V3.30 — Renforcement du moteur juridique

- Import article par article du snapshot CGFP dans le corpus national, avec validation du PDF, de son empreinte SHA-256, de la pagination et des 4 242 références ; mode contrôle à blanc par défaut et rôle d'ingestion dédié obligatoire.
- Recherche à la date des faits dans le fonds `CODE_DATE` du CGFP et le fonds `LODA_DATE` pour les textes réglementaires complémentaires, avec contrôle de l'identifiant officiel et du texte consulté.
- Recherche CETAT maintenue au niveau métadonnées/extraits tant que la consultation du texte intégral n'a pas été validée sur PISTE réel.
- Recherche dans les documents locaux de l'organisation et de la collectivité sélectionnée ; les documents non scannés, non extraits, non validés ou hors période sont exclus du contexte IA.
- Pas d'analyse IA contextualisée sans date des faits ni source officielle datée exploitable ; le snapshot CGFP seul ne déclenche pas l'analyse IA.
- Extraits renvoyés au navigateur bornés ; les textes intégraux restent côté serveur.
- Tests : 164 réussis, 2 ignorés dans l'environnement de génération ; les deux tests PostgreSQL RLS exigent une base de test réelle.
- Les accès PISTE, l'import dans la base cible, la recette PostgreSQL, les tests Keycloak/ClamAV et le déploiement restent à réaliser dans l'environnement de l'exploitant.


## Profil d'instance privée (10 comptes)
Le projet comporte un profil privé activable par `PRIVATE_INSTANCE_MODE=true` et `PRIVATE_INSTANCE_MAX_USERS=10`. Voir `docs/40_INSTANCE_PRIVEE_10_COMPTES.md` pour la procédure d'installation, l'approbation manuelle des comptes et la migration 015.


## Kit développeur ZIP

Après validation complète de la CI, le workflow publie un artefact téléchargeable nommé `CFDT-JURIS-V3.30-Kit-Developpeur` (conservation 30 jours). Il contient les sources et la documentation, sans dépôt Git local, caches, environnements virtuels ni fichiers de secrets.

Pour produire l'archive depuis une copie locale du dépôt :
```bash
python scripts/package_developer_kit.py
```
Le fichier est créé dans `dist/CFDT_JURIS_V3_30_Kit_Developpeur.zip`. Le script ajoute `SHA256SUMS_KIT.txt`, qui permet de contrôler l'intégrité des fichiers extraits. Les fichiers `.env` réels, clés privées et certificats ne sont jamais inclus ; seuls les modèles `.env.example` et `.env.staging.example` sont conservés.

Ne placez jamais de mots de passe, jetons, URL de base de données avec identifiants ou données syndicales réelles dans l'archive.


## V3.33 — Limitation partagée des parcours juridiques coûteux
Le quota PostgreSQL existant est désormais partagé entre les questions du chat et les revues de cohérence des règles locales. Une même personne ne peut donc pas contourner la limitation en alternant les deux routes. Le contrôle intervient avant la lecture du document et la recherche du corpus ; le dépassement renvoie HTTP 429 avec `Retry-After`. Le compteur reste limité à l'organisation et à l'utilisateur, sans stocker de contenu juridique.


## V3.35 — Sécurisation des imports PISTE
Les routes d'administration qui importent les textes réglementaires et la jurisprudence contrôlent désormais les recherches et limitent chaque import à 20 résultats maximum avant tout accès à la base d'ingestion ou à l'API PISTE. Cette protection évite les imports involontairement trop volumineux et borne les consultations de décisions intégrales.
