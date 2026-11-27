// Deliberately empty static fallback. The backend must provide the public Auth0
// configuration at /auth-config.js; never silently fall back to a legacy Keycloak issuer.
window.CFDT_JURIS_OIDC = Object.freeze({});
