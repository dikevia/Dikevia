# Nouvelle stratégie tarifaire Dikévia — proposition V1

## Catalogue cible

| Offre | Mensuel TTC | Annuel TTC | Accès | Crédits mensuels annoncés |
|---|---:|---:|---:|---:|
| Essentiel | 14,90 € | 149 € | 1 | 125 |
| Pro | 29 € | 290 € | 1 | 248 |
| Équipe & Instances | 119 € | 1 190 € | 5 | 1 000 |
| Collectivité & Syndicats | 299 € | 2 990 € | 15 | 2 450 |

Packs envisagés : 200 crédits à 29 € TTC ; 600 crédits à 79 € TTC.

## Décision produit

Cette grille remplace la grille publique historique comme catalogue cible. Les codes historiques restent présents et non publics pour préserver les abonnements existants. Les nouveaux codes sont définis côté serveur et le Checkout mensuel accepte ces quatre codes.

**Limites explicites de cette première intégration :**
- Le Checkout annuel est implémenté côté serveur : montant et intervalle Stripe sont déterminés depuis le catalogue. L'interface ne déclenche volontairement pas encore de paiement.
- Les packs sont définis côté serveur mais leur paiement et leur attribution ne sont pas activés.
- Les crédits mensuels sont des quotas commerciaux déclaratifs : aucun portefeuille transactionnel, débit atomique, expiration, report ou journal de crédits n'est encore implémenté. Ne pas les présenter comme des crédits techniquement disponibles avant ce chantier.
- Le plafond d'accès est raccordé aux quatre nouvelles offres ; le module de facturation Chorus Pro et les fonctions CAP/CST/CCP/F3SCT ne sont pas activés par ce changement.
- L'interface tarifaire TTC est préparée dans la PR brouillon #19, non intégrée à cette branche tant que cette PR n'est pas fusionnée.
- Aucun abonnement, paiement, migration de base ou configuration Stripe réelle n'a été modifié.

## Audit des hypothèses économiques

Hypothèses de calcul communiquées : TVA 20 %, frais Stripe 1,5 % + 0,25 € par paiement, coût IA moyen 0,0331 € par crédit. Calculs hors coûts fixes, support, stockage, OCR, frais bancaires atypiques, remboursements, impayés et fiscalité de l'entreprise.

| Offre | Contribution estimée à 40 % d'usage | Marge recalculée à 40 % | Marge recalculée à 100 % |
|---|---:|---:|---:|
| Essentiel | 10,29 € | 82,9 % | 62,9 % |
| Pro | 20,20 € | 83,6 % | 63,2 % |
| Équipe & Instances | 83,89 € | 84,6 % | 64,6 % |
| Collectivité & Syndicats | 211,99 € | 85,1 % | 65,6 % |

La contribution à 40 % retrouve les montants communiqués, mais les marges annoncées dans la grille initiale (86,0–86,7 % / 65,0–66,8 %) ne sont pas reproductibles avec les hypothèses affichées. Il faut donc remplacer ces taux dans le prévisionnel avant toute décision commerciale.

### Packs

- 200 crédits : 29 € TTC / 1,20 − (1,5 % × 29 € + 0,25 €) = 23,48 € après TVA et frais estimés ; moins 6,62 € de coût IA = 16,86 € de contribution, soit environ 71,8 %.
- 600 crédits : 79 € TTC / 1,20 − (1,5 % × 79 € + 0,25 €) = 64,40 € ; moins 19,86 € de coût IA = 44,54 €, soit environ 69,2 %.

Ces marges sont des contributions avant frais fixes et fiscalité, pas des bénéfices nets garantis. Le taux de prélèvements de 35 % et l'objectif de revenu personnel de 5 000 € nécessitent une simulation comptable selon la structure juridique et le régime fiscal retenus.

## Prochain chantier obligatoire avant activation commerciale

1. Implémenter le portefeuille de crédits côté serveur (ledger append-only, débit atomique, idempotence, gestion des erreurs et remboursements).
2. Définir les coûts unitaires distincts : question simple, analyse approfondie, rapport de commission, stockage et génération PDF.
3. Conserver le Checkout annuel serveur et ajouter le choix mensuel/annuel dans l'interface au moment de l'activation commerciale ; vérifier le cycle annuel et les metadata webhook.
4. Activer les packs via Checkout en paiement ponctuel, puis créditer uniquement après webhook signé et idempotent.
5. Définir report/expiration des crédits, priorité de consommation, dépassement, remboursement et résiliation.
6. Intégrer la PR #19, vérifier l'interface tarifaire et tester les plafonds 1/5/15 ainsi que la compatibilité des abonnements historiques.
7. Valider fiscalité, CGV, facturation et frais Stripe réels avec le comptable avant toute commercialisation.

## État de déploiement

Changements de code uniquement sur une branche isolée. Aucun déploiement, paiement, appel fournisseur, migration de base ou merge n'est effectué.
