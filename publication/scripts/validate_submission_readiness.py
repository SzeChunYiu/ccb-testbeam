#!/usr/bin/env python3
"""Fail-closed mechanical gate for CCB paper submission readiness.

This is intentionally stricter than validate_publication.py. It does not prove
physics correctness; it verifies that the machine-readable evidence surfaces
needed for scientific review are present and mutually consistent.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PUB = Path(__file__).resolve().parents[1]
REPO = PUB.parent

FINAL_FIGURE_REQUIRED_COLUMNS = {
    "path",
    "status",
    "source_path",
    "sha256",
    "source_sha256",
    "claim_ids",
    "evidence_class",
}
FINAL_TABLE_REQUIRED_COLUMNS = {
    "path",
    "status",
    "source_path",
    "sha256",
    "source_sha256",
    "claim_ids",
}
FORBIDDEN_CLAIM_STATUS = {
    "BLOCKED",
    "BLOCKED_DATA",
    "GATED",
    "FLAWED",
    "SUPERSEDED",
    "TENSION",
    "REVIEW",
}
SOURCE_DATA_SUFFIXES = {".csv", ".tsv", ".json", ".parquet", ".pq"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")
        return list(reader.fieldnames), list(reader)


def non_readme_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(
        p for p in path.rglob("*")
        if p.is_file() and p.name.lower() != "readme.md"
    )


def resolve_repo_source(token: str) -> Path | None:
    token = token.strip()
    if not token or token.startswith(("http://", "https://")):
        return None
    path = Path(token)
    if path.is_absolute():
        return None
    return (REPO / path).resolve()


def current_git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def main() -> int:
    errors: list[str] = []

    status_text = (PUB / "STATUS.md").read_text(encoding="utf-8")
    if "NOT_SUBMISSION_READY" in status_text or "FAIL_CLOSED" in status_text:
        errors.append("publication/STATUS.md still declares a non-submission-ready state")

    for rel in ("figures/final", "figures/source_data", "tables/final"):
        files = non_readme_files(PUB / rel)
        if not files:
            errors.append(f"publication/{rel} has no non-README scientific artifacts")

    # One canonical claim surface: the publication copy may exist for TeX use,
    # but it must be byte-identical to the canonical ledger.
    canonical_claims = REPO / "docs/claim_ledger.csv"
    publication_claims = PUB / "tables/claim_ledger.csv"
    if not canonical_claims.is_file() or not publication_claims.is_file():
        errors.append("canonical/publication claim ledger missing")
        claim_by_id: dict[str, dict[str, str]] = {}
    else:
        if canonical_claims.read_bytes() != publication_claims.read_bytes():
            errors.append("publication/tables/claim_ledger.csv diverges from docs/claim_ledger.csv")
        _, claim_rows = read_csv(canonical_claims)
        claim_by_id = {row.get("claim_id", "").strip(): row for row in claim_rows}

    # Final figures must be actual files with machine-readable source data,
    # hashes and canonical claim IDs.
    fig_manifest = PUB / "figures/MANIFEST.csv"
    fig_fields, fig_rows = read_csv(fig_manifest)
    final_fig_rows = [r for r in fig_rows if r.get("path", "").startswith("final/")]
    missing_fields = FINAL_FIGURE_REQUIRED_COLUMNS.difference(fig_fields)
    if missing_fields:
        errors.append(
            "publication/figures/MANIFEST.csv lacks submission fields: "
            + ", ".join(sorted(missing_fields))
        )
    if not final_fig_rows:
        errors.append("figure manifest contains no final/ rows")

    for row in final_fig_rows:
        rel = row.get("path", "").strip()
        label = f"figure {rel or '<missing path>'}"
        if row.get("status", "").strip() != "FINAL":
            errors.append(f"{label}: status must be FINAL")
        artifact = PUB / "figures" / rel
        if not artifact.is_file():
            errors.append(f"{label}: final artifact missing")
        elif row.get("sha256", "").strip():
            observed = sha256_file(artifact)
            expected = row["sha256"].strip().lower()
            if observed != expected:
                errors.append(f"{label}: SHA-256 mismatch")

        source_token = row.get("source_path", "").strip()
        source = resolve_repo_source(source_token)
        if source is None or not source.is_file():
            errors.append(f"{label}: source_path is not an existing repository file")
        else:
            if source.suffix.lower() not in SOURCE_DATA_SUFFIXES:
                errors.append(f"{label}: source_path is not machine-readable source data")
            expected_source = row.get("source_sha256", "").strip().lower()
            if not expected_source:
                errors.append(f"{label}: source_sha256 missing")
            elif sha256_file(source) != expected_source:
                errors.append(f"{label}: source SHA-256 mismatch")

        claim_ids = [
            tok.strip()
            for tok in row.get("claim_ids", "").replace(";", ",").split(",")
            if tok.strip()
        ]
        if not claim_ids:
            errors.append(f"{label}: no claim_ids")
        for claim_id in claim_ids:
            claim = claim_by_id.get(claim_id)
            if claim is None:
                errors.append(f"{label}: unknown claim_id {claim_id}")
                continue
            status = claim.get("status", "").strip().upper()
            allowed = claim.get("allowed_status_validated", "").strip().upper()
            if status in FORBIDDEN_CLAIM_STATUS or allowed != "YES":
                errors.append(
                    f"{label}: claim {claim_id} is not authorised "
                    f"(status={status or 'EMPTY'}, allowed={allowed or 'EMPTY'})"
                )
            for required in ("source_manifest", "source_commit", "ci_status"):
                if not claim.get(required, "").strip():
                    errors.append(f"{label}: claim {claim_id} lacks {required}")

    # Final tables have the same provenance requirements.
    table_manifest = PUB / "tables/MANIFEST.csv"
    table_fields, table_rows = read_csv(table_manifest)
    final_table_rows = [r for r in table_rows if r.get("path", "").startswith("final/")]
    missing_fields = FINAL_TABLE_REQUIRED_COLUMNS.difference(table_fields)
    if missing_fields:
        errors.append(
            "publication/tables/MANIFEST.csv lacks submission fields: "
            + ", ".join(sorted(missing_fields))
        )
    if not final_table_rows:
        errors.append("table manifest contains no final/ rows")

    for row in final_table_rows:
        rel = row.get("path", "").strip()
        label = f"table {rel or '<missing path>'}"
        if row.get("status", "").strip() != "FINAL":
            errors.append(f"{label}: status must be FINAL")
        artifact = PUB / "tables" / rel
        if not artifact.is_file():
            errors.append(f"{label}: final artifact missing")
        elif row.get("sha256", "").strip():
            if sha256_file(artifact) != row["sha256"].strip().lower():
                errors.append(f"{label}: SHA-256 mismatch")

        source_token = row.get("source_path", "").strip()
        source = resolve_repo_source(source_token)
        if source is None or not source.is_file():
            errors.append(f"{label}: source_path is not an existing repository file")
        else:
            expected_source = row.get("source_sha256", "").strip().lower()
            if not expected_source:
                errors.append(f"{label}: source_sha256 missing")
            elif sha256_file(source) != expected_source:
                errors.append(f"{label}: source SHA-256 mismatch")

        claim_ids = [
            tok.strip()
            for tok in row.get("claim_ids", "").replace(";", ",").split(",")
            if tok.strip()
        ]
        if not claim_ids:
            errors.append(f"{label}: no claim_ids")
        for claim_id in claim_ids:
            claim = claim_by_id.get(claim_id)
            if claim is None:
                errors.append(f"{label}: unknown claim_id {claim_id}")
                continue
            status = claim.get("status", "").strip().upper()
            allowed = claim.get("allowed_status_validated", "").strip().upper()
            if status in FORBIDDEN_CLAIM_STATUS or allowed != "YES":
                errors.append(
                    f"{label}: claim {claim_id} is not authorised "
                    f"(status={status or 'EMPTY'}, allowed={allowed or 'EMPTY'})"
                )

    # Submission source should contain no explicit publication-hold blocks.
    hold_files: list[str] = []
    for tex in (PUB / "chapters").glob("*.tex"):
        if "\\publicationhold" in tex.read_text(encoding="utf-8"):
            hold_files.append(str(tex.relative_to(REPO)))
    if hold_files:
        errors.append("publication-hold blocks remain in: " + ", ".join(sorted(hold_files)))

    # Exact-head build binding + PDF byte identity.
    receipt_path = PUB / "BUILD_RECEIPT.json"
    pdf_path = PUB / "paper.pdf"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"cannot parse BUILD_RECEIPT.json: {exc}")
        receipt = {}

    receipt_status = str(receipt.get("scientific_status", ""))
    if receipt_status != "SUBMISSION_READY":
        errors.append(
            "BUILD_RECEIPT scientific_status must be SUBMISSION_READY, "
            f"got {receipt_status or 'EMPTY'}"
        )
    head = current_git_head()
    receipt_head = str(receipt.get("source_repository_head", "")).strip()
    if not receipt_head:
        errors.append("BUILD_RECEIPT source_repository_head missing")
    elif head is None:
        errors.append("cannot determine current git HEAD for exact-head receipt check")
    elif receipt_head != head:
        errors.append(
            f"BUILD_RECEIPT head {receipt_head} does not match current HEAD {head}"
        )
    if not pdf_path.is_file():
        errors.append("publication/paper.pdf missing")
    else:
        expected_pdf = str(receipt.get("pdf_sha256", "")).strip().lower()
        if not expected_pdf:
            errors.append("BUILD_RECEIPT pdf_sha256 missing")
        elif sha256_file(pdf_path) != expected_pdf:
            errors.append("paper.pdf SHA-256 does not match BUILD_RECEIPT")

    if errors:
        print("SUBMISSION_READINESS_FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("SUBMISSION_READINESS_PASS")
    print(
        "Mechanical evidence gate passed; independent physics/statistics review is still required."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
