// Configuration OIDC de la beta Render Dikévia.
// Aucun secret client ne doit être exposé dans le navigateur.
window.CFDT_JURIS_OIDC = {
  "issuer": "https://dikevia-identity-l2r8.onrender.com/realms/cfdt",
  "client_id": "cfdt-juris-web",
  "redirect_uri": "https://dikevia-commercial-api-l2r8.onrender.com/",
  "silent_redirect_uri": "https://dikevia-commercial-api-l2r8.onrender.com/static/silent-check-sso.html",
  "scopes": "openid"
};
