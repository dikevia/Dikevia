# Dikévia Android beta

This is the installable Android shell for the Dikévia commercial beta. It loads the commercial application over HTTPS in a native Android WebView; the backend, identity provider and legal data are not bundled in the APK and require their configured services to be available.

- Package: `fr.dikevia.commercial.beta`
- Minimum Android: 7.0 (API 24)
- Build: debug APK, signed automatically with the Android debug key by Gradle
- Allowed in-app origins: the commercial API and the dedicated Keycloak identity service
- External HTTPS links open in the device browser
- File selection is enabled for document attachments
- The browser client is configured for OIDC Authorization Code + PKCE; the APK contains no client secret. **The live sign-in flow has not yet been validated on a physical Android device**, so WebView / Keycloak compatibility remains a manual beta acceptance check.

## Build and retrieve the beta APK

The GitHub Actions workflow **Android beta APK** is configured to build on pushes to `integration/beta-commercial-security`, `android/beta-apk-delivery` and the legacy commercial branch, when Android or frontend configuration files change. It can also be started manually with `workflow_dispatch`.

A successful run publishes the artifact `dikevia-commercial-beta-apk` for 14 days. It contains:

- `app-debug.apk`: installable debug beta package
- `app-debug.apk.sha256`: SHA-256 checksum for integrity verification

The workflow checks that the APK exists, is a valid ZIP archive, exceeds the minimum size and declares the expected package identifier. **This is a build/archive check only**: it does not prove that the app has been installed on a physical device, that the hosted services are healthy, or that a live OIDC login succeeds.

## Installation and device checks

1. Download the artifact from the successful **Android beta APK** workflow run and extract it.
2. On the Android device, open `app-debug.apk` and authorize installation from the file manager/browser if Android requests it.
3. Launch **Dikévia**, sign in with an already provisioned beta account, and verify that the application returns to its authenticated screen.
4. Check navigation, conversation history, file selection, dossier save/reopen and logout.
5. If sign-in or loading fails, record the visible error and the device Android/WebView version; do not bypass certificate or HTTPS errors.
6. On Android 15 (target SDK 35), also verify that the status/navigation bars do not cover the page, that gesture navigation remains usable, and that the keyboard does not hide the active form field.

The APK is a demonstration build, not a Play Store release. It uses the commercial beta environment and currently has a one-active-user limit. Do not distribute credentials in the APK or in demonstration materials. Hosted API and Keycloak services must already be configured and available; this Android build does not deploy or wake them.

A production release requires a dedicated signing key stored outside the repository, device testing, account provisioning and a separate release process. Never commit a signing key or credentials to Git.
