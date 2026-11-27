# 02 — Architecture technique cible

## 1. Choix d'architecture
Architecture modulaire, API-first, multi-tenant, avec séparation des couches :
- Frontend : React/Next.js ou équivalent, PWA après MVP.
- Backend : Python 3.12 + FastAPI.
- Base relationnelle : PostgreSQL.
- Recherche documentaire : PostgreSQL Full Text au démarrage ; moteur dédié uniquement si les volumes le justifient.
- Fichiers d'actes : stockage objet privé compatible S3, avec chiffrement et accès temporaire ; aucun document accessible publiquement.
- Authentification : fournisseur OIDC éprouvé (ex. Keycloak ou fournisseur managé) ; éviter de développer soi-même la gestion des mots de passe.
- IA : adaptateur fournisseur interchangeable ; API externe ou modèle auto-hébergé après arbitrage confidentialité/coût.
- Tâches longues : file de tâches seulement si l'indexation ou l'ingestion le nécessite.
- Observabilité : métriques et traces techniques sans texte des questions ni réponses.

## 2. Schéma de flux
Navigateur
→ HTTPS / reverse proxy
→ authentification OIDC
→ API FastAPI
→ contrôle organisation/permissions
→ orchestrateur juridique
→ connecteur Légifrance + recherche corpus local
→ normalisation / dédoublonnage / versions
→ sélection de passages
→ modèle IA (sources limitées au paquet récupéré)
→ validateur de citations
→ réponse au navigateur
→ purge mémoire temporaire.

## 3. Multi-tenant
Le tenant est l'organisation syndicale. Toute ressource privée porte `organization_id`. L'identifiant d'organisation est dérivé du jeton d'identité et de l'adhésion en base, jamais accepté aveuglément depuis le navigateur.

Contrôles obligatoires :
- Vérification d'appartenance à l'organisation à chaque requête.
- Filtrage SQL par `organization_id`.
- Row Level Security PostgreSQL comme seconde barrière.
- Tests d'accès croisé automatisés.
- Documents et objets de stockage préfixés par tenant.
- Clés de cache comprenant tenant + requête + version corpus.
- Aucun log de contenu de conversation.
- Les données nationales publiques communes peuvent être dans un référentiel global, séparé des corpus locaux/privés.

## 4. Services
- `IdentityService` : validation OIDC, rôles et adhésions.
- `OrganizationService` : espaces, paramètres, état du compte.
- `LegalOrchestrator` : séquence de recherche et génération.
- `LegifranceClient` : OAuth2, recherche, récupération texte et versions.
- `LocalCorpusService` : ingestion, métadonnées, recherche et validation.
- `CitationValidator` : correspondance stricte des références avec les sources reçues.
- `AIProvider` : interface abstraite, aucun couplage au fournisseur.
- `BillingProvider` : interface future, désactivée au MVP.
- `AuditService` : événements administratifs minimisés, jamais le contenu juridique saisi.

## 5. Modes de défaillance
- API source indisponible : pas de réponse juridique affirmative ; statut NON/PARTIELLEMENT VÉRIFIÉ.
- Date des faits absente et déterminante : demander la date.
- Corpus local sans annexes : document marqué incomplet, non utilisé comme base suffisante.
- Citation non reconnue : retirer la citation et dégrader le statut, ou bloquer la réponse.
- IA indisponible : afficher sources récupérées et indisponibilité, sans inventer l'analyse.
- Organisation suspendue : accès refusé, sans exposer la raison interne.
