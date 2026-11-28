"""Server-side PDF rendering for private legal working dossiers."""
from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable,
)


def _text(value: Any) -> str:
    """Escape user-controlled text before passing it to ReportLab's XML parser."""
    if value is None:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    return escape(text).replace("\n", "<br/>")


def _section(story: list, title: str, styles: dict, body: Any) -> None:
    if isinstance(body, list):
        body = "\n".join(str(item) for item in body if item is not None)
    if body is None or not str(body).strip():
        return
    story.append(KeepTogether([
        Paragraph(_text(title), styles["Section"]),
        Paragraph(_text(body), styles["Body"]),
        Spacer(1, 4 * mm),
    ]))


def render_legal_dossier_pdf(content: dict, dossier_id: str = "") -> bytes:
    """Render the stored dossier faithfully; never create or validate legal claims."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm,
        title=str(content.get("title") or "Dossier juridique")[:160],
        author="Dikévia",
        subject="Dossier juridique de travail — brouillon à vérifier",
    )
    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle(
            "DikeviaTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=19, leading=23, textColor=colors.HexColor("#153c35"),
            alignment=TA_CENTER, spaceAfter=5 * mm,
        ),
        "Subtitle": ParagraphStyle(
            "DikeviaSubtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=9, leading=12, textColor=colors.HexColor("#53645f"),
            alignment=TA_CENTER, spaceAfter=7 * mm,
        ),
        "Section": ParagraphStyle(
            "DikeviaSection", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=colors.HexColor("#153c35"),
            spaceBefore=3 * mm, spaceAfter=2 * mm, keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "DikeviaBody", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9, leading=13, textColor=colors.HexColor("#202927"),
            splitLongWords=True, spaceAfter=1 * mm,
        ),
        "Small": ParagraphStyle(
            "DikeviaSmall", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8, leading=11, textColor=colors.HexColor("#53645f"),
            splitLongWords=True,
        ),
        "Warning": ParagraphStyle(
            "DikeviaWarning", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.5, leading=12, textColor=colors.HexColor("#704d16"),
            backColor=colors.HexColor("#fff6df"), borderColor=colors.HexColor("#e9d7a8"),
            borderWidth=0.6, borderPadding=7, spaceBefore=3 * mm, spaceAfter=5 * mm,
        ),
    }
    story = [
        Paragraph("DIKÉVIA", styles["Subtitle"]),
        Paragraph(_text(content.get("title") or "Dossier juridique"), styles["Title"]),
        Paragraph(
            "DOSSIER DE TRAVAIL · " + _text(content.get("status") or "BROUILLON_A_VALIDER"),
            styles["Subtitle"],
        ),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#b8c9c2")),
        Spacer(1, 4 * mm),
    ]

    warning = content.get("warning") or (
        "Document de travail. Les faits rapportés ne sont pas vérifiés et les analyses "
        "ne valent pas validation juridique. Contrôler les sources, les dates et les pièces."
    )
    story.append(Paragraph(_text(warning), styles["Warning"]))
    _section(story, "Employeur / collectivité", styles, content.get("employer"))
    _section(story, "Objet et demande", styles, content.get("objective"))
    _section(story, "Éléments rapportés et questions", styles, content.get("facts_summary"))
    _section(story, "Chronologie", styles, content.get("chronology"))
    _section(story, "Préparation de l’instance (CST / CAP / CCP / F3SCT)", styles, content.get("instance_preparation"))

    analyses = content.get("legal_analyses") or []
    if analyses:
        story.append(Paragraph("Analyses issues des échanges JURIS", styles["Section"]))
        for index, item in enumerate(analyses, 1):
            if not isinstance(item, dict):
                continue
            status = item.get("verification_status") or "NON_VERIFIE"
            answer = item.get("answer") or ""
            created = item.get("created_at") or ""
            story.append(Paragraph(
                f"<b>Analyse {index} — {_text(status)}</b>"
                + (f" · {_text(created)}" if created else ""),
                styles["Small"],
            ))
            story.append(Paragraph(_text(answer), styles["Body"]))
            story.append(Spacer(1, 2 * mm))

    sources = content.get("legal_sources") or []
    if sources:
        story.append(Paragraph("Sources citées dans les réponses", styles["Section"]))
        for index, source in enumerate(sources, 1):
            if not isinstance(source, dict):
                continue
            label = source.get("title") or source.get("article") or source.get("official_number") or "Source juridique"
            details = [str(source.get(key)) for key in ("article", "official_number", "source_id", "temporal_status")
                       if source.get(key)]
            line = f"<b>{index}. {_text(label)}</b>"
            if details:
                line += "<br/>" + _text(" · ".join(details))
            url = source.get("official_url") or source.get("source_url")
            parsed = urlparse(str(url or ""))
            if parsed.scheme == "https" and parsed.netloc:
                safe_url = escape(str(url), quote=True)
                line += f'<br/><link href="{safe_url}" color="#176b5b">{_text(url)}</link>'
            story.append(Paragraph(line, styles["Body"]))
            story.append(Spacer(1, 2 * mm))

    _section(story, "Points restant à vérifier", styles, content.get("points_to_verify"))
    _section(story, "Pièces et éléments de preuve", styles, content.get("documents_and_evidence"))
    _section(story, "Conclusion provisoire", styles, content.get("conclusion"))
    _section(story, "Plan d'action", styles, content.get("action_plan"))

    generated = content.get("generated_at")
    if generated:
        _section(story, "Date de constitution", styles, generated)
    if dossier_id:
        story.append(Paragraph("Référence interne : " + _text(dossier_id), styles["Small"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d5dfda"))
        canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#68766f"))
        canvas.drawString(20 * mm, 10 * mm, "Dikévia — document de travail confidentiel")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
