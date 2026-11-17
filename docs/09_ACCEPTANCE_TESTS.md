# 09 — Tests d'acceptation obligatoires

## Fiabilité juridique
- Une question déclenche une vraie recherche nationale.
- Le texte intégral et l'identifiant officiel sont récupérés.
- La version applicable à la date des faits est déterminée.
- Une source absente n'est jamais citée.
- Une citation inconnue du validateur bloque la réponse ou est retirée.
- Une API en panne ne déclenche pas de réponse juridique de mémoire.
- L'absence de résultat n'est jamais interprétée comme absence de droit.
- Jurisprudence uniquement si récupérée et vérifiable.

## Isolation multi-tenant
- Un membre A ne peut pas lister les membres B.
- Un membre A ne peut pas lire/modifier un document B.
- Un administrateur A ne peut pas administrer B.
- Changer un UUID dans une URL ne contourne pas le contrôle.
- Les caches et fichiers sont isolés.
- La suspension d'un tenant coupe ses accès sans affecter les autres.

## Confidentialité
- Aucun contenu de chat dans PostgreSQL, Redis, logs, traces ou analytics.
- Aucun contenu de chat dans localStorage/sessionStorage.
- Le navigateur reçoit un request_id non révélateur.
- Les secrets ne sont jamais présents dans le dépôt ou le frontend.
- Les documents ne sont pas servis publiquement.

## Corpus local
- Acte Ville jamais utilisé pour Métropole et inversement.
- Annexe absente = statut incomplet.
- Acte abrogé/remplacé non présenté comme applicable.
- Dates d'adoption, publication et effet distinguées.

## Exploitation
- Sauvegarde/restauration testée.
- Déploiement rollback testé.
- Alertes connecteur et latence.
- Limitation de débit et gestion des quotas.
- Dépendances et images conteneurs scannées.
