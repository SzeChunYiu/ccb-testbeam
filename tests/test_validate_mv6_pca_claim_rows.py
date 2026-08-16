from __future__ import annotations

import csv
import io
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit import validate_mv6_pca_claim_rows as validator


RATIOS = [
    0.6397275304111596,
    0.05803144748933653,
    0.027701235443287935,
    0.02005735713674897,
    0.01943928056747368,
    0.01915966934733869,
    0.01891806012034366,
    0.018849346397427923,
    0.018760204253971523,
    0.018666385239326882,
]

PRODUCER = '''
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
X = waves - PED
peak = X.max(axis=1, keepdims=True)
Xn = X / peak
pca = PCA(n_components=min(10, NSAMP))
Z = pca.fit_transform(Xn)
evr = pca.explained_variance_ratio_
summary["pca_explained_variance_ratio"] = evr.tolist()
summary["pca_cumulative_at_4"] = float(evr[:4].sum())
summary["pca_cumulative_at_8"] = float(evr[:8].sum())
gmm = GaussianMixture(n_components=4, random_state=SEED, n_init=3)
clu = gmm.fit_predict(Z[:, :4])
'''


def summary_text() -> str:
    return json.dumps({
        "n_events_scanned": 220000,
        "n_tracks": 87555,
        "seed": 42,
        "pca_explained_variance_ratio": RATIOS,
        "pca_cumulative_at_4": math.fsum(RATIOS[:4]),
        "pca_cumulative_at_8": math.fsum(RATIOS[:8]),
    })


def row(claim_id: str, value: str, components: int, superseded: str) -> list[str]:
    values = {field: "" for field in validator.EXPECTED_FIELDS}
    values.update({
        "claim_id": claim_id,
        "chapter": "ML",
        "section": "6",
        "claim_text": (
            "MV6 synthetic-waveform PCA cumulative explained variance at "
            f"{components} components"
        ),
        "current_value": value,
        "unit": "fraction",
        "n_events": "220000",
        "n_runs": "1",
        "n_mc": "87555",
        "truth_type": "synthetic_waveform_mc",
        "status": "TRUTH_LEVEL_MC_ONLY",
        "allowed_status_validated": "YES",
        "source_report": validator.SOURCE_REPORT,
        "source_script": validator.SOURCE_SCRIPT,
        "source_data": validator.SOURCE_DATA,
        "figure_ids": "FIG-AN-001",
        "source_commit": validator.SOURCE_COMMIT,
        "link_validated": "YES",
        "ci_status": validator.CI_STATUS,
        "supersedes": superseded,
        "notes": (
            "Source-backed fixed synthetic-waveform MC output from pedestal-subtracted, "
            "peak-normalized waveforms; not beam-data PCA and not an uncertainty claim; "
            f"supersedes {superseded}."
        ),
    })
    return [values[field] for field in validator.EXPECTED_FIELDS]


def ledger_text(value_3: str | None = None, value_8: str | None = None) -> str:
    value_3 = value_3 or repr(math.fsum(RATIOS[:3]))
    value_8 = value_8 or repr(math.fsum(RATIOS[:8]))
    handle = io.StringIO(newline="")
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(validator.EXPECTED_FIELDS)
    writer.writerow(row("CL-023", value_3, 3, "0.89"))
    writer.writerow(row("CL-024", value_8, 8, "0.997"))
    return handle.getvalue()


def test_valid_rows_match_tracked_mv6_output() -> None:
    result = validator.validate_texts(ledger_text(), summary_text(), PRODUCER)
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0
    assert result["claims"]["CL-023"]["source_value"] == math.fsum(RATIOS[:3])
    assert result["claims"]["CL-024"]["source_value"] == math.fsum(RATIOS[:8])


def test_superseded_values_fail_semantic_gate() -> None:
    result = validator.validate_texts(
        ledger_text(value_3="0.89", value_8="0.997"),
        summary_text(),
        PRODUCER,
    )
    assert result["status"] == "FLAWED"
    assert [issue["code"] for issue in result["issues"]].count("VALUE_MISMATCH") == 2


def test_width_mismatch_fails_before_field_interpretation() -> None:
    rows = list(csv.reader(io.StringIO(ledger_text())))
    rows[1].pop()
    handle = io.StringIO(newline="")
    csv.writer(handle, lineterminator="\n").writerows(rows)
    with pytest.raises(validator.ValidationError, match="expected 43"):
        validator.validate_texts(handle.getvalue(), summary_text(), PRODUCER)


def test_summary_cumulative_mismatch_fails_closed() -> None:
    payload = json.loads(summary_text())
    payload["pca_cumulative_at_8"] = 0.997
    with pytest.raises(validator.ValidationError, match="pca_cumulative_at_8"):
        validator.validate_texts(ledger_text(), json.dumps(payload), PRODUCER)


def test_missing_producer_normalization_contract_fails_closed() -> None:
    broken = PRODUCER.replace("Xn = X / peak\n", "")
    with pytest.raises(validator.ValidationError, match="Xn = X / peak"):
        validator.validate_texts(ledger_text(), summary_text(), broken)


def test_cli_writes_machine_readable_and_visual_evidence(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    summary = tmp_path / "summary.json"
    producer = tmp_path / "producer.py"
    output = tmp_path / "result.json"
    svg = tmp_path / "result.svg"
    ledger.write_text(ledger_text(), encoding="utf-8")
    summary.write_text(summary_text(), encoding="utf-8")
    producer.write_text(PRODUCER, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(Path(validator.__file__)),
            str(ledger),
            str(summary),
            str(producer),
            "--output",
            str(output),
            "--svg",
            str(svg),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "VALIDATED"
    assert "Synthetic software/provenance evidence" in svg.read_text(encoding="utf-8")


def test_cli_invalid_utf8_returns_status_2(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    summary = tmp_path / "summary.json"
    producer = tmp_path / "producer.py"
    ledger.write_bytes(bytes([0xFF]))
    summary.write_text(summary_text(), encoding="utf-8")
    producer.write_text(PRODUCER, encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(Path(validator.__file__)), str(ledger), str(summary), str(producer)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "not valid UTF-8" in completed.stderr
