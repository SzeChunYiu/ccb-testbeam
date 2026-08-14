from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "publication"
    / "scripts"
    / "validate_submission_readiness.py"
)


def load_validator():
    spec = importlib.util.spec_from_file_location("ccb_submission_validator", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_ready_fixture(root: Path) -> tuple[Path, Path]:
    pub = root / "publication"
    (pub / "figures" / "final").mkdir(parents=True)
    (pub / "figures" / "source_data").mkdir(parents=True)
    (pub / "tables" / "final").mkdir(parents=True)
    (pub / "tables" / "source_data").mkdir(parents=True)
    (pub / "chapters").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)

    (pub / "STATUS.md").write_text("**State:** `SUBMISSION_READY`\n", encoding="utf-8")
    (pub / "chapters" / "00_abstract.tex").write_text(
        "\\section{Abstract}\nFinal text.\n", encoding="utf-8"
    )

    claim_fields = [
        "claim_id",
        "status",
        "allowed_status_validated",
        "source_manifest",
        "source_commit",
        "ci_status",
    ]
    claim_rows = [
        {
            "claim_id": "CL-X",
            "status": "VALIDATED",
            "allowed_status_validated": "YES",
            "source_manifest": "results/final/manifest.json",
            "source_commit": "abc",
            "ci_status": "COMPLETE",
        }
    ]
    write_csv(root / "docs" / "claim_ledger.csv", claim_fields, claim_rows)
    (pub / "tables" / "claim_ledger.csv").write_bytes(
        (root / "docs" / "claim_ledger.csv").read_bytes()
    )

    figure = pub / "figures" / "final" / "figure.pdf"
    figure.write_bytes(b"%PDF-test")
    figure_source = pub / "figures" / "source_data" / "figure.csv"
    figure_source.write_text("x,y\n1,2\n", encoding="utf-8")
    figure_fields = [
        "path",
        "status",
        "source_path",
        "publication_role",
        "sha256",
        "source_sha256",
        "claim_ids",
        "evidence_class",
    ]
    write_csv(
        pub / "figures" / "MANIFEST.csv",
        figure_fields,
        [
            {
                "path": "final/figure.pdf",
                "status": "FINAL",
                "source_path": "publication/figures/source_data/figure.csv",
                "publication_role": "final result",
                "sha256": sha256(figure),
                "source_sha256": sha256(figure_source),
                "claim_ids": "CL-X",
                "evidence_class": "DATA_MEASUREMENT",
            }
        ],
    )

    table = pub / "tables" / "final" / "result.csv"
    table.write_text("value\n1\n", encoding="utf-8")
    table_source = pub / "tables" / "source_data" / "result.csv"
    table_source.write_text("value\n1\n", encoding="utf-8")
    table_fields = [
        "path",
        "status",
        "source_path",
        "role",
        "sha256",
        "source_sha256",
        "claim_ids",
    ]
    write_csv(
        pub / "tables" / "MANIFEST.csv",
        table_fields,
        [
            {
                "path": "final/result.csv",
                "status": "FINAL",
                "source_path": "publication/tables/source_data/result.csv",
                "role": "final result",
                "sha256": sha256(table),
                "source_sha256": sha256(table_source),
                "claim_ids": "CL-X",
            }
        ],
    )

    pdf = pub / "paper.pdf"
    pdf.write_bytes(b"%PDF-paper")
    (pub / "BUILD_RECEIPT.json").write_text(
        json.dumps(
            {
                "scientific_status": "SUBMISSION_READY",
                "source_repository_head": "abc",
                "pdf_sha256": sha256(pdf),
            }
        ),
        encoding="utf-8",
    )
    return root, pub


def test_submission_validator_passes_complete_fixture(tmp_path: Path, monkeypatch, capsys):
    module = load_validator()
    root, pub = build_ready_fixture(tmp_path)
    monkeypatch.setattr(module, "REPO", root)
    monkeypatch.setattr(module, "PUB", pub)
    monkeypatch.setattr(module, "current_git_head", lambda: "abc")

    assert module.main() == 0
    assert "SUBMISSION_READINESS_PASS" in capsys.readouterr().out


def test_submission_validator_fails_gated_claim(tmp_path: Path, monkeypatch, capsys):
    module = load_validator()
    root, pub = build_ready_fixture(tmp_path)

    claim_path = root / "docs" / "claim_ledger.csv"
    text = claim_path.read_text(encoding="utf-8").replace("VALIDATED,YES", "GATED,NO")
    claim_path.write_text(text, encoding="utf-8")
    (pub / "tables" / "claim_ledger.csv").write_bytes(claim_path.read_bytes())

    monkeypatch.setattr(module, "REPO", root)
    monkeypatch.setattr(module, "PUB", pub)
    monkeypatch.setattr(module, "current_git_head", lambda: "abc")

    assert module.main() == 1
    output = capsys.readouterr().out
    assert "SUBMISSION_READINESS_FAIL" in output
    assert "claim CL-X is not authorised" in output


def test_submission_validator_fails_stale_build_head(tmp_path: Path, monkeypatch, capsys):
    module = load_validator()
    root, pub = build_ready_fixture(tmp_path)
    monkeypatch.setattr(module, "REPO", root)
    monkeypatch.setattr(module, "PUB", pub)
    monkeypatch.setattr(module, "current_git_head", lambda: "different")

    assert module.main() == 1
    assert "does not match current HEAD" in capsys.readouterr().out
