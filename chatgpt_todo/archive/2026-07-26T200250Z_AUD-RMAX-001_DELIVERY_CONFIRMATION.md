# AUD-RMAX-001 Delivery Confirmation

- Initial remote main: `9c576de392c4f81aaea369b4612e16841eeef730`.
- Concurrent merge: `3daa2c96bfb024f00e559bbe1285dbe5fe13126c` (`#942`) landed during finalization and overwrote `scripts/check_rmax_formula.py` with an evidence-free PASS path.
- The concurrent merge was inspected. Its Rmax change exited zero but still called 3.05 MHz “measured (occupancy)” and did not read the canonical WIKI or ledger.
- Remediation commit `fbe893160dab05707806ec839920bf1a084ec746` was reapplied on top of the merge without force-push or history rewrite.
- Remote `main` was re-read after the write and showed `fbe893160dab05707806ec839920bf1a084ec746` as head.
- Current checker blob is `188716b5fb3982b32ba90dcb8364922caaf5ac21`, matching the locally validated byte-exact source.
- The remediated checker intentionally returns nonzero on the current stale WIKI statement; no green Thesis QA result is claimed.
- PR #868 remained closed, unmerged, and non-mergeable.
