# Livraison technique développeur — CFDT JURIS V3.30

## 1. Objet de la livraison

Cette livraison reprend le kit V3.30 transmis et prépare au maximum les opérations qui peuvent être réalisées sans accès aux secrets, au compte PISTE de l'organisation ni à la base PostgreSQL cible.

Le développeur ne doit pas reprendre les développements déjà réalisés dans le kit. Son intervention est concentrée sur les opérations d'environnement, les vérifications réelles et la mise en service.

## 2. Éléments préparés dans le code

### CGFP
- PDF source présent : `corpus_national/legislation/CGFP_snapshot_2026-10-31.pdf`.
- Pagination contrôlée : 1 024 pages.
- Index : 4 242 articles, références et pages validés.
- Empreinte SHA-256 contrôlée : `4752c5a89453b53784bd074d427dfca9253b161369eb960f0082757dbd12d113`.
- Import article par article préparé dans `scripts/import_cgfp_to_legal_corpus.py`.
- Mode contrôle à blanc par défaut, transaction unique, insertion groupée des chunks, contrôle post-import des comptes et des statuts.
- Le script impose le rôle `cfdt_juris_ingest` et `LEGAL_CORPUS_INGEST_DATABASE_URL`.
- Les entrées restent `IMPORTED_UNVERIFIED`, statut `UNKNOWN`, dates d'effet inconnues. L'import ne constitue pas une validation juridique.

### Moteur juridique
- Recherche du CGFP à la date demandée via `CODE_DATE` et consultation de l'article par identifiant.
- Recherche des lois, décrets et arrêtés complémentaires via `LODA_DATE` et `DATE_VERSION`, puis consultation datée `/consult/legiPart`.
- Contrôle de l'identifiant retourné et de la présence d'un texte substantiel.
- Extraits pertinents bornés pour les textes longs ; les textes intégraux ne sont pas renvoyés au navigateur.
- Les appels PISTE utilisent la question actuelle en priorité et respectent la limite de 500 caractères.
- Une source importée sans statut temporel fiable est exclue du contexte IA.
- Le snapshot CGFP seul ne déclenche pas l'analyse IA.
- Sans date des faits, les sources repérées sont signalées comme temporellement incomplètes et aucune analyse contextualisée n'est lancée.
- Les références produites par l'IA sont contrôlées uniquement contre les sources réellement transmises au modèle.

### Jurisprudence administrative
- Recherche CETAT disponible au niveau identifiants, métadonnées et extraits officiels.
- Le texte intégral CETAT via `/consult/juri` reste expérimental : le parcours d'import intégral est protégé par `LEGIFRANCE_CETAT_FULLTEXT_ENABLED=false` par défaut.
- Ne pas activer ce paramètre avant d'avoir validé le contrat sur PISTE sandbox avec un identifiant CETAT connu.

### Documents locaux
- Recherche des documents locaux limitée à l'organisation et à la collectivité sélectionnée.
- Contrôles : document et version scannés CLEAN, extraction EXTRACTED, empreintes concordantes, validation humaine et période d'effet.
- Les documents locaux non validés, hors période ou à empreinte incohérente sont exclus du contexte IA.
- Les sources locales affichent désormais la collectivité et le type de pièce dans l'interface et le dossier juridique.

### Sécurité et exploitation
- Import du CGFP refusé avec le compte API ou un compte DBA.
- Corpus national en lecture seule pour le rôle API.
- Les recherches locales restent tenant-scoped.
- Les erreurs d'ingestion sont consignées comme échecs au lieu de laisser un run bloqué en `RUNNING`.

## 3. Vérifications réalisées dans l'environnement de préparation

- `python scripts/import_cgfp_to_legal_corpus.py` : contrôle à blanc réussi, 4 242 articles et empreinte PDF concordante ; aucune écriture en base.
- `python scripts/audit_env_example.py` : OK, 42 variables `Settings` documentées.
- `python -m pytest -q` : **164 réussis, 2 ignorés**.
- Les deux tests ignorés sont les tests PostgreSQL RLS, faute de base de test configurée.
- Vérification syntaxique Node.js des trois blocs JavaScript intégrés dans `frontend/index.html` : aucune erreur.
- Compilation Python locale : réussie lors du contrôle de préparation.

Aucun déploiement, import dans la base de production, test PostgreSQL réel, test Keycloak réel, test antivirus réel ni appel PISTE avec les identifiants de l'organisation n'est revendiqué.

## 4. Opérations développeur restantes

### A. Base PostgreSQL
1. Faire une sauvegarde et vérifier qu'elle est restaurable.
2. Contrôler la version avec `python scripts/db_migrate.py status`.
3. Sur une base existante, appliquer la migration `014_cgfp_snapshot_source_type.sql` avec le rôle de migration prévu ; sur une installation neuve, suivre le parcours baseline documenté puis `upgrade`.
4. Vérifier que `cfdt_juris_app` reste en lecture seule sur le corpus national et que `cfdt_juris_ingest` n'a ni `SUPERUSER`, ni `BYPASSRLS`, ni propriété des tables.
5. Exécuter les tests RLS réels avec `TEST_DATABASE_ADMIN_URL` et `TEST_DATABASE_URL`.

### B. Import CGFP
1. Configurer `LEGAL_CORPUS_INGEST_DATABASE_URL` avec le rôle dédié `cfdt_juris_ingest`.
2. Exécuter le contrôle à blanc :
   `python scripts/import_cgfp_to_legal_corpus.py`
3. Après sauvegarde et validation du schéma, lancer :
   `python scripts/import_cgfp_to_legal_corpus.py --apply`
4. Vérifier les comptes attendus : 4 242 documents, 4 242 versions et 4 253 chunks pour le snapshot fourni. Le script effectue un contrôle transactionnel post-import et échoue si les comptes ou statuts ne correspondent pas.

### C. PISTE / Légifrance
1. Accepter les CGU API sur PISTE en sandbox et en production.
2. Activer l'API Légifrance sur chacune des applications concernées.
3. Configurer séparément les identifiants, URL et secrets sandbox et production.
4. Tester `CODE_DATE` + `/consult/getArticle` sur un article CGFP connu.
5. Tester `LODA_DATE` + `DATE_VERSION` + `/consult/legiPart` sur un texte réglementaire connu.
6. Vérifier quotas, délais, erreurs, consentements et provenance des résultats.
7. Laisser `LEGIFRANCE_CETAT_FULLTEXT_ENABLED=false` tant que `/consult/juri` n'a pas été confirmé en sandbox. Si le contrat est validé, activer le paramètre et tester l'import intégral sur quelques décisions CETAT connues avant toute ingestion plus large.

### D. Documents locaux et recette fonctionnelle
1. Vérifier les codes/noms de collectivités reconnus dans `backend/app/local_corpus.py`.
2. Tester une pièce propre, une pièce non extraite, une pièce non scannée, une pièce non validée, une pièce hors période et une pièce d'une autre organisation.
3. Vérifier que seule une pièce locale validée et applicable à la date des faits est transmise à l'IA.
4. Faire relire le jeu de scénarios juridiques par un juriste ou référent compétent.

### E. Services et déploiement
1. Renseigner les secrets OIDC/Keycloak, PISTE, IA, SMTP et stockage dans l'environnement serveur ; ne jamais les intégrer au ZIP.
2. Vérifier ClamAV réel, stockage privé, sauvegarde/restauration, HTTPS, reverse proxy, CSP, CORS et supervision.
3. Exécuter `python -m pytest -q` avec les URL PostgreSQL de test configurées.
4. Faire la recette staging complète avant déploiement production.

## 5. Référence PISTE

FAQ officielle Légifrance API :
https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api

Elle documente notamment le filtre `DATE_VERSION`, le fonds `CODE_DATE`, le fonds `LODA_DATE`, les méthodes `/consult/getArticle` et `/consult/legiPart`, ainsi que la séparation des environnements sandbox et production et l'acceptation des CGU.

## 6. Limite de la livraison

Le moteur reste un outil d'aide à l'analyse juridique, pas un service certifié ni un substitut à la validation humaine. Le statut automatique ne dépasse pas `PARTIELLEMENT_VERIFIE`. L'exhaustivité du corpus et l'applicabilité d'une règle doivent toujours être vérifiées au regard des faits, de la date, de l'employeur et des sources officielles.

## Addendum — profil d'instance privée (livraison de travail)
Le ZIP contient désormais le profil privé décrit dans `docs/40_INSTANCE_PRIVEE_10_COMPTES.md` : organisation unique, dix adhésions actives maximum, invitations suivies d'une approbation plateforme, suspension/révocation sans suppression des données et désactivation des routes Stripe. La migration 015 et son rollback sont fournis. Ce profil n'est pas encore déployé sur la base de l'organisation : appliquer la migration et effectuer la recette PostgreSQL/OIDC décrite dans le guide privé avant ouverture aux utilisateurs.


## Addendum V3.31 — limitation des requêtes chat

La migration 017 ajoute une limitation PostgreSQL atomique par utilisateur et organisation (10 requêtes/minute par défaut, configurable). Le compteur est protégé par RLS/FORCE RLS et ne contient aucun texte de conversation. Le dépassement renvoie HTTP 429 avec Retry-After. Cette mesure ne remplace pas un WAF, un quota mensuel de dépenses IA ni les limites PISTE ; ces derniers restent à définir pour la commercialisation.


## Addendum V3.33 — Quota partagé
La limitation PostgreSQL est désormais commune aux questions du chat et aux revues de cohérence des règles locales. Le quota est consommé avant la lecture du document et la recherche du corpus national ; les deux parcours ne peuvent donc pas être alternés pour contourner la limite. Le refus est HTTP 429 avec `Retry-After`.
