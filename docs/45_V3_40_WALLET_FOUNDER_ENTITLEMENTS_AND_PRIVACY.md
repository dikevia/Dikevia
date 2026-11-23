# Dikévia — portefeuille de crédits, accès fondateur et confidentialité

## État
Évolutions préparées et testées sur PostgreSQL éphémère. Elles ne sont pas encore appliquées à Neon et aucun accès fondateur réel n'est attribué.

## Portefeuille de crédits
Migrations :
- `025_credit_wallet_foundation.sql`
- rollback : `rollback/025_credit_wallet_foundation.down.sql`

Principes :
- solde par organisation ;
- journal append-only des mouvements ;
- idempotence des opérations ;
- le rôle runtime `cfdt_juris_app` peut uniquement débiter des crédits pour un usage, avec refus des montants positifs ;
- les allocations positives sont réservées à la fonction privilégiée et au rôle `cfdt_juris_platform_admin` ;
- un débit ne peut jamais faire passer le solde sous zéro ;
- aucun crédit mensuel automatique, débit utilisateur ou paiement Stripe n'est activé par cette migration.

## Accès fondateur permanent
Migrations :
- `026_platform_founder_entitlements.sql`
- rollback : `rollback/026_platform_founder_entitlements.down.sql`

Principes :
- rattachement à l'identifiant interne d'un compte actif et à son identité OIDC vérifiée (`issuer` + `subject`) ;
- aucune attribution par adresse e-mail ;
- attribution et révocation exclusivement par les fonctions de l'administration plateforme ;
- chaque opération est journalisée dans `platform_audit_events` ;
- l'utilisateur ne peut lire que son propre état d'accès ;
- l'API d'administration exige un identifiant interne existant et un motif explicite ;
- aucune attribution réelle n'est effectuée automatiquement.

L'écran d'administration plateforme est distinct de l'interface conversationnelle. L'espace utilisateur expose uniquement son identifiant interne, sans exposer le sujet OIDC brut.

## Confidentialité des documents locaux
Deux autorisations indépendantes sont nécessaires avant qu'un document local puisse être transmis à un fournisseur IA :
1. activation explicite côté serveur (`AI_LOCAL_DOCUMENTS_IN_CHAT_ENABLED` ou `AI_LOCAL_DOCUMENT_REVIEW_ENABLED`) ;
2. consentement explicite de l'utilisateur pour la demande courante.

Sans ces deux conditions :
- les documents locaux restent disponibles pour la recherche et l'affichage côté serveur ;
- ils sont exclus des payloads d'analyse IA et de tri sémantique ;
- les anciennes réponses contenant des sources locales ne sont pas réinjectées dans l'historique IA des demandes suivantes.

Les consentements sont réinitialisés dans l'interface après chaque demande. Les deux variables serveur sont désactivées par défaut.

## Coûts et intégrations externes
- `STARTUP_EXTERNAL_DIAGNOSTICS_ENABLED=false` par défaut : pas de sondes PISTE/IA automatiques au démarrage.
- `STRIPE_BILLING_ENABLED=false` par défaut ; le checkout reste bloqué tant que le compteur et le contrôle des crédits ne sont pas opérationnels.
- les routes externes utilisent un contexte RLS sans transaction PostgreSQL longue pendant les appels réseau.

## Validation attendue avant activation
- appliquer les migrations 025 et 026 sur un environnement de staging après sauvegarde et revue ;
- vérifier les rôles runtime et platform-admin réels ;
- tester attribution, lecture personnelle, révocation, idempotence et refus des soldes négatifs ;
- vérifier le consentement utilisateur et la configuration serveur sans données réelles ;
- ne jamais activer Stripe ou le transfert de documents locaux sans validation séparée.
