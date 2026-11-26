# Dikévia — état de consolidation et règles de restructuration
Date : 26 novembre 2026

## Règle de travail
Toutes les modifications doivent être réalisées directement sur `feature/dikevia-free-vector-search-poc`, branche utilisée par le service Render de staging. Ne pas créer de branche de travail supplémentaire ni de chantier parallèle. La production ne doit pas être modifiée.

Contraintes : aucun outil payant ou service facturable ajouté sans autorisation explicite ; TinyFish est exclu. Préserver les avancées existantes avant toute simplification.

Une fonctionnalité doit être classée séparément comme conçue, codée, déployée et vérifiée. Un commit ou un build ne prouve pas une validation fonctionnelle.

## Constat technique
- Le service Render `dikevia-vector-beta-staging` utilise `feature/dikevia-free-vector-search-poc`, avec auto-déploiement désactivé.
- Le backend sert `frontend/index.html` à la racine HTTP.
- Standard et Administration partagent actuellement ce point d'entrée, avec un paramètre `dikevia_app` et un état de session pour choisir le mode.
- La feuille `frontend/dikevia-chat-theme.css` contient des couches historiques ainsi que des overrides JARVIS bleu glacier. La coexistence de règles anciennes et nouvelles rend le résultat difficile à diagnostiquer.
- Le mode navigateur sans paramètre choisissait `web`, qui n'activait pas la classe CSS JARVIS Standard. Correction appliquée sur cette branche : le mode par défaut est désormais `standard`. Le mode Administration reste sélectionné explicitement par `dikevia_app=admin`.
- Cette correction n'est pas encore déployée ni testée sur appareil.

## Travaux existants à préserver et auditer
- Auth0/OIDC : le code contient Authorization Code + PKCE, choix Google et mécanisme de double preuve pour le rattachement d'identités historiques. Le backend expose une configuration runtime `/auth-config.js`. La présence du code ne prouve pas que toutes les variables runtime, les jetons, les rôles et les callbacks sont validés dans l'environnement.
- Android : deux PR ouvertes (#143 et #144) poursuivent des objectifs proches autour des APK Auth0/staging. Les comparer et consolider une seule voie de livraison avant toute fusion.
- Moteur juridique : le commit `b611a9372b2f3fa9c446d7ba6e3d7d3fe30dd0b6` comprend des corrections de pertinence FPT, un fallback de modèle et des tests associés. Les conserver et les auditer séparément de la refonte UI.
- Ne pas migrer l'authentification de production de Keycloak vers Auth0 avant validation complète et plan de retour arrière.

## Architecture cible
1. Application Standard : chatbot juridique réellement conversationnel, historique et outils agents ; identité JARVIS bleu glacier, bleu acier et bleu nuit ; noyau IA discret et animé.
2. Administration : pilotage des organisations, utilisateurs, rôles, invitations, abonnements, paramétrage et supervision. Aucun chatbot destiné aux agents.
3. Socle partagé : authentification, appels API, composants communs et tokens graphiques ; séparation des navigations et composants métier.
4. Backend : autorisations, isolation multi-organisation, traçabilité et logique juridique indépendantes de la présentation.
5. Configuration : une source runtime documentée par environnement ; pas de configurations Auth0/Keycloak contradictoires embarquées dans les fichiers statiques.
6. Android : deux variantes clairement liées aux points d'entrée Standard et Administration, URLs de test staging et hôtes de confiance minimaux.

## Ordre d'exécution
A. Cartographier les commits depuis le 25 novembre, branches, PR, fichiers, scripts, styles, variables runtime et déploiements réellement servis.
B. Séparer proprement les interfaces Standard et Administration, extraire le socle graphique commun, supprimer les règles obsolètes seulement après preuve qu'elles ne sont plus utilisées.
C. Valider Auth0 : discovery, issuer, audience, PKCE, callback, jetons, /auth/me, rôles et migration d'identité ; maintenir la production inchangée.
D. Comparer les PR Android, retenir une seule voie, builder, installer et tester les deux APK.
E. Reprendre le moteur juridique sans écraser les travaux, exécuter CI, tests de sécurité/multi-tenant et cas juridiques de bout en bout avec sources officielles et abstention.

## Critères d'acceptation
Chaque lot doit avoir un diff relu, des tests exécutés et leurs résultats, un SHA de déploiement si déployé, une vérification fonctionnelle réelle et une liste explicite des limites non testées. Aucun lot n'est déclaré terminé sur la seule base d'une compilation ou d'un statut Render `live`.
