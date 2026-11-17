# 05 — Sécurité, confidentialité et RGPD (V3)

## Implémenté dans le kit
- Validation JWT OIDC : signature via JWKS, issuer, audience, expiration et algorithmes configurés.
- Vérification de l'identité active et du membership ACTIVE à chaque requête tenant.
- Vérification du statut ACTIVE de l'organisation.
- Identifiant d'organisation sélectionné par en-tête mais jamais considéré comme preuve d'autorisation.
- Contexte RLS défini transactionnellement avec `set_config(..., true)`.
- RLS + FORCE RLS dans la migration sur toutes les tables métier privées.
- Pas d'historique de conversation persistant ; moteur juridique fermé sans source vérifiée.

## À configurer / vérifier avant production
- Fournisseur OIDC, client, audience, JWKS, MFA, durée de session et révocation côté IdP.
- Rôle SQL runtime séparé, sans propriété des tables, `BYPASSRLS` ou `SUPERUSER`.
- TLS, reverse proxy, secrets manager, sauvegardes chiffrées, supervision et rotation des secrets.
- Comptabilisation des tokens IA par organisation et utilisateur : seules les métadonnées fournisseur/modèle, les compteurs de tokens disponibles, l'issue de l'appel (réponse, réponse rejetée ou erreur fournisseur) et un identifiant technique sont stockés. Aucun prompt, réponse, conversation ou extrait documentaire n'est enregistré dans ce journal. Le rôle runtime peut uniquement insérer ; la lecture nécessite un accès administratif distinct.
- Limitation PostgreSQL atomique des requêtes chat par utilisateur et organisation (10/minute par défaut, configurable de 1 à 120), avec réponse HTTP 429 et Retry-After. Cette protection applicative ne remplace pas le rate limiting réseau/WAF ni un quota mensuel de coûts IA.
- Les quotas mensuels et le calcul de coûts IA restent à définir à partir des tarifs réels des fournisseurs et des plans commerciaux ; les compteurs inconnus restent NULL et aucun coût estimé n'est inventé. Politique CORS et protections anti-abus en frontal restent à vérifier/configurer.
- Analyse des dépendances et images Docker.
- Procédure de désactivation/révocation et test de propagation immédiate.
- Tests PostgreSQL réels de non-fuite A/B pour SELECT, INSERT, UPDATE et DELETE.

## Données interdites dans le MVP
Ne pas saisir noms/prénoms d'agents, matricules, adresses, coordonnées, bulletins de paie, diagnostics, comptes rendus médicaux, arrêts identifiants, données disciplinaires nominatives ou données syndicales nominatives.

## Fournisseur IA et RGPD
Avant tout choix : vérifier contrat de sous-traitance, localisation, transferts, rétention, usage des données, sous-traitants, suppression et non-entraînement. Responsable de traitement et DPO déterminent finalités, base légale, information, durées, sous-traitants, transferts et nécessité d'une AIPD.
