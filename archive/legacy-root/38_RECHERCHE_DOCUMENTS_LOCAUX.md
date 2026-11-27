# Recherche dans les documents propres à l'employeur

## Fonctionnement

Le moteur juridique interroge le corpus local uniquement lorsque l'employeur sélectionné est une collectivité locale. La recherche est strictement limitée à l'organisation de l'utilisateur courant (`organization_id`) et aux documents dont le fichier et la version sont marqués `CLEAN`, dont le texte est extrait (`EXTRACTED`) et dont l'empreinte correspond à celle de la version stockée.

Les documents sont recherchés dans `document_text` via la recherche plein texte PostgreSQL en français. Le moteur retourne un extrait borné et les métadonnées de la pièce ; le texte complet n'est pas renvoyé au navigateur.

## Filtrage de la collectivité

Les choix d'employeur actuellement proposés par l'interface sont `VILLE_SAINT_ETIENNE` et `SAINT_ETIENNE_METROPOLE`. La recherche utilise les codes et noms de collectivité suivants :

- Ville de Saint-Étienne : `VILLE_SAINT_ETIENNE`, `VILLE_ST_ETIENNE`, `VILLE_DE_SAINT_ETIENNE` ou noms exacts configurés dans `backend/app/local_corpus.py`.
- Saint-Étienne Métropole : `SAINT_ETIENNE_METROPOLE`, `ST_ETIENNE_METROPOLE`, `STE_METROPOLE` ou noms exacts configurés dans le même fichier.

Si le code ou le nom de la collectivité ne correspond pas, le document n'est pas utilisé. Ne pas élargir la recherche à toutes les collectivités d'une organisation : cela risquerait de mélanger des actes locaux qui ne s'appliquent pas au même employeur.

## Conditions d'utilisation par l'IA

Un document local ne peut être transmis à l'IA que si :

1. le scan antivirus du document et de sa version est `CLEAN` ;
2. l'extraction est `EXTRACTED` ;
3. les empreintes SHA-256 du document et de sa version correspondent à l'empreinte du fichier enregistrée avec l'index de texte extrait ;
4. le document est validé `VERIFIED_APPLICABLE` ou `VERIFIED_HISTORICAL` ;
5. sa période d'effet couvre la date des faits demandée.

Les documents non vérifiés, incomplets, hors période ou dont l'empreinte ne correspond pas restent exclus du contexte IA. Ils peuvent être signalés comme points à vérifier, mais ne fondent aucune conclusion.

## Recette développeur

- Créer une collectivité de test avec un code reconnu et une pièce PDF/DOCX propre.
- Vérifier qu'un document de la Ville n'apparaît pas pour Saint-Étienne Métropole, et inversement.
- Vérifier qu'un document d'une autre organisation reste invisible.
- Vérifier qu'un document non scanné, infecté, sans texte ou dont le hash diffère ne remonte pas.
- Vérifier qu'un document `COLLECTED_UNVERIFIED` n'est pas envoyé à l'IA.
- Vérifier qu'une pièce dont la période d'effet ne couvre pas la date des faits est exclue de l'IA.
- Vérifier qu'un document validé et applicable est bien transmis avec son extrait et sa collectivité.
