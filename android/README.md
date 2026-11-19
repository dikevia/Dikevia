# Dikévia Android beta

> **Distribution bloquée à ce stade.** L'application Android actuelle est une coque WebView de démonstration, pas une bêta sécurisée distribuable. La cible retenue est une Trusted Web Activity (TWA) vérifiée. Aucun APK ne doit être distribué avant la validation des critères décrits dans [la décision d'architecture et les critères de distribution](../docs/45_ANDROID_BETA_AUTHENTICATION.md).

## État technique actuel

- Identifiant d'application debug : `fr.dikevia.commercial.beta` (suffixe ajouté à l'identifiant de base).
- Android minimum : 7.0 (API 24).
- Compilation : Java 17, Android SDK 35 et Gradle 8.9 dans la CI.
- La coque actuelle charge l'application web commerciale en HTTPS dans une WebView.
- Le parcours OIDC navigateur actuel n'est pas une intégration Android native et ne constitue pas une validation TWA.
- La signature de CI est une clé debug éphémère du runner GitHub Actions ; elle ne peut pas servir à distribuer une application.
- La configuration de version debug ajoute actuellement le suffixe `-beta` à `0.1.0-beta` ; le libellé résultant est provisoire et devra être normalisé avant une vraie livraison.

## Artefact de validation CI

Le workflow CI publie, lorsqu'il termine avec succès, l'artefact `dikevia-android-debug-signed`, conservé pendant 7 jours.

Cet APK sert uniquement à des essais techniques internes. Il n'est ni signé avec une clé de release, ni prêt pour le Play Store, ni autorisé à être distribué. La compilation réussie ne prouve pas l'authentification sur un appareil réel.

## Conditions préalables à une bêta Android distribuable

- Confirmer le domaine HTTPS final de l'application.
- Choisir et protéger la clé de signature de release ; relever son empreinte SHA-256.
- Publier et vérifier le fichier Digital Asset Links (`assetlinks.json`) pour le domaine et le package définitifs.
- Finaliser la TWA et vérifier qu'elle ouvre bien le domaine attendu, sans barre d'adresse de secours.
- Tester sur un appareil Android réel : installation, connexion OIDC, déconnexion, liens externes, retour arrière et reprise réseau.
- Vérifier le parcours de session et les restrictions d'accès avant toute distribution.

Aucun domaine final, certificat de release ou fichier Digital Asset Links ne doit être inventé ou généré avant les décisions correspondantes. Aucun secret ne doit être intégré à l'APK ou au dépôt.
