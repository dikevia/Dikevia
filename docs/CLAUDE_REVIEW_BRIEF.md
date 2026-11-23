# Dossier de revue technique — Dikévia
Date de préparation : 22 novembre 2026
Branche analysée : `feature/dikevia-v3.38.5-cgfp-chat`
Commit exact inclus dans le ZIP : `ef6d09e27ebfc918f165634c8128a6b7fe161703`.
Le snapshot CGFP et le code sont ceux de cette révision ; le dossier est produit par GitHub Actions.

## Mission confiée à Claude

Tu es chargé d'effectuer une revue d'architecture indépendante de Dikévia, un assistant conversationnel juridique consacré à la fonction publique française (FPT, FPE, FPH). L'objectif est de recommander la meilleure façon d'exploiter le corpus documentaire dans PostgreSQL et dans le moteur de réponse, avec priorité à la fiabilité juridique, à la traçabilité, à la fraîcheur des textes et à la qualité du rappel documentaire.

**Ne modifie pas le code.** Commence par établir les faits à partir du dépôt, puis formule des recommandations hiérarchisées, avec avantages, risques, coûts de mise en œuvre et tests d'acceptation. Ne présume pas qu'une architecture vectorielle est nécessaire : compare d'abord la recherche plein texte existante, une approche hybride et le coût réel d'un éventuel reranking.

## Produit et périmètre

- Dikévia est un SaaS conversationnel d'information et d'assistance juridique destiné aux agents publics et aux organisations syndicales.
- Périmètre juridique : fonction publique territoriale, fonction publique d'État et fonction publique hospitalière.
- L'expérience attendue est un dialogue naturel, pédagogique et contextualisé, qui conserve l'historique de conversation et pose des questions de clarification lorsque des faits essentiels manquent.
- Les réponses doivent distinguer droit positif, doctrine administrative, guides professionnels, jurisprudence et positions syndicales.
- L'application Administration est séparée du chatbot destiné aux agents.
- L'acquisition commerciale ne repose pas sur une prospection active des collectivités.

## Architecture technique à examiner

- Backend Python / FastAPI ; code principal dans `backend/app/`.
- Orchestration conversationnelle et qualification des demandes : `backend/app/orchestrator.py` et modules associés.
- Index CGFP local : `corpus_national/index/CGFP_articles_2026-10-31.json` et code de recherche associé.
- Corpus national PostgreSQL : `backend/app/legal_corpus.py`.
- Tables : `legal_documents`, `legal_document_versions`, `legal_chunks`.
- Recherche actuelle : PostgreSQL full-text search en français (`websearch_to_tsquery`), requête initiale pondérée plus expansion de synonymes, sélection de passages et vérification SHA-256 du texte complet.
- Taille des chunks configurée dans le code : 4 200 caractères, chevauchement de 300.
- L'orchestrateur peut produire jusqu'à cinq axes de recherche, interroge le corpus permanent pour chaque axe, puis intercale les résultats.
- Le contexte conversationnel, le CGFP, les sources Légifrance/PISTE, la jurisprudence et les documents propres à l'employeur sont d'autres piliers de recherche à étudier dans leur ordre d'exécution et leur articulation.
- PostgreSQL/Neon ; migrations versionnées dans `database/migrations/`.
- Déploiement backend sur Render ; workflows et CI dans `.github/workflows/`.
- Le dépôt contient les tests backend dans `backend/tests/`.

## État documentaire vérifié au 22 novembre 2026

### 1. Socle juridique livré dans l'application

Le dépôt contient un snapshot CGFP consolidé au 31 octobre 2026 :
- 1 024 pages ;
- 4 242 articles indexés ;
- fichier JSON d'environ 2,59 Mo ;
- index livré avec l'application Render.

Ce snapshot sert au repérage et à la découverte des articles. Il ne doit pas, à lui seul, être considéré comme preuve de la version applicable à une date donnée. Les textes normatifs officiels et leur version temporelle doivent être vérifiés auprès de Légifrance.

### 2. Service-Public / DILA

Un export DILA Service-Public Fonction publique a été collecté :
- 199 fiches ;
- 4 455 401 caractères ;
- 194 fiches contiennent des références juridiques ;
- 994 références juridiques distinctes extraites ;
- licence identifiée dans les métadonnées : Licence Ouverte 2.0 ;
- attribution : Service-Public.gouv.fr / DILA.

Le JSON source extrait est fourni dans ce dossier sous `corpus_review/service-public-corpus.json`. Les références juridiques extraites n'ont pas été validées individuellement : les fiches restent de la documentation administrative secondaire et ne doivent pas devenir des autorités normatives.

### 3. Guides institutionnels, professionnels et syndicaux

18 ressources ont été téléchargées et extraites en dry-run :
- 6 PDF, 241 pages ;
- 12 pages HTML ;
- environ 590 716 caractères extraits.
Elles couvrent notamment DGAFP, CDG35, CIG Petite Couronne, CDG59, CDG69, CNFPT, CFDT, CGT, FO, CFTC, UNSA et Solidaires.

Le guide CFDT Interco 2026 a été extrait : 68 pages, 181 469 caractères.
Ces ressources sont conservées dans les artefacts d'audit, mais ne sont pas jointes intégralement au présent dossier. Leurs droits de réutilisation sont encore `REVIEW_REQUIRED`. Les 18 ressources ont le statut `EXTRACTED_NOT_IMPORTED`.

### 4. Inventaire du registre

- 21 sources répertoriées ;
- 34 ressources candidates ;
- 18 ressources extraites mais non importées ;
- 16 ressources non collectées ;
- toutes les ressources candidates ont actuellement le statut de réutilisation `REVIEW_REQUIRED`, à l'exception du dataset Service-Public qui porte ses métadonnées de licence ouverte dans son export.

## État réel de PostgreSQL

La base de production Neon a été contrôlée le 22 novembre 2026 :
- `legal_documents` : 0 ligne ;
- `legal_document_versions` : 0 ligne ;
- `legal_chunks` : 0 ligne ;
- migrations jusqu'à la version 22.

Le schéma du corpus existe, mais le corpus permanent est vide en production. Les ressources extraites ne sont donc pas encore accessibles via `search_legal_corpus` dans le chatbot. Ne pas confondre snapshot CGFP embarqué et corpus PostgreSQL permanent.

Le rôle PostgreSQL d'ingestion dédié `cfdt_juris_ingest` existe. Le workflow GitHub Actions attend le secret `LEGAL_CORPUS_INGEST_DATABASE_URL`, mais la dernière exécution a ignoré l'import car ce secret n'était pas disponible dans l'environnement du workflow. Aucun import PostgreSQL n'a été effectué.

## Points d'audit prioritaires

1. **Hiérarchie des sources dans le ranking.** Vérifier si la recherche plein texte peut classer une fiche administrative ou une position syndicale avant un texte normatif. Le SQL de `search_legal_corpus` semble principalement classer par pertinence textuelle et date de publication ; évaluer un classement multi-critères qui donne la priorité aux textes normatifs applicables, puis à la jurisprudence pertinente, puis aux guides administratifs/professionnels, puis aux positions syndicales. Ne pas réduire artificiellement la pertinence d'une source secondaire lorsqu'elle répond à une question pédagogique, mais ne jamais la présenter comme droit positif.
2. **Typologie des sources.** Le registre distingue `PRIMARY_LEGAL`, `OFFICIAL_ADMIN_GUIDANCE`, `PROFESSIONAL_GUIDANCE` et `TRADE_UNION_POSITION`. La migration 022 n'autorise que `SERVICE_PUBLIC_PART` et `INSTITUTIONAL_GUIDANCE` comme catégories de source génériques. L'importeur `scripts/import_public_guidance_sources.py` mappe actuellement toutes les sources en `INSTITUTIONAL_GUIDANCE` et distingue seulement `PROFESSIONAL_GUIDANCE` de `ADMIN_GUIDANCE`. Évaluer une typologie de données permettant de préserver explicitement les positions syndicales et leur éditeur.
3. **URL/provenance.** Examiner `safe_official_url` dans `legal_corpus.py` : la liste des domaines autorisés doit rester cohérente avec les domaines validés par le registre, y compris les sites professionnels et syndicaux ; éviter un élargissement permissif à n'importe quel HTTPS.
4. **Temporalité.** Les guides et fiches ont souvent des dates de publication, de mise à jour ou de validité incomplètes. Proposer un modèle séparant date de publication, dernière vérification, période de validité juridique et date de collecte.
5. **Dédoublonnage et versions.** Évaluer les clés source/version, les hashes, les mises à jour, les contenus quasi identiques et les anciennes versions.
6. **Chunking.** Évaluer les chunks de 4 200 caractères / 300 de chevauchement pour des articles de code, fiches FAQ, tableaux et PDF paginés. Proposer des frontières sémantiques (article, section, question, page) et des citations stables.
7. **Recherche multi-axes.** Vérifier la déduplication, le rappel et la précision lorsque jusqu'à cinq requêtes sont lancées. Évaluer fusion de rangs (RRF), plafonds par source et diversité des résultats.
8. **Recherche hybride.** Comparer full-text, synonymes, embeddings et reranking sur un benchmark réel ; recommander uniquement les composants dont le gain mesuré justifie la complexité et le coût.
9. **Sécurité multi-tenant.** Examiner la séparation entre corpus national partagé et documents propres à un employeur, les politiques RLS, les rôles d'ingestion et les surfaces de fuite de données.
10. **Contexte génératif et citations.** Vérifier que les sources, leur nature, leur date et leur statut de validation arrivent jusqu'au prompt final, et que le chatbot ne transforme pas une interprétation en règle juridique.
11. **Observabilité et qualité.** Proposer des métriques : Recall@k, MRR/nDCG, exactitude des citations, taux de réponses sans source, contradictions, latence, coût et taux de clarification.
12. **Plan de tests.** Concevoir un jeu de questions représentatif des trois versants, avec situations factuelles, date des faits, réponse attendue, sources primaires et critères de notation.

## Questions auxquelles répondre

- Quelle architecture de recherche recommandes-tu pour Dikévia, compte tenu du code existant et de la base réelle ?
- Comment hiérarchiser les sources sans sacrifier le rappel ni confondre autorité juridique et pertinence documentaire ?
- Quel schéma PostgreSQL et quelles métadonnées manquent pour assurer provenance, versionnement, temporalité et attribution ?
- Comment améliorer le découpage en chunks et la génération de citations robustes ?
- Dans quel ordre intégrer les 199 fiches Service-Public, puis les guides institutionnels/professionnels et les contenus syndicaux après validation des droits ?
- Quelles optimisations sont prioritaires avant de choisir un moteur vectoriel ?
- Quels tests et seuils objectifs permettraient de démontrer une fiabilité élevée ?
- Donne un plan d'action en trois horizons : corrections immédiates, amélioration à court terme, évolutions avancées.

## Contraintes de la recommandation

- Ne jamais inventer une règle juridique ni présenter une source secondaire comme texte officiel.
- Préserver le CGFP, Légifrance et la jurisprudence comme piliers de vérification normative.
- Attribuer explicitement les positions syndicales à l'organisation concernée.
- Respecter les licences et droits de réutilisation.
- Éviter les refontes coûteuses non justifiées par des mesures.
- Donner des recommandations concrètes, applicables au dépôt fourni, avec références de fichiers, schémas ou fonctions.
- Signaler clairement les informations absentes ou non vérifiées.

## Confidentialité du dossier

Ce dossier ne contient volontairement aucun secret, mot de passe, jeton, fichier `.env` réel, clé privée ni identifiant d'accès. Ne demande pas à l'utilisateur de les communiquer dans le rapport. Ne pas publier ou redistribuer les documents dont les droits de réutilisation sont encore à examiner.
