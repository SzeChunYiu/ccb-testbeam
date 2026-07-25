# Active Task

- **Task ID:** AUD-G4-024
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T180216Z
- **Initial remote main SHA:** `a5b108fc8ead2f644c8b362f3a8732ef1d0528fc`
- **Scope:** review and remediate the minimal NumPy v1.0 writer used by the
  optional single-stave Opticks input-photon path.
- **Confirmed defects:** former code wrote the header length and float payload
  in native byte order while declaring NumPy little-endian data; did not check
  shape multiplication, non-empty null payloads, or stream failures; and could
  return success without creating an artifact.
- **Validated changes:** explicit little-endian header and float32 payload,
  shape and pointer validation, open/write/flush failure checks, compiled C++
  regression, NumPy load verification, JSON evidence, SVG evidence, and audit
  report.
- **Validation:** focused pytest returned `6 passed in 0.36s`; py_compile,
  valid/empty array loading, little-endian header inspection, null/overflow/
  unwritable controls, JSON parse, SVG XML parse, and line-length checks passed.
- **Negative control:** exact former algorithm returned status `0` while an
  unwritable target produced no file.
- **Unrun checks:** Geant4 build/CTest, Opticks A40 execution, real photon
  artifact regeneration, repository-wide pytest/ruff, link inventory, and
  GitHub Actions.
- **Scientific boundary:** serialization and artifact-failure handling only;
  no GPU transport, hit gathering, optical-yield, calibration, or detector
  performance result was validated.
- **Focused status:** VALIDATED.
- **Cumulative status:** PARTIAL until GPU capture/transport provenance,
  creator-process accounting, immutable artifacts, hit gathering, and CPU/GPU
  parity with uncertainty are validated.
