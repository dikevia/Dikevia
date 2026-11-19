# Android beta — décision d'architecture et critères de distribution

## Décision

Ne pas distribuer l'APK Android actuel comme bêta de confiance. Il embarque l'application web dans une `WebView` et y exécute le parcours OIDC/PKCE. Ce choix conserve les cookies tiers dans le composant embarqué et ne fournit pas les garanties du navigateur système pour l'authentification.

Pour cette application qui possède déjà une interface web HTTPS et un parcours OIDC navigateur, la cible privilégiée est une **Trusted Web Activity (TWA)**, adossée à la PWA. La TWA ouvre le site dans le navigateur de confiance en plein écran ; le flux OIDC existant reste un flux navigateur. Cela évite de transmettre un jeton d'accès natif à une WebView par pont JavaScript.

Si des fonctions natives importantes deviennent nécessaires, retenir plutôt **Chrome Custom Tabs + AppAuth** avec un client OIDC Android public distinct, PKCE S256 et URI de redirection d'application vérifiée. Ne pas mélanger les deux modèles.

## État constaté dans le dépôt

- Le paquet Gradle est `fr.dikevia.commercial` ; le build debug ajoute le suffixe `.beta`, donc son identifiant effectif est `fr.dikevia.commercial.beta`.
- `MainActivity.kt` charge `https://dikevia-commercial-api-l2r8.onrender.com/` dans une WebView.
- La WebView autorise les cookies tiers pour le parcours entre l'application et Keycloak.
- Le client Keycloak déclaré dans le realm est uniquement `cfdt-juris-web`, un client public navigateur avec PKCE S256.
- Le client web redirige vers l'origine Render et le code frontend effectue l'échange du code dans le navigateur.
- Aucun fichier Digital Asset Links ni empreinte SHA-256 de certificat Android n'est actuellement fourni par le dépôt.

## Conditions préalables à une TWA vérifiée

1. Confirmer l'origine HTTPS définitive de la bêta. L'origine actuellement codée est `https://dikevia-commercial-api-l2r8.onrender.com` ; ne pas la considérer comme définitive sans décision de domaine.
2. Fixer l'identifiant d'application bêta. Le build debug actuel utilise `fr.dikevia.commercial.beta`; l'identifiant doit être cohérent dans Gradle, les builds distribués et Digital Asset Links.
3. Choisir le certificat qui signera réellement l'APK distribué. Obtenir son empreinte SHA-256 avec les outils Android, sans publier ni transmettre la clé privée.
4. Publier `/.well-known/assetlinks.json` sur l'origine exacte, avec le package et l'empreinte du certificat de distribution. Un certificat debug local ne doit pas être confondu avec le certificat de distribution.
5. Vérifier l'association Digital Asset Links depuis un appareil Android réel. Si la vérification échoue, le navigateur doit rester en mode Custom Tab ; ne pas présenter ce résultat comme une TWA vérifiée.
6. Tester connexion OIDC, déconnexion, retour après expiration de session, invitations, pièces jointes, téléchargements, navigation externe, bouton retour, mode hors connexion et reprise réseau.
7. Garder le service worker limité aux ressources statiques hors ligne. Ne jamais mettre en cache API, jetons, conversations, documents, données personnelles ou pages authentifiées.

## Conditions si AppAuth est retenu à la place

- Ajouter une dépendance AppAuth Android maintenue et utiliser le navigateur système / Custom Tabs.
- Créer dans Keycloak un client public Android séparé, sans secret client, Authorization Code + PKCE S256, sans implicit ni password grant.
- Déclarer une URI de redirection exacte liée au package/signature et la valider dans le manifeste Android.
- Prévoir une stratégie explicite de transfert du résultat d'authentification vers l'interface ; ne jamais exposer le jeton dans une URL, un log, un stockage partagé ou une interface JavaScript non maîtrisée.
- Tester le cycle complet sur appareil réel avant de produire un APK bêta.

## Critères bloquants avant APK distribuable

- [ ] Architecture WebView retirée du parcours d'authentification.
- [ ] Origine et identifiant d'application bêta confirmés.
- [ ] Signature de distribution définie et empreinte vérifiée.
- [ ] Association Digital Asset Links validée (si TWA).
- [ ] OIDC/PKCE et retours de navigation validés sur appareil réel.
- [ ] Sélection et téléchargement de documents validés.
- [ ] Aucun secret embarqué dans l'APK.
- [ ] Artefact signé et provenance de build documentée.

## Limite de cette préparation

Ce document ne crée ni certificat, ni clé de signature, ni client Keycloak, ni configuration d'origine. Ces éléments dépendent de choix de distribution et de preuves cryptographiques qui ne doivent pas être inventés. Aucun déploiement, aucune migration et aucun service payant ne sont nécessaires pour préparer cette décision.
