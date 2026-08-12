# ARU-SIPM-CAMPAIGN-MANIFEST-CORE-SHA-SOURCE-001

Status: `ACTIVE / PRE-CI SOFTWARE-PROVENANCE CLOSURE`

Parent: #977. Cross-dependencies: #1067, #1072, #1280, #1282.

## Selected atom and exact contract

The previous downstream gate can compare every sensitivity sidecar against an optional `--expected-core-sha`, but the expectation itself is currently an operator-provided string. This atom defines the source of that expectation.

For one SiPM sensitivity campaign let:

- `H_link(I)` be the `geant4/single_stave/sipm` gitlink in the exact superproject commit that defines campaign intent `I`;
- `H_expected(I)` be the core revision recorded in the campaign-intent manifest;
- `H_meta,j` be `digitizer.ccb_sipm_core_commit` in point `j`'s producer sidecar;
- `M = SHA256(canonical campaign-intent bytes)`;
- `G_k = SHA256(points_<knob>.csv)` for each submitted knob grid.

The bounded campaign contract is

`H_expected(I) = H_link(I)`

and every job/analysis point must satisfy

`H_meta,j = H_expected(I)`.

The scheduler submission binds `M` into each job's argv. Each job verifies the current manifest bytes against that frozen `M` and verifies its selected grid against `G_k` before launching simulation. This prevents a post-submission edit of the manifest or grid from silently changing the intended campaign.

This is source-intent provenance only. It does not prove that the build directory contains executable bytes built from the declared superproject commit; that remains `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`.

## Input/output and scientific meaning

Inputs: exact checked-out superproject `HEAD`; exact gitlink object at `geant4/single_stave/sipm`; generated `points_<knob>.csv` bytes; campaign base CLI; event count per point; fixed single-thread execution intent.

Output: canonical `ccb-sipm-campaign-intent/1` JSON plus SHA-256, with exact superproject commit, exact expected core gitlink, provenance source string `SUPERPROJECT_GITLINK:geant4/single_stave/sipm`, execution intent, and every selected grid SHA-256. The job also writes a point companion `ccb-sipm-campaign-point/1` record only after the producer sidecar's compiled core SHA equals the manifest expectation.

No detector measurand is estimated by this atom. The observable is provenance consistency over code/configuration identities.

## Competing mechanisms

### H1 — operator-provided expected SHA is campaign truth

Rejected as authorising provenance. A correctly formatted 40-hex token can be stale, mistyped, or intentionally substituted and has no content-bound relation to the source tree.

### H2 — campaign-internal sidecar homogeneity is sufficient

Rejected as sufficient. Homogeneity detects mixed implementations but does not establish that a homogeneous historical label is authentic or intended.

### H3 — derive expected SHA from exact superproject gitlink and freeze campaign bytes before submission

Survives as the bounded implementation. The expected core cannot be entered independently; it is derived by `git ls-tree HEAD geant4/single_stave/sipm`. Canonical manifest bytes, grid hashes, and an argv-bound manifest digest make later mutations fail closed.

### H4 — binary/toolchain build manifest is the only acceptable source

Scientifically stronger for executable-byte identity but not equivalent to campaign source intent. It remains a child rather than replacing H3.

## Equations, invariants, limiting cases

- `H_expected != H_link -> reject before submission` by construction: the creator has no expected-core input.
- `SHA256(manifest_now) != M_submit -> reject before simulation`.
- `SHA256(grid_now) != G_k -> reject before simulation`.
- `H_meta != H_expected -> reject task after producer execution and before declaring the point campaign-compatible`.
- Re-running the exact same intent in the same output directory is idempotent; attempting to overwrite an existing path with different intent is rejected.
- A canonical manifest and matching core sidecar do not establish `H_binary = H_superproject`; stale-build identity is an independent child.

## Implemented repository surfaces

Branch `audit/sipm-campaign-manifest-core-sha-source-v1` started from exact protected `main@4abbf9112ad7933b4f0ec5b927f2d0f358ad08be`.

- `scripts/single_stave/sipm_campaign_manifest.py`: canonical create/verify helper; derives superproject/core identities from Git; hashes selected grids; refuses changed intent overwrite; validates frozen manifest/grid digests.
- `tests/test_sipm_campaign_manifest.py`: seven deterministic hostile/positive controls.
- `geant4/single_stave/slurm/run_sensitivity_campaign.sh`: creates and freezes intent after grid generation; passes literal manifest digest into every Slurm job; analyzer expectation is re-derived from the frozen manifest.
- `geant4/single_stave/slurm/submit_systematic.sh`: verifies manifest and selected grid before simulation; after execution, requires exact sidecar core equality and writes a point-level campaign provenance record.

The existing `sipm_sensitivity.py --expected-core-sha` remains unchanged; direct manual invocation can still supply an operator token. That is a surviving child, `ARU-SIPM-CAMPAIGN-POINT-MANIFEST-CONSUMER-001`, if direct/manual analyzer use is to become authorising.

## Executed discriminators

All tests below are software/provenance fixtures only. No beam data, production Geant4, detector ROOT population, or measured electronics calibration participated.

1. Focused unit suite: `python -m pytest -q tests/test_sipm_campaign_manifest.py` in a reconstructed repository fixture returned `7 passed in 0.04s` under the available Python runtime. The seven controls cover exact gitlink source, operator-source rejection, post-submission byte mutation, canonical key-order invariance, overwrite refusal, malformed/wrong-path source contracts, and grid-byte mutation.
2. Python compile check: `python -m py_compile sipm_campaign_manifest.py` succeeded.
3. Shell syntax: `bash -n run_sensitivity_campaign.sh submit_systematic.sh` succeeded.
4. Gitlink derivation fixture: a temporary Git repository with a gitlink pointing to the current real core revision `3627dc87137a9f33f511a755671414b11853c0a0` produced that exact expected core from the manifest creator and verifier. Mutating `nevents_per_point` from 60 to 61 while retaining the submitted digest caused verification exit code 3 with a manifest-byte-digest mismatch.
5. End-to-end fake-job fixture: a mocked `module`/`srun` plus a fake executable writing a dummy ROOT path and producer sidecar completed only when observed core equalled the manifest gitlink. It wrote `ccb-sipm-campaign-point/1` with `core_match=true`. After mutating the submitted grid while retaining the frozen campaign digest, the job exited 3 on the grid digest mismatch and no new fake ROOT output was produced.

Ruff is not installed in the local execution container, so no local Ruff PASS is claimed. The Python files were explicitly checked for lines longer than 100 characters and none remained after formatting. Protected exact-head repository CI remains the integration gate.

## Four sequential AI review passes

### A. Detector-response/provenance lead

Evidence inspected: current #977 contract/comments, #1280 compile-bound producer, #1282 consumer gate, current gitlink, campaign launcher, systematic launcher, helper/tests and executed fixtures.

Strongest counter-hypothesis: an explicit operator `--expected-core-sha` is enough once sidecars are homogeneous.

Attempted falsifier: remove any independent expected-core input and derive only from a Git object in campaign intent; hostile operator-source fixture is rejected.

Residual uncertainty: the build directory/executable can still be stale relative to the superproject intent.

Vote: **ACCEPT source-bound campaign-intent design / REVISE until exact-head protected CI passes / BLOCK #977 COMPLETE**.

### B. Adversarial provenance reviewer

Evidence inspected: manifest overwrite semantics, canonical serialization, digest propagation into job argv, grid binding and fake-job path.

Strongest counter-hypothesis: writing a manifest plus a digest file is cosmetic because both files can be edited together.

Attempted falsifier: the literal manifest digest is copied into submitted job argv. Mutating on-disk manifest/grid bytes after submission while retaining argv state fails before simulator execution.

Residual uncertainty: scheduler job argv and executable/build bytes are not yet serialized into the producer sidecar itself.

Vote: **ACCEPT mutation/substitution control / BLOCK executable-byte identity**.

### C. Independent statistics/validation reviewer

Evidence inspected: seven deterministic tests; gitlink derivation fixture; manifest mutation; grid mutation; point-core equality path; no RNG/statistical data involved.

Strongest counter-hypothesis: deterministic fixtures establish detector-response reproducibility.

Attempted falsifier: distinguish deterministic provenance equality from physics equivalence. None of these tests samples detector response, so detector inference is impossible by design.

Residual uncertainty: protected CI and real scheduler execution remain unexecuted for this branch.

Vote: **ACCEPT deterministic software oracle / BLOCK detector inference / REVISE pending CI**.

### D. Claims/provenance reviewer

Evidence inspected: #977 and #1067 acceptance criteria; current handoff; historical sidecar caveat from #1282; direct analyzer CLI.

Strongest counter-hypothesis: a source-bound campaign manifest retroactively authorises old sensitivity outputs.

Attempted falsifier: pre-#1280 sidecars could still contain caller-provided full SHAs and cannot be authenticated by a later manifest.

Residual uncertainty: historical artifacts and direct/manual analyzer invocation remain separate leaves.

Vote: **ACCEPT bounded source-intent improvement / KEEP #977 and #1067 OPEN/PARTIAL**.

## Cross-scale propagation and claims

Micro/software: campaign source intent now has a deterministic identity relation to the exact superproject gitlink.

Run/point: the orchestrated Slurm lane rejects changed intent/grids before simulation and rejects a produced sidecar whose compiled core revision disagrees with intent.

Study: this does not authenticate legacy campaign artifacts and does not prove the executable was built from the superproject commit. Direct analyzer invocation is not yet forced to consume the manifest.

Claim/wiki: no detector-response, DATA↔MC, timing, PID, efficiency, rate, saturation, ESS, p-value, or calibration claim is promoted. #977 and #1067 remain open.

## Spawned / retained children

- `ARU-SIPM-CAMPAIGN-POINT-MANIFEST-CONSUMER-001`: make direct/manual analysis consume a content-bound campaign manifest rather than a raw expected-SHA token if it is to be authorising.
- `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`: bind executable bytes/toolchain/build inputs to superproject/core source intent.
- `ARU-SIPM-CAMPAIGN-SUPERPROJECT-BUILD-CLOSURE-001`: test stale-build versus source-tree mismatch explicitly at launch.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`: classify historical sidecars produced before compile binding.
- #1072 requested-to-effective operating-point closure.
- #1067 measured-impulse source/calibration authorization.

## Handoff

Require exact final-head protected MC Validation before merging. Do not close #977/#1067. Do not absorb unrelated draft PR #1279. If this branch goes green, the next highest-value atom is the binary/build-manifest child because source-bound campaign intent still cannot prove which executable bytes actually generated an output.