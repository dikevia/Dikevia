"""Exact-reference safeguards for direct CGFP article lookups."""

import re
import unicodedata


_ARTICLE_REFERENCE = re.compile(r"\b([LRD])\.?\s*(\d+(?:-\d+)*)\b", re.IGNORECASE)
_DIRECT_LOOKUP_INTENT = re.compile(
    r"\b(?:"
    r"que\s+(?:prevoit|dit|dispose)\s+(?:l['’]\s*)?article"
    r"|(?:texte|contenu|teneur)\s+(?:integral\s+)?(?:de\s+)?(?:l['’]\s*)?article"
    r"|(?:donne|fournis|reproduis)\s+(?:moi\s+)?(?:le\s+)?texte\s+(?:de\s+)?(?:l['’]\s*)?article"
    r"|article\s+[lrd]\.?\s*\d+(?:-\d+)*.{0,100}\b(?:texte|contenu|teneur|prevoit|dispose)"
    r")\b",
    re.IGNORECASE,
)


def _fold(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in raw if not unicodedata.combining(char)).casefold()


def _normalise_reference(value: object) -> str:
    match = _ARTICLE_REFERENCE.search(str(value or ""))
    return (match.group(1) + match.group(2)).upper() if match else ""


def missing_direct_article_reference(question: str, sources: list[dict]) -> str | None:
    """Return a requested CGFP article ref when a direct lookup has no exact verified source.

    This deliberately does not activate for ordinary case-specific questions that merely
    cite an article. Related decrees and case law remain available when the exact article
    itself has been retrieved and validated.
    """
    question_text = str(question or "").strip()
    requested_refs = list(dict.fromkeys(
        (match.group(1) + match.group(2)).upper()
        for match in _ARTICLE_REFERENCE.finditer(question_text)
    ))
    if not requested_refs or not _DIRECT_LOOKUP_INTENT.search(_fold(question_text)):
        return None

    verified_refs: set[str] = set()
    source_records = sources if isinstance(sources, (list, tuple)) else []
    for source in source_records:
        if not isinstance(source, dict):
            continue
        if source.get("source_type") not in {
            "LEGIFRANCE_API", "CGFP_SNAPSHOT",
        }:
            continue
        integrity = source.get("citation_integrity")
        if not isinstance(integrity, dict) or integrity.get("valid") is not True:
            continue
        if source.get("content_kind") == "METADATA":
            continue
        candidate = (
            _normalise_reference(source.get("article"))
            or _normalise_reference(source.get("requested_reference"))
            or _normalise_reference(source.get("official_number"))
        )
        if candidate:
            verified_refs.add(candidate)
    return next((reference for reference in requested_refs if reference not in verified_refs), None)
