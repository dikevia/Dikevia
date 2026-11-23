#!/usr/bin/env python3
"""Construit un index article/page depuis le snapshot CGFP fourni dans le kit."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "backend"))
from app.cgfp import clean_cgfp_article_text

ARTICLE_RE = re.compile(r'^\s*Article\s+([LDR]\s*\d+(?:-\d+)*?)\s*$', re.I)

def build(pdf: Path, output: Path) -> dict:
    reader = PdfReader(str(pdf))
    articles: list[dict] = []
    current = None
    def finish():
        if current is None:
            return
        text = clean_cgfp_article_text("\n".join(current.pop("_lines")) )
        if text:
            current["text"] = text
            articles.append(current.copy())
    for page_number, page in enumerate(reader.pages, 1):
        page_text = page.extract_text() or ""
        for line in page_text.splitlines():
            match = ARTICLE_RE.match(line)
            if match:
                finish()
                current = {"article": re.sub(r"\s+", "", match.group(1)).upper(),
                           "page_start": page_number, "page_end": page_number, "_lines": []}
            elif current is not None:
                current["page_end"] = page_number
                current["_lines"].append(line)
    finish()
    payload = {
        "schema_version": 1,
        "source_id": "FR-CGFP-2026-10-31",
        "source_file": pdf.name,
        "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "page_count": len(reader.pages),
        "article_count": len(articles),
        "snapshot_modified_at": "2026-10-31",
        "generated_at": "2026-11-13",
        "verification_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
        "articles": articles,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {k: payload[k] for k in ("page_count", "article_count", "source_sha256", "verification_status")}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="corpus_national/legislation/CGFP_snapshot_2026-10-31.pdf")
    parser.add_argument("--output", default="corpus_national/index/CGFP_articles_2026-10-31.json")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.pdf), Path(args.output)), ensure_ascii=False, indent=2))
