"""
Figure 20 — Key Results Dashboard (Chapter 12).

Registry-driven summary board. This figure deliberately contains **no
hard-coded quantitative headline values**: every number must come from a
validated result bundle referenced by ``paper/figures.yaml``. When a result
bundle is not synced (registry status EXTERNAL_BLOCKER) the card reports
BLOCKED with the registry id(s) — never a stale or fabricated literal.

The dashboard renders card STRUCTURE + STATUS only:
  * the result category and the registry id(s) it summarises,
  * the status colour stripe (PASS / BLOCKED / OPEN) sourced from the registry,
  * the numeric value, *iff* the referenced result JSON is present on disk and
    carries the entry's ``value_key``; otherwise "pending result sync".

Quantitative literals in figure code are banned (PUB-002); the companion CI
test (tests/test_fig20_no_quantitative_literals.py) guards against regressions.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from ..config import PALETTE, new_fig, save_pub

# Repo root (src/ccb_figures/figures/<this> -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY = _REPO_ROOT / "paper" / "figures.yaml"

# Each card summarises one or more registry ids. No quantitative values live
# here — only the category, the registry ids, and a qualitative descriptor.
_CARDS = [
    {"pos": (0.2, 3.0, 3.2, 2.0), "title": "Timing\nResolution",
     "ids": ["TIME-01", "TIME-02"],
     "detail": "B6 single-stave +\ncombined 3-stave\n(MV4 release BLOCKED)"},
    {"pos": (3.8, 3.0, 3.2, 2.0), "title": "Pile-up\nTolerance",
     "ids": ["PU-01"],
     "detail": "R_max + tau_eff\n(MV5 release BLOCKED)"},
    {"pos": (7.4, 3.0, 3.2, 2.0), "title": "Particle\nIdentification",
     "ids": ["PID-01"],
     "detail": "Truth-labelled MC only;\ndata transfer unvalidated"},
    {"pos": (0.2, 0.3, 5.0, 2.0), "title": "MC Validation\n& Systematics",
     "ids": ["MV3-01", "MV0-01"],
     "detail": "MV3 stopping: FAIL\n(geometry blocker).\nSystematics pending."},
    {"pos": (5.6, 0.3, 5.0, 2.0), "title": "Anomaly\nDiscovery",
     "ids": ["AN-01"],
     "detail": "Truth-labelled MC only;\nreal-data identity\nunvalidated"},
]


def _load_registry() -> dict:
    """Best-effort load of paper/figures.yaml. Never raises."""
    try:
        import yaml  # type: ignore[import-not-found]  # noqa: PLC0415
        if not _REGISTRY.is_file():
            return {}
        data = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8")) or {}
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _result_value(entry: dict) -> str | None:
    """Read the headline value from the entry's result bundle, or None.

    Returns None whenever the bundle is absent or the value key is missing —
    the caller then renders "pending result sync". No literal fallback.
    """
    rel = entry.get("result")
    if not rel:
        return None
    path = _REPO_ROOT / rel
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    vk = entry.get("value_key")
    val = payload.get(vk) if vk else None
    if val is None:
        return None
    uk = entry.get("uncertainty_key")
    unc = payload.get(uk) if uk else None
    if unc is not None:
        return f"{val}  (CI: {unc})"
    return str(val)


def _status_of(registry: dict, ids: list[str]) -> str:
    """Worst-case status across the card's ids. Defaults to EXTERNAL_BLOCKER."""
    rank = {"VALIDATED": 0, "PRELIMINARY": 1, "TENSION": 2,
            "EXTERNAL_BLOCKER": 3, "ILLUSTRATIVE": 4}
    worst = "EXTERNAL_BLOCKER"
    worst_r = rank.get(worst, 3)
    for cid in ids:
        st = str(registry.get(cid, {}).get("status", "EXTERNAL_BLOCKER"))
        r = rank.get(st, 3)
        if r > worst_r:
            worst, worst_r = st, r
    return worst


_STATUS_VERDICT = {"VALIDATED": "PASS", "PRELIMINARY": "PRELIM",
                   "TENSION": "TENSION", "EXTERNAL_BLOCKER": "BLOCKED",
                   "ILLUSTRATIVE": "SCHEMA"}

_STATUS_COLOR = {"PASS": PALETTE["pass_green"], "PRELIM": PALETTE["tension_orange"],
                 "TENSION": PALETTE["tension_orange"], "BLOCKED": PALETTE["fail_red"],
                 "SCHEMA": PALETTE["neutral_mid"]}


def build() -> str:
    registry = _load_registry()

    fig, ax = new_fig(11, 5)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")

    ax.text(5.5, 5.7, "CCB Test-Beam: Key Results Dashboard",
            ha="center", fontsize=11, fontweight="bold",
            color=PALETTE["neutral_black"])
    ax.text(5.5, 5.42,
            "Registry-driven: values read from validated result bundles only "
            "(paper/figures.yaml).",
            ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    for card in _CARDS:
        x, y, w, h = card["pos"]
        status = _status_of(registry, card["ids"])
        verdict = _STATUS_VERDICT.get(status, "BLOCKED")
        color = _STATUS_COLOR.get(verdict, PALETTE["fail_red"])

        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=PALETTE["bg_light"],
                     edgecolor=PALETTE["neutral_light"], lw=0.8))
        ax.add_patch(plt.Rectangle((x, y + h - 0.25), w, 0.25, facecolor=color,
                     edgecolor="none", alpha=0.85))
        ax.text(x + w / 2, y + h - 0.13, verdict, ha="center", fontsize=6,
                fontweight="bold", color="white")

        ax.text(x + 0.15, y + h - 0.55, card["title"], fontsize=7.5,
                fontweight="bold", color=PALETTE["neutral_black"])

        # Headline value: only from a present result bundle; else pending.
        value_lines = []
        for cid in card["ids"]:
            entry = registry.get(cid, {})
            val = _result_value(entry)
            if val is not None:
                value_lines.append(f"{cid}: {val}")
            else:
                value_lines.append(f"{cid}: pending sync")
        ax.text(x + 0.15, y + h - 1.2, "\n".join(value_lines), fontsize=7.0,
                fontweight="bold", color=PALETTE["b2"])

        ax.text(x + 0.15, y + 0.05, card["detail"], fontsize=5.5,
                color=PALETTE["neutral_mid"], va="bottom")

    ax.text(5.5, 5.18,
            "Critical blocker: MV3 geometry fix -> new MC production -> "
            "re-run all Tier-2 validations. See docs/claim_ledger.csv.",
            ha="center", fontsize=6.5, color=PALETTE["fail_red"], fontweight="bold")

    name = "20_key_results"
    save_pub(fig, name)
    return name
