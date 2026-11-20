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
        ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel",
         "representants du personnel", "representant syndical", "representants syndicaux", "local syndical", "locaux syndicaux", "decharge d activite", "decharges d activite", "decharge syndicale",
         "credit de temps syndical", "credit d heures syndical", "asa syndicale",
         "autorisation speciale d absence syndicale",
         "formation syndicale", "reunion d information syndicale",
         "comite social territorial"),
        "droit syndical fonction publique territoriale CGFP livre II exercice du droit "
        "syndical dialogue social représentation des agents garanties exercice droit "
        "syndical facilités organisations syndicales locaux syndicaux autorisations "
        "spéciales absence décharges activité service crédit temps syndical formation "
        "syndicale réunions information syndicale partie réglementaire CGFP "
        "délibération protocole accord local",
    ),
    (
        ("heures supplementaires", "heure supplementaire", "heures sup", "ihts",
         "indemnites horaires pour travaux supplementaires", "travaux supplementaires"),
        "indemnités horaires pour travaux supplémentaires IHTS décret 2002-60 "
        "décret 91-875 décret 2001-623 fonction publique territoriale "
        "délibération assemblée délibérante repos compensateur",
    ),
    (
        ("harcelement moral",),
        "harcèlement moral agents territoriaux CGFP protection fonctionnelle "
        "décret procédure fonction publique territoriale jurisprudence administrative",
    ),
    (
        ("harcelement sexuel", "agissement sexiste", "propos sexistes"),
        "harcèlement sexuel agissement sexiste agents publics territoriaux CGFP "
        "protection fonctionnelle jurisprudence administrative",
    ),
    (
        ("protection fonctionnelle",),
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
        ("renouvellement de contrat", "non renouvellement", "fin de contrat",
         "licenciement contractuel", "recrutement contractuel", "terme du contrat"),
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
    current_turn = original.splitlines()[0]
    current_turn_folded = _fold(current_turn)
    if _ARTICLE_REFERENCE.search(current_turn) and _DIRECT_ARTICLE_LOOKUP.search(current_turn_folded):
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

# Independent, bounded research axes. These are separate retrieval queries,
# not claims about the applicable law. Keep the number small to control latency
# and provider load while avoiding a single overloaded keyword string.
_TOPIC_RESEARCH_AXES = (
    (
        ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel",
         "representants du personnel", "representant syndical", "representants syndicaux",
         "local syndical", "locaux syndicaux", "decharge d activite", "decharges d activite",
         "decharge syndicale", "credit de temps syndical", "credit d heures syndical",
         "asa syndicale", "autorisation speciale d absence syndicale",
         "formation syndicale", "reunion d information syndicale", "comite social territorial"),
        (
            "CGFP livre II droit syndical fonction publique territoriale exercice droits syndicaux agents territoriaux",
            "CGFP autorisations speciales absence syndicale decharges activite service credit temps syndical locaux syndicaux deliberation locale reunions information formation syndicale dialogue social organisations syndicales",
        ),
    ),
)


def build_official_search_queries(question: str, max_queries: int = 3) -> list[str]:
    """Build a small set of distinct, topic-focused legal retrieval queries.

    The original expanded query remains first for backward-compatible recall.
    Additional axes are only emitted for explicitly recognized topics.
    """
    primary = build_official_search_query(question)
    if not primary:
        return []
    queries = [primary]
    folded = _fold(str(question or ""))
    for triggers, axes in _TOPIC_RESEARCH_AXES:
        if any(_fold(trigger) in folded for trigger in triggers):
            for axis in axes:
                candidate = axis[:500]
                if candidate not in queries:
                    queries.append(candidate)
                if len(queries) >= max(1, min(max_queries, 3)):
                    break
            break
    return queries[:max(1, min(max_queries, 3))]
