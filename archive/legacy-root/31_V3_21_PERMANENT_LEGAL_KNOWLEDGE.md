# V3.21 — Référentiel juridique permanent

## Objectif et périmètre

V3.21 ajoute un référentiel juridique national partagé entre les espaces syndicaux. Il est distinct des documents propres à une organisation, qui restent dans les tables tenant-scoped avec RLS.

Le référentiel stocke :
- textes consolidés LEGI/LODA récupérés via l'API stable Légifrance/PISTE ;
- décisions administratives CETAT uniquement lorsque la consultation retourne un texte et un identifiant correspondant ;
- métadonnées du flux CIRCULAIRES DILA importé depuis un XML fourni par un administrateur plateforme ;
- versions, dates d'effet lorsqu'elles sont explicitement présentes, empreintes SHA-256, identifiants de source et liens officiels ;
- relations documentaires et historique des opérations d'import.

Références officielles :
- https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api
- https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api
- https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides
- https://www.data.gouv.fr/datasets/circulaires-instructions-et-circulaires-des-ministeres

## Modèle de données

- `legal_documents` : identité stable de la source et métadonnées.
- `legal_document_versions` : versions, dates de validité, texte complet réellement récupéré et empreinte SHA-256.
- `legal_chunks` : fragments plein texte français pour la recherche ; `content_kind` distingue `FULL_TEXT` et `METADATA`.
- `legal_document_relations` : relations entre textes (modification, abrogation, remplacement, interprétation, citation).
- `legal_ingestion_runs` : journal des imports, volumes et erreurs.

Le corpus est national et partagé. Les documents locaux restent dans `documents`, `document_versions` et `document_text`, cloisonnés par organisation.

## Statut et règle de prudence

- `OFFICIAL_TEXT_ID_VERIFIED` : l'API a retourné l'identifiant demandé et un texte substantiel consultable ; l'empreinte du texte stocké est calculée.
- `OFFICIAL_TEXT_RETRIEVED` : texte officiel récupéré, sans que tous les contrôles de version soient nécessairement terminés.
- `IMPORTED_UNVERIFIED` : fichier XML importé par un administrateur ; l'origine et l'exhaustivité du fichier ne sont pas certifiées par l'application.
- `METADATA_ONLY` : métadonnées seules, jamais utilisées pour établir une règle de droit.
- `MANUALLY_VERIFIED` : statut à réserver à une procédure de validation humaine documentée.

Le moteur calcule `temporal_status` à la date demandée :
- `IN_FORCE_ON_REQUESTED_DATE` si les deux bornes de validité connues couvrent la date ;
- `NOT_YET_EFFECTIVE` si la date précède le début connu ;
- `NO_LONGER_IN_FORCE` si la date dépasse la fin connue ;
- `TEMPORAL_SCOPE_INCOMPLETE` si les bornes ne permettent pas une conclusion.

Une source dont le texte ou l'empreinte n'est pas vérifiable, ou dont la temporalité est incomplète, est exclue du paquet transmis au modèle IA. Une circulaire importée en simple métadonnée ne peut pas soutenir une conclusion IA. Les dates de signature ou de publication ne sont jamais assimilées automatiquement à une date d'entrée en vigueur.

## API

Toutes les routes nécessitent une authentification sauf les routes de santé déjà présentes.

| Méthode | Route | Accès | Fonction |
|---|---|---|---|
| GET | `/api/v1/legal/knowledge/search?q=...&effective_date=AAAA-MM-JJ&limit=12` | Adhésion active | Recherche plein texte dans le corpus commun |
| POST | `/api/v1/platform/legal-corpus/ingest/regulatory?q=...&effective_date=...&limit=10` | Administrateur plateforme | Recherche puis consultation LODA/LEGI via PISTE |
| POST | `/api/v1/platform/legal-corpus/ingest/administrative-case-law?q=...&effective_date=...&limit=10` | Administrateur plateforme | Recherche CETAT puis tentative de consultation du texte intégral |
| POST | `/api/v1/platform/legal-corpus/ingest/circulaires-xml` | Administrateur plateforme | Import du XML CIRCULAIRES DILA ; l'import reste non vérifié |
| GET | `/api/v1/platform/legal-corpus/ingestion-runs?limit=30` | Administrateur plateforme | Historique des imports |

Les routes d'import ne sont pas exposées aux administrateurs d'un syndicat. Les recherches de textes sont ciblées ; elles ne constituent pas une synchronisation exhaustive du fonds.

## Comptes PostgreSQL séparés

Le rôle `cfdt_juris_app` a uniquement des droits de lecture sur le corpus national. Les opérations d'import passent par un pool séparé `LEGAL_CORPUS_INGEST_DATABASE_URL` associé au rôle `cfdt_juris_ingest`.

Pour une installation neuve, Docker initialise les rôles via :
- `deploy/init/01-create-app-role.sh`
- `deploy/init/02-create-corpus-ingest-role.sh`

Pour une base existante, créer le rôle d'ingestion avant d'appliquer `009_permanent_legal_knowledge.sql`, puis exécuter les grants de la migration comme DBA. Ne pas donner `BYPASSRLS`, `SUPERUSER` ou la propriété des tables à ces rôles.

Variables à renseigner dans `.env` :
- `POSTGRES_INGEST_PASSWORD`
- `LEGAL_CORPUS_INGEST_DATABASE_URL`

Le mot de passe du rôle d'ingestion doit être différent des mots de passe runtime et migration.

## Installation / mise à niveau

Base neuve : utiliser `database/schema.sql` puis `database/grant_runtime_permissions.sql` (le compose de développement les applique au premier démarrage).

Base existante :
1. créer le rôle `cfdt_juris_ingest` avec `deploy/init/02-create-corpus-ingest-role.sh` ou un script DBA équivalent ;
2. appliquer `database/migrations/009_permanent_legal_knowledge.sql` ;
3. réexécuter `database/grant_runtime_permissions.sql` ;
4. renseigner `LEGAL_CORPUS_INGEST_DATABASE_URL` ;
5. redémarrer l'API.

Ne pas rejouer `database/schema.sql` sur une base existante.

## Limites connues de cette livraison

- La recherche LODA importe les textes LEGITEXT consultables ; elle ne constitue pas une synchronisation exhaustive de tous les décrets et arrêtés.
- Les décisions CETAT sont stockées uniquement lorsque la consultation intégrale passe les contrôles d'identifiant et de contenu ; une recherche seule ne devient pas une décision vérifiée.
- Le flux CIRCULAIRES DILA est importé à partir d'un fichier XML fourni par un administrateur. L'application ne télécharge pas encore automatiquement les archives DILA et marque l'import `IMPORTED_UNVERIFIED`.
- Les liens de modification/abrogation sont prévus dans le schéma mais leur extraction automatique n'est pas encore complète.
- Le moteur de recherche est lexical PostgreSQL (français) ; l'index vectoriel/sémantique n'est pas inclus.
- La recette PISTE réelle, les quotas, la conformité des données, la migration sur une base de test et les tests de sécurité PostgreSQL restent obligatoires avant production.
