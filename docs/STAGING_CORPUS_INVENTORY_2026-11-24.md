# État du corpus de recette — 24 novembre 2026

Contrôle SQL en lecture seule sur la branche Neon dédiée `dikevia-corpus-ingestion-test`
(`br-billowing-haze-bd5a1cns`), avec le marqueur de sécurité attendu.

Inventaire constaté :
- CGFP snapshot : 4 242 documents, 4 253 fragments.
- Service-Public : 199 documents, 1 226 fragments.
- Ressources institutionnelles : 18 documents, 161 fragments.
- Total : 4 459 documents, 5 640 fragments.
- Embeddings 384 dimensions, modèle `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` : 5 640 / 5 640 fragments.

Les statuts restent volontairement `IMPORTED_UNVERIFIED` / `UNKNOWN` : l'import et les embeddings ne certifient ni l'applicabilité temporelle ni la valeur normative. Ce relevé ne constitue pas une validation juridique.

Le contrôle de pertinence vectorielle et l'audit d'admissibilité des ressources non normatives doivent encore être exécutés. Aucun enregistrement n'est écrit en production par ce contrôle.
