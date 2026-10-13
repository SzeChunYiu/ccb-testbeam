"""Pin the real publication package's submission-readiness violation set.

The package is intentionally NOT submission-ready: four artifacts cite gated
claims (CL-029 / CL-1318-002 / CL-1320-002), STATUS.md holds, and the build
receipt predates the current head. Everything else -- manifest schema, artifact
and source SHA-256s, machine-readable sources, claim resolution and claim
provenance -- must stay clean. These tests fail whenever the *kind* of
violations changes, so a new bookkeeping defect cannot hide behind the known
scientific blockers, and a resolved blocker forces this pin to be updated in
the same PR that resolves it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "publication" / "scripts" / "validate_submission_readiness.py"
SHA_RE = re.compile(r"\b[0-9a-f]{40,64}\b")

EXPECTED_VIOLATIONS = {
    "publication/STATUS.md still declares a non-submission-ready state",
    "figure final/data_depth_profile.pdf: claim CL-1318-002 is not authorised "
    "(status=GATED, allowed=NO)",
    "figure final/timing_b4_b6_residual.pdf: claim CL-1320-002 is not authorised "
    "(status=GATED, allowed=NO)",
    "table final/heldout_energy_reconstruction_summary_E_raw.csv: claim CL-029 "
    "is not authorised (status=GATED, allowed=YES)",
    "table final/heldout_energy_reconstruction_summary_E_vis.csv: claim CL-029 "
    "is not authorised (status=GATED, allowed=YES)",
    "BUILD_RECEIPT scientific_status must be SUBMISSION_READY, "
    "got FAIL_CLOSED_NOT_SUBMISSION_READY",
    "BUILD_RECEIPT head <sha> does not match current HEAD <sha>",
}

# Bookkeeping defect classes that the 2026-08-17 manifest wiring eliminated.
# Any reappearance is a regression regardless of which artifact triggers it.
BOOKKEEPING_SUBSTRINGS = (
    "lacks submission fields",
    "status must be FINAL",
    "sha256 missing",
    "SHA-256 mismatch",
    "source_path is not",
    "no claim_ids",
    "unknown claim_id",
    "lacks source_manifest",
    "lacks source_commit",
    "lacks ci_status",
    "has no non-README",
    "evidence_class missing",
    "final artifact missing",
    "diverges from",
    "publication-hold blocks remain",
    "contains no final/ rows",
)


def _validator_lines() -> list[str]:
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, (
        f"validator exit {proc.returncode}; expected exactly the pinned blocker set"
    )
    assert "SUBMISSION_READINESS_FAIL" in proc.stdout
    return [ln[2:] for ln in proc.stdout.splitlines() if ln.startswith("- ")]


def test_real_package_violations_are_exactly_the_known_blockers() -> None:
    normalized = {SHA_RE.sub("<sha>", ln) for ln in _validator_lines()}
    added = sorted(normalized - EXPECTED_VIOLATIONS)
    removed = sorted(EXPECTED_VIOLATIONS - normalized)
    assert not added and not removed, (
        f"submission-readiness violation set changed.\n"
        f"  new violations: {added}\n"
        f"  resolved/renamed: {removed}\n"
        f"Update EXPECTED_VIOLATIONS in the same PR that changes the package."
    )


def test_no_bookkeeping_violations_remain() -> None:
    hits = [ln for ln in _validator_lines() if any(s in ln for s in BOOKKEEPING_SUBSTRINGS)]
    assert not hits, f"bookkeeping violations must stay at zero: {hits}"
