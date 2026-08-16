# ARU-MC01-EVENT-STAVE-PUBLICATION-CHILD

Status: ACTIVE / PARTIAL
Parent: ARU-MC01-EVENT-STAVE-001, issues #1052/#1164, PR #1169

During the adversarial pass, the first producer implementation wrote the NPZ and manifest through two independent `os.replace` commits. That is not a transaction: a process failure after product replacement but before manifest replacement can leave the previous manifest naming bytes that no longer match it.

The rejected mechanism is therefore `replace(product) -> replace(manifest)`. Reordering the two independent replacements is equivalent; either ordering has a mixed-generation crash window.

PR #1169 now publishes each H3 product as a new immutable generation directory. The producer computes a generation identity from the source-content SHA-256, tree, coincidence window, weighting mode, population limit, exact executing source hashes for the script/constants/event-builder/event-stave/PDG/trigger modules, and Python/NumPy/Uproot versions. A SHA-256 of that canonical identity names `out/generations/<generation_id>/`.

Publication sequence:

`private staging directory -> write+fsync NPZ -> bind NPZ bytes/SHA256 in manifest -> write+fsync manifest -> fsync staging -> rename staging directory to previously absent generation path under flock -> fsync generations root`.

There is deliberately no mutable `latest` alias in this diagnostic producer. Reusing an existing generation ID fails closed rather than overwriting prior bytes. Any exception before the directory rename removes staging and leaves no visible generation.

New negative controls verify that product+manifest appear under one generation, manifest digest reproduces the exact product bytes, a second identical publication is rejected without modifying the first, and an injected `np.savez_compressed` failure leaves no visible generation directory.

Reviewer update: detector/Geant4 vote unchanged; adversarial software vote becomes **ACCEPT immutable-generation publication pending exact-head CI**; validation vote remains **ACCEPT deterministic transaction falsifiers / BLOCK real artifact**; claims/provenance vote remains **BLOCK promotion** because publication integrity does not supply H4/H5 detector response.

Only the workflow associated with the final PR head/current base may authorize merge. No real MC artifact was generated here.
