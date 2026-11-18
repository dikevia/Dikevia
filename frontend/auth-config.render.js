// Configuration OIDC de la beta Render Dikévia.
// Seul le scope OIDC obligatoire est demandé : profile/email ne sont pas encore
// provisionnés dans le realm cfdt et provoquaient invalid_scope côté Keycloak.
window.CFDT_JURIS_OIDC = {
  "issuer": "https://dikevia-identity-l2r8.onrender.com/realms/cfdt",
  "client_id": "cfdt-juris-web",
  "redirect_uri": "https://dikevia-commercial-api-l2r8.onrender.com/",
  "scopes": "openid"
};
