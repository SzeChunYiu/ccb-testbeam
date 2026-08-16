from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "broken_link_checker.py"


def load_module():
    spec = importlib.util.spec_from_file_location("broken_link_checker", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_checker(root: Path, json_out: Path | None = None):
    command = [sys.executable, str(SCRIPT), "--root", str(root)]
    if json_out is not None:
        command.extend(["--json-out", str(json_out)])
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_valid_local_external_and_fragment_links_pass(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text("# Target\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[local](docs/target.md) [web](https://example.org) [self](#section)\n",
        encoding="utf-8",
    )

    result = load_module().audit_markdown_links(tmp_path)

    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0
    assert result["markdown_files"] == 2
    assert result["links_seen"] == 3
    assert result["local_links_checked"] == 1


def test_missing_link_returns_structured_finding_and_clean_summary(tmp_path):
    (tmp_path / "README.md").write_text("[missing](docs/nope.md)\n", encoding="utf-8")
    json_out = tmp_path / "result.json"

    completed = run_checker(tmp_path, json_out)
    payload = json.loads(json_out.read_text(encoding="utf-8"))

    assert completed.returncode == 1
    assert "1 Markdown link finding(s) found." in completed.stdout
    assert "NameError" not in completed.stderr
    assert payload["status"] == "FLAWED"
    assert payload["findings"][0]["code"] == "MISSING_TARGET"
    assert payload["findings"][0]["resolved"] == "docs/nope.md"


def test_invalid_utf8_is_controlled_and_does_not_hide_bytes(tmp_path):
    (tmp_path / "bad.md").write_bytes(b"# bad\n\xa3\n")

    completed = run_checker(tmp_path)

    assert completed.returncode == 1
    assert "INVALID_UTF8" in completed.stdout
    assert "UnicodeDecodeError" not in completed.stderr
    result = load_module().audit_markdown_links(tmp_path)
    assert result["findings"][0]["code"] == "INVALID_UTF8"
    assert "byte 6" in result["findings"][0]["detail"]


def test_repository_escape_is_rejected_even_when_target_exists(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (root / "README.md").write_text("[outside](../outside.md)\n", encoding="utf-8")

    result = load_module().audit_markdown_links(root)

    assert result["status"] == "FLAWED"
    assert result["findings"][0]["code"] == "TARGET_ESCAPES_ROOT"


def test_percent_encoded_local_path_resolves(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "space name.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[encoded](docs/space%20name.md#section)\n", encoding="utf-8"
    )

    result = load_module().audit_markdown_links(tmp_path)

    assert result["status"] == "VALIDATED"
    assert result["local_links_checked"] == 1


def test_json_output_is_atomic_and_deterministic(tmp_path):
    (tmp_path / "README.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    json_out = tmp_path / "artifacts" / "result.json"

    first = run_checker(tmp_path, json_out)
    first_bytes = json_out.read_bytes()
    second = run_checker(tmp_path, json_out)

    assert first.returncode == second.returncode == 1
    assert json_out.read_bytes() == first_bytes
    assert not (json_out.parent / ".result.json.tmp").exists()
