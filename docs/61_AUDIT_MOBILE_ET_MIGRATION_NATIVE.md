# Dikévia — audit mobile et trajectoire de migration native

Date : 27 novembre 2026  
Référence : branche `main` et prototypes Android historiques  
Statut : audit de code, aucune migration mobile exécutée

## 1. Constat sur main

Le répertoire `android/` de `main` contient :
- une activité Android de 7,8 Ko basée sur `android.webkit.WebView` ;
- deux product flavors Gradle (`standard` et `admin`) qui chargent le même hôte staging avec des paramètres d'édition différents ;
- aucune dépendance Jetpack Compose ;
- aucun projet iOS (`ios/`, Xcode project ou Swift package) trouvé à la racine.

Le build Android actuel produit donc deux conteneurs WebView, pas deux applications mobiles natives.

La liste `TRUSTED_HOSTS` vérifiée dans `android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt` contient actuellement deux hôtes exacts : `dikevia-vector-beta-staging.onrender.com` et l'issuer Auth0 de développement `dev-brlgaz1yh2de3mjo.us.auth0.com`. Les anciens hôtes API Render et Keycloak ont été retirés de cette liste. Cette configuration reste provisoire : elle pointe vers le staging et devra être remplacée lorsque l'URL de l'unique service applicatif cible et les domaines Auth0 définitifs seront validés. Ne pas ajouter de wildcard.

## 2. Prototype Android Compose examiné

Branche : `android/native-compose-integration`.

Fichiers analysés :
- `android/app/build.gradle.kts` ;
- `android/settings.gradle.kts` ;
- `android/app/src/main/AndroidManifest.xml` ;
- `android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt` ;
- `android/README.md`.

Le prototype apporte une base de travail utile :
- Jetpack Compose / Material 3 ;
- AppAuth et Authorization Code + PKCE ;
- client HTTP OkHttp ;
- appels API Bearer ;
- composants et écrans pour connexion, assistant, historique, documents, collectivités, membres et profil ;
- quelques contrôles de durée de requête et de cycle de vie.

Mais il est impropre à une fusion directe :
- API codée en dur : `dikevia-commercial-api-l2r8.onrender.com` ;
- issuer codé en dur : `dikevia-identity-l2r8.onrender.com/realms/cfdt` (Keycloak) ;
- client `dikevia-android` lié à l'ancien fournisseur ;
- palette `Emerald & Gold` dans le code Kotlin, désormais abandonnée ;
- une activité monolithique d'environ 514 lignes qui concentre authentification, appels réseau et UI ;
- les jetons sont conservés en mémoire dans ce prototype et ne sont pas restaurés après fermeture complète ;
- scopes OIDC `openid` uniquement et audience API non confirmée dans la documentation de la branche.

La comparaison de cette branche avec `main` est très divergente (192 commits en avance et 2 130 en retard au moment de l'audit). Elle contient aussi une grande quantité de backend, migrations, corpus et configuration historique. Aucun merge global n'est acceptable.

Décision : réutiliser sélectivement les patterns Compose et les écrans après découpage, pas copier la branche ni son code d'authentification.

### Vérification des autres branches Android

- `android/native-compose-beta` : malgré son nom et ses dépendances Gradle Compose, le `MainActivity.kt` examiné instancie encore une `WebView`. Ce n'est pas une application native livrable. Les tests UI de cette branche concernent principalement le frontend web.
- `android/native-compose-beta-v2` : contient effectivement une UI Jetpack Compose, mais conserve les URL de l'ancienne API Render, l'issuer Keycloak et la palette Émeraude & Or abandonnée. Elle est moins complète que `android/native-compose-integration` et n'est pas intégrable telle quelle.
- `android/apk-auth0-staging` : reste également une WebView ; son contrôle Auth0 autorise tout sous-domaine `.auth0.com`, ce qui est plus large que la liste d'hôtes exacts de `main`. Aucun motif ne justifie de reprendre cette politique.

La comparaison actualisée de `android/native-compose-integration` avec `main` au moment de cet audit indique 192 commits propres et 2 159 commits de retard. Le diff couvre aussi de nombreux fichiers backend, migrations et corpus : cela confirme qu'une fusion globale serait inappropriée.

Aucune branche iOS n'a été trouvée avec la recherche de branches `ios`, et la recherche de fichiers SwiftUI/Xcode n'a révélé aucun projet iOS.

## 3. Dépendance Keycloak résiduelle dans le backend `main`

L'authentification des requêtes prend en charge Auth0, et `oidc_provider` vaut `auth0` par défaut. Toutefois, Keycloak n'est pas encore entièrement retiré du code opérationnel :
- `backend/app/main.py` importe toujours `KeycloakAdmin`, `KeycloakAdminConfig` et `KeycloakAdminError` ;
- le parcours d'invitation conserve une branche conditionnelle `settings.oidc_provider == "keycloak"` qui provisionne les comptes via l'API d'administration Keycloak ;
- `backend/app/config.py` accepte encore `oidc_provider` égal à `keycloak` et conserve les paramètres `KEYCLOAK_ADMIN_*` ainsi que leur validation ;
- `backend/app/keycloak_admin.py` reste présent et un test de contrat vérifie explicitement la coexistence des deux parcours.

La suppression de Keycloak exige donc de traiter le parcours d'invitation et ses tests, puis de vérifier les flux de comptes historiques et les données d'identité avant retrait. Ne pas supprimer simplement l'import ou les paramètres : cela pourrait casser les invitations ou la compatibilité des comptes existants. Aucune migration d'identité ni rapprochement par email ne doit être effectué.

## 4. Authentification native cible

- Utiliser Auth0, Authorization Code + PKCE, client public natif et navigateur système/SDK OIDC approprié.
- Ne jamais embarquer de secret client.
- Valider les tokens sur le backend actuel : signature, issuer, audience, expiration, algorithmes et identité OIDC.
- Définir les callback/logout URLs pour chaque application et chaque environnement.
- Utiliser un stockage sécurisé de session conforme aux recommandations des plateformes.
- Ne jamais rapprocher ou attribuer un compte par email seul.
- Ne pas réintroduire Keycloak ni ses URLs.

## 5. Architecture mobile cible

### Android

- Kotlin + Jetpack Compose + Material 3.
- Séparer au minimum les couches `app`, `core/auth`, `core/network`, `core/designsystem`, `feature/assistant`, `feature/documents`, `feature/organization`, `feature/profile`, et les modules d'administration distincts.
- ViewModels + StateFlow pour états d'écran ; repositories pour appels API ; DTOs typés et erreurs normalisées.
- Sphère JARVIS en composant Compose dédié, avec états explicites et animations adaptées à l'énergie et aux préférences d'accessibilité.

### iOS

- SwiftUI, architecture équivalente et contrats API identiques.
- Module identité OIDC Auth0 via SDK iOS approprié.
- Sphère JARVIS avec états et palette équivalents, sans chercher une identité graphique différente.
- Projet iOS à créer sur `main` : aucun projet ou prototype iOS n'a été retrouvé dans les branches examinées.

### Éditions standard et administration

Les deux expériences peuvent partager les fondations techniques et composants, mais doivent garder des points d'entrée et permissions distincts. L'édition Administration n'embarque pas l'assistant juridique des agents. Les autorisations sont toujours appliquées côté backend ; le masquage d'un écran ne constitue jamais une protection.

## 6. Sphère JARVIS

La source de vérité visuelle actuelle est `frontend/dikevia-chat-theme.css` et le document `docs/60_IDENTITE_VISUELLE_JARVIS.md`.

La sphère ne doit pas simuler une activité qui n'a pas lieu. Ses états sont pilotés par l'état réel du client et les événements backend :
- prêt ;
- écoute uniquement si une entrée vocale existe et est active ;
- analyse/recherche après réception effective du statut correspondant ;
- génération après démarrage effectif de la réponse ;
- terminé ;
- erreur / indisponible.

La disponibilité d'une animation CSS n'est pas la preuve que les classes d'état sont correctement activées. Il reste à auditer le JavaScript et le cycle d'événements. L'implémentation native devra avoir des tests de transitions d'état.

## 7. Plan de consolidation

1. Stabiliser les contrats API et le mécanisme de configuration des environnements sur `main`.
2. Créer une architecture Android native modulaire sur `main`, sans reprendre les dépendances Keycloak.
3. Reprendre progressivement les écrans utiles du prototype Compose, un par un, en les alignant sur les endpoints actuels.
4. Mettre en place Auth0 natif et tester le retour OIDC sur appareils physiques.
5. Implémenter le composant JARVIS selon la source de vérité existante.
6. Créer le projet iOS SwiftUI avec les mêmes contrats, états et droits.
7. Ajouter les tests automatisés Android/iOS et les pipelines de build.
8. Maintenir les applications Web complémentaires tant que les parcours mobiles ne sont pas validés.

## 8. Garde-fous

- Aucun déploiement Render ni publication d'application sans autorisation.
- Aucun achat, service payant ou quota IA consommé par des tests réels sans accord distinct.
- Aucune migration DB ni modification Auth0 hébergée dans le cadre de cet audit.
- Aucune suppression de branche avant inventaire complet et récupération.
- Aucun écran métier ou chatbot déclaré natif tant que les builds et tests ne le prouvent pas.


## 9. Vérification Auth0 spécifique au client mobile — 27 novembre 2026

Le dossier Auth0 `docs/47_AUTH0_MIGRATION.md` identifie un seul client applicatif Auth0 configuré dans le tenant de développement : la SPA Web `Dikévia Web SPA - Development`, Client ID `BSpBdDO3IUyG2g5JcHYH29e80JRbnW41`. Le dossier documente également l'API `https://api.dikevia.fr` et l'issuer de développement `https://dev-brlgaz1yh2de3mjo.us.auth0.com/`.

Ce Client ID est celui d'une SPA web et ne constitue pas la preuve d'une application native Auth0. Le prototype Compose utilise un ancien client Keycloak `dikevia-android`, qui ne doit pas être repris. Aucun Client ID Auth0 natif Android n'a été retrouvé dans les fichiers de configuration/documentation examinés, et aucun callback mobile Auth0 n'est documenté.

**Blocage explicite avant l'implémentation du login Android natif :** enregistrer dans le tenant Auth0 de développement une application native dédiée (client public), confirmer Authorization Code + PKCE, le callback de schéma personnalisé Android, l'URL de retour après logout, les origines/URLs autorisées et l'accès à l'API avec l'audience exacte `https://api.dikevia.fr`. Ne créer aucun secret client. Le Client ID natif doit ensuite être fourni au build comme configuration publique d'environnement, jamais confondu avec le Client ID SPA.

La configuration backend actuelle exige également que l'access token ait l'audience de l'API et que l'ID token soit émis par le même issuer avec le même `sub`. Le client natif devra donc transmettre le jeton d'accès Bearer et l'ID token dans le contrat attendu par le backend (`X-OIDC-ID-Token`), ou une évolution du contrat backend devra être conçue et testée séparément. Ne pas supprimer cette vérification pour simplifier le mobile.

Aucune application native Auth0 n'a été créée, aucun paramètre du tenant n'a été modifié et aucun test d'authentification mobile n'a été lancé. Le compte SPA existant n'est pas réutilisé comme client natif par défaut.

## 10. Séquencement Android sans dette d'intégration

1. Faire confirmer le Client ID Auth0 natif et ses callbacks autorisés.
2. Introduire les plugins Compose et les dépendances Android nécessaires dans le module existant, avec versions alignées et verrouillées.
3. Remplacer l'activité WebView par une activité Compose seulement lorsque le premier parcours OIDC natif peut être configuré sans valeurs inventées.
4. Découper l'authentification, le client HTTP, les modèles d'API et les écrans en couches testables ; ne pas conserver l'activité monolithique du prototype.
5. Porter les écrans standard et administration avec des destinations et contrôles d'accès séparés.
6. Ajouter les tests unitaires des états UI, tests de contrats API, tests Compose et builds debug des deux éditions.
7. Recetter la connexion, la rotation/expiration de session, la déconnexion, les erreurs 401/403 et les permissions sur appareil physique.

La migration de la WebView doit être une bascule explicite et réversible : garder l'ancien chemin de build jusqu'à validation du premier APK natif, sans distribuer ni déployer ce dernier prématurément.


## 11. Première fondation Compose native créée sur main — 27 novembre 2026

Une première brique de code native, isolée du parcours WebView encore en service, a été ajoutée :

- `android/build.gradle.kts` : déclaration du plugin Kotlin Compose versionné avec Kotlin 2.0.21 ;
- `android/app/build.gradle.kts` : activation de Compose et ajout du BOM Compose 2024.12.01, UI, graphics, Material 3 et tooling ;
- `android/app/src/main/java/fr/dikevia/commercial/designsystem/JarvisOrb.kt` : composant Compose JARVIS, palette glacier/acier/bleu nuit, noyau lumineux, anneaux, pulsation et états sémantiques `READY`, `LISTENING`, `ANALYZING`, `GENERATING`, `COMPLETED`, `ERROR`.

Le composant reçoit explicitement son état du client appelant. Il ne simule pas de microphone, de recherche ni de génération par lui-même. L'appelant ne devra passer `LISTENING` que lorsqu'une capture vocale réelle sera active.

**Limites actuelles :** le composant n'est pas encore branché à `MainActivity`, qui reste une WebView. Il n'y a pas encore de ViewModel d'état assistant, de tests Compose, de validation de build Gradle, de gestion de réduction des animations, ni d'intégration Auth0 native. Aucun APK natif n'a été construit ou distribué. Les modifications constituent une fondation UI isolée, pas une application native achevée.

Le premier contrôle de compilation doit être exécuté dans un environnement Android/Gradle avec SDK 35 et JDK 17 avant toute bascule du point d'entrée de l'application.
