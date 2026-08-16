#!/usr/bin/env python3
"""#1088 WLS fluorescence multiplicity known-answer test.

Runs ccb_stave_sim four times on the SAME seed (argv-only config, no macro),
one run per multiplicity mode, and asserts the known-answer observable
    E[n_wls_generated / n_wls_absorbed] = 1 | mu | q
per mode: every WLS creation is caused by exactly one OpWLS absorption,
independent of re-absorption chains. Additionally discriminates default-one
from Poisson(1) — the grid-provenance defect #1088 closes — via the per-event
diff dispersion ratio: d_i = gen_i - abs_i carries transport noise only in
deterministic mode, plus ~sqrt(A) Poisson sampling noise at mu=1
(A ~ 2.7e4 absorptions/event; measured dispersion ratio 3.4, std 100 vs 30).

argv-only configuration (NO --macro): with a macro, main.cc executes the
macro's own /run/beamOn and --nevents is ignored ("Prefer argv", per the
proton_point.mac header). These argv values reproduce proton_point.mac:
proton, 100 MeV, normal incidence at (0,0), Birks kB 0.126 mm/MeV.

Poisson mu=3 CHAINS: every re-absorbed photon re-emits Poisson(3) again, so
photon load grows super-linearly (measured ~150 s/event vs ~3.5 s/event
default, ~40x) and late-generation photons are still in flight at event end
(ratio 2.67, not 3.0). That mode runs fewer events and executes last.
Exits 77 (SKIP) when uproot is absent.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import uproot
except ImportError:
    print("SKIP: uproot not available (exit 77)")
    sys.exit(77)

import numpy as np


def run_mode(exe: Path, optical_dir: Path, out_root: Path,
             events: int, seed: int, threads: int, extra: list) -> tuple:
    cmd = [
        str(exe),
        "--physics-list", "QGSP_BIC",
        "--neutron-timecut-policy-id", "pin_qgsp_bic_default_10us",
        "--particle", "proton",
        "--energy", "100",
        "--birks-kB", "0.126",
        "--hit-x", "0",
        "--hit-y", "0",
        "--theta", "0",
        "--threads", str(threads),
        "--optical-dir", str(optical_dir),
        "--output", str(out_root),
        "--seed", str(seed),
        "--nevents", str(events),
    ] + [str(x) for x in extra]
    print(f"RUN: {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"ccb_stave_sim exited {proc.returncode}")
    with uproot.open(out_root) as f:
        tree = f["events"]
        gen = tree["n_wls_generated"].array(library="np")
        absorbed = tree["n_wls_absorbed"].array(library="np")
    return gen.astype(float), absorbed.astype(float)


def check(name, gen, absorbed, lo, hi) -> bool:
    total_gen, total_abs = gen.sum(), absorbed.sum()
    if total_abs <= 0:
        print(f"FAIL {name}: zero WLS absorptions counted")
        return False
    ratio = total_gen / total_abs
    ok = lo <= ratio <= hi
    print(f"{'PASS' if ok else 'FAIL'} {name}: "
          f"gen={int(total_gen)} abs={int(total_abs)} ratio={ratio:.4f} "
          f"[{lo}, {hi}]")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", required=True, type=Path, help="ccb_stave_sim executable")
    ap.add_argument("--optical-dir", required=True, type=Path)
    ap.add_argument("--events", type=int, default=10)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    # All four runs share one seed and differ ONLY in the multiplicity mode.
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        # 1) default mode: exactly-one secondary per absorption -> ratio 1.
        g_def, a_def = run_mode(args.exe, args.optical_dir,
                                td / "m_default.root", args.events, 1,
                                args.threads, [])
        ok &= check("default_one", g_def, a_def, 0.97, 1.03)

        # 2) Poisson mu=1: SAME mean as default but per-event diffs fluctuate
        #    at the ~sqrt(A) level. Paired with (1), this is the #1088
        #    discriminator: per-event exact gen==abs never holds even in
        #    deterministic mode (stable ~-200/event boundary offset of WLS
        #    photons in flight or boundary-terminated at event end), so the
        #    discriminator is the DISPERSION RATIO of d = gen - abs between
        #    the two modes: ~1 (transport noise only) vs ~sqrt(1 + A/s^2).
        g_p1, a_p1 = run_mode(args.exe, args.optical_dir,
                              td / "m_poisson1.root", args.events, 1,
                              args.threads,
                              ["--wls-fluorescence-model", "geant4_poisson_mean",
                               "--wls-mean-number-photons", "1.0"])
        ok &= check("poisson_mu1", g_p1, a_p1, 0.80, 1.20)
        std_def = float(np.std(g_def - a_def))
        std_p1 = float(np.std(g_p1 - a_p1))
        disp = std_p1 / max(std_def, 1e-9)
        det = disp >= 2.0
        print(f"{'PASS' if det else 'FAIL'} discriminator: "
              f"std(d)_poisson1={std_p1:.1f} std(d)_default={std_def:.1f} "
              f"dispersion ratio={disp:.2f} (need >= 2.0)")
        ok &= det

        # 3) Bernoulli q=0.70: mean ratio ~q (thinned: sub-unit photon load).
        g, a = run_mode(args.exe, args.optical_dir,
                        td / "m_bernoulli.root", args.events, 1, args.threads,
                        ["--wls-fluorescence-model", "bernoulli_thinned"])
        ok &= check("bernoulli_q0.70", g, a, 0.58, 0.82)

        # 4) Poisson mu=3: knob evidence, ratio ~3. Runs last with fewer
        #    events: ~3.5x photon load makes it the slowest mode.
        g, a = run_mode(args.exe, args.optical_dir,
                        td / "m_poisson3.root", min(args.events, 4), 1,
                        args.threads,
                        ["--wls-fluorescence-model", "geant4_poisson_mean",
                         "--wls-mean-number-photons", "3.0"])
        ok &= check("poisson_mu3", g, a, 2.60, 3.40)

    print("WLS_MULTIPLICITY_PASS" if ok else "WLS_MULTIPLICITY_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
