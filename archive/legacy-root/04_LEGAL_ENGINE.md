# 04 — Moteur juridique, sources et IA

## 1. Ordre d'exécution obligatoire
1. Valider utilisateur, organisation et permissions.
2. Valider et normaliser la question.
3. Détecter les données identifiantes/sensibles et demander anonymisation si nécessaire.
4. Identifier thème, employeur, statut si fourni, date/période des faits.
5. Si un fait déterminant manque, poser une question courte avant de conclure.
6. Rechercher dans les sources nationales.
7. Rechercher le corpus local du bon employeur et du bon tenant.
8. Récupérer les textes et passages intégraux nécessaires, pas seulement les snippets.
9. Déterminer la version applicable à la date des faits.
10. Dédupliquer et qualifier chaque source.
11. Appeler le modèle avec les seules sources retenues et une consigne stricte.
12. Extraire les citations structurées et les valider côté serveur.
13. Calculer le statut de vérification à partir des résultats techniques, pas du jugement du modèle.
14. Retourner réponse + sources + limites.
15. Purger les données temporaires.

## 2. Sources nationales
Source prioritaire : API Légifrance via PISTE. Documentation à consulter :
- https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api
- https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api
- https://piste.gouv.fr/

Le développeur doit utiliser le Swagger de production au moment de l'intégration pour confirmer endpoints, scopes, fonds, filtres temporels, pagination, quotas et modalités OAuth2. Ne pas utiliser d'URL d'API supposée. Les secrets restent côté serveur.

## 3. Corpus local
Collectivités initiales :
- Ville de Saint-Étienne : https://publi-actes.saint-etienne.fr/
- Saint-Étienne Métropole : https://www.saint-etienne-metropole.fr/

Les liens de délibérations repérés antérieurement sont des pistes, pas des actes validés. Chaque document doit être vérifié, accompagné de ses annexes, dates d'effet, chaîne de modification et empreinte SHA-256.

Statuts documentaires :
`TO_COLLECT`, `COLLECTED_UNVERIFIED`, `VERIFIED_APPLICABLE`, `VERIFIED_HISTORICAL`, `REPEALED`, `REPLACED`, `INCOMPLETE`.

Seul un document `VERIFIED_APPLICABLE` ou `VERIFIED_HISTORICAL` dans la bonne période peut être utilisé comme acte local probant. Le référent documentaire humain approuve ce statut.

## 4. Jurisprudence
Ne pas promettre l'exhaustivité des TA/CAA. Définir le périmètre selon les bases officielles accessibles et testées. Chaque décision doit être récupérée depuis une source vérifiable, avec juridiction, date, numéro, URL et portée. Sinon ne pas la citer.

## 5. Statut de vérification
- `VERIFIE` : sources déterminantes récupérées, source/texte/versions contrôlés, références validées.
- `PARTIELLEMENT_VERIFIE` : sources pertinentes mais éléments manquants, version historique non confirmée ou acte local incomplet.
- `NON_VERIFIE` : aucune source suffisante, erreur de connecteur, absence de version ou échec de validation.

Le modèle ne choisit pas seul le statut.

## 6. Format d'appel IA
Le modèle reçoit un paquet JSON composé de `question_anonymisee`, `date_faits`, `employeur`, `sources[]` et `consignes`. Chaque source inclut `source_id`, `source_type`, `title`, `url`, `version_from`, `version_to`, `retrieved_at`, `passages[]`.

Le modèle doit retourner une structure JSON conforme au schéma API. Il doit référencer les sources par `source_id` uniquement. Toute source inconnue entraîne rejet/contrôle.

## 7. Prompt système
Voir `config/system_prompt_fpt.md`. Le prompt protège contre l'injection d'instructions dans les documents, mais le contrôle technique des citations reste obligatoire.

### Fonction CGFP livrée en V3.11
Le backend dispose d'une recherche lexicale locale dans un index article/page construit à partir du snapshot CGFP livré. Les articles détectés sont retournés avec leur page PDF et un extrait. Cette recherche est utilisée par `chat/ask` et disponible via `/api/v1/legal/cgfp/search`. Elle ne constitue pas une vérification juridique officielle : le moteur doit encore récupérer la version Légifrance applicable à la date des faits, contrôler les dispositions réglementaires et connexes, puis valider chaque référence.


## 8. Contrôle d'intégrité documentaire (V3.13)
Le backend contrôle les citations CGFP avant de les exposer : référence d'article, identifiant de source, pages et présence de l'extrait dans le texte intégral indexé. Ce contrôle empêche une référence ou un extrait fabriqué de passer comme citation du snapshot. Il ne constitue pas une validation officielle ni temporelle. La date des faits doit être fournie en format ISO `AAAA-MM-JJ`; une date ambiguë est refusée.
