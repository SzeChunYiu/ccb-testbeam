# Latest Handoff

## Session

- **UTC:** 2026-07-23T12:14:45Z
- **Task:** `AUD-G4-008`
- **Initial remote main:** `9681e44d94fa825bb8db6c84af31448df0ec0689`
- **Validated implementation/evidence head:** `eb8791bd795d11a101d72a5d383a60baf0e19606`
- **Coordination/archive/session-log head before this handoff:** `7da55fb22112d1b42c1114703b441775f689194f`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for fail-closed quenched-proxy handling; PARTIAL for accepted stopping-power physics closure.

## Start-of-run review and concurrency

- A direct clone remained unavailable because the runtime could not resolve `github.com`; authenticated GitHub connector reads and direct-to-main writes were used.
- Inspected current main history and concurrent changes, repository metadata, open pull requests, PR #890, commit status, the stopping-power script and focused tests, prior validation records, and every mandatory `chatgpt_todo/` coordination file.
- The previous handoff head was `4bef9d97657c91ec5771830743629d5cda5eb95e`. A concurrent non-overlapping merge advanced main to session base `9681e44d94fa825bb8db6c84af31448df0ec0689` before implementation. Later concurrent documentation/QA merges were preserved because every contents write applied to the then-current `main`; no history was rewritten or force-pushed.
- The selected stopping-power script was unchanged by the concurrent base update and remained pre-change blob `7c3c05f12a1311d5ead8d1d45e0f5fea91dc92ce`.
- No status checks were attached to the initial or implementation/evidence heads. No GitHub Actions success is claimed.
- PR #868 remains closed and unmerged and was not modified.

## Confirmed defect

The former simulation reader preferred unquenched fields `edep_scint_raw_MeV` / `edep_raw_MeV`, but silently fell back to quenched visible-energy fields `edep_scint_MeV` / `edep_MeV` after printing a warning. The quenched value then passed through the same raw-PSTAR tolerance gate and could report `within_tolerance=True`.

A targeted reproduction of the exact old fallback path with one quenched-only synthetic event produced:

```text
WARNING: edep_scint_raw_MeV absent -- using the QUENCHED edep_scint_MeV; ratios vs raw PSTAR will look low.
rows=1 ratio=1.0 within_tolerance=True
```

This is a physics-semantics error, not merely a missing warning. Geant4 Birks quenching is a nonlinear conversion from deposited energy to visible detector response, while NIST PSTAR total stopping power is collision plus nuclear projectile energy loss per unit path length. A quenched visible-energy proxy is not raw stopping power even when the numbers happen to agree.

Primary method references reviewed:

- Geant4 Collaboration, *Birks Quenching*, Book for Application Developers 11.4: `https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/birks.html`
- NIST, *Description of PSTAR and ASTAR databases*: `https://physics.nist.gov/PhysRefData/Star/Text/programs.html`
- NIST, *Significance of Calculated Quantities*: `https://physics.nist.gov/PhysRefData/Star/Text/appendix.html`

## Validated change

`scripts/single_stave/compare_stopping_power.py` now:

- rejects quenched-only input by default with `StoppingPowerInputError` and CLI status 2;
- adds `--allow-quenched-proxy` only for explicitly labelled diagnostic output;
- rejects a file mixing raw and quenched rows because the aggregate has no single energy-deposit convention;
- records `energy_deposit_basis` as `UNQUENCHED_RAW` or `QUENCHED_PROXY`;
- records `raw_pstar_comparable`;
- separates arithmetic-only `numeric_within_tolerance` from accepted `within_tolerance`;
- forces accepted `within_tolerance=False` for every quenched proxy;
- prints `NUMERICAL TOLERANCE: NOT_ACCEPTED_QUENCHED_PROXY` and exits nonzero in explicit proxy mode;
- preserves normal diagnostic numeric behavior for unquenched raw input.

Added:

- `tests/test_compare_stopping_power_quenched_proxy.py`
- `docs/validation/stopping_power_quenched_proxy_audit.md`
- `docs/validation/stopping_power_quenched_proxy_validation.json`
- `docs/validation/stopping_power_quenched_proxy.svg`

The four new tests cover default rejection, explicit labelled/non-accepting output plus CSV provenance, mixed-semantics rejection, and unchanged raw-input acceptance.

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

- exact old fallback reproduced a quenched-only ratio `1.0` with `within_tolerance=True`;
- no changed Python line exceeded 100 characters;
- validation JSON parsed successfully;
- validation SVG parsed successfully as XML;
- committed script blob `ef535a47ee36b2706f6b720f0231648c23bc11a7` matches the validated local Git blob;
- committed test blob `af282789ce2e47ba680fa29296cdb81a7c45287f` matches the validated local Git blob;
- reconstructed pre-append `SESSION_LOG.md` matched existing blob `87a06b62c74c6b29445cc0d590b84f73ee34cf9f`, and the append produced blob `5188115b58a863275c62df7930e35428a9f66f65` without changing prior bytes.

The local reference fixture contained the energies required by the existing synthetic tests. The complete committed PSTAR table, real Geant4 event files, full repository pytest, ruff, CTest, real simulation processing, and GitHub Actions were not run.

## Visual evidence

`docs/validation/stopping_power_quenched_proxy.svg` is explicitly labelled as a synthetic regression schematic and not detector data. It contrasts:

- the former quenched-field fallback, warning, and possible numerical PASS;
- default status-2 rejection;
- explicit `QUENCHED_PROXY` diagnostic output with `NOT_ACCEPTED_QUENCHED_PROXY`.

The distinction is communicated by labels and layout, not color alone.

## Scientific interpretation

The correction prevents a quenched detector-response proxy from masquerading as raw PSTAR agreement. It does not establish Geant4-to-PSTAR closure.

Still unresolved under `AUD-G4-005` / `BLK-G4-SP-001`:

- local deposited energy may differ from projectile total energy loss when generated secondaries escape;
- projectile energy evolves along the scored path;
- material, density, production cuts, and physics list affect the result;
- deuteron `S_d(E) ≈ S_p(E/2)` remains an approximation;
- the committed PSTAR transcription was not independently refreshed in this session.

No Geant4 executable, ROOT file, real simulation, stopping-power measurement, calibration, or detector-performance output was generated.

## Direct-to-main commits

Implementation and validation evidence:

- `4b93451980ee116a1d11aa0ac513d3aa21b9fb0f` — `fix(single-stave): reject quenched PSTAR proxy acceptance`
- `0aba2ed3eb40403da9169c51cf1ca299a25845b1` — `test(single-stave): cover quenched PSTAR proxy gate`
- `6c1ee31c302ffc2ae925807ba950451832a09cf4` — `docs(validation): record quenched PSTAR proxy audit`
- `1a4696418344db25b05d9a82ad208edc58d43153` — `docs(validation): add quenched PSTAR proxy record`
- `eb8791bd795d11a101d72a5d383a60baf0e19606` — `docs(validation): visualize quenched PSTAR proxy gate`

Coordination and provenance:

- `5126bf426bcfa1a379b82f7e78983aeba22a21b5` — `docs(audit): claim quenched PSTAR proxy gate`
- `7b51eb86229bfea4f34b20084f4b4dac5c8cff25` — `docs(audit): track quenched PSTAR proxy gate`
- `f19412297dd148e5917366942975037900881669` — `docs(audit): index quenched PSTAR proxy risk`
- `f25d9963ddb59a1810d4ab26795c43e6dc02763b` — `docs(audit): map quenched proxy to PSTAR output`
- `3ab7667b556e2ee94023f21186a7ae80b0ce1340` — `docs(audit): update stopping study input semantics`
- `17762a456415dd3bd3c30a6171b2c8771493f6d9` — `docs(audit): classify quenched PSTAR proxy claim`
- `6cc3272eaf43fa0cb9225f527896542ccbe372d0` — `docs(audit): register quenched PSTAR proxy visual`
- `49a253646dc5613dba4ecfb963b206ccbaa48817` — `docs(audit): refine stopping blocker with quenched proxy gate`
- `4975030e86cc1d46eceeedca61c08ea88119c0e6` — `docs(audit): archive quenched PSTAR proxy gate`
- `7da55fb22112d1b42c1114703b441775f689194f` — `docs(audit): append quenched PSTAR proxy session`

Push/output record: every GitHub contents write returned a successful commit SHA directly on `main`. Recent remote history confirmed these commits in order while preserving concurrent non-overlapping commits. No task branch, draft PR, force-push, or history rewrite was used.

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
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/HANDOFF.md`

Added immutable provenance:

- `chatgpt_todo/archive/2026-07-23T121445Z_AUD-G4-008_QUENCHED_PROXY_GATE.md`

## Acceptance and next action

- Exact pre-change failure reproduction: COMPLETE.
- Default quenched-input rejection: COMPLETE.
- Explicit proxy labelling and non-acceptance: COMPLETE.
- Mixed-semantics rejection: COMPLETE.
- Raw-input compatibility: COMPLETE.
- Focused synthetic regression: COMPLETE (`18 passed`).
- Markdown/JSON/SVG evidence: COMPLETE.
- Direct-to-main implementation/evidence: COMPLETE.
- Accepted stopping-power closure: PARTIAL / BLOCKED.

Next task: execute `AUD-G4-005` in a clean Geant4 environment. Start with proton-only `G4EmCalculator::ComputeTotalDEDX` at exact reference energies and exact material/physics/cut configuration, then add primary entry/exit-energy and secondary-escape diagnostics. Retain exact versions, commands, seeds, event counts, hashes, statistical/systematic uncertainties, overlays, ratios, and failure interpretation. Keep the deuteron approximation separate.
