"""Minimize direct personal identifiers before sending user text to AI providers.

This is data minimization, not anonymization: contextual and special-category data
may remain and still require an appropriate legal basis and provider safeguards.
"""
from __future__ import annotations

import re


_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+",
    re.IGNORECASE,
)
_FRENCH_PHONE = re.compile(
    r"(?<!\w)(?:(?:\+33|0033)\s*(?:\(0\)\s*)?|0)[1-9]"
    r"(?:[\s().-]*\d{2}){4}(?!\w)"
)
_NIR = re.compile(r"(?<!\d)[12](?:[\s.-]?\d){14}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b", re.IGNORECASE)


def redact_direct_identifiers(value: str | None) -> str:
    """Mask common French contact, national-ID and banking identifiers."""
    text = str(value or "")
    text = _IBAN.sub("[COORDONNÉE BANCAIRE MASQUÉE]", text)
    text = _NIR.sub("[IDENTIFIANT PERSONNEL MASQUÉ]", text)
    text = _FRENCH_PHONE.sub("[NUMÉRO DE TÉLÉPHONE MASQUÉ]", text)
    text = _EMAIL.sub("[ADRESSE E-MAIL MASQUÉE]", text)
    return text
