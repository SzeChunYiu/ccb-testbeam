# Latest Handoff

## Session

- **UTC:** 2026-07-23T10:29:57Z
- **Task:** `AUD-G4-006`
- **Initial observed remote main:** `6d1d982e0eb6764cc3cc036aa1df76b8f3fe35c7`
- **Concurrent main incorporated before writes:** `9521eca866a42a02d17a26dffbaaf0f21d6d8eb7`
- **Implementation/evidence head:** `ddae4a4db15a58745dbbb95bb0abcc02bc973b4c`
- **Coordination/archive head before this handoff:** `4dfa7b0d0ba2e7aa03b2c523f2219f3c28f043fd`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Canonical destination:** `main`
- **Acceptance:** COMPLETE for fail-closed PSTAR reference-domain handling; PARTIAL for accepted stopping-power physics closure.

## Start-of-run review

- A direct clone was attempted and failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and direct-to-main writes were used.
- Inspected current history, current-main status, PR #868, the latest mandatory `chatgpt_todo/` files, the PR #890 stopping-power script and regression, and the committed PSTAR reference table.
- PR #868 remains closed and unmerged (`merged=false`, head `7992aa318b6f13b5f4bcbd828ad97996075fed4b`); it was not modified or merged.
- No status checks were attached to the pre-change head, so no GitHub Actions success is claimed.
- Concurrent main advanced from the first observed head to `9521eca866a42a02d17a26dffbaaf0f21d6d8eb7`; all writes followed that current head through GitHub's contents API. No force-push or history rewrite occurred.

## Confirmed defect

`interp_loglog()` silently clamped every lookup below the first PSTAR energy to the first stopping-power value and every lookup above the last energy to the last value.

A simulation point outside the committed reference domain could therefore reuse an unrelated endpoint value and potentially pass the numerical tolerance. For deuterons the relevant lookup is the transformed proton-equivalent energy `E/2`, so the range gate must apply after that transformation.

Synthetic two-point reproduction for a 1--10 MeV reference:

```text
old lookup 0.5 MeV -> reused 1 MeV endpoint
old lookup 20 MeV  -> reused 10 MeV endpoint
```

Endpoint reuse is neither interpolation nor supported extrapolation.

## Validated change

`scripts/single_stave/compare_stopping_power.py` now:

- requires a finite, positive proton-equivalent lookup energy;
- accepts exact reference endpoints;
- performs log-log interpolation only inside the table domain;
- rejects below- and above-range lookups instead of clamping;
- reports particle beam energy and transformed proton-equivalent lookup energy in failures;
- writes lookup energy, reference minimum/maximum energy, and in-range state to output CSV;
- returns CLI status 2 and does not print a numerical PASS when the range gate fails.

Added:

- `tests/test_compare_stopping_power_energy_range.py`;
- `docs/validation/stopping_power_reference_domain_audit.md`;
- `docs/validation/stopping_power_reference_domain_validation.json`;
- `docs/validation/stopping_power_reference_domain.svg`.

## Reproducible validation

The pre-change script was reconstructed exactly. Its local Git blob was:

```text
d9282a5c26b8bc86427356f51dfe7e5ecba769d8
```

This exactly matched the remote pre-change blob.

Commands:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py

python -m pytest \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py -q
```

Result:

```text
7 passed in 1.15s
```

Additional validation:

- no changed Python line exceeded 100 characters;
- JSON evidence parsed successfully;
- SVG parsed successfully as XML;
- remote post-change script blob `0436fb390476697cfc83f88208322a99d7792a1c` matched the validated local script;
- remote new-test blob `12f3ad78f5a261ebd427e5a37b62db7ccab81b10` matched the validated local test.

The local fixture was synthetic and minimal. Full repository pytest, ruff, Geant4, CTest, ROOT, real simulation comparison, and GitHub Actions were not run.

## Visual and machine-readable evidence

- `docs/validation/stopping_power_reference_domain.svg` labels the below-range and above-range regions `REJECT`, shows the supported interpolation interval, and depicts former endpoint reuse with dashed lines. It explicitly states that it is a synthetic regression schematic rather than detector data.
- `docs/validation/stopping_power_reference_domain_validation.json` records task/session identifiers, initial/concurrent SHAs, reviewed blobs, exact commands, focused result, validated behavior, unrun checks, and `DIAGNOSTIC_ONLY` scientific status.

## Scientific interpretation

The correction prevents unsupported reference reuse. It does not establish a stopping-power closure.

Still unresolved under `AUD-G4-005` / `BLK-G4-SP-001`:

- local deposited energy may differ from projectile total energy loss when generated secondaries escape;
- particle energy evolves along the scored path;
- material, density, production cuts, and physics list affect the comparison;
- a direct proton closure has not been run here;
- `S_d(E) ~= S_p(E/2)` remains an approximation rather than a direct deuteron PSTAR datum.

No Geant4 executable, ROOT file, simulation output, calibration, stopping-power value, or detector-performance result was generated or changed.

## Direct-to-main commits

Implementation and validation evidence:

- `3f290bf64d9d47734ca6b9309249d27cc00ce8a0` — `fix(single-stave): reject unsupported PSTAR extrapolation`
- `237b67301355f37b2a26fec4fc02a858648be419` — `test(single-stave): cover PSTAR reference-domain gate`
- `72f60f61a3d88674b8d7bfa8d5ace7a01a1438fa` — `docs(validation): record PSTAR reference-domain audit`
- `7e1eb981848671302ef49c4c578d6a4ffa7fb487` — `docs(validation): add PSTAR domain validation record`
- `ddae4a4db15a58745dbbb95bb0abcc02bc973b4c` — `docs(validation): visualize PSTAR reference-domain gate`

Coordination and provenance:

- `a7f60d6008feccaaace51d798d6e9f90128b6551` — active task
- `663eedd58b1cc4e37e6e253bb8f7c34ec211c3fc` — backlog
- `cb1d72cd12dc188e760e6d94f37a49d54fdde52f` — master index
- `353c1a47c5a14eb6122c49cfef508988468e70d0` — code-result map
- `533853a7e4d392c2b0a9c015018d737cf40cc809` — study ledger
- `d2034c47c0be6809a62c7acb1c7d1e4181e5e9d6` — claim matrix
- `8be9e3dd776d96e39f328315dcf57642b7e3c34c` — visualization matrix
- `8c861bb67b207be4678a2f077555dd69f178fc8a` — blocker register
- `4dfa7b0d0ba2e7aa03b2c523f2219f3c28f043fd` — immutable archive

Every write returned a successful commit SHA on `main`. The remote head must be queried after this handoff write to record final confirmation in the user-facing report.

## Repository-local records

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/HANDOFF.md`

Added immutable record:

- `chatgpt_todo/archive/2026-07-23T102957Z_AUD-G4-006_PSTAR_REFERENCE_DOMAIN.md`

`chatgpt_todo/SESSION_LOG.md` is append-only. The connector provides complete-file replacement but no append operation; replacing the log without a checkout would risk changing prior history. The immutable archive contains the complete session entry. A checkout-capable follow-up should append it verbatim without changing earlier entries.

## Acceptance and next action

- Reference-domain failure mode: COMPLETE.
- Exact endpoint handling: COMPLETE.
- Deuteron transformed-energy gate: COMPLETE.
- CSV domain provenance: COMPLETE.
- Focused synthetic regression: COMPLETE.
- Visual and JSON evidence: COMPLETE.
- Remote-main implementation/evidence: COMPLETE.
- Accepted stopping-power closure: PARTIAL / BLOCKED.

Next task: execute `AUD-G4-005` in a clean Geant4 environment. Start with proton-only `G4EmCalculator::ComputeTotalDEDX` at exact reference energies and exact material/physics/cut configuration, then add primary entry/exit energy and secondary-escape diagnostics. Retain exact versions, commands, seeds, event counts, hashes, uncertainties, overlays/ratios, and failure interpretation. Keep the deuteron approximation separate.
