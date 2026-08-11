"""Tests for PUBLIC_CLAIM_AUTHORITY contract (#969)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import validate_public_claim_authority as v


def test_authority_schema_and_readme_pass():
    errs = v.validate(REPO)
    assert errs == [], errs


def test_stale_absent_phrase_fails(tmp_path: Path):
    auth = json.loads((REPO / "docs/contracts/PUBLIC_CLAIM_AUTHORITY.json").read_text(encoding="utf-8"))
    (tmp_path / "docs/contracts").mkdir(parents=True)
    (tmp_path / "docs/contracts/PUBLIC_CLAIM_AUTHORITY.json").write_text(json.dumps(auth), encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "raw beam ROOT (`hrdb_run_*.root`) is not staged on LUNARC\n",
        encoding="utf-8",
    )
    errs = v.validate(tmp_path)
    assert any(e.startswith("FORBIDDEN_DATA_LOCATION_PHRASE") for e in errs)


def test_validated_with_blockers_fails(tmp_path: Path):
    auth = {
        "data_location": {"forbidden_readme_phrases": [], "required_readme_phrases": []},
        "headlines": [{
            "short_name": "x",
            "claim_id": "CL-X",
            "truth_type": "DATA_MEASUREMENT",
            "authorization_status": "VALIDATED",
            "blocking_issues": ["#999"],
            "value": "1",
        }],
    }
    (tmp_path / "docs/contracts").mkdir(parents=True)
    (tmp_path / "docs/contracts/PUBLIC_CLAIM_AUTHORITY.json").write_text(json.dumps(auth), encoding="utf-8")
    (tmp_path / "README.md").write_text("ok", encoding="utf-8")
    errs = v.validate(tmp_path)
    assert any(e.startswith("VALIDATED_WITH_OPEN_BLOCKERS") for e in errs)
