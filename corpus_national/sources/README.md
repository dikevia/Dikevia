# Sources du corpus national

Le registre `registry.json` distingue le statut de gouvernance d'une source de son état réel d'intégration. Une entrée `CANDIDATE` n'est ni collectée ni indexée. Les statuts `IMPORTED` et `RETRIEVAL_VERIFIED` ne doivent être attribués qu'après vérification dans la base et par des tests de recherche.

## Collecte automatisée des PDF et pages HTML

Le script `scripts/import_public_guidance_sources.py` télécharge les ressources PDF/HTML du tableau `document_seeds`, vérifie le domaine final contre la liste blanche du registre, limite la taille, extrait le texte, calcule les empreintes SHA-256 et prépare les métadonnées de provenance.

- Sans option : téléchargement/extraction en **dry-run**, aucune écriture PostgreSQL.
- `--id <seed-id>` : sélection d'une ou plusieurs ressources précises.
- `--apply` : écriture via le rôle dédié `cfdt_juris_ingest` uniquement si la source et la réutilisation sont toutes deux explicitement marquées `APPROVED`.
- Les documents importés restent `IMPORTED_UNVERIFIED`, `UNKNOWN` et `ADMIN_GUIDANCE` ou `PROFESSIONAL_GUIDANCE` ; ils ne constituent jamais une preuve juridique primaire.
- Les dates d'effet restent nulles lorsqu'elles ne sont pas établies. Un PDF image sans couche texte exploitable est rejeté ; l'OCR doit être ajouté séparément avec contrôle qualité.

Exemple de prévisualisation : `python scripts/import_public_guidance_sources.py --id dgafp-faq-tpt-2026`.

## Périmètre des sources communiquées pour Dikévia

Le registre recense notamment les domaines suivants, tous encore au statut `CANDIDATE` tant que leur collecte, leurs droits de réutilisation et leur indexation n'ont pas été contrôlés :

- **Socle public national** : Légifrance, Service-Public.gouv.fr, data.gouv.fr, DGAFP (`fonction-publique.gouv.fr`), DGCL (`collectivites-locales.gouv.fr`), Info.gouv.fr.
- **CNFPT** : `cnfpt.fr` et `wikiterritorial.cnfpt.fr`.
- **CIG** : `cig929394.fr` (Petite Couronne) et `cigversailles.fr` (Grande Couronne).
- **CDG** : `cdg35.fr`, `cdg44.fr`, `cdg59.fr` et `cdg69.fr`.

Le registre prévoit les glossaires DGAFP/CNFPT, les guides RH DGAFP, les ressources statutaires DGCL et les fiches pratiques/lexiques CDG-CIG. Seules les pages publiques sont dans le périmètre ; aucun extranet, espace abonné ou contenu réservé ne doit être aspiré sans autorisation.

## Import Service-Public Particuliers

Le flux DILA 3.5 est publié quotidiennement et réutilisable sous Licence Ouverte 2.0, avec attribution obligatoire à Service-Public.gouv.fr / DILA, URL complète de téléchargement, nom du fichier et date du fichier.

Le script `scripts/import_service_public_to_legal_corpus.py` :
- télécharge les métadonnées du jeu de données et l'archive ZIP courante ;
- filtre les fiches du thème Fonction publique ;
- conserve références, versants détectés et provenance dans les métadonnées ;
- indexe les fiches comme `ADMIN_GUIDANCE` avec le statut `IMPORTED_UNVERIFIED` ;
- ne promeut jamais les références extraites au rang de textes officiels ;
- n'écrit rien par défaut.

Depuis la racine du dépôt, après installation de `backend/requirements.txt` :

```bash
PYTHONPATH=backend python scripts/import_service_public_to_legal_corpus.py --limit 5
```

Cette commande est un aperçu sans écriture. Pour un import pilote, définir `LEGAL_CORPUS_INGEST_DATABASE_URL` avec le seul rôle PostgreSQL `cfdt_juris_ingest`, puis exécuter explicitement :

```bash
PYTHONPATH=backend python scripts/import_service_public_to_legal_corpus.py --apply --limit 5
```

Après contrôle du nombre de fiches, des empreintes, de la provenance et des résultats de recherche, l'import complet peut être lancé sans `--limit`. Ne pas lancer l'import de production avant validation du pilote.

## Règles de hiérarchie

- Légifrance et les sources normatives officielles restent le fondement juridique primaire.
- Service-Public, DGAFP et DGCL sont des ressources administratives officielles d'explication.
- CNFPT, CIG et CDG sont des ressources professionnelles/statutaires : elles éclairent l'analyse mais ne remplacent pas les textes.
- Un versant détecté lexicalement reste un indice, jamais une qualification juridique validée.
- Les dates d'effet absentes restent inconnues ; ne pas les inférer de la date de collecte.
