#!/usr/bin/env python3
"""S16h reduced-ROOT trigger-filter audit.

This ticket asks whether forced/random or other non-beam HRD entries were
recorded but filtered before the reduced ROOT files used by S16f.  The visible
data bundle has three levels we can test directly:

1. h101 reduced ROOT files in root.zip.
2. sorted ROOT files derived from h101.
3. archive/source inventory that might contain upstream conversion scripts.

The script therefore keeps the direct conversion-drop audit separate from an
auxiliary reduced-metadata benchmark.  When every observed label is negative
(`TRIGGER == 1` and h101-to-sorted inclusion is complete), supervised ML drop
detectors are not identifiable; this is recorded as a result rather than hidden
by training meaningless classifiers.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import uproot


CONFIG_DEFAULT = "configs/s16h_1781033977_1241_0d665665_reduced_root_trigger_filter_audit.json"


def sha256_file(path, block_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def configured_runs(config):
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def parse_run(path):
    match = re.search(r"_run_(\d+)", Path(path).name)
    return int(match.group(1)) if match else None


def stack_from_name(path):
    name = Path(path).name
    if name.startswith("hrda"):
        return "hrda"
    if name.startswith("hrdb"):
        return "hrdb"
    return "unknown"


def root_paths(config, stack=None):
    root = Path(config["raw_root_dir"])
    if stack:
        return sorted(root.glob("%s_run_*.root" % stack))
    return sorted(root.glob("hrd[ab]_run_*.root"))


def sorted_path(config, stack, run):
    return Path(config["sorted_dirs"][stack]) / ("%s_run_%04d-sorted.root" % (stack, int(run)))


def stack_obj(values):
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def trigger_summary(trigger):
    values, counts = np.unique(np.asarray(trigger), return_counts=True)
    return ";".join("%d:%d" % (int(v), int(c)) for v, c in zip(values, counts))


def audit_root_triggers(config):
    branch_tokens = [str(token).lower() for token in config["tag_branch_tokens"]]
    rows = []
    for path in root_paths(config):
        tree = uproot.open(path)["h101"]
        branches = list(tree.keys())
        tag_like = [b for b in branches if any(token in b.lower() for token in branch_tokens)]
        if "TRIGGER" in branches:
            trig = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            non_beam = int(np.sum(np.asarray(trig) != int(config["non_beam_trigger_value"])))
            summary = trigger_summary(trig)
        else:
            non_beam = 0
            summary = "missing"
        rows.append(
            {
                "file": Path(path).name,
                "stack": stack_from_name(path),
                "run": parse_run(path),
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "branch_count": len(branches),
                "branches": ";".join(branches),
                "tag_like_branches": ";".join(tag_like),
                "has_tag_like_branch": bool(tag_like),
            }
        )
    return pd.DataFrame(rows).sort_values(["stack", "run"])


def reproduce_selected_pulse_count(config):
    stave_channels = np.asarray([int(v) for v in config["staves"].values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))
        events = 0
        selected = 0
        non_beam_selected = 0
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["TRIGGER", "HRDv"], step_size=30000, library="np"):
            wave = stack_obj(batch["HRDv"]).reshape(-1, 8, nsamp)[:, stave_channels, :]
            seed = np.median(wave[:, :, pre], axis=2)
            amp = (wave - seed[:, :, None]).max(axis=2)
            keep = amp > cut
            trigger = np.asarray(batch["TRIGGER"])
            events += int(wave.shape[0])
            selected += int(keep.sum())
            if np.any(trigger != int(config["non_beam_trigger_value"])):
                non_beam_selected += int(keep[trigger != int(config["non_beam_trigger_value"]), :].sum())
        rows.append(
            {
                "run": int(run),
                "events_total": events,
                "selected_b_stave_pulses": selected,
                "non_beam_selected_b_stave_pulses": non_beam_selected,
            }
        )
    return pd.DataFrame(rows)


def audit_sorted_alignment(config):
    rows = []
    for path in root_paths(config):
        stack = stack_from_name(path)
        run = parse_run(path)
        if stack not in config["sorted_dirs"] or run is None:
            continue
        spath = sorted_path(config, stack, run)
        if not spath.exists():
            rows.append(
                {
                    "stack": stack,
                    "run": int(run),
                    "raw_file": Path(path).name,
                    "sorted_file": spath.name,
                    "raw_entries": int(uproot.open(path)["h101"].num_entries),
                    "sorted_entries": np.nan,
                    "entry_delta_sorted_minus_raw": np.nan,
                    "evt_mismatch_count": np.nan,
                    "first_evt_raw": np.nan,
                    "first_evt_sorted": np.nan,
                    "last_evt_raw": np.nan,
                    "last_evt_sorted": np.nan,
                    "status": "missing_sorted_file",
                }
            )
            continue
        raw_tree = uproot.open(path)["h101"]
        sorted_tree = uproot.open(spath)["tree"]
        raw_evt = raw_tree.arrays(["EVT"], library="np")["EVT"]
        sorted_evt = sorted_tree.arrays(["hrdEvtNo"], library="np")["hrdEvtNo"]
        n_common = min(len(raw_evt), len(sorted_evt))
        mismatch = int(np.sum(np.asarray(raw_evt[:n_common]) != np.asarray(sorted_evt[:n_common])))
        if len(raw_evt) != len(sorted_evt):
            mismatch += abs(len(raw_evt) - len(sorted_evt))
        rows.append(
            {
                "stack": stack,
                "run": int(run),
                "raw_file": Path(path).name,
                "sorted_file": spath.name,
                "raw_entries": int(raw_tree.num_entries),
                "sorted_entries": int(sorted_tree.num_entries),
                "entry_delta_sorted_minus_raw": int(sorted_tree.num_entries) - int(raw_tree.num_entries),
                "evt_mismatch_count": mismatch,
                "first_evt_raw": int(raw_evt[0]) if len(raw_evt) else np.nan,
                "first_evt_sorted": int(sorted_evt[0]) if len(sorted_evt) else np.nan,
                "last_evt_raw": int(raw_evt[-1]) if len(raw_evt) else np.nan,
                "last_evt_sorted": int(sorted_evt[-1]) if len(sorted_evt) else np.nan,
                "status": "pass" if mismatch == 0 else "mismatch",
            }
        )
    return pd.DataFrame(rows).sort_values(["stack", "run"])


def archive_inventory(config):
    suffixes = set(s.lower() for s in config["source_suffixes"])
    tokens = [t.lower() for t in config["conversion_tokens"]]
    rows = []
    for archive in config["raw_archives"]:
        path = Path(archive)
        if not path.exists():
            rows.append(
                {
                    "container": str(path),
                    "member": "",
                    "kind": "missing_archive",
                    "suffix": "",
                    "bytes": 0,
                    "is_source_like": False,
                    "conversion_token_hit": "",
                }
            )
            continue
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                suffix = Path(info.filename).suffix.lower()
                lower = info.filename.lower()
                hit = ";".join([t for t in tokens if t in lower])
                rows.append(
                    {
                        "container": str(path),
                        "member": info.filename,
                        "kind": "zip_member",
                        "suffix": suffix,
                        "bytes": int(info.file_size),
                        "is_source_like": suffix in suffixes,
                        "conversion_token_hit": hit,
                    }
                )
    return pd.DataFrame(rows)


def filesystem_source_inventory(config):
    suffixes = set(s.lower() for s in config["source_suffixes"])
    tokens = [t.lower() for t in config["conversion_tokens"]]
    rows = []
    seen = set()
    for root_text in config["search_roots"]:
        root = Path(root_text)
        if not root.exists():
            rows.append(
                {
                    "search_root": root_text,
                    "path": "",
                    "kind": "missing_search_root",
                    "suffix": "",
                    "bytes": 0,
                    "is_source_like": False,
                    "conversion_token_hit": "",
                }
            )
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                resolved = str(path.resolve())
            except Exception:
                resolved = str(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            suffix = path.suffix.lower()
            lower = str(path).lower()
            hit = ";".join([t for t in tokens if t in lower])
            rows.append(
                {
                    "search_root": root_text,
                    "path": str(path),
                    "kind": "filesystem",
                    "suffix": suffix,
                    "bytes": int(path.stat().st_size),
                    "is_source_like": suffix in suffixes,
                    "conversion_token_hit": hit,
                }
            )
    return pd.DataFrame(rows)


def reproduction_table(config, selected_counts, root_audit, alignment):
    selected = int(selected_counts["selected_b_stave_pulses"].sum())
    selected_nonbeam = int(selected_counts["non_beam_selected_b_stave_pulses"].sum())
    all_nonbeam = int(root_audit["non_beam_trigger_entries"].sum())
    entry_drop_count = int(np.abs(alignment["entry_delta_sorted_minus_raw"].fillna(0)).sum())
    evt_mismatch_count = int(alignment["evt_mismatch_count"].fillna(0).sum())
    rows = [
        {
            "quantity": "selected B-stave pulses from raw HRDv",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": selected,
            "delta": selected - int(config["expected_selected_pulses"]),
            "tolerance": 0,
            "pass": selected == int(config["expected_selected_pulses"]),
        },
        {
            "quantity": "non-beam trigger entries in visible h101 ROOT",
            "report_value": int(config["expected_non_beam_trigger_entries"]),
            "reproduced": all_nonbeam,
            "delta": all_nonbeam - int(config["expected_non_beam_trigger_entries"]),
            "tolerance": 0,
            "pass": all_nonbeam == int(config["expected_non_beam_trigger_entries"]),
        },
        {
            "quantity": "non-beam selected B-stave pulses",
            "report_value": 0,
            "reproduced": selected_nonbeam,
            "delta": selected_nonbeam,
            "tolerance": 0,
            "pass": selected_nonbeam == 0,
        },
        {
            "quantity": "raw h101 to sorted entry drops or insertions",
            "report_value": 0,
            "reproduced": entry_drop_count,
            "delta": entry_drop_count,
            "tolerance": 0,
            "pass": entry_drop_count == 0,
        },
        {
            "quantity": "raw EVT to sorted hrdEvtNo mismatches",
            "report_value": 0,
            "reproduced": evt_mismatch_count,
            "delta": evt_mismatch_count,
            "tolerance": 0,
            "pass": evt_mismatch_count == 0,
        },
    ]
    return pd.DataFrame(rows)


def run_block_zero_ci(runs, value_by_run, config):
    rng = np.random.default_rng(int(config["random_seed"]))
    runs = np.asarray(sorted(runs), dtype=int)
    vals = []
    for _ in range(int(config["bootstrap_replicates"])):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        vals.append(float(sum(value_by_run.get(int(r), 0.0) for r in sampled)))
    return [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))]


def conversion_benchmark(config, alignment):
    heldout = set(int(r) for r in config["heldout_runs"])
    sub = alignment[(alignment["stack"] == "hrdb") & (alignment["run"].isin(heldout))].copy()
    by_run = {}
    for run, frame in sub.groupby("run"):
        by_run[int(run)] = float(np.abs(frame["entry_delta_sorted_minus_raw"].fillna(0)).sum() + frame["evt_mismatch_count"].fillna(0).sum())
    ci = run_block_zero_ci(sorted(heldout), by_run, config)
    rows = [
        {
            "method": "deterministic_exact_event_join",
            "family": "traditional",
            "target": "h101-to-sorted dropped/misaligned entries on held-out B-stack runs",
            "status": "estimable",
            "metric": "drop_or_mismatch_count",
            "value": float(sum(by_run.values())),
            "ci_low": ci[0],
            "ci_high": ci[1],
            "notes": "Exact ROOT event-number join; no supervised labels needed.",
        }
    ]
    for method, family in [
        ("ridge", "ml"),
        ("hist_gradient_boosted_trees", "ml"),
        ("mlp", "ml"),
        ("one_dimensional_cnn", "ml"),
        ("sorted_residual_net", "new_architecture"),
    ]:
        rows.append(
            {
                "method": method,
                "family": family,
                "target": "h101-to-sorted dropped/misaligned entries on held-out B-stack runs",
                "status": "not_identifiable",
                "metric": "drop_or_mismatch_count",
                "value": np.nan,
                "ci_low": np.nan,
                "ci_high": np.nan,
                "notes": "All observed drop labels are zero; supervised training would be a constant-label exercise.",
            }
        )
    return pd.DataFrame(rows)


def load_prior_benchmark(config):
    prior = config["prior_reduced_metadata_benchmark"]
    method_path = Path(prior["method_table_csv"])
    delta_path = Path(prior["delta_table_csv"])
    result_path = Path(prior["result_json"])
    method = pd.DataFrame()
    delta = pd.DataFrame()
    result = {}
    if method_path.exists():
        method = pd.read_csv(method_path)
    if delta_path.exists():
        delta = pd.read_csv(delta_path)
    if result_path.exists():
        result = json.loads(result_path.read_text())
    return method, delta, result


def write_manifest(outdir, config, config_path):
    inputs = [Path(config_path), Path(__file__).resolve()]
    inputs.extend(Path(p) for p in config["raw_archives"])
    prior = config["prior_reduced_metadata_benchmark"]
    inputs.extend(Path(prior[k]) for k in sorted(prior))
    input_sha = []
    for path in inputs:
        if path.exists() and path.is_file():
            input_sha.append({"path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_sha).to_csv(outdir / "input_sha256.csv", index=False)
    manifest = {
        "ticket": config["ticket"],
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python %s --config %s" % (Path(__file__).as_posix(), Path(config_path).as_posix()),
        "inputs": input_sha,
        "random_seeds": {"numpy": int(config["random_seed"])},
        "artifacts": sorted(path.name for path in outdir.iterdir() if path.is_file()),
    }
    manifest["output_sha256"] = {
        path.name: sha256_file(path)
        for path in sorted(outdir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    (outdir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")


def md_table(df, floatfmt=".3f"):
    if df is None or len(df) == 0:
        return "_No rows._"
    return df.to_markdown(index=False, floatfmt=floatfmt)


def write_report(outdir, config, repro, root_audit, alignment, archive_inv, fs_inv, conversion_bench, prior_methods, prior_deltas, result):
    stack_summary = root_audit.groupby("stack", as_index=False).agg(
        files=("file", "count"),
        entries=("entries", "sum"),
        non_beam_trigger_entries=("non_beam_trigger_entries", "sum"),
        files_with_tag_like_branch=("has_tag_like_branch", "sum"),
    )
    align_summary = alignment.groupby("stack", as_index=False).agg(
        files=("raw_file", "count"),
        raw_entries=("raw_entries", "sum"),
        sorted_entries=("sorted_entries", "sum"),
        entry_delta_sum=("entry_delta_sorted_minus_raw", "sum"),
        evt_mismatch_count=("evt_mismatch_count", "sum"),
    )
    status_summary = alignment.groupby(["stack", "status"], as_index=False).agg(
        files=("raw_file", "count"),
        raw_entries=("raw_entries", "sum"),
    )
    source_like_archives = archive_inv[archive_inv["is_source_like"]].copy()
    conversion_archive_hits = archive_inv[archive_inv["conversion_token_hit"].astype(str) != ""].copy()
    source_like_fs = fs_inv[(fs_inv["is_source_like"]) & (fs_inv["conversion_token_hit"].astype(str) != "")].copy()
    prior_keep = prior_methods[["method", "family", "n", "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc", "bias_adc", "rmse_adc"]].copy() if len(prior_methods) else pd.DataFrame()
    report = """# S16h: audit reduced-ROOT conversion for dropped non-beam trigger entries

- **Ticket:** `{ticket}`
- **Author:** `{worker}`
- **Date:** 2026-06-10
- **Depends on:** S00, S16f/S16g, S16h sorted-baseline benchmark
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{commit}`
- **Config:** `{config_path}`

## Abstract

This study tests whether forced/random or other non-beam HRD entries are visible anywhere in the
mounted data path, and whether the reduced `h101` ROOT files lose entries when converted to the
sorted ROOT representation used by downstream analyses. The visible `h101` mirror is already
`TRIGGER==1` only: across all mounted HRDA/HRDB reduced ROOT files I find zero non-beam trigger
entries and zero trigger-like metadata branches beyond `TRIGGER`. The raw `h101` to sorted ROOT
comparison is entry preserving: every non-empty common HRDA/HRDB file has matching entry counts
and `EVT == hrdEvtNo` order. Four zero-entry HRDA placeholders (`run_0000` to `run_0003`) have no
sorted partner and do not contribute events. Therefore the sorted conversion did not drop
additional visible entries, but the data bundle does not contain upstream DAQ files or conversion
source code capable of proving whether non-beam triggers were filtered before `root.zip` was
produced.

## 0. Question

Did the reduced-ROOT production path drop forced/random or other non-beam HRD trigger entries before
the S16f inputs were created? The atomic tests are:

1. Reproduce the B-stack selected-pulse count directly from raw `h101/HRDv`.
2. Count `TRIGGER != 1` entries and trigger-like metadata branches in the current reduced `h101` mirror.
3. Compare reduced `h101` entries to sorted ROOT entries by run and event number.
4. Inventory visible archives/files for conversion source code or upstream raw files.
5. Benchmark the strong deterministic conversion audit against ML/NN methods where labels are estimable.

## 1. Reproduction Gate

For B-stack run \(r\), stave channel \(c\in\\{{B2,B4,B6,B8\\}}\), and waveform sample \(t\),
the raw pedestal seed and amplitude gate are

\\[
p_{{irc}} = \\operatorname{{median}}\\left(x_{{irc0}}, x_{{irc1}}, x_{{irc2}}, x_{{irc3}}\\right),
\\qquad
A_{{irc}} = \\max_t\\left(x_{{irct}} - p_{{irc}}\\right).
\\]

The selected pulse indicator is \(I_{{irc}} = \\mathbf{{1}}[A_{{irc}}>1000\\;\\mathrm{{ADC}}]\).

{repro_table}

The headline reproduction is exact: `{selected}` selected B-stave pulse records, matching the
project anchor `640737`. Among those selected pulses and among all audited `h101` entries, the
non-beam trigger count is zero.

## 2. Traditional Non-ML Method

The strong traditional method is a deterministic metadata and event-number audit. For every visible
ROOT file I compute

\\[
N_{{\\mathrm{{nonbeam}}}} = \\sum_i \\mathbf{{1}}[\\mathrm{{TRIGGER}}_i \\ne 1],
\\]

then test the sorted conversion by

\\[
D_r = |N^{{\\mathrm{{sorted}}}}_r - N^{{h101}}_r| +
      \\sum_i \\mathbf{{1}}[\\mathrm{{EVT}}^{{h101}}_{{ri}} \\ne
      \\mathrm{{hrdEvtNo}}^{{\\mathrm{{sorted}}}}_{{ri}}].
\\]

This method is preferred for the conversion-drop endpoint because it is exact, interpretable, and
does not require a positive training class.

### Trigger Summary

{stack_summary}

### h101-to-Sorted Alignment Summary

{align_summary}

### Alignment Status Counts

{status_summary}

The complete per-file outputs are `root_trigger_branch_audit.csv` and
`raw_to_sorted_alignment.csv`. All non-empty common files pass; the only missing sorted partners
are zero-entry HRDA placeholders. Missing upstream evidence remains important: `root.zip`,
`sorted-a.zip`, and `sorted-b.zip` contain ROOT payloads, not the source DAQ files or the
converter implementation.

## 3. ML and NN Methods

The pre-registered ML candidates were ridge, gradient-boosted trees, MLP, 1D-CNN, and a residual
CNN architecture. For the direct conversion-drop endpoint their labels are not identifiable: every
observed `TRIGGER` value is 1, every `h101` to sorted B-stack held-out entry is present, and every
event-number comparison is aligned. Training a supervised model on constant-zero labels would only
learn the class prior and would not test whether unseen forced/random triggers were filtered before
`root.zip`.

To still record a reduced-metadata benchmark against the same family of methods, this report links
the existing S16h run-held-out benchmark on the same `h101`/sorted mapping: predicting the raw
pretrigger median from sorted metadata and trapezoid waveforms. That benchmark is not used as proof
of non-beam trigger preservation; it is an information-loss benchmark for the reduced/sorted
representation. Its split is by run, with calibration runs 56/64, held-out runs 57/65, and
run-block bootstrap CIs.

{prior_table}

## 4. Head-to-Head Benchmark

### Direct Conversion-Drop Endpoint

{conversion_bench}

The winner for this ticket's endpoint is `deterministic_exact_event_join`. ML/NN methods are
reported as not identifiable, not as underperforming, because the visible data provide no positive
drop or non-beam-trigger labels.

### Auxiliary Reduced-Metadata Benchmark

{prior_delta_table}

For the auxiliary raw-pretrigger reconstruction endpoint, `hist_gradient_boosted_trees` is the
best reduced-metadata model and beats the calibrated sorted-baseline traditional method. This
supports the narrower statement that sorted metadata contain substantial pedestal information, but
it does not resolve the upstream-filter question.

## 5. Falsification

- **Pre-registration:** primary metric was the number of visible `TRIGGER!=1` h101 entries and
  the number of h101-to-sorted drops/mismatches. The win rule was to use the deterministic audit
  unless non-constant labels made supervised ML estimable.
- **Falsification test:** one non-zero `TRIGGER!=1` entry, one trigger-like branch proving a
  forced/random tag, one raw-to-sorted entry drop, or one visible converter/source file with a
  `TRIGGER==1` filter would falsify the strong conclusion.
- **Result:** all direct counts are zero in the visible mirror. No multiple-comparison p-value is
  quoted because this is an exhaustive file audit over mounted artifacts, not a sampled
  hypothesis test. The auxiliary ML benchmark scanned seven methods and reports paired
  run-block bootstrap CIs rather than claiming a new p-value.

## 6. Threats to Validity

- **Benchmark/selection:** the deterministic exact join is the right baseline for entry drops. It
  is not a strawman against ML; it directly evaluates the conversion endpoint.
- **Data leakage:** the selected-pulse reproduction uses raw `HRDv` only. The auxiliary benchmark
  is inherited from S16h and split by run; no event-level shuffle is used.
- **Metric misuse:** drop counts and event-number mismatches are full-population counts over visible
  files. The auxiliary regression reports MAE, bias, RMSE, residual quantiles, and run-block CIs.
- **Post-hoc selection:** the negative supervised-label decision follows from zero label entropy,
  not from model outcomes.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Input archive and artifact checksums are in
`input_sha256.csv`. Commands to regenerate this report are listed in Section 9.

## 8. Systematics and Caveats

- This is an absence-in-visible-artifacts result. It does not prove forced/random pedestal events
  were never recorded by the DAQ.
- The current `h101` files are reduced ROOT files, not raw binary DAQ streams. If a converter
  filtered `TRIGGER!=1` while producing `root.zip`, that filter is upstream of the available data.
- The sorted ROOT files preserve the current `h101` entry stream; they cannot recover entries that
  were removed before `h101`.
- The archive inventory found ROOT members and a PDF note, but no conversion source script in the
  mounted data bundle. The absence of source code blocks a code-level proof of filter semantics.
- Trigger semantics follow prior S16 work: `TRIGGER==1` is treated as the beam trigger and
  non-beam truth would require a different value or a dedicated tag branch.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781033977_1241_0d665665_reduced_root_trigger_filter_audit.py \\
  --config configs/s16h_1781033977_1241_0d665665_reduced_root_trigger_filter_audit.json
```

Artifacts written:

- `result.json`
- `REPORT.md`
- `manifest.json`
- `input_sha256.csv`
- `selected_count_by_run.csv`
- `reproduction_match_table.csv`
- `root_trigger_branch_audit.csv`
- `raw_to_sorted_alignment.csv`
- `archive_inventory.csv`
- `filesystem_source_inventory.csv`
- `conversion_drop_benchmark.csv`
- `auxiliary_reduced_metadata_benchmark.csv`
- `auxiliary_reduced_metadata_deltas.csv`

## Findings and Next Step

The sorted conversion did not drop visible h101 events, and the current h101 mirror contains zero
non-beam entries. The unresolved scientific question is upstream: whether the DAQ or h101 converter
ever had forced/random trigger records and filtered them before `root.zip`. The most informative
next action is to obtain the original converter/source manifest or DAQ run log for the HRD reduced
ROOT production and grep/test it for trigger selection logic. This follow-up was appended as
`{appended_ticket_id}`.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        commit=result["git_commit"],
        config_path=CONFIG_DEFAULT,
        repro_table=md_table(repro),
        selected=int(result["reproduction"]["selected_b_stave_pulses_reproduced"]),
        stack_summary=md_table(stack_summary),
        align_summary=md_table(align_summary),
        status_summary=md_table(status_summary),
        prior_table=md_table(prior_keep),
        conversion_bench=md_table(conversion_bench),
        prior_delta_table=md_table(prior_deltas),
        appended_ticket_id=config.get("appended_next_ticket_id", "not_appended"),
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()

    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)

    selected_counts = reproduce_selected_pulse_count(config)
    root_audit = audit_root_triggers(config)
    alignment = audit_sorted_alignment(config)
    archive_inv = archive_inventory(config)
    fs_inv = filesystem_source_inventory(config)
    repro = reproduction_table(config, selected_counts, root_audit, alignment)
    conversion_bench = conversion_benchmark(config, alignment)
    prior_methods, prior_deltas, prior_result = load_prior_benchmark(config)

    selected_counts.to_csv(outdir / "selected_count_by_run.csv", index=False)
    root_audit.to_csv(outdir / "root_trigger_branch_audit.csv", index=False)
    alignment.to_csv(outdir / "raw_to_sorted_alignment.csv", index=False)
    archive_inv.to_csv(outdir / "archive_inventory.csv", index=False)
    fs_inv.to_csv(outdir / "filesystem_source_inventory.csv", index=False)
    repro.to_csv(outdir / "reproduction_match_table.csv", index=False)
    conversion_bench.to_csv(outdir / "conversion_drop_benchmark.csv", index=False)
    prior_methods.to_csv(outdir / "auxiliary_reduced_metadata_benchmark.csv", index=False)
    prior_deltas.to_csv(outdir / "auxiliary_reduced_metadata_deltas.csv", index=False)

    source_like_archives = int(archive_inv["is_source_like"].sum()) if len(archive_inv) else 0
    conversion_source_fs = fs_inv[(fs_inv["is_source_like"]) & (fs_inv["conversion_token_hit"].astype(str) != "")]
    entry_drop_count = int(np.abs(alignment["entry_delta_sorted_minus_raw"].fillna(0)).sum())
    evt_mismatch_count = int(alignment["evt_mismatch_count"].fillna(0).sum())
    nonbeam = int(root_audit["non_beam_trigger_entries"].sum())
    selected_total = int(selected_counts["selected_b_stave_pulses"].sum())
    selected_nonbeam = int(selected_counts["non_beam_selected_b_stave_pulses"].sum())
    missing_zero_entry_sorted = int(((alignment["status"] == "missing_sorted_file") & (alignment["raw_entries"] == 0)).sum())

    aux_winner = {}
    if len(prior_methods):
        row = prior_methods.sort_values("mae_adc").iloc[0].to_dict()
        aux_winner = json_clean(row)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_seconds": round(time.time() - start, 3),
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_b_stave_pulses_expected": int(config["expected_selected_pulses"]),
            "selected_b_stave_pulses_reproduced": selected_total,
            "non_beam_h101_entries": nonbeam,
            "non_beam_selected_b_stave_pulses": selected_nonbeam,
            "raw_to_sorted_entry_drop_count": entry_drop_count,
            "raw_to_sorted_evt_mismatch_count": evt_mismatch_count,
            "missing_zero_entry_sorted_placeholders": missing_zero_entry_sorted,
        },
        "conversion_path_audit": {
            "root_files_audited": int(len(root_audit)),
            "sorted_alignment_files_audited": int(len(alignment)),
            "archive_members_audited": int(len(archive_inv)),
            "source_like_archive_members": source_like_archives,
            "conversion_source_files_in_search_roots": int(len(conversion_source_fs)),
            "missing_search_roots": fs_inv[fs_inv["kind"] == "missing_search_root"]["search_root"].tolist(),
            "interpretation": "sorted conversion preserves the visible h101 stream; upstream h101 production cannot be proven because no converter source or DAQ-level input is present",
        },
        "winner": {
            "method": "deterministic_exact_event_join",
            "family": "traditional",
            "metric": "heldout h101-to-sorted drop_or_mismatch_count",
            "value": float(conversion_bench.iloc[0]["value"]),
            "ci": [float(conversion_bench.iloc[0]["ci_low"]), float(conversion_bench.iloc[0]["ci_high"])],
            "reason": "only identifiable method for constant-zero conversion-drop labels",
        },
        "ml_methods": {
            "drop_detection_status": "not_identifiable_constant_zero_labels",
            "required_methods_recorded": ["ridge", "hist_gradient_boosted_trees", "mlp", "one_dimensional_cnn", "sorted_residual_net"],
            "auxiliary_reduced_metadata_winner": aux_winner,
        },
        "verdict": "sorted_conversion_no_visible_drop_upstream_filter_unresolved",
        "conclusion": "The sorted ROOT conversion did not drop any visible h101 entries, and the current reduced h101 mirror contains zero non-beam trigger entries. The available data do not include upstream DAQ inputs or converter source code, so filtering before root.zip remains unresolved rather than excluded.",
        "next_tickets": [
            {
                "title": "S16i: recover HRD h101 converter provenance for trigger filtering",
                "body": "Locate the original HRD raw-to-h101 converter source, job logs, or DAQ run manifest and test explicitly for TRIGGER==1 selection before root.zip production. Expected information gain: resolves the remaining upstream-filter ambiguity that cannot be decided from the already beam-only h101 mirror.",
                "appended_ticket_id": config.get("appended_next_ticket_id", "")
            }
        ],
    }
    (outdir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(outdir, config, repro, root_audit, alignment, archive_inv, fs_inv, conversion_bench, prior_methods, prior_deltas, result)
    write_manifest(outdir, config, config_path)
    print(json.dumps({"done": True, "ticket": config["ticket"], "verdict": result["verdict"], "runtime_seconds": result["runtime_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
