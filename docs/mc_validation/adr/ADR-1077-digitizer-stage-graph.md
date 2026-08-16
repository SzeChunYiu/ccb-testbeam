# ADR-1077: Requested digitizer stage graph equals effective graph

## Status

**ACCEPTED (fail-closed resolver)**

## Context

Omitting `sampling` still triggered a hidden `integrate_samples` fallback, and
an `electronics` stage entry did not control final gain/pedestal/noise/quantize.

## Decision

1. Resolve requested stages before event 0 via `resolve_stage_graph`.
2. Reject unknown, duplicate, reordered, empty, and deprecated `electronics`
   requests.
3. Require `sampling` for ADC waveform production; refuse hidden fallbacks.
4. Always record mandatory final node `daq_observation` in the resolved graph.
5. Persist `stage_graph` + `digitizer_config_sha256` on every waveform product.

## Consequences

Ablation claims must archive the resolved graph. Legacy callers that relied on
hidden sampling must request `sampling` explicitly (default stage list already
includes it).
