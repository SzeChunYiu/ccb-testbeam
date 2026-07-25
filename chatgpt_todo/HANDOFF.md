# Latest Handoff — AUD-G4-024 NPY writer contract remediation

## Delivery identity

- **Session stamp:** `2026-07-25T180216Z`
- **Task ID:** `AUD-G4-024`
- **Initial remote `main`:** `a5b108fc8ead2f644c8b362f3a8732ef1d0528fc`
- **Validated implementation/evidence/archive head:**
  `b8f132ddf473c5026f4a5d1236a9ccdb7bb00e59`
- **Destination:** direct GitHub contents-API commits to remote `main`; no
  force-push, history rewrite, task branch, or PR transport.
- **Push-output boundary:** the connector returned successful commit SHAs rather
  than conventional textual `git push` stdout.
- **PR #868:** closed, unmerged, non-mergeable, and untouched.

## Reviewed repository state

Fetched current `main`, recent history and CI status, open PRs, PR #868, merged
Opticks PR #920, repository-local coordination records, the single-stave CMake
configuration, NPY writer, and its RunAction/EventAction/SteppingAction/
StackingAction/TrackingAction consumers.

The execution container could not resolve `github.com`, so a complete clone was
unavailable. Exact source bytes were fetched through the GitHub connector; the
focused standalone C++/Python validation files were reconstructed and executed
locally.

## Confirmed defects

Former writer blob `21ab586666daa978e4befa3b7b3387e808d76495`:

1. copied the NumPy v1.0 header length in native byte order even though the
   format requires a little-endian unsigned short;
2. declared payload dtype `<f4` while writing native float bytes;
3. did not check shape-product overflow;
4. accepted a null payload for a non-empty array;
5. ignored stream open, write, and flush state.

The exact former algorithm returned status `0` while an unwritable target
produced no output file. In the calling path this could allow a successful
`CCB_GPU_PHOTONS` message without a reusable artifact.

Authoritative format reference:
<https://numpy.org/doc/2.0/reference/generated/numpy.lib.format.html>.

## Validated remediation

Commit `e54f1f5d8c3a3175e3bce56e459d461c523e01cc`:

- emits the v1.0 header length explicitly as little-endian bytes;
- emits little-endian float32 bytes on both little- and big-endian hosts;
- requires at least one shape dimension;
- rejects shape-product overflow;
- rejects a null payload for a non-empty array;
- checks output open, write, and flush state and throws before the caller can
  report successful publication.

Corrected header identity:

- Git blob: `0db837e3614eb725571e3863fce3a15855c52f03`
- bytes: `3473`
- SHA-256: `84df93606b6b2e3e5011806c2f2e652b9a2fb8e0c92008e9347c20163cb31b9d`

## Validation

```text
python -m py_compile \
  tests/test_npy_writer_contract.py \
  tools/audit/render_npy_writer_contract_evidence.py

pytest -q tests/test_npy_writer_contract.py
6 passed in 0.36s
```

The compiled C++ helper and NumPy loader validated exact float32 values and
shape, explicit little-endian header bytes, valid empty `(0,4,4)` arrays, and
fail-closed null, overflow, and unwritable-path controls. JSON and SVG parsing
passed. Maximum changed line lengths were 82 characters for C++ and 92 for
Python.

## Files and evidence

Updated:

- `geant4/single_stave/include/NpyWriter.hh`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

Added:

- `tests/test_npy_writer_contract.py`
- `tools/audit/render_npy_writer_contract_evidence.py`
- `docs/validation/npy_writer_contract_validation.json`
- `docs/validation/npy_writer_contract.svg`
- `docs/validation/npy_writer_contract_audit.md`
- `chatgpt_todo/archive/2026-07-25T180216Z_AUD-G4-024_NPY_WRITER_CONTRACT.md`

## Direct-main sequence through archive

- `e54f1f5d8c3a3175e3bce56e459d461c523e01cc` — fail-closed writer
- `09d4409e2b9091718b563b98da186376ce22cad6` — compiled regression
- `b3dfbf5ab5a5710b5ada0e634c1ccfd6324269e8` — initial renderer
- `5e064ca5bca2b1472679cf22071ef375dc3a8d8c` — valid SVG renderer
- `c81ebf5e3ef42440429aae01f6712af491ce013e` — validation JSON
- `1aea4a30415a8fb95dd12d91ed8c30fb07c6e64b` — visual evidence
- `c8f0cbca9033010861c7982c1358d17d3e80c945` — audit report
- `6444cc6693bd3c5183c9f88e4f25adbf24c1cc97` — active completion
- `b8f132ddf473c5026f4a5d1236a9ccdb7bb00e59` — immutable archive

## Scientific boundary and next action

Focused serialization remediation is `VALIDATED`; cumulative GPU optical work
is `PARTIAL`. No Geant4 event, Opticks propagation, hit gathering, optical
yield, calibration, or detector-performance result was produced.

Next, validate `(N,4,4)` vector cardinality against event counters, distinguish
scintillation/Cerenkov/other input-photon creator processes, record GPU-vs-CPU
transport mode in run metadata, fail closed on output-directory creation, retain
per-event content hashes, and complete a preregistered CPU/GPU parity analysis
only after successful GPU hit gather.

## Unrun checks and coordination limitation

Geant4 build/CTest, Opticks A40 execution, real input-photon regeneration,
repository-wide pytest/ruff, broad link checking, and GitHub Actions were not
run. No broad CI success is claimed.

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were read but not replaced. The connector exposes whole-file
replacement while complete shared records are paged/truncated; replacing a
partial reconstruction could erase unrelated append-only provenance. The
immutable archive and this handoff preserve the append-equivalent record.
