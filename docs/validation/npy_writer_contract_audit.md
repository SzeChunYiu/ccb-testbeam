# NPY writer contract audit

- **Task:** `AUD-G4-024`
- **Session:** `2026-07-25T180216Z`
- **Initial remote main:** `a5b108fc8ead2f644c8b362f3a8732ef1d0528fc`
- **Policy:** `NPY_OUTPUT_MUST_BE_LITTLE_ENDIAN_AND_FAIL_CLOSED`
- **Focused result:** `VALIDATED`

## Scope

This unit reviewed the minimal C++ writer used by the optional single-stave
Opticks path to publish per-event `(N,4,4)` float32 input-photon arrays.

The NumPy version-1.0 format requires the two-byte header length to be an
explicit little-endian unsigned short. The array dtype descriptor must also
match the byte order of the emitted payload. Authoritative reference:
<https://numpy.org/doc/2.0/reference/generated/numpy.lib.format.html>.

## Confirmed defects

Former blob `21ab586666daa978e4befa3b7b3387e808d76495`:

1. wrote `header_len` by copying the native in-memory `uint16_t` representation,
   although the file contract says little-endian;
2. declared payload dtype `<f4` while writing native float bytes directly;
3. did not check shape multiplication for overflow;
4. accepted a null data pointer for a non-empty array;
5. did not check stream open, write, or flush state.

The exact former algorithm was compiled and asked to write beneath a missing
parent directory. It returned status `0` while producing no output file. In the
calling path, this could allow a `CCB_GPU_PHOTONS` success message even though
no reusable artifact existed.

## Remediation

Commit `e54f1f5d8c3a3175e3bce56e459d461c523e01cc` makes the writer fail closed:

- shape must contain at least one dimension;
- shape-product overflow is rejected;
- a non-empty array requires a non-null payload;
- version-1.0 header length is emitted explicitly as little-endian bytes;
- float32 payload bytes are converted to little-endian on a big-endian host;
- output open/write/flush failures throw an exception before the caller can
  print a successful photon-publication line.

Corrected source identity:

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

The compiled C++ helper and NumPy reader verified:

- exact `(2,2)` float32 values and dtype `<f4`;
- explicit little-endian header length;
- valid empty `(0,4,4)` arrays;
- controlled rejection of non-empty null payloads;
- controlled rejection of shape-product overflow;
- controlled rejection of an unwritable output target.

The JSON parsed successfully and the SVG parsed as XML. Changed Python lines
were at most 92 characters; the corrected C++ header was at most 82 characters.

## Evidence

- `tests/test_npy_writer_contract.py`
- `tools/audit/render_npy_writer_contract_evidence.py`
- `docs/validation/npy_writer_contract_validation.json`
- `docs/validation/npy_writer_contract.svg`

## Scientific boundary

This validates serialization and fail-closed artifact handling only. It does
not validate Opticks propagation, GPU hit gathering, creator-process accounting,
optical yield, wavelength/time/path distributions, sensor response, calibration,
or detector performance.

A complete GPU validation still requires immutable per-event input arrays,
run metadata that distinguishes GPU capture from CPU optical transport, exact
input/output hashes, successful Opticks event-save/hit gather, and a
preregistered CPU/GPU parity analysis with uncertainty and falsifier plots.

## Unrun checks

- full Geant4 build and CTest;
- Opticks execution on the A40 environment;
- real input-photon artifact regeneration;
- repository-wide pytest and ruff;
- GitHub Actions and repository-wide link inventory.
