# V3.23 — Tarification TTC et accès gratuits individuels

## Catalogue public

| Code | Offre | Prix TTC mensuel | Places payantes |
|---|---|---:|---:|
| `INDIVIDUAL_1` | Individuel | 15 € | 1 |
| `SYNDICAT_10` | Syndicat 10 | 80 € | 10 |
| `SYNDICAT_50` | Syndicat 50 | 300 € | 50 |

Les anciens abonnements `ESSENTIAL_3` et `SYNDICAT_10` sont renommés en codes `LEGACY_*` lors de la migration 010 afin de préserver les quotas et métadonnées Stripe existants. Ils ne sont pas proposés aux nouveaux clients.

## Accès gratuits individuels

L'administrateur plateforme gère une liste d'adresses e-mail normalisées via `/api/v1/platform/free-email-access`. Les adresses actives (non révoquées et non expirées) ne consomment pas de place payante dans le calcul des invitations et des membres actifs. Une invitation à un espace syndical reste nécessaire : la gratuité est un droit d'accès individuel, pas un accès transversal aux données d'une organisation. Les données restent isolées par organisation.

## Stripe et TTC

Le Checkout crée les prix côté serveur en centimes d'euro et fixe `tax_behavior=inclusive`, active Stripe Tax, demande l'adresse de facturation et autorise la collecte du numéro de TVA. Avant le passage en production, le compte Stripe doit avoir une adresse professionnelle et les immatriculations fiscales configurées. Les paramètres de taxe, les factures et les règles applicables doivent être validés par le responsable comptable/fiscal. Les montants affichés sont les montants TTC de référence ; Stripe peut calculer le détail fiscal selon la localisation et le statut du client.

## Migration

Appliquer `010_subscription_catalog_and_free_email_access.sql` après la migration 009, puis exécuter `database/grant_runtime_permissions.sql` avec le rôle DBA. Le rollback correspondant est fourni, mais une sauvegarde PostgreSQL préalable reste obligatoire.
