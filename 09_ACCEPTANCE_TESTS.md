# 09 — Tests d'acceptation obligatoires

## Fiabilité juridique
- Une question déclenche une vraie recherche nationale.
- Le texte intégral et l'identifiant officiel sont récupérés lorsque la source le permet.
- La version applicable à la date des faits est déterminée ou l'incertitude est explicitement signalée.
- Une source absente n'est jamais citée.
- Une citation inconnue du validateur bloque la réponse ou est retirée.
- Une API en panne ne déclenche pas de réponse juridique de mémoire.
- L'absence de résultat n'est jamais interprétée comme absence de droit.
- Jurisprudence uniquement si récupérée et vérifiable.

## Isolation multi-tenant et propriété des conversations
- Un membre A ne peut pas lister les membres B.
- Un membre A ne peut pas lire/modifier un document B.
- Un administrateur A ne peut pas administrer B.
- Changer un UUID dans une URL ne contourne pas le contrôle.
- Un utilisateur A ne peut ni lire ni modifier les conversations, messages ou dossiers d'un autre utilisateur A.
- Un utilisateur de l'organisation A ne peut ni lire ni modifier les conversations, messages ou dossiers de l'organisation B.
- Les caches et fichiers sont isolés.
- La suspension d'un tenant coupe ses accès sans affecter les autres.
- La suppression d'une conversation supprime ses messages et traite correctement les dossiers associés selon la règle de conservation validée.

## Confidentialité et données persistées
- Les conversations, messages et dossiers sont persistés uniquement dans les espaces de stockage autorisés et protégés par RLS/FORCE RLS.
- Le contenu des conversations n'est jamais recopié dans les logs applicatifs, traces, analytics ou journaux de consommation IA.
- Aucun contenu de chat n'est stocké dans localStorage/sessionStorage.
- Le navigateur reçoit un request_id non révélateur.
- Les secrets ne sont jamais présents dans le dépôt ou le frontend.
- Les documents ne sont pas servis publiquement.
- Une durée de conservation approuvée est appliquée aux conversations, messages, dossiers, documents et journaux concernés.
- La purge automatique est testée, y compris les effets sur les sauvegardes et les restaurations.
- Les demandes d'accès, d'export et de suppression sont testées selon le processus validé par le responsable de traitement/DPO.

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
