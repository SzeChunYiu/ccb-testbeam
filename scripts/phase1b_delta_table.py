#!/usr/bin/env python3
"""
Phase 1B delta table: historical vs authorising 1M MC HRD-proxy baseline.

Methodology source of truth: `process_mc_file` imported from
`scripts/trigger_baseline_characterization.py` — the ORIGINAL characterization
methodology. This script deliberately does NOT reimplement the event
classification: an earlier inline reimplementation here produced divergent
counts (enter_B 88,791 hist / 4,524 auth; sample_I 88,738 / 4,519) that
contradicted the original methodology's reproduction of the historical
baseline (enter_B 237,098 hist / 7,100 auth; sample_I 64,762 / 554). That
version was replaced wholesale by this one; the divergent numbers are
RETRACTED (see research/trigger_migration_study/PHASE1B_AUTHORISING_MC_FINDINGS.md).

Modes (automatic, per side):
  * ROOT file present AND uproot importable: recomputes via the original
    methodology after verifying the file's sha256 (LUNARC; ~40 s per 1M-side).
  * Otherwise: consumes the committed JSON receipt emitted by the same
    original methodology (SLURM job 3506920) — CI/laptop reproducibility.

Env overrides (only if the ROOT files live outside the repo checkout):
  PHASE1B_HIST_ROOT, PHASE1B_AUTH_ROOT

Errors are binomial sqrt(p(1-p)/n) on the ACTUAL denominator of each quantity:
event rates n = 1,000,000 primary events; per-species eps_HRD n = species
enter_B count; sample_I purity n = deuteron+proton sample_I count. Delta
errors combine the two independent sides in quadrature.

Usage:
  python3 scripts/phase1b_delta_table.py \
      [--out research/trigger_migration_study/phase1b_delta_table.md]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SIDES = {
    "hist": {
        "label": "Historical 1M",
        "root_env": "PHASE1B_HIST_ROOT",
        "root_default": REPO_ROOT / "geant4/data/output_krakow_1M.root",
        "sha256": "2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc",
        "receipt": REPO_ROOT / "research/trigger_migration_study/phase1b_baseline_hist_1M.json",
        "sanity": {"n_enter_B": 237098, "n_sample_I": 64762},
    },
    "auth": {
        "label": "Authorising 1M",
        "root_env": "PHASE1B_AUTH_ROOT",
        "root_default": REPO_ROOT / "geant4/data/output_krakow_1M_authorising.root",
        "sha256": "19cd97c1106632e9746dd76a683105186484aa34aa74be8617973072ebcf84ea",
        "receipt": REPO_ROOT / "research/trigger_migration_study/phase1b_baseline_authorising_1M.json",
        "sanity": {"n_enter_B": 7100, "n_sample_I": 554},
    },
}

SPECIES_ORDER = ["deuteron", "proton", "alpha", "C12"]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_side(key: str, spec: dict) -> tuple[dict, str]:
    """Recompute from ROOT via the ORIGINAL methodology, else use the receipt."""
    root_path = Path(os.environ.get(spec["root_env"]) or spec["root_default"])
    if root_path.exists():
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            from trigger_baseline_characterization import process_mc_file
        except ImportError as exc:
            print(f"WARN: cannot import original methodology ({exc}); falling back to receipt", file=sys.stderr)
        else:
            actual = sha256_of(root_path)
            if actual != spec["sha256"]:
                sys.exit(f"FAIL: {key} ROOT sha256 {actual} != expected {spec['sha256']}")
            stats = process_mc_file(str(root_path))
            return dict(stats), f"recomputed from ROOT {root_path} (sha256 verified, original methodology)"
    receipt_path = spec["receipt"]
    if not receipt_path.exists():
        sys.exit(f"FAIL: neither ROOT file ({root_path}) nor receipt ({receipt_path}) available for {key}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("source_root_sha256") != spec["sha256"]:
        sys.exit(f"FAIL: {key} receipt sha256 mismatch")
    return receipt, f"receipt {receipt_path.name} (emitted by the original methodology, SLURM job 3506920)"


def binom(p: float, n: int) -> float:
    """Binomial standard error sigma = sqrt(p(1-p)/n); 0 for n=0."""
    if n <= 0:
        return 0.0
    return (p * (1.0 - p) / n) ** 0.5


def pct(x: float, err: float, nd: int = 3) -> str:
    return f"{100 * x:.{nd}f}% ± {100 * err:.{nd}f}%"


def fmt_count(n: int) -> str:
    return f"{n:,}"


def rate_row(name: str, h: dict, a: dict, hk: str, ak: str) -> str:
    nh, na = h["n_events_processed"], a["n_events_processed"]
    ch, ca = h[hk], a[ak]
    ph, pa = ch / nh, ca / na
    eh, ea = binom(ph, nh), binom(pa, na)
    d = (pa - ph) * 100.0
    sd = (eh**2 + ea**2) ** 0.5 * 100.0
    return (
        f"| {name} | {fmt_count(ch)} ({pct(ph, eh)}) | {fmt_count(ca)} ({pct(pa, ea)}) "
        f"| **{fmt_count(ca - ch)} ({d:+.3f} ± {sd:.3f} pp)** |"
    )


def eps_row(name: str, h: dict, a: dict, sp: str) -> str:
    hs, as_ = h["species_counts"][sp], a["species_counts"][sp]
    nh, na = hs["enter_B"], as_["enter_B"]
    ch, ca = hs["sample_I"], as_["sample_I"]
    if nh == 0 and na == 0:
        return f"| ε_HRD, {sp} | {fmt_count(ch)}/{fmt_count(nh)} | {fmt_count(ca)}/{fmt_count(na)} | — |"
    ph = ch / nh if nh else 0.0
    pa = ca / na if na else 0.0
    eh, ea = binom(ph, nh), binom(pa, na)
    d = (pa - ph) * 100.0
    sd = (eh**2 + ea**2) ** 0.5 * 100.0
    cells = []
    for c, n, p, e in ((ch, nh, ph, eh), (ca, na, pa, ea)):
        cells.append("—" if n == 0 else f"{pct(p, e)} ({fmt_count(c)}/{fmt_count(n)})")
    delta = "—" if (nh == 0 or na == 0) else f"**{d:+.3f} ± {sd:.3f} pp**"
    return f"| {name} | {cells[0]} | {cells[1]} | {delta} |"


def purity(h: dict, a: dict) -> tuple[tuple[float, float, int], tuple[float, float, int]]:
    def one(s: dict) -> tuple[float, float, int]:
        d = s["species_counts"]["deuteron"]["sample_I"]
        p = s["species_counts"]["proton"]["sample_I"]
        n = d + p
        v = d / n if n else 0.0
        return v, binom(v, n), n

    return one(h), one(a)


def sigma_of(d_pp: float, sd_pp: float) -> str:
    return f"{abs(d_pp) / sd_pp:.1f}σ" if sd_pp > 0 else "—"


def build_section(h: dict, a: dict, src_h: str, src_a: str) -> str:
    ph = h["n_enter_B"] / h["n_events_processed"]
    pa = a["n_enter_B"] / a["n_events_processed"]
    factor = ph / pa if pa else float("inf")

    # Deuteron epsilon for the interpretation sentence.
    hd, ad = h["species_counts"]["deuteron"], a["species_counts"]["deuteron"]
    dh = (ad["sample_I"] / ad["enter_B"] - hd["sample_I"] / hd["enter_B"]) * 100.0
    sdh = ((binom(hd["sample_I"] / hd["enter_B"], hd["enter_B"]) ** 2
            + binom(ad["sample_I"] / ad["enter_B"], ad["enter_B"]) ** 2) ** 0.5) * 100.0

    (pur_h, pur_he, pur_hn), (pur_a, pur_ae, pur_an) = purity(h, a)
    pur_d = (pur_a - pur_h) * 100.0
    pur_sd = (pur_he**2 + pur_ae**2) ** 0.5 * 100.0

    lines = [
        "> **Computed by `scripts/phase1b_delta_table.py`, which imports `process_mc_file`",
        "> from the ORIGINAL `scripts/trigger_baseline_characterization.py` — no",
        "> reimplementation. Ground truth recomputed from BOTH ROOT files (SLURM job",
        "> 3506920; receipts `research/trigger_migration_study/phase1b_baseline_{hist,authorising}_1M.json`):**",
        "> - Historical: `output_krakow_1M.root` (sha256 `2b62403f0aa7…`)",
        "> - Authorising: `output_krakow_1M_authorising.root` (sha256 `19cd97c11066…`)",
        ">",
        f"> **Sanity gate PASSED exactly**: hist enter_B {fmt_count(h['n_enter_B'])} / auth",
        f"> {fmt_count(a['n_enter_B'])}; hist sample_I {fmt_count(h['n_sample_I'])} / auth",
        f"> {fmt_count(a['n_sample_I'])} — bit-identical to the historical-side values of the",
        "> original Phase 1 characterization. The numbers previously shown here",
        "> (88,791 / 4,524 / 88,738 / 4,519) came from a divergent inline",
        "> reimplementation in an earlier version of the delta script and are RETRACTED.",
        "",
        f"Sources: historical — {src_h}; authorising — {src_a}.",
        "",
        "The corrected `ScatteringGenerator` produces a dramatically different HRD proxy baseline:",
        "",
        "| Metric | Historical 1M | Authorising 1M | Delta (auth − hist) |",
        "|--------|---------------|----------------|--------------------|",
        rate_row("Enter B", h, a, "n_enter_B", "n_enter_B"),
        rate_row("Sample I (A∧B)", h, a, "n_sample_I", "n_sample_I"),
        eps_row("ε_HRD, deuteron", h, a, "deuteron"),
        eps_row("ε_HRD, proton", h, a, "proton"),
        (f"| Sample I purity (d/(d+p)) | {pct(pur_h, pur_he)} (n={fmt_count(pur_hn)}) "
         f"| {pct(pur_a, pur_ae)} (n={fmt_count(pur_an)}) | **{pur_d:+.3f} ± {pur_sd:.3f} pp** |"),
        "",
        "Errors are binomial `sqrt(p(1-p)/n)` on the ACTUAL denominator of each quantity:",
        "event rates use n = 1,000,000 primary events; per-species ε_HRD uses that species'",
        "enter_B count; purity uses the deuteron+proton sample_I count. Delta errors combine",
        "the two independent sides in quadrature.",
        "",
        "**Breakdown by species (both sides)**:",
        "",
        "| Species | hist enter_B | hist sample_I | hist ε_HRD | auth enter_B | auth sample_I | auth ε_HRD |",
        "|---------|--------------|---------------|------------|--------------|---------------|-----------|",
    ]
    for sp in SPECIES_ORDER:
        hs, as_ = h["species_counts"][sp], a["species_counts"][sp]
        cells = []
        for s in (hs, as_):
            n = s["enter_B"]
            e = "—" if n == 0 else pct(s["sample_I"] / n, binom(s["sample_I"] / n, n))
            cells += [fmt_count(s["enter_B"]), fmt_count(s["sample_I"]), e]
        lines.append(f"| {sp.capitalize()} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "**Sample II**: in this characterization `n_sample_II` is recorded identically to",
        "`n_enter_B` on both sides (the Sample II branch applies no additional selection),",
        "so it carries no independent information and is not tabulated. The earlier",
        "\"Sample II 53 vs 5\" row was an artifact of the retracted counts.",
        "",
        (f"**Interpretation**: the corrected cross-section sampling reduces the Enter B rate by "
         f"−{(1 - pa / ph) * 100:.2f}% ± 0.043 pp ({100 * ph:.3f}% → {100 * pa:.3f}%; a "
         f"{factor:.0f}× reduction) and Sample I by −99.14% ± 0.025 pp. This is the expected "
         "outcome of fixing the unit-weight/uniform-fallback sampling bug. Among deuterons "
         f"that do reach the B arm, the coincidence efficiency ε_HRD drops by {dh:+.2f} ± "
         f"{sdh:.2f} pp ({100 * hd['sample_I'] / hd['enter_B']:.1f}% → "
         f"{100 * ad['sample_I'] / ad['enter_B']:.1f}%, {sigma_of(dh, sdh)}) — the corrected "
         "angular distribution changes not only how many events reach B but also the "
         "time/geometry structure of those that do. The deuteron purity of Sample I is "
         f"statistically unchanged ({100 * pur_h:.2f}% → {100 * pur_a:.2f}%, "
         f"Δ = {pur_d:+.2f} ± {pur_sd:.2f} pp), indicating the surviving coincidence sample "
         "is still overwhelmingly deuteronic."),
        "",
    ]
    return "\n".join(lines)


def check_sanity(key: str, spec: dict, stats: dict) -> None:
    for field, expected in spec["sanity"].items():
        actual = stats.get(field)
        if actual != expected:
            sys.exit(
                f"FAIL sanity gate ({key}): {field} = {actual!r}, expected {expected!r}. "
                "The original methodology must reproduce these counts exactly "
                "(SLURM job 3506920 ground truth); refusing to emit a table from divergent stats."
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out", type=Path, default=None, help="write the markdown section to this file")
    args = ap.parse_args()

    h, src_h = load_side("hist", SIDES["hist"])
    a, src_a = load_side("auth", SIDES["auth"])
    check_sanity("hist", SIDES["hist"], h)
    check_sanity("auth", SIDES["auth"], a)

    section = build_section(h, a, src_h, src_a)
    print(section)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(section + "\n", encoding="utf-8")
        print(f"\n[written to {args.out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
