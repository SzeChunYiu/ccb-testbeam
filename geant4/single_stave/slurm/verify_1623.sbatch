#!/usr/bin/env bash
#SBATCH --job-name=ccb1623_verify
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
#
# Verification for the issue #1623 producer changes.
#
# Every simulation command is wrapped in `timeout` so that a single pathological
# optical event (#1623 / #1083 boundary thrashing) cannot take out the checks
# behind it -- notably the default-path equivalence check, which is what protects
# the recorded 1T/48T same-seed branch equality.
#
# CTest is run against BOTH the pristine parent-commit build and the modified
# tree, and the two failure sets are diffed. Several ccb_stave_* tests fail on
# the parent commit already (their CTest definitions predate the fail-closed
# --physics-list / --neutron-timecut-policy-id requirements of #1006 / #1091);
# only a test that fails HERE and passes THERE is attributable to this branch.
set -uo pipefail
if [ -z "${MODULESHOME:-}" ]; then source /etc/profile.d/modules.sh 2>/dev/null || true; fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2
NEW=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave
BASE=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623-base/geant4/single_stave
V=$NEW/verify_1623
rm -rf "$V"; mkdir -p "$V"
C="--physics-list QGSP_BIC --neutron-timecut-policy-id pin_qgsp_bic_default_10us --mode optical --strict-optical"
AREA="--hit-x-range -22:22 --hit-y-range -2.2:2.2 --theta-spread 10"
GUARD="--optical-max-time-ns 1000 --optical-max-steps 200000"

# The analysis venv is built against Python/3.11.5 (GCCcore/13.2.0), which does
# not coexist with the Geant4 GCC/12.3.0 stack; run python in its own subshell.
pyrun() {
  ( module purge >/dev/null 2>&1
    module load GCCcore/13.2.0 Python/3.11.5 >/dev/null 2>&1
    /projects/hep/fs10/shared/nnbar/billy/ccb1623_venv/bin/python "$@" )
}

echo "===== 1. pristine baseline build ====="
cmake -S "$BASE" -B "$BASE/build" -DCMAKE_BUILD_TYPE=Release -DCCB_ENABLE_VIS=OFF >/dev/null
cmake --build "$BASE/build" -j 32 >/dev/null && echo "BASELINE_BUILD_OK"

echo "===== 2. default-path equivalence (no #1623 flags, same seed) ====="
for TAG in base new; do
  if [ "$TAG" = base ]; then EXE=$BASE/build/ccb_stave_sim; OPT=$BASE/build/optical
  else EXE=$NEW/build/ccb_stave_sim; OPT=$NEW/build/optical; fi
  timeout 5400 $EXE $C --particle proton --energy 20 --nevents 60 --seed 1 --threads 1 \
    --hit-x 0 --hit-y 0 --optical-dir "$OPT" --output "$V/eq_$TAG.root" > "$V/eq_$TAG.log" 2>&1
  echo "  $TAG exit=$?"
done

echo "===== 3. envelope preflight rejects an out-of-stave window ====="
timeout 300 $NEW/build/ccb_stave_sim $C --particle proton --energy 20 --nevents 1 --seed 1 --threads 1 \
  --hit-y-range -4.0:4.0 --optical-dir "$NEW/build/optical" --output "$V/bad.root" > "$V/bad.log" 2>&1
echo "  exit=$? (expect 4)"; grep -E "ENVELOPE|^fatal" "$V/bad.log" | head -3

echo "===== 4. thread independence of the sampled phase space ====="
# 1 thread is ~30x slower per wall-clock second than 32; keep the sample small
# enough that the single-threaded leg finishes well inside its timeout.
for T in 1 16; do
  timeout 5400 $NEW/build/ccb_stave_sim $C --particle proton --energy 8 --nevents 120 --seed 7 \
    --threads $T $AREA $GUARD --no-photon-ntuple \
    --optical-dir "$NEW/build/optical" --output "$V/mt_t$T.root" > "$V/mt_t$T.log" 2>&1
  echo "  threads=$T exit=$?"
done

echo "===== 5. new species smoke ====="
for P in mu- mu+ pi+ pi-; do
  L=${P//+/plus}
  timeout 1800 $NEW/build/ccb_stave_sim $C --particle "$P" --energy 300 --nevents 100 --seed 3 \
    --threads 32 $AREA $GUARD --no-photon-ntuple \
    --optical-dir "$NEW/build/optical" --output "$V/sp_$L.root" > "$V/sp_$L.log" 2>&1
  echo "  $P exit=$?"
done

echo "===== 6. python cross-checks ====="
pyrun "$NEW/slurm/verify_checks_1623.py" "$V" 2>&1 | tail -60
CHECKS=${PIPESTATUS[0]}

echo "===== 7. ctest: baseline vs modified (attribution) ====="
timeout 5400 ctest --test-dir "$BASE/build" > "$V/ctest_base.log" 2>&1
echo "  baseline ctest exit=$?"
timeout 5400 ctest --test-dir "$NEW/build" > "$V/ctest_new.log" 2>&1
echo "  modified ctest exit=$?"
grep -oE "Test +#[0-9]+: [a-z_0-9]+ \.+\*\*\*Failed" "$V/ctest_base.log" | sed -E "s/.*: ([a-z_0-9]+) .*/\1/" | sort > "$V/fail_base.txt"
grep -oE "Test +#[0-9]+: [a-z_0-9]+ \.+\*\*\*Failed" "$V/ctest_new.log"  | sed -E "s/.*: ([a-z_0-9]+) .*/\1/" | sort > "$V/fail_new.txt"
echo "  baseline failures: $(wc -l < "$V/fail_base.txt")"; sed "s/^/    /" "$V/fail_base.txt"
echo "  modified failures: $(wc -l < "$V/fail_new.txt")"; sed "s/^/    /" "$V/fail_new.txt"
REGRESSED=$(comm -13 "$V/fail_base.txt" "$V/fail_new.txt")
FIXED=$(comm -23 "$V/fail_base.txt" "$V/fail_new.txt")
echo "  NEW failures introduced by this branch: ${REGRESSED:-<none>}"
echo "  failures no longer present:             ${FIXED:-<none>}"
[ -z "$REGRESSED" ] && echo "CTEST_NO_REGRESSION" || echo "CTEST_REGRESSION"
echo "VERIFY_DONE checks_exit=$CHECKS"
