// OIDC Render configuration shared by production and isolated staging deployments.
// Redirects are scoped to the current application origin; no client secret is exposed.
const appOrigin = window.location.origin;
window.CFDT_JURIS_OIDC = {
  "issuer": "https://dikevia-identity-l2r8.onrender.com/realms/cfdt",
  "client_id": "cfdt-juris-web",
  "redirect_uri": appOrigin + "/",
  "silent_redirect_uri": appOrigin + "/static/silent-check-sso.html",
  "scopes": "openid profile email"
};
