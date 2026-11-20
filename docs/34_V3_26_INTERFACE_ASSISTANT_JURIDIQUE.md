# V3.26 — Refonte de l'interface de question juridique

## Intégration
L'écran « Question juridique » de `frontend/index.html` adopte désormais une interface conversationnelle inspirée de la maquette fournie, en conservant l'identité visuelle et l'architecture CFDT JURIS existantes.

## Contrat backend conservé
- Authentification : module OIDC Authorization Code + PKCE déjà en place.
- Jeton : conservé en mémoire par `oidc-auth.js`, jamais demandé ni enregistré dans `localStorage` par l'interface.
- Organisation : `api()` transmet `Authorization: Bearer …` et `X-Organization-ID` depuis l'espace sélectionné.
- Analyse : `POST /api/v1/chat/ask` avec `{ employer, facts_date, question }` ; le champ `employer` est une valeur du contrat Pydantic existant.
- Réponse : affichage du `verification_status`, `answer`, `missing_information`, `disclaimer` et des `sources` réellement retournés par l'API.

## Corrections de sécurité et de fiabilité par rapport à la maquette Gemini
- Suppression de la configuration manuelle d'URL et de jeton API : l'interface utilise l'API relative du même domaine et le flux OIDC existant.
- Aucun jeton Bearer stocké dans `localStorage`.
- Suppression du mode simulation : si l'API est indisponible, l'interface affiche une erreur et ne fabrique jamais de réponse juridique.
- Aucun historique juridique n'est persisté dans le navigateur ; les échanges ne restent visibles qu'en mémoire jusqu'au rechargement.
- L'interface précise que l'historique visuel n'est pas envoyé comme contexte : chaque question reste une analyse indépendante conformément au contrat actuel.
- Réponses et extraits insérés via `textContent`, sans interprétation HTML/Markdown arbitraire.
- Liens de sources limités aux domaines officiels Légifrance en HTTPS, avec `rel="noopener noreferrer"`.
- Conservation de l'employeur et de la date des faits, du plafond de 5 000 caractères et de la validation minimale de 8 caractères du backend.
- Affichage des statuts `VERIFIE`, `PARTIELLEMENT_VERIFIE` et `NON_VERIFIE`, ainsi que des réserves et sources retournées.
- Interface responsive, suggestions de questions, compteur de caractères, envoi par Entrée et saut de ligne par Maj+Entrée.

## Limites connues
Cette version fournit un affichage conversationnel, pas une conversation IA multi-tours : le backend actuel n'accepte pas de tableau d'historique ou de `session_id` dans `AskRequest`. L'historique n'est pas sauvegardé et ne doit pas être présenté comme un dossier persistant. Le statut juridique affiché est celui renvoyé par le moteur ; il ne constitue pas une certification ou un avis juridique définitif.


> Évolution V3.27 : la limite de non-persistance décrite ci-dessus est remplacée par la persistance serveur cloisonnée des conversations, documentée dans `docs/35_V3_27_CONVERSATIONS_MULTI_TOURS.md`.
