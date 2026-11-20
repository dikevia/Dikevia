# Dikévia Android native beta

Cette branche remplace l'ancienne enveloppe WebView par une application Android native Kotlin + Jetpack Compose.

## Architecture actuelle

- Interface native Compose : connexion, accueil, assistant, historique, documents, collectivités, membres et profil.
- Authentification : OpenID Connect Authorization Code + PKCE via AppAuth, dans le navigateur système.
- API : HTTPS vers l'API commerciale, jeton Bearer et en-tête `X-Organization-ID`.
- Le serveur reste l'autorité pour vérifier l'identité, l'appartenance à l'organisation et les permissions.
- Les jetons d'accès, d'identité et de renouvellement restent en mémoire uniquement ; ils ne sont pas écrits dans les préférences ni dans les fichiers de l'application. Le renouvellement automatique est tenté avant expiration lorsque Keycloak fournit un refresh token.
- Les documents sont affichés en métadonnées uniquement dans cette première étape ; aucun fichier non validé n'est téléchargé.
- Palette Emerald & Gold définie dans la spécification de design du dépôt.

## Configuration OIDC indispensable avant un vrai test de connexion

Le code utilise actuellement les valeurs suivantes :

- Issuer : `https://dikevia-identity-l2r8.onrender.com/realms/cfdt`
- Client public : `dikevia-android`
- Redirect URI de connexion : `fr.dikevia.commercial:/oauth2redirect`
- URI de retour après déconnexion à autoriser dans l'attribut client Keycloak `post.logout.redirect.uris` : `fr.dikevia.commercial:/oauth2redirect`
- Flow : Authorization Code + PKCE S256 ; aucun secret client ne doit être créé ou embarqué.
- Scopes demandés : `openid` uniquement, car les scopes `profile` et `email` ne sont pas provisionnés sur le realm actuel.

**Le client `dikevia-android` et son audience API n'ont pas été confirmés comme configurés dans Keycloak.** Avant le test de connexion, un administrateur Keycloak doit créer/configurer un client public dédié avec PKCE S256, cette URI de redirection exacte, et un mapper/audience qui fait apparaître l'audience attendue par l'API dans le jeton d'accès. Ne pas réutiliser le client navigateur `cfdt-juris-web` et ne pas ajouter de secret dans l'APK.

Le jeton doit satisfaire les contrôles backend existants : issuer, signature, expiration, algorithmes autorisés et audience. Le backend reste inchangé par cette branche.

## Compilation

Depuis `android/` avec Java 17 et Android SDK installés :

```bash
gradle --no-daemon :app:assembleDebug
```

L'APK debug utilise le package `fr.dikevia.commercial.beta`. Il s'agit d'un build de test, pas d'une version Play Store.

## Limites connues de cette première livraison native

- La session n'est pas restaurée après fermeture complète de l'application ; il faut se reconnecter.
- La déconnexion efface immédiatement les jetons locaux et tente de terminer la session OIDC via l'endpoint de fin de session du fournisseur. Le résultat réel dépend de la configuration Keycloak hébergée.
- L'historique permet de consulter les messages et de reprendre une conversation ; le contexte antérieur est rechargé par le serveur lors de la question suivante.
- L'assistant affiche le statut de vérification, les informations manquantes, les sources et les extraits disponibles ; il prend en charge les dates de situation, le caractère toujours en cours et le choix d'une collectivité.
- Les documents restent consultables en métadonnées uniquement, sans téléchargement avant validation antivirus.
- L'écran Membres dépend du rôle ORG_ADMIN et affiche l'erreur 403 pour les autres rôles.
- La compilation APK et le test Compose sur émulateur sont exécutés par GitHub Actions. La connexion OIDC réelle, les appels API avec un compte autorisé et les essais sur appareil physique restent des validations manuelles indispensables avant diffusion.

Aucune migration de base, modification de configuration hébergée, dépense, fusion ou mise en production n'est effectuée par cette branche.


Le workflow de génération APK se déclenche sur les modifications de cette branche et sur les mises à jour de la PR vers la branche d'intégration. Consulter l'onglet Actions du dépôt ; ne pas installer ni distribuer l'APK avant validation du build.
