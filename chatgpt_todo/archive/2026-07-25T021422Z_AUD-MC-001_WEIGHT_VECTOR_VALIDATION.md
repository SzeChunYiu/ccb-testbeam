# Immutable handoff — AUD-MC-001 strict MC weight-vector validation

## Identity

- UTC session stamp: `2026-07-25T021422Z`
- Initial remote `main`: `f01b16fba39bcd21bb57a10638d36dcfe521b01f`
- Focused implementation/evidence head before archive: `f97063a81a2dc7c9b903e99261cdea1d50729b5b`
- Owner: scheduled scientific-review session
- Acceptance: `COMPLETE` for the focused software/provenance unit

## Start-of-run review

Authenticated GitHub reads confirmed push/admin permission, default branch `main`, initial
head `f01b16fba39bcd21bb57a10638d36dcfe521b01f`, no attached status checks, open issues
#885/#879/#887/#880, current open PR inventory, and PR #868 closed, unmerged, and
non-mergeable. The run reviewed `chatgpt_todo/ACTIVE_TASK.md`, `BACKLOG.md`,
`HANDOFF.md`, the beginning and append constraints of `SESSION_LOG.md`, the MC weight
contract, the retained A-003 ESS report, the former auditor, and its existing tests.

## Repository and measured facts

- Issue #880 requests correct use of MC event weights.
- `docs/contracts/MC_WEIGHT_POLICY.md` states that the Krakow source samples `theta_cm`
  uniformly and stores the lab-angle cross-section factor in `PrimaryWeight`.
- The retained production report records 2,000,000 primaries, sum of weights 6,445,162,
  ESS 694,524, ESS fraction 0.347, min/max 0.126/15.325, and p50/p99 0.652/14.919.
- Exact former auditor blob: `9b2375b98fd76784ce3fb961e4dcdbf169f7495e`.
- Exact former bytes: 2,414; SHA-256
  `16977d2ef277dd3cdeb3dea9047e09db84a3a6881d1d2bf278fff72d698bd7ed`.

## Confirmed defects and negative controls

The former algorithm flattened arbitrary arrays, silently dropped nonfinite weights,
selected the first recognized branch when several existed, did not check weight count
against tree entries, omitted exact input-byte provenance, and wrote directly to `--out`.

Exact-source synthetic negative controls measured:

- `[1, NaN, 2]` returned `OK`, changed `n` from 3 to 2, and reported ESS 1.8;
- simultaneous `PrimaryWeight` and `EventWeight` returned `OK` after silently selecting
  `PrimaryWeight`;
- a 2×2 array was flattened and returned `OK`, `n=4`;
- `--out` equal to the ROOT input overwrote the input with JSON and exited zero.

The alias control changed SHA-256 from
`747f014492eac371c58a294bc2a97c41a9cbf380db921276c91e1e26ce39020e` to
`352c05a0940c3c8ac708589fb34a34fb8ce091f728b2218d8c1f61e747f36874`.

## Correction

`tools/audit/audit_mc_weight_usage.py` is now version 2.0.0 under policy:

`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`

The accepting path requires exactly one recognized branch, a one-dimensional vector, one
weight per tree entry, finite nonnegative values, at least one positive weight, and positive
finite sufficient statistics. It records input size/SHA-256, entry/weight/zero/positive
counts, sum of weights, sum of squared weights, ESS, tail diagnostics, and
`PYTHON_MATH_FSUM_BINARY64`. It rejects input/output aliases and publishes JSON atomically.

`docs/contracts/MC_WEIGHT_POLICY.md` is now v2 and distinguishes weight-vector validity
from proof of downstream weight consumption.

## Files and exact validated identities

- `tools/audit/audit_mc_weight_usage.py`
  - blob `d304aff96aa5321be5cff6d26f981657145d4e56`
  - 8,434 bytes
  - SHA-256 `789d344eb08bc1cbdaf1db789bd34b1c4e9f3f8da86c562890d5cf9c5ce114b0`
- `tests/test_audit_mc_weight_usage_strict.py`
  - blob `4217beb2cb0bd0a8df39fa5169541be590e587a2`
  - 5,296 bytes
  - SHA-256 `e3b413ac5e2a8689eda80a13fe86428cf3bc3af9dac1c13cc99f9b6fa778675a`
- `tools/audit/render_mc_weight_vector_validation_evidence.py`
  - blob `ffef2dbdb9bbde05f674abe5bc0f46abf2155b21`
  - 2,228 bytes
  - SHA-256 `614153a7b49662fa04d377967b66350bc7ece7cc8c3dd29e0d22ae6fd39ebbd7`
- `docs/contracts/MC_WEIGHT_POLICY.md`
  - blob `c24e7f1a529b7d709fd0b71db105164e84a4d576`
  - 3,224 bytes
  - SHA-256 `a241a932d8bdd7d7d1633f5474e8de3942614e25d8fe00d79ea629ef7e87b647`
- validation JSON blob `ee18c4231d3688f9374674b4905138928fffb4bb`
- validation SVG blob `f5c5c19c815ff0c439b85d1e4f428f2e0d259748`
- validation audit blob `3cf001dd7cc8ff489c7a804bd5aa53f8d663153a`

## Commands and results

```text
python -m py_compile \
  tools/audit/audit_mc_weight_usage.py \
  tests/test_audit_mc_weight_usage_strict.py \
  tools/audit/render_mc_weight_vector_validation_evidence.py

pytest -q tests/test_audit_mc_weight_usage_strict.py

8 passed in 0.04s
```

Runtime: Python 3.13.5, NumPy 2.3.5, pytest 9.0.2. JSON parsing passed, SVG XML parsing
passed, and changed Python lines are at most 100 characters. The committed script, test,
renderer, and contract blobs were re-fetched and match the validated identities.

## Direct-main commits before archive

- `88aefe06566e8f70aa01ca5d7a8b58f9ac182065` — claim task;
- `dfbbf1237311df72f876ab5ca491dfda51630abf` — strict validator;
- `73351ddd411c6f64ec2c26700932c8febdec4ccd` — policy v2;
- `d9c5fae6fcb3567c3be1ae125ffff26563ad356e` — focused tests;
- `481388b464acf62d5a60a39fb3b840a76d7a5676` — renderer;
- `0370618d71e669bafc58f8826bcc48557c2323e4` — validation JSON;
- `e8698364327f51771a12e6bfc7597530cbe73b92` — visual evidence;
- `472db185a3851244db2407a8343ca6dac8bb42e3` — audit report;
- `f97063a81a2dc7c9b903e99261cdea1d50729b5b` — task completion.

The GitHub connector returned successful direct-main commit SHAs rather than conventional
textual `git push` stdout. Recent-history inspection showed no interleaved concurrent commit
inside the focused sequence.

## Scientific boundary

This is synthetic software/provenance validation. No production ROOT bytes were available,
so the retained 2,000,000-primary ESS was not independently regenerated. A valid weight
vector does not prove that downstream histograms, fits, metrics, or models consume it.
No generator regeneration, weighted before/after physics plots, uncertainty propagation,
ROOT runtime, data/MC closure, or repository-wide CI is claimed.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but
not replaced. The connector exposes whole-file replacement rather than byte-safe append or
patch operations for these shared long-lived records; replacing a partial or concurrently
changing reconstruction could erase unrelated provenance. This immutable archive and the
latest handoff retain the complete append-equivalent record. Aggregate synchronization
remains explicitly unmet.

## Next action

Run v2.0.0 on the exact production Krakow ROOT file, retain the new content-addressed JSON,
then audit and rerun each `MC_WEIGHT_NOT_DECLARED` downstream analysis with weighted and
unweighted comparisons, weight-tail stability, uncertainty propagation, and data/MC closure.
