#!/usr/bin/env python3
"""Cross-checks for the issue #1623 generator/observable changes."""
import sys, pathlib
import numpy as np
import uproot

V = pathlib.Path(sys.argv[1])
fails: list[str] = []


def tree(p: pathlib.Path):
    if not p.exists():
        fails.append(f"missing output {p.name} (upstream run failed or timed out)")
        return None
    return uproot.open(str(p))["events"]


# --- 1. default-path equivalence -------------------------------------------
base, new = tree(V / "eq_base.root"), tree(V / "eq_new.root")
if base is not None and new is not None:
    bk, nk = set(base.keys()), set(new.keys())
    print(f"[equivalence] baseline columns={len(bk)} new columns={len(nk)}")
    print(f"[equivalence] added   = {sorted(nk - bk)}")
    print(f"[equivalence] removed = {sorted(bk - nk)}")
    if bk - nk:
        fails.append(f"columns removed from the events tree: {sorted(bk - nk)}")
    db, dn = base.arrays(library="np"), new.arrays(library="np")
    print(f"[equivalence] rows baseline={len(db['event'])} new={len(dn['event'])}")
    if len(db["event"]) != len(dn["event"]):
        fails.append("default-path row count changed")
    else:
        diff = [k for k in sorted(bk) if not np.array_equal(db[k], dn[k])]
        print(f"[equivalence] shared columns compared={len(bk)} differing={len(diff)}")
        for k in diff:
            print(f"[equivalence]   DIFFERS: {k}")
        if diff:
            fails.append(f"{len(diff)}/{len(bk)} shared columns differ on the default path")

# --- 2. thread independence of the sampled phase space ----------------------
t1, t16 = tree(V / "mt_t1.root"), tree(V / "mt_t16.root")
if t1 is not None and t16 is not None:
    cols = ["event", "gen_x_cm", "gen_y_cm", "dir_ux", "dir_uy", "dir_uz"]
    a1, a16 = t1.arrays(cols, library="np"), t16.arrays(cols, library="np")
    o1, o16 = np.argsort(a1["event"]), np.argsort(a16["event"])
    print(f"[threads] rows 1T={len(o1)} 16T={len(o16)}")
    if len(o1) != len(o16):
        fails.append("thread-independence: row counts differ")
    else:
        for k in cols[1:]:
            if np.array_equal(a1[k][o1], a16[k][o16]):
                print(f"[threads] {k}: identical event-by-event")
            else:
                fails.append(f"thread-independence: {k} differs between 1 and 16 threads")

    # --- 3. the sampled phase space is actually populated and in range ------
    d = t16.arrays(["gen_x_cm", "gen_y_cm", "dir_uz", "entry_x_cm", "entry_y_cm"],
                   library="np")
    th = np.degrees(np.arccos(np.clip(d["dir_uz"], -1, 1)))
    print(f"[spread] gen_x [{d['gen_x_cm'].min():7.2f},{d['gen_x_cm'].max():7.2f}] cm "
          f"(window -22..22)")
    print(f"[spread] gen_y [{d['gen_y_cm'].min():7.2f},{d['gen_y_cm'].max():7.2f}] cm "
          f"(window -2.2..2.2)")
    print(f"[spread] theta [{th.min():7.2f},{th.max():7.2f}] deg (cone half-angle 10)")
    if d["gen_x_cm"].min() < -22.001 or d["gen_x_cm"].max() > 22.001:
        fails.append("sampled x left the requested window")
    if d["gen_y_cm"].min() < -2.2001 or d["gen_y_cm"].max() > 2.2001:
        fails.append("sampled y left the requested window")
    if np.ptp(d["gen_x_cm"]) < 40.0:
        fails.append(f"x spread only {np.ptp(d['gen_x_cm']):.1f} cm of a 44 cm window")
    if np.ptp(d["gen_y_cm"]) < 4.0:
        fails.append(f"y spread only {np.ptp(d['gen_y_cm']):.2f} cm of a 4.4 cm window")
    if th.max() > 10.001:
        fails.append(f"cone half-angle exceeded: max theta={th.max():.4f} deg")
    if th.max() < 8.0:
        fails.append(f"cone barely sampled: max theta={th.max():.4f} deg")

# --- 4. species smoke -------------------------------------------------------
for name, pdg in [("mu-", 13), ("mu+", -13), ("pi+", 211), ("pi-", -211)]:
    t = tree(V / f"sp_{name.replace('+', 'plus')}.root")
    if t is None:
        continue
    a = t.arrays(["primary_pdg", "edep_scint_raw_MeV", "edep_scint_MeV",
                  "n_scint_generated", "detected_readout", "primary_stopped"],
                 library="np")
    got = sorted({int(x) for x in a["primary_pdg"] if x != 0})
    print(f"[species] {name:4s} rows={len(a['primary_pdg']):4d} pdg={got} "
          f"Edep={a['edep_scint_raw_MeV'].mean():6.3f} MeV "
          f"Evis={a['edep_scint_MeV'].mean():6.3f} MeV "
          f"Nscint={a['n_scint_generated'].mean():8.0f} "
          f"Npe={a['detected_readout'].mean():7.1f} "
          f"stopped={int(a['primary_stopped'].sum())}/{len(a['primary_stopped'])}")
    if pdg not in got:
        fails.append(f"species {name}: expected primary pdg {pdg}, got {got}")
    if a["detected_readout"].mean() <= 0:
        fails.append(f"species {name}: zero detected photoelectrons")
    if a["edep_scint_MeV"].mean() > a["edep_scint_raw_MeV"].mean():
        fails.append(f"species {name}: Birks-visible energy exceeds the raw deposit")

print()
if fails:
    print("VERIFY_CHECKS_FAIL")
    for f in fails:
        print("  FAIL:", f)
    sys.exit(1)
print("VERIFY_CHECKS_PASS")
