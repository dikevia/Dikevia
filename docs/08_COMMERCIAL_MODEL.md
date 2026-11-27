# 08 — Modèle commercial actuel de Dikévia

Ce document remplace les anciennes hypothèses de prix et de capacité. La référence technique des droits est également décrite dans [54_AGENT_UNION_ACCESS_MODEL.md](54_AGENT_UNION_ACCESS_MODEL.md).

## Agent individuel

- Tarif cible : **5 € TTC par mois**.
- Un seul accès.
- Chatbot juridique uniquement.
- Limite commerciale : **5 questions par jour civil**, selon le fuseau Europe/Paris.
- Les modules CST, formation spécialisée, CAP, CCP, défense et outils syndicaux ne sont pas inclus dans cette offre.

## Abonnements syndicaux

Trois capacités sont prévues :

| Offre | Accès | Fonctionnalités | Quota commercial de questions |
|---|---:|---|---|
| Syndicat 5 | 5 | Toutes les fonctionnalités Dikévia | Aucun |
| Syndicat 10 | 10 | Toutes les fonctionnalités Dikévia | Aucun |
| Syndicat 15 | 15 | Toutes les fonctionnalités Dikévia | Aucun |

Les prix de ces trois abonnements ne sont pas encore définis. Ne pas inventer de prix, de crédits ou de plafonds de questions.

## Périmètre commercial

- Aucune offre collectivité n'est commercialisée.
- Les collectivités peuvent être des périmètres documentaires dans le travail syndical, mais ne constituent pas une catégorie de client ou d'abonnement à ce stade.
- Le modèle privé historique à 10 membres n'est pas une offre commerciale actuelle et reste désactivé par défaut.
- Le privilège fondateur permanent est distinct d'un abonnement commercial. Il doit être rattaché à une identité OIDC vérifiée par issuer et subject, jamais à une adresse e-mail seule.

## Paiement et période de bêta

- Dikévia reste gratuit pendant la phase actuelle.
- Aucun paiement, checkout, rechargement de crédits ou service payant n'est activé.
- Stripe reste désactivé. Ne pas réactiver les anciens flux de facturation sans prix validés et autorisation explicite.
- Aucun coût externe ne doit être généré sans accord explicite.

## Application des droits

- Les droits sont calculés côté serveur à partir de l'identité, de l'appartenance à l'organisation et de l'abonnement actif.
- Les restrictions ne doivent jamais reposer uniquement sur le masquage d'éléments de l'interface.
- Le quota quotidien de cinq questions concerne l'offre Agent individuelle.
- Les limites techniques anti-abus (par minute, concurrence, taille de requête) sont distinctes des quotas commerciaux.
- Les abonnements syndicaux donnent accès aux modules syndicaux sans quota commercial de questions.

## Référence d'état

Pour les validations réellement exécutées, les limites connues et les tâches restantes, consulter [57_ETAT_CONSOLIDE_2026-11-27.md](57_ETAT_CONSOLIDE_2026-11-27.md). Les prix syndicaux restent à définir ; ne pas créer de checkout en attendant.
