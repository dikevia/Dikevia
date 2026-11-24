# Évaluation métier du chatbot Dikévia

## Objectif

Ce dossier contient un premier jeu de 100 questions représentatives de la fonction publique territoriale. Il sert à mesurer si le chatbot comprend la demande, sélectionne des sources juridiquement pertinentes, explique la règle et propose une suite utile sans inventer.

## Important : pas encore de vérité juridique certifiée

Le fichier `fpt_chatbot_eval_v1.json` contient les questions, l'intention à reconnaître et les critères d'échec. Il ne contient volontairement pas de réponses juridiques présentées comme certaines. Chaque réponse de référence doit être rédigée ou vérifiée par un référent juridique FPT, avec les sources officielles exactes et leur version applicable à la date du cas.

Ne pas transformer les critères d'intention en conclusions juridiques. Plusieurs questions nécessitent des précisions (statut, délibération locale, date, faits, règlement intérieur).

## Références candidates pour les réponses de référence

Les 100 cas disposent désormais d'une première cartographie de sources candidates et d'avertissements de portée. Les cas FPT-001 à FPT-030 ont fait l'objet de cartographies thématiques plus détaillées. Les cas FPT-031 à FPT-100 sont organisés par familles : carrière/rémunération, discipline, protection fonctionnelle, droits syndicaux, CST/formation spécialisée, santé-sécurité/télétravail et mobilité/fin de fonctions. Pour ces 70 cas, les références de base sont des textes-cadres officiels de la famille concernée ; elles constituent un point de départ documentaire et non une vérification article par article de chaque question. Les textes spéciaux (NBI, classement, cumul, procédures locales, seuils CST, modalités d'ASA, suppression d'emploi, rupture conventionnelle, etc.) doivent être recherchés et contrôlés au cas par cas avant de rédiger une réponse de référence.

La cartographie signale expressément les points nécessitant des vérifications supplémentaires. Le décret n° 85-397 du 3 avril 1985 sur le droit syndical est indiqué comme texte historique abrogé à compter du 1er février 2025 et ne doit pas être présenté comme droit positif. Le Code général de la fonction publique consolidé constitue le socle, à compléter par les dispositions réglementaires codifiées et les textes spéciaux en vigueur.

Le script `scripts/fpt_benchmark.py prepare-review` reporte ces références candidates et les avertissements de portée dans la grille de revue humaine. Tous les cas conservent le statut « validation juridique humaine requise ». La présence d'une source candidate ne signifie ni que l'article exact a été vérifié pour la question ni que la réponse juridique est validée.


## Pilote de recette en 15 questions

Le manifeste `fpt_pilot_15_v1.json` sélectionne 15 cas répartis sur les dix familles du jeu de 100 questions. Il fixe un protocole reproductible, avec une seule session authentifiée et un contexte neutre identique. Il ne contient pas de vérité juridique certifiée : les réponses de référence restent à établir ou valider par un référent juridique FPT. Le statut du pilote reste `NOT_EVALUATED` tant que les réponses réelles et leur revue ne sont pas consignées.

## Régressions conversationnelles

Le fichier `conversation_regression_v1.json` ajoute 20 scénarios multi-tours couvrant :
- les relances qui doivent conserver le sujet ;
- les réponses courtes à une question de clarification ;
- les nouvelles questions qui ne doivent pas hériter du sujet précédent ;
- les changements explicites de versant FPT/FPE/FPH ;
- les chaînes de plusieurs relances.

Ces scénarios sont exécutés automatiquement par `backend/tests/test_conversation_regression_benchmark.py`. Ils vérifient la construction du contexte, pas la justesse d'une réponse juridique complète. Ils ne remplacent donc pas les 100 cas FPT évalués sur les réponses produites par le moteur.

## Questions générales et situations individuelles

Une question générale sur les droits ou les règles de la FPT ne doit pas déclencher automatiquement une demande de date des faits. Le chatbot peut expliquer le droit actuellement consulté en précisant qu'il s'agit d'une information générale. Une date ou une période est demandée lorsque la formulation décrit une situation personnelle concrète ou un différend dont l'analyse dépend de la temporalité. Cette distinction fait l'objet de tests automatisés dans `backend/tests/test_case_date_clarification.py`.

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


### Exécuter le pilote de 15 questions

Le script hors ligne accepte directement le manifeste pilote, sans modifier le jeu complet de 100 questions :

```bash
python scripts/fpt_benchmark.py validate --dataset docs/quality/fpt_pilot_15_v1.json
python scripts/fpt_benchmark.py prepare-review --dataset docs/quality/fpt_pilot_15_v1.json --responses pilot_responses.json --out pilot_review.json
python scripts/fpt_benchmark.py score --dataset docs/quality/fpt_pilot_15_v1.json --responses pilot_responses.json --reviews pilot_review.json --out pilot_score.json
```

Le fichier de réponses doit contenir exactement une réponse par identifiant du manifeste. La grille générée reprend les critères et avertissements du cas. Le score du pilote porte uniquement sur ces 15 cas et ne remplace pas le benchmark de 100 questions. Le statut de validation juridique humaine reste obligatoire ; les seuils du rapport ne constituent pas une certification juridique.
