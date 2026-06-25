"""Claim ledger and staleness guard for MC validation artifacts."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required claim-ledger input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required claim-ledger input: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _metric(row: dict[str, str]) -> str:
    for key in ("hgb_auc", "proton_ekin_recon_res68", "n_sample_I"):
        if row.get(key):
            return f"{key}={row[key]}"
    return "no headline metric"


def generate_claim_ledger(run_root: Path) -> dict[str, Any]:
    """Generate a conservative claim ledger from validated frozen artifacts."""
    run_root = Path(run_root)
    validation = _load_json(run_root / "VALIDATION.json")
    audit = _load_json(run_root / "QA_RELEASE_AUDIT.json")
    rows = _load_rows(run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv")
    run_id = str(validation.get("run_id") or run_root.name)
    generated = datetime.now(tz=timezone.utc).isoformat()
    claims: list[dict[str, Any]] = []

    validation_status = validation.get("status")
    claims.append(
        {
            "id": "CLAIM-ARTIFACT-VALIDATION",
            "status": "SUPPORTED" if validation_status == "PASS" else "BLOCKED",
            "statement": "The selected run has internally consistent frozen MV1-MV3/MV9 artifacts.",
            "evidence": ["VALIDATION.json", "VALIDATION_SUMMARY.md"],
            "limitations": "Does not by itself prove full release readiness or complete detector-physics validation.",
        }
    )
    for row in rows:
        study = row.get("study", "")
        status = row.get("status", "")
        claims.append(
            {
                "id": f"CLAIM-{study}-SUMMARY",
                "status": "SUPPORTED" if status == "PRODUCTION" else "BLOCKED",
                "statement": f"{study} has a frozen artifact-summary metric ({_metric(row)}) for run {run_id}.",
                "evidence": ["reports/mc_validation/summary/metrics_table.csv"],
                "limitations": "Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates.",
            }
        )
    for study in ("MV4", "MV5", "MV6", "MV7", "MV8"):
        claims.append(
            {
                "id": f"CLAIM-{study}-RELEASE",
                "status": "BLOCKED",
                "statement": f"{study} production validation is complete.",
                "evidence": [],
                "limitations": "Blocked pending calibrated digitized MC/systematic production artifacts.",
            }
        )
    claims.append(
        {
            "id": "CLAIM-FINAL-RELEASE",
            "status": "SUPPORTED" if audit.get("release_ready") is True else "BLOCKED",
            "statement": "The MC validation package is final-release ready.",
            "evidence": ["QA_RELEASE_AUDIT.json", "publication/PUBLICATION_MANIFEST.json"],
            "limitations": "Release requires every QA audit gate to pass; current blocked gates must remain visible.",
        }
    )
    blocked = [claim for claim in claims if claim["status"] != "SUPPORTED"]
    payload = {
        "status": "PASS",
        "scope": "claim-ledger",
        "release_claims_allowed": len(blocked) == 0,
        "run_id": run_id,
        "claims": claims,
        "blocked_claim_count": len(blocked),
        "generated_at": generated,
    }
    out_dir = run_root / "reports" / "mc_validation" / "claims"
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "CLAIM_LEDGER.json", payload)
    lines = [
        "# MC validation claim ledger",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Release claims allowed:** `{payload['release_claims_allowed']}`",
        f"- **Blocked claim count:** `{len(blocked)}`",
        "",
        "| Claim | Status | Statement | Limitations |",
        "|---|---:|---|---|",
    ]
    for claim in claims:
        lines.append(f"| {claim['id']} | {claim['status']} | {claim['statement']} | {claim['limitations']} |")
    (out_dir / "CLAIM_LEDGER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
