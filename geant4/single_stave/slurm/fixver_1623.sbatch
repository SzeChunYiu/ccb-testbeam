#!/usr/bin/env bash
#SBATCH --job-name=ccb1623_fixver
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --time=05:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
set -uo pipefail
if [ -z "${MODULESHOME:-}" ]; then source /etc/profile.d/modules.sh 2>/dev/null || true; fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2
NEW=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave
BASE=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623-base/geant4/single_stave
V=$NEW/fixver; rm -rf "$V"; mkdir -p "$V"
C="--physics-list QGSP_BIC --neutron-timecut-policy-id pin_qgsp_bic_default_10us --mode optical --strict-optical --no-photon-ntuple --optical-dir $NEW/build/optical"
GUARD="--optical-max-time-ns 1000 --optical-max-steps 200000"

echo "===== 1. ctest attribution: pristine baseline vs fixed tree ====="
cmake -S "$BASE" -B "$BASE/build" -DCMAKE_BUILD_TYPE=Release -DCCB_ENABLE_VIS=OFF >/dev/null
cmake --build "$BASE/build" -j 32 >/dev/null && echo "  BASELINE_BUILD_OK"
timeout 7200 ctest --test-dir "$BASE/build" > "$V/ctest_base.log" 2>&1; echo "  baseline exit=$?"
timeout 7200 ctest --test-dir "$NEW/build"  > "$V/ctest_new.log"  2>&1; echo "  fixed    exit=$?"
# Authoritative failing-test list from CTest's own trailer block. A regex over
# the per-test progress lines only knows "***Failed" and silently misses
# "Subprocess aborted" (signal death) and "***Timeout" -- which produced a false
# "NEWLY broken: <none>" while a test was dying on SIGABRT.
for t in base new; do
  "$NEW/slurm/ctest_fail_list.sh" "$V/ctest_$t.log" > "$V/fail_$t.txt" || {
    echo "  FATAL: could not parse ctest_$t.log"; exit 3; }
done
echo "  baseline failures: $(wc -l < "$V/fail_base.txt")"; sed 's/^/    /' "$V/fail_base.txt"
echo "  fixed    failures: $(wc -l < "$V/fail_new.txt")";  sed 's/^/    /' "$V/fail_new.txt"
echo "  FIXED by this change:   $(comm -23 "$V/fail_base.txt" "$V/fail_new.txt" | tr '\n' ' ')"
echo "  NEWLY broken:           $(comm -13 "$V/fail_base.txt" "$V/fail_new.txt" | tr '\n' ' ')"
grep -E "tests passed|tests failed" "$V/ctest_new.log" | tail -2

echo
echo "===== 2. strict-optical tests must still fail for the RIGHT reason ====="
# They assert a non-zero exit. Before the fix they got it from the missing
# --physics-list, so they would have passed even with optical validation gone.
for t in ccb_stave_strict_optical_missing_table ccb_stave_strict_optical_bad_units; do
  timeout 600 ctest --test-dir "$NEW/build" -R "^${t}$" --output-on-failure > "$V/so_$t.log" 2>&1
  rc=$?
  echo "  $t ctest_rc=$rc (0 = the test passes, i.e. the sim correctly refused)"
  grep -iE "optical|physics-list|fatal|abort" "$V/so_$t.log" | grep -v "^ *[0-9]*:" | head -3
done

echo
echo "===== 3. ADC saturation is now reported, not silent ====="
for T in 1 32; do
 for E in 12 18 46; do
  timeout 1800 $NEW/build/ccb_stave_sim $C $GUARD --particle proton --energy $E \
    --nevents 40 --seed 5 --threads $T --hit-x 0 --hit-y 0 \
    --output "$V/adc_p${E}_t$T.root" > "$V/adc_p${E}_t$T.log" 2>&1
  echo "  proton ${E} MeV threads=$T: $(grep -m1 CCB_ADC_SATURATION "$V/adc_p${E}_t$T.log")"
 done
done

echo
echo "===== 4. --adc-lsb-pe widens the range and clears the clipping ====="
for L in 0.01 0.20; do
  timeout 1800 $NEW/build/ccb_stave_sim $C $GUARD --particle deuteron --energy 44 \
    --nevents 40 --seed 5 --threads 32 --hit-x 0 --hit-y 0 --adc-lsb-pe $L \
    --output "$V/lsb_d44_$L.root" > "$V/lsb_d44_$L.log" 2>&1
  timeout 1800 $NEW/build/ccb_stave_sim $C $GUARD --particle proton --energy 160 \
    --nevents 40 --seed 5 --threads 32 --hit-x 0 --hit-y 0 --adc-lsb-pe $L \
    --output "$V/lsb_p160_$L.root" > "$V/lsb_p160_$L.log" 2>&1
  echo "  lsb=$L  d44:  $(grep -m1 -o 'saturated_fraction=[0-9.e+-]*' "$V/lsb_d44_$L.log")  headroom=$(grep -m1 -o 'headroom_pe=[0-9.e+-]*' "$V/lsb_d44_$L.log")"
  echo "  lsb=$L  p160: $(grep -m1 -o 'saturated_fraction=[0-9.e+-]*' "$V/lsb_p160_$L.log")"
done

echo
echo "===== 4b. --sipm-n-cells must fail CLEANLY, not on SIGABRT ====="
$NEW/build/ccb_stave_sim $C --particle proton --energy 100 --nevents 1 --seed 1 \
  --sipm-n-cells 1800 --output "$V/ncells.root" > "$V/ncells.log" 2>&1
rc=$?
echo "  exit=$rc (expect 2; 134 = the old SIGABRT)"
grep -m1 "sipm-n-cells" "$V/ncells.log"

echo
echo "===== 5. default-path equivalence vs the pristine parent build ====="
for TAG in base new; do
  if [ "$TAG" = base ]; then EXE=$BASE/build/ccb_stave_sim; OPT=$BASE/build/optical
  else EXE=$NEW/build/ccb_stave_sim; OPT=$NEW/build/optical; fi
  timeout 5400 $EXE --physics-list QGSP_BIC \
    --neutron-timecut-policy-id pin_qgsp_bic_default_10us --mode optical \
    --strict-optical --particle proton --energy 20 --nevents 60 --seed 1 --threads 1 \
    --hit-x 0 --hit-y 0 --optical-dir "$OPT" --output "$V/eq_$TAG.root" > "$V/eq_$TAG.log" 2>&1
  echo "  $TAG exit=$?"
done
( module purge >/dev/null 2>&1
  module load GCCcore/13.2.0 Python/3.11.5 >/dev/null 2>&1
  /projects/hep/fs10/shared/nnbar/billy/ccb1623_venv/bin/python - "$V" <<'PY'
import sys, pathlib, numpy as np, uproot
V = pathlib.Path(sys.argv[1])
b = uproot.open(str(V/"eq_base.root"))["events"]
n = uproot.open(str(V/"eq_new.root"))["events"]
bk, nk = set(b.keys()), set(n.keys())
print("  columns baseline=%d new=%d  added=%s  removed=%s"
      % (len(bk), len(nk), sorted(nk-bk), sorted(bk-nk)))
db, dn = b.arrays(library="np"), n.arrays(library="np")
diff = [k for k in sorted(bk) if not np.array_equal(db[k], dn[k])]
print("  rows %d vs %d   shared compared=%d   differing=%d %s"
      % (len(db["event"]), len(dn["event"]), len(bk), len(diff), diff))
print("  EQUIVALENCE_OK" if not diff and not (bk-nk) else "  EQUIVALENCE_FAIL")
PY
)
echo FIXVER_DONE
