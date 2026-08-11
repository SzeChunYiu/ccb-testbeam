# Digitizer hit-order RNG audit (issue #1074)

Status: **FIXED** under RNG schema `hit_keyed_v1`.

Stochastic transport draws are keyed on
`(global_seed, source, run, event, channel, track_id, step_id, stage, schema)`.
Multi-hit events without stable hit identity fail closed. Pure row
permutations of an identified hit multiset reproduce the same ADC under
a fixed seed (electronics noise remains channel-level).
