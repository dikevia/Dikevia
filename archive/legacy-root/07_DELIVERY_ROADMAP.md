# 07 — Plan de réalisation et transfert

## Lot 0 — cadrage technique
- Dépôt privé, branches, CI, secrets, environnements.
- Choix hébergement, IdP, stockage, base.
- Accès PISTE et lecture du Swagger.
**Jalon :** architecture et preuve de faisabilité API.

## Lot 1 — fondations multi-tenant
- Organisations, memberships, rôles.
- OIDC, MFA, révocation.
- PostgreSQL RLS et tests d'isolation.
- Interface chat vide.
**Jalon :** tenant A et B isolés par tests.

## Lot 2 — sources nationales
- Client OAuth2 PISTE.
- Recherche et récupération des textes.
- Pagination, quotas, retries, timeouts, version temporelle.
**Jalon :** texte réel avec version et URL officielle.

## Lot 3 — corpus local
- Ingestion PDF/HTML contrôlée.
- Métadonnées et empreinte SHA-256.
- Gestion des annexes et liens entre actes.
- Validation humaine et recherche par collectivité/date/tenant.
**Jalon :** actes Ville et Métropole séparés.

## Lot 4 — orchestration IA
- Qualification et clarification.
- Paquet de sources contrôlé.
- Adaptateur IA interchangeable.
- JSON structuré et validateur citations.
- Statut calculé côté serveur.
**Jalon :** réponses de recette avec zéro citation inventée.

## Lot 5 — sécurité et recette
- Revue sécurité, tests d'intrusion ciblés.
- Cartographie RGPD, DPO, AIPD si nécessaire.
- Tests de charge et de panne.
- Documentation et formation.
**Jalon :** accord écrit avant ouverture.

## Lot 6 — commercialisation
- Paramétrage offres, abonnements, facturation.
- Conditions générales, contrats, support, SLA.
- Processus onboarding multi-OS.
- Mesure coûts par tenant sans contenu conversationnel.
**Jalon :** pilote client externe séparé.

## Estimation indicative
Une estimation fiable exige un développeur qui connaît son environnement. Le cadrage initial envisageait plusieurs semaines de travail, mais l'authentification, la sécurité multi-tenant, les API, les corpus locaux et la validation juridique peuvent prolonger le délai. Ne pas promettre une date ferme avant la preuve PISTE et le choix des services externes.
