from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
SOURCE = ROOT / "geant4/src_patch/sigma_pd_cm_190.source.json"

EXPECTED_SHA256 = "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
EXPECTED_ROWS = (
    (26.49, 6.005, 0.011),
    (31.10, 4.383, 0.007),
    (35.69, 3.123, 0.009),
    (40.24, 2.363, 0.005),
    (44.75, 1.710, 0.008),
    (49.22, 1.388, 0.004),
    (53.64, 1.037, 0.006),
    (58.01, 0.780, 0.004),
    (62.32, 0.624, 0.005),
    (66.58, 0.523, 0.003),
    (70.77, 0.429, 0.003),
    (74.90, 0.341, 0.002),
    (78.75, 0.273, 0.002),
    (84.73, 0.222, 0.001),
    (90.73, 0.180, 0.001),
    (96.74, 0.164, 0.001),
    (102.76, 0.137, 0.001),
    (108.80, 0.129, 0.001),
    (114.85, 0.129, 0.001),
    (120.91, 0.126, 0.001),
    (126.99, 0.146, 0.001),
    (133.08, 0.156, 0.001),
    (139.17, 0.180, 0.001),
    (145.28, 0.201, 0.001),
    (151.40, 0.264, 0.001),
    (157.52, 0.305, 0.002),
    (162.62, 0.351, 0.003),
    (169.78, 0.446, 0.002),
)


def _parse_rows(text: str) -> tuple[tuple[float, float, float], ...]:
    rows: list[tuple[float, float, float]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"line {line_number}: expected exactly three columns")
        rows.append(tuple(float(field) for field in fields))
    return tuple(rows)


def test_sigma_pd_cm_190_exact_bytes_and_table_vi_projection() -> None:
    raw = TABLE.read_bytes()
    assert len(raw) == 640
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256

    rows = _parse_rows(raw.decode("ascii"))
    assert rows == EXPECTED_ROWS
    assert len(rows) == 28
    assert rows[0][0] == 26.49
    assert rows[-1][0] == 169.78
    assert all(left[0] < right[0] for left, right in zip(rows, rows[1:]))
    assert all(sigma > 0.0 and stat_uncertainty > 0.0 for _, sigma, stat_uncertainty in rows)


def test_sigma_pd_cm_190_source_sidecar_binds_frame_units_and_history() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    assert source["schema_version"] == "ccb_cross_section_table_source_v1"
    assert source["data_sha256"] == EXPECTED_SHA256
    assert source["data_bytes"] == 640
    assert source["data_rows"] == 28
    assert source["incident_proton_kinetic_energy_MeV"] == 190.0
    assert source["angle_frame"] == "center_of_mass"
    assert source["angle_unit"] == "degree"
    assert source["observable"] == "differential_cross_section_dsigma_domega"
    assert source["observable_unit"] == "mb/sr"
    assert source["support_theta_cm_deg"] == [26.49, 169.78]

    citation = source["source"]
    assert citation["doi"] == "10.1103/PhysRevC.71.064004"
    assert citation["journal"] == "Physical Review C"
    assert citation["volume"] == 71
    assert citation["article"] == "064004"
    assert citation["year"] == 2005
    assert citation["table"] == "VI"

    projection = source["projection_from_source_table"]
    assert projection == [
        "theta_cm_deg",
        "dsigma_domega_mb_per_sr",
        "statistical_uncertainty_dsigma_domega_mb_per_sr",
    ]

    uncertainty = source["source_uncertainty_note"]
    assert uncertainty["point_to_point_systematic_fraction"] == pytest.approx(0.03)
    assert uncertainty["total_systematic_fraction_bound"] == "<0.045"
    assert uncertainty["systematics_encoded_in_data_file"] is False

    history = source["historical_identity"]
    assert history["s21_external_table_sha256"] == EXPECTED_SHA256
    assert history["s21b_external_table_sha256"] == EXPECTED_SHA256


def test_source_contract_fails_under_single_value_drift() -> None:
    rows = list(_parse_rows(TABLE.read_text(encoding="ascii")))
    rows[0] = (rows[0][0], rows[0][1] + 0.001, rows[0][2])
    assert tuple(rows) != EXPECTED_ROWS
