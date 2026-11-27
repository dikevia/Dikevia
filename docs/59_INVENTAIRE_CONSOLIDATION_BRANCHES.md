# Inventaire de consolidation GitHub — Dikévia

Date de l'audit : 27 novembre 2026  
Dépôt : `dikevia/Dikevia`  
Branche de référence : `main`  
Statut : inventaire partiel approfondi, récupération sélective en cours

## 1. Règle de consolidation

La cible est un dépôt dont `main` contient l'intégralité du produit maintenu. Les branches historiques ne sont pas des environnements de déploiement et ne doivent pas être fusionnées en bloc. Les différences doivent être évaluées fichier par fichier et, lorsque nécessaire, au niveau des fonctions et tests.

Les branches ne doivent pas être supprimées tant que :
- l'inventaire des commits et différences n'est pas terminé ;
- chaque changement utile n'est pas intégré et vérifié dans `main` ;
- les branches qui constituent une seule copie des commits déjà intégrés ne sont pas identifiées ;
- les développeurs responsables du dépôt n'ont pas validé la sauvegarde et la suppression.

## 2. Volume et méthode

La recherche paginée GitHub a retourné 143 branches au total, dont `main). Un premier ensemble de branches a été comparé directement à `main` avec l'API GitHub Compare.

Attention : `ahead_by` indique le nombre de commits propres à une branche dans la comparaison, pas le nombre de fonctionnalités encore absentes. Une branche peut être très divergente et ancienne, et contenir du code déjà remplacé dans `main`. Les fichiers listés dans une comparaison doivent être relus sur leur contenu actuel avant toute récupération.

## 3. Constat mobile

### État réel de main

- Le projet Android présent dans `main` est une enveloppe `WebView`, pas une application native Jetpack Compose.
- Les deux variantes standard et administration pointent actuellement vers l'URL de staging dans le build Gradle.
- Les hôtes de confiance incluent encore plusieurs domaines Render historiques et l'ancien hôte Keycloak en plus de l'hôte Auth0 de développement.
- La documentation `android/README.md` confirme que la recette Auth0 sur appareil réel n'est pas validée.
- Aucun projet iOS n'a été trouvé à la racine du dépôt.

### Prototype Android natif historique

La branche `android/native-compose-integration` contient une application Jetpack Compose avec :
- écrans natifs login, accueil, assistant, historique, documents, collectivités, membres et profil ;
- OIDC Authorization Code + PKCE avec AppAuth ;
- appels API avec jeton Bearer et en-tête d'organisation ;
- client HTTP avec délais explicites ;
- début de conservation/renouvellement de session.

Mais elle utilise explicitement :
- `https://dikevia-commercial-api-l2r8.onrender.com` comme API ;
- `https://dikevia-identity-l2r8.onrender.com/realms/cfdt` comme issuer Keycloak ;
- un client OIDC dont la configuration n'est pas transposable telle quelle à Auth0.

Elle est fortement divergente de `main` (192 commits en avance et 2 130 en retard au moment de la comparaison) et son diff inclut de nombreux fichiers backend, migrations, données de corpus et documentation. **Ne pas fusionner cette branche entière.**

La branche `android/native-compose-beta-v2` contient un prototype natif plus petit (19 commits propres, 2 130 en retard), mais conserve les mêmes dépendances Keycloak/API historique. Son README précise que le client Android et l'audience API n'étaient pas confirmés. Ne pas l'utiliser sans adaptation.

La branche `feat/dikevia-two-android-apps` est une enveloppe WebView, pas une application native. Elle dépend aussi des anciens domaines Render/Keycloak.

Décision : récupérer uniquement le travail d'interface Compose et les composants réutilisables après audit, en remplaçant l'authentification par une intégration Auth0 native, l'URL API par le service Render unique et les appels par les contrats backend actuels. Ne pas embarquer de secret dans l'application. Prévoir une architecture mobile cohérente Android/iOS plutôt que deux applications indépendantes ayant des règles métier divergentes.

## 4. Auth0 et identité

Branches comparées :
- `feat/auth0-oidc-foundation` : 72 commits propres, 985 en retard. Contient des changements de sécurité/OIDC, de dépendances, de configuration, de frontend, scripts de migration Keycloak et un `render.yaml` ancien.
- `fix/auth0-api-audience-alignment` : 17 commits propres, 640 en retard. Contient plusieurs fichiers backend, tests OIDC, contrats d'invitation, diagnostics, configuration de déploiement.
- `fix/auth0-provider-blueprint` : 19 commits propres, 640 en retard, changements très proches de la précédente avec différences sur certains tests/configurations.
- `fix/beta-user-runtime-sync` : 1 commit propre, 1 169 en retard ; changements sur identité runtime, périmètre FPT, corpus et frontend.

### Récupération ciblée effectuée depuis `security/runtime-role-guard`

La comparaison a confirmé que `backend/app/db.py` est déjà identique dans cette branche et dans `main` : la protection au démarrage contre les rôles PostgreSQL `SUPERUSER` et `BYPASSRLS` est déjà présente pour les pools API, ingestion et administration de plateforme.

En revanche, la branche comportait des tests de régression absents de `main`. Les trois groupes de tests ont été repris uniquement dans `backend/tests/test_v35_runtime_security.py` :
- vérification des trois pools configurés ;
- refus d'un rôle SUPERUSER ou BYPASSRLS dans chacun des pools ;
- omission des pools optionnels non configurés.

Commit de récupération sur `main` : `d6de01c8ad84627282854ad4fee1c4fa84bed5d7`.

Aucun code runtime n'a été remplacé. Les tests n'ont pas encore été exécutés : le statut GitHub et la liste des workflows pour ce commit sont vides. Le changement est donc intégré mais non validé par exécution.

Décision : comparer les implémentations Auth0 avec le code courant de `main`, puis reprendre uniquement les corrections non déjà présentes. Ne pas récupérer de fichier de configuration Render ou de migration d'identité sans vérifier les valeurs et l'environnement cible. Ne pas exécuter de migration de comptes sans plan explicite et procédure de retour arrière.

### Audit complémentaire du code Auth0 actuel dans main

- `backend/app/dependencies.py` valide les jetons Auth0, vérifie le jeton d'identité OIDC et peut mapper une identité historique uniquement via issuer/subject et RLS, sans rapprochement par e-mail.
- `backend/app/security.py` vérifie la signature, issuer, audience, expiration, algorithmes et concordance subject/issuer des jetons.
- `backend/app/config.py` garde néanmoins le choix `oidc_provider` entre `keycloak` et `auth0`, ainsi que les paramètres Keycloak Admin.
- `backend/app/main.py` importe encore `KeycloakAdmin` et conserve un chemin de provisionnement Keycloak conditionnel. Le chemin Auth0 s'appuie sur Universal Login et envoie seulement l'invitation Dikévia.
- `render.yaml` contient encore deux services historiques, l'API sur l'ancienne branche et Keycloak. Son commentaire interdit explicitement une synchronisation sans plan de migration production.

Conclusion : l'authentification Auth0 existe dans le code, mais l'élimination complète de Keycloak n'est pas encore démontrée. La transition doit être effectuée en conservant la compatibilité des comptes et des invitations, puis en retirant le code et service Keycloak seulement après validation du dernier compte et des flux de récupération.

## 5. Chatbot et recherche juridique

Constats de comparaison :
- `fix/chat-orchestration-lot1` : 74 commits propres, 1 170 en retard, avec nombreux changements orchestrateur, fournisseur IA, CGFP, recherche, assurance juridique et tests. Diff trop large pour une fusion globale.
- `fix/conversation-topic-shift` : 2 commits propres, 963 en retard ; le fichier `legal_qualification.py` est déjà plus avancé dans `main` sur plusieurs règles de contexte et de statut. Aucun cherry-pick automatique.
- `fix/fpt-ihts-medicosocial-exceptions-v2` : 2 commits propres, 960 en retard ; uniquement orchestrateur et test IHTS ciblé à examiner.
- `fix/temporal-endpoint-claim-guard` : 94 commits propres, 2 134 en retard ; diff large backend, tests, configuration et docs, à considérer comme archive d'idées et de correctifs, pas comme une branche de livraison.
- `fix/verified-legal-status-combined` : 20 commits propres, 640 en retard ; changements de corpus, recherche, orchestrateur et contrats Auth0.
- `fix/disable-recurring-startup-provider-probes` : 13 commits propres, 640 en retard ; correction potentielle de comportement de démarrage, à auditer dans le code courant.
- `fix/shared-legal-corpus-reader` : 27 commits propres, 640 en retard ; modifications corpus, import, backend, workflows et render.yaml.
- Plusieurs branches telles que `fix/chatbot-agent-situations-retrieval`, `fix/chatbot-coherence-explanatory-answers`, `fix/chatbot-retrieval-convocation-fallback` sont derrière `main` (aucun commit propre dans la comparaison) : elles ne justifient pas de fusion.

Décision : priorité aux correctifs étroits encore absents de `main`, avec tests ciblés. Ne pas réimporter des versions anciennes de l'orchestrateur ou du corpus.

## 6. Autres familles repérées dans les 143 branches

- CI et tests : workflows Android, provider retry, embedding parity, corpus audit, commercial checks, live smoke tests.
- Corpus : sources officielles, Service-Public, SIG, provenance et ingestion.
- Sécurité : ownership conversations, opt-in documents locaux, runtime role guard.
- Produit et interface : design Emerald, drawer conversationnel, UI mobile, navigation, thèmes.
- Offres et administration : pricing, capacité bêta, invitations, abonnements et facturation.
- Exploitation : diagnostics OIDC, récupération Keycloak, drapeaux de sécurité, observabilité corpus.

Ces familles restent à comparer individuellement. Les branches relatives à Stripe/paiement ne doivent pas activer de paiement ni de fournisseur payant ; les branches Keycloak ne doivent pas réintroduire Keycloak dans la cible.

## 6 bis. Contrôles supplémentaires effectués le 27 novembre 2026

### Branches de tests et de CI

- `fix/p0-ai-usage-outcome-constraint` : la migration 020 et le test de contrat de contrainte sont strictement identiques à `main`. Aucun transfert.
- `test/provider-http-status-matrix-main` : la branche est moins avancée que `main` ; le test courant contient déjà les scénarios supplémentaires de timeout et de cache. Aucun transfert.
- `fix/disable-recurring-startup-provider-probes` : sa version de `main.py` est une génération antérieure, avec moins de routes et des protections Auth0/session/RLS absentes. Le code de cette branche est rejeté comme source de fusion.
- `fix/telemetry-failure-isolation` : le test d'isolation de télémétrie est déjà identique à `main`. Le code applicatif de la branche est trop ancien et contient des parcours de paiement Stripe actifs qui ne correspondent pas aux décisions actuelles. Aucun transfert.
- `fix/service-public-reference-id-provenance` : le script d'import Service-Public et son test principal sont identiques à `main`. Aucun transfert.
- `fix/sig-official-source-page-urls` : son registre de sources est plus ancien. Il marque encore les données ouvertes de la justice administrative comme `CANDIDATE`, alors que `main` a enregistré la revue d'accès du 26 novembre et le statut `ACCESS_REVIEWED`. La version de cette branche ne doit pas écraser le registre actuel.
- `security/runtime-role-guard` : seul son complément de tests a été repris (voir section 4 bis).

### Identités Auth0 historiques : migration par e-mail rejetée

La branche `fix/auth0-google-legacy-account-linking` propose une fonction SQL `link_auth0_google_legacy_user` qui rattache un sujet Google Auth0 à un compte Keycloak historique sur la base d'une adresse e-mail vérifiée et unique. Même si la migration est limitée à un issuer Auth0 de staging et refuse les correspondances multiples, cette approche utilise l'e-mail comme clé de rapprochement. Elle ne respecte pas la règle de Dikévia : l'accès fondateur et l'identité applicative doivent être attachés à l'identité OIDC vérifiée (issuer + subject), et jamais attribués ou fusionnés sur la seule adresse e-mail. La migration 029 de cette branche entre également en conflit de numérotation/contenu avec la migration 029 déjà présente sur `main` (sessions OIDC). **Ne pas intégrer et ne pas exécuter cette migration.**

La famille `feat/dual-proof-keycloak-auth0-linking` dépend de cette migration 029 et ajoute une migration 030 ; elle est également exclue de toute fusion en bloc. Toute migration de comptes historiques devra être conçue sur une preuve de contrôle des deux identités, une table de correspondance auditable et un parcours explicite, sans attribution par e-mail.

### Design mobile et identité visuelle

La branche `design/emerald-interface-refresh` contenait un document de système de design cohérent avec les décisions visuelles Dikévia : émeraude comme couleur de marque et d'action, or limité aux libellés de boutons principaux sur vert profond et à quelques détails, jamais aux contenus juridiques ou fonds généraux. Le document a été adapté pour couvrir Android, iOS et le web complémentaire puis intégré sur `main` sous `docs/60_SYSTEME_DESIGN_EMERAUDE_OR.md`.

Commit : `da4fbd75ae1006b7e3ade40ac0d32eb557c52c58`. Aucun écran applicatif n'a été modifié dans ce transfert documentaire.

### Décision

Ces comparaisons confirment qu'un grand nombre de commits propres à des branches ne sont pas des évolutions manquantes : ce sont des versions antérieures ou des duplications de fichiers déjà intégrés dans `main`. La consolidation doit être basée sur le contenu des fichiers, et non sur le nombre de commits en avance.

## 7. Consolidation des comptes et des services

La cible d'exploitation doit éviter les identités et configurations dispersées :
- un dépôt GitHub canonique pour le code produit ;
- une seule branche de développement, `main` ;
- un seul workspace Render propriétaire du service applicatif Dikévia ;
- un seul service applicatif Render pour le backend et les interfaces web/API ;
- un tenant Auth0 de référence, avec séparation documentée des environnements/clients et des callbacks ;
- un seul projet Neon de référence, avec branches/bases séparées pour les environnements et aucune confusion des données.

Cette cible signifie une source de vérité et un périmètre de propriété clair par fournisseur, pas le partage de mots de passe ni l'utilisation d'un compte personnel commun. Pour GitHub, privilégier un dépôt canonique dans une organisation contrôlée par le propriétaire du produit, avec des accès nominatifs. Pour Render, un workspace propriétaire et un service applicatif. Pour Auth0, un tenant de référence avec des applications/clients distincts si les environnements l'exigent. Pour Neon, un projet de référence avec des branches de base de données distinctes par environnement.

Lors de l'audit Render précédent, un seul workspace Render était visible ; le problème identifié est donc la multiplicité des services et des branches de déploiement, pas la preuve de plusieurs comptes Render. Ne pas déplacer la propriété ou fusionner des comptes fournisseurs sans vérifier les propriétaires, rôles, facturation, domaines, secrets, données et capacité de récupération. Ne jamais partager un compte administrateur personnel ni centraliser des secrets dans Git.

## 8. Prochaines actions ordonnées

1. Terminer l'inventaire paginé des 143 branches et les comparer par familles.
2. Pour chaque branche avec commits propres, identifier les fichiers et fonctions réellement absents de `main`.
3. Reprendre en premier les corrections de sécurité/identité et les tests étroits, après vérification des versions courantes.
4. Concevoir l'architecture mobile cible (réutilisation des composants Kotlin, partage de logique, stratégie iOS et CI).
5. Adapter les applications à Auth0 et au backend unique.
6. Consolider le backend et les configurations de déploiement sans écraser les secrets.
7. Valider le service unique Render et l'isolation Neon.
8. Vérifier le privilège fondateur permanent, exclusivement sur identité Auth0 OIDC vérifiée.
9. Exécuter les contrôles sur le SHA exact de `main` avant toute déclaration de conformité.

## 9. Garde-fous

- Aucun déploiement production.
- Aucun frais, plan payant ou service payant.
- Aucun changement destructif de base, compte, branche, service ou volume pendant l'inventaire.
- Aucune fusion globale de branches.
- Aucun secret dans le dépôt ou dans les applications mobiles.
- Aucun test IA réel consommant quota sans autorisation distincte.
- Aucun développement métier tant que l'architecture cible n'est pas conforme.
- Les travaux d'architecture doivent être commits directement sur `main`.

### Rectification et récupération de l'identité visuelle

Le document provisoire `docs/60_SYSTEME_DESIGN_EMERAUDE_OR.md` a été supprimé : la direction Émeraude & Or avait été abandonnée. La référence JARVIS a été retrouvée directement dans `frontend/dikevia-chat-theme.css` sur `main` (bloc final « DIKEVIA JARVIS — palette verrouillée : glacier / acier / bleu nuit »), ainsi que dans les commentaires Android.

Le document `docs/60_IDENTITE_VISUELLE_JARVIS.md` décrit maintenant cette source de vérité. Le code comporte déjà une sphère d'accueil bleue avec anneaux et pulsation CSS, ainsi que des styles prévus pour les états `is-generating` et `is-speaking`. En revanche, il reste à vérifier que ces états sont effectivement pilotés par le JavaScript et à concevoir une sphère persistante réactive aux états réels du moteur. Ne pas présenter l'animation actuelle comme une sphère 3D ou audio-réactive.

### Audit mobile approfondi

L'analyse de `android/` sur `main` confirme que les deux flavors Android sont des WebView, pas des applications natives. Aucun projet iOS n'a été retrouvé à la racine ni dans les branches recherchées par les termes `ios`, `native`, `mobile` et `design`.

La branche `android/native-compose-integration` fournit des composants Jetpack Compose utiles, mais reste non intégrable telle quelle : API Render historique, issuer Keycloak, client OIDC Keycloak, palette Émeraude & Or, activité monolithique et session non persistée après fermeture complète. Le diff est très divergent (192 commits en avance, 2 130 en retard au moment du contrôle). Elle ne doit pas être fusionnée globalement.

Les détails de l'audit et la trajectoire Android Compose / iOS SwiftUI sont dans `docs/61_AUDIT_MOBILE_ET_MIGRATION_NATIVE.md`. Le README Android a été rectifié pour ne plus présenter les WebView comme des applications natives.


### Sécurité des conversations et confidentialité des documents locaux

Les branches `security/chat-explicit-ownership` et `security/chat-local-documents-opt-in` ont été comparées à `main`. Leurs fichiers sont fortement en retard et ne doivent pas être fusionnés. L'examen des tests montre toutefois que les contrôles essentiels ont déjà été repris et consolidés dans `main`, notamment dans `backend/tests/test_chat_ownership_privacy.py` :
- les requêtes de conversations et dossiers filtrent par organisation et propriétaire ;
- les documents locaux sont exclus du payload IA sans consentement ;
- le planificateur de recherche ne reçoit pas les documents locaux du tenant ;
- les documents locaux dans l'historique ne sont pas réutilisés par l'IA sans consentement ;
- deux opt-in indépendants sont exigés (paramétrage serveur et confirmation explicite de la requête) ;
- l'interface demande une case à cocher fraîche pour chaque transfert ;
- l'historique utilisateur conservé est limité à une liste autorisée de métadonnées.

Le fichier de test historique `test_v338_local_document_ai_privacy.py` n'existe pas sous ce nom dans `main`, mais ses scénarios ont été regroupés dans le test actuel `test_chat_ownership_privacy.py`. Aucun transfert de code ni de test n'est nécessaire pour cette famille.


### Facturation, offres et privilège fondateur

- Dans `main`, `STRIPE_BILLING_ENABLED` est à `false` par défaut. La validation de configuration exige les deux secrets Stripe lorsque cette option est activée et impose les contrôles de configuration associés. Les tests actuels vérifient que Stripe reste désactivé par défaut.
- Les branches `fix/stripe-billing-explicit-opt-in`, `feature/new-economic-pricing-grid` et `feature/pricing-ui-alignment-v2` sont très en retard et ne doivent pas remplacer la logique commerciale actuelle.
- `feature/72h-trial-founder-access-design` est explicitement incompatible avec la décision d'accès fondateur permanent : sa période d'essai de 72 h et sa migration dédiée ne doivent pas être reprises.
- La migration 026 de `main` stocke `user_id`, `oidc_issuer` et `oidc_subject`, interdit les écritures directes du rôle applicatif et expose l'attribution/révocation via des fonctions réservées à l'administration plateforme. La policy RLS de lecture vérifie l'issuer et le subject du contexte OIDC ; l'attribution ne repose pas sur l'e-mail.
- `resolve_entitlements(founder=True)` supprime le quota quotidien (valeur `None`) et active les outils syndicat, mais retourne actuellement `max_users=15`. Cela ne limite pas le nombre de questions, mais reste un plafond d'accès organisationnel à vérifier si le privilège fondateur devait aussi être illimité en nombre de sièges. Aucun changement n'a été effectué sur ce point.
- Aucun paiement, activation Stripe, attribution d'accès fondateur ou migration n'a été exécuté pendant cet audit.


### Provenance des références et registre des sources

- La branche `chore/audit-service-public-reference-provenance` contient `scripts/audit_staging_reference_provenance.py` et ses tests, mais les deux fichiers sont déjà strictement identiques dans `main`. Aucun transfert.
- La branche `corpus/add-sig-info-gouv-guidance` est une version antérieure du registre : `main` contient déjà le domaine `info-gouv`, les tests de registre et davantage de contrôles de gouvernance. Son registre ne doit pas écraser la version actuelle.
- Les branches documentaires Auth0 et readiness examinées sont des versions antérieures de documents déjà consolidés ; aucun remplacement global n'est justifié.


### Déploiement, CI et anciennes branches d'intégration

- `fix/deployment-branch-ci-trigger` et `fix/main-render-api-ci-trigger` n'ont aucun commit propre par rapport à `main` : leurs changements sont déjà intégrés ou dépassés.
- `fix/production-branch-push-ci` ne contient qu'un commit propre sur le workflow CI, mais la branche est très ancienne (plus de 2 100 commits derrière). Le workflow actuel de `main` doit rester la référence ; aucune reprise sans comparaison ligne par ligne.
- `integration/beta-commercial-security` est une branche très divergente (116 commits en avance, 2 149 en retard) et contient d'anciennes migrations 020–022, un realm Keycloak, l'ancien backend et le prototype Android. Ses numéros de migration entrent en collision avec l'historique courant ; fusion globale interdite.
- `ops/pin-production-safety-flags` et `release/production-sync-main-safe` contiennent des snapshots de `render.yaml` et de backend antérieurs. Ne pas les utiliser pour synchroniser Render.
- Les documents `docs/beta-migration-019-sync` et `docs/android-twa-beta-gate` décrivent d'anciens parcours et des enveloppes TWA/WebView ; ils ne changent pas la cible native Android/iOS.
- Les branches archive staging sont des archives et ne sont pas des sources de livraison.


### Recherche juridique, sources CIG et thèmes alternatifs

- `feat/chatbot-cig-public-sources` : les cinq fichiers métier/documentaires comparés (deux modules CIG, deux tests et la documentation) sont identiques octet pour octet dans `main`. Les 16 commits propres de cette branche ne justifient pas de transfert.
- `feature/hybrid-legal-rag` et `fix/gemini-cgfp-fallback-main` n'ont aucun commit propre par rapport à `main`.
- `fix/gemini-cgfp-snapshot-fallback`, `fix/gemini-staging-diagnostics`, `feat/conversational-legal-analysis` et `fix/chatbot-relevance-gemini-commercial` contiennent des snapshots fonctionnels anciens. Ils sont conservés comme références d'audit, mais le développement métier/chatbot est suspendu jusqu'à conformité de l'architecture.
- `feature/dikevia-free-vector-search-poc` contient une migration Auth0/Google par identité historique et un ancien prototype mobile ; ne pas fusionner (risque de collision migration 029/030 et dépendances historiques).
- `feature/ui-five-color-themes` introduit un système de thèmes alternatifs concurrent. Il ne doit pas remplacer l'identité JARVIS verrouillée.


### Android, OIDC et icônes

- `fix/android-15-system-bars` propose un état Android 15 antérieur à la palette JARVIS et conserve les couleurs vertes. `main` a déjà les insets Android 15, les barres système claires et le fond bleu glacier : ne pas écraser le fichier actuel.
- `feat/android-launcher-icons` contient des icônes Émeraude & Or, alors que `main` contient les icônes bleues actuelles. Ne pas reprendre.
- Les branches `fix/android-oidc-login-bootstrap`, `fix/oidc-login-integration-beta`, `fix/oidc-silent-sso-session-restore`, `fix/oidc-api-401-diagnostics-2026-11-20`, `fix/oidc-browser-discovery-timeout-2026-11-20`, `fix/oidc-login-visibility`, `fix/dikevia-oidc-branding-init` et `release/oidc-client-id-blueprint` sont des implémentations ou configurations anciennes, en partie liées à Keycloak. Aucun merge global ; reprendre uniquement une correction isolée après comparaison avec le flux Auth0 actuel.

