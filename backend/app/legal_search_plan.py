"""Deterministic, narrow query expansions for French territorial public-service law."""

from __future__ import annotations

import re
import unicodedata


_ARTICLE_REFERENCE = re.compile(r"\b(?:article\s+)?[LRD]\.?\s*\d+(?:-\d+)*\b", re.IGNORECASE)
_DIRECT_ARTICLE_LOOKUP = re.compile(
    r"\b(?:que\s+(?:prevoit|dit|dispose)\s+(?:l['’]\s*)?article"
    r"|(?:texte|contenu|teneur)\s+(?:integral\s+)?(?:de\s+)?(?:l['’]\s*)?article"
    r"|(?:donne|fournis|reproduis)\s+(?:moi\s+)?(?:le\s+)?texte\s+(?:de\s+)?(?:l['’]\s*)?article)\b",
    re.IGNORECASE,
)

# The most specific topic wins. Expansions are deliberately tied to French
# territorial public-service source families and their implementing texts.
_TOPIC_EXPANSIONS = (
    (
        ("heures supplementaires", "heure supplementaire", "heures sup", "ihts",
         "indemnites horaires pour travaux supplementaires", "travaux supplementaires"),
        "indemnités horaires pour travaux supplémentaires IHTS décret 2002-60 "
        "décret 91-875 décret 2001-623 fonction publique territoriale "
        "délibération assemblée délibérante repos compensateur",
    ),
    (
        ("harcelement moral", "agissements repetes", "degradation des conditions de travail"),
        "harcèlement moral agents territoriaux CGFP protection fonctionnelle "
        "décret procédure fonction publique territoriale jurisprudence administrative",
    ),
    (
        ("harcelement sexuel", "agissement sexiste", "propos sexistes"),
        "harcèlement sexuel agissement sexiste agents publics territoriaux CGFP "
        "protection fonctionnelle jurisprudence administrative",
    ),
    (
        ("protection fonctionnelle", "menace", "injure", "agression", "diffamation", "outrage"),
        "protection fonctionnelle agent territorial CGFP obligations employeur public "
        "jurisprudence Conseil d'État collectivités territoriales",
    ),
    (
        ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline",
         "avertissement", "blame", "exclusion temporaire", "revocation"),
        "discipline fonction publique territoriale CGFP décret 89-677 "
        "droits défense conseil de discipline jurisprudence administrative",
    ),
    (
        ("agent contractuel", "agents contractuels", "contractuel", "cdd", "cdi",
         "renouvellement de contrat", "fin de contrat", "licenciement contractuel"),
        "agents contractuels territoriaux décret 88-145 CGFP recrutement renouvellement "
        "licenciement garanties procédure jurisprudence administrative",
    ),
    (
        ("temps de travail", "duree du travail", "annualisation", "astreinte",
         "temps partiel", "cycle de travail", "rtt"),
        "temps de travail fonction publique territoriale décret 2001-623 "
        "décret 2000-815 cycle de travail annualisation astreintes repos",
    ),
    (
        ("accident de service", "maladie professionnelle", "citis",
         "conge longue maladie", "conge longue duree", "conge maladie"),
        "congé pour invalidité temporaire imputable au service CITIS agents territoriaux "
        "accident de service maladie professionnelle CGFP décret 87-602",
    ),
    (
        ("ifse", "rifseep", "nbi", "regime indemnitaire",
         "remuneration", "traitement indiciaire"),
        "rémunération fonctionnaires territoriaux régime indemnitaire RIFSEEP IFSE NBI "
        "délibération locale décret 91-875 CGFP",
    ),
)


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text)).strip()


def build_official_search_query(question: str, max_length: int = 500) -> str:
    """Keep the user's wording first, then append one narrowly matched FPT expansion."""
    original = str(question or "").strip()
    if not original:
        return original
    # Exact legal-reference requests must remain exact; extra terms can turn
    # a direct lookup into an unrelated full-text search.
    folded = _fold(original)
    if _ARTICLE_REFERENCE.search(original) and _DIRECT_ARTICLE_LOOKUP.search(folded):
        return original[:max_length]

    expansion = next(
        (
            terms for triggers, terms in _TOPIC_EXPANSIONS
            if any(_fold(trigger) in folded for trigger in triggers)
        ),
        "",
    )
    if not expansion:
        return original[:max_length]

    # Preserve the full question where possible; truncate only the appended
    # legal vocabulary so the official connector's 500-character contract holds.
    prefix = original[: min(len(original), 250)]
    remaining = max(0, max_length - len(prefix) - 1)
    return (prefix + " " + expansion[:remaining]).strip()
