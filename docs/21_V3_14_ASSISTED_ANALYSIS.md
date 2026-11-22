# V3.14 — Adaptateur IA facultatif et analyse assistée

Le backend peut désormais appeler un fournisseur compatible avec l'API OpenAI Chat Completions. La configuration est facultative : sans `AI_API_BASE_URL`, `AI_API_KEY` et `AI_MODEL`, le service reste en mode recherche documentaire CGFP.

## Configuration

Renseigner les trois variables dans `.env` :
- `AI_API_BASE_URL` : origine ou base `/v1` du fournisseur ;
- `AI_API_KEY` : secret privé, jamais intégré au frontend ni au dépôt ;
- `AI_MODEL` : identifiant du modèle choisi.
- `AI_TIMEOUT_SECONDS` : délai maximal, entre 2 et 120 secondes.

En production, l'URL doit être HTTPS. Le fournisseur doit être validé contractuellement et au regard du RGPD avant utilisation de données personnelles. Pour le pilote, ne transmettre aucune donnée nominative, médicale ou confidentielle.

## Fonctionnement

1. Le backend recherche les articles dans l'index CGFP.
2. Il vérifie de manière déterministe les références, pages et extraits.
3. Seuls les extraits ayant passé ces contrôles sont transmis au modèle.
4. Le modèle produit une analyse structurée en français, en distinguant faits, hypothèses et éléments manquants.
5. Les citations exposées restent celles établies par le backend ; le modèle ne peut pas créer une nouvelle source.
6. Le statut demeure `PARTIELLEMENT_VERIFIE` : le modèle ne valide ni l'authenticité officielle, ni la version historique, ni les textes locaux ou la jurisprudence.

## Limites

- Ce connecteur est OpenAI-compatible ; la compatibilité réelle dépend du fournisseur choisi.
- Aucun secret API n'est fourni dans le kit.
- L'analyse IA ne remplace pas Légifrance/PISTE, la constitution du corpus territorial ou la validation juridique humaine.
- Les documents et extraits transmis au modèle sont traités comme données non fiables, jamais comme instructions.

## Interface utilisateur

Le formulaire de question accepte désormais une date calendrier (format ISO transmis à l'API). Après réponse, l'interface affiche le statut, le texte d'analyse, les articles, les pages PDF, les extraits et les vérifications manquantes. Le bouton est désactivé pendant le traitement.


## Contrôle des références générées — V3.15

Le backend extrait les références d'articles présentes dans la réponse générée et les compare à la liste des références réellement récupérées. Une réponse comportant un numéro d'article absent du corpus transmis, un article numérique non sourcé ou une référence numérotée à un autre type d'acte (décret, loi, arrêté, ordonnance, circulaire, décision) est écartée. Ce contrôle réduit les citations fabriquées mais ne prouve pas l'exactitude de l'analyse ni l'absence d'autres erreurs factuelles.
