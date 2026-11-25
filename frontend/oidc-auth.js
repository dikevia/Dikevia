/* OIDC Authorization Code + PKCE pour application navigateur publique.
 * Jeton d'accès conservé uniquement en mémoire ; aucun refresh token persistant.
 * La restauration SSO utilise une iframe cachée : pas de redirection complète au démarrage.
 * L'API reste responsable de la validation cryptographique du jeton.
 */
(() => {
  'use strict';
  const initialInvitation = new URLSearchParams(window.location.search).get('invitation_token');
  if (initialInvitation) sessionStorage.setItem('cfdt_pending_invitation', initialInvitation);
  const cfg = window.CFDT_JURIS_OIDC;
  if (!cfg || !cfg.issuer || !cfg.client_id || !cfg.redirect_uri) return;
  let accessToken = null;
  let idToken = null;
  let expiresAt = 0;
  let discovery = null;
  let silentCheckInFlight = null;
  const encoder = new TextEncoder();
  const random = (n=32) => {
    const bytes = crypto.getRandomValues(new Uint8Array(n));
    return Array.from(bytes, b => b.toString(16).padStart(2,'0')).join('');
  };
  const base64url = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  function decodeJwtPayload(token) {
    const part = String(token || '').split('.')[1];
    if (!part) throw new Error('Jeton d’identité OIDC mal formé.');
    const base64 = part.replace(/-/g,'+').replace(/_/g,'/');
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    const bytes = Uint8Array.from(atob(padded), char => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  async function challenge(verifier) {
    return base64url(await crypto.subtle.digest('SHA-256', encoder.encode(verifier)));
  }
  async function legacyMetadata() {
    const issuer=cfg.legacy_issuer;
    if(!issuer||!cfg.legacy_client_id)throw new Error('La vérification de l’ancien compte n’est pas configurée.');
    if(!issuer.startsWith('https://'))throw new Error('L’ancien fournisseur d’identité doit utiliser HTTPS.');
    const response=await fetch(issuer.replace(/\/+$/,'')+'/.well-known/openid-configuration',{cache:'no-store'});
    if(!response.ok)throw new Error('Découverte de l’ancien fournisseur d’identité indisponible.');
    const data=await response.json();
    if(data.issuer!==issuer||!data.authorization_endpoint||!data.token_endpoint)throw new Error('Métadonnées Keycloak incohérentes.');
    return data;
  }
  async function exchangeLegacyCode(code,verifier,redirectUri,expectedNonce) {
    const oidc=await legacyMetadata();
    const body=new URLSearchParams({grant_type:'authorization_code',client_id:cfg.legacy_client_id,code,redirect_uri:redirectUri,code_verifier:verifier});
    const response=await fetch(oidc.token_endpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,cache:'no-store'});
    if(!response.ok)throw new Error('Échange du code Keycloak refusé. Vérifiez l’URI de retour et le client public PKCE.');
    const data=await response.json();
    if(!data.id_token)throw new Error('Keycloak n’a pas fourni de jeton d’identité.');
    const claims=decodeJwtPayload(data.id_token);
    const audiences=Array.isArray(claims.aud)?claims.aud:[claims.aud];
    if(claims.iss!==cfg.legacy_issuer||!audiences.includes(cfg.legacy_client_id)||claims.nonce!==expectedNonce||!claims.sub)
      throw new Error('La preuve Keycloak ne correspond pas à la demande de rattachement.');
    return data.id_token;
  }
  async function completeLegacyCallback() {
    const params=new URLSearchParams(window.location.search);
    const code=params.get('code'),error=params.get('error'),state=params.get('state');
    const expected=sessionStorage.getItem('cfdt_oidc_state');
    const verifier=sessionStorage.getItem('cfdt_oidc_verifier');
    const nonce=sessionStorage.getItem('cfdt_oidc_nonce');
    sessionStorage.removeItem('cfdt_oidc_state');
    sessionStorage.removeItem('cfdt_oidc_verifier');
    sessionStorage.removeItem('cfdt_oidc_nonce');
    sessionStorage.removeItem('cfdt_oidc_flow');
    if(!state||!expected||state!==expected||(code&&(!verifier||!nonce))){
      cleanCallbackUrl();
      throw new Error('État de vérification Keycloak invalide. Recommencez le rattachement.');
    }
    if(error){cleanCallbackUrl();throw new Error(params.get('error_description')||'Keycloak a refusé la vérification ('+error+').');}
    try{
      const idToken=await exchangeLegacyCode(code,verifier,cfg.legacy_redirect_uri||cfg.redirect_uri,nonce);
      sessionStorage.setItem('cfdt_legacy_link_id_token',idToken);
      sessionStorage.setItem('cfdt_legacy_link_nonce',nonce);
    }finally{cleanCallbackUrl();}
    return true;
  }
  async function finishPendingLegacyLink() {
    const legacyToken=sessionStorage.getItem('cfdt_legacy_link_id_token');
    const nonce=sessionStorage.getItem('cfdt_legacy_link_nonce');
    if(!legacyToken||!nonce||!accessToken||!idToken)return false;
    const response=await fetch('/api/v1/auth/link-legacy/complete',{
      method:'POST',cache:'no-store',
      headers:{'Authorization':'Bearer '+accessToken,'X-OIDC-ID-Token':idToken,'Content-Type':'application/json'},
      body:JSON.stringify({keycloak_id_token:legacyToken,nonce})
    });
    const data=await response.json().catch(()=>({detail:'Réponse serveur illisible.'}));
    if(!response.ok)throw new Error(data.detail||'Le rattachement des identités a échoué.');
    sessionStorage.removeItem('cfdt_legacy_link_id_token');
    sessionStorage.removeItem('cfdt_legacy_link_nonce');
    window.dispatchEvent(new CustomEvent('cfdt:legacy-identity-linked',{detail:data}));
    return true;
  }
  async function beginLegacyLink() {
    const bearer=await window.CFDT_JURIS_AUTH.getAccessToken();
    const identity=await window.CFDT_JURIS_AUTH.getIdentityToken();
    if(!bearer||!identity)throw new Error('Connectez-vous d’abord à votre compte Dikévia/Auth0.');
    const challengeResponse=await fetch('/api/v1/auth/link-legacy/challenge',{
      method:'POST',cache:'no-store',headers:{'Authorization':'Bearer '+bearer,'X-OIDC-ID-Token':identity}
    });
    const challengeData=await challengeResponse.json().catch(()=>({}));
    if(!challengeResponse.ok)throw new Error(challengeData.detail||'Impossible de préparer la vérification du compte historique.');
    const oidc=await legacyMetadata();
    const state=random(24),verifier=random(48),nonce=challengeData.nonce;
    sessionStorage.setItem('cfdt_oidc_state',state);
    sessionStorage.setItem('cfdt_oidc_verifier',verifier);
    sessionStorage.setItem('cfdt_oidc_nonce',nonce);
    sessionStorage.setItem('cfdt_oidc_flow','legacy-link');
    const redirectUri=challengeData.redirect_uri||cfg.legacy_redirect_uri||cfg.redirect_uri;
    const url=new URL(oidc.authorization_endpoint);
    url.search=new URLSearchParams({
      client_id:cfg.legacy_client_id,response_type:'code',redirect_uri:redirectUri,
      scope:'openid profile email',state,nonce,code_challenge_method:'S256',
      code_challenge:await challenge(verifier),prompt:'login'
    });
    window.location.assign(url.toString());
  }
  async function metadata() {
    if (discovery) return discovery;
    // Preserve the issuer exactly as advertised by discovery. Auth0 issuers
    // normally end with '/', and that slash is part of the JWT iss claim.
    const issuer = cfg.issuer;
    const discoveryUrl = issuer.replace(/\/+$/,'')+'/.well-known/openid-configuration';
    if (!issuer.startsWith('https://') && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(issuer))
      throw new Error('L’émetteur OIDC doit utiliser HTTPS.');
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),210000);
    let response;
    try {
      response=await fetch(discoveryUrl,{cache:'no-store',signal:controller.signal});
    } catch(error) {
      if(error.name==='AbortError') throw new Error('Le fournisseur d’identité met trop de temps à répondre.');
      throw error;
    } finally { clearTimeout(timeout); }
    if (!response.ok) throw new Error('Découverte OIDC indisponible.');
    const data = await response.json();
    if (data.issuer !== issuer || !data.authorization_endpoint || !data.token_endpoint)
      throw new Error('Métadonnées OIDC incohérentes ou incomplètes.');
    discovery = data;
    return data;
  }
  function authorizationUrl(oidc, redirectUri, state, verifier, prompt, nonce, connection) {
    const params = {
      client_id:cfg.client_id,response_type:'code',redirect_uri:redirectUri,
      scope:cfg.scopes||'openid profile email',state,nonce,
      code_challenge_method:'S256'
    };
    if (cfg.audience) params.audience=cfg.audience;
    if (connection) params.connection=connection;
    return challenge(verifier).then(value => {
      params.code_challenge=value;
      if (prompt) params.prompt=prompt;
      const url=new URL(oidc.authorization_endpoint);
      url.search=new URLSearchParams(params);
      return url.toString();
    });
  }
  async function beginAuthorization(prompt, connection) {
    const pending = new URLSearchParams(window.location.search).get('invitation_token');
    if (pending) sessionStorage.setItem('cfdt_pending_invitation', pending);
    const oidc = await metadata();
    const state = random(24), verifier = random(48), nonce = random(24);
    sessionStorage.setItem('cfdt_oidc_state',state);
    sessionStorage.setItem('cfdt_oidc_verifier',verifier);
    sessionStorage.setItem('cfdt_oidc_nonce',nonce);
    sessionStorage.setItem('cfdt_oidc_flow','interactive');
    const url=await authorizationUrl(oidc,cfg.redirect_uri,state,verifier,prompt,nonce,connection);
    window.location.assign(url);
  }
  async function login() {
    sessionStorage.removeItem('cfdt_oidc_silent_failed');
    return beginAuthorization(null, null);
  }
  async function loginWithGoogle() {
    sessionStorage.removeItem('cfdt_oidc_silent_failed');
    return beginAuthorization('select_account', 'google-oauth2');
  }
  function cleanCallbackUrl() {
    history.replaceState({},document.title,window.location.pathname+window.location.hash);
  }
  async function acceptPendingInvitation() {
    const pendingInvitation = sessionStorage.getItem('cfdt_pending_invitation');
    if (!pendingInvitation) return;
    const accepted = await fetch('/api/v1/invitations/accept', {
      method:'POST',cache:'no-store',
      headers:{
        'Authorization':'Bearer '+accessToken,
        'X-OIDC-ID-Token':idToken,
        'Content-Type':'application/json'
      },
      body:JSON.stringify({token:pendingInvitation})
    });
    if (accepted.ok) {
      sessionStorage.removeItem('cfdt_pending_invitation');
      window.dispatchEvent(new CustomEvent('cfdt:invitation-accepted',{detail:await accepted.json()}));
    } else {
      const detail=await accepted.json().catch(()=>({}));
      window.dispatchEvent(new CustomEvent('cfdt:invitation-error',{detail:{message:detail.detail||'Impossible d’accepter l’invitation.'}}));
    }
  }
  async function exchangeCode(code,verifier,redirectUri,expectedNonce) {
    const oidc=await metadata();
    const body=new URLSearchParams({
      grant_type:'authorization_code',client_id:cfg.client_id,code,
      redirect_uri:redirectUri,code_verifier:verifier
    });
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),30000);
    let response;
    try {
      response=await fetch(oidc.token_endpoint,{
        method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body,cache:'no-store',signal:controller.signal
      });
    } catch(error) {
      if(error.name==='AbortError') throw new Error('Le fournisseur d’identité ne répond pas assez rapidement.');
      throw error;
    } finally { clearTimeout(timeout); }
    if(!response.ok) throw new Error('Échange du code OIDC refusé. Vérifiez les URI autorisées et le support CORS du fournisseur.');
    const data=await response.json();
    if(!data.access_token||!data.id_token||!Number.isFinite(data.expires_in)) throw new Error('Réponse OIDC incomplète.');
    const identityClaims=decodeJwtPayload(data.id_token);
    const identityAudiences=Array.isArray(identityClaims.aud)?identityClaims.aud:[identityClaims.aud];
    if(!expectedNonce||identityClaims.nonce!==expectedNonce||identityClaims.iss!==cfg.issuer||
       !identityAudiences.includes(cfg.client_id)||typeof identityClaims.sub!=='string'||!identityClaims.sub)
      throw new Error('Jeton d’identité OIDC incohérent. Relancez la connexion.');
    accessToken=data.access_token;
    idToken=data.id_token;
    expiresAt=Date.now()+data.expires_in*1000;
    sessionStorage.removeItem('cfdt_oidc_silent_failed');
    await acceptPendingInvitation();
  }
  async function completeCallback() {
    if(sessionStorage.getItem('cfdt_oidc_flow')==='legacy-link')return completeLegacyCallback();
    const params=new URLSearchParams(window.location.search);
    const code=params.get('code'),error=params.get('error');
    if(!code&&!error) return false;
    const state=params.get('state');
    const expected=sessionStorage.getItem('cfdt_oidc_state');
    const verifier=sessionStorage.getItem('cfdt_oidc_verifier');
    const expectedNonce=sessionStorage.getItem('cfdt_oidc_nonce');
    sessionStorage.removeItem('cfdt_oidc_state');
    sessionStorage.removeItem('cfdt_oidc_verifier');
    sessionStorage.removeItem('cfdt_oidc_nonce');
    sessionStorage.removeItem('cfdt_oidc_flow');
    if(!state||!expected||state!==expected||(code&&(!verifier||!expectedNonce))){
      cleanCallbackUrl();
      throw new Error('État OIDC invalide. Relancez la connexion.');
    }
    if(error){
      cleanCallbackUrl();
      if(['login_required','interaction_required','consent_required'].includes(error)){
        sessionStorage.setItem('cfdt_oidc_silent_failed','1');
        return false;
      }
      throw new Error(params.get('error_description')||'Le fournisseur d’identité a refusé la connexion ('+error+').');
    }
    try { await exchangeCode(code,verifier,cfg.redirect_uri,expectedNonce); }
    finally { cleanCallbackUrl(); }
    return true;
  }
  async function silentCheckSso(force=false) {
    if(silentCheckInFlight) return silentCheckInFlight;
    silentCheckInFlight=(async()=>{
      const redirectUri=cfg.silent_redirect_uri;
      if(!redirectUri) return false;
      const callback=new URL(redirectUri,window.location.href);
      if(callback.origin!==window.location.origin) return false;
      const oidc=await metadata();
      const state=random(24),verifier=random(48),nonce=random(24);
      sessionStorage.setItem('cfdt_oidc_state',state);
      sessionStorage.setItem('cfdt_oidc_verifier',verifier);
      sessionStorage.setItem('cfdt_oidc_nonce',nonce);
      sessionStorage.setItem('cfdt_oidc_flow','silent');
      const authUrl=await authorizationUrl(oidc,redirectUri,state,verifier,'none',nonce);
      const frame=document.createElement('iframe');
      frame.setAttribute('aria-hidden','true');
      frame.tabIndex=-1;
      frame.style.cssText='position:absolute;width:1px;height:1px;left:-10000px;border:0';
      const result=await new Promise(resolve=>{
        let settled=false;
        const finish=value=>{
          if(settled)return;
          settled=true;
          clearTimeout(timer);
          window.removeEventListener('message',onMessage);
          frame.remove();
          resolve(value);
        };
        const onMessage=event=>{
          if(event.origin!==window.location.origin||event.source!==frame.contentWindow)return;
          if(!event.data||event.data.type!=='cfdt-oidc-silent-callback'||typeof event.data.url!=='string')return;
          finish(event.data.url);
        };
        window.addEventListener('message',onMessage);
        const timer=setTimeout(()=>finish(null),8000);
        frame.src=authUrl;
        document.body.appendChild(frame);
      });
      if(!result){
        sessionStorage.removeItem('cfdt_oidc_state');
        sessionStorage.removeItem('cfdt_oidc_verifier');
        sessionStorage.removeItem('cfdt_oidc_nonce');
        sessionStorage.removeItem('cfdt_oidc_flow');
        sessionStorage.setItem('cfdt_oidc_silent_failed','1');
        return false;
      }
      const returned=new URL(result,window.location.origin);
      if(returned.origin!==window.location.origin||returned.pathname!==callback.pathname){
        sessionStorage.removeItem('cfdt_oidc_state');
        sessionStorage.removeItem('cfdt_oidc_verifier');
        sessionStorage.removeItem('cfdt_oidc_nonce');
        sessionStorage.removeItem('cfdt_oidc_flow');
        throw new Error('Retour OIDC silencieux provenant d’une origine inattendue.');
      }
      const params=returned.searchParams;
      const code=params.get('code'),error=params.get('error'),returnedState=params.get('state');
      const expected=sessionStorage.getItem('cfdt_oidc_state');
      const storedVerifier=sessionStorage.getItem('cfdt_oidc_verifier');
      const expectedNonce=sessionStorage.getItem('cfdt_oidc_nonce');
      sessionStorage.removeItem('cfdt_oidc_state');
      sessionStorage.removeItem('cfdt_oidc_verifier');
      sessionStorage.removeItem('cfdt_oidc_nonce');
      sessionStorage.removeItem('cfdt_oidc_flow');
      if(!returnedState||!expected||returnedState!==expected||(code&&(!storedVerifier||!expectedNonce)))
        throw new Error('État OIDC silencieux invalide.');
      if(error){
        if(['login_required','interaction_required','consent_required'].includes(error)){
          sessionStorage.setItem('cfdt_oidc_silent_failed','1');
          return false;
        }
        throw new Error('Restauration SSO impossible : '+error+'.');
      }
      if(!code||!storedVerifier) return false;
      await exchangeCode(code,storedVerifier,redirectUri,expectedNonce);
      return true;
    })().finally(()=>{silentCheckInFlight=null;});
    return silentCheckInFlight;
  }
  async function restoreSsoSession() {
    const hadCallback=new URLSearchParams(window.location.search).has('code')||
      new URLSearchParams(window.location.search).has('error');
    const completed=await completeCallback();
    if(sessionStorage.getItem('cfdt_legacy_link_id_token')){
      if(!accessToken)await silentCheckSso().catch(()=>false);
      if(accessToken)await finishPendingLegacyLink();
      return;
    }
    if(hadCallback||completed||accessToken)return;
    if(sessionStorage.getItem('cfdt_oidc_silent_failed')==='1')return;
    try { await silentCheckSso(); }
    catch(error) {
      sessionStorage.setItem('cfdt_oidc_silent_failed','1');
      throw error;
    }
  }
  const ready=restoreSsoSession();
  window.CFDT_JURIS_AUTH={
    ready,
    async getAccessToken(){
      await ready;
      if(accessToken&&Date.now()<expiresAt-60000)return accessToken;
      if(accessToken&&Date.now()>=expiresAt-60000){
        accessToken=null;expiresAt=0;
        const restored=await silentCheckSso(true).catch(()=>false);
        if(restored&&accessToken&&Date.now()<expiresAt-60000)return accessToken;
      }
      return null;
    },
    async getIdentityToken(){
      await ready;
      return idToken;
    },
    async login(){await ready.catch(()=>{});return login();},
    async loginWithGoogle(){await ready.catch(()=>{});return loginWithGoogle();},
    async linkLegacy(){await ready.catch(()=>{});return beginLegacyLink();},
    async logout(){
      accessToken=null;idToken=null;expiresAt=0;
      sessionStorage.removeItem('cfdt_oidc_state');
      sessionStorage.removeItem('cfdt_oidc_verifier');
      sessionStorage.removeItem('cfdt_oidc_nonce');
      sessionStorage.removeItem('cfdt_oidc_flow');
      sessionStorage.removeItem('cfdt_oidc_silent_failed');
      sessionStorage.removeItem('cfdt_legacy_link_id_token');
      sessionStorage.removeItem('cfdt_legacy_link_nonce');
      const oidc=await metadata().catch(()=>null);
      if(oidc?.end_session_endpoint)
        window.location.assign(oidc.end_session_endpoint+'?'+new URLSearchParams({
          client_id:cfg.client_id,post_logout_redirect_uri:cfg.redirect_uri
        }));
    }
  };
})();