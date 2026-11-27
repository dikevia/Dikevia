# Cross-encoder local de reranking — Dikévia

## Modèle retenu

Modèle candidat : `Horizon-Labs/multilingual-reranker-small`.

- Cross-encoder multilingue (40+ langues annoncées), 141 M de paramètres.
- Licence Apache-2.0.
- Export ONNX quantifié CPU : `onnx/model_quantized.onnx`, environ 268 Mo selon la fiche du modèle.
- Longueur maximale d'entraînement annoncée : 384 tokens par paire question-document.
- Le modèle est un outil de classement documentaire, pas un vérificateur juridique.

La fiche du modèle indique notamment une couverture multilingue et des résultats de benchmark génériques. Elle précise aussi que les requêtes juridiques très spécialisées et les passages techniques/longs sont moins couverts. Les résultats publiés ne démontrent donc pas sa qualité sur le droit de la fonction publique territoriale. Un benchmark Dikévia est obligatoire avant activation générale.

## Architecture intégrée

Le cross-encoder est appelé après les filtres juridiques, temporels, de périmètre et d'intégrité des citations, ainsi qu'après le reranking déterministe.

Il :
- reçoit la question contextualisée et les extraits des sources déjà admissibles ;
- score au maximum les 30 premiers candidats textuels ;
- réordonne les candidats selon leur score ;
- conserve les sources non scorées après les candidats ;
- ne supprime, n'ajoute, ne valide et ne requalifie aucune source.

Les filtres d'admissibilité et de preuve restent entièrement indépendants du score du modèle.

## Installation locale des poids

L'application ne télécharge aucun poids automatiquement et n'appelle aucun endpoint externe.

Télécharger depuis Hugging Face les deux fichiers publics du modèle dans un répertoire local :

```bash
hf download Horizon-Labs/multilingual-reranker-small \
  onnx/model_quantized.onnx tokenizer.json \
  --local-dir /opt/dikevia/models/multilingual-reranker-small
```

Dépendances Python ajoutées : `onnxruntime` et `tokenizers`. Aucun PyTorch ni service d'inférence hébergé n'est requis par ce chemin ONNX.

## Configuration

Désactivé par défaut :

```env
LEGAL_CROSS_ENCODER_ENABLED=false
LEGAL_CROSS_ENCODER_ONNX_PATH=/opt/dikevia/models/multilingual-reranker-small/onnx/model_quantized.onnx
LEGAL_CROSS_ENCODER_TOKENIZER_PATH=/opt/dikevia/models/multilingual-reranker-small/tokenizer.json
LEGAL_CROSS_ENCODER_TOP_K=30
LEGAL_CROSS_ENCODER_MAX_LENGTH=384
LEGAL_CROSS_ENCODER_THREADS=1
```

L'activation n'est possible que si les deux fichiers sont présents et si les ressources CPU/RAM du service ont été mesurées. En cas d'indisponibilité du modèle, l'orchestrateur conserve le classement déterministe et poursuit la requête.

## Précautions d'exploitation

- Ne pas activer sur le service Render Free sans mesure de mémoire réelle. Le seul fichier ONNX quantifié représente environ 268 Mo ; le processus Python, ONNX Runtime, les tenseurs et les autres traitements nécessitent de la mémoire supplémentaire.
- Ne pas télécharger le modèle à chaque démarrage ou à chaque requête.
- Ne pas activer en production sans autorisation explicite et sans déploiement contrôlé.
- Ne pas confondre score de pertinence et valeur normative, applicabilité temporelle ou force probante.
- Évaluer sur les questions Dikévia annotées par un spécialiste FPT : Recall@k, nDCG@k, MRR, latence, mémoire et stabilité des sources indispensables.

## État

Le code et les dépendances sont intégrés sur `main`. Les poids du modèle ne sont pas inclus dans le dépôt. Le réglage reste désactivé tant que le modèle n'est pas provisionné localement et que les ressources de l'environnement cible ne sont pas validées.
