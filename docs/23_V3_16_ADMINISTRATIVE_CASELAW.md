# V3.16 — Recherche de jurisprudence administrative (CETAT)

## Périmètre livré

JURIS interroge désormais le fonds `CETAT` de l’API stable Légifrance/PISTE, en réutilisant l’authentification OAuth2 serveur déjà présente en V3.15.

La requête utilise le fonds `CETAT`, recherche les mots de la question dans le champ `ALL`, limite les décisions à celles dont la date est antérieure ou égale à la date des faits (ou à la date de repérage si elle est absente), et limite la première page à 10 résultats. Seuls les identifiants de décision au format `CETATEXT` reconnus sont conservés. Les doublons sont écartés et seules les métadonnées explicitement renvoyées par l’API sont exposées.

Route authentifiée de recherche directe : `GET /api/v1/legal/jurisprudence/administrative/search?q=...&effective_date=AAAA-MM-JJ`.\n\nLes résultats sont ajoutés aux sources documentaires de la réponse. L’interface affiche la date, le numéro d’affaire lorsqu’il est fourni, l’identifiant et le lien de consultation.

## Limites juridiques importantes

Cette évolution réalise une **recherche de jurisprudence administrative**, pas encore la récupération et la vérification du texte intégral des décisions. Le contenu éventuellement renvoyé dans le résultat de recherche est traité comme un extrait, jamais comme le texte intégral.

Les décisions CETAT ne sont pas transmises au fournisseur IA dans cette version. Elles sont affichées comme pistes de recherche pour éviter qu’une analyse soit présentée comme fondée sur un arrêt dont le texte intégral n’a pas été contrôlé.

Le statut de l’analyse reste `PARTIELLEMENT_VERIFIE` lorsque des dispositions législatives ou réglementaires exploitables sont présentes. Une recherche CETAT seule ne suffit pas à produire une conclusion juridique. L’absence de résultat ne démontre jamais l’absence de jurisprudence.

## Tests et recette

Les tests automatisés couvrent le fonds demandé, le filtre temporel, la validation des identifiants, le dédoublonnage, les métadonnées et les entrées invalides.

La recette réelle exige des identifiants PISTE ayant accès à l’API Légifrance, l’acceptation des CGU, l’activation de l’API sur l’application PISTE et des tests en sandbox puis en production. Aucune connexion réelle PISTE n’est revendiquée ici.

Référence de la requête CETAT : FAQ officielle API Légifrance, section 10 « Recherche dans la jurisprudence administrative » :
https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api
