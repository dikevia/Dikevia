# V3.6 — Espace utilisateur et tableau de bord

## Fonctionnalités de l'interface
- Espace d'accueil responsive et navigation par rubriques.
- Connexion navigateur OIDC en Authorization Code + PKCE pour un client public.
- Sélection d'une organisation parmi les adhésions actives du compte.
- Tableau de bord avec compteurs de documents, collectivités et membres (compteur membres réservé aux administrateurs).
- Consultation et recherche plein texte des documents de l'organisation active ; téléchargement des documents autorisés.
- Dépôt PDF/DOCX réservé aux rôles `ORG_ADMIN` et `LEGAL_EDITOR` ; le backend réalise l'analyse antivirus, l'extraction et l'indexation.
- Mise à jour du statut de validation documentaire réservée aux rôles `ORG_ADMIN` et `LEGAL_EDITOR`.
- Consultation des collectivités et création réservée à `ORG_ADMIN`.
- Consultation des membres, invitation et révocation réservées à `ORG_ADMIN`.
- Envoi d'une question juridique depuis l'espace actif.

## Configuration OIDC navigateur
1. Modifier `frontend/auth-config.js` en reprenant la structure de `frontend/auth-config.example.js`.
2. Renseigner l'émetteur HTTPS exact, le `client_id` d'une application publique et l'URI de redirection correspondant exactement à l'URL déployée.
3. Configurer le fournisseur pour Authorization Code + PKCE (S256), sans client secret, et autoriser l'origine/URI de redirection.
4. Vérifier que le fournisseur autorise les appels CORS navigateur au token endpoint.
5. Côté API, aligner `OIDC_ISSUER`, `OIDC_AUDIENCE` et `OIDC_JWKS_URL`. Le jeton d'accès doit contenir les claims attendus par l'API ; l'acceptation des invitations requiert un claim `email` vérifié.
6. Ne jamais committer `auth-config.js` avec une configuration réelle si la politique du déploiement interdit de publier le nom du client ou les URLs internes. Aucun secret client ne doit être placé dans le navigateur.

Le module conserve le jeton d'accès uniquement en mémoire et ne persiste pas de refresh token. À expiration, l'utilisateur doit relancer la connexion. Le vérificateur PKCE et l'état OAuth sont stockés temporairement dans `sessionStorage` pendant l'aller-retour d'authentification.

## Sécurité et limites
- Chaque appel métier envoie `X-Organization-ID` de l'espace sélectionné ; le backend vérifie l'adhésion et applique le contexte RLS. La sélection côté navigateur n'est jamais considérée comme une autorisation.
- Les contrôles de rôle côté interface améliorent l'expérience mais ne remplacent pas les contrôles serveur.
- Le jeton brut d'invitation est affiché une seule fois à l'administrateur pour transmission par un canal sûr ; aucun e-mail n'est envoyé automatiquement.
- L'interface ne constitue pas une preuve de conformité RGPD, une politique CSP complète, ni une validation juridique du corpus.
- L'authentification réelle dépend du fournisseur OIDC et de sa configuration ; aucun fournisseur n'est livré ou préconfiguré dans ce kit.
- Le navigateur appelle l'API sur la même origine. En cas de déploiement séparé, configurer explicitement CORS et HTTPS.

## Essais avant production
- Parcours OIDC réel (connexion, retour, code expiré, mauvais state, expiration du jeton, déconnexion).
- Vérification des claims réellement émis par le fournisseur et de l'audience API.
- Tests PostgreSQL/RLS avec au moins deux organisations et des comptes aux rôles différents.
- Tests upload/download avec ClamAV réel, et essais de fichiers malveillants de test.
- Tests responsive, accessibilité clavier, CSP et politique de cookies/session du fournisseur.
