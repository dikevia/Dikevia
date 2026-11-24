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
        return text[:available] + marker
    return text[:head] + marker + text[-tail:]
