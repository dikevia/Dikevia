# Benchmark juridique Dikévia — 100 questions FPT

## But
Mesurer la qualité réelle des réponses de Dikévia sur le jeu de référence FPT-001–FPT-100. Ce benchmark est distinct des tests unitaires et de l'audit juridique du corrigé.

## Règle de sécurité
Le benchmark doit rester sans dépense non autorisée. Le script `scripts/fpt_benchmark.py` est strictement hors ligne : il ne contacte ni l'API Dikévia, ni fournisseur IA, ni Légifrance/PISTE, ni Render, ni Neon.

**Ne pas exécuter 100 requêtes sur l'API de production avant vérification écrite du coût et des quotas.** Le endpoint de chat peut déclencher l'orchestrateur, un fournisseur IA et des connecteurs juridiques.

## Fichiers attendus
- `docs/quality/fpt_chatbot_eval_v1.json` : le jeu canonique de 100 cas FPT. Il contient les questions, intentions, contrôles attendus et modes d'échec ; il ne contient pas de réponses juridiques certifiées.
- `benchmark/dikevia_responses.json` : une réponse réelle par ID, avec au minimum `id`, `answer`, `sources` et `verification_status`. Exporter depuis un environnement de test sans secrets ni données personnelles.
- `benchmark/review_100.json` : grille remplie par les évaluateurs.
- `benchmark/results.json` : agrégat calculé.

## Procédure
1. Valider le jeu de référence :
   `python scripts/fpt_benchmark.py validate --dataset docs/quality/fpt_chatbot_eval_v1.json`
2. Collecter les 100 réponses via un environnement dont le coût est confirmé nul. Ne pas simuler les réponses.
3. Préparer la grille :
   `python scripts/fpt_benchmark.py prepare-review --dataset docs/quality/fpt_chatbot_eval_v1.json --responses benchmark/dikevia_responses.json --out benchmark/review_100.json`
4. Pour le jeu canonique, évaluer les cinq dimensions déclarées dans le JSON (0 à 2) : compréhension de la question, couverture de la recherche, pertinence des sources, exactitude juridique et fidélité de la synthèse. Renseigner également `question_relevance` et `source_support` (booléens) pour appliquer les seuils du release gate. Le script conserve la compatibilité avec l'ancien format à sept dimensions.
5. Attribuer une sévérité par question : `conforme`, `mineur`, `majeur` ou `critique`. Documenter les constats, la correction attendue, les sources officielles et la date de contrôle.
6. Calculer :
   `python scripts/fpt_benchmark.py score --dataset docs/quality/fpt_chatbot_eval_v1.json --responses benchmark/dikevia_responses.json --reviews benchmark/review_100.json --out benchmark/results.json`

## Règles d'annotation
- 0 = faux, absent, non sourcé ou dangereux ; 1 = partiellement correct / incomplet ; 2 = correct, à jour, suffisamment complet et correctement sourcé.
- Une erreur critique (mauvais droit applicable, règle inventée, citation inexistante, confusion FPT/FPE/FPH susceptible d'induire l'agent en erreur) doit être marquée `critique`, même si la réponse obtient des points sur d'autres dimensions.
- Une réponse qui s'abstient faute de source ne doit pas être pénalisée comme une hallucination ; évaluer si l'abstention était justifiée.
- Ne jamais confondre score de tests logiciels et fiabilité juridique.
- Le résultat global est déclaré complet uniquement après évaluation des 100 réponses. Le `release_gate` doit en outre passer les seuils du JSON (moyenne, pertinence, appui des sources, absence d'échec critique). Aucun score partiel ne doit être présenté comme le taux de fiabilité global.

## État initial
Le référentiel FPT-001–FPT-100 a été transmis par le propriétaire le 19 novembre 2026. Les réponses réelles de Dikévia ne sont pas encore capturées. Les réponses de référence juridiques ne sont pas certifiées. Les appels live sont suspendus tant que leur coût n'est pas confirmé et que l'environnement de test n'est pas isolé.
