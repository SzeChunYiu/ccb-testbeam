# Latest Handoff

## Session

- **Task ID:** `AUD-REP-002`
- **Stamp:** `2026-07-26T150519Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `f30ff1100592e06396598ebf6975afa88e84444f`
- **Validated implementation/evidence through:** `0a6876829c51e59974588bf2c4a10748e5480376`
- **Destination:** sequential commits directly to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** each authenticated GitHub contents write returned a successful direct-main commit SHA. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** software/provenance remediation, regressions, machine-readable evidence, visual evidence, audit report, immutable archive, active-task record, and this handoff are `VALIDATED / COMPLETE`.

## Repository state and concurrent work

At task selection, remote `main` had advanced from the previous timing-audit head to
`f30ff1100592e06396598ebf6975afa88e84444f`, which published a new Cluster E
canonical claim front door. That concurrent work was inspected rather than
duplicated. PR #939 remained open and unmerged with the previously documented
event-identity, residual-visualization, and single-stave-inference defects. PR #868
remained closed and unmerged. No pull request was merged in this task.

## Confirmed defects

The pre-remediation producer read each input path once for parsing and SHA-256, then
separately ran `git hash-object --no-filters -- <path>` against the live path. A
replacement between those operations could pair parsed bytes A with a Git blob
identifier for bytes B.

The producer checked that the requested base commit equalled `HEAD`, but did not
require the retained worktree bytes to equal `base_commit:path`. Dirty but
semantically valid source bytes could therefore be published while provenance
claimed a clean base commit.

The preceding provenance bundle recorded syntactically valid blob/SHA-256 values but
had no per-input commit, expected commit-tree blob, equality state, or authorization
policy. Validator v2.0.0 could not distinguish base-commit bytes from dirty or
replacement bytes.

## Policy and remediation

Policy:

`INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS`

The producer now:

1. reads every UTF-8 input exactly once;
2. calculates the Git blob SHA-1 directly from the retained bytes using
   `blob <length>\0<bytes>`;
3. resolves the expected identity with `git rev-parse <base_commit>:<path>`;
4. rejects any mismatch as `INPUT_NOT_AT_BASE_COMMIT:<path>`;
5. records the measured and commit-tree blobs, commit, equality state, SHA-256,
   bytes, snapshot policy, and authorization policy;
6. publishes schema-3 provenance and metrics.

Validator v2.1.0 requires the same machine-readable contract and rejects legacy
unbound identities or commit-blob mismatch.

## Independent controls

- Committed control Git blob: `f80f50c325b2c99bb467c4758a4c23535d133162`.
- Dirty control Git blob after one uncommitted line:
  `6a11afca199b1afb42510881f24df961e085ddf9`.
- Expected result: dirty bytes fail with `INPUT_NOT_AT_BASE_COMMIT`.
- A replacement-after-snapshot regression changes the path before the commit lookup;
  the recorded digest remains the digest of the retained bytes, not later path
  contents.

## Files delivered

- `scripts/clusterE/clusterE_canonical_frontdoor.py`
- `tests/test_clusterE_canonical_frontdoor.py`
- `tools/audit/validate_clusterE_canonical_binding_v2.py`
- `tests/test_validate_clusterE_canonical_binding_v2.py`
- `tools/audit/render_clusterE_input_commit_binding_evidence.py`
- `docs/validation/clusterE_input_commit_binding_validation.json`
- `docs/validation/clusterE_input_commit_binding.svg`
- `docs/validation/clusterE_input_commit_binding_audit.md`
- `chatgpt_todo/archive/2026-07-26T150519Z_AUD-REP-002_CLUSTERE_INPUT_COMMIT_BINDING.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this handoff.

## Validation

```text
python -m py_compile \
  scripts/clusterE/clusterE_canonical_frontdoor.py \
  tools/audit/validate_clusterE_canonical_binding_v2.py \
  tests/test_clusterE_canonical_frontdoor.py \
  tests/test_validate_clusterE_canonical_binding_v2.py \
  tools/audit/render_clusterE_input_commit_binding_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_clusterE_canonical_frontdoor.py \
  tests/test_validate_clusterE_canonical_binding_v2.py

11 passed in 0.20s
```

The evidence renderer returned `VALIDATED` with zero findings. The JSON parsed, the
SVG parsed as XML, and changed Python lines are at most 100 characters.

SHA-256 identities:

- producer `230df0122c6a56cdf6a6d99870cf16e254da7467580d630363b2eeb2f681fee8`;
- producer tests `d11ade4f7b0de3596860f3af30c7b3df84ca28ef43147b23f7c840293ce47cf6`;
- validator `42e9c6a676d215aa8f546bcd32bf9bb0617398eafcced2cdf76cd928a8530aa5`;
- validator tests `85def154c01f8f77673c6ed20c6fb714d15f3dff60c0a07f3c12e49d9e47003c`;
- renderer `102f508d09ea91399a8e783acda59e6f15d79a94a3677968b3ab8d2afd22116f`;
- JSON `8477f037c289aad968d64ee323655cd07f113dc809228e8b2fc4de3b4002c4c5`;
- SVG `fe3431a1c650eec3f79bf9efad4333ceabd824d74f6698b1fad694856a016639`.

## Direct-main sequence

- `d4ae31bbe2c5065b7904ee1c93273204240f7a3e` — bind retained input bytes to the base commit;
- `75144e43bd69040b80743bd29b787dd5a621f594` — producer regressions;
- `a77e1853c5658c62aa9dd4d7f13f5330d4e11584` — commit-bound validator gate;
- `0c084bb821a6c4e630068f1f7a22002fd168f487` — validator regressions;
- `bbfe1cb0b79f83bd2d334a2a987149ba5b1ed9eb` — evidence renderer;
- `35340e6d8852f5f540b0dbe3ad3c1704d6d4438f` — validation JSON;
- `dffcfd2c172a23edc20087f206ded7ddef22c593` — visual evidence;
- `0938e1a907d37ae33a0dcce4dffc4d7481515f4f` — audit report;
- `702163c3880638d501158577d94f6992b8575c1b` — immutable archive;
- `0a6876829c51e59974588bf2c4a10748e5480376` — active-task completion;
- this handoff commit.

## Scientific boundary and unrun checks

No scientific central value, calibration, stopping-profile closure, C12 identity,
data/MC transfer, uncertainty, ROOT output, or detector-performance result was
recalculated or validated.

The public canonical Cluster E outputs published immediately before this task remain
claim-binding documentation rendered from connector-inspected exact identities, but
they predate the new schema-3 machine-readable commit-binding contract. A future
clean-checkout regeneration should use the corrected producer and validate the
resulting schema-3 bundle before calling that generation independently reproduced.

Repository-wide pytest, ruff, ROOT processing, the complete paper build, link
inventory, and GitHub Actions were not run and are not claimed as passing. No status
checks were attached to the implementation head when last queried.

`SESSION_LOG.md` and the long aggregate ledgers were reviewed. The connector exposes
paged reads but only whole-file replacement; complete append-only bytes were not
safely reconstructable in this run without risking historical provenance. The
immutable archive and this handoff retain the complete append-equivalent record. This
unmet synchronization requirement is explicit and is not reported as completed.

## Next action

Run the corrected producer from a clean checkout whose `HEAD` is the declared base
commit, regenerate all six Cluster E public outputs under schema 3, run both Cluster E
validators and focused tests, and retain exact output hashes. Keep the result limited
to canonical claim/provenance binding; do not strengthen calibration, closure, C12,
or detector-performance claims without their separate scientific acceptance gates.
