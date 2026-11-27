# CFDT JURIS V3.30 — Préparation du moteur juridique

## Périmètre de cette livraison

Cette livraison prépare le moteur juridique sans prétendre déployer quoi que ce soit sur l'environnement du développeur.

### 1. Sécurisation de l'absence de date des faits

Dans `backend/app/orchestrator.py` :
- la date du jour peut toujours servir au repérage des sources, mais elle n'est plus assimilée à la date des faits ;
- si `facts_date` est absent, l'appel au fournisseur IA est suspendu pour cette demande ;
- la réponse reste documentaire et affiche explicitement que la date du jour sert uniquement au repérage ;
- le statut reste `PARTIELLEMENT_VERIFIE` lorsque des sources documentaires sont présentes, jamais `VERIFIE` sur la seule base du snapshot.

Une date de faits invalide continue de produire `NON_VERIFIE` sans analyse.

### 2. Qualification explicite du snapshot CGFP

Migration `014_cgfp_snapshot_source_type.sql` :
- ajoute `CGFP_SNAPSHOT` aux types de source admis dans `legal_documents` ;
- le distingue des textes récupérés officiellement via Légifrance ;
- le rollback est fourni dans `database/migrations/rollback/`.

Le snapshot reste `IMPORTED_UNVERIFIED`, de statut juridique `UNKNOWN`, sans dates d'effet historiques inventées.

### 3. Import structuré CGFP — mode contrôlé

Script : `scripts/import_cgfp_to_legal_corpus.py`

Le script :
- vérifie l'empreinte SHA-256 du PDF avant import ;
- vérifie le compteur d'articles déclaré ;
- contrôle les références uniques, le texte et la pagination ;
- prépare un document par article et des chunks de texte ;
- conserve le snapshot, la page PDF, l'article et la provenance ;
- laisse les dates d'effet et le statut juridique à `UNKNOWN` ;
- est idempotent grâce aux clés uniques et aux `UPSERT`.

**Mode contrôle à blanc (aucune écriture) :**

```bash
python scripts/import_cgfp_to_legal_corpus.py
```

**Import réel (après sauvegarde, migration et validation du DBA) :**

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/014_cgfp_snapshot_source_type.sql
python scripts/import_cgfp_to_legal_corpus.py --apply
```

Le compte utilisé pour l'import doit avoir les droits d'écriture nécessaires sur le corpus national. Ne pas utiliser le compte applicatif en lecture seule. Le script n'exécute pas lui-même la migration et ne se connecte pas sans `--apply`.

### 4. Tests ajoutés

`backend/tests/test_v330_legal_preparation.py` couvre :
- l'absence d'appel IA lorsque la date des faits manque ;
- le contrôle des 4 242 articles et de l'empreinte PDF ;
- le rejet d'un PDF dont l'empreinte ne correspond pas.

### 5. Résultat des tests dans l'environnement de préparation

Commande exécutée depuis `backend/` :

```bash
python -m pytest -q
```

Résultat : **135 passed, 2 skipped**.

Les deux tests ignorés concernent l'intégration PostgreSQL/RLS qui nécessite des bases de test configurées. Aucun test d'intégration à la base de production n'a été exécuté.

### 6. Limites et actions requises du développeur

Cette livraison ne :
- récupère pas les versions historiques officielles du CGFP ;
- ne prouve pas que le PDF fourni est le texte officiel consolidé ;
- ne déduit aucune date d'effet historique ;
- ne récupère pas le texte intégral des décisions CETAT ;
- ne déploie pas la migration ni l'import ;
- ne vérifie pas les identifiants PISTE, la base réelle, les droits SQL, la RLS ou les sauvegardes.

Le développeur doit appliquer la migration en environnement de test, lancer l'import en mode contrôlé, vérifier le compte de lignes, tester la recherche, puis exécuter les tests PostgreSQL/RLS avant toute mise en production.
