#!/usr/bin/env python3
"""Publish the Cluster E canonical claim front door from tracked sources."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from io import StringIO
from pathlib import Path

POLICY = "CLUSTERE_HEADLINES_MUST_BIND_CANONICAL_LEDGER_AND_FULL_PROVENANCE"
INPUT_POLICY = "INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS"
LEDGER = "docs/claim_ledger.csv"
SOURCES = {
    "CL-013": "reports/mv0_calibration_1782677847/calibration.json",
    "CL-021": "reports/mv3_stopping_v3_1782679272/mv3_summary.json",
    "CL-022": "reports/mv6_representation_1782678362/mv6_representation_summary.json",
}
DIAGNOSTIC = "reports/studies/clusterD/mv_runs/mv3/mv3_summary.json"
PRODUCER = "scripts/clusterE/clusterE_canonical_frontdoor.py"


class ContractError(RuntimeError):
    """Controlled front-door contract failure."""


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(f"GIT_FAILED:{exc}") from exc


def _git_blob_sha1(raw: bytes) -> str:
    """Return the Git blob object ID for exactly ``raw`` bytes."""
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _read(root: Path, rel: str, commit: str) -> tuple[str, dict[str, object]]:
    """Read once and require those exact bytes to equal ``commit:rel``."""
    raw = (root / rel).read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractError(f"INVALID_UTF8:{rel}") from exc

    measured_blob = _git_blob_sha1(raw)
    try:
        commit_blob = _git(root, "rev-parse", f"{commit}:{rel}")
    except ContractError as exc:
        raise ContractError(f"COMMIT_PATH_UNAVAILABLE:{rel}") from exc
    if re.fullmatch(r"[0-9a-f]{40}", commit_blob) is None:
        raise ContractError(f"INVALID_COMMIT_BLOB:{rel}")
    if measured_blob != commit_blob:
        raise ContractError(f"INPUT_NOT_AT_BASE_COMMIT:{rel}")

    return text, {
        "algorithm": "git_blob_sha1",
        "digest": measured_blob,
        "commit_blob_digest": commit_blob,
        "commit": commit,
        "commit_match": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "snapshot_policy": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        "authorization_policy": INPUT_POLICY,
    }


def _json(text: str, rel: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError(f"INVALID_JSON:{rel}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON_ROOT_NOT_OBJECT:{rel}")
    return value


def _claims(text: str) -> dict[str, dict[str, str]]:
    rows = list(csv.reader(text.splitlines()))
    if not rows or len(rows[0]) != 43:
        raise ContractError("LEDGER_HEADER_WIDTH")
    out: dict[str, dict[str, str]] = {}
    for line, row in enumerate(rows[1:], 2):
        if len(row) != 43:
            raise ContractError(f"LEDGER_ROW_WIDTH:{line}")
        item = dict(zip(rows[0], row, strict=True))
        claim = item["claim_id"]
        if not claim or claim in out:
            raise ContractError(f"DUPLICATE_OR_EMPTY_CLAIM:{claim}")
        out[claim] = item
    return out


def _require(row: dict[str, str], claim: str, **expected: str) -> None:
    for field, value in expected.items():
        if row.get(field) != value:
            raise ContractError(f"CLAIM_MISMATCH:{claim}.{field}")


def _validate(claims: dict[str, dict[str, str]], source: dict[str, dict]) -> None:
    _require(
        claims["CL-013"],
        "CL-013",
        current_value="92",
        unit="ADC/MeV",
        syst_unc="28",
        truth_type="data_mc_calibration_proxy",
        status="GATED",
        source_data=SOURCES["CL-013"],
    )
    _require(
        claims["CL-021"],
        "CL-021",
        current_value="68269.40598948313",
        truth_type="legacy_data_mc_profile_diagnostic",
        status="FLAWED",
        source_data=SOURCES["CL-021"],
    )
    _require(
        claims["CL-022"],
        "CL-022",
        current_value="0.003232254011764034",
        numerator="283",
        denominator="87555",
        truth_type="mc_truth_only",
        status="TRUTH_LEVEL_MC_ONLY",
        source_data=SOURCES["CL-022"],
    )
    calibration = source["CL-013"].get("calibration", {})
    if (
        calibration.get("gain_adc_per_mev") != 92.0
        or calibration.get("gain_systematic_unc_pct") != 30
    ):
        raise ContractError("CL013_SOURCE_MISMATCH")
    if source["CL-021"].get("chi2_per_ndf") != 68269.40598948313:
        raise ContractError("CL021_SOURCE_VALUE")
    mv6 = source["CL-022"]
    if (
        mv6.get("n_tracks") != 87555
        or mv6.get("morphology_counts", {}).get("early_peak") != 283
        or mv6.get("anomaly_frac_total") != 0.003232254011764034
    ):
        raise ContractError("CL022_SOURCE_MISMATCH")


def _atomic(path: Path, raw: bytes, inputs: list[Path]) -> None:
    if any(path.resolve(strict=False) == item.resolve(strict=False) for item in inputs):
        raise ContractError(f"OUTPUT_ALIASES_INPUT:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except Exception as exc:
        Path(name).unlink(missing_ok=True)
        raise ContractError(f"PUBLICATION_FAILED:{path}") from exc
    if path.read_bytes() != raw:
        raise ContractError(f"PUBLICATION_VERIFY_FAILED:{path}")


atomic_write = _atomic


def _csv(rows: list[list[str]]) -> bytes:
    stream = StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    return stream.getvalue().encode()


def _docs(rerun: float, commit: str, stamp: str) -> tuple[str, str]:
    body = "\n".join(
        [
            "## Canonical claims",
            "",
            "| Claim | Exact statement | Status | Limitation |",
            "|---|---|---|---|",
            (
                "| CL-013 | **92 ADC/MeV** with **28 ADC/MeV** heuristic "
                "envelope | **GATED** | Not a confidence interval; "
                "`BLK-MV0-001` remains. |"
            ),
            (
                "| CL-021 | Pearson chi2/ndf = **68269.40598948313** | "
                "**FLAWED** | Legacy diagnostic, not accepted closure; "
                "`BLK-MV3-LEGACY-001` remains. |"
            ),
            (
                "| CL-022 | **283/87555** = **0.003232254011764034** "
                "early-peak morphology rate | **TRUTH_LEVEL_MC_ONLY** | "
                "Total truth-MC rate, not C12 identity; `AUD-ANOM-001` remains. |"
            ),
            "",
            "## Distinct diagnostics",
            "",
            (
                "The later Cluster D MV3 rerun reports chi2/ndf = "
                f"**{rerun}** and does **not supersede CL-021**. The former "
                "MV0 v1 value **110 ADC/MeV** does **not supersede CL-013**. "
                "Early-peak species composition does not replace CL-022 "
                "**283/87555** and does not identify beam data as C12."
            ),
            "",
            (
                f"Generated at `{stamp}` from base commit `{commit}`. Full Git "
                "blob and SHA-256 identities are in "
                "`reports/studies/clusterE/provenance.json`. This validates "
                "claim binding only; no production calibration, accepted "
                "closure, C12 data identity, or detector performance is "
                "established."
            ),
            "",
        ]
    )
    summary = (
        "# Cluster E canonical synthesis front door\n\n"
        "![Canonical claim binding](VIS-CLAIM-001_claim_dashboard.svg)\n\n"
        + body
        + "\nHistorical Cluster E PNGs are diagnostics, not claim-authorizing artifacts.\n"
    )
    dashboard = (
        "# CCB Test-Beam — Canonical Project Dashboard\n\n"
        "![Canonical claim binding](studies/clusterE/"
        "VIS-CLAIM-001_claim_dashboard.svg)\n\n"
        + body
        + "\nThe prior `PROJECT_DASHBOARD_OVERVIEW.png` is historical.\n"
    )
    return summary, dashboard


def build(root: Path, commit: str, stamp: str) -> dict:
    root = root.resolve()
    if (
        re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or _git(root, "rev-parse", "HEAD") != commit
    ):
        raise ContractError("BASE_COMMIT_MISMATCH")
    rels = [LEDGER, *SOURCES.values(), DIAGNOSTIC, PRODUCER]
    text: dict[str, str] = {}
    identities: dict[str, dict[str, object]] = {}
    for rel in rels:
        text[rel], identities[rel] = _read(root, rel, commit)
    claims = _claims(text[LEDGER])
    source = {claim: _json(text[rel], rel) for claim, rel in SOURCES.items()}
    _validate(claims, source)
    rerun = _json(text[DIAGNOSTIC], DIAGNOSTIC).get("chi2_per_ndf")
    if not isinstance(rerun, (int, float)) or rerun == 68269.40598948313:
        raise ContractError("DISTINCT_DIAGNOSTIC_MISSING")
    summary, dashboard = _docs(float(rerun), commit, stamp)
    table = [
        [
            "claim",
            "headline",
            "evidence_class",
            "status",
            "source",
            "figure",
            "claim_id",
        ],
        [
            "ADC gain (data/MC proxy, MV0)",
            "92 ADC/MeV; 28 ADC/MeV heuristic envelope",
            "DATA_MC_CALIBRATION_PROXY",
            "GATED",
            "CL-013",
            "VIS-CLAIM-001_claim_dashboard.svg",
            "CL-013",
        ],
        [
            "Stopping-depth data/MC closure",
            "Pearson chi2/ndf = 68269.40598948313",
            "LEGACY_DIAGNOSTIC",
            "FLAWED",
            "CL-021",
            "VIS-CLAIM-001_claim_dashboard.svg",
            "CL-021",
        ],
        [
            "Anomaly / C12 identity",
            "283/87555 = 0.003232254011764034 truth-MC morphology",
            "TRUTH_LEVEL_MC_ONLY",
            "TRUTH_LEVEL_MC_ONLY",
            "CL-022",
            "VIS-CLAIM-001_claim_dashboard.svg",
            "CL-022",
        ],
        [
            "Cluster D MV3 rerun diagnostic",
            f"Pearson chi2/ndf = {rerun}; distinct",
            "DIAGNOSTIC_ONLY",
            "FLAWED",
            DIAGNOSTIC,
            "VIS-CLAIM-001_claim_dashboard.svg",
            "",
        ],
    ]
    provenance = {
        "schema": "ccb-clusterE-provenance/3",
        "policy": POLICY,
        "input_authorization_policy": INPUT_POLICY,
        "base_commit": commit,
        "generated_utc": stamp,
        "producer": PRODUCER,
        "input_identities": identities,
    }
    metrics = {
        "schema": "ccb-clusterE-canonical-frontdoor/3",
        "policy": POLICY,
        "input_authorization_policy": INPUT_POLICY,
        "base_commit": commit,
        "canonical_claims": {key: claims[key] for key in SOURCES},
        "distinct_diagnostics": {
            "clusterD_mv3": {
                "chi2_per_ndf": rerun,
                "interpretation": "does not supersede CL-021",
            }
        },
    }
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360">'
        '<rect width="1200" height="360" fill="white"/>'
        '<g font-family="sans-serif">'
        '<text x="30" y="40" font-size="26" font-weight="bold">'
        "Cluster E canonical claim binding</text>"
        '<text x="40" y="105" font-size="20">'
        "CL-013: 92 ADC/MeV; 28 ADC/MeV heuristic envelope — GATED</text>"
        '<text x="40" y="180" font-size="20">'
        "CL-021: 68269.40598948313 — FLAWED legacy diagnostic</text>"
        '<text x="40" y="255" font-size="20">'
        "CL-022: 283/87555 = 0.003232254011764034 — "
        "TRUTH_LEVEL_MC_ONLY</text>"
        '<text x="40" y="320" font-size="16">'
        f"Distinct MV3 rerun {rerun}; does not supersede CL-021.</text>"
        "</g></svg>\n"
    )
    out = root / "reports/studies/clusterE"
    outputs = {
        out / "SUMMARY.md": summary.encode(),
        root / "reports/PROJECT_DASHBOARD.md": dashboard.encode(),
        out / "claims_table.csv": _csv(table),
        out / "metrics.json": (
            json.dumps(metrics, indent=2, sort_keys=True) + "\n"
        ).encode(),
        out / "provenance.json": (
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        ).encode(),
        out / "VIS-CLAIM-001_claim_dashboard.svg": svg.encode(),
    }
    protected = [root / rel for rel in identities]
    for path, raw in outputs.items():
        _atomic(path, raw, protected)
    return {
        "status": "VALIDATED",
        "outputs": {
            str(path.relative_to(root)): hashlib.sha256(raw).hexdigest()
            for path, raw in outputs.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--generated-utc", required=True)
    args = parser.parse_args()
    try:
        result = build(args.root, args.base_commit, args.generated_utc)
    except ContractError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"{result['status']}: {len(result['outputs'])} outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
