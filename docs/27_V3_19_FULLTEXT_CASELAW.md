# V3.19 — Consultation du texte intégral des décisions administratives

## Objectif
Permettre au moteur juridique de passer d'une simple fiche de résultat CETAT à la consultation du texte complet via l'API stable Légifrance/PISTE, sans confondre métadonnées et contenu intégral.

## API
- Recherche : `GET /api/v1/legal/jurisprudence/administrative/search?q=...&effective_date=YYYY-MM-DD`
- Consultation : `GET /api/v1/legal/jurisprudence/administrative/{decision_id}`
- Appel fournisseur : `POST /consult/juri`, corps `{"textId":"<identifiant officiel>"}`.

## Contrôles
1. L'identifiant fourni doit respecter le format CETATEXT ou JURITEXT suivi de 12 chiffres.
2. L'identifiant retrouvé dans la réponse officielle doit correspondre exactement à l'identifiant demandé.
3. Un contenu textuel d'une longueur minimale est requis.
4. En cas d'identifiant absent, différent ou de contenu vide, l'API renvoie une indisponibilité et ne prétend pas avoir récupéré la décision.
5. Le HTML éventuel est converti en texte brut avant restitution ; il n'est jamais rendu comme HTML actif.

## Statuts
- `OFFICIAL_SEARCH_METADATA_ONLY` : métadonnées / extrait de recherche uniquement.
- `OFFICIAL_FULL_TEXT_ID_MATCHED` : consultation officielle, identifiant concordant et texte substantiel récupéré.
- `TEXTE_INTEGRAL_OFFICIEL_ID_VERIFIE` : statut de la route API correspondant au contrôle technique ci-dessus.

Ces statuts ne constituent pas une validation de la pertinence jurisprudentielle, de l'autorité de la décision, de son éventuel abandon ou revirement, de son caractère définitif, ni de l'état du droit à une date donnée. Ces analyses exigent des sources complémentaires et une validation dédiée.

## Tests
`PYTHONPATH=backend pytest -q backend/tests/test_administrative_jurisprudence.py backend/tests/test_legifrance_connector.py`

Les tests sont réalisés avec `httpx.MockTransport`. Une recette PISTE réelle reste nécessaire : identifiants sandbox, validation des CGU, test des méthodes disponibles, contrôle des quotas, puis application de production PISTE distincte.
