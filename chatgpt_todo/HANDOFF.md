# Latest Handoff

## Active atom: byte-exact authoring → committed GitHub content transfer

Protected `main@acd1be85626b5047b434360eb8ce54bea167a139` was inspected after #1208 merged. #1208 exact head `9f9f061c74c2338d88ffc629897910b1a170bf49` passed MC Validation run `31467815511`; the same-descriptor runtime ELF/link co-observation was independently reviewed, marked ready, and squash-merged as `acd1be85626b5047b434360eb8ce54bea167a139`. That software/runtime provenance refinement does not close #1182 or CL-021.

The selected new child is `ARU-REPO-CONTENT-TRANSFER-001`, branch `audit/repository-content-transfer`.

### Why this atom exists

PR #1208 preserved a failed exact head, `965ba13719ce711d47f88941be2e8a471837345e`, whose GitHub source was truncated and contained additional defects even though a separate local authoring copy had passed `py_compile`. Therefore filename/path/intended-edit identity is not sufficient to attribute a local validation result to repository bytes. Exact-head CI caught the problem, but the local evidence itself had been mis-scoped.

### Exact contract

For authoring bytes `A`, intended repository path `p`, post-write/fetched committed bytes `C`, and optional GitHub Contents API file SHA `g`:

- require exact path equality;
- require `len(C)=len(A)`;
- require `SHA256(C)=SHA256(A)`;
- derive `git_blob_sha1(X)=SHA1(b"blob " || ascii(len(X)) || NUL || X)` and require equality for `A` and `C`;
- if `g` is supplied, require `g=git_blob_sha1(C)`;
- require the authoring receipt self-digest to verify.

SHA-256 is the primary content identity. Git blob SHA-1 is retained only to cross-bind the byte string to the Git/GitHub file object. Byte count and both hashes are correlated deterministic descriptions, not independent statistical evidence.

Git's authoritative documentation states that `git hash-object` computes object IDs from content, defaults to blob type, and that `--no-filters` suppresses attribute/EOL transformations. Git object documentation specifies the type/size/NUL header preceding data for the object hash. GitHub's Repository Contents API exposes each file `sha` and the corresponding Git blob URL. Any intentional Git clean/EOL transform is therefore a separate authoring→canonical representation contract rather than silently equivalent under this byte-exact atom.

### Implemented evidence

New code: `tools/audit/repository_content_transfer.py`.

New tests: `tests/test_repository_content_transfer.py`.

Local Python 3.13/Linux/no-RNG execution on the measured authoring files:

`python -m pytest -q tests/test_repository_content_transfer.py` → `9 passed in 0.11 s`.

Hostile controls cover truncation, same-size one-byte corruption, CRLF→LF normalization, wrong repository path, wrong GitHub blob SHA, tampered receipt, binary content, nominal identity, and explicit Git blob object-ID construction. The local environment did not provide `ruff`, so no local ruff PASS is claimed.

The mechanism was self-applied before publication for the two new source files:

- tool: 8927 bytes; SHA-256 `112cf07d252241dd8f705049ec8440a0f0dd0712ae53f53f0a96ae66ab57fd6d`; expected Git blob SHA-1 `2fbc5347ab1c777fdfbb8972221ee693aa9436ae`; branch `fetch_file` reports exactly `2fbc5347ab1c777fdfbb8972221ee693aa9436ae`.
- tests: 4455 bytes; SHA-256 `40de70883cf63ce2038388ac843a54210b0f10be64c8fd8049dab154897af17f`; expected Git blob SHA-1 `e78c1ac7bbb96f029a204d7fd7cf03b06b9eac00`; branch `fetch_file` reports exactly `e78c1ac7bbb96f029a204d7fd7cf03b06b9eac00`.

An attempted pre-hash of the workflow edit is explicitly **not evidence**: its locally constructed Python string collapsed shell backslash-newline continuations, so the expected hash described different bytes. The actual committed workflow blob and exact-head repository CI are authoritative for that file.

### Four sequential AI reviews

- **Scientific software/provenance lead — ACCEPT bounded mechanism / REVISE adoption.** Strongest counter-hypothesis: exact-head CI makes authoring-transfer binding unnecessary. Falsifier: CI can catch a bad commit, but a pre-transfer local check still cannot be attributed to that commit without a byte binding. Residual uncertainty: future write paths must actually invoke this discipline.
- **Adversarial mechanism reviewer — ACCEPT fail-closed byte identity / BLOCK undeclared canonicalization.** CRLF/LF is intentionally non-equivalent here. Git clean filters or canonicalization need their own transformation contract.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK merge pending exact-head CI.** Nine local hostile fixtures pass; curated ruff and full repository pytest must still succeed on the final branch head.
- **Claims/provenance reviewer — ACCEPT evidence-attribution repair / BLOCK physics promotion.** No Geant4 event, beam data, detector response, event weight, B2/B8, PID, timing, calibration, pile-up, ESS, p-value, rate or public detector claim is validated by this atom.

### Repository state

Branch `audit/repository-content-transfer` is based on exact main `acd1be85626b5047b434360eb8ce54bea167a139`.

Commits so far:
- `ddbd56897769bfb1b2cefd0e53a56ccf1a351f33` — provenance tool;
- `c7124781b40a0c703d760cb16bf2b479aacd7860` — hostile tests;
- `b7cf2f103fe10ce64fdf8796ccb0c169a812edbe` — curated ruff/CI inclusion;
- `6dfddbb2f96dfa5dc41e93b35c6c09798dfc178c` — immutable ARU archive;
- `1addcf01d91cda970659561633ed7f571aebe3c7` — active-task transition.

### Next actions

1. Open one focused PR for `ARU-REPO-CONTENT-TRANSFER-001` and run exact-head MC Validation.
2. If ruff/full pytest fail, preserve that head and repair only demonstrated failures; do not reuse local evidence across different bytes.
3. If the exact final head is green and main ancestry remains valid, merge normally.
4. Then return to the higher-level Geant4 provenance graph: loader-search decision or linker-command/static-input provenance are higher-value scientific children. Keep `ARU-REPO-CONTENT-TRANSFER-ADOPTION-001` open until future write workflows consistently bind pre-write authoring bytes to post-write exact blobs or validate only exact committed checkouts.

No production Geant4 campaign, beam ROOT, production-MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.
