# Import des archives de jurisprudence administrative

Le corpus de Dikévia peut être enrichi à partir des archives XML mensuelles officielles du Conseil d'État, des cours administratives d'appel et des tribunaux administratifs.

## Périmètre juridique

L'importeur conserve uniquement les décisions dont le périmètre est explicitement identifié comme **FPT** ou comme règle commune aux trois versants. Les décisions exclusivement FPE, FPH, ainsi que les décisions dont le périmètre reste général ou indéterminé, sont écartées du corpus FPT.

Les archives sont téléchargées depuis l'hôte fixe `opendata.justice-administrative.fr`, en HTTPS, sans redirection, avec une limite de 100 Mo par archive. Les archives absentes (HTTP 404) sont ignorées. L'import passe par le registre `legal_source_registry` et le rôle PostgreSQL dédié `cfdt_juris_ingest`.

## Préparer une collecte

Sans `--apply`, le script fonctionne en **dry-run** : il télécharge et analyse les archives, mais n'écrit rien en base.

Exemple pour tester quelques archives CAA et TA :

```bash
python scripts/import_administrative_open_data_archives.py \
  --court CAA --court TA \
  --from-month 2022-03 --to-month 2022-06 \
  --max-archives 8 \
  --export-json /tmp/dikevia-open-data-plan.json
```

Pour parcourir toutes les périodes disponibles, la limite doit être relevée explicitement :

```bash
python scripts/import_administrative_open_data_archives.py \
  --court CE --court CAA --court TA \
  --from-month 2021-06 --to-month 2026-11 \
  --max-archives 180 \
  --export-json /tmp/dikevia-open-data-plan.json
```

## Appliquer l'import

Après examen du dry-run et de la capacité disponible sur la base de staging, fournir une URL PostgreSQL **directe** avec le rôle `cfdt_juris_ingest` dans `LEGAL_CORPUS_INGEST_DATABASE_URL`, puis ajouter `--apply`.

Le script saute par défaut les archives déjà importées avec succès. `--reimport-existing` force leur retraitement. Il ne crée ni service, ni abonnement, ni appel à un fournisseur payant. Les imports restent séquentiels, avec une pause configurable entre les archives.

Ne pas exécuter une collecte complète sur la production sans validation distincte. Vérifier d'abord le volume réel d'un petit lot sur staging, puis contrôler le nombre de décisions FPT, les rejets, les embeddings et la taille de la base avant d'élargir la période.
