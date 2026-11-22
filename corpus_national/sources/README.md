# Sources du corpus national

Le registre `registry.json` distingue le statut de gouvernance d'une source de son état réel d'intégration. Une entrée `CANDIDATE` n'est ni collectée ni indexée. Les statuts `IMPORTED` et `RETRIEVAL_VERIFIED` ne doivent être attribués qu'après vérification dans la base et par des tests de recherche.

## Collecte automatisée des PDF et pages HTML

Le script `scripts/import_public_guidance_sources.py` télécharge les ressources PDF/HTML du tableau `document_seeds`, vérifie le domaine final contre la liste blanche du registre, limite la taille, extrait le texte, calcule les empreintes SHA-256 et prépare les métadonnées de provenance.

- Sans option : téléchargement/extraction en **dry-run**, aucune écriture PostgreSQL.
- `--id <seed-id>` : sélection d'une ou plusieurs ressources précises.
- `--apply` : écriture via le rôle dédié `cfdt_juris_ingest` uniquement si la source et la ressource sont toutes deux explicitement marquées `REUSE_APPROVED` (ou `APPROVED`).
- Les documents importés restent `IMPORTED_UNVERIFIED`, `UNKNOWN` et `ADMIN_GUIDANCE` ou `PROFESSIONAL_GUIDANCE` ; ils ne constituent jamais une preuve juridique primaire.
- Les dates d'effet restent nulles lorsqu'elles ne sont pas établies. Un PDF image sans couche texte exploitable est rejeté ; l'OCR doit être ajouté séparément avec contrôle qualité.

Exemple de prévisualisation : `python scripts/import_public_guidance_sources.py --id dgafp-faq-tpt-2026`.

### Exécution sécurisée de l'import Service-Public

Le workflow GitHub `Corpus public-source pilot` réalise une collecte réelle en dry-run à chaque changement pertinent. Pour autoriser l'écriture :
1. créer le secret GitHub Actions `LEGAL_CORPUS_INGEST_DATABASE_URL` avec la chaîne PostgreSQL du rôle dédié `cfdt_juris_ingest` ;
2. vérifier que la CI est verte ;
3. lancer manuellement `Corpus public-source pilot` sur la branche de développement : le déclenchement manuel importe l'ensemble des fiches sélectionnées. Le push automatique, lui, se limite à un pilote de dix fiches.
Sans ce secret, aucune écriture n'est effectuée. Ne jamais utiliser le compte propriétaire ou le compte runtime pour contourner ce contrôle.


## Périmètre des sources communiquées pour Dikévia

Le registre recense notamment les domaines suivants. Leur statut individuel (candidat, accès examiné, réutilisation approuvée, importé ou indexé) fait foi ; l'inscription d'un domaine ne signifie pas que ses documents sont intégrés :

- **Socle public national** : Légifrance, Service-Public.gouv.fr, data.gouv.fr, DGAFP (`fonction-publique.gouv.fr`), DGCL (`collectivites-locales.gouv.fr`), Info.gouv.fr.
- **CNFPT** : `cnfpt.fr` et `wikiterritorial.cnfpt.fr`.
- **CIG** : `cig929394.fr` (Petite Couronne) et `cigversailles.fr` (Grande Couronne).
- **CDG** : `cdg35.fr` / `cdg35.bzh`, `cdg44.fr`, `cdg59.fr` et `cdg69.fr`.

Le registre prévoit les glossaires DGAFP/CNFPT, les guides RH DGAFP, les ressources statutaires DGCL et les fiches pratiques/lexiques CDG-CIG. Seules les pages publiques sont dans le périmètre ; aucun extranet, espace abonné ou contenu réservé ne doit être aspiré sans autorisation.

## Import Service-Public Particuliers

Le flux DILA 3.5 est publié quotidiennement et réutilisable sous Licence Ouverte 2.0, avec attribution obligatoire à Service-Public.gouv.fr / DILA, URL complète de téléchargement, nom du fichier et date du fichier.

### Résultat de collecte vérifié — 22 novembre 2026

Le workflow a téléchargé et extrait :
- **199 fiches Service-Public Fonction publique**, soit environ 4,45 millions de caractères ; 194 comportent des références juridiques extraites ;
- **9 ressources professionnelles** (5 PDF et 4 pages HTML : DGAFP, CDG35, CIG Petite Couronne, CDG59, CDG69 et CNFPT), dont 173 pages PDF et environ 359 000 caractères.

Les empreintes SHA-256 des textes extraits ont été contrôlées. Les fiches Service-Public sont préparées comme `ADMIN_GUIDANCE`, `IMPORTED_UNVERIFIED`, avec version et dates d'effet inconnues. Les ressources professionnelles restent `EXTRACTED_NOT_IMPORTED` et `REVIEW_REQUIRED` pour la réutilisation. Aucun de ces documents n'est encore présent dans PostgreSQL.

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
