# Active Task

- **Task ID:** `ARU-S00-PUBLICATION-GENERATION-PRIMITIVE-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T070000Z`
- **Initial remote main SHA:** `5cb0b9426dc2f9e1b58a33fcb36c2e0c3eaa8f0a`
- **Validated merge before atom selection:** PR #1143 -> `5cb0b9426dc2f9e1b58a33fcb36c2e0c3eaa8f0a`; exact-head MC Validation CI run 910 was `success`.
- **Parent issue:** `#1110`
- **Branch:** `fix/s00-publication-generation-primitive`
- **Selected atom:** `validated staging generation -> immutable generation -> atomic authority pointer -> downstream logical artifact resolution`.
- **Contract:** a failed publication must leave the previous authority pointer byte-identical; a successful publication retains old immutable generations and changes authority only by atomic `CURRENT.json` replacement.
- **Implemented:** reusable `s00_publication.py` primitive with strict IDs/paths, required-artifact validation, pre-move model-identity serialization, same-filesystem generation move, publisher locking, fsync, atomic pointer replacement, typed pointer parsing and logical resolver.
- **Negative controls:** injected pointer-commit failure, missing artifact, existing generation ID, path traversal, wrong staging root, malformed pointer, missing authoritative artifact, and non-serializable model identity.
- **Expert votes:** filesystem/reconstruction `ACCEPT primitive / BLOCK integration`; adversarial/concurrency `ACCEPT primitive / residual downstream-bypass risk`; validation `ACCEPT deterministic design / pending exact-head CI`; claims/provenance `BLOCK #1110 closure until producer and consumers use pointer authority`.
- **Scientific boundary:** no beam ROOT or Geant4 execution; no S00 count or detector-performance quantity changed.
- **Status:** `ACTIVE / IMPLEMENTED_PRIMITIVE_PENDING_CI_AND_INTEGRATION`
