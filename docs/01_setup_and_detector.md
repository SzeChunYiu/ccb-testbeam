# 01 — Setup and detector

## Facility and beam
- **Facility:** CCB = Centrum Cyklotronowe Bronowice (Cyclotron Centre Bronowice), Kraków.
- **Beam:** protons, kinetic energy **T_p = 190 MeV**.
- **Beam current:** most runs at **20 nA**; runs **46 and 47 at 2 nA** (low-current reference,
  used throughout for the current-scaling / pile-up cross-checks).
- **Target:** deuterated polyethylene **CD₂** near a vacuum window. The p+CD₂ reactions emit
  protons and deuterons (among others) into the detector.

## Apparatus (Fig. 1 in the notes)
- Target region → **trigger scintillators** → **TPC** → **two HRD scintillator range stacks**
  (Stack A, Stack B), each ≈ **100 cm** from the target.
- Each stack is a stack of scintillator **staves** (~1 m long), read out at **one end** by a
  **wavelength-shifting (WLS) fibre**; assumed WLS propagation speed **v_WLS = 17.0 cm/ns**.
- A stack ranges out charged particles → acts as a **ΔE–E / range telescope**: amplitude
  vector + hit multiplicity + penetration depth + pulse shape + inter-stave timing together
  discriminate particle topology.

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
- Deuteron-like: median ≈ 15.8 MeV (16–84%: 7.2–34.7 MeV).
- Proton-like (penetrating): median ≈ 69.3 MeV (16–84%: 53.3–90.2 MeV).

Energy is reconstructed via a **2-parameter power-law range model** R(T)=aT^p
(a=1.913×10⁻³, p=1.797) anchored to 4 CSDA points — explicitly *not* a replacement for
PSTAR/GEANT4. The dominant uncertainties are systematic (geometry, Birks quenching, relative
gains). See [09_open_questions.md](09_open_questions.md).
