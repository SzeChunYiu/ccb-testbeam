# ADR-WAVE-D-LANE10: Torch failure must not inherit foreign method identities

**Status:** accepted
**Date:** 2026-08-12
**Lane:** Wave D Lane 10
**Issues:** #1126

## Context

P04p/P04q previously caught Torch failures and copied MLP/GBT probabilities into
columns still labelled `cnn_1d` / `wavegate_resnet`. That silently falsifies
model-family multiplicity and winner identity.

## Decision

1. On Torch failure, raise fail-closed instead of aliasing another method.
2. When NN methods are not requested, withhold cnn/resnet probabilities as NaN
   with an explicit `NOT_REQUESTED` status rather than copying MLP/GBT outputs.
3. No physics parameters were invented.

## Consequences

Missing Torch environments surface as hard failures for NN method claims, which
is the correct provenance behaviour.
