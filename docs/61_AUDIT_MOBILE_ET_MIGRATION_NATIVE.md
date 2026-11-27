# Dikévia — audit mobile et trajectoire de migration native

Date : 27 novembre 2026  
Référence : branche `main` et prototypes Android historiques  
Statut : audit de code, aucune migration mobile exécutée

## 1. Constat actualisé sur main — 27 novembre 2026

Le répertoire `android/` contient désormais une première fondation Jetpack Compose, ajoutée sans basculer le point d'entrée de l'application :

- `android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt` instancie toujours explicitement une `WebView` : les éditions livrées restent des conteneurs web.
- Les variantes Gradle `standard` et `admin` chargent le même hôte staging avec un paramètre d'édition différent.
- Le plugin Kotlin Compose est déclaré à la version 2.0.21 ; le module active Compose et importe le BOM 2024.12.01, UI, graphics et Material 3.
- `designsystem/JurisOrb.kt` contient le premier composant Compose JURIS, avec états sémantiques et animation locale.
- Aucun projet iOS (`ios/`, projet Xcode ou Swift Package) n'a été retrouvé dans `main`.

Le build peut donc produire les deux APK WebView existants ; la présence de Compose et de la sphère JURIS ne transforme pas encore ces APK en applications natives. La compilation de cette nouvelle fondation doit être confirmée par le workflow Android et les tests associés.

La liste `TRUSTED_HOSTS` vérifiée dans `MainActivity.kt` contient actuellement deux hôtes exacts : `dikevia-vector-beta-staging.onrender.com` et `dev-brlgaz1yh2de3mjo.us.auth0.com`. Les anciens hôtes API Render et Keycloak ont été retirés. Cette configuration reste provisoire : elle pointe vers le staging. Ne pas ajouter de wildcard.
 
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

## 3. État Keycloak actualisé dans le backend — 27 novembre 2026

Le runtime applicatif sur `main` a été basculé vers Auth0 :

- `backend/app/main.py` ne contient plus d'import `KeycloakAdmin` ni de branche de provisionnement Keycloak dans les invitations.
- `backend/app/config.py` définit Auth0 comme fournisseur par défaut et ne contient plus de sélection runtime Keycloak ni de paramètres de provisionnement Admin Keycloak.
- Le flux d'invitation Auth0 envoie un jeton Dikévia à usage unique par SMTP ; l'utilisateur s'authentifie ensuite via Universal Login. Aucun appel Auth0 Management API n'est utilisé dans ce parcours.
- Les contrôles d'intégrité des invitations, la vérification d'adresse portée par l'identité authentifiée et la compatibilité des identités historiques exactes `issuer + subject` sont conservés.

Le retrait runtime ne signifie pas que tous les artefacts historiques ont été supprimés : le module `backend/app/keycloak_admin.py`, les fichiers realm, profils Docker legacy et le service Render historique d'identité doivent encore faire l'objet d'un inventaire et d'un plan de retrait réversible. Aucun rapprochement de compte par email n'est autorisé et aucune désactivation du service Render n'a été effectuée.

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
- Sphère JURIS en composant Compose dédié, avec états explicites et animations adaptées à l'énergie et aux préférences d'accessibilité.

### iOS

- SwiftUI, architecture équivalente et contrats API identiques.
- Module identité OIDC Auth0 via SDK iOS approprié.
- Sphère JURIS avec états et palette équivalents, sans chercher une identité graphique différente.
- Projet iOS à créer sur `main` : aucun projet ou prototype iOS n'a été retrouvé dans les branches examinées.

### Éditions standard et administration

Les deux expériences peuvent partager les fondations techniques et composants, mais doivent garder des points d'entrée et permissions distincts. L'édition Administration n'embarque pas l'assistant juridique des agents. Les autorisations sont toujours appliquées côté backend ; le masquage d'un écran ne constitue jamais une protection.

## 6. Sphère JURIS

La source de vérité visuelle actuelle est `frontend/dikevia-chat-theme.css` et le document `docs/60_IDENTITE_VISUELLE_JURIS.md`.

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
5. Implémenter le composant JURIS selon la source de vérité existante.
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
- `android/app/src/main/java/fr/dikevia/commercial/designsystem/JurisOrb.kt` : composant Compose JURIS, palette glacier/acier/bleu nuit, noyau lumineux, anneaux, pulsation et états sémantiques `READY`, `LISTENING`, `ANALYZING`, `GENERATING`, `COMPLETED`, `ERROR`.

Le composant reçoit explicitement son état du client appelant. Il ne simule pas de microphone, de recherche ni de génération par lui-même. L'appelant ne devra passer `LISTENING` que lorsqu'une capture vocale réelle sera active.

**Limites actuelles :** le composant n'est pas encore branché à `MainActivity`, qui reste une WebView. Il n'y a pas encore de ViewModel d'état assistant, de tests Compose, de validation de build Gradle, de gestion de réduction des animations, ni d'intégration Auth0 native. Aucun APK natif n'a été construit ou distribué. Les modifications constituent une fondation UI isolée, pas une application native achevée.

Le premier contrôle de compilation doit être exécuté dans un environnement Android/Gradle avec SDK 35 et JDK 17 avant toute bascule du point d'entrée de l'application.


## Rectification de nomenclature — 27 novembre 2026

Le nom de la sphère interactive est **JURIS** (et non JARVIS). Le composant natif est donc nommé `JurisOrb` et son état `JurisOrbState`. La direction visuelle reste la sphère lumineuse organique glacier/acier/bleu nuit.


## 12. Rectification du nom de la sphère — 27 novembre 2026

Le nom officiel est **JURIS**. Le composant natif, les animations CSS et les tests de régression sont nommés JURIS. Les mentions JARVIS dans les constats historiques décrivent uniquement l'ancien nom employé avant rectification ; elles ne constituent plus la nomenclature du produit.


## 13. Première tranche d'implémentation native — 27 novembre 2026

Les premiers fichiers d'interface native ont été ajoutés directement à `main`, sans basculer le point d'entrée de production :

### Android
- `feature/home/NativeHomeScreen.kt` : écran Compose natif avec l'identité JURIS, les quatre entrées CST/CAP/CCP/F3SCT, et une surface Administration distincte sans chatbot.
- `NativePreviewActivity.kt` : hôte isolé pour prévisualiser l'interface native.
- Dépendance `androidx.activity:activity-compose` ajoutée.
- L'activité de prévisualisation n'est volontairement pas enregistrée dans le manifeste et ne remplace pas `MainActivity`. Les APK actuellement générés continuent donc à démarrer sur le parcours WebView existant.

### iOS
- Création de `ios/Dikevia.xcodeproj` et du premier target SwiftUI.
- `ContentView.swift` : écran d'accueil natif, déclinaisons standard et administration.
- `JurisOrbView.swift` : sphère JURIS native, palette glacier/acier/bleu nuit et respect du réglage de réduction des animations.
- Les sources et le projet Xcode n'ont pas encore été compilés sur macOS/Xcode.

### Blocages d'intégration non levés
1. Le tenant Auth0 documenté ne contient qu'un client SPA Web connu. Son Client ID ne doit pas être réutilisé comme client natif.
2. Aucun client Auth0 Native Android/iOS ni callback mobile n'a été configuré ou validé. La création de cet objet dans le tenant nécessite une action distincte et une autorisation explicite.
3. Le contrat backend exige un access token d'audience `https://api.dikevia.fr` et un ID token Auth0 vérifié transmis dans `X-OIDC-ID-Token`. Le client mobile doit respecter ce contrat ; aucune vérification ne doit être désactivée.
4. Le parcours de connexion, la sélection d'organisation, le client API authentifié, l'historique, les documents et les fonctions d'administration ne sont pas encore raccordés aux écrans natifs.
5. Les nouvelles interfaces ne sont pas encore les points d'entrée livrés. Ne pas annoncer une application native prête ni distribuer un APK/IPA sur cette seule base.

La prochaine tranche doit porter sur l'enregistrement du client Auth0 natif (après autorisation), l'intégration OIDC PKCE avec stockage sécurisé, puis le client API typé et les tests sur appareils réels. Aucun changement de secret, aucune dépense et aucun déploiement n'ont été effectués dans cette tranche.


## 14. Intégration Auth0 native Android — 27 novembre 2026

Une première intégration SDK a été ajoutée sur `main` :

- `android/app/src/main/java/fr/dikevia/commercial/core/auth/Auth0NativeAuth.kt` : client d'authentification Auth0 natif utilisant Authorization Code + PKCE, Universal Login dans le navigateur système, restauration de session, logout et `SecureCredentialsManager`.
- `android/app/build.gradle.kts` : SDK officiel `com.auth0.android:auth0:3.21.3`, retenu car le projet conserve `minSdk=24` (la branche v4 du SDK requiert API 26 minimum).
- Le Client ID est injecté par la propriété Gradle locale `auth0AndroidClientId`, avec une valeur de garde qui bloque le login tant que le vrai Client ID natif n'est pas fourni.
- Domaine de développement : `dev-brlgaz1yh2de3mjo.us.auth0.com`.
- Audience API : `https://api.dikevia.fr`.
- Scopes demandés : `openid profile email offline_access`.
- Aucun secret client n'est embarqué.

Le SDK Android est intégré au code, mais le module n'est pas encore relié au point d'entrée natif livré. L'activité de lancement reste la WebView, par choix réversible. L'écran Compose demeure une prévisualisation isolée et ne doit pas être présenté comme l'application native active.

### Configuration Auth0 encore absente

Aucun client Auth0 Native Android n'a été créé dans le tenant à cette étape. Il faut enregistrer les quatre callback/logout URI listées dans `android/README.md`, activer l'accès à l'API avec l'audience exacte, puis valider `offline_access` et la rotation des refresh tokens. La SPA existante ne doit pas être réutilisée.

### Build automatisé

Un workflow GitHub Actions `.github/workflows/android-native-build.yml` a été ajouté pour assembler les deux variantes debug et publier des APK comme artefacts temporaires. La première tentative a échoué pendant l'installation d'un package Android SDK obsolète par l'action d'installation ; le workflow a été corrigé pour utiliser le SDK préinstallé du runner. Le résultat de la nouvelle compilation doit encore être confirmé.

### Limites restant à lever

1. Confirmer la compilation des variantes standard et administration avec le SDK Auth0.
2. Enregistrer et valider le client natif Auth0 Android.
3. Relier le module Auth0 à une activité native de production, sans rendre JURIS disponible avant authentification et contrôle API.
4. Implémenter le client API natif et respecter le contrat backend actuel : access token pour l'audience API et ID token Auth0 vérifié dans `X-OIDC-ID-Token`.
5. Ajouter les tests appareil réel (login, annulation, retour callback, restauration, expiration, logout).
6. Réaliser l'intégration Auth0.swift côté iOS ; le projet SwiftUI existe mais n'a pas encore d'authentification native.
7. Ne remplacer la WebView qu'après recette et conservation d'un chemin de repli.

Aucun déploiement Render, aucune modification du tenant Auth0, aucun secret et aucune dépense n'ont été effectués.


## 15. Client API Android natif — 27 novembre 2026

Le commit `e01908a0` ajoute `DikeviaApiClient.kt` :

- base API dérivée de l'URL HTTPS de la variante Android (staging actuellement) ;
- appel `GET /api/v1/organizations` avec Bearer access token, `X-OIDC-ID-Token` et contrôle de l'issuer/subject côté serveur ;
- appel `POST /api/v1/chat/ask` avec le même couple de jetons et l'en-tête `X-Organization-ID` ;
- lecture du statut de vérification, de la réponse, des demandes de précision et des titres des sources ;
- aucun jeton écrit dans les logs ni dans le stockage de ce client.

Le commit `015fd60a` raccorde ce client à l'écran de prévisualisation Android : restauration de session, chargement des organisations, sélection explicite lorsqu'il y en a plusieurs, question JURIS, affichage de la réponse et déconnexion. L'édition Administration n'envoie aucune question à JURIS.

### Limites avant recette

- Le Client ID Auth0 natif reste à créer et configurer dans le tenant ; la valeur de garde empêche toute connexion si ce paramètre manque.
- L'activité native demeure une prévisualisation non lancée par l'icône de l'application. La WebView est encore le point d'entrée de production.
- Le chat natif ne conserve pas encore le `conversation_id` retourné pour les questions de suivi ; il ne faut donc pas le présenter comme une conversation multi-tours finalisée.
- L'API est actuellement dérivée de l'URL staging inscrite dans les variantes Android. La configuration prod doit être explicitement définie avant une publication.
- Le contrat API est aligné sur le code actuel : `Authorization: Bearer`, `X-OIDC-ID-Token`, `X-Organization-ID`. Il reste à valider avec un vrai compte et le tenant Auth0 sur appareil physique.
- La CI backend sur le commit `6d3c7ead` a 10 échecs parmi 1 547 tests : certains sont des assertions frontend devenues obsolètes après le cache-busting et le nouveau gestionnaire de clic ; les autres touchent au prompt juridique, à la normalisation du contexte utilisateur et au statut de vérification des sources. Ils doivent être diagnostiqués séparément, sans désactiver les contrôles juridiques.


### 16. Passage conditionnel au lanceur natif et continuité JURIS — 27 novembre 2026

Le commit `20d3d791` ajoute dans `MainActivity` un basculement automatique vers `NativePreviewActivity` dès qu'un véritable Client ID Auth0 natif est injecté à la compilation. Tant que la valeur de garde est présente, l'application conserve la WebView existante. Cela évite de distribuer une application native qui ne peut pas authentifier ses utilisateurs.

Les commits `1a3c7b9f`, `a1d42935` et `6ad5b7f1` ajoutent la continuité conversationnelle :
- envoi du `conversation_id` au backend sur les tours suivants ;
- récupération du `conversation_id` retourné par l'API ;
- conservation du contexte entre questions dans la même organisation ;
- remise à zéro du contexte lorsque l'utilisateur change d'organisation.

Le backend reste l'autorité pour la vérification des jetons, les adhésions, les droits et la persistance des messages. Le client Android ne décide pas lui-même des droits.

Le build Android des commits précédents `015fd60a` a réussi. Le build du dernier commit `6ad5b7f1` est relancé pour valider les changements du lanceur et du contexte conversationnel. Aucun APK issu du commit final ne doit être considéré comme validé avant la réussite de ce workflow.
