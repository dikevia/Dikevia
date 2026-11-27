# 20 — Ajout du Code général de la fonction publique au corpus national

## Source intégrée

Le répertoire `corpus_national/legislation/` contient une copie du PDF du **Code général de la fonction publique (CGFP)** fourni pour le projet :

- Fichier : `CGFP_snapshot_2026-10-31.pdf`
- Pagination : 1 024 pages
- Dernière modification indiquée dans le document : 31 octobre 2026
- Date de génération indiquée : 13 novembre 2026
- Couche texte PDF : présente et extractible
- Empreinte SHA-256 et métadonnées : `CGFP_snapshot_2026-10-31.metadata.json`

## Ce que cet ajout réalise

- Conservation du PDF dans le kit développeur.
- Identification de la source, de sa date de consolidation et de son empreinte.
- Définition des règles de traitement et de prudence juridique pour son intégration au corpus.

## Ce que cet ajout ne réalise pas

- Le PDF n'est pas déclaré chargé dans une base de données de production ; aucun accès à la base cible n'est disponible dans le kit.
- Le pipeline d'import article par article est désormais fourni par `scripts/import_cgfp_to_legal_corpus.py`. Il alimente le corpus national partagé en conservant le statut `UNKNOWN` et la provenance du snapshot ; il ne crée pas d'historique juridique réel.
- Le moteur juridique et le connecteur PISTE/Légifrance ne sont pas implémentés par cet ajout.
- La présence du PDF ne prouve pas, à elle seule, que chaque disposition est applicable à la date des faits étudiés.

## Traitement attendu dans le moteur documentaire

1. Importer le PDF dans l'espace documentaire national, sans le rattacher à une collectivité particulière.
2. Contrôler le fichier par l'antivirus avant toute extraction ou mise à disposition.
3. Extraire le texte et indexer les références d'articles (`L`, `R`, `D`), en conservant le livre, le titre, le chapitre, la page PDF et la source.
4. Détecter les articles modifiés, abrogés ou créés et ne jamais assimiler la consolidation du 31 octobre 2026 à une version historique.
5. Lors d'une question, identifier la date des faits puis vérifier la version applicable à cette date sur Légifrance et dans l'historique des textes.
6. N'afficher le statut `VERIFIE` qu'après récupération et validation des sources officielles nécessaires. À défaut, conserver `PARTIELLEMENT_VERIFIE` ou `NON_VERIFIE`.

## Règle de portée

Le CGFP est une source législative et réglementaire nationale centrale pour la FPT, mais il ne remplace pas les décrets d'application, les autres codes, les textes spéciaux, les actes locaux, les accords collectifs ni la jurisprudence pertinente. Les règles applicables aux agents contractuels doivent être déterminées disposition par disposition, notamment au regard du champ d'application prévu par le code.

## Mise en service documentaire V3.11

Le kit V3.11 ajoute un index JSON article/page généré depuis le PDF fourni. Il recense les articles législatifs et réglementaires détectés, leur texte extrait et les pages du PDF. Le script reproductible est `scripts/build_cgfp_index.py` ; l'index livré est `corpus_national/index/CGFP_articles_2026-10-31.json`.

Le backend expose `GET /api/v1/legal/cgfp/search?q=...` (authentification et contexte d'organisation requis) et utilise cette recherche dans `POST /api/v1/chat/ask`. Les résultats sont classés lexicalement et retournent l'identifiant de source, l'article, les pages et un extrait. L'index est commun au corpus national ; il ne contient aucune donnée propre à une organisation.

**Limites juridiques actuelles :** le snapshot ne contient pas à lui seul l'historique juridique des versions. Lorsque PISTE est configuré, le moteur peut interroger le CGFP à la date demandée et rechercher des textes complémentaires dans `LODA_DATE`, mais ces parcours doivent encore être validés avec les identifiants réels de l'organisation. La recherche CETAT fournit actuellement des identifiants et métadonnées/extraits, pas un texte intégral de décision validé dans le parcours utilisateur. La couverture de tous les codes, textes spéciaux, circulaires et jurisprudences n'est pas exhaustive. Le statut reste au plus `PARTIELLEMENT_VERIFIE` ; une absence de résultat ne prouve pas l'absence de droit.

Pour reconstruire l'index depuis le PDF : `python scripts/build_cgfp_index.py`. Le conteneur Docker embarque désormais `corpus_national/`.


## Import structuré du snapshot — préparation V3.30

Le script `scripts/import_cgfp_to_legal_corpus.py` valide l'index JSON, vérifie l'empreinte SHA-256 du PDF associé, contrôle les références d'articles, les doublons, les textes vides et les pages, puis prépare l'import des 4 242 entrées dans `legal_documents`, `legal_document_versions` et `legal_chunks`.

- Le mode par défaut est un contrôle à blanc : aucune écriture en base.
- L'écriture exige `--apply` et le DSN `LEGAL_CORPUS_INGEST_DATABASE_URL` (ou `--dsn`).
- Le DSN est refusé si son utilisateur PostgreSQL n'est pas `cfdt_juris_ingest`. Le compte API `cfdt_juris_app` et le compte DBA ne doivent pas être utilisés.
- Les documents sont marqués `CGFP_SNAPSHOT`, `IMPORTED_UNVERIFIED`, avec statut et dates d'effet `UNKNOWN`.
- L'import ne signifie pas que la base cible a été alimentée : cette opération reste à effectuer par le développeur dans l'environnement disposant des secrets PostgreSQL.

Contrôle local effectué sur le kit : 4 242 articles détectés, empreinte PDF conforme aux métadonnées. Ce contrôle vérifie la cohérence entre PDF et index, pas l'exactitude juridique de chaque article au regard de la version en vigueur sur Légifrance.

## Portée de la jurisprudence administrative

L'orchestrateur interroge le fonds CETAT lorsque PISTE est configuré. À ce stade, il ne retient que les identifiants et métadonnées/extraits de recherche retournés par la recherche officielle. Il ne transmet pas ces extraits comme du texte intégral à l'IA et indique explicitement que la décision complète doit être vérifiée. La méthode de consultation expérimentale présente dans le connecteur n'est pas activée dans le parcours utilisateur avant validation du contrat de l'API en environnement PISTE réel.

## Recherche Légifrance à la date des faits — parcours applicatif

Le parcours du moteur utilise les fonds et méthodes décrits par la FAQ officielle de l'API Légifrance :

- `CODE_DATE` + `POST /consult/getArticle` pour consulter les articles de code à une date donnée ;
- `LODA_DATE` + `POST /consult/legiPart` pour récupérer le texte d'une loi ou d'un texte réglementaire à une date donnée ;
- `CETAT` pour repérer la jurisprudence administrative, sans présenter les seuls résultats de recherche comme des décisions intégrales.

Référence technique officielle : https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api

Le développeur devra vérifier sur le compte PISTE de l'organisation que les CGU API ont été acceptées et que l'API Légifrance est activée sur les applications sandbox et production. Les environnements, URL et identifiants sont distincts ; les secrets restent dans l'environnement serveur et ne doivent pas être transmis dans le ZIP.

La consultation du texte intégral CETAT via `/consult/juri` est considérée expérimentale dans le kit : l'endpoint d'ingestion correspondant est désactivé par défaut (`LEGIFRANCE_CETAT_FULLTEXT_ENABLED=false`). Le développeur devra confirmer le contrat sur PISTE sandbox avec une décision connue avant de l'activer.

Pour les textes `LODA_DATE`, le statut temporel `IN_FORCE_ON_REQUESTED_DATE` provient du couple `DATE_VERSION` + consultation datée `/consult/legiPart` avec identifiant retourné concordant. Si la réponse de recherche ne fournit pas de libellé d'état juridique, le statut brut reste `UNKNOWN` dans les métadonnées ; seule la version consultée à la date demandée est qualifiée comme version applicable à cette date.
