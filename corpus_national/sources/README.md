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
3. demander l'import complet en ajoutant le marqueur `corpus_national/sources/FULL_IMPORT_REQUESTED` sur la branche de développement. Le workflow détecte ce marqueur et importe toutes les fiches. Sans marqueur, un push autorise uniquement un pilote de dix fiches.
Sans ce secret, aucune écriture n'est effectuée. Ne jamais utiliser le compte propriétaire ou le compte runtime pour contourner ce contrôle.


## Périmètre des sources communiquées pour Dikévia

Le registre recense notamment les domaines suivants. Leur statut individuel (candidat, accès examiné, réutilisation approuvée, importé ou indexé) fait foi ; l'inscription d'un domaine ne signifie pas que ses documents sont intégrés :

- **Socle public national** : Légifrance, Service-Public.gouv.fr, data.gouv.fr, DGAFP (`fonction-publique.gouv.fr`), DGCL (`collectivites-locales.gouv.fr`), Info.gouv.fr.

Le SIG / Info.gouv.fr est qualifié comme guidance administrative officielle non normative. Quatre ressources ciblées ont été ajoutées au registre : présentation des missions du SIG, page « La marque de l'État », PDF « Charte d'accessibilité de la communication de l'État » (64 pages, septembre 2022) et PDF « Charte pour un usage responsable de l'IA pour les communicants de l'État » (février 2026). Les mentions légales du portail prévoient la Licence Ouverte Etalab 2.0 pour les contenus hors droits de tiers, avec attribution de la source et de la date de dernière mise à jour. La collecte porte uniquement sur ces URL précises ; les images et contenus tiers sont exclus. Les deux PDF ont été téléchargés et extraits avec succès lors du dry-run du 24 novembre 2026 : la charte d'accessibilité (64 pages, 85 022 caractères ; SHA-256 du fichier `2769053883943eccafc9707febc32daf088a295f41b326608aca99a2e05fde58`) et la charte IA (49 pages, 69 101 caractères ; SHA-256 `e870ea079281b65ea395fc7956a7fb4043f4a0e407465606dc9b502bd1f2b912`). Les deux pages HTML ont renvoyé HTTP 403 et restent non extraites. Les deux PDF restent toutefois en dry-run uniquement : aucune écriture PostgreSQL n'a été réalisée, leur `content_status` demeure `NOT_COLLECTED` au sens de l'intégration persistante, et leur statut juridique demeure `UNKNOWN` / `NOT_VERIFIED`. Aucun de ces contenus n'est indexé dans Neon.
- **CNFPT** : `cnfpt.fr` et `wikiterritorial.cnfpt.fr`.
- **CIG** : `cig929394.fr` (Petite Couronne) et `cigversailles.fr` (Grande Couronne).
- **CDG** : `cdg35.fr` / `cdg35.bzh`, `cdg44.fr`, `cdg59.fr` et `cdg69.fr`.

Le registre prévoit les glossaires DGAFP/CNFPT, les guides RH DGAFP, les ressources statutaires DGCL et les fiches pratiques/lexiques CDG-CIG. Seules les pages publiques sont dans le périmètre ; aucun extranet, espace abonné ou contenu réservé ne doit être aspiré sans autorisation.

## Import Service-Public Particuliers

Le flux DILA 3.5 est publié quotidiennement et réutilisable sous Licence Ouverte 2.0, avec attribution obligatoire à Service-Public.gouv.fr / DILA, URL complète de téléchargement, nom du fichier et date du fichier.

### Sources syndicales : traitement documentaire spécifique

Les publications syndicales sont enregistrées dans une famille distincte `TRADE_UNION_POSITION`. Elles servent à documenter les analyses, revendications, guides pratiques, argumentaires et retours d'expérience des organisations. Elles ne constituent pas, à elles seules, une preuve du droit positif.

Règles de traitement :
- conserver systématiquement l'organisation éditrice, la date, le versant et le contexte ;
- distinguer une règle juridique citée, une interprétation syndicale, une revendication et un commentaire ;
- vérifier toute règle de droit dans le CGFP, les lois, décrets, arrêtés et jurisprudences applicables ;
- en cas de divergence entre organisations, restituer les positions attribuées sans fabriquer de consensus ;
- ne pas présenter une organisation comme référence exclusive ou comme source neutre ;
- vérifier les droits de réutilisation avant toute ingestion durable ou exposition de larges extraits.

Périmètre initial inscrit au registre : CFDT Fonctions Publiques (UFFA), CFDT Interco, CGT Fonction publique, FO Fonction publique, CFTC, UNSA Fonction Publique et Solidaires Fonction publique. Les pages et documents restent candidats tant que collecte, fraîcheur, portée et réutilisation ne sont pas contrôlées.

Le Guide de l'agent public 2026 CFDT Interco est identifié via sa page de présentation du 22 octobre 2026 et le PDF intégral hébergé par CFDT Interco 35 (`https://cfdtinterco35.fr/wp-content/uploads/2026/04/Guide-de-lagent-public-2026-PDF.pdf`). Le PDF a été téléchargé/extrait en dry-run le 22 novembre 2026 : 68 pages, 181 469 caractères. Au contrôle du 24 novembre, la page de présentation et le PDF figurent tous deux dans la base Neon de staging ; leur réutilisation est approuvée, mais leur statut reste `IMPORTED_UNVERIFIED`, `UNKNOWN` et `NOT_VERIFIED` sur le plan juridique. Ils ne constituent pas des preuves normatives et ne sont pas déclarés importés en production.

### Résultat de collecte vérifié — 22 novembre 2026

Le workflow a téléchargé et extrait :
- **199 fiches Service-Public Fonction publique**, soit environ 4,45 millions de caractères ; 194 comportent des références juridiques extraites ;
- **18 ressources institutionnelles et syndicales** (6 PDF et 12 pages HTML : DGAFP, CDG35, CIG Petite Couronne, CDG59, CDG69, CNFPT, CFDT, CGT, FO, CFTC, UNSA et Solidaires), dont 241 pages PDF et environ 590 000 caractères.

Les empreintes SHA-256 des textes extraits ont été contrôlées. Les fiches Service-Public sont préparées comme `ADMIN_GUIDANCE`, `IMPORTED_UNVERIFIED`, avec version et dates d'effet inconnues. Les ressources professionnelles et syndicales ne sont importées que lorsque leur réutilisation est explicitement approuvée. La page Solidaires extraite ne contient que 890 caractères : elle reste une collecte partielle, à approfondir.

### État d'intégration vérifié sur Neon staging — 24 novembre 2026

Une vérification en lecture seule de la branche Neon de staging `br-billowing-haze-bd5a1cns` a établi la composition suivante :

| Famille | Documents | Fragments |
|---|---:|---:|
| Snapshot CGFP | 4 242 | 4 253 |
| Fiches Service-Public | 199 | 1 226 |
| Ressources institutionnelles, professionnelles et syndicales | 18 | 161 |
| **Total** | **4 459** | **5 640** |

Les 5 640 fragments disposent d'un embedding 384 dimensions conforme au modèle `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ; aucune incohérence de modèle ou de dimension n'a été détectée. Le workflow de staging a confirmé cette couverture et n'a pas eu besoin de régénérer les vecteurs.
Le même workflow exécute un contrôle de retrieval vectoriel seul sur quatre questions techniques. Il vérifie le modèle, le SQL, les dates et la disponibilité de résultats réels ; il ne certifie pas la pertinence juridique ni le classement métier.

Pour les 199 fiches Service-Public et les 18 ressources complémentaires, les documents restent `IMPORTED_UNVERIFIED` et leur statut juridique reste `UNKNOWN`. Les 18 ressources complémentaires ont un statut de réutilisation `REUSE_APPROVED`, mais leur validation juridique reste `NOT_VERIFIED`. Les sources syndicales restent identifiées dans le registre comme `TRADE_UNION_POSITION` ; en base, elles sont stockées sous `INSTITUTIONAL_GUIDANCE` avec les métadonnées d'éditeur nécessaires à leur classement comme doctrine syndicale non normative.

Le moteur les traite comme contexte documentaire non normatif : `claim_eligible=false`, `reference_role=NON_NORMATIVE_CONTEXT_ONLY` et `usable_for_conclusion=false`. Elles peuvent aider à expliquer ou contextualiser une réponse, mais ne peuvent pas fonder seules une affirmation juridique ni remplacer une référence officielle. Des tests automatisés vérifient cette séparation.

**Périmètre de cette vérification : staging uniquement.** Aucune base de production n'a été interrogée ; il ne faut donc pas déduire de ces chiffres que les mêmes documents sont présents en production. La présence en base et la vectorisation ne valent ni validation juridique, ni validation complète de la pertinence du retrieval.

Les identifiants présents dans les éléments XML `Reference` de Service-Public sont conservés sous `source_reference_id`. Ils ne sont exposés sous `id_legifrance` que lorsque leur format correspond explicitement à un identifiant Légifrance reconnu (par exemple `LEGIARTI…`, `LEGITEXT…` ou `JORFTEXT…`). Un identifiant interne tel que `R57657` ne doit jamais être présenté ni transformé en identifiant Légifrance. Même lorsqu'un identifiant Légifrance est reconnu syntaxiquement, la référence et sa version restent à vérifier sur Légifrance avant toute utilisation juridique.

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
