# ARU-REPO-CONTENT-TRANSFER-001 — byte-exact authoring→GitHub publication provenance

Status: `ACTIVE / IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_PENDING`

Protected base inspected: `main@acd1be85626b5047b434360eb8ce54bea167a139` after validated PR #1208 merged.

## Atom / parent / scientific meaning

This atom was spawned by PR #1208 exact-head failure `31466409401`: a locally checked authoring copy was not byte-identical to the source actually committed to GitHub. The first committed implementation was truncated and contained additional defects, so local `py_compile` evidence could not be attributed to the repository blob.

Input contract: authoring byte string `A`, intended repository path `p`, and later committed/fetched byte string `C` plus GitHub Contents API blob SHA `g`.

Output contract: a content-transfer receipt that is `PASS` only for byte-exact identity. This is repository/software provenance only; it has no detector measurand, unit, event population, statistical estimator, or physics authority.

## Invariants

Primary content identity:

`h256(A) = SHA256(A)`.

Git blob cross-check for the repository object:

`oid(A) = SHA1(b"blob " || ascii(len(A)) || NUL || A)`.

PASS requires all of:

- exact repository path equality;
- `len(C)=len(A)`;
- `SHA256(C)=SHA256(A)`;
- `oid(C)=oid(A)`;
- when a GitHub Contents API file SHA is supplied, `g=oid(C)`;
- receipt self-digest remains valid.

SHA-256 is the primary content identity; Git blob SHA-1 is retained only to bind the byte string to the Git/GitHub file object. Byte count and the two hashes are correlated descriptions, not independent statistical evidence.

## Competing mechanisms and eliminations

1. Shared filename / intended edit implies identity — **rejected** by #1208 failed exact head.
2. Local tests on an authoring copy imply repository tests — **rejected** unless bytes are explicitly bound.
3. Exact-head CI alone — **survives as repository validation**, but does not retroactively prove that pre-transfer local checks ran on the same bytes.
4. Pre-write receipt + post-write/fetch byte/object comparison — **preferred bounded mechanism**.
5. Silent newline/filter canonicalization — **rejected under this atom**. Any intentional Git clean/EOL transform is a separate declared transformation contract; exact-byte mode fails closed.

Authoritative semantics: Git documents that `git hash-object` computes a blob object ID from file contents and that `--no-filters` hashes bytes without attribute/EOL transformation. Git's object-format documentation states that the object hash includes a type/size header plus the data. GitHub's Repository Contents API exposes each file `sha` and a `git_url` to the corresponding Git blob.

References:
- https://git-scm.com/docs/git-hash-object.html
- https://git-scm.com/docs/user-manual
- https://docs.github.com/en/rest/repos/contents
- https://docs.github.com/en/rest/git/blobs

## Executed discriminating tests

Local Python 3.13, Linux, no RNG:

`python -m pytest -q tests/test_repository_content_transfer.py` -> `9 passed in 0.11 s` on the measured authoring files.

Hostile fixtures:
- truncation;
- same-byte-count one-byte corruption;
- CRLF→LF normalization;
- wrong repository path;
- wrong GitHub blob SHA;
- tampered receipt digest;
- binary byte payload;
- nominal byte-exact transfer;
- explicit Git blob object-ID definition check.

The local environment did not have `ruff` installed, so no local ruff PASS is claimed; curated repository CI is required.

## Self-application to the new implementation

Before publication, measured authoring identities were:

- `tools/audit/repository_content_transfer.py`: 8927 bytes, SHA-256 `112cf07d252241dd8f705049ec8440a0f0dd0712ae53f53f0a96ae66ab57fd6d`, Git blob SHA-1 `2fbc5347ab1c777fdfbb8972221ee693aa9436ae`.
- `tests/test_repository_content_transfer.py`: 4455 bytes, SHA-256 `40de70883cf63ce2038388ac843a54210b0f10be64c8fd8049dab154897af17f`, Git blob SHA-1 `e78c1ac7bbb96f029a204d7fd7cf03b06b9eac00`.

After GitHub publication on branch `audit/repository-content-transfer`, `fetch_file` reported exactly those two Git blob SHAs for the corresponding paths. Thus the implementation and hostile-test source files themselves satisfy the new authoring→Git object transfer cross-check. This does not substitute for exact-head CI execution.

A separate attempted pre-hash of the workflow edit was invalid because Python source-string backslash continuation collapsed the shell continuation lines in the local constructed string. That incorrect expected hash is explicitly discarded rather than treated as evidence. The actual GitHub workflow blob is the source of truth for CI execution.

## Four sequential AI reviews

### (a) scientific software/provenance lead — ACCEPT bounded mechanism / REVISE workflow
Evidence: #1208 failed exact head, exact GitHub blob inspection, new receipt implementation, 9 hostile fixtures. Strongest counter-hypothesis: exact-head CI makes authoring-transfer provenance unnecessary. Falsifier: pre-transfer local checks can still be misattributed even when later CI catches the defect. Residual: adoption by every future write path is procedural, not automatically enforced by this library.

### (b) adversarial mechanism reviewer — ACCEPT fail-closed byte identity / BLOCK canonicalization assumptions
Strongest counter-hypothesis: newline or Git-filter transformations are harmless equivalent representations. Falsifier: CRLF/LF fixture intentionally fails; scientific/source provenance is byte-specific unless a transformation contract is declared. Residual: Git SHA-256 object-format repositories and intentional filters would require an explicit extension.

### (c) independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference
No stochastic model or uncertainty interval is involved. The test matrix discriminates truncation, corruption, path mismatch, receipt mutation and wrong repository object identity. Repository-level ruff/full pytest remain pending for the final PR head.

### (d) claims/provenance reviewer — ACCEPT provenance child / BLOCK all detector promotion
This atom repairs evidence attribution only. It does not validate Geant4, source physics, event weights, detector response, DATA/MC closure, B2/B8, PID, timing, calibration, pile-up, ESS, p-values or public detector claims. #1182 and CL-021 remain gated.

## Child assumptions

- `ARU-REPO-CONTENT-TRANSFER-ADOPTION-001`: future AI/tool write paths must actually generate a pre-write receipt and verify the post-write exact blob, or validate only in exact committed checkout.
- `ARU-REPO-CANONICALIZATION-001`: any intentionally configured Git clean/EOL filter requires a separately versioned authoring→canonical-blob transformation contract.

## Repository actions in this run

- merged validated PR #1208 after exact-head run `31467815511` succeeded;
- created branch `audit/repository-content-transfer` from `main@acd1be85626b5047b434360eb8ce54bea167a139`;
- added the provenance tool, hostile tests, and curated-riff/CI inclusion;
- fresh exact-head PR CI is required before merge.
