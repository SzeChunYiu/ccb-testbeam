# ADR-880: Raw PrimaryWeight carrier contract

## Status

**PARTIAL / BLOCKED for legacy importance-weight derivation (#1053)**

## Context

A branch named `PrimaryWeight` does not define the physical event measure.
Scalar-event, common-replicated-primary, and direct-sampling/unit-weight worlds
are distinct. Arbitrary `weights[0]` is unauthorized.

## Decision

1. `adapt_raw_primary_weight` requires `generator_measure_mode` and a matching
   `weight_adapter_id` class.
2. Supported adapters: `scalar_event_weight_v1`,
   `common_replicated_primary_weight_v1`, `direct_sampling_unit_weight_v1`.
3. Direct-sampling mode rejects non-unit raw payloads.
4. Common-replicated mode collapses only after proving sibling equality.
5. Legacy proposal→target importance derivation remains **BLOCKED** under #1053;
   this ADR does not invent a transfer measure.

## Consequences

Weighted event-stave products must bind a generator measure mode. Population
ESS contracts (`nonnegative_event_measure_v2`) remain downstream of a successful
adapter.
