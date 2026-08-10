# Active Task

- **Task ID:** `ARU-MC-WEIGHT-CARRIER-001 / WKS-NULL-CLUSTER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T143900Z`
- **Current remote main SHA inspected:** `d088b5a886e0c8891d7926af7015193db7a503b8`
- **Selected atom:** raw generator `PrimaryWeight` representation -> exactly one validated event-measure weight per generator-event statistical unit.
- **Trigger for selection:** active PR `#1169` implements the #1052/#1164 H3 event/stave truth product but defines event weight as the first element of a per-event `PrimaryWeight` payload and has a positive regression accepting `[2.5, 9.0] -> 2.5`.
- **Repository contradiction:** `docs/contracts/MC_WEIGHT_POLICY.md` / `audit_mc_weight_usage.py` describe one scalar weight per tree entry, while legacy `mc01_trigger_split_truth.py` describes a variable-length per-primary payload. The issue-880 audits explicitly say first-primary carrier correctness was not established.
- **New source evidence:** content-addressed S17a schema `reports/0000000004.1.g4truth/truth_schema.csv` records `PrimaryWeight` as `std::vector<double>` / jagged. The companion no-`CSFile` 100k smoke ROOT is SHA-256 `74387a04571cf92724fb97974b1214579996ed33cff0b128e6a96eb21fc3164a`. It is schema evidence only, not production weight-law validation.
- **Exact falsifier:** for event-1 raw payload `[2.5,9.0]`, event-2 weight 1 and observables `{0,1}`, first-element collapse gives `F_w(0)=0.7142857143`; permuting only the primary-row order to `[9.0,2.5]` gives `F_w(0)=0.9`. Arbitrary first-element collapse is therefore representation-order dependent unless sibling equality is source-proven.
- **Surviving adapter worlds:** source-proven scalar event weight; source-proven common replicated per-primary weight with exact sibling equality/permutation invariance; source-proven direct-sampled unit-weight mode. Aggregate or arbitrary first-primary rules remain rejected/unidentified without generator derivation.
- **Repository actions:** reopened `#880`; cross-linked `#1053` and `#1164`; submitted blocking/corrective reviews on `#1169`; opened audit PR `#1170` at head `3768cf85e2e8431a3d60c9ab7bfae4b63029a7b7` preserving the full ARU and S17a schema supplement.
- **CI state:** PR `#1169` exact-head run `31397051913` succeeded but does not falsify the semantic concern; PR `#1170` exact-head run `31398696604` is still in progress and therefore not merge-authorising yet.
- **Claim state:** no weighted MC physics number is promoted or automatically invalidated. `#1053` generator-measure mode, `#880` carrier definition, `#1164` event-unit propagation and `#1049` null calibration remain open. CL-021 remains open and no detector-performance value changed.
- **Next discriminating work:** on immutable representative production MC files, measure raw `PrimaryWeight` branch form/cardinality, sibling equality, primary identity/order and generator mode; serialize `generator_measure_mode` + `raw_weight_adapter_id`. If bytes remain unavailable, implement only adapter-independent post-collapse gates: positive total mass, stable `math.fsum` `sum(w)`/`sum(w^2)`, ESS, and fail-closed provenance.
- **Status:** `ACTIVE / BLOCKED_EXTERNAL_FOR_SOURCE_CARRIER / PARTIAL`
