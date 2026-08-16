# ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001 — exact-head CI falsifier and repair

Status: `ACTIVE / REVISED_AFTER_EXACT_HEAD_CI_FAILURE / REPAIRED_HEAD_PENDING_CI`

Parent: #1182. Branch/PR: `audit/geant4-runtime-link-coobservation`, draft #1208. Protected base inspected: `a9b7184bce1b898a2b36143ed4bd7f725d5a0f8a`.

## Atom contract retained

For every runtime file-backed executable object with key `K=(dev_major,dev_minor,inode)`, a current mapped pathname must resolve to `K`, an opened file descriptor must `fstat()` to `K`, and one descriptor snapshot `B` supplies both `SHA256(B)` and the bounded ELF metadata parser input. Path resolution, process start-time, and the complete executable mapping projection are rechecked before PASS. Non-path `DT_NEEDED` closes by a unique co-observed `DT_SONAME`; relative slash paths remain blocked without cwd provenance; absolute dependencies and `PT_INTERP` close by stable device/inode resolution to exactly one co-observed object.

## Exact-head falsifier

MC Validation run `31466409401` evaluated PR head `965ba13719ce711d47f88941be2e8a471837345e` and failed. Runner Python was 3.11.15. The curated ruff step returned status 1 with three syntax findings at source lines 204-205, centered on an unexpected indentation after `raise ValueError(m)`. Full non-integration pytest returned status 2 because collection of `tests/test_geant4_runtime_link_coobservation.py` raised the same `IndentationError`. The final enforcement step correctly failed the job.

Exact-blob inspection then found that the committed tool was truncated in the middle of `attest_runtime_link_coobservation()` and contained two additional latent defects before the truncation:

1. `_fd_snapshot` tested undefined `bloc` instead of `block`, so a successful read would raise `NameError` when that line executed.
2. `_runtime_object_key` constructed `(device_major,inode,inode)` rather than `(device_major,device_minor,inode)`, invalidating the mapped-object identity contract.
3. The content-mismatch `ValueError` expression was malformed, producing the observed syntax failure.

Therefore the earlier local authoring-note statement that `py_compile` passed cannot be mapped onto the committed branch bytes and is superseded as repository evidence. The exact-head CI failure is retained, not averaged away.

## Repair executed

Commit `fb6df0e528b5a98351b179a82d78612cca80b3ce` replaced the corrupt/truncated Git blob with a complete implementation. It fixes the short-read variable, restores `(device_major,device_minor,inode)`, repairs the content-mismatch exception, completes receipt/process/projection validation, co-observes every object, uniquely identifies the live executable, closes direct dependencies/interpreter under the bounded rules, rechecks maps/start-time, and emits a content-digested receipt.

Post-repair local evidence is intentionally narrow: Python 3.13.5 `py_compile` passed on the repaired authoring file; a small stubbed core-logic smoke returned `1 passed`. Those observations do not substitute for repository ruff/full pytest and do not validate HIBEAM or Geant4 physics. Fresh exact-head MC Validation run `31467525013` is the authoritative pending gate for repaired head `fb6df0e528b5a98351b179a82d78612cca80b3ce`.

## Competing mechanisms and eliminations

- `H1`: first CI failure was transient runner noise — **eliminated** by exact source syntax corruption and pytest import failure on the same bytes.
- `H2`: only one indentation typo existed — **eliminated** by exact-blob inspection showing file truncation plus `bloc` and device-minor defects.
- `H3`: local authoring validation implies committed-source validation — **eliminated** because exact-head CI inspected different/corrupted committed bytes.
- `H4`: repaired complete source satisfies the intended contract — **survives locally**, pending exact-head repository tests.

## Four sequential AI reviews

### (a) Linux/Geant4 runtime-provenance lead — `REVISE / ACCEPT repaired bounded mechanism / BLOCK HIBEAM authorisation`
Evidence inspected: failed CI log, exact corrupt Git blob, predecessor receipt contracts, repaired source. Strongest counter-hypothesis: the failure is cosmetic and the intended mechanism can still be treated as validated. Falsifier: source does not import on the failed head. Residual uncertainty: repaired full repository behavior and real HIBEAM runtime remain untested.

### (b) Adversarial mechanism reviewer — `REVISE / BLOCK until repaired exact-head tests pass`
Evidence inspected: truncation, identity tuple defect, short-read typo, hostile test matrix. Strongest counter-hypothesis: correcting syntax alone is sufficient. Falsifier: the two latent semantic/runtime defects are independent of syntax. Residual uncertainty: additional integration defects may emerge under full pytest.

### (c) Independent statistics/validation reviewer — `BLOCK merge pending exact-head ruff + full pytest`
No stochastic estimator is involved in this software-provenance atom. Evidence inspected: CI statuses `ruff=1`, `pytest=2`; local repaired py_compile/stub smoke. Strongest counter-hypothesis: the local smoke is enough to validate the branch. Falsifier: it does not load the full repository predecessor modules/tests. Residual uncertainty: exact-head GitHub test outcome.

### (d) Claims/provenance reviewer — `ACCEPT transparent correction / BLOCK CL-021 and detector promotion`
Evidence inspected: PR wording, issue #1182, failed/run identifiers and repair commit. Strongest counter-hypothesis: overwrite the prior failure in the narrative once repaired. Falsifier: provenance requires preserving the failed head because it invalidates a prior evidence statement. Residual uncertainty: downstream linker/runtime/run-manifest/compiled physics controls remain open.

## Child atoms

New child: `ARU-REPO-CONTENT-TRANSFER-001` — when local validation is used as evidence for a repository change, explicitly compare the locally checked bytes/hash against the committed GitHub blob or otherwise execute validation directly on the exact committed checkout.

Existing children remain: `ARU-MC-G4-LOADER-SEARCH-001`, `ARU-MC-G4-LINK-COMMAND-001`, `ARU-MC-G4-LATE-DLOPEN-001`, `ARU-MC-G4-NONEXEC-RELOCATION-001`, wrapper/descendant identity, immutable consumption, runtime manifest, compiled hostile source/stopping controls, source/support/UQ, event-weight and detector-response chains.

## Claim consequences

This repair changes software/provenance evidence only. It regenerates no Geant4 event, beam/MC ROOT product, detector observable, B2/B8 value, PID, timing, calibration, pile-up, ESS, p-value or rate. #1182 and CL-021 remain gated regardless of this atom's eventual CI result.
