# 05 — Sécurité, confidentialité et RGPD (V3)

## Contrôles présents dans le kit
- Validation JWT OIDC : signature via JWKS, issuer, audience, expiration et algorithmes configurés.
- Vérification de l'identité active et du membership ACTIVE à chaque requête tenant.
- Vérification du statut ACTIVE de l'organisation.
- Identifiant d'organisation sélectionné par en-tête mais jamais considéré comme preuve d'autorisation.
- Contexte RLS défini transactionnellement avec `set_config(..., true)`.
- RLS + FORCE RLS sur les tables métier privées ; les conversations et messages sont limités à leur organisation et à leur utilisateur propriétaire.
- Les conversations et messages sont persistés dans PostgreSQL ; les dossiers juridiques sont également persistés. Il ne faut donc pas présenter le produit actuel comme un chat sans historique serveur.
- Le journal de consommation IA conserve des métadonnées techniques et compteurs disponibles, pas les prompts, réponses, messages ou documents.
- Les contrôles de références empêchent de présenter une source non vérifiée comme fondement juridique.

## Points bloquants à traiter avant production
- Définir avec le responsable de traitement/DPO les finalités, bases légales, durées de conservation et règles de purge des conversations, messages, dossiers, documents, journaux d'audit et métadonnées de consommation.
- Implémenter et tester une purge automatique conforme à ces durées ; vérifier les sauvegardes, exports et suppressions en cascade.
- Définir les droits d'accès, d'export et de suppression des utilisateurs et administrateurs, ainsi que le traitement des demandes RGPD.
- Fournisseur OIDC, client, audience, JWKS, MFA, durée de session et révocation côté IdP.
- Rôle SQL runtime séparé, sans propriété des tables, `BYPASSRLS` ou `SUPERUSER`.
- TLS, reverse proxy, secrets manager, sauvegardes chiffrées, supervision et rotation des secrets.
- Rate limiting, quotas, politique CORS et protections anti-abus en frontal.
- Analyse des dépendances et images Docker.
- Procédure de désactivation/révocation et test de propagation immédiate.
- Tests PostgreSQL réels de non-fuite A/B pour SELECT, INSERT, UPDATE et DELETE, y compris conversations, messages et dossiers.
- Vérifier que les contenus conversationnels ne sont jamais recopiés dans les logs applicatifs, traces, analytics ou journaux de consommation IA.

## Données à ne pas saisir dans le pilote
Ne pas saisir noms/prénoms d'agents, matricules, adresses, coordonnées, bulletins de paie, diagnostics, comptes rendus médicaux, arrêts identifiants, données disciplinaires nominatives ou données syndicales nominatives tant que le cadre de traitement, les habilitations et les mesures de sécurité adaptées n'ont pas été validés.

## Fournisseur IA et RGPD
Avant tout choix : vérifier contrat de sous-traitance, localisation, transferts, rétention, usage des données, sous-traitants, suppression et non-entraînement. Responsable de traitement et DPO déterminent finalités, base légale, information, durées, sous-traitants, transferts et nécessité d'une AIPD.

## État de conformité
La présence de contrôles techniques dans le dépôt ne constitue pas une conformité RGPD démontrée. La recette juridique, la documentation du traitement, les contrats, la politique de conservation et la purge effective restent à valider avant tout usage avec des dossiers réels.
