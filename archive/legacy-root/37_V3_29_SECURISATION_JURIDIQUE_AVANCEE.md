# V3.29 — Sécurisation juridique avancée

## Objectif

La V3.29 renforce le RAG fermé sans prétendre rendre toute erreur impossible. Elle organise la qualification des sources, signale les situations nécessitant une comparaison et fournit un premier parcours de revue des documents propres à une collectivité.

## 1. Qualification des sources et hiérarchie

`backend/app/legal_assurance.py` classe les familles de sources (code, loi, ordonnance, décret, arrêté, jurisprudence, circulaire, délibération, règlement local, protocole local). Le classement produit une famille, un libellé, une priorité indicative de revue et un indicateur de statut temporel/validation.

Ce classement n'est **pas** un moteur juridictionnel de résolution des conflits. Il ne suffit pas de comparer des nombres de priorité ni de retenir le texte le plus récent. Le champ d'application, la spécialité, les dispositions transitoires, la date des faits, la portée de la jurisprudence et la compétence de l'auteur doivent être étudiés.

Les réponses de l'assistant incluent désormais `legal_assurance` pour chaque source affichée. Les sources au statut temporel incomplet ou non validées ne sont pas marquées comme utilisables pour conclure.

## 2. Revue d'une règle locale

Nouvelle route authentifiée :

`POST /api/v1/legal/compliance/review/{document_id}?q=...&effective_date=YYYY-MM-DD`

La route :
- vérifie que le document appartient à l'organisation active ;
- exige un scan antivirus `CLEAN` et une extraction textuelle `EXTRACTED` ;
- charge le texte local extrait depuis le périmètre de l'organisation ;
- recherche les textes nationaux dans le corpus partagé ;
- exclut des propositions IA les métadonnées seules et les versions non exploitables à la date demandée ;
- conserve une trace dans `audit_events` ;
- renvoie les sources nationales, les avertissements, les limites et, si disponible, une revue IA préliminaire contrôlée.

La route ne conclut jamais automatiquement à la légalité ou à l'illégalité d'un acte. `COMPARISON_REQUIRED` signifie qu'une comparaison humaine est requise, pas qu'une contradiction a été démontrée. `NATIONAL_SOURCES_NOT_FOUND` ne prouve pas la conformité.

L'interface Documents ajoute un bouton « Contrôler » et une zone de saisie du point de droit à examiner.

## 3. Fraîcheur et veille

Nouvelle route plateforme :

`GET /api/v1/platform/legal-corpus/freshness`

Elle expose les dernières exécutions d'ingestion et l'inventaire du corpus (source, statut, dernière détection). Elle est réservée aux administrateurs plateforme.

Un script d'exécution périodique est fourni :

```bash
JURIS_API_URL=https://juris.example.fr \
JURIS_PLATFORM_ADMIN_TOKEN='...' \
bash scripts/run_legal_watchlist.sh
```

La liste de requêtes est dans `scripts/legal_watchlist.example`. L'exploitant doit définir ses propres requêtes et planifier le script avec cron ou systemd, protéger le jeton, surveiller les erreurs et contrôler les imports. Cette automatisation ne couvre que l'import ciblé des textes réglementaires Légifrance via la route existante. Elle ne constitue pas une veille exhaustive, ni une surveillance automatique de toutes les jurisprudences, circulaires ou modifications de tous les actes locaux.

## 4. Règles de sécurité et limites

- Les documents locaux restent isolés par organisation via les requêtes tenant-scoped et les politiques RLS existantes.
- Le texte local n'est transmis au fournisseur IA que dans le cadre d'une revue explicitement demandée par un utilisateur authentifié ; vérifier les conditions contractuelles et la politique de données du fournisseur avant production.
- Les extraits nationaux transmis à l'IA doivent être des textes intégraux indexés, avec intégrité de citation valide et statut temporel admissible.
- Les références juridiques produites sont contrôlées contre les références récupérées ; une sortie non ancrée est écartée.
- La revue IA demeure indicative et ne constitue pas un avis juridique certifié.

## 5. Vérifications

Tests unitaires : `backend/tests/test_v329_legal_assurance.py` (classement local, comparaison locale/nationale, date incomplète).

À réaliser sur staging : tests d'accès croisé entre organisations, document antivirus non propre, document sans extraction, corpus vide, versions abrogées, date d'effet, import Légifrance, droits administrateur de la route de fraîcheur, et vérification du comportement du fournisseur IA. La veille planifiée doit être supervisée en exploitation.
