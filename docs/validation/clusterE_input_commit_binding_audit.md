# Cluster E input/base-commit provenance binding audit

- **Task:** `AUD-REP-002`
- **Session stamp:** `2026-07-26T150519Z`
- **Initial remote main:** `f30ff1100592e06396598ebf6975afa88e84444f`
- **Policy:** `INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS`
- **Scope:** software provenance authorization for the Cluster E canonical front door.

## Confirmed defects

The former producer read each path once for parsing and SHA-256, then separately ran
`git hash-object --no-filters -- <path>` against the live path. A path replacement
between those operations could pair parsed bytes A with a Git blob identifier for
bytes B.

The producer also checked only that the requested `base_commit` equalled `HEAD`.
It did not require the retained worktree bytes to equal `base_commit:path`. A dirty,
semantically valid ledger or source JSON could therefore be published while the
provenance claimed a clean base commit.

The previous provenance schema stored syntactically valid blob and SHA-256 values,
but did not record or verify a commit-tree blob identity for each input. The
validator could not distinguish a base-commit input from dirty or replacement bytes.

## Remediation

The producer now:

1. reads every UTF-8 input exactly once;
2. calculates the Git blob SHA-1 directly from those retained bytes using the Git
   object header `blob <length>\0`;
3. resolves the expected blob with `git rev-parse <base_commit>:<path>`;
4. fails closed with `INPUT_NOT_AT_BASE_COMMIT:<path>` unless the identities are
   exactly equal;
5. records `commit`, `commit_blob_digest`, `commit_match=true`, the authorization
   policy, SHA-256, byte count, and snapshot policy for every input;
6. publishes provenance and metrics under schema version 3.

Validator v2.1.0 requires the same machine-readable contract. Legacy provenance
that only contains a path hash and SHA-256 is no longer sufficient for validation.

## Deterministic controls

The committed control bytes have Git blob SHA-1
`f80f50c325b2c99bb467c4758a4c23535d133162`. Adding one uncommitted line changes
the blob identity to `6a11afca199b1afb42510881f24df961e085ddf9`; the corrected producer rejects it.

A replacement-after-snapshot regression changes the path after the retained byte
read but before the commit-tree lookup. The recorded digest remains the digest of
the retained bytes, not the later path contents.

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

The evidence renderer returned `VALIDATED` with zero findings. The JSON parsed,
the SVG parsed as XML, and changed Python lines are at most 100 characters.

SHA-256 identities:

- producer: `230df0122c6a56cdf6a6d99870cf16e254da7467580d630363b2eeb2f681fee8`;
- producer tests: `d11ade4f7b0de3596860f3af30c7b3df84ca28ef43147b23f7c840293ce47cf6`;
- validator: `42e9c6a676d215aa8f546bcd32bf9bb0617398eafcced2cdf76cd928a8530aa5`;
- validator tests: `85def154c01f8f77673c6ed20c6fb714d15f3dff60c0a07f3c12e49d9e47003c`;
- renderer: `102f508d09ea91399a8e783acda59e6f15d79a94a3677968b3ab8d2afd22116f`;
- validation JSON: `8477f037c289aad968d64ee323655cd07f113dc809228e8b2fc4de3b4002c4c5`;
- SVG: `fe3431a1c650eec3f79bf9efad4333ceabd824d74f6698b1fad694856a016639`.

## Acceptance boundary

This is a validated software/provenance remediation. It does not recalculate or
validate the CL-013 calibration proxy, CL-021 stopping-profile diagnostic, CL-022
truth-MC morphology rate, data/MC closure, C12 identity, or detector performance.

The public canonical Cluster E outputs published immediately before this task remain
claim-binding documentation generated from connector-inspected exact identities.
They predate the new schema-3 machine-readable commit-binding contract. A future
full-checkout regeneration should run the corrected producer from a clean immutable
base commit and validate the resulting schema-3 bundle before treating that run as
an independently reproduced production generation.

Repository-wide pytest, ruff, the complete paper build, ROOT processing, link
inventory, and GitHub Actions were not run and are not claimed as passing.
