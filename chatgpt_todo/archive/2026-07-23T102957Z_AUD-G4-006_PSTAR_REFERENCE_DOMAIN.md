# AUD-G4-006 — PSTAR reference-domain gate

## Session

- UTC: `2026-07-23T10:29:57Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Canonical branch: `main`
- Initial observed remote main: `6d1d982e0eb6764cc3cc036aa1df76b8f3fe35c7`
- Concurrent main incorporated before writes: `9521eca866a42a02d17a26dffbaaf0f21d6d8eb7`
- Reviewed pre-change script blob: `d9282a5c26b8bc86427356f51dfe7e5ecba769d8`
- Reviewed reference-table blob: `7e953dd346caedcee6da54180fb636b890a64040`
- PR #868 status checked: closed, unmerged, head `7992aa318b6f13b5f4bcbd828ad97996075fed4b`; it was not modified or merged.

## Start-of-run review

A direct clone was attempted and failed with `Could not resolve host: github.com`. Authenticated GitHub connector reads and direct-to-main writes were used. The run inspected current history, PR #868, commit status, the latest handoff/active task/backlog/index/maps/blockers, the PR #890 comparison script, its regression, and the committed PSTAR table. No force-push, history rewrite, or unrelated deletion was performed.

The initial visible head advanced concurrently from `6d1d982e0eb6764cc3cc036aa1df76b8f3fe35c7` to `9521eca866a42a02d17a26dffbaaf0f21d6d8eb7`; all writes were based on the later head through GitHub's contents API.

## Confirmed defect

`interp_loglog()` returned the first table value for every lookup at or below the minimum energy and the last value for every lookup at or above the maximum energy. Thus values outside the committed PSTAR domain were silently clamped to an endpoint.

A numerical tolerance could therefore pass even though the selected stopping power did not support the requested energy. For deuterons, the relevant reference lookup is the proton-equivalent energy `E/2`, so range validation must be applied after that transformation.

Synthetic two-point reproduction, reference domain 1--10 MeV:

```text
old lookup 0.5 MeV -> 1 MeV endpoint
old lookup 20 MeV  -> 10 MeV endpoint
```

## Validated engineering change

`scripts/single_stave/compare_stopping_power.py` now:

- requires finite positive proton-equivalent lookup energy;
- permits exact table endpoints;
- performs log-log interpolation only inside the reference domain;
- rejects lower/upper extrapolation instead of clamping;
- reports beam energy and transformed lookup energy in errors;
- records lookup energy, minimum/maximum reference energy, and in-range state in CSV output;
- returns CLI status 2 and does not print a numerical PASS when the gate fails.

Added:

- `tests/test_compare_stopping_power_energy_range.py`;
- `docs/validation/stopping_power_reference_domain_audit.md`;
- `docs/validation/stopping_power_reference_domain_validation.json`;
- `docs/validation/stopping_power_reference_domain.svg`.

## Reproducible validation

The unmodified script was reconstructed exactly before patching. Its local Git blob was `d9282a5c26b8bc86427356f51dfe7e5ecba769d8`, matching the remote pre-change blob.

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

Additional checks:

- both changed Python files had no line longer than 100 characters;
- validation JSON parsed successfully;
- SVG parsed successfully as XML;
- remote script blob after write: `0436fb390476697cfc83f88208322a99d7792a1c`;
- remote test blob after write: `12f3ad78f5a261ebd427e5a37b62db7ccab81b10`;
- those remote blobs exactly match the validated local files.

The local reconstruction used a minimal static reference fixture. The complete committed reference table was inspected through the connector but was not executed locally. Full repository pytest, ruff, Geant4, CTest, ROOT, real simulation comparison, and GitHub Actions were not run.

## Visual evidence

`docs/validation/stopping_power_reference_domain.svg` shows:

- below-range lookup: REJECT;
- in-domain lookup: supported log-log interpolation;
- above-range lookup: REJECT;
- former endpoint reuse as dashed lines;
- proton-equivalent lookup energy axis in MeV;
- explicit synthetic/non-data label.

## Direct-to-main commits

Implementation and evidence:

- `3f290bf64d9d47734ca6b9309249d27cc00ce8a0` — `fix(single-stave): reject unsupported PSTAR extrapolation`
- `237b67301355f37b2a26fec4fc02a858648be419` — `test(single-stave): cover PSTAR reference-domain gate`
- `72f60f61a3d88674b8d7bfa8d5ace7a01a1438fa` — `docs(validation): record PSTAR reference-domain audit`
- `7e1eb981848671302ef49c4c578d6a4ffa7fb487` — `docs(validation): add PSTAR domain validation record`
- `ddae4a4db15a58745dbbb95bb0abcc02bc973b4c` — `docs(validation): visualize PSTAR reference-domain gate`

Coordination before archive:

- `a7f60d6008feccaaace51d798d6e9f90128b6551` — active task
- `663eedd58b1cc4e37e6e253bb8f7c34ec211c3fc` — backlog
- `cb1d72cd12dc188e760e6d94f37a49d54fdde52f` — master index
- `353c1a47c5a14eb6122c49cfef508988468e70d0` — code-result map
- `533853a7e4d392c2b0a9c015018d737cf40cc809` — study ledger
- `d2034c47c0be6809a62c7acb1c7d1e4181e5e9d6` — claim matrix
- `8be9e3dd776d96e39f328315dcf57642b7e3c34c` — visualization matrix
- `8c861bb67b207be4678a2f077555dd69f178fc8a` — blocker register

Every connector write returned a successful commit SHA on `main`. A final remote history check is required after the handoff write.

## Scientific boundary

This correction establishes only that the comparison does not invent reference support outside the committed table domain. It does not establish an accepted stopping-power result.

Unresolved under `BLK-G4-SP-001`:

- local deposited energy versus projectile total energy loss;
- energy evolution along the scored path;
- energy carried by generated secondaries;
- material/density/production-cut/physics-list dependence;
- direct proton closure;
- validity of the approximate deuteron `S_d(E) ~= S_p(E/2)` mapping.

No Geant4 executable, ROOT file, simulation output, calibration, stopping-power number, or detector-performance result was generated or changed.

## Session-log limitation

`chatgpt_todo/SESSION_LOG.md` is append-only. The connector exposes complete-file replacement but no append operation, and replacing the log without a checkout would risk altering prior history. This immutable archive contains the complete session record. A checkout-capable follow-up should append this record verbatim to `SESSION_LOG.md` without changing earlier entries.

## Acceptance

- Unsupported endpoint clamping: COMPLETE.
- Finite/positive lookup gate: COMPLETE.
- Deuteron transformed-energy range gate: COMPLETE.
- CSV reference-domain provenance: COMPLETE.
- Focused synthetic regression: COMPLETE.
- Markdown/JSON/SVG evidence: COMPLETE.
- Remote-main implementation/evidence delivery: COMPLETE.
- Accepted proton stopping-power closure: PARTIAL / blocked.
- Deuteron stopping-power validation: NOT ESTABLISHED.

## Next action

Execute `AUD-G4-005` in a clean Geant4 environment. Begin with proton-only `G4EmCalculator::ComputeTotalDEDX` at exact reference energies and the exact material/physics/cut configuration, then add primary entry/exit energy and secondary-escape diagnostics. Retain exact versions, commands, seeds, event counts, hashes, uncertainties, overlay/ratio plots, and failure interpretation. Keep the deuteron approximation separate.
