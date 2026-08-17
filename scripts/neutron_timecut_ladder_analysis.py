#!/usr/bin/env python3
"""#1091 neutron timecut sensitivity-ladder analysis.

Reads the paired production-grid runs (p/d x {pin 10us, ext disabled}, same
seed) plus the 1 GeV wiring triple ({1 ns, 10 us, disabled}) from the ladder
runs directory and emits a self-describing JSON result:

  research/neutron_timecut_ladder/ladder_result.json

Per the issue's discriminating experiments:
  1. paired pin-vs-ext per-event observable deltas (same seed -> any
     difference is causal from the neutron tracking-time cut);
  2. neutron-step census (count, t_ns spectrum, in-scint fraction,
     deposits) and late (>1 us) scintillator-deposit census (kind 1);
  3. cumulative E_n(<T) deposit curve per run;
  4. wiring-control deltas (cut1ns vs ext) demonstrating the policy
     visibly truncates neutron history when set short enough to bite;
  5. adversarial tail check: per-event max |delta| over all paired events,
     not just means.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import uproot

RUNS = Path("/projects/hep/fs10/shared/nnbar/billy/ccb_1091_ladder/runs")
WT = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1091")
OUT = WT / "research/neutron_timecut_ladder/ladder_result.json"

EVENT_OBS = [
    "edep_scint_MeV", "edep_scint_raw_MeV",
    "adc_readout", "adc_f1far", "adc_f2near", "adc_f2far",
    "detected_readout", "detected_f1far", "detected_f2near", "detected_f2far",
    "n_scint_generated", "n_wls_generated",
]
T_GRID = [1.0, 10.0, 100.0, 1000.0, 10000.0, 1e9]  # ns cumulative-E grid

# Binary provenance by campaign job: the p-grid + wiring runs were
# produced under job 3507231 at e2baa589; the d-grid runs were produced
# under job 3508094 at ca65d63d, which adds the env-tunable optical-
# photon trap guard (CCB_OPTICAL_PHOTON_MAX_STEPS, default 100000) after
# d70_pin livelocked at event 1979 (single worker spinning in
# G4OpBoundaryProcess; see ADR-0013). Within every pin/ext pair both
# members share one binary, so the paired bit-identity tests are
# unaffected by the guard.
RUN_COMMIT = {
    **{f"{s}_{p}": "e2baa589" for s in ("p60", "p100", "p140")
       for p in ("pin2000", "ext2000")},
    **{f"{s}_{p}": "ca65d63d" for s in ("d70", "d110")
       for p in ("pin2000", "ext2000")},
    **{f"w1gev_{p}": "e2baa589" for p in ("cut1ns1000", "pin1000", "ext1000")},
}
GUARD_COMMITS = {"ca65d63d"}


def trap_guard_census(tag: str) -> dict:
    """Count OPTICAL_TRAP_KILL firings recorded in the run log."""
    log = RUNS / f"{tag}.log"
    out = {"guard_in_binary": RUN_COMMIT.get(tag) in GUARD_COMMITS}
    if not log.exists():
        out["log_present"] = False
        return out
    kills = {}
    for line in log.read_text().splitlines():
        if line.startswith("OPTICAL_TRAP_KILL event="):
            ev = int(line.split("event=")[1].split()[0])
            kills[ev] = kills.get(ev, 0) + 1
    out.update({"log_present": True, "kills": sum(kills.values()),
                "events_with_kills": len(kills)})
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_run(tag: str) -> dict:
    root = RUNS / f"{tag}.root"
    meta_path = Path(str(root) + ".meta.json")
    if not root.exists() or not meta_path.exists():
        return {"tag": tag, "present": False}
    meta = json.loads(meta_path.read_text())
    f = uproot.open(root)
    ev = f["events"].arrays(["event"] + EVENT_OBS, library="np")
    ns = f["neutron_steps"].arrays(
        ["kind", "t_ns", "edep_MeV", "ke_MeV", "in_scint", "pdg"], library="np")
    nph = f["photons"].num_entries
    order = np.argsort(ev["event"])
    ev = {k: v[order] for k, v in ev.items()}
    kind = ns["kind"].astype(int)
    t = ns["t_ns"].astype(float)
    edep = ns["edep_MeV"].astype(float)
    steps = kind == 0
    late = kind == 1
    return {
        "tag": tag, "present": True,
        "root_sha256": sha256(root),
        "policy_id": meta.get("neutron_timecut_policy_id"),
        "neutron_time_cut_us": meta.get("neutron_time_cut_us"),
        "particle": meta.get("particle"), "ke_MeV": meta.get("kinetic_energy_MeV"),
        "n_events": int(meta.get("n_events", -1)),
        "physics_list": meta.get("physics_list"),
        "geometry_hash": meta.get("geometry_hash"),
        "physics_hash": meta.get("physics_hash"),
        "git_commit": RUN_COMMIT.get(tag, "unknown"),
        "optical_trap_guard": trap_guard_census(tag),
        "n_photons": int(nph),
        "obs_sums": {k: float(ev[k].sum()) for k in EVENT_OBS},
        "neutron_census": {
            "n_steps": int(steps.sum()),
            "t_ns_max": float(t[steps].max()) if steps.any() else 0.0,
            "t_ns_p50": float(np.median(t[steps])) if steps.any() else 0.0,
            "n_steps_in_scint": int((ns["in_scint"].astype(int)[steps] == 1).sum()),
            "n_steps_with_edep": int((edep[steps] > 0).sum()),
            "sum_edep_steps_MeV": float(edep[steps].sum()),
            "n_steps_t_gt_1us": int((t[steps] > 1000).sum()),
            "n_steps_t_gt_10us": int((t[steps] > 10000).sum()),
            "n_late_scint_deposits": int(late.sum()),
            "sum_late_scint_edep_MeV": float(edep[late].sum()),
            "cumulative_edep_MeV_at_T_ns": {
                f"{T:g}": float(edep[(kind == 0) & (t < T)].sum()) for T in T_GRID},
            "t_spectrum": {
                "bins_ns": [0, 1, 10, 100, 1000, 10000, 1e9],
                "step_counts": [
                    int(((t[steps] >= lo) & (t[steps] < hi)).sum())
                    for lo, hi in zip([0, 1, 10, 100, 1000, 10000],
                                      [1, 10, 100, 1000, 10000, 1e9])],
            },
        },
        "_ev": ev,  # private, paired comparison only
    }


def paired_delta(pin: dict, ext: dict) -> dict:
    """Same-seed paired per-event comparison; identity check + adversarial tail."""
    if not (pin["present"] and ext["present"]):
        return {"present": False}
    n = min(pin["_ev"]["event"].size, ext["_ev"]["event"].size)
    out = {"present": True, "n_paired_events": int(n), "observables": {}}
    identical = True
    for k in EVENT_OBS:
        a, b = pin["_ev"][k][:n], ext["_ev"][k][:n]
        d = a.astype(float) - b.astype(float)
        bit_identical = bool(np.array_equal(a, b))
        identical &= bit_identical
        out["observables"][k] = {
            "bit_identical": bit_identical,
            "sum_pin": float(a.sum()), "sum_ext": float(b.sum()),
            "max_abs_delta": float(np.abs(d).max()) if n else 0.0,
            "n_events_differing": int((d != 0).sum()),
        }
    out["all_observables_bit_identical"] = identical
    out["photon_count_identical"] = pin["n_photons"] == ext["n_photons"]
    out["neutron_step_count_identical"] = (
        pin["neutron_census"]["n_steps"] == ext["neutron_census"]["n_steps"])
    return out


def public(run: dict) -> dict:
    return {k: v for k, v in run.items() if not k.startswith("_")}


def main() -> int:
    grid = [("p60", "proton", 60), ("p100", "proton", 100), ("p140", "proton", 140),
            ("d70", "deuteron", 70), ("d110", "deuteron", 110)]
    result = {
        "schema": "ccb-1091-ladder-result/1",
        "issue": 1091,
        "adr": "docs/adr/ADR-0013-neutron-tracking-time-cut.md",
        "binary_commit": "e2baa589 (p-grid + wiring) / ca65d63d "
                         "(d-grid: optical-photon trap guard)",
        "harness": "/projects/hep/fs10/shared/nnbar/billy/ccb_1091_ladder.slurm",
        "seed": 2, "threads": 8, "physics_list": "QGSP_BIC",
        "production_grid": [], "wiring_triple": [], "pairs": [], "wiring_deltas": {},
    }
    runs = {}
    for stem, part, ke in grid:
        for pol, sfx in (("pin", "pin2000"), ("ext", "ext2000")):
            tag = f"{stem}_{sfx}"
            runs[tag] = load_run(tag)
            runs[tag].setdefault("particle", part), runs[tag].setdefault("ke_MeV", ke)
            result["production_grid"].append(public(runs[tag]))
        result["pairs"].append({
            "point": stem, "particle": part, "ke_MeV": ke,
            "pin_tag": f"{stem}_pin2000", "ext_tag": f"{stem}_ext2000",
            "delta": paired_delta(runs[f"{stem}_pin2000"], runs[f"{stem}_ext2000"]),
        })
    for tag in ("w1gev_cut1ns1000", "w1gev_pin1000", "w1gev_ext1000"):
        runs[tag] = load_run(tag)
        result["wiring_triple"].append(public(runs[tag]))
    if runs["w1gev_cut1ns1000"]["present"] and runs["w1gev_ext1000"]["present"]:
        result["wiring_deltas"] = {
            "cut1ns_vs_ext": paired_delta(
                runs["w1gev_cut1ns1000"], runs["w1gev_ext1000"])}
    if runs["w1gev_pin1000"]["present"] and runs["w1gev_ext1000"]["present"]:
        # production-policy pairing inside the neutron-rich fixture: the 10 us
        # reference cut must not bite here either (all tails end << 1 us)
        result["wiring_deltas"]["pin_vs_ext"] = paired_delta(
            runs["w1gev_pin1000"], runs["w1gev_ext1000"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    # console summary
    for p in result["pairs"]:
        d = p["delta"]
        if not d.get("present"):
            print(f"{p['point']:5s}: INCOMPLETE")
            continue
        ident = d["all_observables_bit_identical"] and d["photon_count_identical"]
        pin = runs[p["pin_tag"]]
        cens = pin["neutron_census"]
        print(f"{p['point']:5s}: bit_identical={ident}  n_neutron_steps="
              f"{cens['n_steps']}  t_max={cens['t_ns_max']:.1f}ns  "
              f"late>1us_rows={cens['n_steps_t_gt_1us']+cens['n_late_scint_deposits']}")
    if result["wiring_deltas"]:
        wd = result["wiring_deltas"]["cut1ns_vs_ext"]
        print("wiring cut1ns_vs_ext: bit_identical=",
              wd["all_observables_bit_identical"], " photons_identical=",
              wd["photon_count_identical"])
        for k in ("edep_scint_MeV", "detected_readout", "adc_readout"):
            o = wd["observables"][k]
            print(f"  {k}: pin_sum={o['sum_pin']:.6g} ext_sum={o['sum_ext']:.6g} "
                  f"max|d|={o['max_abs_delta']:.6g} n_diff={o['n_events_differing']}")
    print(f"WROTE {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
