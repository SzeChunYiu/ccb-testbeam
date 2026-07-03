#!/usr/bin/env python
"""STATS01 — program-level Benjamini-Hochberg FDR pass over all delta-CI claims.

Context (External Review 2026-07-02, section 4): the 2026-06 program ran ~238
adaptive studies on one dataset with no multiplicity control; with thousands of
CIs, ~12+ chance "CI excludes zero" wins are expected — about the number of
scoreboard wins. This script is the claim-level census:

1. Walks every ``reports/*/result.json`` artifact.
2. Extracts every ML-vs-traditional (and stratum/ablation) *paired delta* that
   carries a bootstrap CI. The artifact schemas are heterogeneous; extraction
   is a recursive walk keyed on ``*delta*``/``*minus*`` keys with ``_ci`` /
   ``_ci95`` suffixes, with the point estimate taken from the sibling key
   (fallback: CI midpoint, flagged). Nothing is dropped silently — every skip
   is counted and logged.
3. Converts each CI to an approximate two-sided normal p-value
   (``se = width / (2 * 1.96)``, ``z = delta / se``). This is approximate for
   percentile bootstrap CIs (documented caveat), but it is the only uniform
   conversion available post hoc.
4. Applies Benjamini-Hochberg at q = 0.05 *within claim families* (timing /
   amplitude-charge / pileup / pid / pedestal / representation, classified by
   study-id prefix).
5. Writes ``reports/stats01_program_fdr_<stamp>/`` with a full claims CSV and
   a REPORT.md summarizing how many nominal wins survive BH per family and
   which scoreboard "Yes" wins fail.

Run:
    /home/billy/anaconda3/envs/nnbar_env/bin/python scripts/stats01_program_fdr.py
"""

from __future__ import annotations

import csv
import json
import logging
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from ccb_mc_validation.statistics.estimators import bh_fdr  # noqa: E402

log = logging.getLogger("stats01")

Q_FDR = 0.05
Z975 = 1.959963984540054

# ---------------------------------------------------------------------------
# Claim-family classification by study-id prefix.
# Judgment calls are documented inline; unmapped prefixes land in "other" and
# are BH-corrected as their own family (never dropped).
# ---------------------------------------------------------------------------
FAMILY_BY_PREFIX = {
    # timing pickoff / timewalk / pair-residual studies
    "S02": "timing", "S03": "timing", "S04": "timing", "S05": "timing",
    "S18": "timing",                      # A-stack timing reproduction
    "P02": "timing",                      # early-peak timing-tail validation
    "P03": "timing",                      # NN timing architectures
    "P06": "timing",                      # amplitude-binned timing atoms
    # amplitude / charge / energy recovery
    "S06": "amplitude-charge",            # amplitude-energy support closure
    "S14": "amplitude-charge",            # saturation / energy acceptance
    "P04": "amplitude-charge",            # duplicate-readout charge closure
    "P07": "amplitude-charge",            # saturation recovery
    # pile-up / rate / two-pulse
    "S07": "pileup",                      # current/contamination classifiers
    "S10": "pileup", "S11": "pileup", "S12": "pileup", "S13": "pileup",
    "P05": "pileup",                      # two-pulse abstention/failure
    # particle identification
    "S09": "pid", "S15": "pid", "P08": "pid",
    # pedestal / baseline
    "S16": "pedestal",
    "P11": "pedestal",                    # pretrigger charge-transfer gates
    # representation / templates / anomaly taxonomy / pipeline arbitration
    "S00": "representation", "S01": "representation",
    "P01": "representation", "P09": "representation", "P10": "representation",
    "P12": "representation", "P13": "representation",
    "T07": "representation",
}

CI_SUFFIXES = ("_ci95", "_ci", "ci95")  # order matters: longest first

# identifying context fields worth carrying into the claim label
CONTEXT_KEYS = (
    "method", "metric", "name", "model", "stratum", "strata_definition",
    "family", "atom", "label", "feature_family", "comparison", "stave",
    "run", "fold", "group", "definition", "selection_method",
)


def classify_family(study_id: str) -> str:
    m = re.match(r"([A-Z]+\d+)", study_id.upper())
    if m:
        return FAMILY_BY_PREFIX.get(m.group(1), "other")
    return "other"


def is_ci_pair(v: object) -> bool:
    return (
        isinstance(v, (list, tuple))
        and len(v) == 2
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    )


def base_of_ci_key(key: str) -> str | None:
    kl = key.lower()
    for suf in CI_SUFFIXES:
        if kl.endswith(suf) and len(kl) > len(suf):
            return key[: -len(suf)].rstrip("_")
    return None


def _looks_like_ci_component(key: str) -> bool:
    kl = key.lower()
    return (
        base_of_ci_key(key) is not None
        or kl.endswith(("_ci_low", "_ci_high", "_ci_width"))
        or kl in ("ci", "ci_low", "ci_high", "ci95")
    )


def find_point_estimate(container: dict, base: str):
    """Sibling point estimate for a CI key: exact match, then prefix match."""
    if base in container and isinstance(container[base], (int, float)) \
            and not isinstance(container[base], bool):
        return float(container[base]), "sibling_exact"
    candidates = [
        k for k, v in container.items()
        if k.lower().startswith(base.lower())
        and not _looks_like_ci_component(k)
        and isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if candidates:
        best = min(candidates, key=len)
        return float(container[best]), f"sibling_prefix:{best}"
    return None, None


def context_label(container: dict) -> str:
    parts = []
    for k in CONTEXT_KEYS:
        v = container.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            parts.append(f"{k}={v}")
    return ";".join(parts[:4])


DELTAISH = re.compile(r"delta|minus|excess|shift", re.IGNORECASE)


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_ci(val, skips: Counter):
    lo, hi = float(val[0]), float(val[1])
    if not (math.isfinite(lo) and math.isfinite(hi)):
        skips["ci_nonfinite"] += 1
        return None
    if lo > hi:
        lo, hi = hi, lo
        skips["ci_swapped_lo_hi"] += 1
    if hi - lo <= 0.0:
        skips["ci_zero_width"] += 1
        return None
    return lo, hi


def _emit(out, claimed, path, ci_key, delta, lo, hi, src, node, pattern):
    key_id = (path, ci_key)
    if key_id in claimed:
        return
    claimed.add(key_id)
    out.append({
        "json_path": f"{path}/{ci_key}",
        "ci_key": ci_key,
        "delta": delta,
        "ci_low": lo,
        "ci_high": hi,
        "estimate_source": src,
        "pattern": pattern,
        "context": context_label(node),
    })


def _extract_from_dict(node: dict, path: str, out, skips: Counter, claimed: set):
    # --- pattern A: CI-suffixed key whose own name is delta-ish -------------
    for key, val in node.items():
        kl = key.lower()
        if ("delta" in kl or "minus" in kl) and base_of_ci_key(key) is not None:
            if not is_ci_pair(val):
                skips["ci_key_not_2list"] += 1
                continue
            ci = _validate_ci(val, skips)
            if ci is None:
                continue
            lo, hi = ci
            base = base_of_ci_key(key)
            est, src = find_point_estimate(node, base)
            if est is None:
                est, src = 0.5 * (lo + hi), "ci_midpoint"
                skips["point_estimate_from_midpoint"] += 1
            _emit(out, claimed, path, key, est, lo, hi, src, node, "A_delta_named_ci_key")

    # --- pattern B: delta-named numeric key with a CI sibling ----------------
    for key, val in node.items():
        kl = key.lower()
        if not (("delta" in kl or "minus" in kl) and _is_num(val)):
            continue
        candidates = [key + "_ci95", key + "_ci"]
        # generic CI siblings are only safe when no plain 'value' could own them
        if "value" not in node:
            candidates += ["bootstrap_ci", "ci95", "ci"]
        for cand in candidates:
            if cand in node and is_ci_pair(node[cand]):
                ci = _validate_ci(node[cand], skips)
                if ci is None:
                    break
                lo, hi = ci
                _emit(out, claimed, path, cand, float(val), lo, hi,
                      f"delta_key:{key}", node, "B_delta_key_with_ci_sibling")
                break

    # --- pattern C: {value, ci_low/ci_high or ci} rows with delta-ish metric -
    if _is_num(node.get("value")):
        metric_text = " ".join(
            str(node[k]) for k in ("metric", "name", "label", "definition", "quantity")
            if isinstance(node.get(k), str)
        )
        if DELTAISH.search(metric_text):
            ci_val = None
            ci_key = None
            if _is_num(node.get("ci_low")) and _is_num(node.get("ci_high")):
                ci_val, ci_key = [node["ci_low"], node["ci_high"]], "ci_low/ci_high"
            elif is_ci_pair(node.get("ci")):
                ci_val, ci_key = node["ci"], "ci"
            elif is_ci_pair(node.get("ci95")):
                ci_val, ci_key = node["ci95"], "ci95"
            if ci_val is not None:
                ci = _validate_ci(ci_val, skips)
                if ci is not None:
                    lo, hi = ci
                    _emit(out, claimed, path, ci_key, float(node["value"]), lo, hi,
                          "value_field", node, "C_delta_metric_value_row")
            else:
                skips["delta_metric_value_without_ci"] += 1

    # --- pattern E: scalar '<base>_ci_low'/'<base>_ci_high' pairs -------------
    for key, val in node.items():
        kl = key.lower()
        if kl.endswith("_ci_low") and _is_num(val):
            base = key[: -len("_ci_low")]
            hi_key = base + "_ci_high"
            if ("delta" in base.lower() or "minus" in base.lower()) \
                    and _is_num(node.get(hi_key)):
                ci = _validate_ci([val, node[hi_key]], skips)
                if ci is None:
                    continue
                lo, hi = ci
                est, src = find_point_estimate(node, base)
                if est is None:
                    est, src = 0.5 * (lo + hi), "ci_midpoint"
                    skips["point_estimate_from_midpoint"] += 1
                _emit(out, claimed, path, f"{key}/{hi_key}", est, lo, hi, src,
                      node, "E_scalar_ci_low_high_pair")

    # --- pattern D: ml vs traditional per-method CIs (unpaired, conservative) -
    ml, trad = node.get("ml"), node.get("traditional")
    if isinstance(ml, dict) and isinstance(trad, dict):
        derived_any = False
        # D1: canonical {metric, value, ci} form
        same_metric = (
            "metric" not in ml or "metric" not in trad
            or ml.get("metric") == trad.get("metric")
        )
        if (same_metric and _is_num(ml.get("value")) and _is_num(trad.get("value"))
                and is_ci_pair(ml.get("ci")) and is_ci_pair(trad.get("ci"))):
            ci_m = _validate_ci(ml["ci"], skips)
            ci_t = _validate_ci(trad["ci"], skips)
            if ci_m and ci_t:
                se = math.hypot((ci_m[1] - ci_m[0]) / (2.0 * Z975),
                                (ci_t[1] - ci_t[0]) / (2.0 * Z975))
                delta = float(ml["value"]) - float(trad["value"])
                _emit(out, claimed, path, "ml.ci-vs-traditional.ci",
                      delta, delta - Z975 * se, delta + Z975 * se,
                      "unpaired_per_method_cis", node,
                      "D_unpaired_ml_vs_traditional")
                skips["derived_unpaired_ml_vs_traditional"] += 1
                derived_any = True
        # D2: matching per-metric keys '<k>' + '<k>_ci' present in BOTH dicts
        for k, v in ml.items():
            if not _is_num(v) or k == "value":
                continue
            for suf in ("_ci95", "_ci"):
                ci_k = k + suf
                if (is_ci_pair(ml.get(ci_k)) and _is_num(trad.get(k))
                        and is_ci_pair(trad.get(ci_k))):
                    ci_m = _validate_ci(ml[ci_k], skips)
                    ci_t = _validate_ci(trad[ci_k], skips)
                    if ci_m and ci_t:
                        se = math.hypot((ci_m[1] - ci_m[0]) / (2.0 * Z975),
                                        (ci_t[1] - ci_t[0]) / (2.0 * Z975))
                        delta = float(v) - float(trad[k])
                        _emit(out, claimed, path, f"ml.{ci_k}-vs-traditional.{ci_k}",
                              delta, delta - Z975 * se, delta + Z975 * se,
                              "unpaired_per_method_cis", node,
                              "D_unpaired_ml_vs_traditional")
                        skips["derived_unpaired_ml_vs_traditional"] += 1
                        derived_any = True
                    break
        # D3: matching per-metric keys '<k>' + '<k>_ci_low'/'<k>_ci_high' scalars
        for k, v in ml.items():
            if not _is_num(v) or _looks_like_ci_component(k):
                continue
            lo_k, hi_k = k + "_ci_low", k + "_ci_high"
            if (_is_num(ml.get(lo_k)) and _is_num(ml.get(hi_k))
                    and _is_num(trad.get(k))
                    and _is_num(trad.get(lo_k)) and _is_num(trad.get(hi_k))):
                ci_m = _validate_ci([ml[lo_k], ml[hi_k]], skips)
                ci_t = _validate_ci([trad[lo_k], trad[hi_k]], skips)
                if ci_m and ci_t:
                    se = math.hypot((ci_m[1] - ci_m[0]) / (2.0 * Z975),
                                    (ci_t[1] - ci_t[0]) / (2.0 * Z975))
                    delta = float(v) - float(trad[k])
                    _emit(out, claimed, path, f"ml.{k}_ci-vs-traditional.{k}_ci",
                          delta, delta - Z975 * se, delta + Z975 * se,
                          "unpaired_per_method_cis", node,
                          "D_unpaired_ml_vs_traditional")
                    skips["derived_unpaired_ml_vs_traditional"] += 1
                    derived_any = True
        if not derived_any and _is_num(ml.get("value")) and _is_num(trad.get("value")):
            skips["ml_traditional_values_without_both_cis"] += 1


def walk_claims(node: object, path: str, out: list[dict], skips: Counter,
                claimed: set | None = None):
    if claimed is None:
        claimed = set()
    if isinstance(node, dict):
        _extract_from_dict(node, path, out, skips, claimed)
        for key, val in node.items():
            walk_claims(val, f"{path}/{key}", out, skips, claimed)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk_claims(item, f"{path}/[{i}]", out, skips, claimed)


def norm_sf(z: float) -> float:
    """Two-sided normal p-value from |z|."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def parse_scoreboard_wins(summary_path: Path) -> list[str]:
    """Study ids of the bold '**Yes**' / '**ML' win rows in reports/SUMMARY.md."""
    wins = []
    for line in summary_path.read_text().splitlines():
        if "**Yes**" in line or "| **ML" in line:
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 1 and cells[1]:
                m = re.match(r"([A-Za-z]+\d+[a-z]?)", cells[1])
                if m:
                    wins.append(m.group(1))
    return wins


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    reports_dir = REPO / "reports"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = reports_dir / f"stats01_program_fdr_{stamp}"
    out_dir.mkdir(parents=True)

    artifact_paths = sorted(reports_dir.glob("*/result.json"))
    log.info("found %d result.json artifacts", len(artifact_paths))

    claims: list[dict] = []
    skips: Counter = Counter()
    file_status: Counter = Counter()
    no_claim_files: list[str] = []
    unmapped_prefixes: Counter = Counter()

    for path in artifact_paths:
        rel_dir = path.parent.name
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("unparseable artifact %s: %s", rel_dir, exc)
            file_status["unparseable_json"] += 1
            continue
        if not isinstance(data, dict):
            log.warning("non-dict artifact %s", rel_dir)
            file_status["non_dict_json"] += 1
            continue

        study_id = str(data.get("study") or data.get("study_id") or "")
        if not study_id:
            m = re.search(r"__([a-z]+\d+[a-z]?)_", rel_dir)
            study_id = m.group(1).upper() if m else "UNKNOWN"
            skips["study_id_from_dirname_or_unknown"] += 1

        found: list[dict] = []
        walk_claims(data, "", found, skips)
        if not found:
            file_status["no_delta_ci_claims"] += 1
            no_claim_files.append(f"{rel_dir} (study={study_id})")
            continue
        file_status["with_claims"] += 1

        family = classify_family(study_id)
        if family == "other":
            m = re.match(r"([A-Z]+\d+)", study_id.upper())
            unmapped_prefixes[m.group(1) if m else study_id] += 1
        for c in found:
            width = c["ci_high"] - c["ci_low"]
            se = width / (2.0 * Z975)
            z = c["delta"] / se
            c.update({
                "study_id": study_id,
                "family": family,
                "report_dir": rel_dir,
                "se_from_ci": se,
                "z": z,
                "p": norm_sf(z),
                "nominal_ci_excludes_zero": (c["ci_low"] > 0.0) or (c["ci_high"] < 0.0),
            })
        claims.extend(found)

    log.info("parsed %d claims from %d artifacts", len(claims),
             file_status["with_claims"])
    log.info("file status: %s", dict(file_status))
    log.info("claim-level skips (nothing dropped silently): %s", dict(skips))
    if unmapped_prefixes:
        log.info("study prefixes classified as 'other': %s", dict(unmapped_prefixes))

    # --- BH within family ---------------------------------------------------
    by_family: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(claims):
        by_family[c["family"]].append(i)
    for family, idxs in by_family.items():
        pvals = [claims[i]["p"] for i in idxs]
        reject, p_adj = bh_fdr(pvals, q=Q_FDR)
        for j, i in enumerate(idxs):
            claims[i]["bh_pass"] = bool(reject[j])
            claims[i]["p_bh_adjusted"] = float(p_adj[j])

    # --- claims CSV ----------------------------------------------------------
    csv_path = out_dir / "claims.csv"
    fields = [
        "study_id", "family", "report_dir", "json_path", "ci_key", "pattern",
        "context", "delta", "ci_low", "ci_high", "estimate_source",
        "se_from_ci", "z", "p", "p_bh_adjusted", "nominal_ci_excludes_zero",
        "bh_pass",
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(claims)
    log.info("wrote %s (%d rows)", csv_path, len(claims))

    skipped_path = out_dir / "artifacts_without_claims.txt"
    skipped_path.write_text("\n".join(no_claim_files) + "\n")

    # --- family summary -------------------------------------------------------
    fam_rows = []
    for family in sorted(by_family):
        idxs = by_family[family]
        n = len(idxs)
        n_nom = sum(claims[i]["nominal_ci_excludes_zero"] for i in idxs)
        n_bh = sum(claims[i]["bh_pass"] for i in idxs)
        n_studies = len({claims[i]["study_id"] for i in idxs})
        fam_rows.append((family, n_studies, n, n_nom, n_bh))

    # --- scoreboard "Yes" wins vs BH ------------------------------------------
    summary_md = reports_dir / "SUMMARY.md"
    win_ids = parse_scoreboard_wins(summary_md) if summary_md.exists() else []
    log.info("scoreboard bold wins parsed from SUMMARY.md: %s", win_ids)
    win_rows = []
    for wid in win_ids:
        widu = wid.upper()
        mine = [c for c in claims if c["study_id"].upper() == widu]
        n_nom = sum(c["nominal_ci_excludes_zero"] for c in mine)
        n_bh = sum(c["bh_pass"] for c in mine)
        if not mine:
            status = "NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed)"
        elif n_bh > 0:
            status = "survives BH (at least one claim)"
        else:
            status = "FAILS BH (no claim survives)"
        fam = classify_family(wid)
        win_rows.append((wid, fam, len(mine), n_nom, n_bh, status))

    # --- REPORT.md -------------------------------------------------------------
    lines = []
    lines.append("# STATS01 — Program-level FDR pass over all delta-CI claims")
    lines.append("")
    lines.append(f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Input:** {len(artifact_paths)} `reports/*/result.json` artifacts")
    lines.append(f"- **Procedure:** Benjamini-Hochberg at q = {Q_FDR} within claim family; "
                 "p-values from a normal approximation of each bootstrap CI "
                 "(`se = (hi - lo) / (2 x 1.96)`, two-sided).")
    lines.append("- **Motivation:** External Review 2026-07-02 section 4 — ~238 adaptive studies "
                 "on one dataset, no multiplicity control; ~12+ chance wins expected among "
                 "thousands of CIs.")
    lines.append("")
    lines.append("## Caveats (read first)")
    lines.append("")
    lines.append("- The normal approximation understates tail p-values for skewed percentile "
                 "bootstrap CIs, and most underlying bootstraps iid-resampled dependent residuals "
                 "(CIs ~ sqrt(1.5) too narrow per the review), so **the BH survivor counts below "
                 "are an upper bound on trustworthy wins**.")
    lines.append("- Claims are *every* delta-with-CI in the artifacts (method deltas, ablations, "
                 "strata), not only headline claims; the per-family BH is therefore stricter than "
                 "a headline-only correction, which is the intended posture after an adaptive "
                 "program.")
    lines.append("- Four extraction patterns are used (column `pattern` in `claims.csv`): "
                 "A = delta-named `*_ci` key; B = delta-named scalar with a CI sibling; "
                 "C = `{value, ci_low, ci_high}` rows whose metric name is delta-like "
                 "(delta/minus/excess/shift); D = **derived unpaired** ML-vs-traditional delta "
                 "from two independent per-method CIs (`se = hypot(se_ml, se_trad)`) — pattern D "
                 "ignores the positive correlation of paired evaluation, so it is conservative "
                 "(too wide), whereas patterns A-C inherit the underlying (often too-narrow) "
                 "bootstrap.")
    lines.append("- This census supersedes the 137-row `reports/SUMMARY.md` sample as the "
                 "claim-level record.")
    lines.append("")
    lines.append("## Parse accounting (no silent drops)")
    lines.append("")
    lines.append(f"- Artifacts found: **{len(artifact_paths)}**")
    for k, v in sorted(file_status.items()):
        lines.append(f"- Artifacts {k.replace('_', ' ')}: **{v}**")
    lines.append(f"- Claims parsed: **{len(claims)}**")
    for k, v in sorted(skips.items()):
        lines.append(f"- Claim-level `{k}`: {v}")
    lines.append(f"- Artifacts with zero extractable delta-CI claims are listed in "
                 f"`artifacts_without_claims.txt` ({file_status['no_delta_ci_claims']} files); "
                 "these include verdict-only, count-only, and classifier-metric-only artifacts.")
    if unmapped_prefixes:
        lines.append(f"- Study prefixes bucketed as family `other`: "
                     f"{', '.join(f'{k} (x{v})' for k, v in sorted(unmapped_prefixes.items()))}")
    lines.append("")
    lines.append(f"## Family summary (BH at q = {Q_FDR} within family)")
    lines.append("")
    lines.append("| Family | Studies | Claims | Nominal CI-excludes-zero | Survive BH | Survival rate of nominal |")
    lines.append("|---|---|---|---|---|---|")
    tot = [0, 0, 0, 0]
    for family, n_studies, n, n_nom, n_bh in fam_rows:
        rate = f"{n_bh / n_nom:.0%}" if n_nom else "-"
        lines.append(f"| {family} | {n_studies} | {n} | {n_nom} | {n_bh} | {rate} |")
        tot[0] += n_studies; tot[1] += n; tot[2] += n_nom; tot[3] += n_bh
    rate = f"{tot[3] / tot[2]:.0%}" if tot[2] else "-"
    lines.append(f"| **total** | {tot[0]} | **{tot[1]}** | **{tot[2]}** | **{tot[3]}** | {rate} |")
    lines.append("")
    lines.append("## Scoreboard bold wins vs BH")
    lines.append("")
    lines.append("The rolling scoreboard (`reports/SUMMARY.md`) marks "
                 f"{len(win_rows)} rows as bold ML wins. Per-study verdicts against the "
                 "family-level BH pass:")
    lines.append("")
    lines.append("| Win study | Family | Parsed claims | Nominal wins | BH survivors | Verdict |")
    lines.append("|---|---|---|---|---|---|")
    for wid, fam, n_c, n_nom, n_bh, status in win_rows:
        lines.append(f"| {wid} | {fam} | {n_c} | {n_nom} | {n_bh} | {status} |")
    lines.append("")
    n_fail = sum(1 for r in win_rows if r[5].startswith("FAILS"))
    n_missing = sum(1 for r in win_rows if r[5].startswith("NO PARSED"))
    n_ok = sum(1 for r in win_rows if r[5].startswith("survives"))
    lines.append(f"**Headline:** of {len(win_rows)} scoreboard bold wins, **{n_ok} survive BH** "
                 f"(at least one delta-CI claim), **{n_fail} fail BH**, and **{n_missing} have no "
                 "machine-readable delta CI at all** (win asserted in prose/derived numbers only).")
    lines.append("")
    lines.append("A BH-surviving claim is *necessary, not sufficient*: it does not repair "
                 "dependent-residual iid bootstraps, leakage, or unfair baselines. Studies whose "
                 "wins fail BH here (or have no parsable delta CI) must not be cited as wins "
                 "pending confirmation on the reserved partition "
                 "(`docs/CONFIRMATION_PARTITION.md`).")
    lines.append("")
    lines.append("Worked cautionary example: **S03k** (withdrawn from the bold wins on "
                 "2026-07-03) has delta-CI claims that *survive* BH here (e.g. "
                 "delta = -0.44 ns, CI [-0.84, -0.24] vs the analytic comparator), yet its gain "
                 "was falsified by the S03p/S03r feature-leakage null grids — multiplicity "
                 "control cannot detect leakage.")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("/home/billy/anaconda3/envs/nnbar_env/bin/python scripts/stats01_program_fdr.py")
    lines.append("```")
    lines.append("")
    lines.append("Artifacts: `claims.csv` (one row per delta-CI claim, with family, z, p, "
                 "BH-adjusted p, pass flag), `artifacts_without_claims.txt`.")
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    log.info("wrote %s", out_dir / "REPORT.md")

    # console headline
    print()
    print(f"claims parsed: {len(claims)}  |  nominal wins: {tot[2]}  |  BH survivors: {tot[3]}")
    for family, n_studies, n, n_nom, n_bh in fam_rows:
        print(f"  {family:18s} claims={n:5d} nominal={n_nom:4d} bh_pass={n_bh:4d}")
    print(f"scoreboard wins: {n_ok} survive / {n_fail} fail / {n_missing} unparsable "
          f"of {len(win_rows)}")
    print(f"output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
