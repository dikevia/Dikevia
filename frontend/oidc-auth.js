/* OIDC Authorization Code + PKCE pour application navigateur publique.
 * Jeton d'accès conservé uniquement en mémoire ; aucun refresh token persistant.
 * L'API reste responsable de la validation cryptographique du jeton.
 */
(() => {
  'use strict';
  const initialInvitation = new URLSearchParams(window.location.search).get('invitation_token');
  if (initialInvitation) sessionStorage.setItem('cfdt_pending_invitation', initialInvitation);
  const cfg = window.CFDT_JURIS_OIDC;
  if (!cfg || !cfg.issuer || !cfg.client_id || !cfg.redirect_uri) return;
  let accessToken = null;
  let expiresAt = 0;
  let discovery = null;
  const encoder = new TextEncoder();
  const random = (n=32) => {
    const bytes = crypto.getRandomValues(new Uint8Array(n));
    return Array.from(bytes, b => b.toString(16).padStart(2,'0')).join('');
  };
  const base64url = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  async function challenge(verifier) {
    return base64url(await crypto.subtle.digest('SHA-256', encoder.encode(verifier)));
  }
  async function metadata() {
    if (discovery) return discovery;
    const issuer = cfg.issuer.replace(/\/$/,'');
    if (!issuer.startsWith('https://') && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(issuer))
      throw new Error('L’émetteur OIDC doit utiliser HTTPS.');
    const response = await fetch(issuer+'/.well-known/openid-configuration',{cache:'no-store'});
    if (!response.ok) throw new Error('Découverte OIDC indisponible.');
    const data = await response.json();
    if (data.issuer !== issuer || !data.authorization_endpoint || !data.token_endpoint)
      throw new Error('Métadonnées OIDC incohérentes ou incomplètes.');
    discovery = data;
    return data;
  }
  async function login() {
    const pending = new URLSearchParams(window.location.search).get('invitation_token');
    if (pending) sessionStorage.setItem('cfdt_pending_invitation', pending);
    const oidc = await metadata();
    const state = random(24), verifier = random(48);
    sessionStorage.setItem('cfdt_oidc_state',state);
    sessionStorage.setItem('cfdt_oidc_verifier',verifier);
    const url = new URL(oidc.authorization_endpoint);
    url.search = new URLSearchParams({client_id:cfg.client_id,response_type:'code',redirect_uri:cfg.redirect_uri,
      scope:cfg.scopes||'openid profile email',state,code_challenge:await challenge(verifier),code_challenge_method:'S256'});
    window.location.assign(url.toString());
  }
  async function completeCallback() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (!code) return;
    const state = params.get('state');
    const expected = sessionStorage.getItem('cfdt_oidc_state');
    const verifier = sessionStorage.getItem('cfdt_oidc_verifier');
    sessionStorage.removeItem('cfdt_oidc_state');
    sessionStorage.removeItem('cfdt_oidc_verifier');
    if (!state || !expected || state !== expected || !verifier) throw new Error('État OIDC invalide. Relancez la connexion.');
    const oidc = await metadata();
    const body = new URLSearchParams({grant_type:'authorization_code',client_id:cfg.client_id,code,
      redirect_uri:cfg.redirect_uri,code_verifier:verifier});
    const response = await fetch(oidc.token_endpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,cache:'no-store'});
    if (!response.ok) throw new Error('Échange du code OIDC refusé. Vérifiez les URI autorisées et le support CORS du fournisseur.');
    const data = await response.json();
    if (!data.access_token || !Number.isFinite(data.expires_in)) throw new Error('Réponse OIDC incomplète.');
    accessToken = data.access_token;
    expiresAt = Date.now() + data.expires_in * 1000;
    const pendingInvitation = sessionStorage.getItem('cfdt_pending_invitation');
    if (pendingInvitation) {
      const accepted = await fetch('/api/v1/invitations/accept', {
        method: 'POST', cache: 'no-store',
        headers: {'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({token: pendingInvitation})
      });
      if (accepted.ok) {
        sessionStorage.removeItem('cfdt_pending_invitation');
        window.dispatchEvent(new CustomEvent('cfdt:invitation-accepted', {detail: await accepted.json()}));
      } else {
        const detail = await accepted.json().catch(() => ({}));
        window.dispatchEvent(new CustomEvent('cfdt:invitation-error', {detail: {message: detail.detail || 'Impossible d’accepter l’invitation.'}}));
      }
    }
    // Nettoyage des paramètres OAuth de l'URL sans toucher au chemin.
    history.replaceState({},document.title,window.location.pathname+window.location.hash);
  }
  const ready = completeCallback();
  window.CFDT_JURIS_AUTH = {
    ready,
    async getAccessToken() { await ready; if (!accessToken || Date.now() >= expiresAt-30000) return null; return accessToken; },
    // Une callback précédente peut avoir échoué (code refusé, CORS, réseau).
    // Cela ne doit pas empêcher l'utilisateur de relancer une authentification.
    async login() { await ready.catch(() => {}); return login(); },
    async logout() { accessToken=null;expiresAt=0;sessionStorage.removeItem('cfdt_oidc_state');sessionStorage.removeItem('cfdt_oidc_verifier');const oidc=await metadata().catch(()=>null);if(oidc?.end_session_endpoint)window.location.assign(oidc.end_session_endpoint+'?'+new URLSearchParams({client_id:cfg.client_id,post_logout_redirect_uri:cfg.redirect_uri})); }
  };
})();
