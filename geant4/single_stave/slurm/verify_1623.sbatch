#!/usr/bin/env bash
#SBATCH --job-name=ccb1623_verify
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
#
# Every simulation command is wrapped in `timeout` so that a single pathological
# optical event (issue #1623 / #1083 boundary thrashing) cannot take out the
# checks behind it -- notably the default-path equivalence check, which is what
# protects the recorded 1T/48T same-seed branch equality.
set -uo pipefail
if [ -z "${MODULESHOME:-}" ]; then source /etc/profile.d/modules.sh 2>/dev/null || true; fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2
NEW=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave
BASE=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623-base/geant4/single_stave
PY=/projects/hep/fs10/shared/nnbar/billy/ccb_venv/bin/python
V=$NEW/verify_1623
rm -rf "$V"; mkdir -p "$V"
C="--physics-list QGSP_BIC --neutron-timecut-policy-id pin_qgsp_bic_default_10us --mode optical --strict-optical"
AREA="--hit-x-range -22:22 --hit-y-range -2.2:2.2 --theta-spread 10"
GUARD="--optical-max-time-ns 1000 --optical-max-steps 200000"

echo "===== 1. pristine baseline build ====="
cmake -S "$BASE" -B "$BASE/build" -DCMAKE_BUILD_TYPE=Release -DCCB_ENABLE_VIS=OFF >/dev/null
cmake --build "$BASE/build" -j 32 >/dev/null && echo "BASELINE_BUILD_OK"

echo "===== 2. default-path equivalence (no #1623 flags, same seed) ====="
for TAG in base new; do
  if [ "$TAG" = base ]; then EXE=$BASE/build/ccb_stave_sim; OPT=$BASE/build/optical
  else EXE=$NEW/build/ccb_stave_sim; OPT=$NEW/build/optical; fi
  timeout 1800 $EXE $C --particle proton --energy 20 --nevents 200 --seed 1 --threads 1 \
    --hit-x 0 --hit-y 0 --optical-dir "$OPT" --output "$V/eq_$TAG.root" > "$V/eq_$TAG.log" 2>&1
  echo "  $TAG exit=$?"
done

echo "===== 3. envelope preflight rejects an out-of-stave window ====="
timeout 300 $NEW/build/ccb_stave_sim $C --particle proton --energy 20 --nevents 1 --seed 1 --threads 1 \
  --hit-y-range -4.0:4.0 --optical-dir "$NEW/build/optical" --output "$V/bad.root" > "$V/bad.log" 2>&1
echo "  exit=$? (expect 4)"; grep -E "ENVELOPE|^fatal" "$V/bad.log" | head -3

echo "===== 4. thread independence of the sampled phase space ====="
for T in 1 16; do
  timeout 1800 $NEW/build/ccb_stave_sim $C --particle proton --energy 20 --nevents 300 --seed 7 \
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
$PY "$NEW/slurm/verify_checks_1623.py" "$V" 2>&1 | tail -60
CHECKS=$?

echo "===== 7. ctest on the modified tree ====="
timeout 3600 ctest --test-dir "$NEW/build" --output-on-failure > "$V/ctest.log" 2>&1
echo "  ctest exit=$?"; tail -30 "$V/ctest.log"
echo "VERIFY_DONE checks_exit=$CHECKS"
