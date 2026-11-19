# Dikévia Android beta

> **Distribution bloquée à ce stade :** l'APK actuel est une démonstration WebView et ne doit pas être présenté comme une bêta sécurisée. La cible retenue pour la suite est une TWA vérifiée ; voir [la décision d'architecture et les critères de distribution](../docs/45_ANDROID_BETA_AUTHENTICATION.md). Aucun APK ne doit être distribué avant validation de ces critères.

This Android shell loads the commercial Dikévia web application over HTTPS and keeps the OIDC Authorization Code + PKCE flow inside the same WebView session.

- Package: `fr.dikevia.commercial.beta`
- Minimum Android: 7.0 (API 24)
- Build: debug APK, signed automatically with the Android debug key by Gradle
- Allowed in-app origins: the commercial API and the dedicated Keycloak identity service
- External HTTPS links open in the device browser
- File selection is enabled for document attachments

## Demonstration build

The GitHub Actions workflow **Android beta APK** builds and validates the APK on this development branch. A successful run publishes the file as the artifact `dikevia-commercial-beta-apk` (retained for 14 days).

The APK is a demonstration build, not a Play Store release. It uses the commercial beta environment and currently has a one-active-user limit. Do not distribute credentials in the APK or in demonstration materials.

## Before the CFDT demonstration

- Verify the commercial API and identity service are healthy.
- Install the APK on the demonstration Android device and complete sign-in before the meeting.
- Test at least one FPT question with documentary sources and one question for which the assistant must ask for missing facts or abstain.
- Keep a browser access as a fallback if the device blocks installation.

A production release requires a dedicated signing key, device testing, account provisioning and a separate release process.
