"""Conservative typographic normalization for exact evidence matching.

Only typography variants are unified. Words, numbers, punctuation presence,
negations and legal references remain intact.
"""
from __future__ import annotations

import re
import unicodedata


_TYPOGRAPHIC_TRANSLATION = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201b": "'", "\u02bc": "'", "\uff07": "'",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u00ab": '"', "\u00bb": '"', "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2026": "...",
    # Invisible formatting controls can split or visually reorder legal evidence.
    **{character: None for character in (
        "\u00ad", "\u034f", "\u061c", "\u180e", "\u200b", "\u200c",
        "\u200d", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c",
        "\u202d", "\u202e", "\u2060", "\u2066", "\u2067", "\u2068",
        "\u2069", "\ufeff",
    )},
})


def normalize_evidence_text(value: object) -> str:
    """Normalize Unicode composition, selected typography and whitespace."""
    normalized = unicodedata.normalize("NFC", str(value or "")).translate(_TYPOGRAPHIC_TRANSLATION)
    return re.sub(r"\s+", " ", normalized).strip()

def bound_evidence_text(value: object, max_chars: int = 12000, head_chars: int = 9000) -> str:
    """Bound evidence sent to a model while retaining both the opening and closing provisions."""
    text = str(value or "").strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    marker = "\n\n[Passage intermédiaire non transmis]\n\n"
    available = max(0, max_chars - len(marker))
    head = min(max(0, head_chars), available)
    tail = available - head
    if tail <= 0:
        return text[:max_chars]
    return text[:head] + marker + text[-tail:]

def build_legal_evidence_text(
    full_text: object,
    selected_excerpt: object = None,
    max_chars: int = 12000,
) -> str:
    """Keep retrieved relevant passages and the beginning/end of verified full text."""
    full = str(full_text or "").strip()
    excerpt = str(selected_excerpt or "").strip()
    if not full:
        return bound_evidence_text(excerpt, max_chars=max_chars)
    if not excerpt:
        return bound_evidence_text(full, max_chars=max_chars)
    if excerpt in full and len(full) <= max_chars:
        return full

    marker = "\n\n[Autres passages du texte officiel]\n\n"
    if max_chars <= len(marker):
        return bound_evidence_text(excerpt or full, max_chars=max_chars)
    excerpt_budget = min(len(excerpt), max(0, max_chars - len(marker) - 3000))
    if excerpt_budget <= 0:
        return bound_evidence_text(full, max_chars=max_chars)
    primary = bound_evidence_text(excerpt, max_chars=excerpt_budget)
    remaining = max_chars - len(primary) - len(marker)
    supplement = bound_evidence_text(
        full,
        max_chars=remaining,
        head_chars=max(1, remaining * 3 // 4),
    )
    return primary + marker + supplement

