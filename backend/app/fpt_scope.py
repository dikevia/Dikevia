"""Conservative public-service scope classifier for Légifrance regulatory hits.

A text is eligible for case-specific FPT analysis only when its own content
supports a territorial or genuinely cross-public-service scope. Ambiguous
records remain visible as research leads but are not sent to Gemini as applicable
law. This is a relevance guard, not a legal applicability determination.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_FPT_MARKERS = (
    "fonction publique territoriale",
    "fonctionnaires territoriaux",
    "agents territoriaux",
    "collectivites territoriales",
    "collectivite territoriale",
    "centre national de la fonction publique territoriale",
    "cnfpt",
    "centres de gestion",
    "centre de gestion",
    "conseil superieur de la fonction publique territoriale",
    "communes et leurs etablissements publics",
    "departements et regions",
    "maires et presidents d etablissements publics",
    "decret 88-145", "decret n 88 145",
    "decret 87-602", "decret n 87 602",
    "decret 89-677", "decret n 89 677",
    "decret 91-298", "decret n 91 298",
)

_FPH_MARKERS = (
    "fonction publique hospitaliere",
    "etablissements publics de sante",
    "personnels hospitaliers",
    "personnels medicaux",
    "directeur d hopital",
    "centres hospitaliers",
)

_FPE_MARKERS = (
    "fonction publique de l etat",
    "fonctionnaires de l etat",
    "agents de l etat",
    "administrations centrales",
    "services deconcentres de l etat",
    "ministeres",
)

_GENERAL_MARKERS = (
    "code general de la fonction publique",
    "fonction publique",
    "agents publics",
    "fonctionnaires",
    "droits et obligations des fonctionnaires",
    "discipline des fonctionnaires",
    "protection fonctionnelle",
)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def classify_public_service_scope(source: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative scope label and whether this hit may reach Gemini."""
    title = str(source.get("title") or "")
    text = str(source.get("full_text") or source.get("text") or source.get("excerpt") or "")
    corpus = _fold((title + " " + text)[:500_000])

    fpt_hits = [marker for marker in _FPT_MARKERS if _fold(marker) in corpus]
    fph_hits = [marker for marker in _FPH_MARKERS if _fold(marker) in corpus]
    fpe_hits = [marker for marker in _FPE_MARKERS if _fold(marker) in corpus]

    # Narrow FPT bridge: decree n° 2002-60 is the IHTS reference regime
    # used through the territorial indemnity framework. The prompt still
    # requires decree n° 91-875 and the local deliberation to be checked.
    is_ihts_reference = (
        "2002 60" in corpus
        and "indemnites horaires pour travaux supplementaires" in corpus
    )
    if is_ihts_reference:
        return {
            "scope": "FPT_REFERENCE",
            "evidence": ["decret 2002-60 : reference IHTS a verifier avec le decret 91-875 et la deliberation locale"],
            "analysis_eligible": True,
        }

    if fpt_hits:
        return {
            "scope": "FPT",
            "evidence": fpt_hits[:3],
            "analysis_eligible": True,
        }
    if fph_hits:
        return {
            "scope": "FPH",
            "evidence": fph_hits[:3],
            "analysis_eligible": False,
        }
    if fpe_hits:
        return {
            "scope": "FPE",
            "evidence": fpe_hits[:3],
            "analysis_eligible": False,
        }

    general_hits = [marker for marker in _GENERAL_MARKERS if _fold(marker) in corpus]
    if len(general_hits) >= 2:
        return {
            "scope": "GENERAL_PUBLIC_SERVICE",
            "evidence": general_hits[:3],
            "analysis_eligible": True,
        }
    return {
        "scope": "SCOPE_TO_VERIFY",
        "evidence": general_hits[:2],
        "analysis_eligible": False,
    }

_IHTS_QUERY_MARKERS = (
    "heures supplementaires", "heure supplementaire", "heures sup",
    "heures supp", "heures supolementaires", "heure supolementaire",
    "ihts", "travaux supplementaires",
)

_IHTS_SOURCE_MARKERS = (
    "indemnites horaires pour travaux supplementaires",
    "indemnite horaire pour travaux supplementaires",
    "indemnites horaires de travaux supplementaires",
    "ihts",
    "2002 60",
    "91 875",
    "2001 623",
    "repos compensateur des heures supplementaires",
    "repos compensateur au titre des heures supplementaires",
)


def is_ihts_relevant_source(question: str, source: dict[str, Any]) -> bool:
    """Reject generic hour credits and unrelated CGFP hits for IHTS questions."""
    folded_question = _fold(str(question or ""))
    if not any(_fold(marker) in folded_question for marker in _IHTS_QUERY_MARKERS):
        return True

    title = str(source.get("title") or "")
    article = str(source.get("article") or source.get("article_id") or "")
    text = str(source.get("full_text") or source.get("text") or source.get("excerpt") or "")
    corpus = _fold((title + " " + article + " " + text)[:500_000])

    # Explicitly exclude unrelated CGFP provisions that use "heures
    # supplémentaires" to describe CPF credits or union time credits.
    excluded_articles = ("r422 96", "l422 15", "r214 28", "r214 32", "r214 33")
    if any(_fold(code) in corpus for code in excluded_articles):
        return False

    # Generic mentions of extra hours are not enough: require the IHTS
    # terminology or one of the implementing/reference decrees.
    return any(_fold(marker) in corpus for marker in _IHTS_SOURCE_MARKERS)

