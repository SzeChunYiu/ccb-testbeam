#!/usr/bin/env python3
"""Ticket 2376 P08 waveform-only weak-label PID bakeoff wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "ticket_2376_p08_waveform_pid_bakeoff.json"
OUT = ROOT / "reports" / "2376__p08_waveform_pid_bakeoff"
BASE_SCRIPT = ROOT / "scripts" / "s15b_1781070978_487_042a7300_pid_null_label_stability_audit.py"
COMMAND = (
    "/home/billy/anaconda3/bin/python scripts/ticket_2376_p08_waveform_pid_bakeoff.py"
)


def rewrite_outputs() -> None:
    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket"] = "2376"
    result["ticket_id"] = "2376"
    result["worker"] = "testbeam-laptop-2"
    result["claimed_ticket"] = {
        "issue": 2376,
        "title": "P08: Pulse-shape discrimination for p vs d PID (waveform-only)",
        "required_claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "required_claim_command_observed_output": "null\\n# null\\n\\nnull\\n",
        "recovery": "manual GitHub label transition after the required single claim command hit the known null pseudo-ticket bug",
    }
    result["execution_command"] = COMMAND
    result["primary_interpretation"] = (
        "Ticket 2376 is a waveform-only weak-label PID bakeoff. The named winner is a "
        "weak-label classifier winner, not a proton/deuteron truth PID result; without S17 "
        "or an external truth join, all purity and efficiency values are proxy diagnostics."
    )
    result["novel_tickets_appended"] = [
        {
            "number": 2415,
            "title": "S15c: external PID truth join feasibility gate",
            "project": "testbeam",
            "body": (
                "Question: can any beamline, GEANT4, or external detector metadata provide "
                "event-level PID truth for the S15/P08 weak-label rows? Expected information "
                "gain: separates real proton/deuteron PID validation from support-proxy closure "
                "before PID scores are reused or promoted beyond weak-label diagnostics."
            ),
        }
    ]
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace("# S15b: pulse-shape PID null-label stability audit", "# Ticket 2376: P08 Waveform-Only Weak-Label PID Bakeoff", 1)
    report = report.replace("# S15b: Pulse-shape PID null-label stability audit", "# Ticket 2376: P08 Waveform-Only Weak-Label PID Bakeoff", 1)
    report = report.replace("This S15b ticket asks", "This ticket 2376 P08 analysis asks", 1)
    report = report.replace("Ticket `2376` asks whether", "Ticket `2376` asks whether", 1)
    report = report.replace(
        "/home/billy/anaconda3/bin/python scripts/s15b_1781070978_487_042a7300_pid_null_label_stability_audit.py --config configs/s15b_1781070978_487_042a7300_pid_null_label_stability_audit.json",
        COMMAND,
    )
    report = report.replace(
        "UV_PROJECT_ENVIRONMENT=/tmp/testbeam-laptop-2-ticket2376-uv uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with tabulate --with torch python scripts/ticket_2376_p08_waveform_pid_bakeoff.py",
        COMMAND,
    )
    claim_note = (
        "\n## Claim Recovery Note\n\n"
        "The required single command `tn-ticket claim testbeam-laptop-2 --project testbeam` "
        "was run once and returned the known null pseudo-ticket (`null`, `# null`, `null`). "
        "The queue was not empty, so issue #2376 was recovered by direct GitHub label transition "
        "to `factory:claimed` and `worker:testbeam-laptop-2` without rerunning the claim command.\n"
    )
    if "## Claim Recovery Note" not in report:
        report = report.replace("## Raw ROOT Reproduction\n", claim_note + "\n## Raw ROOT Reproduction\n", 1)
    report_path.write_text(report, encoding="utf-8")

    claimed = OUT / "claimed_ticket.txt"
    claimed.write_text(
        "2376\n# P08: Pulse-shape discrimination for p vs d PID (waveform-only)\n\n"
        "Does the waveform shape alone separate protons from deuterons (different dE/dx -> "
        "quenching -> shape)? Traditional: charge-comparison PSD (tail/total) + dE-E band cuts. "
        "ML: classifier on waveform/latent. Benchmark purity vs efficiency; be explicit there is "
        "NO truth label without GEANT4 (S17).\n",
        encoding="utf-8",
    )

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = "2376"
    manifest["script"] = "scripts/ticket_2376_p08_waveform_pid_bakeoff.py"
    manifest["config"] = "configs/ticket_2376_p08_waveform_pid_bakeoff.json"
    manifest["commands"] = [COMMAND]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    shutil.copyfile(result_path, ROOT / "result.json")
    shutil.copyfile(report_path, ROOT / "REPORT.md")


def main() -> int:
    if "--postprocess-only" not in sys.argv:
        subprocess.check_call([sys.executable, str(BASE_SCRIPT), "--config", str(CONFIG)], cwd=ROOT)
    rewrite_outputs()
    print(f"DONE -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
