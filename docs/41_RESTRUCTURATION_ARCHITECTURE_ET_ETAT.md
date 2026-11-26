# Dikévia — audit de consolidation et plan de restructuration
Date : 26 novembre 2026
Branche de travail : `refactor/dikevia-shells-2026-11-26`
Base : `feature/dikevia-free-vector-search-poc`

## 1. Règles de gouvernance

- La production et ses données ne sont pas modifiées dans ce chantier.
- Les changements sont d'abord réalisés sur une branche de restructuration, puis contrôlés avant toute intégration au staging.
- Aucun déploiement automatique : le service Render de staging est configuré avec `autoDeploy=off`.
- Aucun nouvel outil payant, abonnement, fournisseur ou appel facturable ne doit être introduit. TinyFish est exclu.
- Une fonctionnalité n'est considérée comme acquise qu'après distinction de quatre états : conçue, codée, déployée, vérifiée fonctionnellement.
- Les travaux existants doivent être récupérés et consolidés ; pas de réécriture destructive ni de suppression sans preuve d'équivalence.

## 2. État observé au moment de l'audit

### Déploiement staging
- Service Render : `dikevia-vector-beta-staging`.
- Branche configurée : `feature/dikevia-free-vector-search-poc`.
- Déploiement courant observé : commit `e055dc6c3490b17f507023ead7b608217b7ed13d`, statut Render `live`.
- Auto-deploy désactivé.
- Le statut `live` confirme la fin du déploiement, pas la recette visuelle ou fonctionnelle dans un navigateur/appareil.

### Interface
- Le backend sert `frontend/index.html` à la racine HTTP. Le fichier racine `index.html` n'est pas celui renvoyé par cette route.
- L'application Standard et l'Administration partagent actuellement `frontend/index.html`, avec des modes sélectionnés par `dikevia_app` et conservés dans `sessionStorage`.
- La feuille `frontend/dikevia-chat-theme.css` contient plusieurs couches historiques, puis des overrides JARVIS bleu glacier pour `dikevia-standard-app` et `dikevia-admin-mode`.
- Le mode Standard était activé seulement si `dikevia_app=standard` ou si ce mode avait été conservé en session. Sans paramètre, l'entrée navigateur choisissait `web`, qui ne recevait pas la classe CSS JARVIS Standard. Cela explique une partie plausible du retour à l'ancienne interface dans le navigateur.
- Première correction isolée sur cette branche : le mode navigateur par défaut devient Standard ; le mode Administration reste explicitement sélectionné par `dikevia_app=admin`.
- Cette correction de sélection de mode n'est pas encore déployée ni testée sur appareil.

### Authentification
- Le code navigateur contient le flux OIDC Authorization Code + PKCE, le choix explicite Google et un mécanisme de double preuve pour rattacher une identité Keycloak historique à l'identité Auth0.
- Le backend expose une configuration OIDC runtime sur `/auth-config.js`, générée à partir des variables d'environnement. Le fichier statique de repli `frontend/auth-config.js`/son modèle reste historique Keycloak ; il ne constitue pas une preuve que le runtime est configuré Auth0.
- La présence du code Auth0 ne prouve pas la validation complète des jetons, du rattachement d'identité ou des droits dans l'environnement cible.
- La migration de production reste interdite tant que les tests d'identité, de continuité des comptes et de retour arrière ne sont pas terminés.

### Android
- Deux demandes de fusion distinctes sont ouvertes : PR #143 et PR #144, toutes deux pour les APK Android Auth0/staging/identité bleue. Elles sont redondantes en intention et doivent être comparées avant d'en retenir une.
- Les variantes Android ciblent le staging via `?dikevia_app=standard` et `?dikevia_app=admin`.
- Un build réussi ne vaut ni installation ni test de connexion ni recette de l'interface.

### Moteur juridique
- Le commit `b611a9372b2f3fa9c446d7ba6e3d7d3fe30dd0b6` contient des corrections de pertinence de recherche FPT, de fallback de modèle Gemini et de tests associés.
- Ces changements doivent être conservés et audités séparément de la refonte de l'interface.
- Les améliorations du moteur ne doivent pas être déclarées validées en production sur la seule base de tests unitaires ou d'une présence dans une branche.

## 3. Architecture cible à consolider

1. **Application Standard** : expérience conversationnelle juridique, historique, dossiers et outils agents ; identité JARVIS glacier/acier/bleu nuit ; noyau IA discret et animé.
2. **Application Administration** : interface de pilotage uniquement (organisations, utilisateurs, rôles, invitations, abonnements, configuration et supervision). Aucun chatbot utilisateur.
3. **Socle partagé** : authentification OIDC, appels API, composants de formulaire/tableau, tokens de design et gestion des erreurs, sans mélanger les navigations des deux applications.
4. **Backend/API** : conserver les règles d'autorisation, l'isolation multi-organisation, les validations juridiques et la traçabilité ; ne pas coupler la logique métier à la présentation.
5. **Configuration d'environnement** : une source runtime documentée par environnement ; pas de configuration Auth0/Keycloak contradictoire embarquée dans les fichiers statiques.
6. **Android** : deux variantes clairement liées à leurs points d'entrée Standard et Administration ; même politique de sécurité WebView, sans URL de production dans les APK de test.

## 4. Ordre de travail

### Lot A — inventaire et cartographie
- Comparer les branches et demandes de fusion depuis le 25 novembre.
- Identifier les commits réellement présents dans le staging, ceux qui ne sont que dans des branches et ceux qui sont déjà intégrés à `main`.
- Cartographier les points d'entrée HTTP, scripts, styles, modes, variables runtime et dépendances.
- Détecter les duplications et les chemins morts avant suppression.

### Lot B — séparation des interfaces
- Extraire les styles communs dans un socle unique.
- Isoler les styles et composants Standard et Administration.
- Éliminer les anciennes règles vert forêt/émeraude/or résiduelles après vérification de leur absence d'usage.
- Garantir que le mode navigateur Standard active bien JARVIS et que l'Administration reste distincte.
- Vérifier les vues mobile et desktop, clavier, focus, réduction des animations et états vides/erreur.

### Lot C — authentification
- Confirmer les valeurs publiques runtime (issuer, audience, client ID, redirect URI) sans exposer de secrets.
- Vérifier discovery, JWKS, PKCE, callback, jeton d'accès, ID token, /auth/me et contrôle des rôles.
- Tester le rattachement Keycloak/Auth0 avec deux preuves fraîches et un nonce à usage unique.
- Maintenir Keycloak en production tant que la recette Auth0 et le plan de retour arrière ne sont pas approuvés.

### Lot D — Android
- Comparer PR #143 et #144 ; retenir une seule ligne de livraison.
- Construire les deux APK depuis la branche contrôlée.
- Vérifier empreintes, version, URL embarquées et hôtes de confiance.
- Installer et tester réellement les deux parcours, y compris connexion et retour de callback.

### Lot E — moteur juridique et exploitation
- Auditer les changements depuis le 25 novembre sans les écraser.
- Exécuter CI complète, tests PostgreSQL/RLS, tests contractuels et cas juridiques représentatifs.
- Tester les réponses de bout en bout avec sources officielles, temporalité, références et abstention.
- Contrôler les quotas et coûts avant tout appel à un fournisseur externe.

## 5. Critères de sortie

Aucun lot n'est déclaré terminé sans :
- commit identifié et diff relu ;
- tests pertinents exécutés et résultat conservé ;
- déploiement staging identifié par son SHA, s'il y a lieu ;
- contrôle fonctionnel réel de l'interface ou du parcours concerné ;
- limites et points non testés explicitement documentés.

## 6. Première correction de ce chantier

Le mode d'entrée navigateur sans paramètre est désormais réglé sur Standard sur la branche de restructuration. Cette modification n'a pas été fusionnée dans la branche staging, n'a pas été déployée et n'a pas été testée sur appareil.
