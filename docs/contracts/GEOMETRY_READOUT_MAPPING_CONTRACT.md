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

## Versioned code-level policy (GEO-001 fix)

The *physical* bar→stave assignment (which real copy number is `B2`, etc.) is
still `BLOCKED_COMPUTE` below. To stop code modules from silently diverging in
the meantime, the **code-level** layer-merge policy is fixed in exactly one
place and versioned:

| constant | location | value |
|---|---|---|
| `READOUT_CONTRACT_VERSION` | `src/ccb_mc_validation/truth/geometry.py` | `2026.0-truth-geometry` |
| `DEFAULT_LAYER_MERGE_POLICY` | `src/ccb_mc_validation/truth/geometry.py` | `pair_merge` |
| `DEFAULT_B_STAVES` | `src/ccb_mc_validation/truth/geometry.py` | `{"B2":0,"B4":2,"B6":4,"B8":6}` |

`GeometryRegistry` (`truth/geometry.py`) reads **this** contract: with
`NB_LAYERS == 8` B layers and 4 instrumented staves, `pair_merge` maps adjacent
MC layers `{0,1}->B2, {2,3}->B4, {4,5}->B6, {6,7}->B8`. If a caller passes a
configuration whose layer/stave counts are inconsistent with the declared
policy, the builder **fails closed** (`ConfigurationError`) rather than guessing
a one-to-one map (the historical GEO-001 defect).

**Every other module MUST obtain its layer→stave mapping from
`GeometryRegistry` / `build_layer_to_stave`** (or the constants above), not
re-derive one. Coordination note (out of scope for the truth/geometry PR):
`scripts/mc01_trigger_split_truth.py` already pair-merges via
`f"B{(lay_int+1)*2}"`; `studies/` MV3 owns its own copy and must be migrated to
import `GeometryRegistry` in a follow-up by the studies/ owner. Bumping the
contract version requires updating this table and the constant together.

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
| Versioned code-level policy enforced in `geometry.py` (GEO-001) | **DONE** | — |
| `geometry_contract.json` template | **DONE** (template) | — |
| Populate from deployed ROOT (VGM/ROOT inspection) | **BLOCKED_COMPUTE** | ROOT + LUNARC |
| Falsify competing mappings on coordinates | **BLOCKED_COMPUTE** | deployed ROOT |
| Material-budget ray trace | **BLOCKED_COMPUTE** | Geant4 + LUNARC |
| Migrate `studies/` MV3 to `GeometryRegistry` | TODO | studies/ owner |
