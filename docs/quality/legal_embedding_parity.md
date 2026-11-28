# Mesure de parité des embeddings navigateur / FastEmbed

## Objet

Ce protocole compare, sur les mêmes textes, les vecteurs générés par le worker navigateur Transformers.js et par FastEmbed côté Python. Il ne contacte aucune base PostgreSQL et n'active pas la recherche vectorielle.

La comparaison vérifie les identifiants et le hash des textes, puis calcule pour chaque entrée :
- la similarité cosinus ;
- l'erreur absolue moyenne ;
- l'erreur absolue maximale.

Le générateur FastEmbed reprend le contrat de requête du navigateur : troncature à 5 000 caractères, segmentation de 500 caractères avec chevauchement de 60 caractères, mean pooling sans normalisation par segment, moyenne des vecteurs de segments puis normalisation finale.

## Procédure locale

Depuis la racine du dépôt :

1. Installer les dépendances optionnelles :
   ```bash
   python -m pip install -r backend/requirements-embeddings.txt
   ```

2. Générer les vecteurs de référence FastEmbed :
   ```bash
   python scripts/compare_legal_embedding_parity.py generate-fastembed \
     --input docs/quality/legal_embedding_parity_inputs.example.json \
     --output /tmp/dikevia-fastembed-vectors.json
   ```

3. Ouvrir `scripts/legal_embedding_parity.html` dans un navigateur connecté à Internet. Sélectionner le fichier JSON FastEmbed, puis lancer le calcul navigateur. Le modèle Transformers.js est téléchargé depuis le dépôt public Hugging Face via jsDelivr lors de la première exécution. Le navigateur traite les textes localement ; ils ne sont pas envoyés à une API Dikévia.

4. Télécharger l'export navigateur, puis comparer :
   ```bash
   python scripts/compare_legal_embedding_parity.py compare \
     --browser browser-legal-embeddings.json \
     --fastembed /tmp/dikevia-fastembed-vectors.json \
     --output /tmp/dikevia-embedding-parity-report.json
   ```

Les fichiers d'export peuvent contenir des textes de questions et des vecteurs ; les conserver localement et ne pas les committer.

## Interprétation

- Une similarité cosinus proche de 1 indique que les deux vecteurs ont une direction proche ; cela ne prouve pas que le modèle retrouve les bons textes juridiques.
- Une divergence doit être investiguée par entrée, notamment en vérifiant la version du modèle, les poids ONNX, le tokenizer, le pooling et la troncature.
- Aucun seuil de tolérance n'est déclaré ici comme validé. Il faut d'abord observer les mesures réelles et leur stabilité.
- Cette mesure technique ne remplace pas l'évaluation de la pertinence du retrieval sur des questions et documents juridiques représentatifs.

## Sécurité d'activation

Le code active désormais la recherche vectorielle par défaut (`VECTOR_SEARCH_ENABLED=true`), mais un paramètre d'environnement Render peut remplacer cette valeur. Le passage de ce protocole n'est pas encore attesté : la parité numérique des embeddings navigateur/FastEmbed et la pertinence du retrieval doivent être mesurées avant de considérer pgvector comme validé en production. La recherche vectorielle ne s'exécute que si le frontend reçoit le feature flag actif et transmet un vecteur de 384 dimensions. Ne pas modifier les paramètres d'environnement Render ni déployer sans autorisation explicite. Prévoir une procédure de retour arrière en désactivant le feature flag.


## Benchmark de retrieval vectoriel staging (100 questions FPT)

Le smoke test vectoriel a été étendu pour utiliser les 100 questions du jeu
`docs/quality/fpt_chatbot_eval_v1.json`. Il interroge uniquement les fragments
`FULL_TEXT` portant un embedding 384 dimensions compatible et dont la période
de validité couvre la date de l'audit. Pour chaque question, il exporte les cinq
premiers résultats, leur similarité cosinus et un extrait de texte pour revue.

Depuis la racine du dépôt, après installation de
`backend/requirements-embeddings.txt` et configuration locale de
`LEGAL_CORPUS_INGEST_DATABASE_URL` avec le rôle dédié `cfdt_juris_ingest` :

```bash
python scripts/audit_staging_vector_retrieval.py --limit 100 --top-k 5 > /tmp/dikevia-vector-audit.json
```

Le script vérifie le marqueur de la branche Neon staging et exécute toutes les
requêtes dans une transaction PostgreSQL `READ ONLY`. Il n'écrit aucune donnée.
Le rapport inclut les sources candidates du jeu d'évaluation uniquement comme
pistes de revue humaine : elles ne sont pas validées juridiquement et ne servent
pas de vérité terrain automatisée.

Ce benchmark mesure la disponibilité et le classement vectoriel structurel. Il
ne certifie ni la pertinence sémantique, ni l'applicabilité FPT, ni la qualité du
retrieval hybride du backend, du reranker ou des réponses finales. Une revue
juridique humaine des résultats est indispensable avant de définir des scores
de rappel ou des seuils de qualité.
