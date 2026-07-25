# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T021422Z`
- **Task:** `AUD-MC-001`
- **Unit:** strict event-aligned MC weight-vector and ESS validation
- **Initial remote `main`:** `f01b16fba39bcd21bb57a10638d36dcfe521b01f`
- **Validated implementation/evidence head:** `f97063a81a2dc7c9b903e99261cdea1d50729b5b`
- **Immutable archive:** `ae2fe82c04358f3ef983b50ff39a150e73f8af26`
- **Complete delivery handoff:** `cb932d9266d108be7a3cdea6de9be3a7eef0ea77` was confirmed as remote `main` head; this update records confirmation metadata only
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** **COMPLETE** for the focused software/provenance unit

## Start-of-run review

Authenticated GitHub reads inspected repository metadata and permissions, current `main`,
recent history, open issues and pull requests, attached status checks, PR #868, the
repository-local coordination records, the MC weight contract, the retained A-003
production ESS report, the former weight auditor, and its existing tests.

Initial facts:

- remote `main`: `f01b16fba39bcd21bb57a10638d36dcfe521b01f`;
- no status checks were attached to that head;
- PR #868 was closed, unmerged, and non-mergeable and was not modified;
- issue #880 asks that MC event weights be used correctly;
- the retained Krakow report records 2,000,000 primaries, ESS 694,524, ESS fraction
  0.347, weight range 0.126–15.325, and p50/p99 0.652/14.919.

## Confirmed defects

The exact former auditor was Git blob
`9b2375b98fd76784ce3fb961e4dcdbf169f7495e`, 2,414 bytes, SHA-256
`16977d2ef277dd3cdeb3dea9047e09db84a3a6881d1d2bf278fff72d698bd7ed`.

Exact-source synthetic negative controls demonstrated that it:

1. silently removed a NaN and returned `OK`, changing `n=3` to `n=2` and reporting
   ESS 1.8;
2. silently selected `PrimaryWeight` when `EventWeight` was also present;
3. flattened a 2×2 array and returned `OK`, `n=4`;
4. did not bind the weight count to `tree.num_entries`;
5. omitted exact input byte size and SHA-256;
6. overwrote the ROOT input with JSON and exited zero when `--out` aliased the input.

The destructive alias control changed input SHA-256 from
`747f014492eac371c58a294bc2a97c41a9cbf380db921276c91e1e26ce39020e` to
`352c05a0940c3c8ac708589fb34a34fb8ce091f728b2218d8c1f61e747f36874`.

## Correction delivered

`tools/audit/audit_mc_weight_usage.py` is now version `2.0.0` under policy:

`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`

An accepting audit now requires exactly one recognized branch, a one-dimensional vector,
one finite nonnegative weight per tree entry, at least one positive weight, and positive
finite sufficient statistics. It records exact input size and SHA-256, entry/weight/zero/
positive counts, `sum_w`, `sum_w2`, ESS, ESS fraction, tail diagnostics, and
`PYTHON_MATH_FSUM_BINARY64`. Input/output aliases are rejected and JSON is published
atomically through a same-directory temporary file.

`docs/contracts/MC_WEIGHT_POLICY.md` is now v2 and explicitly distinguishes a validated
weight vector from demonstrated downstream use of those weights.

Added:

- `tests/test_audit_mc_weight_usage_strict.py`;
- `tools/audit/render_mc_weight_vector_validation_evidence.py`;
- `docs/validation/mc_weight_vector_validation.json`;
- `docs/validation/mc_weight_vector_validation.svg`;
- `docs/validation/mc_weight_vector_validation_audit.md`;
- `chatgpt_todo/archive/2026-07-25T021422Z_AUD-MC-001_WEIGHT_VECTOR_VALIDATION.md`.

Updated `tools/audit/audit_mc_weight_usage.py`, the MC weight policy,
`chatgpt_todo/ACTIVE_TASK.md`, and this handoff.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mc_weight_usage.py \
  tests/test_audit_mc_weight_usage_strict.py \
  tools/audit/render_mc_weight_vector_validation_evidence.py

pytest -q tests/test_audit_mc_weight_usage_strict.py

8 passed in 0.04s
```

Coverage includes valid ESS and exact provenance, nonfinite and negative weights,
all-zero weights, ambiguous branches, non-vector shape, entry-count mismatch, atomic JSON
publication, retained compatibility fields, and destructive-alias prevention.

Runtime was Python 3.13.5, NumPy 2.3.5, and pytest 9.0.2. JSON parsing passed, SVG XML
parsing passed, and changed Python lines were no longer than 100 characters. Re-fetched
committed blobs matched validated bytes:

- auditor blob `d304aff96aa5321be5cff6d26f981657145d4e56`;
- test blob `4217beb2cb0bd0a8df39fa5169541be590e587a2`;
- renderer blob `ffef2dbdb9bbde05f674abe5bc0f46abf2155b21`;
- policy blob `c24e7f1a529b7d709fd0b71db105164e84a4d576`.

No production ROOT runtime, exact fs10 input rerun, repository-wide pytest, ruff, Python
3.11 CI, ROOT processing, Geant4 execution, weighted downstream rerun, or data/MC closure
is claimed.

## Direct-main commit sequence

- `88aefe06566e8f70aa01ca5d7a8b58f9ac182065` — claim task;
- `dfbbf1237311df72f876ab5ca491dfda51630abf` — strict validator;
- `73351ddd411c6f64ec2c26700932c8febdec4ccd` — policy v2;
- `d9c5fae6fcb3567c3be1ae125ffff26563ad356e` — focused tests;
- `481388b464acf62d5a60a39fb3b840a76d7a5676` — evidence renderer;
- `0370618d71e669bafc58f8826bcc48557c2323e4` — validation JSON;
- `e8698364327f51771a12e6bfc7597530cbe73b92` — SVG evidence;
- `472db185a3851244db2407a8343ca6dac8bb42e3` — validation audit;
- `f97063a81a2dc7c9b903e99261cdea1d50729b5b` — task completion;
- `ae2fe82c04358f3ef983b50ff39a150e73f8af26` — immutable archive;
- `cb932d9266d108be7a3cdea6de9be3a7eef0ea77` — complete handoff, confirmed on remote `main`.

The connector returned successful direct-main commit SHAs instead of conventional textual
`git push` stdout. Post-write history confirmed the complete handoff and the focused
sequence on remote `main` without an interleaved concurrent commit.

## Scientific boundary

This is synthetic software/provenance validation. The retained production ESS was not
independently regenerated because the exact ROOT bytes were unavailable. A valid weight
vector does not prove that downstream histograms, fits, metrics, or models consume it.
Negative weights are rejected for this source-specific nonnegative cross-section policy;
signed-weight generators require a separate estimator and interpretation contract.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but
not replaced because the connector provides whole-file replacement rather than byte-safe
append/patch semantics for shared long-lived files. Replacing a partial or concurrently
changing reconstruction could erase unrelated provenance. The immutable archive and this
handoff preserve the complete append-equivalent record. Aggregate synchronization remains
explicitly unmet.

## Next action

Run v2.0.0 on the exact production Krakow ROOT file and retain its content-addressed JSON.
Then audit and rerun every `MC_WEIGHT_NOT_DECLARED` downstream analysis with weighted and
unweighted comparisons, weight-tail stability, uncertainty propagation, and data/MC
closure before restoring any affected physics claim.
