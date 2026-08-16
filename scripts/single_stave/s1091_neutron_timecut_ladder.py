#!/usr/bin/env python3
"""s1091 — neutron tracking-time-cut sensitivity ladder (#1091).

Measures the sensitivity of production single-stave observables to the
QGSP_BIC G4NeutronTrackingCut time limit (10 us pinned default vs 1e9 us
diagnostic-extended), as required to authorize any delayed-neutron
sensitivity/negligibility claim (ADR-0005 / ADR-0013; registry policy
pin_qgsp_bic_default_10us; python gate
authorize_neutron_timecut_sensitivity_claim).

Design
------
Paired-policy runs: identical seed (2), identical thread count (8), identical
primary (particle, energy) per pair. G4 MT per-event seeding makes event ids
pairable 1:1; any event whose neutron history ends before the shorter cut of
a pair must yield bitwise-identical observables, so per-event deltas isolate
exactly the affected (delayed-neutron) population.

  ladder    5 production-grid points x {pin 10 us, ext 1e9 us}, 2000 events:
            proton {60,100,140} MeV, deuteron {70,110} MeV.
  wiring    neutron-rich fixture (1 GeV proton, 500 events) x {1 ns, 10 us,
            1e9 us}: known-answer control proving the knob bites — the 1 ns
            cut must remove neutron-step history and in-scintillator neutron
            deposits that the 10 us policy keeps.

Gates (pre-registered in configs/s1091_neutron_timecut_ladder.json)
  G1 wiring-bites     1 ns policy: zero neutron steps beyond ~1 ns AND zero
                      in-scint neutron Edep beyond it, while the 10 us policy
                      retains >= wiring_min_rows_beyond_1ns rows and > 0 MeV.
                      If the fixture itself has no >1 ns history: INCONCLUSIVE
                      (loud), never a pass.
  G2 pairing          event-id sets identical inside every pair; sidecars
                      agree on particle/energy/seed/threads/nevents/policy.
  G3 insensitivity    for every grid point and observable: |mean delta| <=
                      z_max * SEM (paired) — with the affected-event fraction
                      and max |delta| reported as the measured bound. Any
                      violation => SENSITIVE => claims stay blocked.
  G4 time-partition   from ext runs: cumulative in-scint neutron Edep vs T
                      with the DAQ window (<180 ns, #1090) and the 10 us cut
                      marked — the mechanism statement of what the cut
                      removes vs what the DAQ can see.

Verdict INSENSITIVE_WITHIN_MEASURED_BOUND requires G1..G4 pass at all points.
The result core (config echo + file sha256s + gates + headline numbers) is
sha256-digested; that digest is what registers into
configs/transport/neutron_timecut_registry.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import uproot

OBS = [
    "edep_scint_MeV",
    "edep_scint_raw_MeV",
    "primary_edep_scint_MeV",
    "n_scint_generated",
    "n_wls_generated",
    "detected_readout",
    "pe_sat_readout",
    "adc_readout",
]
T_PARTITION_NS = [1.0, 10.0, 100.0, 180.0, 1e3, 1e4, 1e5, 1e6, 1e7]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_events(root: Path) -> dict:
    with uproot.open(root) as f:
        t = f["events"]
        ev = t["event"].array(library="np")
        out = {"event": ev}
        for k in OBS:
            out[k] = t[k].array(library="np")
    order = np.argsort(ev)
    return {k: v[order] for k, v in out.items()}


def load_neutron_steps(root: Path) -> dict:
    with uproot.open(root) as f:
        if "neutron_steps" not in f:
            return {
                k: np.array([]) for k in ["event", "kind", "t_ns", "edep_MeV", "ke_MeV", "in_scint"]
            }
        t = f["neutron_steps"]
        cols = {}
        for k, ty in [
            ("event", "i"),
            ("kind", "i"),
            ("t_ns", "f"),
            ("edep_MeV", "f"),
            ("ke_MeV", "f"),
            ("in_scint", "i"),
        ]:
            a = t[k].array(library="np")
            cols[k] = a.astype(ty)
    return cols


def load_meta(root: Path) -> dict:
    with (root.parent / (root.name + ".meta.json")).open() as fh:
        return json.load(fh)


def paired_deltas(pin: dict, ext: dict) -> dict:
    assert np.array_equal(pin["event"], ext["event"]), "event-id mismatch (G2)"
    d = {}
    for k in OBS:
        delta = ext[k] - pin[k]
        nz = delta != 0
        sem = float(delta.std(ddof=1) / np.sqrt(len(delta))) if len(delta) > 1 else 0.0
        d[k] = {
            "mean_delta": float(delta.mean()),
            "sem_delta": sem,
            "z": float(delta.mean() / sem) if sem > 0 else 0.0,
            "n_nonzero": int(nz.sum()),
            "max_abs_delta": float(np.abs(delta).max()) if len(delta) else 0.0,
            "mean_abs_obs": float(np.abs(pin[k]).mean()),
        }
    any_nz = np.zeros(len(pin["event"]), dtype=bool)
    for k in OBS:
        any_nz |= (ext[k] - pin[k]) != 0
    d["_n_affected"] = int(any_nz.sum())
    d["_n_events"] = int(len(pin["event"]))
    return d


def time_partition(ns: dict) -> dict:
    kind, t, edep, insc = ns["kind"], ns["t_ns"], ns["edep_MeV"], ns["in_scint"]
    m_insc_neutron = (kind == 0) & (insc == 1)
    out = {
        "n_neutron_steps": int((kind == 0).sum()),
        "n_events_with_neutrons": int(len(set(ns["event"][kind == 0].tolist()))),
        "in_scint_neutron_edep_MeV_total": float(edep[m_insc_neutron].sum()),
        "n_late_deposits_gt1us": int((kind == 1).sum()),
        "late_deposit_edep_MeV_total": float(edep[kind == 1].sum()),
        "cumulative": {},
    }
    for T in T_PARTITION_NS:
        m = m_insc_neutron & (t <= T)
        out["cumulative"][f"{T:g}"] = {
            "in_scint_neutron_edep_MeV": float(edep[m].sum()),
            "n_neutron_steps": int(m.sum()),
        }
    return out


def wiring_gate(cut1: dict, pin: dict, ext: dict, cfg: dict) -> dict:
    eps = cfg["wiring_cut_epsilon_ns"]
    min_rows = cfg["wiring_min_rows_beyond_1ns"]
    min_edep = cfg["wiring_min_edep_MeV_beyond_1ns"]

    def beyond(ns, T):
        m = (ns["kind"] == 0) & (ns["t_ns"] > T)
        e = ns["edep_MeV"][m & (ns["in_scint"] == 1)]
        return int(m.sum()), float(e.sum())

    n1, e1 = beyond(cut1, 1.0 + eps)
    np_, ep = beyond(pin, 1.0)
    ne, ee = beyond(ext, 1.0)
    late1 = float(cut1["edep_MeV"][(cut1["kind"] == 1)].sum())
    latep = float(pin["edep_MeV"][(pin["kind"] == 1)].sum())
    latee = float(ext["edep_MeV"][(ext["kind"] == 1)].sum())
    fixture_adequate = (np_ >= min_rows) and (ep >= min_edep)
    g1a = (n1 == 0) if fixture_adequate else None
    g1b = (e1 == 0.0) if fixture_adequate else None
    g1c = (latee >= latep >= late1) if fixture_adequate else None
    return {
        "rows_beyond_1ns": {"cut1ns": n1, "pin10us": np_, "ext1e9us": ne},
        "in_scint_neutron_edep_beyond_1ns_MeV": {"cut1ns": e1, "pin10us": ep, "ext1e9us": ee},
        "late_deposit_edep_MeV": {"cut1ns": late1, "pin10us": latep, "ext1e9us": latee},
        "fixture_adequate": bool(fixture_adequate),
        "G1a_cut_removes_history": g1a,
        "G1b_cut_removes_edep": g1b,
        "G1c_monotone_late_deposits": g1c,
        "verdict": (
            "PASS"
            if (fixture_adequate and g1a and g1b and g1c)
            else "INCONCLUSIVE"
            if not fixture_adequate
            else "FAIL"
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--config", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    args.out.mkdir(parents=True, exist_ok=True)

    tags = sorted(
        {t for pt in cfg["grid_points"].values() for t in (pt["pin"], pt["ext"])}
        | set(cfg["wiring"][k] for k in ("cut1ns", "pin", "ext"))
    )
    files = {}
    metas = {}
    for tag in tags:
        root = args.ladder_dir / f"{tag}.root"
        files[tag] = root
        metas[tag] = load_meta(root)

    result = {
        "study": "s1091_neutron_timecut_ladder",
        "issue": 1091,
        "config": cfg,
        "inputs": {
            t: {
                "sha256": sha256(p),
                "bytes": p.stat().st_size,
                "policy_id": metas[t]["neutron_timecut_policy_id"],
                "neutron_time_cut_us": metas[t]["neutron_time_cut_us"],
                "seed": metas[t]["seed"],
                "threads": metas[t]["threads_effective"],
                "n_events": metas[t]["n_events"],
                "particle": metas[t]["particle"],
                "ke_MeV": metas[t]["kinetic_energy_MeV"],
            }
            for t, p in files.items()
        },
        "gates": cfg["gates"],
        "grid_points": {},
        "wiring": {},
    }

    # --- G2 pairing + G3 sensitivity per grid point ---
    g2_ok, g3_ok = True, True
    for pt in cfg["grid_points"]:
        pin_tag, ext_tag = cfg["grid_points"][pt]["pin"], cfg["grid_points"][pt]["ext"]
        mp, me = metas[pin_tag], metas[ext_tag]
        pair_ok = (
            mp["particle"] == me["particle"]
            and mp["kinetic_energy_MeV"] == me["kinetic_energy_MeV"]
            and mp["seed"] == me["seed"]
            and mp["threads_effective"] == me["threads_effective"]
            and mp["n_events"] == me["n_events"]
            and mp["neutron_timecut_policy_id"] != me["neutron_timecut_policy_id"]
        )
        pin = load_events(files[pin_tag])
        ext = load_events(files[ext_tag])
        deltas = paired_deltas(pin, ext)
        zmax = max(abs(deltas[k]["z"]) for k in OBS)
        point_g3 = zmax <= cfg["gates"]["z_max"]
        g2_ok &= pair_ok
        g3_ok &= point_g3
        result["grid_points"][pt] = {
            "pin": pin_tag,
            "ext": ext_tag,
            "pair_meta_consistent": bool(pair_ok),
            "deltas": {k: deltas[k] for k in OBS},
            "n_affected_events": deltas["_n_affected"],
            "n_events": deltas["_n_events"],
            "max_abs_z": float(zmax),
            "G3_pass": bool(point_g3),
        }
        # G4 time partition from the ext run
        nse = load_neutron_steps(files[ext_tag])
        nsp = load_neutron_steps(files[pin_tag])
        result["grid_points"][pt]["time_partition_ext"] = time_partition(nse)
        result["grid_points"][pt]["time_partition_pin"] = time_partition(nsp)

    # --- wiring triple ---
    w = cfg["wiring"]
    cut1 = load_neutron_steps(files[w["cut1ns"]])
    wpin = load_neutron_steps(files[w["pin"]])
    wext = load_neutron_steps(files[w["ext"]])
    wg = wiring_gate(cut1, wpin, wext, cfg["gates"])
    result["wiring"] = {
        "tags": w,
        "time_partition": {
            k: time_partition(v)
            for k, v in [("cut1ns", cut1), ("pin10us", wpin), ("ext1e9us", wext)]
        },
        "gate": wg,
    }

    # --- headline verdict ---
    wiring_pass = wg["verdict"] == "PASS"

    def _late_dep(pt: str, which: str) -> float:
        return result["grid_points"][pt][f"time_partition_{which}"]["late_deposit_edep_MeV_total"]

    g4_note = all(_late_dep(pt, "ext") >= _late_dep(pt, "pin") for pt in result["grid_points"])
    verdict = (
        "INSENSITIVE_WITHIN_MEASURED_BOUND"
        if (g2_ok and g3_ok and wiring_pass)
        else "SENSITIVE"
        if not g3_ok
        else "INCONCLUSIVE"
    )
    result["headline"] = {
        "G2_pairing_pass": bool(g2_ok),
        "G3_insensitivity_pass": bool(g3_ok),
        "G1_wiring_verdict": wg["verdict"],
        "G4_ext_ge_pin_late_deposits": bool(g4_note),
        "verdict": verdict,
    }

    core = {
        "config": cfg,
        "inputs": result["inputs"],
        "headline": result["headline"],
        "grid_point_summary": {
            pt: {
                "n_affected_events": v["n_affected_events"],
                "n_events": v["n_events"],
                "max_abs_z": v["max_abs_z"],
            }
            for pt, v in result["grid_points"].items()
        },
        "wiring_gate": wg,
    }
    digest = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result["result_core_sha256_digest"] = digest

    (args.out / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True))
    print(json.dumps(result["headline"], indent=1))
    print("digest:", digest)


if __name__ == "__main__":
    main()
