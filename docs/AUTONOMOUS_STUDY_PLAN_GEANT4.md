# Autonomous Study Plan — GEANT4 Simulation as Truth / Validation Source

Updated: 2026-06-11. Trigger: GEANT4 1M-event sim now available
(`geant4/results/sim_summary.json`: 836,534 truth protons + 314,646 truth deuterons,
7 layers, per-layer p_frac/d_frac and mean_edep).

## Goal
Compare GEANT4 simulation with real HRD signals to understand the test beam better —
energy, PID, timing, pile-up, and detector response — using simulation as a
**validation and (after tuning) truth** source.

## Non-negotiable rules
1. Do NOT assume simulation is perfect.
2. FIRST validate sim-vs-data distributions (G4-01).
3. Use simulation truth for energy/PID/timing ONLY after detector-response tuning (G4-04).
4. Before any sim-trained ML touches data, quantify the domain gap (G4-07).
5. Tickets are atomic and live in `tn-ticket project:testbeam`.

## Dependency / gating order
```
G4-01 (waveform validation)  ─┐
                              ├─> G4-02 energy calib ─┐
G4-04 (response tuning) ──────┘                       ├─> G4-08 sim->data transfer
G4-03 PID ─────────────────────────────────────────┐ │
G4-05 timing ──────────────────────────────────────┤ │
G4-06 pile-up ─────────────────────────────────────┘ │
G4-07 domain gap ─────────────────────────────────────┘ (gates G4-08)
```

## Batch (filed as atomic tickets)
- **G4-01** Sim-vs-data waveform distribution comparison (B2/B4/B6/B8) — the gate.
- **G4-02** Energy calibration vs GEANT4 truth deposited energy.
- **G4-03** Proton/deuteron PID: GEANT4 truth vs dE-E and waveform/ML PID.
- **G4-04** Detector-response tuning (Birks, material, geometry, light yield, ADC, smearing).
- **G4-05** Timing validation vs GEANT4 true hit time.
- **G4-06** Pile-up validation via simulated overlays / multi-hit truth.
- **G4-07** Domain-gap quantification before sim-trained ML on data.
- **G4-08** Sim-to-data transfer: train on GEANT4, validate on data control regions.

Each ticket specifies: scientific question, simulation inputs, real-data comparison target,
traditional baseline, ML method, metrics, systematic checks, success/failure criteria, deliverables.

## Worker protocol addition
Every report MUST be human-readable at high-school level: state the motivation, the process,
and discuss every atomic step clearly. A reader with no detector-physics background should
follow why the study matters, what was done, and what the numbers mean.
