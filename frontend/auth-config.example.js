// Générer frontend/auth-config.js avec scripts/render_keycloak_config.py.
// Application navigateur publique : aucun client_secret ne doit être ajouté ici.
window.DIKEVIA_OIDC = {
  issuer: "http://localhost:8081/realms/cfdt",
  client_id: "cfdt-juris-web",
  redirect_uri: "http://localhost:8000/",
  scopes: "openid profile email"
};
