# NLT01 — source-only neutron-late diagnostic lineage falsifier (2026-10-24)

**STATUS: SOURCE_CLASSIFICATION_COUNTEREXAMPLE; scientific release NOT_AUTHORIZED.**
LIVE owning issue post, verified readback:
https://github.com/SzeChunYiu/ccb-testbeam/issues/1091#issuecomment-6379142395

This is distinct from #1091's already-known 10-microsecond neutron transport cut.
On main a61427813344e29047ca9eb9b764182eb29e4c83, native C++ file
geant4/single_stave/src/SteppingAction.cc (Git blob
baf2ad6e0e5b4ce44ad059b70d47aca96b5ead20) implements:

- kind=0: neutron (PDG 2112) step at any time/volume.
- kind=1: any **non-neutron** PDG step in Scintillator whose pre-step t>1000 ns.
- No neutron ancestry, parent, track, process or positive-Edep requirement.

The source comment and SimData.hh call the latter 'neutron-delayed by construction',
which is not an invariant of the code. The RunAction.cc neutron_steps ntuple
contains only event,kind,t_ns,edep_MeV,ke_MeV,in_scint,pdg; track/parent and
transitive causal ancestry cannot be recovered from old rows. Native executable
also allows mu+ primaries; Geant4 G4Decay and the 2025 PDG free muon lifetime
2.1969811 us furnish a physically admissible non-neutron delayed positron route.
The conditional free muon survival exp(-1/2.1969811)=0.634340088417 is NOT a
detector rate or CCB p/d campaign contamination estimate.

The exact #1091 source predicate from this source is preserved as
source/step_diagnostic.inc (manual GitHub excerpt; independently checked excerpt
SHA256 1c1c1c8ad76fe2bd3bf8587c36b5cfc828e36b9a370656be303ee4391cf754de).
The local independent C++ API-mock compiled and executed the verbatim predicate
with nine named hostile/positive controls; four unittest methods passed normally
and under -O; both C++ optimization modes produced identical RESULT.json. This
is NOT a native Geant4/ROOT/DAQ run, real beam or independent human validation.

**Repository packet scope:** this directory is a durable outcome and handoff
only. The full runnable replay.cc, test_replay.py, logs, hashes, receipt and
longer science report are in conversation artifact
ccb_neutron_late_lineage_20261024.zip (SHA256
ac4e768d44a3381e314e8466afbbc09a5efb5864c29b669b8920b6bbfa253379).
**Those uncommitted executable files are not represented as if present here.**

For actual neutron-attributed late deposited energy, version the ntuple, persist
full per-event track/parent/creator ancestry, reconcile late direct neutron steps
(kind0) with descendants (potentially kind1), record deposit positivity and
pre/post-step time, and run native neutron-free mu+ and neutron-capture controls
with frozen G4/geometry/data/executable/config/seed receipts. Only then evaluate
p/d transport sensitivity and finite DAQ-window effects. Do not assume old
ROOT can reconstruct non-recorded genealogy.

No physical detector number, neutron-fraction correction, MC performance or
publication gate is authorized. Protected #977/PR1294, PR1595 and all production
files were not edited. Avoid rediscovering NLT01 as a different source atom.
