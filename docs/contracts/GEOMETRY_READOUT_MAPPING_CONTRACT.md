# Geometry / readout mapping contract (v1) — resolves P0 A-004

**Problem (A-004, CONFIRMED):** two incompatible layer→stave mappings coexist.
Most analyses merge MC layers **in pairs** into `B2/B4/B6/B8`; the ΔE–E
supervisor script maps layers **one-to-one**. No quantitative MC/data result is
admissible until a single mapping is fixed **from deployed-ROOT geometry
coordinates / copy numbers**, not chosen by whichever map best fits the stopping
fractions.

## The single source of truth

The mapping is defined by the **deployed compact ROOT geometry** (the file used
to generate the production MC, e.g. `krakow_109_8-38deg_4-71deg.root`), via each
`Sci_bar` `LayerID` copy number, its centre depth coordinate, and its
metrology/DAQ readout label. Arm convention (confirmed elsewhere in the audit):
`Sci_bar_LayerID1 == 1 -> B arm`, `== 2 -> A arm`; steering requests **8 B bars,
4 A bars**.

## Falsification procedure (do NOT fit-to-stopping)

Produce one row per simulated bar: `copy_number, LayerID, centre_depth_cm,
thickness_cm, arm, physical_readout_label, readout_status(instrumented|passive),
data_channel`. Then test the competing mappings **against geometry coordinates +
readout drawings**, never against which map best reproduces B8 fraction:

1. one simulated layer per data stave (one-to-one);
2. two adjacent simulated bars merged per instrumented channel (pair-merge);
3. instrumented/passive alternating bars;
4. any hardware-specific map from survey/DAQ documentation.

The surviving mapping is the contract. Until then, **every** ΔE–E / MV0 / MV2 /
MV3 / PID number that depends on `B2/B4/B6/B8` carries mapping systematic and is
`BLOCKED_COMPUTE` for final admissibility.

## GeometryContract artifact (required, template shipped)

A machine-readable `geometry_contract.json` must record: ROOT geometry sha256;
builder source commit + config + macro; Geant4/ROOT/VGM versions; full volume
hierarchy (copy number, shape params, material/density, global transform,
bounding box); per readout layer (arm, depth, physical label, readout status,
data channel); representative ray-traced material budget to each stave; ROOT AND
post-VGM Geant4 overlap checks; three orthogonal renderings with scale bars.

A field-complete template with `BLOCKED_COMPUTE` placeholders is at
`docs/contracts/geometry_contract.template.json`.

## Why "zero overlaps" is not fidelity

ROOT `CheckOverlaps(1e-4 cm)` returned zero overlaps on the compact geometry, but
overlap-freedom is geometric consistency, **not** detector fidelity: a sparse
geometry can be overlap-free yet omit most passive material. Fidelity requires a
**material-budget** validation — ray-trace the exact path distribution and
compare areal density component-by-component (this is the `#844` stopping work,
`BLOCKED_COMPUTE`).

## Status

| item | status | blocker |
|---|---|---|
| Publish mapping contract + procedure | **DONE** (this file) | — |
| `geometry_contract.json` template | **DONE** (template) | — |
| Populate from deployed ROOT (VGM/ROOT inspection) | **BLOCKED_COMPUTE** | ROOT + LUNARC |
| Falsify competing mappings on coordinates | **BLOCKED_COMPUTE** | deployed ROOT |
| Material-budget ray trace | **BLOCKED_COMPUTE** | Geant4 + LUNARC |
