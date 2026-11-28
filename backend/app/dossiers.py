"""Faithful dossier assembly from an authenticated user's legal conversation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EMPLOYER_LABELS = {
    "NATIONAL": "National / non précisé",
    "VILLE_SAINT_ETIENNE": "Ville de Saint-Étienne",
    "SAINT_ETIENNE_METROPOLE": "Saint-Étienne Métropole",
}


def _metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def build_dossier_content(conversation: dict, messages: list[dict]) -> dict:
    """Build a structured draft; do not invent or silently synthesize legal facts."""
    facts, analyses, questions, sources, missing = [], [], [], [], []
    seen_sources = set()
    employers, dates = [], []
    for message in messages:
        meta = _metadata(message.get("metadata"))
        if message.get("role") == "user":
            text = str(message.get("content") or "").strip()
            if text:
                questions.append(text)
                created_at = str(message.get("created_at") or "")
                facts.append((created_at, text))
            if meta.get("employer"):
                employers.append(meta["employer"])
            if meta.get("facts_date"):
                dates.append(str(meta["facts_date"]))
        elif message.get("role") == "assistant":
            answer = str(message.get("content") or "").strip()
            if answer:
                analyses.append({
                    "verification_status": meta.get("verification_status", "NON_VERIFIE"),
                    "answer": answer,
                    "created_at": str(message.get("created_at") or ""),
                })
            for item in meta.get("sources", []) if isinstance(meta.get("sources"), list) else []:
                if not isinstance(item, dict):
                    continue
                key = item.get("source_id") or item.get("official_url") or item.get("title")
                if key and key not in seen_sources:
                    seen_sources.add(key)
                    sources.append(item)
            for item in meta.get("missing_information", []) if isinstance(meta.get("missing_information"), list) else []:
                text = str(item).strip()
                if text and text not in missing:
                    missing.append(text)
    employer = next((EMPLOYER_LABELS.get(x, x) for x in reversed(employers)), "Non précisé")
    facts_dates = list(dict.fromkeys(dates))
    title = str(conversation.get("title") or "Dossier juridique").strip()[:160]
    return {
        "schema_version": 1,
        "status": "BROUILLON_A_VALIDER",
        "title": title,
        "employer": employer,
        "facts_dates": facts_dates,
        "objective": "À préciser par l'utilisateur.",
        "facts_summary": "\n\n".join(f"Échange {i + 1}" + (f" ({stamp})" if stamp else "") + f" — {q}" for i, (stamp, q) in enumerate(facts)),
        "chronology": "\n".join(f"{i + 1}. " + (f"{stamp} — " if stamp else "") + q for i, (stamp, q) in enumerate(facts)),
        "questions": questions,
        "legal_analyses": analyses,
        "legal_sources": sources,
        "instance_preparation": "",
        "documents_and_evidence": "Aucune pièce jointe n'est automatiquement incorporée. Ajouter ici les références des pièces utiles, sans données personnelles excessives.",
        "points_to_verify": missing,
        "conclusion": "Conclusion à établir après vérification des faits, des textes applicables et des pièces du dossier.",
        "action_plan": "À compléter après validation par un référent compétent.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conversation_message_count": len(messages),
        "warning": "Document de travail constitué à partir des échanges. Il ne vaut ni validation juridique ni constatation des faits. Les réponses antérieures ne remplacent pas les sources officielles. Vérifier chaque référence et compléter les pièces manquantes.",
    }


def validate_dossier_content(content: Any) -> dict:
    if not isinstance(content, dict):
        raise ValueError("Le contenu du dossier doit être un objet JSON.")
    allowed = {"schema_version", "status", "title", "employer", "facts_dates", "objective", "facts_summary",
               "chronology", "questions", "legal_analyses", "legal_sources", "instance_preparation", "documents_and_evidence",
               "points_to_verify", "conclusion", "action_plan", "generated_at", "conversation_message_count", "warning"}
    clean = {k: v for k, v in content.items() if k in allowed}
    for key, limit in {"title": 160, "employer": 180, "objective": 5000, "facts_summary": 20000,
                       "chronology": 20000, "instance_preparation": 20000, "documents_and_evidence": 10000, "conclusion": 10000,
                       "action_plan": 10000}.items():
        value = clean.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"Champ {key} invalide ou trop long (maximum {limit} caractères).")
    if clean.get("status") not in {"BROUILLON_A_VALIDER", "EN_REVISION", "VALIDE_HUMAINEMENT", "CLOTURE"}:
        raise ValueError("Statut de dossier invalide.")
    for key in ("facts_dates", "questions", "legal_analyses", "legal_sources", "points_to_verify"):
        if not isinstance(clean.get(key, []), list) or len(clean.get(key, [])) > 200:
            raise ValueError(f"Champ {key} invalide.")
    import json
    if len(json.dumps(clean, ensure_ascii=False, default=str)) > 200_000:
        raise ValueError("Le dossier dépasse la taille maximale autorisée.")
    return clean
