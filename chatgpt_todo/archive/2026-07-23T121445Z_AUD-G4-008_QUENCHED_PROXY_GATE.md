# AUD-G4-008 — Quenched PSTAR Proxy Acceptance Gate

## Session

- **UTC:** 2026-07-23T12:14:45Z
- **Owner:** scheduled ChatGPT audit session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial main SHA:** `9681e44d94fa825bb8db6c84af31448df0ec0689`
- **Implementation/evidence head:** `eb8791bd795d11a101d72a5d383a60baf0e19606`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for fail-closed quenched-proxy handling; PARTIAL for accepted stopping-power physics closure.

## Start-of-run review

Inspected current main history and concurrent changes, repository permissions, open pull requests, combined status checks, PR #890, the stopping-power script and focused tests, prior stopping-power validation records, and the mandatory `chatgpt_todo/` files. A concurrent non-overlapping merge advanced main from the previous handoff to `9681e44d94fa825bb8db6c84af31448df0ec0689`; the reviewed stopping-power script remained blob `7c3c05f12a1311d5ead8d1d45e0f5fea91dc92ce`.

A direct clone remained unavailable because the runtime could not resolve `github.com`. Authenticated GitHub connector reads and direct-to-main writes were used. No status checks were attached to the initial head.

## Confirmed defect

The former simulation reader selected `edep_scint_raw_MeV` / `edep_raw_MeV` when present but silently fell back to quenched `edep_scint_MeV` / `edep_MeV` after printing a warning. The quenched value then passed through the same raw-PSTAR tolerance calculation and could produce `within_tolerance=True`.

Targeted reproduction of the exact old fallback path with one synthetic quenched-only event produced:

```text
WARNING: edep_scint_raw_MeV absent -- using the QUENCHED edep_scint_MeV; ratios vs raw PSTAR will look low.
rows=1 ratio=1.0 within_tolerance=True
```

That is a method error. Geant4 Birks quenching is a nonlinear deposited-energy-to-visible-signal response, while NIST PSTAR total stopping power is collision plus nuclear energy loss per unit path length. Numerical equality of a quenched signal proxy and the PSTAR value is not raw stopping-power agreement.

## Validated correction

`scripts/single_stave/compare_stopping_power.py` now:

- rejects quenched-only input by default with `StoppingPowerInputError` and CLI status 2;
- provides `--allow-quenched-proxy` only for explicitly labelled diagnostic output;
- records `energy_deposit_basis`, `raw_pstar_comparable`, `numeric_within_tolerance`, and accepted `within_tolerance` separately;
- forces `within_tolerance=False` for quenched proxy output even when arithmetic is numerically close;
- prints `NUMERICAL TOLERANCE: NOT_ACCEPTED_QUENCHED_PROXY` and exits nonzero in explicit proxy mode;
- rejects files that mix raw and quenched rows because aggregate semantics are undefined;
- preserves normal diagnostic behavior for unquenched raw input.

Added `tests/test_compare_stopping_power_quenched_proxy.py` with four focused cases covering default rejection, explicit non-accepting proxy output and CSV provenance, mixed-semantics rejection, and unchanged raw-input acceptance.

## Reproducible validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_quenched_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_quenched_proxy.py -q

18 passed in 2.86s
```

Additional checks:

- no changed Python line exceeded 100 characters;
- validation JSON parsed successfully;
- validation SVG parsed successfully as XML;
- validated script blob: `ef535a47ee36b2706f6b720f0231648c23bc11a7`;
- validated test blob: `af282789ce2e47ba680fa29296cdb81a7c45287f`;
- both local Git blob hashes matched the committed GitHub content SHAs.

The local reference fixture contained the energies required by the existing synthetic tests. The complete committed PSTAR table, real Geant4 event files, full repository test suite, ruff, CTest, and GitHub Actions were not executed.

## Version-controlled evidence

Added:

- `docs/validation/stopping_power_quenched_proxy_audit.md`
- `docs/validation/stopping_power_quenched_proxy_validation.json`
- `docs/validation/stopping_power_quenched_proxy.svg`

The SVG is explicitly labelled as a synthetic regression schematic and is not detector data.

## Direct-to-main commits before archive

Implementation and evidence:

- `4b93451980ee116a1d11aa0ac513d3aa21b9fb0f` — `fix(single-stave): reject quenched PSTAR proxy acceptance`
- `0aba2ed3eb40403da9169c51cf1ca299a25845b1` — `test(single-stave): cover quenched PSTAR proxy gate`
- `6c1ee31c302ffc2ae925807ba950451832a09cf4` — `docs(validation): record quenched PSTAR proxy audit`
- `1a4696418344db25b05d9a82ad208edc58d43153` — `docs(validation): add quenched PSTAR proxy record`
- `eb8791bd795d11a101d72a5d383a60baf0e19606` — `docs(validation): visualize quenched PSTAR proxy gate`

Coordination:

- `5126bf426bcfa1a379b82f7e78983aeba22a21b5` — active task
- `7b51eb86229bfea4f34b20084f4b4dac5c8cff25` — backlog
- `f19412297dd148e5917366942975037900881669` — master index
- `f25d9963ddb59a1810d4ab26795c43e6dc02763b` — code-result map
- `3ab7667b556e2ee94023f21186a7ae80b0ce1340` — study ledger
- `17762a456415dd3bd3c30a6171b2c8771493f6d9` — claim matrix
- `6cc3272eaf43fa0cb9225f527896542ccbe372d0` — visualization matrix
- `49a253646dc5613dba4ecfb963b206ccbaa48817` — blocker register

Every write returned a successful commit SHA on `main`; no force-push or history rewrite was used.

## Scientific boundary

This work prevents a quenched detector-response proxy from masquerading as raw PSTAR agreement. It does not establish Geant4-to-PSTAR closure. Still unresolved under `AUD-G4-005` / `BLK-G4-SP-001`:

- local deposited energy may differ from projectile energy loss when generated secondaries escape;
- projectile energy evolves along the scored path;
- material, density, production cuts, and physics list affect the result;
- deuteron `S_d(E) ≈ S_p(E/2)` remains an approximation;
- the committed PSTAR source transcription has not been independently refreshed here.

No Geant4 executable, ROOT file, real simulation, stopping-power measurement, calibration, or detector-performance result was generated.

## Next action

Execute `AUD-G4-005` in a clean Geant4 environment. Start with proton-only `G4EmCalculator::ComputeTotalDEDX` at exact reference energies and exact material/physics/cut configuration, then add primary entry/exit-energy and secondary-escape diagnostics. Retain versions, commands, seeds, event counts, hashes, statistical/systematic uncertainties, overlays, ratios, and explicit failure interpretation. Keep the deuteron approximation separate.
