> **DOCUMENT HISTORIQUE — CONSOLE COMMERCIALE ET STRIPE NON ACTIVÉS.** Les métriques de revenus, factures et flux Stripe décrits ici ne sont pas un périmètre commercial actif. Le modèle actuel ne comporte pas d'offre collectivité et aucun paiement n'est activé. Voir `docs/08` et `docs/57`.

# V3.24 — Espace commercial et client

## Fonctionnalités
La console d'administration plateforme expose les indicateurs commerciaux globaux : chiffre d'affaires encaissé du mois sélectionné, abonnements actifs, abonnements en impayé, organisations actives, licences payantes utilisées et capacité souscrite, membres bénéficiant d'un accès gratuit et factures émises. Elle présente aussi le détail des syndicats, des licences et des factures récentes.

Chaque espace syndical dispose de son propre historique de factures. La route utilise le contexte d'organisation déjà validé par l'API et une fonction SQL `SECURITY DEFINER` qui refuse tout identifiant d'organisation différent du contexte courant.

## Source des données
Les événements Stripe `invoice.created`, `invoice.finalized`, `invoice.updated`, `invoice.paid`, `invoice.payment_succeeded`, `invoice.payment_failed`, `invoice.voided` et `invoice.marked_uncollectible` alimentent `stripe_invoice_records`. Les montants sont stockés en centimes, sans conversion flottante. L'identifiant Stripe rend les mises à jour idempotentes. L'organisation est déterminée par la métadonnée `organization_id` de la facture ou par le rattachement de l'abonnement Stripe déjà enregistré.

La signature du webhook est vérifiée avant l'ouverture de la transaction. Une variable de transaction `app.stripe_webhook_verified` est alors définie et les politiques RLS autorisent les insertions/mises à jour de factures uniquement dans ce contexte. Les lectures tenant restent limitées à `app.current_org_id`.

## Migration
Appliquer `database/migrations/011_commercial_customer_console.sql` après les migrations 010. Le runner de migrations applique le fichier avec son verrou et son contrôle d'intégrité. Le rollback est fourni dans `database/migrations/rollback/011_commercial_customer_console.down.sql` ; il supprime les données de facturation collectées par cette version.

## Limites et recette obligatoire
- Les factures antérieures à l'activation de V3.24 ne sont pas automatiquement importées. Une synchronisation historique Stripe reste à développer si elle est souhaitée.
- Les indicateurs reflètent uniquement les événements Stripe reçus et traités. Un webhook manquant ou mal configuré crée un décalage.
- Le chiffre d'affaires mensuel est calculé à partir des montants `amount_paid` et de `paid_at` transmis par Stripe. Il ne constitue pas un journal comptable certifié et ne traite pas les remboursements/avoirs comme une comptabilité complète.
- Tester en préproduction les événements de paiement réussi, paiement échoué, facture mise à jour, doublon webhook, et accès d'un syndicat aux factures d'un autre.
- Tester également l'ouverture des liens de factures hébergées et PDF dans le portail client Stripe.
