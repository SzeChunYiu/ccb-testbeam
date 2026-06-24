#!/usr/bin/env python3
"""Regenerate human-facing MC validation documentation from run artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_dir(run_id: str) -> Path:
    return ROOT / "reports/mc_validation/runs" / run_id


def generate_docs(run_id: str, strict: bool = False) -> int:
    run_path = _run_dir(run_id)
    if not run_path.is_dir():
        print(f"run directory not found: {run_path}", file=sys.stderr)
        return 3

    state_path = run_path / "RUN_STATE.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}

    smoke = run_path / "SMOKE_GATE.json"
    gate = json.loads(smoke.read_text()) if smoke.is_file() else {}

    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    marker_start = "<!-- mc-validation-generated:start -->"
    marker_end = "<!-- mc-validation-generated:end -->"

    block = f"""{marker_start}
## MC validation execution status (auto-generated)

- **Run ID:** `{run_id}`
- **Generated:** {generated_at}
- **Git SHA:** `{state.get('git_sha', 'unknown')}`
- **Profile:** `{state.get('profile', 'unknown')}`
- **Smoke gate:** `{gate.get('status', 'NOT_RUN')}` ({gate.get('mode', 'unknown')})

> Numbers in this block are resolved from validated run artifacts only.
> See `reports/mc_validation/runs/{run_id}/` for manifests and study outputs.

{marker_end}"""

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if marker_start in text:
        pre, rest = text.split(marker_start, 1)
        _, post = rest.split(marker_end, 1)
        readme.write_text(pre + block + post, encoding="utf-8")
    else:
        readme.write_text(text.rstrip() + "\n\n" + block + "\n", encoding="utf-8")

    exec_dir = ROOT / "reports/mc_validation/execution"
    exec_dir.mkdir(parents=True, exist_ok=True)
    (exec_dir / "DOCS_GENERATION.md").write_text(
        f"# Documentation generation\n\nRun `{run_id}` at {generated_at}\n",
        encoding="utf-8",
    )

    mv9 = run_path / "MV9" / "MV9_SYNTHESIS.md"
    if mv9.is_file():
        dest = ROOT / "reports" / "mc_validation" / "MV9_SYNTHESIS.md"
        dest.write_text(mv9.read_text(encoding="utf-8"), encoding="utf-8")

    if strict and gate.get("status") != "PASS":
        print("strict mode: smoke gate not PASS", file=sys.stderr)
        return 5
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    return generate_docs(args.run_id, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
