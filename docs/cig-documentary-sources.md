# CIG Petite Couronne – source registry for Dikévia

## Purpose
The CIG is a specialist documentary publisher for territorial civil-service HR and
statutory matters. Dikévia catalogues resources as secondary explanatory sources,
not as binding law.

## Current implementation
- `backend/app/cig_sources.py`: source families, access classification,
  URL allowlist and fail-closed permission gate for content ingestion.
- `backend/app/cig_public_resources.py`: curated public discovery metadata and
  topic tags. Metadata only; no PDF, audio, transcript or protected content copied.
- Unit tests verify source identifiers, topic discovery and rights safeguards.

## Mandatory legal and data safeguards
1. Public visibility is not a blanket licence for commercial reproduction,
   scraping, model training or persistent indexing.
2. Authenticated access, including an individual or collective account, is not
   permission to copy content into Dikévia or expose it across tenants.
3. Any content ingestion requires written permission covering the exact
   materials, commercial SaaS use, storage, indexing, excerpts, derived metadata,
   model processing, retention, updates and deletion.
4. Preserve publisher, title, canonical URL, publication/update date and
   territorial scope. Distinguish CIG editorial analysis from official texts.
5. Resolve and verify the primary legal sources cited by a CIG document before
   presenting a legal conclusion. A CIG publication is never itself a binding
   legal authority.
6. Keep CIG-specific local or affiliated-authority arrangements distinct from
   general FPT rules. Never imply that a 92/93/94 local rule applies nationally.
7. No login automation, credential storage, paywall circumvention or bulk
   authenticated crawling.

## Next steps
- Maintain a dated inventory of public resources and their exact public landing
  pages.
- Contact CIG publications team for a written commercial reuse/licensing
  proposal for BIP, IAJ, public PDFs and podcasts.
- Only after permission: implement a source-specific importer with provenance,
  versioning, document hashes, update checks and tenant-safe retrieval.
