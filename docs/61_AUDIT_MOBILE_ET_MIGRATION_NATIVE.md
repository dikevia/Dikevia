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
