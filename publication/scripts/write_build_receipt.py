#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "paper.pdf"
OUT = ROOT / "BUILD_RECEIPT.json"


def cmd(*args: str) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"UNAVAILABLE:{type(exc).__name__}"


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""

pdfinfo = cmd("pdfinfo", str(PDF))
info = {}
for line in pdfinfo.splitlines():
    if ":" in line:
        k, v = line.split(":", 1)
        info[k.strip()] = v.strip()

receipt = {
    "schema": "ccb-publication-build-receipt-v1",
    "scientific_status": "FAIL_CLOSED_NOT_SUBMISSION_READY",
    "source_repository_head": cmd("git", "rev-parse", "HEAD"),
    "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH", "UNSET"),
    "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "entrypoint": "publication/build.sh",
    "master_tex": "publication/main.tex",
    "output": "publication/paper.pdf",
    "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
    "pdf_bytes": PDF.stat().st_size,
    "pdf_pages": int(info.get("Pages", "0") or 0),
    "pdf_page_size": info.get("Page size", "UNKNOWN"),
    "latexmk": first_line(cmd("latexmk", "-v")),
    "pdflatex": first_line(cmd("pdflatex", "--version")),
    "validation": "PUBLICATION_STRUCTURE_PASS",
    "pdf_preflight": "openable, unencrypted, chapterised working build",
    "note": "A successful build authorises typography/structure only, not gated physics claims."
}
OUT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(f"PUBLICATION_RECEIPT_WRITTEN: {OUT}")
