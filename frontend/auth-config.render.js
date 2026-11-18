// Configuration OIDC de la beta Render Dikévia.
// Les URI sont synchronisées avec render.yaml et realm-cfdt.render.json.
window.CFDT_JURIS_OIDC = {
  "issuer": "https://dikevia-identity-l2r8.onrender.com/realms/cfdt",
  "client_id": "cfdt-juris-web",
  "redirect_uri": "https://dikevia-commercial-api-l2r8.onrender.com/",
  "scopes": "openid profile email"
};
