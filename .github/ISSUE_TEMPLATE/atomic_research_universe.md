---
name: Atomic Research Universe
about: One independently falsifiable scientific/software atom using the mandatory recursive mechanism framework
title: "[P?][DOMAIN][ATOM] "
labels: ""
assignees: ""
---

<!-- ccb-audit-id: ASSIGN-STABLE-ID -->

## Evidence state and severity

- Severity: `P0 | P1 | P2`
- Evidence state: `CONFIRMED_BUG | CONFIRMED_GAP | CANDIDATE | NEGATIVE_RESULT | VALIDATED_METHOD`
- Audited commit:

## Atomic-universe contract card

- **Atom:**
- **Input X / population:**
- **Transformation or mechanism T:**
- **Output/measurand Y:**
- **Units / truth type:**
- **Parameters Θ:**
- **Nuisance variables N:**
- **Parent atoms/issues:**
- **Child atoms/issues:**
- **Authorising scope:**

Atomic question:

> Given `X`, under contract `C`, which surviving mechanism `H_k(Θ,N)` maps `X→Y`, and what experiment can falsify it against the other surviving mechanisms?

## Exact evidence inspected

List commit/path/line, report page/table/figure, input hash, configuration, literature DOI/authoritative source, or executable output. Distinguish source-derived fact from inference.

## Competing mechanism / hypothesis ledger

| ID | mechanism / mathematical description | parameters / nuisances | evidence for | evidence against | state |
|---|---|---|---|---|---|
| H1 | | | | | `SURVIVING` |
| H2 | | | | | `SURVIVING` |

States: `SURVIVING`, `EQUIVALENT`, `ELIMINATED`, `BLOCKED_EXTERNAL`, `NOT_IDENTIFIABLE`.

## Equivalence collapse

Which candidate descriptions are algebraic reparameterizations, aliases, or observationally equivalent under current observables? Record the canonical surviving equivalence classes so duplicate work is not spawned.

## Equation / invariant ledger

Define every symbol, unit, domain, approximation and limiting case used. Include relevant conservation laws, geometry/hardware constraints, event-key/data-contract invariants, probability bounds, weight identities, or covariance relations.

## Eliminated hypotheses

For every eliminated hypothesis, state the exact reason and evidence pointer. Do not delete negative results.

## Surviving hypotheses and unresolved dependencies

List only material survivors. Identify shared/degenerate nuisance parameters explicitly.

## Four role-separated review passes

These are sequential AI lenses, not independent human reviewers.

### 1. Domain / physics lead
- Evidence inspected:
- Strongest surviving counter-hypothesis:
- Falsifier:
- Residual uncertainty:
- Vote: `ACCEPT | REVISE | BLOCK | REJECT`

### 2. Adversarial mechanism reviewer
- Evidence inspected:
- Strongest surviving counter-hypothesis:
- Falsifier:
- Residual uncertainty:
- Vote:

### 3. Validation / statistics reviewer
- Evidence inspected:
- Strongest surviving counter-hypothesis:
- Falsifier:
- Residual uncertainty:
- Vote:

### 4. Claims / provenance reviewer
- Evidence inspected:
- Strongest surviving counter-hypothesis:
- Falsifier:
- Residual uncertainty:
- Vote:

## Discriminating experiment matrix

| discriminant | H1 prediction | H2 prediction | held fixed | required data/MC | decision rule |
|---|---|---|---|---|---|
| | | | | | |

Prefer the cheapest high-information falsifier. State sample size / MC convergence / stopping rule where applicable.

## Implementation plan

1.
2.
3.

Keep implementation narrower than the scientific parent problem.

## Positive and adversarial controls

- Positive control:
- Negative/fault injection 1:
- Negative/fault injection 2:
- Boundary/limiting case:
- Held-out/domain-shift case:

## Weight, uncertainty and dependence contract

- Independent sampling/resampling unit:
- Data/MC/event weights and semantics:
- `sum(w)`, `sum(w²)`, ESS diagnostics if applicable:
- Statistical uncertainty:
- Systematic/nuisance set:
- Shared correlations with parent/child atoms:
- Multiple-model/model-selection treatment:

## Cross-atom compatibility gate

Check micro→meso→event→study→claim composition:

- parameter ownership;
- unit/coordinate convention;
- causal order/no downstream tuning leakage;
- shared nuisance correlations;
- held-out assembled-chain closure;
- counterfactual wrong-combination rejection.

## Acceptance criteria

- [ ]
- [ ]

## Rejection / fail-closed criteria

- [ ] Missing required evidence exits nonzero or marks result non-authorising.
- [ ] A declared negative control fails the proposed model/method when it should.
- [ ] The issue cannot be closed if a material surviving alternative remains untested without an explicit `BLOCKED_EXTERNAL` dependency.

## Required provenance

- exact code commit;
- config/schema/detector-response digests;
- real-data/MC paths, bytes and SHA-256;
- RNG seeds / Geant4 and data-library versions;
- literature DOI/source type;
- commands/tests executed;
- output artifact hashes.

## Claim / wiki / report consequences

List every affected claim ID, README/WIKI section, report, figure, table, config and cached artifact. State what must be gated, superseded or regenerated.

## Recursive child-atom check

After the preferred solution survives, list every new assumption it introduces. Spawn a child issue only for assumptions with an independent falsifier/implementation boundary.

## AI handoff

- Smallest next executable action:
- Exact files likely to change:
- Exact test/experiment to run first:
- External blocker, if any:
- Parent issue unlocked when complete:
