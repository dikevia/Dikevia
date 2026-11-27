> **DOCUMENT HISTORIQUE — PAIEMENTS DÉSACTIVÉS.** Les anciens tarifs Stripe et plafonds décrits ici ne correspondent plus au modèle Agent/Syndicat actuel. Aucun checkout ni paiement n'est actif. Voir `docs/08` et `docs/57`.

# V3.17 — Abonnements SaaS et plafonds d'utilisateurs

## Offres implémentées

| Code | Tarif mensuel configuré | Plafond | Attribution |
|---|---:|---:|---|
| `ESSENTIAL_3` | 15 € | 3 utilisateurs | Checkout Stripe |
| `SYNDICAT_10` | 50 € | 10 utilisateurs | Checkout Stripe |
| `FOUNDING_FREE` | 0 € | 10 utilisateurs | Administrateur plateforme uniquement |

Les montants sont définis côté serveur dans `backend/app/billing.py`. Le navigateur ne transmet jamais de montant ou de devise.

## Routes

- `GET /api/v1/billing/plans` : catalogue public.
- `GET /api/v1/billing/subscription` : formule et consommation de l'espace actif.
- `POST /api/v1/billing/checkout` : création d'une session Stripe, réservée à `ORG_ADMIN`.
- `POST /api/v1/billing/portal` : portail Stripe, réservé à `ORG_ADMIN`.
- `POST /api/v1/billing/stripe/webhook` : réception des événements Stripe avec vérification HMAC `Stripe-Signature` et idempotence par identifiant d'événement.
- `POST /api/v1/platform/organizations/{organization_id}/grant-free` : attribution d'un accès offert par un administrateur plateforme ; un motif est obligatoire.

Le plafond compte les membres actifs et les invitations non expirées. L'API refuse les nouvelles invitations lorsque le plafond est atteint. Les utilisateurs déjà présents ne sont pas supprimés lors d'une rétrogradation.

## Base de données

Pour une nouvelle installation, `database/schema.sql` inclut les colonnes d'abonnement et la table `billing_webhook_events`.

Pour une base existante V3.16, appliquer `database/migrations/007_saas_billing.sql` avec le rôle DBA, puis exécuter `database/grant_runtime_permissions.sql` en DBA.

## Configuration Stripe

Définir dans `.env` :

```dotenv
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
BILLING_SUCCESS_URL=https://votre-domaine/abonnement/confirmation
BILLING_CANCEL_URL=https://votre-domaine/abonnement
```

Créer dans Stripe un webhook pointant vers `https://votre-domaine/api/v1/billing/stripe/webhook` et sélectionner au minimum :

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`
- `invoice.paid`

Utiliser des clés `sk_test` avant la recette. Passer en production seulement après vérification de tous les événements, de la signature, des renouvellements, des impayés, des annulations et des rétrogradations. Le traitement de la TVA, les mentions légales, les factures et les obligations fiscales doivent être déterminés avec le comptable avant commercialisation. Les prix sont affichés en euros par mois ; le traitement fiscal n’est pas encore implémenté.

## Limites connues

- Les abonnements sont gérés via Stripe Checkout/Portal ; la facturation électronique réglementaire, les avoirs et la comptabilité ne sont pas implémentés dans JURIS.
- Les accès offerts sont attribués à une organisation entière, pas à des utilisateurs isolés d'une même organisation.
- L'endpoint d'attribution gratuite ne dispose pas encore d'une interface graphique d'administration plateforme.
- La recette doit être réalisée avec un compte Stripe test et PostgreSQL réel. Aucun paiement réel ni webhook de production n'a été exécuté pendant la génération du kit.
