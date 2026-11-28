"""Validation and safe serialization for organisation-level instance session dossiers."""
from __future__ import annotations

from datetime import date
from typing import Any

INSTANCE_CODES = {"CST", "CAP", "CCP", "F3SCT"}
SESSION_STATUSES = {"PREPARATION", "CONVOQUEE", "TENUE", "COMPTE_RENDU_A_VALIDER", "CLOTUREE"}


def validate_instance_session(payload: Any, *, partial: bool = False) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Le dossier de séance doit être un objet JSON.")
    allowed = {
        "instance_code", "title", "meeting_date", "meeting_status",
        "agenda", "preparation", "questions", "documents", "minutes", "action_items",
    }
    if set(payload) - allowed:
        raise ValueError("Le dossier contient des champs non autorisés.")
    result = dict(payload)
    if not partial or "instance_code" in result:
        if result.get("instance_code") not in INSTANCE_CODES:
            raise ValueError("Instance invalide : CST, CAP, CCP ou F3SCT attendu.")
    if not partial or "title" in result:
        title = result.get("title")
        if not isinstance(title, str) or not 3 <= len(title.strip()) <= 200:
            raise ValueError("L'intitulé doit contenir entre 3 et 200 caractères.")
        result["title"] = title.strip()
    if "meeting_date" in result and result["meeting_date"] not in (None, ""):
        try:
            result["meeting_date"] = date.fromisoformat(str(result["meeting_date"])).isoformat()
        except ValueError:
            raise ValueError("Date de séance invalide (AAAA-MM-JJ attendu).")
    elif "meeting_date" in result:
        result["meeting_date"] = None
    if "meeting_status" in result and result["meeting_status"] not in SESSION_STATUSES:
        raise ValueError("Statut de séance invalide.")
    for key, limit in (("agenda", 100), ("questions", 200), ("documents", 200), ("action_items", 300)):
        if key in result:
            value = result[key]
            if not isinstance(value, list) or len(value) > limit or any(not isinstance(x, (str, dict)) for x in value):
                raise ValueError(f"Champ {key} invalide (maximum {limit} éléments).")
    if "preparation" in result and (not isinstance(result["preparation"], dict) or len(result["preparation"]) > 100):
        raise ValueError("Champ preparation invalide.")
    if "minutes" in result and (not isinstance(result["minutes"], str) or len(result["minutes"]) > 50000):
        raise ValueError("Le compte rendu dépasse 50 000 caractères.")
    import json
    if len(json.dumps(result, ensure_ascii=False, default=str)) > 200_000:
        raise ValueError("Le dossier de séance dépasse 200 Ko.")
    return result


def ensure_instance_identity_unchanged(stored_instance_code: str, payload: dict) -> None:
    """Reject attempts to move a saved session dossier to another instance."""
    requested_instance = payload.get("instance_code", stored_instance_code)
    if requested_instance != stored_instance_code:
        raise ValueError(
            "L'instance d'un dossier de séance ne peut pas être modifiée. Créez un nouveau dossier."
        )


def serialize_instance_session(row: Any) -> dict:
    def get(key):
        value = row[key]
        if key in {"agenda", "preparation", "questions", "documents", "action_items"} and isinstance(value, str):
            import json
            return json.loads(value)
        return value
    return {
        "id": str(get("id")),
        "instance_code": get("instance_code"),
        "title": get("title"),
        "meeting_date": get("meeting_date").isoformat() if get("meeting_date") else None,
        "meeting_status": get("meeting_status"),
        "agenda": get("agenda"),
        "preparation": get("preparation"),
        "questions": get("questions"),
        "documents": get("documents"),
        "minutes": get("minutes"),
        "action_items": get("action_items"),
        "created_by": str(get("created_by")),
        "created_at": get("created_at"),
        "updated_at": get("updated_at"),
    }


def render_instance_session_pdf(session: dict) -> bytes:
    """Render a saved session record without generating or approving its minutes."""
    import json
    from .dossier_pdf import render_legal_dossier_pdf

    agenda = session.get("agenda") or []
    questions = session.get("questions") or []
    documents = session.get("documents") or []
    documents = [
        (
            f"{item.get('title') or item.get('filename') or 'Document sans titre'} — "
            f"collectivité : {item.get('collectivity_name') or 'non précisée'} — "
            f"validation : {item.get('validation_status') or 'inconnue'} — "
            f"analyse antivirus : {item.get('scan_status') or 'non renseignée'} — "
            f"référence : {item.get('document_id')}"
        ) if isinstance(item, dict) and item.get("document_id") else
        (str(item.get("title") or item.get("name") or item) if isinstance(item, dict) else str(item))
        for item in documents
    ]
    actions = session.get("action_items") or []
    preparation = session.get("preparation") or {}
    content = {
        "title": session.get("title") or "Dossier de séance",
        "status": session.get("meeting_status") or "PREPARATION",
        "employer": "Instance " + str(session.get("instance_code") or ""),
        "objective": "Date de séance : " + str(session.get("meeting_date") or "à fixer"),
        "facts_summary": "Ordre du jour\n" + "\n".join(
            str(item.get("title") or item) if isinstance(item, dict) else str(item) for item in agenda
        ),
        "chronology": "",
        "instance_preparation": json.dumps(preparation, ensure_ascii=False, indent=2) if preparation else "",
        "documents_and_evidence": documents,
        "points_to_verify": questions,
        "conclusion": session.get("minutes") or "Compte rendu non renseigné.",
        "action_plan": actions,
        "warning": (
            "Dossier de séance de travail. Les questions, notes et comptes rendus sont saisis "
            "par les utilisateurs et ne constituent pas une validation juridique. Vérifier les "
            "faits, les textes applicables, les citations et les décisions avant diffusion."
        ),
    }
    return render_legal_dossier_pdf(content, str(session.get("id") or ""))
