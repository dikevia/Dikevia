"""Recherche documentaire dans l'index article/page du snapshot CGFP.

Les résultats sont des pistes documentaires. Le snapshot n'est pas une source
suffisante pour certifier la version applicable à une date donnée.
"""
from __future__ import annotations
import json
import math
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from collections import Counter

DEFAULT_INDEX = Path(os.getenv("CGFP_INDEX_PATH") or (Path(__file__).resolve().parents[2] / "corpus_national/index/CGFP_articles_2026-10-31.json"))
STOPWORDS = {"dans", "avec", "pour", "par", "sur", "une", "des", "les", "aux", "est", "sont", "que", "qui", "quoi", "quel", "quelle", "quels", "quelles", "comment", "quand", "doit", "peut", "faire", "fait", "agent", "agents", "fonction", "fonctionnaire", "fonctionnaires", "territorial", "territoriaux", "territoriale", "territoriales", "collectivite", "collectivites", "public", "publique", "publiques", "publics", "article", "code"}
ARTICLE_REF = re.compile(r"\b([LDR]\s*\d+(?:-\d+)*)\b", re.I)
TOKEN = re.compile(r"[a-z0-9]{2,}")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def tokenize(value: str) -> list[str]:
    return [t for t in TOKEN.findall(normalize(value)) if t not in STOPWORDS]


@lru_cache(maxsize=1)
def load_index() -> dict:
    if not DEFAULT_INDEX.is_file():
        raise FileNotFoundError(f"Index CGFP absent : {DEFAULT_INDEX}")
    data = json.loads(DEFAULT_INDEX.read_text(encoding="utf-8"))
    if data.get("source_id") != "FR-CGFP-2026-10-31" or not isinstance(data.get("articles"), list):
        raise ValueError("Format ou provenance de l'index CGFP invalide.")
    if not data["articles"]:
        raise ValueError("Index CGFP vide.")
    return data


@lru_cache(maxsize=1)
def _search_corpus() -> dict:
    data = load_index()
    docs = []
    df = Counter()
    total_length = 0
    by_ref = {}
    for article in data["articles"]:
        ref = re.sub(r"\s+", "", str(article.get("article", ""))).upper()
        if not re.fullmatch(r"[LDR]\d+(?:-\d+)*", ref):
            continue
        terms = tokenize(article.get("text", ""))
        counts = Counter(terms)
        for term in counts:
            df[term] += 1
        total_length += len(terms)
        item = {"article": ref, "page_start": int(article["page_start"]),
                "page_end": int(article["page_end"]), "text": str(article.get("text", "")),
                "terms": counts, "length": len(terms)}
        docs.append(item)
        by_ref[ref] = item
    if not docs:
        raise ValueError("Aucun article exploitable dans l'index CGFP.")
    return {"docs": docs, "df": df, "avgdl": total_length / len(docs), "by_ref": by_ref}


def _excerpt(text: str, query_terms: set[str], max_chars: int = 1800) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    normalized = normalize(clean)
    positions = [normalized.find(term) for term in query_terms if normalized.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - max_chars // 4)
    # Keep a readable boundary while retaining the most useful query context.
    start = clean.rfind(" ", 0, start) + 1 if start else 0
    end = min(len(clean), start + max_chars)
    end = clean.rfind(" ", start, end) if end < len(clean) else end
    return ("…" if start else "") + clean[start:end].strip() + ("…" if end < len(clean) else "")


def get_cgfp_article(article_ref: str) -> dict | None:
    ref = re.sub(r"\s+", "", article_ref).upper()
    if not re.fullmatch(r"[LDR]\d+(?:-\d+)*", ref):
        return None
    data = load_index()
    item = _search_corpus()["by_ref"].get(ref)
    if not item:
        return None
    return {"source_id": data["source_id"], "article": item["article"],
            "page_start": item["page_start"], "page_end": item["page_end"],
            "text": item["text"], "source_file": data["source_file"],
            "source_sha256": data["source_sha256"],
            "verification_status": data["verification_status"]}


def search_cgfp(query: str, limit: int = 8) -> dict:
    data = load_index()
    corpus = _search_corpus()
    normalized_query = normalize(query)
    refs = {re.sub(r"\s+", "", m.group(1)).upper() for m in ARTICLE_REF.finditer(query)}
    terms = tokenize(query)
    unique_terms = set(terms)
    if not refs and not unique_terms:
        return {"source": {k: data[k] for k in ("source_id", "source_file", "source_sha256", "page_count", "article_count", "snapshot_modified_at", "generated_at", "verification_status")}, "results": []}
    n = len(corpus["docs"])
    avgdl = corpus["avgdl"] or 1
    phrase = " ".join(terms)
    results = []
    for doc in corpus["docs"]:
        score = 10000.0 if doc["article"] in refs else 0.0
        for term in unique_terms:
            tf = doc["terms"].get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - corpus["df"][term] + 0.5) / (corpus["df"][term] + 0.5))
            k1, b = 1.5, 0.75
            denom = tf + k1 * (1 - b + b * doc["length"] / avgdl)
            score += idf * (tf * (k1 + 1) / denom)
        body_norm = normalize(doc["text"])
        if phrase and len(phrase) >= 5 and phrase in body_norm:
            score += 2.5
        if unique_terms and unique_terms.issubset(doc["terms"].keys()):
            score += 1.0
        if score <= 0:
            continue
        results.append({"article": doc["article"], "page_start": doc["page_start"],
                        "page_end": doc["page_end"],
                        "excerpt": _excerpt(doc["text"], unique_terms),
                        "score": round(score, 4), "source_id": data["source_id"]})
    results.sort(key=lambda item: (-item["score"], item["article"]))
    return {"source": {k: data[k] for k in ("source_id", "source_file", "source_sha256", "page_count", "article_count", "snapshot_modified_at", "generated_at", "verification_status")},
            "results": results[:max(1, min(int(limit), 20))]}
