# 01 — Setup and detector

## Facility and beam
- **Facility:** CCB = Centrum Cyklotronowe Bronowice (Cyclotron Centre Bronowice), Kraków.
- **Beam:** protons, kinetic energy **T_p = 190 MeV**.
- **Beam current:** most runs at **20 nA**; runs **46 and 47 at 2 nA** (low-current reference,
  used throughout for the current-scaling / pile-up cross-checks).
- **Target:** deuterated polyethylene **CD₂** near a vacuum window. The p+CD₂ reactions emit
  protons and deuterons (among others) into the detector.

## Apparatus (corrected 2026-07-03 — experiment-owner setup facts; diagram source: `drawing_ccb_setup`)
- **Two independent HRD scintillator range stacks** (Stack A, Stack B) at **conjugate angles**,
  each ≈ **100 cm** from the CD₂ target, **each behind its own trigger scintillators**; the
  **TPC sits in front of Stack A only**. (An earlier version of this section described a single
  serial chain target → triggers → TPC → stacks; that was wrong.)
- The two arms measure **different particles**: pd-elastic scattering sends the proton into one
  arm and the kinematically-correlated deuteron into the other. An A·B coincidence tags a
  correlated **pair** sharing the event T0 — never the same particle twice.
- Each stack is a stack of scintillator **staves** (~1 m long), read out at **one end** by a
  **wavelength-shifting (WLS) fibre**; assumed WLS propagation speed **v_WLS = 17.0 cm/ns**.
- A stack ranges out charged particles → acts as a **ΔE–E / range telescope**: amplitude
  vector + hit multiplicity + penetration depth + pulse shape + inter-stave timing together
  discriminate particle topology.

## Triggers and samples (2026-07-03, experiment-owner setup facts)
- **Sample I** = **A AND B trigger coincidence**. MC mimic: a charged particle entering the
  first A layer and the first B layer within **15 ns**.
- **Sample II** = **B trigger only** (A ignored).
- **In MC** the definitions are **inclusive**: Sample I is a **subset** of Sample II (boolean
  flags `sample_I`/`sample_II` in `src/ccb_mc_validation/io/root_truth.py`; the legacy
  `sample_label` column was exclusive — "II" meant II minus I).
- **In data** Samples I and II are **disjoint run sets** recorded with different trigger
  configurations. Every MC-vs-data sample comparison must state this subset-vs-disjoint
  asymmetry.

## Channels actually used
- **B-stack:** staves **B2, B4, B6, B8** (the positive-pulse blocks 2/4/6/8; deeper number =
  deeper into the stack). Centre-to-centre spacing taken as **d = 4 cm** (positions x = 0, 4,
  8, 12 cm) in the newer report; ~2 cm in the older note — a discrepancy to resolve (S00).
- **A-stack:** only **A1 and A3** are usable (A2/A4 channels have no selected pulses; odd
  duplicate readout channels dropped).

## Waveform / digitiser
- **18 samples per pulse**, nominal **sample spacing Δt_samp = 10 ns**.
- Signal in **ADC counts**; baseline (pedestal) subtracted per pulse (see
  [03_pulse_reconstruction.md](03_pulse_reconstruction.md)).

## Energy scale (interpretation only — NOT per-event truth)
Fitted component scales:
- Deuteron-like: median ≈ 15.8 MeV (16-84%: 7.2-34.7 MeV) [sample-level characterization from analytic range model (2-parameter power-law fit to 4 NIST PSTAR CSDA points); NOT per-event measurement. Dominant systematics (geometry, Birks quenching, relative gains) unquantified.].
- Proton-like (penetrating): median ≈ 69.3 MeV (16-84%: 53.3-90.2 MeV) [same caveat as above -- sample-level characterization, not per-event measurement].

Energy is reconstructed via a **2-parameter power-law range model** R(T)=aT^p
(a=1.913×10⁻³, p=1.797) anchored to 4 CSDA points — explicitly *not* a replacement for
PSTAR/GEANT4. The dominant uncertainties are systematic (geometry, Birks quenching, relative
gains). See [09_open_questions.md](09_open_questions.md).
