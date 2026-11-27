# Dikévia Android — état actuel et trajectoire native

## État réel de `main`

Les deux variantes Android actuellement présentes (`standard` et `admin`) sont des **conteneurs Android WebView** qui chargent le frontend web depuis Render. Elles ne constituent pas encore des applications Android natives.

- `standard` : package `fr.dikevia.commercial`, avec suffixe `.beta` en debug.
- `admin` : package `fr.dikevia.admin`, avec suffixe `.beta` en debug.
- Les deux variantes chargent actuellement le même hôte staging Render, avec un paramètre de mode différent.
- La liste des hôtes de confiance a été réduite à l'hôte staging actif et à l'issuer Auth0 de développement. Les anciens hôtes Render API et Keycloak ne sont plus autorisés à rester dans la WebView.
- Le flux Auth0 dans la WebView n'est pas validé sur appareil réel.

Le fait de disposer de deux APK ne signifie donc pas que les interfaces sont natives. Ne pas annoncer une application Android native terminée.

## Direction produit

Dikévia doit être une application Android et iOS native en priorité. Le web reste une interface complémentaire. L'édition standard contient l'assistant juridique conversationnel ; l'édition Administration est dédiée au pilotage et ne doit pas exposer le chatbot agent.

La référence visuelle est JURIS, documentée dans [l'identité visuelle JURIS](../docs/60_IDENTITE_VISUELLE_JURIS.md). Ne pas réintroduire l'identité Émeraude & Or.

## Prototype natif historique — non intégrable tel quel

La branche historique `android/native-compose-integration` contient un prototype Kotlin + Jetpack Compose. Elle fournit des éléments réutilisables à auditer : navigation, écrans, appels API, client HTTP, OIDC AppAuth/PKCE et composants Compose.

Elle ne peut pas être fusionnée directement :
- URL API codée en dur vers l'ancien service Render ;
- issuer Keycloak codé en dur ;
- client OIDC Keycloak et scopes anciens ;
- palette Émeraude & Or explicitement abandonnée ;
- une seule activité monolithique d'environ 500 lignes ;
- aucune preuve que les endpoints utilisés correspondent tous aux contrats actuels de `main`.

Le prototype doit être traité comme une référence de composants et de flux, pas comme une base de livraison. Toute récupération doit adapter Auth0, les contrats API, l'identité JURIS et les éditions standard/administration.

## Construction actuelle

Depuis `android/`, avec Java 17 et Android SDK :

```bash
gradle --no-daemon :app:assembleStandardDebug :app:assembleAdminDebug
```

Le build ne prouve ni la conformité native, ni la connexion Auth0 sur appareil réel, ni la disponibilité des fonctions backend.

## Conditions préalables à une livraison native

- Auth0 Authorization Code + PKCE, client public natif et Universal Login via navigateur système/AppAuth ou SDK officiel approprié ; aucun secret client dans l'application.
- URI de redirection et logout propres à chaque application, configurées dans Auth0.
- Base URL API injectée par configuration de build/environnement, jamais ancienne URL Render codée en dur.
- Jetons stockés selon les recommandations de sécurité Android/iOS, pas dans les logs ni les préférences non chiffrées.
- Contrats API vérifiés contre `main`, autorisations contrôlées côté serveur.
- Sphère JURIS intégrée à l'expérience standard et réagissant uniquement à des états réellement émis par l'application/backend.
- Interface Administration séparée du parcours agent, sans chatbot conversationnel.
- Tests unitaires, tests UI, tests OIDC, tests API, accessibilité et essais sur appareils physiques.
- Signature de production et secrets conservés hors Git.

Aucun déploiement, publication, dépense ou migration de fournisseur n'est autorisé par cette documentation.


## Auth0 natif Android — première intégration sur `main`

Le module `core/auth/Auth0NativeAuth.kt` utilise le SDK officiel Auth0.Android **3.21.3** avec le flux natif Authorization Code + PKCE, Universal Login et le navigateur système. La branche v3 est conservée car le projet prend en charge Android API 24 ; la branche SDK v4 exige API 26 minimum.

Le module utilise `SecureCredentialsManager` avec un stockage chiffré adossé à Android Keystore. Aucun contrôle biométrique n'est imposé à chaque ouverture. Il ne journalise ni jeton ni code d'autorisation et ne contient aucun secret client.

### Configuration locale du Client ID

Le Client ID Auth0 natif Android n'est pas encore créé dans le tenant. Le Client ID SPA web ne doit pas être réutilisé. Après création de l'application Native Android dans Auth0, injecter le Client ID public localement :

```bash
cd android
gradle --no-daemon -Pauth0AndroidClientId=VOTRE_CLIENT_ID_NATIVE :app:assembleStandardDebug
```

Ne pas committer le Client ID réel dans le dépôt. La propriété Gradle peut être conservée dans `~/.gradle/gradle.properties` sous la forme `auth0AndroidClientId=...`. Ce Client ID est une donnée publique d'application native, contrairement à un secret client qui ne doit jamais exister dans le binaire.

Le domaine de développement configuré est `dev-brlgaz1yh2de3mjo.us.auth0.com`, l'audience API est `https://api.dikevia.fr`, et les scopes demandés sont `openid profile email offline_access`. Le renouvellement de session exige que l'autorisation `offline_access` et la rotation des refresh tokens soient activées et vérifiées côté Auth0 avant recette.

### URI Auth0 à autoriser

Le SDK génère le callback selon le package effectif de chaque variante. Ajouter les quatre URI ci-dessous dans **Allowed Callback URLs** et **Allowed Logout URLs** du client Native Android :

```text
https://dev-brlgaz1yh2de3mjo.us.auth0.com/android/fr.dikevia.commercial/callback
https://dev-brlgaz1yh2de3mjo.us.auth0.com/android/fr.dikevia.commercial.beta/callback
https://dev-brlgaz1yh2de3mjo.us.auth0.com/android/fr.dikevia.admin/callback
https://dev-brlgaz1yh2de3mjo.us.auth0.com/android/fr.dikevia.admin.beta/callback
```

Le SDK doit également être autorisé à demander un access token pour l'audience `https://api.dikevia.fr`. Ne pas ajouter de wildcard aux URI de callback ou de logout.

### Limites avant activation

- Le module d'authentification est ajouté, mais le point d'entrée de l'application reste la WebView pour conserver un chemin de repli.
- L'écran Compose de prévisualisation n'est pas encore l'écran de lancement distribué.
- Le Client ID natif et ses URI ne sont pas encore enregistrés/confirmés dans le tenant Auth0.
- Le client API natif n'est pas encore raccordé. Une authentification réussie ne doit pas encore débloquer artificiellement l'envoi de questions JURIS.
- Le workflow CI actuel ne compile pas Android ; un build Gradle Android dédié reste à mettre en place et à faire passer avant de remplacer le point d'entrée.
- La validation finale doit inclure un aller-retour Auth0 sur appareil Android physique, restauration/expiration de session, logout, puis appel réel au backend avec access token et ID token conformément au contrat serveur.
