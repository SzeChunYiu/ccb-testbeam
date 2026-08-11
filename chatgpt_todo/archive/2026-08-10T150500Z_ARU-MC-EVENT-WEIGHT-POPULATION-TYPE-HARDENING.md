# ARU-MC-EVENT-WEIGHT-POPULATION-001 supplement — coercive dtype adversary

During the adversarial diff pass on PR #1171, the first implementation's input gate was found to be too permissive even though its core probability-measure equations were correct.

The first version rejected only an array whose NumPy dtype was exactly boolean and then used `astype(float64)`. That admitted two representation-only mechanisms that are not valid real analysis weights:

1. a complex array such as `[1+2j]` could be cast to real with the imaginary component discarded (NumPy emits a warning rather than a contract exception);
2. textual numeric tokens such as `["1", "2"]` could be silently parsed into floating-point weights.

These mechanisms are observationally distinct from a source adapter that has already produced a real numeric event-weight vector. They therefore must not be treated as equivalent valid representations at this layer.

The current head now requires the pre-cast NumPy dtype kind to be one of real signed-integer, unsigned-integer, or floating-point (`i`, `u`, `f`) before binary64 conversion. Boolean, complex, text, object and nested/non-1D representations fail closed. Focused negative controls were added for complex and textual arrays.

This correction does not choose the raw `PrimaryWeight` carrier and does not change the scientific weight measure. It tightens only the post-adapter software contract. Exact-head GitHub CI after this correction remains the merge authority.

A second adversarial documentation pass also noticed that v3 of `MC_WEIGHT_POLICY.md` had inadvertently dropped the prior high-weight-tail reporting requirement while adding `max(w)/sum(w)`. The requirement has been restored: claim-bearing reports still need the 99th percentile, maximum and maximum-to-mean ratio, with the percentile convention named when it can affect a threshold. The new package primitive is intentionally the core probability-measure/ESS gate rather than a complete tail-report implementation.

Role disposition after these corrections: source/physics lead **ACCEPT local gate / REVISE source-adapter integration**; adversarial reviewer **ACCEPT after type hardening and reporting restoration**; statistics reviewer **ACCEPT numerical contract / BLOCK inference**; claims/provenance reviewer **ACCEPT local repository repair / BLOCK physics promotion**.
