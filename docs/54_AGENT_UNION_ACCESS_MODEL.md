> **NOTE DE VERSION.** Le modèle Agent/Syndicat et les droits décrits ici restent la référence commerciale. Les premières descriptions d'implémentation des instances sont dépassées par `docs/55_CST_TOPIC_QUALIFICATION.md` et `docs/56_CAP_CCP_QUALIFICATION.md`. Pour l'état et les limites actuelles, utiliser `docs/57`.

# Dikévia — modèle Agent / Syndicats

## Catalogue public cible

Le catalogue public ne comporte plus que deux catégories :

- `AGENT_5_QUESTIONS` : un accès, 5 € TTC/mois, chatbot juridique uniquement, cinq questions par jour civil selon le fuseau Europe/Paris.
- `SYNDICAT_5_ACCES`, `SYNDICAT_10_ACCES`, `SYNDICAT_15_ACCES` : 5, 10 ou 15 accès, toutes les fonctionnalités, sans quota quotidien de questions. Les prix de ces trois formules restent à fixer et ne sont donc pas renseignés dans le catalogue.

Aucune offre de collectivité n'est commercialisée. Les collectivités restent des périmètres documentaires possibles dans le travail syndical, pas des clients ou des catégories d'abonnement.

## Droits et sécurité

Les droits sont calculés côté serveur à partir du code d'abonnement et de son statut. Seuls les codes syndicaux actuels avec un abonnement `ACTIVE` ou `TRIAL` ouvrent les fonctionnalités syndicales. Les comptes Agent, les abonnements inactifs et les anciens codes sont limités au chatbot et au quota quotidien. L'accès fondateur vérifié conserve son droit premium.

Le quota Agent est stocké dans `chat_daily_question_usage`, isolé par organisation et utilisateur avec RLS activée et forcée. Le compteur ne conserve aucun contenu de question. La journée est calculée selon `Europe/Paris`.

La limitation technique anti-abus par minute reste distincte du quota commercial. Les abonnements syndicaux ne sont pas soumis au quota quotidien.

Les routes documentaires, de recherche juridique autonome, de gestion des périmètres, des membres, des invitations, des dossiers et de préparation des instances sont protégées côté serveur par l'éligibilité syndicale.

## Préparation des instances — première version

L'endpoint `POST /api/v1/instances/{CST|CAP|CCP|FS}/prepare` produit une liste de questions et de documents à demander à partir d'un texte descriptif. Il est réservé aux abonnements syndicaux.

Cette première version est un aide-mémoire lexical, pas une analyse juridique. Elle ne détermine ni la compétence d'une instance, ni une consultation obligatoire, ni la légalité d'une décision, ni un délai statutaire. Les références du prototype initial n'ont pas été reprises parce qu'elles nécessitent une vérification juridique article par article et dans leur version applicable.

Les prochaines évolutions devront relier ces fiches aux documents fournis, au moteur de recherche juridique et aux sources officielles, avec traçabilité et tests de non-régression.

## Facturation

La facturation et le checkout restent désactivés. Les offres syndicales ne sont pas achetables tant que leurs prix ne sont pas fixés et que la facturation n'a pas été validée. Les anciens codes sont conservés uniquement pour lire les abonnements historiques ; ils ne sont plus publiés ni achetables et ne donnent pas accès aux nouveaux outils syndicaux.
