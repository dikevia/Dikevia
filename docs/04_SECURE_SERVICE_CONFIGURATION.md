# Configuration sécurisée des services Dikévia

Ce document liste les variables nécessaires à l'exploitation. **Aucune valeur secrète ne doit être inscrite dans Git, dans ce document ou dans une archive de sauvegarde.**

## API commerciale — Render

À conserver dans les variables d'environnement du service API :

- `AI_API_KEY` : clé du fournisseur d'inférence configuré.
- `AI_API_BASE_URL` : endpoint du fournisseur compatible OpenAI configuré pour Dikévia.
- `AI_MODEL` : modèle effectivement autorisé par le fournisseur. La configuration du dépôt utilise actuellement `gpt-5-mini`.
- `LEGIFRANCE_CLIENT_ID` : identifiant OAuth PISTE pour l'environnement sandbox.
- `LEGIFRANCE_CLIENT_SECRET` : secret OAuth PISTE correspondant.
- `LEGIFRANCE_ENVIRONMENT=sandbox` : ne pas basculer en production avant validation contractuelle et autorisation.

Les deux variables PISTE doivent provenir d'une **nouvelle paire de credentials**. Ne pas réutiliser une valeur précédemment partagée dans une conversation ou un dépôt. Tant que les deux credentials ne sont pas valides, les recherches officielles Légifrance ne sont pas disponibles et le chatbot doit s'abstenir de conclure.

Le fournisseur IA actuellement configuré est le fournisseur compatible OpenAI relié à la passerelle IA Neon. Gemini n'est pas activé dans l'environnement courant. Tout changement de fournisseur doit être suivi d'un test réel du mode JSON structuré et de la validation des citations.

## Keycloak — Render

- `KC_BOOTSTRAP_ADMIN_USERNAME`
- `KC_BOOTSTRAP_ADMIN_PASSWORD`

Le mot de passe d'administration doit rester dans Render. Ne jamais le copier dans le dépôt ou dans l'APK.

## Neon

Les chaînes de connexion, clés d'API et identifiants de stockage doivent rester dans les variables secrètes du service concerné. Les sauvegardes du code ne contiennent pas les données de la base.

## Vérifications avant bêta

- Tester l'authentification avec un vrai compte utilisateur, puis l'accès à une route protégée.
- Vérifier que les trois familles de recherches juridiques sont disponibles : CGFP, textes Légifrance et jurisprudence.
- Activer la consultation intégrale des décisions uniquement après validation du contrat d'API et des credentials.
- Vérifier l'inférence réelle du fournisseur IA, puis tester les réponses JSON, les citations exactes et les abstentions.
- Conserver la limite bêta d'un seul compte jusqu'à décision explicite contraire.

## Règles de sécurité

1. Ne jamais committer de secrets, même temporairement.
2. Ne jamais placer de secrets dans l'APK, le frontend ou un fichier de configuration public.
3. Toute clé précédemment exposée doit être révoquée et remplacée.
4. Toute modification de secrets doit être faite dans le coffre de variables d'environnement du service concerné.
5. En cas de source juridique indisponible ou non vérifiable, le chatbot doit afficher une abstention explicite.
