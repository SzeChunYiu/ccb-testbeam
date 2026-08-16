from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

CONTRACT = (
    Path(__file__).parents[1]
    / "docs"
    / "contracts"
    / "deltae_event_csv_reader.json"
)


def load_dtype_contract() -> dict[str, str]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return payload["pandas_read_csv_dtype"]


def test_contract_marks_every_provenance_identifier_as_text() -> None:
    dtypes = load_dtype_contract()
    required = {
        "provenance_policy",
        "provenance_runner_version",
        "provenance_input_sha256",
        "provenance_repository_commit",
        "provenance_bridge_sha256",
        "provenance_runner_sha256",
        "provenance_generation_command",
        "provenance_python",
        "provenance_pandas",
    }
    assert required == set(dtypes)
    assert set(dtypes.values()) == {"string"}


def test_explicit_dtype_preserves_all_digit_and_leading_zero_identifiers() -> None:
    all_digit_commit = "1" * 40
    leading_zero_commit = "0" + "1" * 39
    input_digest = "2" * 64
    frame = pd.DataFrame(
        {
            "provenance_repository_commit": [all_digit_commit, leading_zero_commit],
            "provenance_input_sha256": [input_digest, input_digest],
        }
    )
    csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    loaded = pd.read_csv(io.BytesIO(csv_bytes), dtype=load_dtype_contract())

    assert loaded["provenance_repository_commit"].tolist() == [
        all_digit_commit,
        leading_zero_commit,
    ]
    assert loaded["provenance_input_sha256"].tolist() == [input_digest, input_digest]
    assert str(loaded["provenance_repository_commit"].dtype) == "string"


def test_contract_points_to_authoritative_json_bundle_metadata() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["authoritative_bundle_metadata"] == "result.json"
    assert payload["csv_artifact"] == "deltaE_E_events_data.csv"
