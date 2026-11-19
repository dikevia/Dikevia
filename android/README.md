# Dikévia Android native beta

Cette branche remplace l'ancienne enveloppe WebView par une application Android native Kotlin + Jetpack Compose.

## Architecture actuelle

- Interface native Compose : connexion, accueil, assistant, historique, documents, collectivités, membres et profil.
- Authentification : OpenID Connect Authorization Code + PKCE via AppAuth, dans le navigateur système.
- API : HTTPS vers l'API commerciale, jeton Bearer et en-tête `X-Organization-ID`.
- Le serveur reste l'autorité pour vérifier l'identité, l'appartenance à l'organisation et les permissions.
- Le jeton d'accès est conservé en mémoire uniquement ; il n'est pas écrit dans les préférences ni dans les fichiers de l'application.
- Les documents sont affichés en métadonnées uniquement dans cette première étape ; aucun fichier non validé n'est téléchargé.
- Palette Emerald & Gold définie dans la spécification de design du dépôt.

## Configuration OIDC indispensable avant un vrai test de connexion

Le code utilise actuellement les valeurs suivantes :

- Issuer : `https://dikevia-identity-l2r8.onrender.com/realms/cfdt`
- Client public : `dikevia-android`
- Redirect URI : `fr.dikevia.commercial:/oauth2redirect`
- Flow : Authorization Code + PKCE S256 ; aucun secret client ne doit être créé ou embarqué.

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
- La déconnexion locale efface le jeton en mémoire ; la fermeture de session Keycloak reste à intégrer.
- L'historique permet de rouvrir une conversation et d'afficher ses messages ; une nouvelle question peut démarrer depuis l'assistant avec un contexte de conversation conservé pendant l'écran actif.
- L'assistant prend en charge les dates de situation, le caractère toujours en cours et le choix d'une collectivité ; les documents restent consultables en métadonnées uniquement, sans téléchargement avant validation antivirus.
- L'écran Membres dépend du rôle ORG_ADMIN et affiche l'erreur 403 pour les autres rôles.
- Les tests de compilation, de connexion OIDC et sur appareil physique doivent être observés avant de déclarer la bêta prête.

Aucune migration de base, modification de configuration hébergée, dépense, fusion ou mise en production n'est effectuée par cette branche.


Build trigger: cette branche native est incluse dans le workflow de génération de l'APK debug ; consulter l'onglet Actions du dépôt pour le résultat de compilation avant installation.


La branche d'intégration native est construite par GitHub Actions lors des modifications Android. Le résultat doit être contrôlé dans Actions avant toute installation.
