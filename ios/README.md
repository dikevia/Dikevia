# Dikévia iOS — native SwiftUI foundation

This directory contains the first native SwiftUI application target:

- `Dikevia.xcodeproj`: Xcode application project;
- `Dikevia/DikeviaApp.swift`: SwiftUI app entry point;
- `Dikevia/ContentView.swift`: standard/admin landing surfaces and JURIS entry point;
- `Dikevia/JurisOrbView.swift`: native JURIS orb using the glacier/steel/navy palette.

## Current limitations

This is an initial native UI foundation, not a release-ready application:

- Auth0 native login is not wired.
- The Auth0 Native application/client and callback allowlists have not been created or validated.
- The authenticated API client, organization selection, chat history, document workflows and administration API screens remain to be integrated.
- The Xcode target has not yet been compiled or tested on a simulator or physical Apple device.
- The standard/admin editions still need separate signed schemes/targets and server-side authorization checks.

Do not insert the existing SPA Client ID into the iOS app. A dedicated public Auth0 Native client using Authorization Code + PKCE is required. No client secret may be embedded in the application.

## Build

Open `Dikevia.xcodeproj` in Xcode and build the `Dikevia` scheme for an iOS Simulator. Device signing and distribution are intentionally not configured.
