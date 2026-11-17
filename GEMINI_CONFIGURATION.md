# Configuration de Gemini pour Dikévia

## Principe

Le backend Dikévia possède déjà un adaptateur serveur compatible avec le format OpenAI Chat Completions. Gemini peut donc être utilisé sans exposer la clé dans le navigateur.

Variables à configurer uniquement dans l'environnement serveur :

```dotenv
AI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_API_KEY=<secret Gemini API>
AI_MODEL=gemini-3.8-flash
AI_TIMEOUT_SECONDS=25
```

Le modèle doit être choisi parmi ceux effectivement disponibles pour le projet Google AI Studio. L'identifiant ci-dessus est un exemple issu de la documentation Google, pas une garantie de disponibilité permanente.

L'adaptateur envoie une requête vers `/chat/completions` et utilise `Authorization: Bearer`, conformément au point de terminaison de compatibilité Gemini. La clé reste côté serveur : ne jamais la mettre dans le frontend, dans Git ou dans un message.

## Confidentialité et zone EEE

Dikévia est destiné notamment à des utilisateurs en France/EEE. Les conditions supplémentaires Gemini consultées indiquent que seuls les services payants peuvent être utilisés lorsqu'une API est mise à disposition d'utilisateurs dans l'EEE. En conséquence :

- le quota gratuit peut servir uniquement à des essais internes et privés du développeur, avec des données entièrement fictives ;
- ne pas déployer une version accessible à des utilisateurs de l'EEE en s'appuyant sur le service gratuit ;
- avant toute ouverture à des utilisateurs, activer un service payant et vérifier les conditions contractuelles et RGPD applicables ;
- même avec un service payant, ne pas promettre une absence totale de conservation : Google décrit une journalisation limitée pour la surveillance des abus.

Un avertissement demandant de ne saisir aucun nom ne suffit pas à rendre un traitement de données personnelles conforme. Pour les essais, ne transmettre aucun nom, prénom, matricule, adresse, nom de collectivité/service, donnée médicale, disciplinaire, syndicale nominative, ni fait réel permettant d'identifier quelqu'un. Utiliser exclusivement des situations fictives et génériques.

## Limites juridiques du moteur actuel

Gemini ne constitue pas une source juridique. Le backend doit récupérer et contrôler les textes avant de lui demander une analyse. Le modèle ne doit pas créer de références : les citations affichées restent celles du backend.

L'orchestrateur suspend actuellement l'analyse IA si la date des faits n'est pas fournie. Il exclut aussi le snapshot CGFP seul des sources transmises au modèle. Il faut donc une date des faits et au moins une source éligible, datée et contrôlée (par exemple via Légifrance/PISTE ou le corpus juridique validé). Si ces conditions ne sont pas réunies, Dikévia reste en mode documentaire et ne produit pas d'analyse IA.

## Configuration Render

Ajouter les variables ci-dessus dans les variables d'environnement privées du service API Render. Ne jamais les ajouter au dépôt GitHub ni à une variable frontend. Après enregistrement, redémarrer/redéployer le service et vérifier les journaux sans jamais afficher la valeur de `AI_API_KEY`.

## Références Google

- Compatibilité OpenAI : https://ai.google.dev/gemini-api/docs/openai
- Tarification et différences entre services gratuits et payants : https://ai.google.dev/gemini-api/docs/pricing
- Conservation et surveillance des abus : https://ai.google.dev/gemini-api/docs/usage-policies
- Conditions supplémentaires : https://ai.google.dev/gemini-api/terms
