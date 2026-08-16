"""Wave D Lane 04: dedx provenance headers fail closed for authorising use (#1058)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation.exceptions import ConfigurationError
from ccb_mc_validation.source.dedx_table_provenance import require_dedx_provenance_headers


def test_missing_headers_block_authorising(tmp_path: Path) -> None:
    path = tmp_path / "dedx.txt"
    path.write_text("1.0\t2.0\n2.0\t3.0\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="BLOCKED|#1058|missing required provenance"):
        require_dedx_provenance_headers(path, authorising=True)


def test_complete_approved_headers_pass(tmp_path: Path) -> None:
    path = tmp_path / "dedx.txt"
    path.write_text(
        "\n".join(
            [
                "# units_energy: MeV/u",
                "# units_dedx: MeV/um",
                "# material: CD2",
                "# conversion_energy: MeV/u -> MeV via 938.28/931.5 (UNVALIDATED)",
                "# conversion_dedx: um^-1 -> mm^-1 via x1000 (UNVALIDATED)",
                "# source: historical-campaign-table",
                "# status: APPROVED",
                "1.0\t2.0",
                "2.0\t3.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    headers = require_dedx_provenance_headers(path, authorising=True)
    assert headers["material"] == "CD2"


def test_non_authorising_allows_missing_headers(tmp_path: Path) -> None:
    path = tmp_path / "dedx.txt"
    path.write_text("1.0\t2.0\n2.0\t3.0\n", encoding="utf-8")
    assert require_dedx_provenance_headers(path, authorising=False) == {}
