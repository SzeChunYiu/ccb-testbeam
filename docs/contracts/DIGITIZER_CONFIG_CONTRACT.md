# Digitizer config & stage-graph contract

Schema: `digitizer-stage-graph/1` (Lane 08 Wave B).

Resolves audit issues #1075, #1076, #1077, #1080.

## Booleans (#1076)

Response-defining switches (currently `apply_birks`) use **strict** parsing — never Python truthiness.

Accepted: native `True`/`False`; integers `0`/`1`; strings
`true|false|yes|no|on|off|0|1` (case-insensitive).

Rejected: typos (`flase`), empty string, `None`, arbitrary nonempty strings,
floats, containers.

## Time constants (#1075)

`tau_rise_ns > 0` and `tau_decay_ns > 0`, both finite. Invalid values **fail
closed**; they are not clamped to `1e-12 ns` (that would substitute a different
model). Explicit zero-rise analytic limits, if ever needed, require a separately
named API.

## Scalar domains (#1080)

| parameter | production / control domain |
|---|---|
| `n_samples` | integer `>= 1` |
| `sample_spacing_ns` | `> 0` (zero/negative = INVALID_INPUT) |
| `transport_sigma_ns` | `>= 0` (`0` = VALID_CONTROL) |
| `noise_adc_rms` | `>= 0` (`0` = VALID_CONTROL) |
| `gain_adc_per_mev` | `>= 0` (`0` = VALID_CONTROL null gain) |
| `adc_bits` | integer in `[1, 63]` |
| `adc_ceiling` | integer `>= 1` |
| `pedestal_adc` | finite float |

Validation runs in `DigitizerPipeline.__post_init__` / `ElectronicsConfig.__post_init__`
before event 0.

## Stage graph (#1077)

Per-hit `stages` may only contain, in dependency order subsequence:

`birks → scintillation → transport → sampling`

- **`sampling` is mandatory** for the ADC observation model. If omitted from
  the request it is inserted into the **effective** graph and recorded under
  `mandatory_inserted`.
- **`electronics` is not a per-hit stage.** Final gain / pedestal / noise /
  quantisation is always applied **once** after hit summation
  (`mandatory_final = daq_observation_once`). Listing `electronics` in `stages`
  is rejected so ablation claims cannot pretend the final operator was toggled.
- Unknown and duplicate stages are rejected.
- Hidden `integrate_samples` fallbacks after the stage loop are removed.

Provenance: `DigitizerPipeline.resolved_config()` and each `run()` result expose
`stage_graph` with `requested_stages`, `effective_stages`, `mandatory_inserted`,
and `mandatory_final`.
