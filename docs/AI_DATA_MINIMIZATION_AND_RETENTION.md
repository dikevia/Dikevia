# Minimisation des données transmises aux fournisseurs IA et conservation

Dernière revue : 27 novembre 2026.

## État du traitement côté fournisseur IA

Les quatre points d'appel du fournisseur IA (evaluate_source_relevance, plan_legal_research, analyze_question et verify_claim_entailment) appliquent une minimisation récursive aux valeurs textuelles de leur payload juste avant sérialisation.

Le filtre reconnaît et masque actuellement :
- adresses e-mail ;
- numéros de téléphone français ;
- numéros NIR français ;
- IBAN.

La minimisation récursive couvre aussi les extraits documentaires, les titres et métadonnées, les éléments de contexte conversationnel et les données provenant des documents personnels lorsqu'un transfert a été explicitement autorisé.

Les clés des objets, valeurs numériques et booléennes sont conservées. Les références juridiques, dates de textes, dates de faits et montants ne sont pas supprimés par principe.

## Limites importantes

Ce mécanisme est une **minimisation partielle**, pas une anonymisation ni une pseudonymisation garantie.

Il ne détecte pas de façon fiable :
- les noms et prénoms ;
- les adresses postales ;
- les matricules et identifiants internes propres aux employeurs ;
- les dates de naissance lorsqu'elles ne sont pas identifiables par leur contexte ;
- les données sensibles ou les éléments indirectement identifiants dans un récit libre ;
- les combinaisons d'informations qui permettent une réidentification.

Un texte expurgé par ces expressions régulières peut donc encore contenir des données à caractère personnel. Ne pas présenter cette fonction comme une conformité RGPD ou comme une garantie d'anonymat.

## Conservation des conversations

Les messages utilisateur et les réponses sont persistés pour permettre l'historique conversationnel. Les conversations sont cloisonnées par organisation et utilisateur et peuvent être supprimées via le parcours de suppression prévu par l'application.

Un script opérateur de purge des conversations anciennes existe (scripts/purge_private_conversations.py). Il :
- exige un seuil temporel ISO-8601 explicite avec fuseau ;
- fonctionne en aperçu (dry-run) par défaut ;
- exige les deux options --execute et --confirm-delete pour supprimer ;
- utilise une connexion explicitement autorisée à contourner RLS ;
- n'est ni planifié ni appelé par l'API.

**Aucune durée de conservation ne doit être inventée dans le code.** Tant qu'une politique de conservation n'a pas été décidée et validée, la purge automatique ne doit pas être activée. La durée doit être définie par finalité et catégorie de données, puis documentée et communiquée aux personnes concernées.

## Conditions préalables avant ouverture au public

1. Définir les finalités et durées de conservation des conversations, dossiers et documents personnels.
2. Définir et tester les règles de purge des conversations, dossiers associés, fichiers et objets de stockage.
3. Vérifier les garanties contractuelles, les sous-traitants, les lieux de traitement, les transferts hors EEE et les durées de conservation du fournisseur IA.
4. Évaluer si une anonymisation ou pseudonymisation plus robuste est nécessaire avant transfert, notamment pour les noms, adresses et matricules.
5. Documenter les traitements, l'information des personnes, les droits et la procédure d'exercice de ces droits.
6. Évaluer la nécessité d'une AIPD avec le responsable de traitement / DPO.

## Périmètre de la modification du 27 novembre 2026

La modification récursive de minimisation agit uniquement sur les payloads transmis aux fournisseurs IA. Elle ne modifie pas les messages conservés dans l'historique de conversation, n'efface aucune donnée existante, ne fixe aucune durée de conservation et ne change aucun paramètre de production.
