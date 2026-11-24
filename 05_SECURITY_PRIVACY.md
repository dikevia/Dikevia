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

L'instance de développement utilise actuellement Google Gemini 2.5 Flash via l'API Google. Lorsqu'une analyse IA est déclenchée, le backend transmet au fournisseur la question, l'employeur déclaré, la date ou période des faits, le contexte récent de conversation et les extraits documentaires retenus. Les métadonnées de consommation IA ne conservent pas les prompts ni les réponses, mais les échanges eux-mêmes restent enregistrés dans PostgreSQL conformément au fonctionnement du chat.

L'interface du pilote doit informer explicitement de cette transmission et imposer l'usage de situations fictives ou anonymisées tant que le cadre de traitement, les contrats et les garanties du fournisseur n'ont pas été validés.

Le backend applique désormais, avant transfert des questions et de l'historique récent aux fournisseurs IA, un masquage déterministe de certains identifiants directs courants : adresses e-mail, numéros de téléphone français, NIR et IBAN. Cette mesure réduit l'exposition de ces identifiants mais ne constitue pas une anonymisation : elle ne détecte pas de façon fiable les noms, adresses postales, identifiants métier ou toutes les formes d'identifiants. Elle ne supprime pas non plus les données sensibles de santé, disciplinaires ou syndicales nécessaires au contexte, ni les données personnelles pouvant figurer dans les extraits documentaires transmis. Les restrictions de saisie, l'information des utilisateurs et la validation juridique/contractuelle restent donc intégralement applicables.
Avant tout choix : vérifier contrat de sous-traitance, localisation, transferts, rétention, usage des données, sous-traitants, suppression et non-entraînement. Responsable de traitement et DPO déterminent finalités, base légale, information, durées, sous-traitants, transferts et nécessité d'une AIPD.

## État de conformité
La présence de contrôles techniques dans le dépôt ne constitue pas une conformité RGPD démontrée. La recette juridique, la documentation du traitement, les contrats, la politique de conservation et la purge effective restent à valider avant tout usage avec des dossiers réels.


## V3.37 — mécanisme de purge privée préparé, non activé

Un utilitaire opérateur `scripts/purge_private_conversations.py` est ajouté pour préparer la purge des conversations privées et de leurs données dépendantes.

- Aucun délai de conservation n'est codé en dur et aucun seuil par défaut n'existe.
- Le seuil doit être fourni explicitement en date/heure ISO-8601 avec fuseau.
- Le mode par défaut est une prévisualisation sans suppression.
- L'exécution réelle exige simultanément `--execute` et `--confirm-delete`.
- La connexion doit utiliser `RETENTION_DATABASE_URL`, un compte explicitement autorisé à contourner RLS ; le script refuse un compte qui ne possède ni `SUPERUSER` ni `BYPASSRLS`.
- La suppression cible les conversations dont `updated_at` est antérieur au seuil ; les messages et dossiers associés sont supprimés par les contraintes de cascade déjà testées.
- La sortie ne contient que le nombre de conversations supprimées/prévues et les identifiants d'organisation avec leurs compteurs, jamais les contenus.
- L'outil n'est pas appelé par l'API, n'est pas planifié et n'est pas exécuté sur une base réelle. Il n'y a pas de variable de durée préconfigurée.

**Important :** ce mécanisme technique ne définit pas la politique juridique. Avant toute activation, le responsable du traitement/DPO doit encore décider et documenter les durées, le point de départ du délai (la règle actuelle utilise le champ technique `updated_at`), les exceptions éventuelles (contentieux, gel légal, demandes d'accès), les sauvegardes et le périmètre des autres données. La purge des documents téléversés, journaux d'audit et métriques est hors du périmètre de cet utilitaire. Aucune suppression automatique n'est active.
