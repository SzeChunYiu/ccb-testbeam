# Active Task

- **Task ID:** `ARU-MC-EVENT-WEIGHT-POPULATION-001 / ARU-MC-WEIGHT-CARRIER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T145500Z`
- **Current remote main SHA inspected:** `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe`
- **Just validated/merged:** audit PR `#1170` exact head `e25545883453116d645e1c40738e8e688e6416d3` had two completed `test` check-runs with conclusion `success`; squash merge `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe` puts the source-mode-aware weight-carrier audit on protected `main`.
- **Selected atom:** adapter-independent validity of the *derived* nonnegative event-weight population after a source-specific raw `PrimaryWeight` adapter has produced one analysis weight per final generator-event row.
- **Exact contract:** for nonempty `w_i>=0`, require finite `S1=fsum(w)>0` and finite `S2=fsum(w^2)>0`; define `ESS=(S1/sqrt(S2))^2`, enforce `1<=ESS<=n`, record ESS fraction and `max(w)/S1`. Empty diagnostic populations are allowed only with `measure_defined=false` and null ESS/dominance.
- **Executed falsifier:** `np.sum([1e16,1,1])=1e16` while reversing the same finite multiset gives `1.0000000000000002e16`; `math.fsum` gives `1.0000000000000002e16` in both orders. A nonempty all-zero vector is rejected because the normalized weighted measure has zero denominator.
- **Dominance control:** `[1000,1,1,1]` gives `sum_w=1003`, `sum_w2=1000003`, `ESS=1.006005981982054`, ESS fraction `0.2515014954955135`, maximum-weight fraction `0.9970089730807578`.
- **Implementation branch:** `fix/mc-event-weight-population-contract`; new package primitive `truth/event_weight_population.py`, focused tests, v3 source-aware `MC_WEIGHT_POLICY.md`, and immutable ARU record are committed. A temporary isolated regression of the new module/tests returned `16 passed`; repository CI remains required.
- **Raw carrier remains unresolved:** #880/#1053 still distinguish scalar-event, common-replicated-primary and direct-sampled/unit-weight adapters. This atom deliberately does not choose among them and does not authorize `weights[0]`.
- **Integration target:** active PR `#1169` should consume the new population primitive after a source-authorized adapter, replace NumPy moment reductions and fake `ESS=0`, and serialize `generator_measure_mode`, `raw_weight_adapter_id`, population policy ID and summation method.
- **Claim state:** no real MC population or detector result was regenerated. #1049/#1052/#1164 remain blocking for inference and detector closure; no weighted p-value or detector-performance claim is promoted.
- **Status:** `ACTIVE / IMPLEMENTED_PENDING_PR_CI / BLOCKED_EXTERNAL_FOR_SOURCE_ADAPTER`
