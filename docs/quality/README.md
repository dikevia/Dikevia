# Évaluation métier du chatbot Dikévia

## Objectif

Ce dossier contient un premier jeu de 100 questions représentatives de la fonction publique territoriale. Il sert à mesurer si le chatbot comprend la demande, sélectionne des sources juridiquement pertinentes, explique la règle et propose une suite utile sans inventer.

## Important : pas encore de vérité juridique certifiée

Le fichier `fpt_chatbot_eval_v1.json` contient les questions, l'intention à reconnaître et les critères d'échec. Il ne contient volontairement pas de réponses juridiques présentées comme certaines. Chaque réponse de référence doit être rédigée ou vérifiée par un référent juridique FPT, avec les sources officielles exactes et leur version applicable à la date du cas.

Ne pas transformer les critères d'intention en conclusions juridiques. Plusieurs questions nécessitent des précisions (statut, délibération locale, date, faits, règlement intérieur).

## Protocole de recette

1. Fixer une version du backend, du prompt, du modèle et du corpus juridique.
2. Exécuter les 100 questions avec un contexte utilisateur neutre et identique, sans données personnelles réelles.
3. Conserver pour chaque exécution : question, réponse, sources récupérées, sources citées, dates/versions, latence et version logicielle.
4. Faire établir une réponse de référence et une liste de sources officielles par un référent juridique pour chaque cas.
5. Faire noter indépendamment chaque réponse par deux évaluateurs sur les cinq dimensions du JSON (0 à 2 chacune).
6. Arbitrer les désaccords et documenter chaque échec critique.
7. Comparer la version candidate à la version de référence, question par question. Toute régression critique bloque la livraison.
8. Rejouer la suite après chaque modification du retrieval, prompt, modèle, corpus ou orchestration.

## Règles de notation

- **Pertinence de la question** : répond-il exactement à la demande, sans digression juridique inutile ?
- **Pertinence des sources** : les sources citées soutiennent-elles directement les affirmations et sont-elles applicables ?
- **Exactitude juridique** : statut, conditions, exceptions, temporalité et portée sont-ils correctement traités ?
- **Utilité pratique** : l'agent comprend-il les conséquences et les démarches possibles ?
- **Calibration** : le chatbot demande-t-il les précisions nécessaires et s'abstient-il quand les sources sont insuffisantes ?

Chaque dimension est notée 0 (échec), 1 (partiel) ou 2 (satisfaisant). Score maximal : 10.

## Échecs critiques

Un seul des cas suivants bloque la recette, même si le score moyen est bon :
- référence légale inventée ou citation qui ne soutient pas l'affirmation ;
- source hors sujet utilisée comme fondement d'une conclusion ;
- règle nationale/localement applicable confondue avec une règle locale ;
- délai, droit, obligation ou sanction inventé ;
- certitude affichée alors qu'une information déterminante manque ;
- exposition d'une donnée personnelle ou sensible dans les jeux de test.

## Seuils de lancement proposés

Les seuils du JSON sont des objectifs de recette, pas des performances acquises. Ils doivent être mesurés sur des réponses effectivement exécutées et évaluées. Aucun déploiement de production ne doit être déduit de la seule présence du jeu de tests ou du passage des tests structurels.

## Familles couvertes

10 familles de 10 questions : rémunération/temps de travail, congés/absences, maladie/protection sociale, carrière/rémunération, discipline/droits de la défense, protection fonctionnelle, droits syndicaux, CST/formation spécialisée, télétravail/santé/sécurité, mobilité/fin de fonctions.
