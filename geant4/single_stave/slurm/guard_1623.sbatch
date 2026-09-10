#!/usr/bin/env bash
#SBATCH --job-name=ccb1623_guard
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
set -uo pipefail
if [ -z "${MODULESHOME:-}" ]; then source /etc/profile.d/modules.sh 2>/dev/null || true; fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2
N=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave
PY=/projects/hep/fs10/shared/nnbar/billy/ccb_venv/bin/python
G=$N/guard_1623; rm -rf $G; mkdir -p $G
C="--physics-list QGSP_BIC --neutron-timecut-policy-id pin_qgsp_bic_default_10us --mode optical --strict-optical --optical-dir $N/build/optical"
AREA="--hit-x-range -22:22 --hit-y-range -2.2:2.2 --theta-spread 10"

echo "=== A. arrival-time census WITH the photon ntuple (guard OFF) ==="
# Guarded by --optical-max-steps only, so the census itself cannot hang; the
# time distribution below is what justifies the production time cut.
for E in 20 60; do
  t0=$SECONDS
  timeout 1800 $N/build/ccb_stave_sim $C --particle proton --energy $E --nevents 150 \
    --seed 91 --threads 32 $AREA --optical-max-steps 200000 \
    --output "$G/census_p$E.root" > "$G/census_p$E.log" 2>&1
  echo "census p$E rc=$? wall=$((SECONDS-t0))s"
done
$PY - <<'PYEOF'
import glob, numpy as np, uproot
for f in sorted(glob.glob("/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave/guard_1623/census_p*.root")):
    try:
        ph = uproot.open(f)["photons"].arrays(["time_ns","detected","sensor"], library="np")
    except Exception as e:
        print(f, "NO photons tree:", e); continue
    t = ph["time_ns"]; det = ph["detected"].astype(bool)
    ev = uproot.open(f)["events"].arrays(["n_optical_killed_steps","arrival_readout","n_scint_generated"], library="np")
    print(f"\n{f.split('/')[-1]}: arrivals={t.size} detected={int(det.sum())}")
    for q in (50,84,95,99,99.9,100):
        print(f"   arrival time p{q}: {np.percentile(t,q):9.2f} ns")
    for cut in (100,250,500,1000,5000):
        print(f"   fraction of ALL arrivals beyond {cut:5d} ns: {(t>cut).mean():.3e}"
              f"   of DETECTED: {(t[det]>cut).mean():.3e}")
    print(f"   step-guard kills total={int(ev['n_optical_killed_steps'].sum())} "
          f"events_with_kill={int((ev['n_optical_killed_steps']>0).sum())}/{ev['n_optical_killed_steps'].size} "
          f"generated_scint={int(ev['n_scint_generated'].sum())}")
PYEOF

echo
echo "=== B. timing with the production guard ON ==="
run() {
  local p=$1 e=$2 nev=$3 lab=$4; shift 4
  local t0=$SECONDS
  timeout 1800 $N/build/ccb_stave_sim $C --particle "$p" --energy "$e" --nevents "$nev" \
    --seed 42 --threads 32 $AREA --no-photon-ntuple "$@" \
    --output "$G/$lab.root" > "$G/$lab.log" 2>&1
  local rc=$? dt=$((SECONDS-t0))
  echo "TIMING $lab part=$p E=$e nev=$nev rc=$rc wall=${dt}s per_event=$(awk -v d=$dt -v n=$nev 'BEGIN{printf "%.3f",d/n}')s size=$(stat -c%s "$G/$lab.root" 2>/dev/null||echo 0)"
}
GUARD="--optical-max-time-ns 1000 --optical-max-steps 200000"
run proton   20  300 g_p20   $GUARD
run proton   60  300 g_p60   $GUARD
run proton  150  300 g_p150  $GUARD
run deuteron 45  300 g_d45   $GUARD
run deuteron 200 300 g_d200  $GUARD
run mu-     300  300 g_mu300 $GUARD
run mu-      20  300 g_mu20  $GUARD
run pi+     200  300 g_pi200 $GUARD
run pi-      30  300 g_pim30 $GUARD

echo
echo "=== C. guard impact on the recorded observables (60 MeV proton, same seed) ==="
run proton 60 300 g_off
$PY - <<'PYEOF'
import numpy as np, uproot
b="/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave/guard_1623/"
cols=["edep_scint_raw_MeV","n_scint_generated","arrival_readout","detected_readout","adc_readout",
      "n_optical_killed_time","n_optical_killed_steps"]
try:
    on=uproot.open(b+"g_p60.root")["events"].arrays(cols,library="np")
    off=uproot.open(b+"g_off.root")["events"].arrays(cols,library="np")
except Exception as e:
    print("compare failed:",e); raise SystemExit(0)
print(f"rows on={on['edep_scint_raw_MeV'].size} off={off['edep_scint_raw_MeV'].size}")
for c in cols[:5]:
    a,bb=on[c].astype(float),off[c].astype(float)
    n=min(a.size,bb.size); a,bb=a[:n],bb[:n]
    d=np.abs(a-bb); rel=d.sum()/max(bb.sum(),1e-9)
    print(f"   {c:22s} mean_on={a.mean():12.4f} mean_off={bb.mean():12.4f} "
          f"identical={int((d==0).sum())}/{n} sum_rel_diff={rel:.3e}")
print(f"   kills(time)={int(on['n_optical_killed_time'].sum())} kills(steps)={int(on['n_optical_killed_steps'].sum())}")
PYEOF
echo GUARD_DONE
