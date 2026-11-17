# V3 — changements

- Conservation du kit documentaire V2 et de son périmètre fonctionnel.
- FastAPI mis à niveau en version d'API 3.0.0.
- Ajout validation JWT OIDC par JWKS, issuer, audience, expiration et algorithmes configurés.
- Ajout résolution serveur du membership et du tenant actif à chaque appel privé.
- Ajout contexte PostgreSQL transactionnel via `set_config(..., true)`.
- Refonte du schéma initial : adhésions, collectivités par tenant, versions documentaires, invitations, paramètres, abonnements, audit.
- Ajout de politiques RLS et FORCE RLS sur les tables métier privées.
- Ajout configuration PostgreSQL dans Docker Compose et runbook de séparation des rôles.
- Maintien du moteur juridique en mode fermé NON_VERIFIE.
- Pas d'historique persistant des conversations.

## Non livré / non certifié
- Aucun IdP réel connecté ni jeton réel testé.
- Aucune instance PostgreSQL accessible pendant cette génération : migrations et scénarios A/B non exécutés.
- Gestion complète des invitations, provisioning PLATFORM_ADMIN et CRUD documentaire non achevée.
- Connecteur Légifrance/PISTE, recherche locale, fournisseur IA et validation des citations non implémentés.
- Pas de déploiement ni de test d'intrusion.


## V3.1 — Administration et invitations
- Ajout de la création d'organisation réservée aux administrateurs plateforme.
- Ajout du bootstrap DBA hors API du premier administrateur plateforme.
- Ajout du cycle d'invitation à jeton aléatoire, hashé, à usage unique et lié à l'e-mail OIDC vérifié.
- Ajout des permissions SQL minimales pour le rôle runtime.
- Ajout des tests statiques de contrat V3.1.
- Les tests PostgreSQL réels et l'envoi d'e-mail restent à réaliser/configurer.
- Ajout de la révocation des invitations en attente et des en-têtes `Cache-Control: no-store` sur les réponses contenant le jeton.
- Ajout du contrat des routes V3.1 et d'un contrôle statique empêchant l'attribution du rôle plateforme par invitation.


## V3.2 — identité globale et tests d'isolation PostgreSQL

- Ajout de `003_global_identity_rls.sql` : RLS + FORCE RLS sur `users` et `platform_admins`.
- Politique `users_self_identity` : lecture/écriture limitée à l'issuer et au subject OIDC définis dans la transaction par l'API.
- Politique `platform_admins_self_read` : un compte ne peut consulter que son propre marqueur d'administration plateforme ; le rôle runtime ne reçoit aucun droit de modification sur cette table.
- Politique `platform_admins_bootstrap_insert` et script de bootstrap adaptés : le DBA établit explicitement l'identité OIDC avant de créer le premier administrateur plateforme, même avec FORCE RLS.
- Contexte OIDC désormais initialisé avant la lecture du profil, l'acceptation d'invitation et la vérification du rôle plateforme.
- Index unique sur le hash des invitations et index de recherche par organisation/état/expiration.
- Ajout de tests contractuels et d'un test d'intégration PostgreSQL à deux organisations.

### Validation V3.2 dans cet environnement

- Tests contractuels ciblés : 9 réussis.
- Test PostgreSQL réel : ignoré faute de `TEST_DATABASE_ADMIN_URL` et `TEST_DATABASE_URL`.
- Suite complète : non exécutable ici, car `asyncpg` n'est pas installé dans l'environnement (erreur de collecte).
- Aucun déploiement, aucune migration sur une base de production et aucun test OIDC externe n'ont été effectués.


## V3.3 — Gestion documentaire (2026-11-16)
- Ajout de la gestion des collectivités.
- Ajout de l'import privé PDF/DOCX avec limite de taille, contrôle de signature/structure et SHA-256.
- Ajout des versions, téléchargements authentifiés et validations par responsable juridique.
- Ajout de la migration SQL 004 et des permissions runtime minimales correspondantes.
- Stockage persistant via volume Docker dédié.
- Limites explicites : antivirus/OCR/indexation non intégrés ; recette PostgreSQL réelle et tests de bout en bout à exécuter.


## V3.4 — antivirus, extraction et recherche documentaire (2026-11-16)
- Ajout d'un contrôle ClamAV INSTREAM fail-closed avant enregistrement de chaque document et de chaque nouvelle version.
- Blocage des téléchargements des fichiers dont le scan n'est pas `CLEAN`, et route de rescannage des versions existantes.
- Extraction de texte PDF/DOCX bornée, sans OCR, sans exécution de macros ou de contenu actif.
- Ajout de `document_text` avec RLS/FORCE RLS, index GIN PostgreSQL et recherche plein texte en français cloisonnée par organisation.
- La recherche conserve le statut de validation juridique et ne branche pas encore les extraits au moteur IA.
- Ajout de tests unitaires du protocole ClamAV et de l'extraction DOCX.
- Ajout d'une route de réindexation des versions historiques après contrôle antivirus.

## V3.5 — Durcissement de l'authentification et du démarrage

- Validation de configuration au démarrage : OIDC complet ou absent hors production ; OIDC, base PostgreSQL et origines CORS explicites obligatoires en production.
- Refus des algorithmes JWT symétriques ou non sûrs ; liste limitée à RS256/ES256, vérification de signature, émetteur, audience, dates et claims requis.
- Limite de taille des jetons Bearer et délai réseau JWKS borné ; erreurs d'authentification volontairement non détaillées.
- En-têtes HTTP de sécurité, HSTS en production et désactivation des réponses API mises en cache.
- Distinction entre `/health` (vivacité) et `/ready` (disponibilité de PostgreSQL) ; documentation OpenAPI désactivée en production.
- Tests automatisés des règles de configuration et des limites de sécurité.

Les tests de cette version vérifient les règles applicatives ; ils ne remplacent pas une validation réelle contre un fournisseur OIDC et une base PostgreSQL de production.

## V3.6 — Espace utilisateur
- Remplacement de la page prototype par un tableau de bord responsive organisé par espace syndical.
- Ajout d'un module navigateur OIDC Authorization Code + PKCE pour client public, jeton en mémoire et absence de refresh token persistant.
- Ajout de la configuration OIDC exemple et de la documentation de raccordement.
- Interface de consultation/recherche/téléchargement documentaire, dépôt et validation selon rôle, gestion des collectivités, membres et invitations, et soumission de questions.
- Les autorisations restent contrôlées côté API ; la sélection d'organisation ne remplace pas l'isolement RLS.

## V3.7 — Intégration Keycloak
- Ajout de Keycloak 26.8.2 dans Docker Compose et d'une base PostgreSQL dédiée à l'identité.
- Ajout du realm `cfdt`, du client public `cfdt-juris-web` avec PKCE S256 et du mapper d'audience API `cfdt-juris-api`.
- Ajout d'un script de rendu des URI de redirection, origines web et configuration OIDC navigateur depuis les URL publiques.
- Ajout de la documentation de démarrage, reverse proxy, provisionnement et recette de sécurité.
- Les rôles métier et l'isolation multi-organisation restent sous le contrôle de l'API et de PostgreSQL.

## V3.8 — Invitations et administration des rôles
- Ajout d'un client serveur Keycloak Admin REST à authentification `client_credentials` pour rechercher/créer un compte sans exposer de secret au navigateur.
- Vérification d'adresse et définition de mot de passe via les actions Keycloak pour les comptes qui le nécessitent.
- Envoi SMTP applicatif du lien d'invitation CFDT JURIS à jeton unique ; acceptation automatique après retour de connexion OIDC lorsque le lien est ouvert dans le navigateur.
- Conservation du mode de remise manuelle si les paramètres d'automatisation ne sont pas renseignés.
- Ajout de la modification du rôle d'un membre, auditée et limitée à l'organisation active ; protection contre le retrait du dernier administrateur.
- Révocation d'une adhésion limitée à l'organisation courante, sans désactivation globale du compte Keycloak.


## V3.9 — Intégrité des invitations et provisionnement sécurisé
- Unicité d'une invitation en attente par adresse et organisation, y compris en cas de requêtes concurrentes.
- Acceptation d'invitation empêchant toute modification implicite du rôle d'un membre déjà actif.
- Validation plus stricte de l'URL Keycloak Admin en production (HTTPS, origine seule).
- Migration 006 révoquant les doublons pendants historiques sans supprimer les traces.
- Ajout de tests contractuels sur les nouveaux garde-fous.

## V3.10 — Intégration documentaire du CGFP
- Ajout d'une photographie PDF du Code général de la fonction publique (consolidation indiquée au 31/10/2026 ; générée le 13/11/2026).
- Ajout des métadonnées de provenance, de l'empreinte SHA-256 et des règles d'exploitation juridique.
- Ajout de `docs/20_CORPUS_NATIONAL_CGFP.md`.
- Cet ajout fournit la source au développeur ; il ne réalise pas encore l'ingestion en base, la recherche historique Légifrance ni le moteur de réponse juridique.

## V3.11 — Recherche exploitable dans le CGFP
- Génération d'un index national article/page depuis le snapshot PDF du CGFP (4 242 articles détectés, 1 024 pages).
- Recherche locale par mots-clés et référence exacte d'article.
- Nouvelle route authentifiée `GET /api/v1/legal/cgfp/search`.
- `POST /api/v1/chat/ask` interroge désormais le CGFP et renvoie les extraits sourcés avec statut `PARTIELLEMENT_VERIFIE`.
- Le Dockerfile embarque le corpus national.
- Aucune prétention de vérification Légifrance ou d'historique des versions : ces fonctions restent à développer.


## V3.12 — Recherche CGFP améliorée
- Remplacement du classement naïf par une pondération BM25 locale sur les 4 242 articles indexés.
- Ajout d'un extrait centré sur les termes de recherche.
- Ajout d'une fonction de consultation du texte intégral d'un article par référence L/R/D.
- Ajout des routes authentifiées `GET /api/v1/legal/cgfp/source` et `GET /api/v1/legal/cgfp/articles/{article_ref}`.
- Validation stricte de la limite de résultats et validation des références d'article.
- Tests ciblés CGFP : 8 réussis. La suite complète nécessite les dépendances d'infrastructure et une base de recette ; aucun test PostgreSQL réel n'est revendiqué.


## V3.13 — Contrôle d'intégrité des citations
- Ajout de `legal_validation.py` pour contrôler les références, les pages et les extraits par rapport au texte complet du snapshot CGFP.
- Intégration du contrôle dans l'orchestrateur : citations invalides écartées, statut `NON_VERIFIE` si aucune source ne passe.
- Validation stricte des dates de faits au format `AAAA-MM-JJ`.
- Ajout de tests positifs, négatifs et de date ambiguë.
- Limite maintenue : contrôle documentaire local uniquement, sans certification Légifrance ni historique des versions.

## V3.14 — Adaptateur IA facultatif
- Ajout d'un adaptateur asynchrone compatible OpenAI Chat Completions.
- Configuration par variables d'environnement, sans clé incluse au kit.
- Injection limitée aux extraits CGFP dont l'intégrité a été contrôlée côté backend.
- Prompt de cadrage : pas de sources inventées, séparation faits/hypothèses, réserves sur l'applicabilité temporelle et neutralisation des instructions contenues dans les documents.
- En l'absence de clé ou en cas d'indisponibilité fournisseur, repli sur la recherche documentaire existante.
- Le statut juridique reste `PARTIELLEMENT_VERIFIE` ; aucune certification juridique n'est simulée.

## V3.15 — Connecteur PISTE/Légifrance et installation locale
- Ajout d'un client OAuth2 Client Credentials PISTE avec cache mémoire du jeton, séparation stricte sandbox/production et secrets serveur uniquement.
- Ajout du ping officiel et des opérations documentées `/search` + `/consult/getArticle` pour le fonds `CODE_DATE` du CGFP.
- La recherche est datée ; un article n'est retenu qu'après correspondance de l'identifiant LEGIARTI et extraction d'un texte exploitable.
- Intégration de la recherche PISTE dans l'orchestrateur ; maintien du statut prudent `PARTIELLEMENT_VERIFIE`.
- Rejet d'une réponse IA contenant une référence d'article absente des sources récupérées.
- Ajout de routes de diagnostic et de recherche Légifrance.
- Docker Compose initialise désormais automatiquement le schéma consolidé et les droits minimaux sur un volume PostgreSQL neuf.
- Ajout d'un générateur local `.env` avec secrets aléatoires et d'une procédure de démarrage local.


## V3.16 — Recherche de jurisprudence administrative (2026-11-16)
- Ajout du connecteur de recherche au fonds CETAT via le client OAuth2 PISTE V3.15.
- Filtre de date de décision borné à la date des faits ou de repérage.
- Validation stricte des identifiants CETATEXT, dédoublonnage et extraction prudente des métadonnées.
- Affichage des résultats CETAT dans le poste de travail, avec date, numéro d’affaire, identifiant et lien.
- Les résultats CETAT ne sont pas transmis à l’IA et ne sont pas assimilés au texte intégral d’un arrêt.
- Tests ciblés du connecteur : 6 réussis. La suite complète reste bloquée par l’absence de `asyncpg` dans l’environnement.
- Connexion PISTE réelle, structure effective des résultats en production et récupération du texte intégral des décisions restent à valider/développer.

## V3.17 — Abonnements SaaS et plafonds d'utilisateurs (2026-11-16)
- Ajout des offres serveur Essentiel (15 €/mois, 3 utilisateurs), Syndicat (50 €/mois, 10 utilisateurs) et accès offert attribuable par administrateur plateforme.
- Ajout de Stripe Checkout et du portail de facturation, avec prix exclusivement définis côté serveur.
- Ajout du webhook Stripe avec contrôle de signature HMAC et idempotence des événements.
- Ajout de la consultation d'abonnement, du suivi du nombre de membres et du blocage des invitations au-delà du plafond.
- Ajout d'une route d'attribution d'accès offert avec motif obligatoire.
- Ajout d'un écran Abonnement dans le frontend.
- Tests unitaires du catalogue, de la signature et de la normalisation d'événements Stripe.
- À réaliser avant commercialisation : tests Stripe en mode test, tests PostgreSQL/RLS, interface d'administration plateforme, documents contractuels et validation comptable/fiscale.


## V3.18 — Console d'administration plateforme
- Ajout d'un annuaire transversal des organisations via fonctions SQL `SECURITY DEFINER` avec contrôle interne du registre administrateur.
- Ajout de la suspension et réactivation d'un espace, avec événement d'audit.
- Ajout d'une interface d'administration pour créer les espaces, attribuer un accès offert et gérer leur état.
- Ajout de la migration `008_platform_admin_console.sql` et intégration au schéma des nouvelles installations.
- Le script vérifie que le rôle de migration possède `BYPASSRLS`. La recette PostgreSQL réelle reste obligatoire avant production.

## V3.19 — Consultation du texte intégral de jurisprudence administrative
- Ajout de la consultation officielle `POST /consult/juri` par identifiant de décision.
- Validation stricte de l'identifiant retourné et du contenu textuel avant de déclarer le texte intégral récupéré.
- Ajout de `GET /api/v1/legal/jurisprudence/administrative/{decision_id}` avec statut de vérification technique explicite et limites juridiques documentées.
- Distinction renforcée entre résultats de recherche, extraits et texte intégral.
- Tests unitaires de récupération, de correspondance d'identifiant et de rejet des identifiants invalides.
- Limites : aucun contrôle automatisé de revirement/portée juridique, aucune persistance de décisions, aucun test réel PISTE en production.


## V3.20 — CI/CD, guides et exploitation
- Ajout du workflow CI GitHub Actions : compilation, lint, analyse statique de sécurité, audit des dépendances, tests et validations de configuration.
- Ajout d'un workflow de déploiement production manuel via SSH et environnement protégé.
- Ajout du healthcheck de l'API Docker sur `/ready`.
- Ajout de scripts de sauvegarde et restauration PostgreSQL et d'un contrôle de santé HTTP.
- Ajout d'un guide utilisateur, d'un manuel administrateur et d'un runbook d'exploitation.
- Documentation des limites : sauvegardes séparées des fichiers et Keycloak, chiffrement distant à configurer, restauration à tester, déploiement non activé par défaut.

## V3.21 — Référentiel juridique national permanent
- Ajout des tables `legal_documents`, `legal_document_versions`, `legal_chunks`, `legal_document_relations` et `legal_ingestion_runs`.
- Historisation des versions, dates d'effet explicites, empreintes SHA-256 et fragments de recherche plein texte français.
- Ajout du connecteur LODA/LEGI via le flux officiel `/search` puis `/consult/legiPart` avec correspondance d'identifiant.
- Ajout de l'ingestion CETAT : une décision n'est stockée comme texte intégral que si l'identifiant consulté correspond et qu'un texte substantiel est retourné.
- Ajout de l'import XML CIRCULAIRES DILA avec statut `IMPORTED_UNVERIFIED` par défaut ; aucune métadonnée non vérifiée n'est utilisée comme source IA.
- Ajout d'une recherche croisée dans le corpus national, intégrée au moteur de réponse et exposant les liens officiels cliquables.
- Contrôle des empreintes de texte, références d'autorités et statut temporel avant transmission au modèle.
- Séparation des droits PostgreSQL : rôle API en lecture seule, rôle d'ingestion dédié et routes d'import réservées à l'administrateur plateforme.
- Ajout de l'interface d'administration des imports, des historiques et des routes API associées.
- Ajout de la migration `009_permanent_legal_knowledge.sql`, du guide `docs/31_V3_21_PERMANENT_LEGAL_KNOWLEDGE.md` et des tests unitaires.
- Limites : synchronisation exhaustive des fonds, extraction automatique complète des liens d'abrogation/modification, vecteurs sémantiques et recette PISTE/DB PostgreSQL de production restent à réaliser.


## V3.22 — Industrialisation et préproduction (2026-11-16)
- Audit automatisé des 39 variables de configuration Pydantic par rapport au modèle `.env.example`, y compris variables optionnelles documentées.
- Confirmation que `asyncpg` est déjà une dépendance runtime ; séparation des dépendances de test dans `backend/requirements-dev.txt` ; CI renforcée avec PostgreSQL 16 et deux tests d'isolation RLS sous le rôle `cfdt_juris_app` non propriétaire, dont 12 organisations concurrentes.
- Ajout du registre `schema_migrations`, baseline automatique V8/V9, checksums, verrou advisory, séquence stricte et transactions atomiques.
- Ajout d'un rollback explicite avec double confirmation et fichiers `down.sql` ; migrations 001-008 protégées par restauration de sauvegarde, rollback 009 destructif disponible uniquement lorsqu'elle a été appliquée après baseline V8.
- Séparation de l'environnement API (`.env.runtime`) des secrets d'infrastructure ; le rôle DBA n'est injecté que dans le service ponctuel `migrator`.
- Ajout de la mise à niveau non destructive des fichiers `.env`, de l'installation guidée et de la gestion idempotente des rôles ingestion/monitoring.
- Ajout d'un staging isolé (`cfdt-juris-staging`, ports 18000/18081), d'un workflow de déploiement staging et d'une procédure de déploiement avec sauvegarde préalable.
- Ajout de la supervision optionnelle Prometheus, Blackbox Exporter, PostgreSQL Exporter, Alertmanager et Grafana avec alertes de disponibilité API/Keycloak/PostgreSQL.
- Limites : le conteneur de travail ne dispose pas de Docker ni de PostgreSQL ; les 105 tests Python réussissent et deux tests RLS sont ignorés localement faute de serveur/URL PostgreSQL. La CI est configurée pour l'exécuter réellement ; aucun déploiement ou test PISTE/Stripe réel n'est revendiqué.

## V3.23 — Tarification TTC et gratuités individuelles
- Nouvelles offres : 15 € TTC / 1 compte, 80 € TTC / 10 comptes, 300 € TTC / 50 comptes.
- Codes legacy préservés pour ne pas changer les droits des abonnements existants.
- Liste blanche d'adresses gratuites administrée par la plateforme, hors quotas payants.
- Checkout Stripe avec prix TTC inclusifs, Stripe Tax, adresse de facturation et collecte facultative de numéro de TVA.
- Administration générale : ajout, consultation et révocation des adresses gratuites.


## V3.24 — Espace commercial et client
- Ajout d'une console commerciale plateforme avec indicateurs de revenus encaissés, abonnements actifs et en impayé, organisations, licences et gratuités.
- Ajout du suivi commercial des syndicats, des quotas utilisés et des accès gratuits.
- Enregistrement idempotent des factures Stripe et de leur cycle de paiement via webhook.
- Ajout de l'historique de facturation cloisonné dans l'espace client de chaque syndicat.
- Ajout de la migration 011 et de son rollback.
- Les données historiques antérieures au déploiement ne sont pas automatiquement récupérées.


## V3.25 — Sécurité et validation de production
- Ajout d'un audit pré-déploiement bloquant pour secrets, HTTPS, OIDC, CORS, DEBUG et chiffrement des sauvegardes.
- Durée de vie des jetons d'accès Keycloak définie à 15 minutes dans les deux fichiers de realm.
- Sauvegardes de production/recette chiffrées avec age ; clé privée à conserver hors serveur.
- Contrat de test couvrant le rôle runtime sans BYPASSRLS et les scénarios d'isolation multi-tenant en CI PostgreSQL.
- Documentation des contrôles qui restent à effectuer sur l'instance réelle.


## V3.26 — Interface conversationnelle juridique
- Refonte de l’écran Question juridique en interface de chat responsive, raccordée au contrat API/OIDC existant.
- Suppression de la simulation juridique, du stockage local des jetons et de la persistance locale des conversations.
- Affichage des statuts, réserves et sources Légifrance autorisées.


## V3.26 — Interface conversationnelle juridique
- Refonte de l'écran Question juridique en interface de chat responsive.
- Raccordement strict au contrat API `/api/v1/chat/ask`, au schéma `AskRequest` et au flux OIDC/tenant existants.
- Suppression de la simulation juridique et du stockage local de jetons/conversations.
- Affichage des statuts de vérification, réserves, avertissement et sources officielles autorisées.
- Documentation : `docs/34_V3_26_INTERFACE_ASSISTANT_JURIDIQUE.md`.


## V3.27 — Conversations juridiques multi-tours persistantes
- Persistance des conversations et messages côté PostgreSQL, jamais dans le stockage local du navigateur.
- Isolation RLS stricte par organisation et utilisateur ; lecture, reprise et suppression de ses seules conversations.
- Transmission des 12 derniers messages pertinents au moteur IA comme contexte conversationnel, sans conférer de valeur juridique aux réponses antérieures.
- Recherche documentaire contextualisée à partir des questions antérieures de l'utilisateur et de la question courante.
- Interface d'historique, reprise et suppression des conversations.
- Migration 012 et rollback.


## V3.28 — Constitution de dossiers juridiques

- Compilation structurée des échanges d'une conversation en dossier de travail.
- Intégration des réponses, statuts de vérification, sources et points à vérifier déjà enregistrés.
- Champs éditables : intitulé, employeur, objet, éléments rapportés, chronologie, pièces, conclusion et plan d'action.
- Enregistrement PostgreSQL privé et RLS FORCE par organisation et utilisateur.
- Impression et export PDF depuis le navigateur.
- Migration 013 avec rollback associé ; intégration à la CI PostgreSQL.
- Le statut initial reste `BROUILLON_A_VALIDER` ; aucune validation juridique automatique et aucune incorporation automatique de fichiers/pièces jointes.


## V3.29 — Sécurisation juridique avancée

- Ajout d'une qualification indicative des familles de sources et du statut temporel/validation ; les sources affichent un indicateur `legal_assurance`.
- Ajout d'une revue de cohérence des documents locaux avec le corpus national, strictement limitée aux documents de l'organisation active, antivirus propres et textes extraits.
- Revue préliminaire IA facultative, limitée aux textes nationaux intégraux, intègres et temporellement exploitables ; les références non ancrées sont écartées.
- Aucun verdict automatique de légalité/illégalité ; absence de résultat ne vaut pas conformité.
- Ajout d'un endpoint d'inventaire de fraîcheur pour les administrateurs plateforme et d'un script de veille réglementaire ciblée à planifier par l'exploitant.
- Pas de migration de base dans cette version.
- Limites : le classement indicatif ne résout pas à lui seul les conflits de normes ; la veille n'est ni exhaustive ni active sans planification, jeton et supervision ; les tests réels d'isolation et d'intégration doivent être réalisés en staging.


## V3.30 — Renforcement du moteur juridique

- Import CGFP optimisé : validation de l'empreinte PDF, du nombre d'articles, des références, de l'absence de doublons, de la pagination et de la sécurité du nom de fichier source.
- Import réservé au rôle PostgreSQL `cfdt_juris_ingest` via `LEGAL_CORPUS_INGEST_DATABASE_URL`, transaction unique et insertion groupée des chunks ; les entrées restent `IMPORTED_UNVERIFIED` et de temporalité `UNKNOWN`.
- Recherche Légifrance à la date des faits : `CODE_DATE` pour les articles du CGFP et `LODA_DATE` pour les lois, décrets et arrêtés complémentaires ; vérification de l'identifiant retourné et récupération du texte avec `/consult/legiPart`.
- Extraits pertinents extraits des textes longs ; textes intégraux conservés côté serveur et non renvoyés au navigateur.
- Recherche CETAT explicitement présentée comme recherche documentaire tant que le texte intégral n'est pas validé dans PISTE réel.
- Recherche des documents locaux tenant-scoped, filtrés par collectivité, antivirus, empreinte, extraction, validation humaine et dates d'effet ; les documents non validés sont exclus du contexte IA.
- Protection contre les recherches longues qui écartent la question actuelle, et contre les références IA provenant de sources exclues du contexte.
- Résultat historique du checkpoint moteur juridique : 164 réussis, 2 ignorés (intégration PostgreSQL réelle non configurée). Le run du kit révisé est consigné ci-dessous.
- Aucune migration ou import de production n'est revendiqué dans cette livraison.

## V3.30 — profil d'instance privée
- Ajout du mode `PRIVATE_INSTANCE_MODE` limité à dix comptes actifs.
- Désactivation des routes de facturation Stripe en mode privé.
- Acceptation des invitations en statut `INVITED` jusqu'à approbation de l'administrateur plateforme.
- Ajout des statuts `SUSPENDED` et `REVOKED` et d'un contrôle SQL transactionnel du quota.
- Documentation de déploiement dans `docs/40_INSTANCE_PRIVEE_10_COMPTES.md`.

## V3.30 — préparation du transfert développeur (2026-11-17)
- La CI applique désormais les migrations 014 et 015 sur PostgreSQL avant les tests.
- Ajout d'un test d'intégration du plafond privé, des approbations concurrentes, de la suspension et de l'audit.
- La migration 015 refuse une base contenant plusieurs organisations ou plus de dix adhésions actives.
- Correction des 42 diagnostics Ruff hérités de l'archive; la commande de lint CI passe maintenant localement.
- Résultat local initial du kit : 169 réussis et 3 ignorés faute de PostgreSQL disponible; ce résultat précède la recette CI.
- Le workflow GitHub crée son propre PostgreSQL éphémère et fournit les URL locales nécessaires; aucun secret GitHub ni URL Neon n'est requis.
- Après le premier run CI, les deux appels à `ElementTree.fromstring` sur du XML non fiable ont été remplacés par `defusedxml`; un test DOCX vérifie le rejet d'entités internes.
- Le contrôle `pip-audit` a ensuite détecté deux avis sur Pytest 8.4.2; la dépendance de développement est relevée à la version corrigée 9.0.3.
- Voir `docs/41_PLAN_DEVELOPPEUR_V3_30.md` pour les étapes de recette qui restent à réaliser.


## V3.30 — séparation des privilèges administrateur PostgreSQL

- Ajout de la migration 016 et du rôle de connexion dédié `cfdt_juris_platform_admin`, distinct des rôles runtime et ingestion.
- Les fonctions SQL d'administration (annuaire, statut des organisations, création d'organisation, accès gratuits et gestion des membres privés) ne sont plus exécutables par le rôle runtime.
- Les écritures de la liste d'accès gratuits et de son journal sont réservées au pool administrateur, avec des privilèges limités aux colonnes nécessaires.
- Ajout de tests PostgreSQL réels qui vérifient le refus des opérations privilégiées depuis le rôle runtime et leur autorisation via le rôle dédié.
- CI finale sur PostgreSQL 16 : **178 tests réussis, aucun échec** ; voir `docs/42_V3_30_PREUVE_VALIDATION_CI.md`.
- Procédure d'installation/migration Docker et PostgreSQL managé : `docs/43_V3_30_ADMIN_DB_ROLE_MIGRATION.md`.


## V3.33 — Limitation partagée des parcours IA
- Extension du compteur PostgreSQL atomique V3.31 aux revues de cohérence des règles locales.
- Chat juridique et revue locale consomment le même quota par utilisateur et organisation : l'alternance des endpoints ne permet plus de contourner la limite.
- Le refus HTTP 429 intervient avant les recherches documentaires coûteuses et fournit `Retry-After`.
- Aucun texte de question, document ou résultat n'est ajouté au compteur.


## V3.34 — Limitation des appels directs aux connecteurs PISTE
- Les contrôles de connexion, recherches Légifrance et recherches/consultations CETAT consomment désormais le même compteur PostgreSQL par organisation et utilisateur que le chat juridique.
- Une réponse HTTP 429 avec `Retry-After` est renvoyée avant tout appel externe lorsque le quota est atteint.
- Les paramètres de recherche et identifiants sont validés avant consommation du quota afin que les entrées invalides ne pénalisent pas l'utilisateur.
- Aucun contenu de recherche n'est ajouté au compteur ; aucune migration supplémentaire n'est nécessaire.


## V3.35 — Bornage des imports PISTE administrateur
- Les deux routes d'ingestion réglementaire et CETAT valident désormais la longueur de recherche avant toute création de run ou appel externe.
- La limite demandée est bornée à 20 résultats maximum, ce qui borne également le nombre de consultations de textes intégraux CETAT.
- Les paramètres invalides renvoient HTTP 422 sans ouvrir de connexion d'ingestion ni appeler PISTE.
- Aucun changement de schéma PostgreSQL et aucune migration Neon ne sont nécessaires.


## V3.37 — Préparation de la purge des conversations privées
- Ajout d'un utilitaire opérateur de purge des conversations privées, avec prévisualisation par défaut et seuil absolu fourni explicitement.
- Suppression réelle protégée par double confirmation ; connexion dédiée refusée si le rôle PostgreSQL ne possède pas SUPERUSER ou BYPASSRLS.
- Les messages et dossiers liés sont supprimés via les cascades SQL existantes.
- Tests unitaires des garde-fous et test d'intégration PostgreSQL de la prévisualisation, de la suppression et des cascades.
- Aucun délai de conservation par défaut, aucune planification et aucune exécution sur une base réelle. La politique (durées, point de départ, exceptions et sauvegardes) reste à valider par le responsable de traitement/DPO.

## V3.38 — Préparation de la recette développeur

- Ajout de `scripts/run_developer_validation.sh` pour rejouer localement les contrôles de compilation, configuration, Ruff, Bandit, pip-audit, pytest et scripts shell.
- Contrôle Docker Compose conditionnel si un fichier `.env` local existe ; construction des images sur demande explicite via `BUILD_IMAGES=1`.
- Tests HTTP `/health` et `/ready` optionnels via `SMOKE_BASE_URL`.
- Mode strict optionnel pour exiger les URL PostgreSQL de test via `REQUIRE_POSTGRES_INTEGRATION=1`.
- Ajout de `docs/44_PREPARATION_RECETTE_DEVELOPPEUR.md` avec commandes reproductibles, matrice de recette externe et preuves attendues.
- Le script ne démarre aucun service, n'applique aucune migration et ne touche à aucune base.
