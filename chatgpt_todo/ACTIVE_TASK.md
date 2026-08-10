# Active Task

- **Task ID:** `ARU-RAW-DIGEST-SAME-STREAM-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T094900Z`
- **Initial remote main SHA:** `4fda4b5013a712a329646127140d8a52d322af92`
- **Parent issue:** `#993`.
- **Child issue:** `#1155`.
- **Reviewed PR:** `#1154` at head `e7ab22893ffad0266acb7c4243ebb748a1334ec7`.
- **Branch:** `audit/raw-digest-same-stream-review`.
- **Selected atom:** `raw ROOT pathname -> one opened byte stream -> digest + byte count + source identity -> provenance row`.
- **Verified defect:** PR #1154 repairs the historical three-digest/33-count truncation, but its helper still performs `exists -> hash(path) -> stat(path)` as separate observations, so a mutable/replaced source can produce a mixed-version provenance row.
- **Invariant:** for one opened stream `B`, require `sha256 = H(B)` and `bytes = |B|`; source identity must come from the same descriptor/snapshot.
- **Review action:** submitted independent PR review `RP-RAW-DIGEST-001`; opened #1155 with one-open helper design and mutation/path-replacement hostile controls.
- **CI state:** both checks on PR #1154 exact head are green, but the PR was tested against an older main. Current main has advanced to `4fda4b50...`; fresh current-base CI is required before merge.
- **Execution boundary:** no beam ROOT files were available, so no real digest manifest or detector quantity was regenerated. Synthetic filesystem tests are sufficient for the #1155 software/provenance atom.
- **Expert votes:** DAQ/provenance `REVISE`; adversarial filesystem `BLOCK mixed-version row authority`; validation `ACCEPT deterministic child design / require mutation tests`; claims/provenance `ACCEPT child / BLOCK scientific promotion`.
- **Scientific boundary:** #993 stays open; CL-001 remains GATED; no 8x16<->8x18 lineage is established.
- **Next acceptance gate:** implement #1155 without conflicting with active #1154 work, then require exact-head/current-base CI and preserve #1154 complete-list/missing-run semantics.
- **Status:** `REVIEWED / CHILD_ATOM_OPEN / IMPLEMENTATION_REQUIRED / NO_SCIENTIFIC_CLAIM_CHANGE`
