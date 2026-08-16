import os
import subprocess
from pathlib import Path


def test_claim_ignores_null_existing_ticket_and_claims_oldest_open(tmp_path: Path) -> None:
    calls = tmp_path / "gh.calls"
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$CALLS_FILE"
case "$*" in
  *"issue list"*"factory:claimed"*)
    printf 'null|null|null\\n'
    ;;
  *"issue list"*"factory:open"*)
    printf '2413\\n'
    ;;
  *"label create"*)
    exit 0
    ;;
  *"issue edit 2413"*)
    exit 0
    ;;
  *"issue view 2413"*"--json labels"*)
    printf 'worker:testbeam-laptop-2\\n'
    ;;
  *"issue view 2413"*"--json title"*)
    printf 'Fix tn-ticket claim null pseudo-ticket handling\\n'
    ;;
  *"issue view 2413"*"--json body"*)
    printf 'Expected behavior: continue to the oldest open issue.\\n'
    ;;
  *)
    printf 'unexpected gh call: %s\\n' "$*" >&2
    exit 99
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["CALLS_FILE"] = str(calls)
    env["GH_TOKEN"] = "test-token"
    env["TN_TICKET_REPO"] = "owner/repo"

    proc = subprocess.run(
        ["bash", "tools/tn-ticket", "claim", "testbeam-laptop-2", "--project", "testbeam"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert proc.stderr.strip() == "2413"
    assert "# Fix tn-ticket claim null pseudo-ticket handling" in proc.stdout
    assert "null|null|null" not in proc.stdout
    assert "issue edit 2413 --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open" in calls.read_text(
        encoding="utf-8"
    )
