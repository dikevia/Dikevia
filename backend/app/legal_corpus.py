"""Stockage, historisation et recherche du corpus juridique national JURIS.

Les documents sont des sources publiques communes à tous les tenants. Les imports
conservent les identifiants de la source, les dates, le statut et le texte réellement
récupéré. Les champs absents restent NULL/UNKNOWN : aucune métadonnée n'est inventée.
"""
from __future__ import annotations

import hashlib
import json
import html
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

CHUNK_SIZE = 4200
CHUNK_OVERLAP = 300


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clean_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:p|div|li|h[1-6]|tr)\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t\u00a0]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n\n", value)
    return value.strip()


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary > start:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def temporal_status(valid_from: date | None, valid_to: date | None, requested: date,
                    document_kind: str | None = None, signature_date: date | None = None,
                    raw_payload: dict | None = None, version_status: str | None = None,
                    source_version_id: str | None = None) -> str:
    if document_kind == "ADMIN_CASELAW":
        if not signature_date:
            return "TEMPORAL_SCOPE_INCOMPLETE"
        return "DECISION_AVAILABLE_BY_REQUESTED_DATE" if signature_date <= requested else "DECISION_POSTERIOR_TO_REQUESTED_DATE"
    if document_kind in {"CODE", "LAW", "ORDONNANCE", "DECREE", "ORDER"}:
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except (ValueError, TypeError):
                raw_payload = {}
        # An explicit repeal status always excludes a text from current-law answers.
        # Historical applicability still requires an independently verified version.
        if version_status in {"REPEALED", "NOT_IN_FORCE"}:
            return "NO_LONGER_IN_FORCE"
        if (raw_payload or {}).get("temporal_scope") == "CURRENT_CODE_SNAPSHOT":
            return "TEMPORAL_SCOPE_INCOMPLETE"
        imported_for_date = (raw_payload or {}).get("requested_date") == requested.isoformat()
        if imported_for_date and version_status == "IN_FORCE":
            return "IN_FORCE_ON_REQUESTED_DATE"
        if imported_for_date and version_status in {"REPEALED", "NOT_IN_FORCE"}:
            return "NO_LONGER_IN_FORCE"
        # A date-filtered LODA search followed by a consultation returning the
        # same official text ID proves which version was retrieved for that date.
        # It does not prove the instrument's separate legal status when metadata
        # omits that status; preserve this weaker, explicit temporal state.
        if (
            imported_for_date
            and version_status == "UNKNOWN"
            and (raw_payload or {}).get("date_filter") == "DATE_VERSION"
            and str((raw_payload or {}).get("matching_consulted_id") or "").strip().casefold()
                == str(source_version_id or "").strip().casefold()
            and bool(str(source_version_id or "").strip())
        ):
            return "VERSION_RETRIEVED_AT_REQUESTED_DATE"
    if valid_from and requested < valid_from:
        return "NOT_YET_EFFECTIVE"
    if valid_to and requested > valid_to:
        return "NO_LONGER_IN_FORCE"
    if valid_from and valid_to:
        # For normative instruments, a bounded interval alone is not enough:
        # require an independently verified IN_FORCE version status before
        # presenting the text as applicable on the requested date.
        if document_kind in {"CODE", "LAW", "ORDONNANCE", "DECREE", "ORDER"}:
            if version_status == "IN_FORCE":
                return "IN_FORCE_ON_REQUESTED_DATE"
            return "TEMPORAL_SCOPE_INCOMPLETE"
        return "IN_FORCE_ON_REQUESTED_DATE"
    return "TEMPORAL_SCOPE_INCOMPLETE"


def safe_official_url(value: str | None) -> str | None:
    """Keep HTTPS links only for explicitly trusted public legal/institutional domains."""
    if not value:
        return None
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    exact_hosts = {
        "www.legifrance.gouv.fr", "legifrance.gouv.fr",
        "opendata.justice-administrative.fr",
        "service-public.gouv.fr", "www.service-public.gouv.fr",
        "lecomarquage.service-public.gouv.fr",
        "data.gouv.fr", "www.data.gouv.fr",
        "cnfpt.fr", "www.cnfpt.fr", "wikiterritorial.cnfpt.fr",
        "cig929394.fr", "www.cig929394.fr",
        "cigversailles.fr", "www.cigversailles.fr",
        # Exact HTTPS hosts of the explicitly selected and approved guidance corpus.
        "cdg35.bzh", "www.cdg35.bzh",
        "uffa.cfdt.fr",
        "interco.cfdt.fr",
        "cfdt-interco31.fr", "www.cfdt-interco31.fr",
        "cfdtinterco35.fr", "www.cfdtinterco35.fr",
        "cgtservicespublics.fr", "www.cgtservicespublics.fr",
        "cgtetat.fr", "www.cgtetat.fr",
        "sante.cgt.fr", "www.sante.cgt.fr",
        "fo-fonctionnaires.fr", "www.fo-fonctionnaires.fr",
        "cftc.fr", "www.cftc.fr", "ledecodeur.cftc.fr",
        "unsa-fp.org", "www.unsa-fp.org",
        "fonctionpublique.solidaires.org",
    }
    is_cdg_domain = bool(re.fullmatch(r"(?:www\.)?cdg\d{2,3}\.fr", host))
    is_gouv_domain = host == "gouv.fr" or host.endswith(".gouv.fr")
    if parsed.scheme == "https" and (host in exact_hosts or is_cdg_domain or is_gouv_domain):
        if parsed.username or parsed.password or parsed.port:
            return None
        return value[:1500]
    return None


def resolve_legal_source_key(item: dict[str, Any]) -> str | None:
    """Resolve an imported document to its reviewed source-registry entry."""
    explicit = item.get("source_key")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    source_type = str(item.get("source_type") or "").strip().upper()
    metadata = item.get("raw_metadata") if isinstance(item.get("raw_metadata"), dict) else {}
    source_id = str(metadata.get("source_id") or "").strip().lower()
    if source_type in {"LEGIFRANCE_LEGI", "LEGIFRANCE_LODA", "LEGIFRANCE_CETAT", "LEGIFRANCE_JORF"}:
        return "LEGIFRANCE_PISTE"
    if source_type == "CGFP_SNAPSHOT":
        return "CGFP_SNAPSHOT"
    if source_type == "SERVICE_PUBLIC_PART":
        return "SERVICE_PUBLIC_DATA"
    if source_type == "DILA_CIRCULAIRES":
        return "DILA_CIRCULAIRES"
    if source_type == "OTHER_OFFICIAL" and metadata.get("import_method") == "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML":
        return "JUSTICE_ADMIN_OPEN_DATA"
    institutional_sources = {
        "cdg-35": "CDG35",
        "cdg-59": "CDG59",
        "cdg-69": "CDG69",
        "cig-petite-couronne": "CIG_PETITE_COURONNE",
        "cnfpt": "CNFPT",
        "dgafp": "DGAFP",
        "info-gouv": "INFO_GOUV",
        "dgcl": "DGCL",
        "cdg-44": "CDG44",
        "cig-grande-couronne": "CIG_GRANDE_COURONNE",
        "cdg-departements": "CDG_DEPARTMENTS",
        "wikiterritorial-cnfpt": "CNFPT_WIKITERRITORIAL",
        "cfdt-interco": "CFDT_INTERCO",
        "cfdt-fonctions-publiques": "CFDT_UFFA",
        "cftc-fonction-publique": "CFTC_FONCTION_PUBLIQUE",
        "cgt-fonction-publique": "CGT_FONCTION_PUBLIQUE",
        "fo-fonction-publique": "FO_FONCTION_PUBLIQUE",
        "solidaires-fonction-publique": "SOLIDAIRES_FONCTION_PUBLIQUE",
        "unsa-fonction-publique": "UNSA_FONCTION_PUBLIQUE",
    }
    return institutional_sources.get(source_id)


async def upsert_legal_document(conn, item: dict[str, Any]) -> dict[str, Any]:
    required = ("source_type", "source_id", "title", "document_kind")
    if any(not isinstance(item.get(k), str) or not item[k].strip() for k in required):
        raise ValueError("Métadonnées minimales de source juridique manquantes.")
    text = clean_text(str(item.get("full_text") or ""))
    text_hash = sha256_text(text) if text else None
    url = safe_official_url(item.get("official_url"))
    metadata = item.get("raw_metadata") if isinstance(item.get("raw_metadata"), dict) else {}
    source_key = resolve_legal_source_key(item)
    if not source_key:
        raise ValueError("Source juridique absente du registre de provenance : import refusé.")
    source_policy = await conn.fetchrow("""
      SELECT metadata_ingestion_allowed,full_text_ingestion_allowed,verification_status
      FROM legal_source_registry WHERE source_key=$1
    """, source_key)
    if not source_policy or not source_policy["metadata_ingestion_allowed"]:
        raise ValueError("La politique du registre interdit l'import des métadonnées de cette source.")
    if text and not source_policy["full_text_ingestion_allowed"]:
        raise ValueError("Le texte intégral de cette source n'est pas autorisé à l'ingestion automatique.")
    if item.get("source_type") == "INSTITUTIONAL_GUIDANCE":
        approved = {"REUSE_APPROVED", "APPROVED"}
        if (
            metadata.get("source_registry_status") not in approved
            or metadata.get("reuse_status") not in approved
        ):
            raise ValueError(
                "Import de contenu institutionnel refusé : la source et la ressource individuelle doivent être explicitement approuvées."
            )
    doc = await conn.fetchrow("""
      INSERT INTO legal_documents(source_type,source_id,source_key,title,document_kind,official_number,jurisdiction,publisher,
        official_url,signature_date,publication_date,status,source_status,raw_metadata,content_sha256,last_seen_at)
      VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,$15,now())
      ON CONFLICT(source_type,source_id) DO UPDATE SET source_key=COALESCE(EXCLUDED.source_key,legal_documents.source_key),
        title=EXCLUDED.title,
        document_kind=EXCLUDED.document_kind,official_number=COALESCE(EXCLUDED.official_number,legal_documents.official_number),
        jurisdiction=COALESCE(EXCLUDED.jurisdiction,legal_documents.jurisdiction),
        publisher=COALESCE(EXCLUDED.publisher,legal_documents.publisher),
        official_url=COALESCE(EXCLUDED.official_url,legal_documents.official_url),
        signature_date=COALESCE(EXCLUDED.signature_date,legal_documents.signature_date),
        publication_date=COALESCE(EXCLUDED.publication_date,legal_documents.publication_date),
        status=CASE WHEN EXCLUDED.status='UNKNOWN' THEN legal_documents.status ELSE EXCLUDED.status END,
        source_status=EXCLUDED.source_status,raw_metadata=legal_documents.raw_metadata || EXCLUDED.raw_metadata,
        content_sha256=COALESCE(EXCLUDED.content_sha256,legal_documents.content_sha256),last_seen_at=now()
      RETURNING id
    """, item["source_type"], item["source_id"], resolve_legal_source_key(item), item["title"][:1000], item["document_kind"],
        item.get("official_number"), item.get("jurisdiction"), item.get("publisher"), url,
        item.get("signature_date"), item.get("publication_date"), item.get("status", "UNKNOWN"),
        item.get("source_status", "METADATA_ONLY"), __import__("json").dumps(metadata, ensure_ascii=False), text_hash)
    version_key = str(item.get("version_key") or (text_hash or "metadata-" + str(item.get("source_id"))))[:180]
    version = await conn.fetchrow("""
      INSERT INTO legal_document_versions(document_id,version_key,source_version_id,valid_from,valid_to,
        version_status,full_text,text_sha256,raw_payload)
      VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
      ON CONFLICT(document_id,version_key) DO UPDATE SET
        full_text=CASE WHEN EXCLUDED.full_text<>'' THEN EXCLUDED.full_text ELSE legal_document_versions.full_text END,
        source_version_id=COALESCE(EXCLUDED.source_version_id,legal_document_versions.source_version_id),
        text_sha256=COALESCE(EXCLUDED.text_sha256,legal_document_versions.text_sha256),
        valid_from=COALESCE(EXCLUDED.valid_from,legal_document_versions.valid_from),
        valid_to=COALESCE(EXCLUDED.valid_to,legal_document_versions.valid_to),
        version_status=CASE WHEN EXCLUDED.version_status='UNKNOWN' THEN legal_document_versions.version_status ELSE EXCLUDED.version_status END,
        raw_payload=legal_document_versions.raw_payload || EXCLUDED.raw_payload,retrieved_at=now()
      RETURNING id
    """, doc["id"], version_key, item.get("source_version_id"), item.get("valid_from"), item.get("valid_to"),
        item.get("version_status", "UNKNOWN"), text, text_hash,
        __import__("json").dumps(item.get("raw_version_payload") or {}, ensure_ascii=False))
    await conn.execute("DELETE FROM legal_chunks WHERE version_id=$1", version["id"])
    if text:
        chunks = split_text(text)
        for ordinal, chunk in enumerate(chunks):
            await conn.execute("INSERT INTO legal_chunks(version_id,ordinal,anchor,content_kind,content) VALUES($1,$2,$3,'FULL_TEXT',$4)",
                version["id"], ordinal, item.get("anchor"), chunk)
    else:
        metadata_text = " — ".join(str(x) for x in (item.get("title"), item.get("official_number"), item.get("publisher")) if x)
        if metadata_text:
            await conn.execute("INSERT INTO legal_chunks(version_id,ordinal,anchor,content_kind,content) VALUES($1,0,$2,'METADATA',$3)",
                version["id"], item.get("anchor"), metadata_text[:4000])
    return {"document_id": str(doc["id"]), "version_id": str(version["id"]), "chunks": len(split_text(text)) if text else (1 if item.get("title") else 0),
            "text_imported": bool(text)}


# Développements lexicaux prudents : uniquement des équivalences documentées
# ou des formulations courantes du même mécanisme. Les notions voisines mais
# juridiquement distinctes ne sont volontairement pas fusionnées.
_LEGAL_QUERY_EXPANSIONS = {
    "ihts": ("indemnités horaires pour travaux supplémentaires", "heures supplémentaires"),
    "indemnités horaires pour travaux supplémentaires": ("IHTS", "heures supplémentaires"),
    "heures supplémentaires": ("IHTS", "indemnités horaires pour travaux supplémentaires"),
    # Colloquial formulations used by agents must retrieve the same legal
    # mechanism without treating recovery and payment as legally interchangeable.
    "récupérerai": ("repos compensateur", "récupération des heures supplémentaires", "indemnisation des heures supplémentaires"),
    "récupérer": ("repos compensateur", "récupération des heures supplémentaires", "indemnisation des heures supplémentaires"),
    "récupération": ("repos compensateur", "compensation des heures supplémentaires", "indemnités horaires pour travaux supplémentaires"),
    "payées": ("indemnisation des heures supplémentaires", "versement des IHTS", "repos compensateur"),
    "compte épargne temps": ("CET", "compte épargne-temps"),
    "cet": ("compte épargne temps", "compte épargne-temps"),
    "congé maladie": ("congé de maladie", "maladie ordinaire", "CMO"),
    "maladie ordinaire": ("congé de maladie", "CMO"),
    "accompagné d'un syndicat": (
        "convocation agent territorial entretien hiérarchique assistance représentant syndical",
        "procédure disciplinaire fonction publique territoriale droits de la défense défenseur de son choix",
        "entretien hiérarchique ordinaire accompagnement syndical conditions applicables",
    ),
    "accompagné d’un syndicat": (
        "convocation agent territorial entretien hiérarchique assistance représentant syndical",
        "procédure disciplinaire fonction publique territoriale droits de la défense défenseur de son choix",
        "entretien hiérarchique ordinaire accompagnement syndical conditions applicables",
    ),
    "accompagné par un syndicat": (
        "convocation agent territorial entretien hiérarchique assistance représentant syndical",
        "procédure disciplinaire fonction publique territoriale droits de la défense défenseur de son choix",
        "entretien hiérarchique ordinaire accompagnement syndical conditions applicables",
    ),
    "assistance syndicale lors d'une convocation": (
        "convocation agent territorial entretien hiérarchique assistance représentant syndical",
        "procédure disciplinaire fonction publique territoriale droits de la défense défenseur de son choix",
    ),
    "protection fonctionnelle": ("protection juridique de l'agent", "assistance de la collectivité"),
    "harcèlement moral": ("agissements répétés", "dégradation des conditions de travail"),
    "temps de travail": ("durée du travail", "cycle de travail", "décompte du temps de travail"),
    "astreinte": ("période d'astreinte", "intervention pendant astreinte"),
}


def _normalize_legal_phrase(value: str) -> str:
    import unicodedata
    folded = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"\s+", " ", "".join(ch for ch in folded if not unicodedata.combining(ch))).strip()


def _referential_query_expansions() -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Load only lexical triggers and legal wording; reference leads remain non-authoritative."""
    try:
        with ( __import__("pathlib").Path(__file__).with_name("fp_lexical_referentiel.json")).open(encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, ValueError, TypeError):
        return []
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    expansions = []
    if not isinstance(entries, list):
        return []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        triggers = entry.get("triggers")
        terms = entry.get("legal_terms")
        if not isinstance(triggers, list) or not isinstance(terms, list):
            continue
        clean_triggers = tuple(x.strip() for x in triggers if isinstance(x, str) and x.strip())
        clean_terms = tuple(x.strip() for x in terms if isinstance(x, str) and x.strip())
        if clean_triggers and clean_terms:
            expansions.append((clean_triggers, clean_terms))
    return expansions


_REFERENTIAL_QUERY_EXPANSIONS = _referential_query_expansions()


def expand_legal_query(query: str, max_variants: int = 6) -> list[str]:
    """Expand user wording with curated synonyms while keeping the original query first."""
    if not isinstance(query, str) or not query.strip() or not 1 <= max_variants <= 20:
        raise ValueError("La requête doit être non vide et max_variants compris entre 1 et 20.")
    original = re.sub(r"\s+", " ", query).strip()
    normalized = _normalize_legal_phrase(original)
    variants = [original]
    seen = {normalized}
    if max_variants == 1:
        return variants

    def append_terms(terms: tuple[str, ...]) -> bool:
        for term in terms:
            candidate = _normalize_legal_phrase(term)
            if candidate and candidate not in seen:
                variants.append(term)
                seen.add(candidate)
                if len(variants) >= max_variants:
                    return True
        return False

    # Explicit, reviewed phrase mappings retain precedence.
    for phrase, expansions in _LEGAL_QUERY_EXPANSIONS.items():
        key = _normalize_legal_phrase(phrase)
        if re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", normalized):
            if append_terms(expansions):
                return variants

    # The JSON referential is used strictly for query recall. Its historical
    # article/decree leads are deliberately never injected as legal evidence.
    for triggers, legal_terms in _REFERENTIAL_QUERY_EXPANSIONS:
        if any(
            re.search(r"(?<!\w)" + re.escape(_normalize_legal_phrase(trigger)) + r"(?!\w)", normalized)
            for trigger in triggers
        ):
            if append_terms(legal_terms):
                return variants
    return variants


def corpus_version_citation_id(source_id: object, version_id: object = None) -> str | None:
    """Return a unique evidence key for one stored legal-text version."""
    stable_source_id = str(source_id or "").strip()
    if not stable_source_id:
        return None
    stable_version_id = str(version_id or "").strip()
    if stable_version_id:
        # The UUID identifies the exact stored version; keep the official ID
        # separately for human-readable legal references and provenance.
        return f"CORPUS_VERSION_{stable_version_id}"
    return stable_source_id


def interleave_legal_corpus_results(results_by_query: list[list[dict]], limit: int = 12) -> list[dict]:
    """Keep results from each independent legal sub-question before de-duplication."""
    if not 1 <= limit <= 30:
        raise ValueError("La limite de résultats du corpus doit être comprise entre 1 et 30.")
    selected: list[dict] = []
    seen: set[str] = set()
    max_depth = max((len(items) for items in results_by_query), default=0)
    for depth in range(max_depth):
        for items in results_by_query:
            if depth >= len(items):
                continue
            item = items[depth]
            # A legal document can have several independently stored versions.
            # De-duplicate repeated retrievals of the same version, not distinct
            # versions sharing the document's stable official source_id.
            version_id = item.get("version_id")
            identifier = (
                f"version:{version_id}"
                if isinstance(version_id, str) and version_id
                else f"source:{item.get('source_id')}"
                if isinstance(item.get("source_id"), str) and item.get("source_id")
                else None
            )
            if identifier is None or identifier in seen:
                continue
            seen.add(identifier)
            selected.append(item)
            if len(selected) >= limit:
                return selected
    return selected


def select_multi_source_chunks(results_by_query: list[list[dict]], limit: int = 12) -> list[dict]:
    """Select multi-axis corpus results without inventing or recomputing relevance scores.

    Each inner list is the ranked output of one independent legal research query.
    Round-robin interleaving prevents the first query from crowding out complementary
    legal sources. Existing temporal, authority and public-service guards remain
    responsible for deciding whether a retrieved source may support an answer.
    """
    return interleave_legal_corpus_results(results_by_query, limit=limit)


async def search_legal_corpus(
    conn, query: str, requested_date: date, limit: int = 12,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    if not isinstance(query, str) or len(query.strip()) < 2 or len(query) > 500:
        raise ValueError("La recherche documentaire doit contenir entre 2 et 500 caractères.")
    if not 1 <= limit <= 30:
        raise ValueError("La limite doit être comprise entre 1 et 30.")
    vector_literal = None
    if query_embedding is not None:
        import math
        if len(query_embedding) != 384 or any(not math.isfinite(float(value)) for value in query_embedding):
            raise ValueError("Le vecteur de requête doit contenir exactement 384 valeurs finies.")
        norm = math.sqrt(sum(float(value) ** 2 for value in query_embedding))
        if norm <= 0:
            raise ValueError("Le vecteur de requête ne peut pas être nul.")
        vector_literal = "[" + ",".join(f"{float(value) / norm:.8f}" for value in query_embedding) + "]"

    variants = expand_legal_query(query.strip())
    # The original wording keeps twice the lexical weight; curated variants widen recall.
    expansion_expression = " OR ".join(variants[1:])
    rows = await conn.fetch("""
      WITH search_terms AS (
        SELECT websearch_to_tsquery('french',$1) AS original_query,
               websearch_to_tsquery('french',$2) AS expansion_query
      ), lexical_candidates AS (
        SELECT c.id chunk_id,c.version_id,c.ordinal,
          (2.0 * ts_rank_cd(c.search_vector,st.original_query)
             + ts_rank_cd(c.search_vector,st.expansion_query)) lexical_score
        FROM legal_chunks c
        JOIN legal_document_versions v ON v.id=c.version_id
        CROSS JOIN search_terms st
        WHERE c.content_kind='FULL_TEXT'
          AND (v.valid_from IS NULL OR v.valid_from <= $5::date)
          AND (v.valid_to IS NULL OR v.valid_to >= $5::date)
          AND (c.search_vector @@ st.original_query OR c.search_vector @@ st.expansion_query)
      ), lexical_ranked AS (
        SELECT chunk_id,version_id,ordinal,
          row_number() OVER(ORDER BY lexical_score DESC,ordinal) candidate_rank
        FROM lexical_candidates
      ), vector_ranked AS (
        SELECT c.id chunk_id,c.version_id,c.ordinal,
          row_number() OVER(ORDER BY c.embedding_384 <=> $4::vector) candidate_rank
        FROM legal_chunks c
        JOIN legal_document_versions v ON v.id=c.version_id
        WHERE $4::vector IS NOT NULL
          AND (v.valid_from IS NULL OR v.valid_from <= $5::date)
          AND (v.valid_to IS NULL OR v.valid_to >= $5::date)
          AND c.embedding_384 IS NOT NULL
          AND c.embedding_384_model='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
          AND c.embedding_384_dimensions=384
          AND c.content_kind='FULL_TEXT'
        ORDER BY c.embedding_384 <=> $4::vector
        LIMIT 120
      ), candidate_scores AS (
        SELECT chunk_id,version_id,ordinal,sum(score) AS rank
        FROM (
          SELECT chunk_id,version_id,ordinal,2.0/(60.0+candidate_rank) AS score
          FROM lexical_ranked WHERE candidate_rank<=120
          UNION ALL
          SELECT chunk_id,version_id,ordinal,1.0/(60.0+candidate_rank) AS score
          FROM vector_ranked
        ) candidates
        GROUP BY chunk_id,version_id,ordinal
      ), ranked AS (
        SELECT d.id document_id,v.id version_id,d.source_type,d.source_id,d.source_key,
          sr.authority_level source_authority_level,sr.verification_status source_registry_status,
          sr.license_name source_license_name,sr.full_text_ingestion_allowed source_full_text_ingestion_allowed,
          d.title,d.document_kind,
          d.official_number,d.jurisdiction,d.official_url,d.signature_date,d.publication_date,d.status document_status,
          d.source_status,d.raw_metadata,d.first_seen_at,v.source_version_id,v.version_key,v.valid_from,v.valid_to,v.version_status,v.raw_payload,v.full_text,v.text_sha256,
          c.anchor,c.content content_chunk,c.content_kind,c.ordinal,candidate_scores.rank,
          CASE
            WHEN d.source_type IN ('LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_JORF','OTHER_OFFICIAL')
              AND d.document_kind IN ('CODE','LAW','ORDONNANCE','DECREE','ORDER','JOURNAL_OFFICIEL')
              AND d.source_status IN ('OFFICIAL_TEXT_RETRIEVED','OFFICIAL_TEXT_ID_VERIFIED','OFFICIAL_XML_IMPORTED','MANUALLY_VERIFIED')
              THEN 1.15
            WHEN d.source_type IN ('LEGIFRANCE_CETAT','OTHER_OFFICIAL') AND d.document_kind='ADMIN_CASELAW'
              AND d.source_status IN ('OFFICIAL_TEXT_RETRIEVED','OFFICIAL_TEXT_ID_VERIFIED','OFFICIAL_XML_IMPORTED','MANUALLY_VERIFIED')
              THEN 1.10
            WHEN d.source_type='DILA_CIRCULAIRES' AND d.document_kind='CIRCULAR'
              AND d.source_status IN ('OFFICIAL_TEXT_RETRIEVED','OFFICIAL_TEXT_ID_VERIFIED','OFFICIAL_XML_IMPORTED','MANUALLY_VERIFIED')
              THEN 1.05
            ELSE 1.0
          END AS authority_weight,
          row_number() OVER(PARTITION BY v.id ORDER BY candidate_scores.rank DESC,c.ordinal) rn
        FROM candidate_scores
        JOIN legal_chunks c ON c.id=candidate_scores.chunk_id
        JOIN legal_document_versions v ON v.id=c.version_id
        JOIN legal_documents d ON d.id=v.document_id
        LEFT JOIN legal_source_registry sr ON sr.source_key=d.source_key
      ), selected_chunks AS (
        -- Keep only passages selected by lexical/vector relevance. Never append
        -- the document's final chunk: it is often unrelated to the user's question.
        -- Bounded authority adjustment: it cannot replace relevance, temporal validity,
        -- public-service scope checks or claim-level evidence validation.
        SELECT version_id,string_agg(content_chunk,E'\\n\\n' ORDER BY chunk_order) AS content,
          max(rank * authority_weight) AS rank
        FROM (
          SELECT version_id,content_chunk,rn AS chunk_order,rank,authority_weight
          FROM ranked WHERE rn<=CASE WHEN document_kind='ADMIN_CASELAW' THEN 1 ELSE 2 END
        ) selected_passages
        GROUP BY version_id
      ), document_metadata AS (
        SELECT DISTINCT ON (version_id) document_id,version_id,source_type,source_id,source_key,
          source_authority_level,source_registry_status,source_license_name,source_full_text_ingestion_allowed,
          title,document_kind,official_number,jurisdiction,official_url,signature_date,publication_date,document_status,
          source_status,raw_metadata,first_seen_at,source_version_id,version_key,valid_from,valid_to,version_status,raw_payload,full_text,text_sha256,
          anchor,content_kind
        FROM ranked ORDER BY version_id,rank DESC,ordinal
      )
      SELECT metadata.*,selected_chunks.content,selected_chunks.rank
      FROM document_metadata metadata JOIN selected_chunks USING(version_id)
      ORDER BY selected_chunks.rank DESC,metadata.publication_date DESC NULLS LAST LIMIT $3
    """, query.strip(), expansion_expression, limit, vector_literal, requested_date)
    results = []
    for row in rows:
        item = dict(row)
        item["temporal_status"] = temporal_status(item.get("valid_from"), item.get("valid_to"), requested_date,
            item.get("document_kind"), item.get("signature_date"), item.get("raw_payload"),
            item.get("version_status"), source_version_id=item.get("source_version_id"))
        item["requested_date"] = requested_date.isoformat()
        metadata = item.get("raw_metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (ValueError, TypeError):
                metadata = {}
        item["raw_metadata"] = metadata if isinstance(metadata, dict) else {}
        if item.get("source_type") == "CGFP_SNAPSHOT":
            item["snapshot_modified_at"] = (
                item["raw_metadata"].get("snapshot_modified_at")
                or item["raw_metadata"].get("generated_at")
            )
            item["snapshot_verification_status"] = item["raw_metadata"].get("verification_status")
        item["excerpt"] = item.pop("content")[:8500]
        item["retrieval_scope"] = (
            "HYBRID_LEXICAL_VECTOR_RELEVANCE_SELECTED_PASSAGES"
            if vector_literal is not None and item.get("document_kind") == "ADMIN_CASELAW"
            else "HYBRID_LEXICAL_VECTOR_SELECTED_PASSAGES"
            if vector_literal is not None
            else "RELEVANCE_SELECTED_PASSAGES_FROM_HASH_VERIFIED_FULL_TEXT"
            if item.get("document_kind") == "ADMIN_CASELAW"
            else "SELECTED_RELEVANT_PASSAGES_FROM_HASH_VERIFIED_FULL_TEXT"
        )
        item["retrieval_mode"] = "HYBRID_LEXICAL_VECTOR" if vector_literal is not None else "LEXICAL_ONLY"
        full_text = item.pop("full_text")
        expected_hash = item.get("text_sha256")
        actual_hash = sha256_text(full_text) if full_text else None
        hash_verified = bool(expected_hash and actual_hash and expected_hash.strip() == actual_hash)
        item.pop("raw_payload", None)
        item["full_text"] = full_text if hash_verified else ""
        item["official_source"] = item.get("source_status") in {
            "OFFICIAL_TEXT_RETRIEVED", "OFFICIAL_TEXT_ID_VERIFIED", "OFFICIAL_XML_IMPORTED", "MANUALLY_VERIFIED"}
        item["citation_integrity"] = {"valid": bool(item["source_id"] and item["source_status"] and hash_verified and item.get("content_kind") == "FULL_TEXT"),
            "verification_scope": "SOURCE_ID_AND_STORED_VERSION", "text_hash_verified": hash_verified,
            "temporal_status": item["temporal_status"]}
        results.append(item)
    return results
