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
