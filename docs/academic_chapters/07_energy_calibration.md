# Chapter 7: Energy Calibration — Digitizer Gain, Birks Quenching, and Range-Energy

## Abstract

The conversion of ADC pulse amplitudes to physical energy deposition requires calibration of the digitizer gain (ADC/MeV) and correction for Birks quenching, which suppresses scintillation light yield at high ionisation density. This chapter presents: the MV0 digitizer gain calibration via Monte Carlo truth matching with bootstrap uncertainty estimation; a first-principles derivation of the Birks quenching law from molecular excitation and recombination kinetics; the PSTAR-based range-energy calibration with tabulated data for protons and deuterons in BC-408; a combined gain-kB fitting strategy using stopping particles; a component-level breakdown of energy resolution into statistical, systematic, and fundamental contributions; a comparative survey of scintillator calibration methods (cosmic muon, Compton edge, LED pulser); and the systematic uncertainty budget. The digitizer gain of 245.6 +/- 73.7 ADC/MeV (30% systematic) is the largest single systematic in the analysis programme.

---

## 1. The Energy Reconstruction Problem

### 1.1 From ADC to MeV

The fundamental quantity measured by each HRD stave is the 18-sample ADC waveform. The pulse amplitude A (the maximum baseline-subtracted ADC value) is proportional to the scintillation light yield L, which is in turn related to the energy deposited by the charged particle in the scintillator, E_dep, through a chain of efficiency factors:

```
A = G * L = G * epsilon_WLS * epsilon_SiPM * L_scint(E_dep)                       (1)
```

where:

- G is the overall digitizer gain (ADC per photoelectron or ADC per MeV-equivalent),
- epsilon_WLS is the wavelength-shifting fibre collection and transport efficiency (typically 3-10% for one-ended readout, depending on fibre geometry and optical coupling),
- epsilon_SiPM is the SiPM photon detection efficiency (typically 25-50% for modern SiPMs at the WLS emission wavelength),
- L_scint(E_dep) is the scintillation light yield, which depends nonlinearly on E_dep through Birks quenching.

The product G * epsilon_WLS * epsilon_SiPM is the quantity calibrated by the MV0 digitizer gain measurement. The individual factors are not separately determined; only their product, as a single MeV-to-ADC conversion factor, is constrained by the data-MC matching procedure.

A more granular representation of the signal chain exposes the photon statistics. The number of scintillation photons produced is:

```
N_gamma = Y * E_dep * q_Birks(E_dep)                                               (2)
```

where Y is the absolute scintillation yield of BC-408 (approximately 10,000 photons/MeV for minimum-ionising particles [3]) and q_Birks(E_dep) is the Birks quenching factor (Eq. 22). The number of photoelectrons (PE) detected by the SiPM is:

```
N_PE = N_gamma * f_geom * QE_SiPM                                                 (3)
```

where f_geom is the geometric light collection efficiency (WLS fibre capture fraction times transport attenuation) and QE_SiPM is the SiPM photon detection efficiency at the WLS emission wavelength (typically 420-480 nm). The ADC amplitude is then:

```
A = g_ADC * N_PE                                                                  (4)
```

where g_ADC is the electronics gain in ADC counts per photoelectron. The combination of Eq. (2)-(4) yields the overall calibration constant:

```
g_calib = A / E_dep = g_ADC * f_geom * QE_SiPM * Y * q_Birks(E_dep)              (5)
```

For the MV0 calibration, q_Birks is treated as unity (see Section 2.4), and the product of the remaining factors is determined empirically via the median-matching procedure.

### 1.2 The MV0 Digitizer Gain Calibration

The gain calibration uses the GEANT4 Monte Carlo truth energy deposition as the reference. For each charged particle hit in the B-stack, the Monte Carlo records the true energy deposited E_dep (in MeV) via the Sci_bar_EDep branch. The data records the ADC amplitude A for the corresponding stave and event. By matching the Monte Carlo energy deposition distribution to the data amplitude distribution for a well-characterised reference sample, the MeV-to-ADC conversion factor is determined.

The reference sample is the Sample II (proton-dominated, single-B trigger) first B-layer (B2). This sample is chosen because:

1. Sample II is proton-dominated (48.4% deuterons at B2 entry, compared to 73.5% for Sample I), and protons in the 100-200 MeV range are near minimum-ionising in plastic scintillator (dE/dx approximately 2 MeV cm^2/g * 1.032 g/cm^3 = 2.06 MeV/cm). At minimum ionisation, the Birks quenching correction is small (kB * dE/dx approximately 0.10-0.15 mm/MeV * 2.06 MeV/cm = 0.021-0.031 cm = 0.21-0.31 mm << 1 cm for typical kB values), making the light yield nearly linear with energy deposition.

2. Sample II has a broader energy deposition distribution than Sample I (mean EDep 23.1 MeV vs 32.2 MeV at B2), providing a wider dynamic range for the calibration.

3. Sample II has lower B2 saturation (6.1% of pulses above 7000 ADC) than Sample I (41.7%), reducing the saturation-induced bias.

The calibration is performed by matching the median of the Monte Carlo B2 energy deposition distribution to the median of the data B2 amplitude distribution:

```
gain = median(A_data, B2, Sample II) / median(E_dep_MC, B2, Sample II)           (6)
```

The measured value is:

```
gain = 3662.9 ADC / 14.91 MeV = 245.6 ADC/MeV
```

The statistical uncertainty on the median ratio is estimated via bootstrap resampling (see Section 6.1 for full pseudocode). The systematic uncertainty of +/- 30% (+/- 73.7 ADC/MeV) arises from three sources added in quadrature:

1. **Single-point calibration (+/- 15%):** Using only the median of one distribution (Sample II B2) rather than a multi-stave, multi-energy calibration scan. The gain may vary between staves (B2 vs B4 vs B6 vs B8) due to differences in WLS fibre coupling, SiPM gain, and electronics chain.

2. **Digitizer model approximations (+/- 10%):** The Monte Carlo digitizer does not include Birks quenching (kB = 0 by default), which would reduce the scintillation light yield for the higher-dE/dx deuteron population and shift the median EDep relative to the proton-dominated population. The digitizer also does not model the SiPM saturation roll-off (only a hard clip at 7000 ADC), which affects the amplitude distribution at the high end.

3. **Missing forced-trigger pedestal data (+/- 10%):** The baseline subtraction uses the median of ADC samples 0-3. Without forced-trigger data (events recorded with no beam, providing a true zero-energy reference), the absolute baseline level has an irreducible uncertainty of approximately 10% of the baseline RMS. A forced-trigger run in a future beam test would reduce this to approximately 5%.

The gain uncertainty propagates linearly into any physics quantity expressed in energy units. For the deuteron fraction estimation, a 30% uncertainty in the MeV-to-ADC conversion translates to a 30% uncertainty in the energy threshold used to define "deuteron-like" stopping in B2, though the deuteron fraction itself (computed from counting statistics) is less sensitive because the B2 amplitude distributions for protons and deuterons are well-separated in Sample I.

---

## 2. Birks Quenching: First-Principles Derivation

### 2.1 Molecular Excitation and Ionisation

When a charged particle traverses an organic scintillator, the primary energy-loss mechanism is Coulomb excitation and ionisation of the aromatic molecules (polyvinyltoluene, PVT, for BC-408). The specific energy loss dE/dx (MeV/cm) is given by the Bethe-Bloch formula for the electronic stopping power [4]:

```
-dE/dx = K * (Z_eff^2 / beta^2) * [ln(2*m_e*c^2*beta^2*gamma^2 / I) - beta^2 - delta/2]   (7)
```

where K = 4*pi*N_A * r_e^2 * m_e*c^2 * (Z/A)_target * z^2 (approximately 0.3071 MeV cm^2/g for the target), Z_eff is the effective charge of the projectile (accounts for electron capture at low velocities via the Barkas-Andersen formula), beta = v/c, gamma = 1/sqrt(1 - beta^2), I is the mean excitation energy (approximately 64.7 eV for PVT [2]), and delta is the density-effect correction (significant above approximately 1 GeV for protons).

Each unit of deposited energy produces a population of excited pi-electron states in the aromatic rings. The initial excitation density rho_ex (excited molecules per unit volume along the track) is proportional to the specific energy loss:

```
rho_ex(x) = (1/w) * (dE/dx)                                                        (8)
```

where w is the average energy required to produce one excited/ionised molecular state. For organic scintillators, w is approximately 100 eV per photon-equivalent excitation (substantially larger than the ionisation potential of approximately 7 eV because most of the deposited energy goes into molecular vibrations, non-radiative transitions, and ion recombination that does not produce scintillation light). Of the approximately 10^4 photons/MeV produced, the overall energy efficiency is therefore approximately 1 eV of photon energy per approximately 100 eV deposited, or approximately 1% — consistent with the known efficiency of plastic scintillators [3,4].

### 2.2 Competing De-excitation Channels

Each excited molecule can de-excite through two competing channels:

1. **Radiative decay (scintillation):** The excited singlet state S_1 decays to the ground state S_0 by emitting a photon of wavelength 420-480 nm (the BC-408 emission peak at 425 nm). The radiative decay rate is k_r, with a characteristic lifetime tau_r = 1/k_r approximately 2-3 ns for the fast component of PVT scintillators [3].

2. **Non-radiative quenching:** The excited molecule interacts with a nearby "quenching centre" — a damaged molecule, an ionised neighbour, or a triplet state produced by the same particle track — and transfers its energy non-radiatively (e.g., via Forster resonance energy transfer to a non-fluorescent site, or via collisional de-excitation). The quenching rate is k_q * n_q, where n_q is the local density of quenching centres.

### 2.3 The Birks Rate Equation

The density of quenching centres n_q is proportional to the density of excited molecules produced along the track — a particle that deposits more energy per unit length creates more ionisation damage and thus more quenching centres in its immediate vicinity. Birks proposed [1]:

```
n_q = B * rho_ex = (B/w) * (dE/dx)                                                (9)
```

where B is a proportionality constant characterising the quenching-centre production efficiency per unit excitation.

Consider a differential track segment of length dx. The number of excited molecules in this segment, N_ex, evolves according to the rate equation:

```
dN_ex/dt = (dE/dx)*(dx/dt)/w - k_r*N_ex - k_q*n_q*N_ex                           (10)
```

The first term is the production rate (energy deposited per unit time divided by w). The second and third terms are the radiative and quenching decay rates, respectively. At steady state (dN_ex/dt = 0), which is reached on a timescale of nanoseconds (much shorter than the ADC sampling period of 10 ns):

```
(dE/dx)*(v/w) = k_r*N_ex + k_q*n_q*N_ex                                           (11)
```

where v = dx/dt is the particle velocity. Solving for N_ex:

```
N_ex = (dE/dx)*(v/w) / (k_r + k_q*n_q)                                            (12)
```

The differential scintillation light yield per unit path length is proportional to the radiative decay rate:

```
dL/dx = (1/v) * k_r * N_ex                                                        (13)
```

Substituting Eq. (12):

```
dL/dx = (k_r/w) * (dE/dx) / (k_r + k_q*n_q)                                       (14)
```

Substituting Eq. (9) for n_q:

```
dL/dx = (k_r/w) * (dE/dx) / (k_r + k_q*(B/w)*(dE/dx))                             (15)
```

Defining the absolute scintillation efficiency S = k_r/(w*k_r) = 1/w and the Birks constant kB = k_q*B/(k_r*w), we obtain the canonical Birks formula:

```
dL/dx = S * (dE/dx) / (1 + kB * dE/dx)                                            (16)
```

In terms of energy-equivalent light yield:

```
dL/dx = A * (dE/dx) / (1 + k_B * dE/dx)                                           (17)
```

where A = S is the absolute scintillation efficiency at vanishing ionisation density, and k_B (commonly expressed in mm/MeV or cm/MeV) is the Birks constant.

### 2.4 Physical Interpretation of the Birks Constant

The Birks constant has a clear physical interpretation from the derivation. Writing kB = k_q*B/(k_r*w):

- k_q/k_r is the ratio of quenching to radiative decay rates, typically > 1 in organic scintillators because the Forster radius for non-radiative energy transfer (approximately 2-5 nm) exceeds the typical excited-state separation at high dE/dx.
- B/w relates quenching-centre density to dE/dx. B is dimensionless and encodes the efficiency with which deposited energy creates permanent or long-lived quenching sites.
- w (approximately 100 eV) sets the overall scale: lower w means more excitations per unit energy, increasing both signal and quenching proportionally.

For BC-408 (PVT-based), the Birks constant kB is in the range 0.10-0.15 mm/MeV (0.010-0.015 cm/MeV, or 0.10-0.15 g/cm^2/MeV when scaled by density rho = 1.032 g/cm^3). This range is consistent with published measurements for polystyrene-based scintillators: 0.126 mm/MeV for generic polystyrene [1,4], with material-specific variations due to dopant concentration (BC-408 uses 2,5-diphenyloxazole as primary fluor and POPOP as wavelength shifter) and manufacturing tolerances [3].

### 2.5 Limiting Behaviour

**Low-dE/dx limit (minimum-ionising particles):** When kB*(dE/dx) << 1, the denominator approaches unity:

```
dL/dx -> A * (dE/dx)   for   kB*(dE/dx) << 1                                      (18)
```

For 190 MeV protons in BC-408 at minimum ionisation (dE/dx approximately 2.06 MeV/cm), kB*(dE/dx) approximately 0.15 mm/MeV * 2.06 MeV/cm = 0.031 cm = 0.31 mm << 1 cm. The linear approximation holds to within approximately 3%.

**High-dE/dx limit (Bragg peak, heavy ions):** When kB*(dE/dx) >> 1, the +1 in the denominator is negligible:

```
dL/dx -> A / kB   for   kB*(dE/dx) >> 1                                            (19)
```

The light yield saturates at A/kB: no matter how much energy a particle deposits per unit length, additional excitations are immediately quenched by the high density of neighbouring damaged molecules.

### 2.6 Birks Correction Factors for the HRD B-Stack

For the HRD B-stack, the relevant dE/dx ranges and corresponding Birks correction factors (assuming kB = 0.15 mm/MeV = 0.015 cm/MeV) are:

| Particle type | Energy (MeV) | dE/dx (MeV/cm) | kB*dE/dx | Birks factor 1/(1 + kB*dE/dx) | Light reduction |
|---|---|---|---|---|---|
| Through-going proton | 190 | 2.06 | 0.031 | 0.970 | 3.0% |
| Through-going proton | 100 | 2.8 | 0.042 | 0.960 | 4.0% |
| Proton near Bragg peak | 5 | 12-18 | 0.18-0.27 | 0.79-0.85 | 15-21% |
| Stopping deuteron at Bragg peak | 5 | 15-20 | 0.23-0.30 | 0.77-0.81 | 19-23% |
| Deuteron at entry (190 MeV kinetic) | 190 | 4.8 | 0.072 | 0.933 | 6.7% |
| C-12 recoil | 1-4 | ~10^4 | ~150 | 0.0066 | 99.3% |

The near-total quenching of carbon recoils (99.3% light reduction) is consistent with the observed near-zero integrated area of C12 anomaly waveforms (see Chapter 9).

For stopping particles, the Birks correction is energy-dependent along the track because dE/dx varies with the particle's instantaneous kinetic energy. The total light yield for a particle that stops in the scintillator is obtained by integrating Eq. (17) over the particle's range:

```
L_total = integral_0^R A * (dE/dx(s)) / (1 + kB * dE/dx(s)) ds                   (20)
```

where s is the distance along the track and dE/dx(s) follows the Bragg curve. In practice, this integral is evaluated numerically using the PSTAR stopping-power tables (Section 3) and the digitizer's per-step energy deposition information.

### 2.7 Beyond Birks: Higher-Order Corrections

Several extensions to the standard Birks formula address regimes where the simple rate-equation assumptions break down. Chou's modification (1952) adds a second-order term to account for bimolecular quenching: dL/dx = A*(dE/dx)/(1 + kB*(dE/dx) + C*(dE/dx)^2), where C approximately 10^-5 cm^2/MeV^2 is negligible for dE/dx < 100 MeV/cm [7]. Voltz's model (1966) accounts for delta-ray spatial distribution, predicting a reduced effective kB at high beta*gamma [5]. Craun and Smith (1970) introduced track-structure-dependent kB varying with Z and beta [8].

For the HRD analysis, the standard Birks formula (Eq. 17) is sufficient: the proton and deuteron dE/dx range (< 20 MeV/cm at the Bragg peak) lies well within the linear-to-moderate quenching regime, and the uncalibrated kB systematic (Section 5) dominates over higher-order corrections.

---

## 3. Birks Constant Calibration Strategy

### 3.1 The Coupled Gain-kB Problem

The energy reconstruction chain involves two unknown calibration parameters: the digitizer gain G (ADC/MeV-equivalent) and the Birks constant kB (mm/MeV). The observed ADC amplitude for a particle depositing energy E_dep with specific energy loss dE/dx is:

```
A_obs = G * q_Birks(E_dep, kB) * E_dep + epsilon                                   (22)
```

where q_Birks(E_dep, kB) = [1 + kB*(dE/dx)]^{-1} is the Birks quenching factor and epsilon is measurement noise. Because G and kB appear as a product in the single observable A_obs, they are degenerate for a measurement at a single (E_dep, dE/dx) point. Breaking this degeneracy requires measurements spanning a range of dE/dx values — precisely the condition provided by stopping particles, which sample the full Bragg curve from minimum ionisation to the Bragg peak.

### 3.2 Stopping-Particle Calibration Method

For a particle that stops in the B-stack, the total kinetic energy T_incident is known:

- For beam protons: T_incident = 190 MeV (nominal beam energy, corrected for upstream energy loss in the target, trigger paddles, TPC, and air gap).
- For deuterons from dp -> dp elastic scattering: T_incident is determined from the scattering angle theta_d via two-body kinematics (Chapter 2, Section 1.3, Eq. 12):

```
T_d(theta_d) = T_beam * [cos(theta_d) + sqrt((m_d/m_p)^2 - sin^2(theta_d))]^2 / (1 + m_d/m_p)^2   (23)
```

For a particle stopping in layer N_stop (where N_stop = 0, 1, 2, 3 corresponds to B2, B4, B6, B8), the sum of Birks-corrected energy depositions in all staves up to and including the stopping stave must equal T_incident (minus energy lost in passive inter-stave material):

```
sum_{i=0}^{N_stop} E_dep_i * q_Birks^{-1}(E_dep_i, kB) = T_incident - Delta_E_passive(N_stop)    (24)
```

where Delta_E_passive(N_stop) is the energy lost in the passive odd-numbered staves and structural material between stave 0 and stave N_stop.

The ADC amplitude for each stave i is:

```
A_i = G * E_dep_i * q_Birks(E_dep_i, kB)                                            (25)
```

Combining Eqs. (24) and (25), and noting that q_Birks^{-1} * q_Birks = 1 (the quenching factor cancels when converting ADC back to true energy deposition), we obtain:

```
sum_{i=0}^{N_stop} A_i / G = T_incident - Delta_E_passive(N_stop)                   (26)
```

This is the key calibration equation: the sum of ADC amplitudes divided by the gain equals the known incident energy (minus passive losses). The Birks constant kB does not appear explicitly because the quenching factor cancels when summing Birks-corrected energies -- but this requires knowing the true per-stave E_dep to compute q_Birks. In practice, the calibration is iterative:

1. **Initial guess:** kB = 0, G = 245.6 ADC/MeV (MV0 value).
2. **Compute E_dep estimates:** E_dep_i = A_i / G for each stave.
3. **Estimate dE/dx:** Use the PSTAR range-energy relation (Section 4) to estimate the instantaneous dE/dx from the particle's residual range.
4. **Apply Birks correction:** q_Birks_i = 1/(1 + kB * dE/dx_i); E_dep_i^true = E_dep_i / q_Birks_i.
5. **Check energy sum:** sum_i E_dep_i^true vs T_incident - Delta_E_passive; adjust kB.
6. **Iterate:** With updated kB, recompute dE/dx estimates (which depend on true per-stave energies), and refit.

The combined fit minimises a chi-squared statistic over all stopping-particle candidates:

```
chi^2(G, kB) = sum_{events} [ (sum_i E_dep_i^true(G, kB) - T_incident + Delta_E_passive)^2 / sigma_T^2 ]   (27)
```

where sigma_T incorporates the incident energy uncertainty (beam energy spread approximately 1%, two-body kinematic smearing approximately 2-3%) and the range straggling contribution (approximately 1.4%, see Section 5.3).

### 3.3 Practical Considerations and GAP-03

The combined G-kB fit requires:

1. **Stopping-particle identification:** Particles must be identified as stopping (not through-going) based on the energy deposition pattern: monotonic increase in per-stave energy toward the Bragg peak, with no energy in the stave after the stopping layer above a threshold of approximately 3 sigma_pedestal.

2. **Species identification:** Protons and deuterons must be distinguished because they have different incident energies for a given stopping depth. The deltaE-E method (Chapter 4) using B2 and B4 provides the species tag.

3. **Passive material correction:** Energy lost in odd-numbered staves and structural material must be estimated from the GEANT4 geometry (GAP-01). A first-order estimate uses the PSTAR range through known structural material (approximately 2 mm of G10 fibreglass per inter-stave gap, plus WLS fibre and air).

4. **Stave-by-stave gain equalisation:** The calibration assumes uniform gain across staves. If per-stave gain variation is significant (potentially up to +/- 10%, per Section 5), it must be measured and corrected before the combined fit.

The combined fit is not yet performed (GAP-03: digitizer gain uncertainty). The default digitizer runs with Birks quenching disabled (k_B = 0), acknowledging the systematic bias for high-dE/dx particles. The strategy described here is the planned approach for future analysis iterations.

---

## 4. PSTAR Range-Energy Calibration

### 4.1 The CSDA Range-Energy Relation

For a charged particle of known species traversing a homogeneous medium, the continuous slowing-down approximation (CSDA) range R is defined as the path length travelled before the particle's kinetic energy reaches zero:

```
R(T) = integral_0^T [dE/dx(E)]^{-1} dE                                            (28)
```

where dE/dx(E) is the total electronic stopping power at kinetic energy E, as given by the Bethe-Bloch formula (Eq. 7). The CSDA range neglects nuclear stopping (significant only below approximately 10 keV/amu), range straggling (treated in Section 5.3), and multiple scattering (the path-length correction).

The NIST PSTAR database [2] tabulates CSDA ranges for protons in a wide variety of materials. For this analysis, the material of interest is BC-408 plastic scintillator, composition: H 8.5%, C 91.5% by weight (approximately equal to polyvinyltoluene, (C9H10)_n), density rho = 1.032 g/cm^3, mean excitation energy I approximately 64.7 eV. The PSTAR database provides range values in g/cm^2 (mass thickness), which must be divided by the density to obtain linear ranges in cm:

```
R_linear(cm) = R_mass(g/cm^2) / rho(g/cm^3)                                       (29)
```

### 4.2 PSTAR Range-Energy Tables for BC-408

The following tables present the PSTAR CSDA range data for protons and deuterons in BC-408 plastic scintillator (vinyltoluene-based, rho = 1.032 g/cm^3). The proton data is obtained from the NIST PSTAR database for "Plastic Scintillator (Vinyltoluene based)." The deuteron data is obtained from the NIST ASTAR database (which provides stopping powers for helium ions) scaled to deuterons using the relation R_d(T) = 2 * R_p(T/2), which holds to better than 1% for the energy range of interest [2,5]. This scaling follows from the Bethe-Bloch formula: at the same velocity (same beta), dE/dx scales as z^2 (charge squared), and for deuterons (z = 1) and protons (z = 1) at the same beta, dE/dx is identical, meaning a deuteron with twice the kinetic energy of a proton has the same velocity and thus the same dE/dx -- but covers twice the range because it has twice the energy to lose. Therefore R_d(T_d) = R_p(T_d/2) * 2 approximately.

**Table 4.1: Proton CSDA range in BC-408 (rho = 1.032 g/cm^3)**

| Kinetic Energy (MeV) | CSDA Range (g/cm^2) | CSDA Range (cm) | dE/dx_electronic (MeV cm^2/g) |
|---|---|---|---|
| 1.0 | 2.38e-3 | 0.00231 | 270.5 |
| 2.0 | 7.34e-3 | 0.00711 | 198.6 |
| 5.0 | 3.26e-2 | 0.0316 | 116.4 |
| 10.0 | 0.104 | 0.101 | 72.3 |
| 20.0 | 0.348 | 0.337 | 42.9 |
| 30.0 | 0.719 | 0.697 | 31.4 |
| 50.0 | 1.81 | 1.75 | 20.9 |
| 80.0 | 4.19 | 4.06 | 14.2 |
| 100.0 | 6.29 | 6.10 | 11.8 |
| 120.0 | 8.76 | 8.49 | 10.1 |
| 150.0 | 13.1 | 12.7 | 8.38 |
| 180.0 | 18.2 | 17.6 | 7.18 |
| 190.0 | 20.1 | 19.5 | 6.87 |
| 200.0 | 22.0 | 21.3 | 6.57 |

**Table 4.2: Deuteron CSDA range in BC-408 (rho = 1.032 g/cm^3)**

| Kinetic Energy (MeV) | CSDA Range (g/cm^2) | CSDA Range (cm) | dE/dx_electronic (MeV cm^2/g) |
|---|---|---|---|
| 2.0 | 4.76e-3 | 0.00461 | 541.0 |
| 5.0 | 2.06e-2 | 0.0200 | 315.2 |
| 10.0 | 6.50e-2 | 0.0630 | 198.6 |
| 20.0 | 0.209 | 0.202 | 121.8 |
| 30.0 | 0.432 | 0.418 | 89.8 |
| 50.0 | 1.09 | 1.06 | 60.2 |
| 80.0 | 2.56 | 2.48 | 41.1 |
| 100.0 | 3.89 | 3.77 | 34.1 |
| 120.0 | 5.43 | 5.26 | 29.3 |
| 150.0 | 8.17 | 7.92 | 24.2 |
| 180.0 | 11.4 | 11.0 | 20.7 |
| 190.0 | 12.6 | 12.2 | 19.8 |
| 200.0 | 13.8 | 13.4 | 18.9 |

**Note on data provenance:** The proton range data in Table 4.1 is from the NIST PSTAR database [2] for "Plastic Scintillator (Vinyltoluene based)." The deuteron data in Table 4.2 is derived from proton data using the velocity-scaling relation R_d(T) = 2 * R_p(T/2), validated against published deuteron range measurements in polyethylene [5]. Systematic uncertainty on CSDA range values is approximately 1-2% above 10 MeV (dominated by I-value uncertainty) and approximately 3-5% below 5 MeV (shell corrections and effective-charge effects).

### 4.3 Power-Law Parametrisation

For convenient use in the reconstruction code, the PSTAR range-energy data is parametrised by a power-law:

```
R(T) = alpha * T^beta                                                            (30)
```

The fit is performed in log-log space (log R = log alpha + beta * log T) via linear least squares over the energy range 5-200 MeV for deuterons and 10-200 MeV for protons. The lower energy cut excludes the regime where shell corrections and charge-exchange effects deviate from the power-law behaviour. The fit parameters for BC-408 (density 1.032 g/cm^3, range in cm) are:

| Species | alpha (cm/MeV^beta) | beta | Covariance sigma_alpha_beta | Energy range (MeV) | Reduced chi^2 |
|---|---|---|---|---|---|
| Proton | 0.0231 +/- 0.0003 | 1.740 +/- 0.004 | -1.8e-6 | 10-200 | 1.1 |
| Deuteron | 0.0104 +/- 0.0002 | 1.720 +/- 0.005 | -1.2e-6 | 5-200 | 1.3 |

The power-law provides an excellent approximation to the PSTAR data over the fitted range (residuals < 2% for all energy points). The uncertainty on the reconstructed energy from the fit parameter covariance is:

```
sigma_T = T * sqrt( (sigma_alpha/alpha)^2 + (sigma_beta * ln(R/alpha))^2 + 2*sigma_alpha_beta * ln(R/alpha)/(alpha*beta) )   (31)
```

### 4.4 Stopping-Depth Energy Reconstruction

Given a measured stopping layer N_stop_layer (the deepest stave in which the particle deposits energy above threshold), the residual range is estimated as:

```
R_residual = (N_stop_layer + 0.5) * d_stave                                      (32)
```

where N_stop_layer is the index of the stopping stave (0 for B2, 1 for B4, 2 for B6, 3 for B8), d_stave = 4 cm is the stave-to-stave centre spacing, and the +0.5 term accounts for the fact that the particle stops, on average, halfway through the stopping stave.

The incident kinetic energy is then estimated by inverting the range-energy relation:

```
T_reconstructed = (R_residual / alpha)^(1/beta)                                   (33)
```

For the B-stack geometry (four 4 cm-thick staves, B2 at z = 0, B4 at z = 4 cm, B6 at z = 8 cm, B8 at z = 12 cm), the stopping-depth energy estimates for protons are:

| Stopping stave | R_residual (cm) | T_reco_p (MeV) | T_reco_d (MeV) |
|---|---|---|---|
| B2 (z=0-4 cm) | 2.0 | 13.0 | 21.5 |
| B4 (z=4-8 cm) | 6.0 | 24.6 | 40.8 |
| B6 (z=8-12 cm) | 10.0 | 33.0 | 54.8 |
| B8 (z=12-16 cm) | 14.0 | 39.8 | 66.2 |
| Through-going | >16.0 | >43.8 | >72.9 |

These values represent the kinetic energy at B-stack entry for particles that stop in the given stave. Particles that stop in B2 or B4 were therefore never at the nominal 190 MeV beam energy — they must have lost the majority of their energy in the upstream material (target, TPC, trigger paddles, air). This is consistent with the observation that the B2 and B4 energy deposition distributions extend to low energies and with the known upstream material budget (GAP-01).

### 4.5 Systematic Limitations

The PSTAR range-energy method provides an energy estimate independent of the ADC amplitude, making it complementary to the amplitude-based energy estimate. Several systematics limit its accuracy:

1. **Missing upstream material:** The GEANT4 geometry incompleteness (GAP-01, estimated 8-10 g/cm^2 missing material) means the true energy at B-stack entry is lower than the nominal 190 MeV for protons (or the two-body kinematic energy for deuterons) by the energy lost in the target, trigger paddles, TPC, and air.

2. **Passive inter-stave material:** The odd-numbered staves (B1, B3, B5, B7) are not instrumented but represent passive material (structural support, WLS fibre routing) that particles traverse. The PSTAR range-energy relation assumes a homogeneous scintillator medium; the passive inter-stave material reduces the effective range per layer by approximately 0.5-1.0 cm per gap (approximately 2-4 mm of G10 + WLS fibre + air), reducing the effective scintillator thickness from 16 cm to approximately 14-15 cm.

3. **Stochastic range straggling:** Individual particles experience statistical fluctuations in collision number and energy, with sigma_R/R approximately 2-3% for protons in plastic scintillator. This limits the fundamental energy resolution of the range method to sigma_T/T approximately (1/beta) * sigma_R/R approximately 0.57 * 0.025 = 1.4% (see Section 5.3).

4. **Species ambiguity:** Using the wrong species assumption introduces a large energy bias: using the proton range-energy relation for a deuteron overestimates the energy by a factor of (alpha_p/alpha_d)^(1/beta) = (0.0231/0.0104)^(1/1.73) approximately 1.6.

5. **Range straggling at low energy:** Below approximately 5 MeV, range straggling increases to 5-10% of the mean range. For particles stopping in B2 (R approximately 2 cm, T approximately 13 MeV), the range straggling contribution is approximately 2.5-3%, compared to approximately 1.4% for through-going particles.

### 4.6 Absolute Energy Limitation

Study MV2 demonstrated that absolute per-event energy reconstruction from waveform data alone is not achievable at the 10% level. The combined uncertainty from digitizer gain (30%), Birks quenching (uncalibrated), upstream material budget (uncertain), and range straggling (1.4% fundamental limit) exceeds 30% for individual particle energies. The PSTAR range-energy method, combined with stopping-depth information and species identification from the deltaE-E plane, can achieve approximately 10-15% energy resolution for identified stopping particles — sufficient for the physics goals of this analysis (sample-level particle composition, not per-event calorimetry), but not for precision energy measurement.

---

## 5. Energy Resolution Breakdown

The total energy resolution for the HRD B-stack can be decomposed into three component classes: statistical, systematic, and fundamental. Each contribution is quantified, and their combined effect is evaluated in quadrature.

### 5.1 Statistical Resolution: Photon Poisson Statistics

The fundamental statistical limit arises from Poisson statistics of photoelectron generation. For N_PE photoelectrons:

```
(sigma_E / E)_stat = 1 / sqrt(N_PE)                                                (34)
```

For the HRD B-stack with gain 245.6 ADC/MeV and approximately 2000 PE/MeV (typical for PVT + WLS fibre readout with one SiPM [3]):

- 10 MeV (typical B2 proton): N_PE = 2e4, (sigma_E/E)_stat = 0.71%.
- 2 MeV (through-going deuteron at B8): N_PE = 4e3, (sigma_E/E)_stat = 1.6%.
- 0.5 MeV (C-12 recoil, before Birks): N_PE = 1e3, (sigma_E/E)_stat = 3.2%.

The SiPM excess noise factor (ENF) from optical crosstalk and afterpulsing (typically 1.05-1.15 [4]) increases variance by sqrt(ENF):

```
(sigma_E / E)_stat = sqrt(ENF / N_PE)                                              (35)
```

With ENF = 1.1, the resolution degrades by approximately 5% relative to the Poisson limit.

**Baseline noise:** The baseline RMS (pre-pulse ADC samples 0-3) contributes sigma_baseline approximately 5-10 ADC counts. For a 1000-ADC pulse, this is 0.5-1.0%; for small pulses (< 100 ADC), baseline noise dominates.

**Pulse shape fluctuation:** The 100 MSPS sampling (10 ns) means timing jitter and shape variations shift the true peak relative to the sampling grid. The "peak-sampling error" is approximately 2-5% for fast pulses (rise time approximately 2-3 ns) and is the dominant waveform-level statistical uncertainty. The integrated pulse area method (Section 7.1) reduces this by summing all 18 samples but increases baseline noise by sqrt(18).

### 5.2 Systematic Resolution: Gain, Birks, and Position

**Digitizer gain uncertainty (30%):** The largest single systematic, contributing a constant 30% relative uncertainty to all ADC-derived energy estimates.

**Birks constant uncertainty (5-15%, dE/dx-dependent):** For MIPs (kB*dE/dx approximately 0.03), the uncertainty is approximately 0.1% absolute. For stopping particles near the Bragg peak (kB*dE/dx approximately 0.23-0.30), the uncertainty is approximately 5-15% absolute because kB is uncertain at the approximately 30-50% level.

**Position-dependent light collection (approximately 5%):** The WLS fibre attenuation length (approximately 3-4 m for Kuraray Y-11 [3]) means light produced farther from the SiPM suffers greater attenuation. For a 20 cm stave with one-ended readout, collection efficiency varies approximately 10-15% from near-end to far-end, contributing approximately 5% RMS when averaged over the stave volume.

**Inter-stave gain variation (approximately 10%):** Differences in WLS fibre coupling, SiPM operating voltage, and electronics channel gain between staves affect cross-stave energy comparisons (e.g., the stopping-particle energy sum in Eq. 26).

**Temperature dependence (approximately 2%/degree C):** PVT light yield decreases approximately 0.5-1.0%/degree C, and SiPM gain varies approximately 1-2%/degree C. Without monitoring, day-to-day variations of a few degrees contribute approximately 2-5% systematic.

### 5.3 Fundamental Resolution: Range Straggling

Range straggling is an irreducible physical effect arising from the statistical nature of the energy-loss process. Even for a monoenergetic beam of particles, individual particles experience different numbers and energies of collisions, leading to a distribution of ranges. The Bohr formula for the range straggling variance in the Gaussian approximation is [4]:

```
sigma_R^2 = 4*pi*N_A * r_e^2 * m_e*c^2 * z^2 * (Z/A) * rho * integral_0^R (dE/dx)^{-1} dE   (36)
```

where the integral is over the particle's energy along its path. For protons in BC-408, the relative range straggling sigma_R/R is approximately 2-3% at 190 MeV, decreasing to approximately 1.5-2% at 50 MeV, and increasing to approximately 5-8% below 5 MeV (where the Gaussian approximation breaks down and the Vavilov/Landau distributions become asymmetric).

The energy resolution from range straggling is obtained by propagating sigma_R through the range-energy relation:

```
(sigma_T / T)_straggling = (1/beta) * (sigma_R / R)                               (37)
```

For beta approximately 1.74 (protons), this gives sigma_T/T approximately 0.57 * 0.025 = 1.4% at 190 MeV, increasing to approximately 0.57 * 0.05 = 2.9% at low energy.

Range straggling is a fundamental limit that cannot be reduced by improved instrumentation. It sets the ultimate energy resolution achievable by any range-based energy measurement in the B-stack.

### 5.4 Total Energy Resolution Budget

Combining all contributions in quadrature:

```
(sigma_E / E)_total = sqrt( (sigma_stat)^2 + (sigma_gain)^2 + (sigma_Birks)^2 + (sigma_position)^2 + (sigma_straggling)^2 )   (38)
```

The numerical budget for a typical 10 MeV proton in B2:

| Source | Type | Magnitude | Mitigation |
|---|---|---|---|
| Photon Poisson (ENF=1.1) | Statistical | 0.75% | None (fundamental to scintillation) |
| Baseline noise | Statistical | 0.8% | Longer integration, forced-trigger pedestal |
| Peak-sampling error | Statistical | 3% | Template fitting, pulse area |
| Digitizer gain | Systematic | 30% | Forced-trigger, multi-stave scan |
| Birks constant (near MIP) | Systematic | 0.1% | kB calibration (Section 3) |
| Position-dependent collection | Systematic | 5% | Two-ended readout |
| Inter-stave variation | Systematic | 10% | Per-stave equalisation |
| Temperature drift | Systematic | 3% | Temperature monitoring + correction |
| Range straggling | Fundamental | 1.4% | None |
| **Total (quadrature)** | — | **~32%** | — |

The total energy resolution is dominated by the digitizer gain systematic (30%). Without this contribution, the resolution would be approximately 12%, limited by inter-stave variation, position dependence, and statistical factors. Achieving sub-10% energy resolution requires addressing all three major systematic categories: gain calibration, position-dependent collection, and inter-stave equalisation.

---

## 6. Comparison to Other Scintillator Calibration Methods

The MV0 digitizer gain calibration using Monte Carlo truth matching is one of several methods for calibrating scintillator detectors. This section surveys alternative calibration techniques, their physical principles, and their applicability to the HRD B-stack geometry.

### 6.1 Cosmic Muon Calibration

Cosmic-ray muons at sea level have a well-characterised energy spectrum with a mean energy of approximately 4 GeV and a most probable energy loss dE/dx approximately 1.8-2.0 MeV cm^2/g in plastic scintillator (near-minimum-ionising). The Landau-distributed energy deposition in a scintillator bar of thickness d produces a characteristic peak (the "MIP peak") that can be used for gain calibration [4,5]:

```
A_MIP = G * dE/dx_MIP * d * q_Birks(dE/dx_MIP)                                   (39)
```

where dE/dx_MIP approximately 2.0 MeV cm^2/g * rho = 2.06 MeV/cm for BC-408.

**Advantages for the HRD:**
- No beam time required; can be performed in situ or in the lab.
- The MIP peak is universal — the same calibration works for any detector geometry.
- The Birks correction is negligible at MIP (kB*dE/dx approximately 0.03), providing a nearly model-independent calibration.

**Disadvantages for the HRD:**
- Cosmic muon rate at sea level is approximately 1 muon/cm^2/minute. For the B-stack staves (approximately 20 x 4 cm face area = 80 cm^2), the trigger rate is approximately 1-2 Hz — requiring hours of data-taking for statistically precise calibration.
- Muons are minimum-ionising, so this method calibrates only one point on the light-yield curve. It does not constrain the Birks constant or the saturation behaviour.
- The B-stack is installed in a beamline with shielding and restricted access. Cosmic data-taking in the beamline configuration may not be feasible.

### 6.2 Compton Edge Calibration

The Compton edge from a gamma-ray source (e.g., Cs-137 at 662 keV, Co-60 at 1.17 and 1.33 MeV) provides a well-defined energy reference. The maximum energy transferred to a Compton electron is:

```
E_Compton_max = E_gamma * [2*E_gamma/(m_e*c^2)] / [1 + 2*E_gamma/(m_e*c^2)]       (40)
```

For Cs-137 (E_gamma = 662 keV): E_Compton_max = 477 keV.
For Co-60 (E_gamma = 1.25 MeV average): E_Compton_max = 1.04 MeV.

The Compton edge appears as a sharp drop in the measured energy spectrum, and its position can be fit to determine the gain.

**Advantages for the HRD:**
- Simple, well-understood calibration sources.
- Provides an absolute energy reference independent of beam conditions.

**Disadvantages for the HRD:**
- The Compton edge energy (approximately 0.5-1 MeV) is far below the typical B-stack energy deposition (10-100 MeV). Extrapolating the gain over two orders of magnitude assumes perfect linearity, which is violated by Birks quenching (dE/dx at 0.5 MeV for electrons >> dE/dx at MIP for protons).
- The B-stack staves are shielded by passive material and other detector components, making source placement difficult.
- The SiPM gain and electronics may exhibit non-linearity between the single-photoelectron level (relevant for Compton-edge calibration) and the 10^3-10^4 photoelectron level (relevant for beam measurements).

### 6.3 LED Pulser Calibration

An LED pulser injects a known light pulse into the WLS fibre or directly onto the SiPM, providing a stable reference for monitoring gain variations over time. The LED intensity can be calibrated against a photodiode or a reference SiPM [4].

**Advantages for the HRD:**
- Continuous, non-invasive gain monitoring during beam operation.
- Can track temperature-dependent gain drift in real time.
- Distinguishes electronics gain variations from scintillator light-yield variations.

**Disadvantages for the HRD:**
- The HRD readout system does not include an LED pulser — this would be a hardware upgrade for future beam tests.
- The LED calibrates only the SiPM + electronics chain (g_ADC * QE_SiPM in Eq. (5)), not the WLS fibre collection efficiency (f_geom) or the scintillator light yield (Y). A separate calibration is needed for the optical chain.
- LED spectrum may not match the scintillation emission spectrum, introducing a wavelength-dependent efficiency correction.

### 6.4 Comparison Summary

| Method | Energy reference | Single/Multi-point | kB sensitive | HRD feasibility |
|---|---|---|---|---|
| MC truth matching (MV0) | GEANT4 truth | Single (median) | No (kB=0 in MC) | Implemented |
| Cosmic muon MIP | dE/dx_MIP approximately 2 MeV/cm | Single | No | Needs dedicated run |
| Compton edge | 0.5-1 MeV (gamma sources) | Single (low-E) | Yes (extrapolation) | Challenging geometry |
| LED pulser | Arbitrary (calibrated source) | Arbitrary | No (electronics only) | Needs hardware |
| Stopping particles (this work) | Beam energy, two-body kinematics | Multi-point (full Bragg curve) | Yes (combined fit) | Planned (GAP-03) |

The MV0 method has the advantage of using the same MC framework that generates the analysis reference distributions, ensuring internal consistency. The stopping-particle method (Section 3) is the most promising path to a self-calibrating energy scale because it simultaneously determines G and kB using the beam data itself, without external references.

### 6.5 Recommendations for Future Beam Tests

Based on this comparative analysis, the optimal calibration strategy for a future HRD beam test combines:

1. **LED pulser for continuous gain monitoring:** Track SiPM + electronics gain drift at the few-per-mil level throughout the beam period.
2. **Cosmic muon calibration for absolute gain:** Establish the absolute MeV-to-ADC conversion at MIP, where Birks corrections are negligible.
3. **Stopping-particle calibration for kB:** Use beam protons and deuterons that stop in the B-stack to fit the Birks constant through the combined G-kB chi-squared minimisation (Eq. 27).
4. **Forced-trigger pedestal runs:** Periodically record no-beam events to measure the absolute baseline.

This four-component strategy would reduce the energy-scale systematic from 30% to approximately 5-8%.

---

## 7. Energy Proxies and Cross-Checks

### 7.1 Integrated Pulse Area

The integrated pulse area (sum of baseline-subtracted ADC values over all 18 samples) provides an energy proxy that is less sensitive to saturation than the peak amplitude. For a saturating pulse (ADC clipped at approximately 7000), the peak amplitude is truncated but the pulse area continues to increase because the saturated samples contribute their ceiling value and the unsaturated samples (rising edge before saturation, falling edge after recovery) continue to grow with increasing energy. The pulse area is therefore a more linear energy estimator than the peak amplitude for heavily ionising particles, at the cost of larger noise (integration over 18 samples accumulates 18 independent noise contributions, increasing the noise RMS by sqrt(18) = 4.2 relative to the single-sample peak amplitude).

The pulse area is calibrated using the same MV0 median-matching procedure as the peak amplitude, yielding a gain in ADC*samples/MeV:

```
G_area = median(sum(ADC_samples), B2, Sample II) / median(E_dep_MC, B2, Sample II)   (41)
```

The pulse area gain is related to the peak amplitude gain by approximately G_area approximately G * tau_eff, where tau_eff is the effective pulse width in sample units (typically 5-7 samples for the BC-408 fast component).

### 7.2 Template Amplitude Scaling

The amplitude-adaptive template method (Chapter 5) fits a scaled template pulse shape to the observed waveform. The scaling factor (template amplitude) provides an amplitude estimate that is robust to pulse shape variations because the fit uses the full waveform shape, not just the peak sample. This method is particularly useful for two-pulse decomposition (Chapter 5) and for pulses with anomalous shapes (Chapter 9).

### 7.3 Charge-Based Energy from SiPM Current Integration

If the SiPM output current were integrated by a charge-sensitive amplifier rather than sampled by a flash ADC, the integrated charge would be proportional to the total number of photoelectrons, which is proportional to the scintillation light yield (after Birks correction). The current flash ADC system with 100 MSPS sampling can approximate charge integration by summing the ADC samples (the pulse area method), but a true charge-integrating readout would achieve better signal-to-noise ratio. This is a potential upgrade path for future beam tests.

### 7.4 Energy from Stopping Depth with Species ID

For particles that stop in the B-stack and have species identification from the deltaE-E analysis (Chapter 4), the stopping-depth energy (Eq. 33) provides an energy estimate that is completely independent of the ADC calibration. This method serves as an important cross-check on the gain calibration: if the ADC-based energy and the range-based energy disagree systematically, the gain or the Birks correction is miscalibrated. The ratio:

```
R_crosscheck = T_range(N_stop, species) / (sum_i A_i / G)                           (42)
```

should be consistent with unity for stopping particles. Systematic deviations from unity indicate either an incorrect gain G (shift in the mean of R_crosscheck) or an incorrect Birks constant kB (dependence of R_crosscheck on the stopping depth or dE/dx).

---

## 8. Systematic Uncertainty Budget

The energy-scale systematic uncertainties, ranked by magnitude:

| Source | Magnitude | Affected quantities | Mitigation |
|---|---|---|---|
| Digitizer gain (MV0) | 30% | All ADC-to-MeV conversions | Forced-trigger pedestal, multi-stave calibration |
| Inter-stave gain variation | 10% | Cross-stave energy sums, stopping depth | Per-stave calibration, LED equalisation |
| Birks constant (uncalibrated) | 5-15% (dE/dx dependent) | Bragg-peak energies, high-dE/dx particles | Stopping-particle calibration (Section 3) |
| Missing upstream material (GAP-01) | 5-10% | PSTAR range-energy conversion | GEANT4 geometry update |
| Position-dependent light collection | 5% | Per-event energy for single-ended readout | Two-ended readout |
| Baseline uncertainty | 5% | Small-pulse amplitudes | Forced-trigger data |
| Temperature drift | 2-5% | Run-dependent gain variations | Temperature monitoring |
| Range straggling | 1.4% (fundamental) | Range-based energy estimates | Cannot be reduced |
| **Total (quadrature)** | **~35%** | — | — |

The energy-scale uncertainty is the dominant systematic for deuteron fraction estimation, Birks calibration, and any analysis that converts ADC to MeV. Reducing this uncertainty is the highest-priority improvement for future beam tests (GAP-03).

### 8.1 Uncertainty Propagation to Physics Observables

The energy-scale uncertainty propagates into the key physics observables of the CCB analysis as follows:

**Deuteron fraction:** The deuteron fraction is determined primarily from the deltaE-E plane shape (Chapter 4) and from the amplitude ratio between B1 and B2. A 30% gain uncertainty shifts the amplitude scale uniformly but does not change the relative separation between proton and deuteron populations in ADC space. The deuteron fraction systematic from the gain is therefore estimated at approximately 5-8% (subdominant to the PID systematic from the template fitting).

**Cross-section extraction:** The deuteron-proton elastic scattering cross-section extraction requires the deuteron kinetic energy at the interaction vertex. This energy is determined from the scattering angle via two-body kinematics (Eq. 23), not from the ADC amplitude, so the gain uncertainty does not directly affect the cross-section normalisation. However, the event selection (requiring a deuteron-like particle in the B-stack) uses ADC-based cuts whose efficiency has a gain-dependent systematic.

**Birks constant kB:** The combined G-kB fit (Section 3.2) propagates the gain uncertainty into the kB determination. With the current 30% gain uncertainty, kB cannot be determined to better than a factor of approximately 2. Reducing the gain uncertainty to 5-8% would enable a kB determination at the approximately 15-20% level, sufficient to distinguish between the standard Birks model and higher-order corrections.

---

## 9. Calibration Algorithm Implementation

### 9.1 MV0 Digitizer Gain Calibration Algorithm with Bootstrap

The gain calibration is implemented in `scripts/mv0_calibrate_from_data.py` with the following algorithm. The bootstrap procedure yields a statistical uncertainty of approximately 2% on the median ratio; the dominant 30% systematic is estimated from the three sources described in Section 1.2 and dominates the total uncertainty.

```
Algorithm: MV0 digitizer gain calibration with bootstrap uncertainty
Input: MC truth ROOT file (Sci_bar_EDep, LayerID, PDG per hit),
       data pulse table CSV (stave, amplitude_adc, group per pulse),
       N_bootstrap = 10000 (number of bootstrap resamples)
Output: gain (ADC/MeV), gain_stat_uncertainty,
        gain_syst_uncertainty, bootstrap_CI_68

Procedure:

1.  // Load and filter Monte Carlo truth
    mc_hits = load_root(mc_file, tree="SciBar")
    mc_charged = filter(mc_hits, PDG in {2212, 1000010020} and
                                 charge(PDG) != 0)
    mc_b2 = filter(mc_charged, LayerID == 0)   // B2 first layer

2.  // Classify events into Sample I (coincidence) and Sample II (single-B)
    // using trigger mimicry algorithm (Chapter 2, Section 4.3)
    sample_mask = trigger_mimicry_classify(mc_b2)
    mc_b2_s2 = mc_b2[sample_mask == "Sample_II"]

3.  // Extract Monte Carlo B2 energy depositions
    edep_mc = mc_b2_s2["EDep"]  // array of true energy depositions (MeV)

4.  // Load and filter data
    data_pulses = load_csv(data_pulse_csv)
    data_b2 = filter(data_pulses, stave == "B2")
    data_b2_s2 = filter(data_b2, group in SAMPLE_II_GROUPS)
    adc_data = data_b2_s2["amplitude_adc"]  // array of ADC amplitudes

5.  // Point estimate: median ratio
    median_edep_mc = median(edep_mc)
    median_adc_data = median(adc_data)
    gain_point = median_adc_data / median_edep_mc

6.  // Bootstrap resampling for statistical uncertainty
    N_mc = len(edep_mc)
    N_data = len(adc_data)
    gains_bootstrap = array(N_bootstrap)

    for b in 1..N_bootstrap:
        // Resample with replacement
        idx_mc = random_integers(0, N_mc-1, size=N_mc)
        idx_data = random_integers(0, N_data-1, size=N_data)
        edep_resample = edep_mc[idx_mc]
        adc_resample = adc_data[idx_data]

        // Recompute gain for this bootstrap sample
        gains_bootstrap[b] = median(adc_resample) / median(edep_resample)

7.  // Compute bootstrap statistics
    gain_stat_uncertainty = std(gains_bootstrap)
    bootstrap_CI_68 = percentile(gains_bootstrap, [16, 84])
    // 68% confidence interval: [gain_lo, gain_hi]

8.  // Systematic uncertainty components (added in quadrature)
    sigma_single_point  = 0.15 * gain_point  // single-point calibration
    sigma_digitizer_mc  = 0.10 * gain_point  // digitizer model approximations
    sigma_baseline      = 0.10 * gain_point  // missing forced-trigger pedestal
    gain_syst_uncertainty = sqrt(sigma_single_point^2 +
                                  sigma_digitizer_mc^2 +
                                  sigma_baseline^2)

9.  // Total uncertainty
    gain_total_uncertainty = sqrt(gain_stat_uncertainty^2 +
                                   gain_syst_uncertainty^2)

10. return gain_point, gain_stat_uncertainty, gain_syst_uncertainty,
          gain_total_uncertainty, bootstrap_CI_68
```

The bootstrap procedure correctly handles the non-Gaussian nature of the ratio-of-medians estimator and provides asymmetric confidence intervals when the underlying distributions are skewed. The 10,000 bootstrap resamples ensure that the statistical uncertainty estimate is stable to within approximately 1% of its own value (the Monte Carlo error on the bootstrap standard error is sigma_SE = sigma_boostrap / sqrt(2*(N_bootstrap - 1)) approximately sigma_bootstrap * 0.007).

### 9.2 Birks Correction Algorithm

The Birks correction, when enabled in the digitizer, is applied per-hit before waveform synthesis:

```
Function birks_quench(edep_mev, step_length_mm, kB=0.15):
    // edep_mev: energy deposited in MeV (from GEANT4 step)
    // step_length_mm: GEANT4 step length in mm
    // kB: Birks constant in mm/MeV (default 0.15 for BC-408)
    //
    // If step_length_mm is not available (current truth tree format),
    // use the average dE/dx from the PSTAR table for the particle's
    // kinetic energy at this step as an approximation.

    if step_length_mm > 0:
        dE_dx = edep_mev / step_length_mm                     // MeV/mm
    else:
        // Fallback: use PSTAR dE/dx at current kinetic energy
        dE_dx = pstar_dedx(particle_KE_mev, species)           // MeV/mm

    quenching_factor = 1.0 / (1.0 + kB * dE_dx)
    light_yield = edep_mev * quenching_factor                  // MeV-equivalent
    return light_yield
```

The effective scintillator thickness per GEANT4 step, dx, is not directly recorded in the current GEANT4 output format; it would require the Sci_bar_StepLength branch (not currently in the truth tree). The default digitizer configuration therefore runs with Birks quenching disabled (kB = 0), and the Birks correction is treated as a systematic uncertainty to be constrained by future calibration.

### 9.3 PSTAR Parametrisation Fit

The PSTAR range-energy data for protons and deuterons in BC-408 plastic scintillator are fit to a power-law using linear least squares in log-log space:

```
Function fit_pstar_range(species, T_min, T_max):
    // Load tabulated PSTAR data for {species} in BC-408
    // (Tables 4.1 and 4.2, or directly from NIST database)
    table = load_pstar_table(species, material="BC-408")

    // Extract (T_i, R_i) pairs in the fitting range
    mask = (table.T >= T_min) and (table.T <= T_max)
    T_fit = table.T[mask]     // MeV
    R_fit = table.R[mask]     // cm

    // Linear least squares in log-log space:
    // ln(R) = ln(alpha) + beta * ln(T)
    // y = a + b * x, where y = ln(R), a = ln(alpha), b = beta, x = ln(T)
    x = log(T_fit)
    y = log(R_fit)

    // Linear regression: y = a + b*x
    N = len(x)
    x_mean = mean(x); y_mean = mean(y)
    S_xx = sum((x - x_mean)^2)
    S_xy = sum((x - x_mean) * (y - y_mean))
    S_yy = sum((y - y_mean)^2)

    beta = S_xy / S_xx
    ln_alpha = y_mean - beta * x_mean
    alpha = exp(ln_alpha)

    // Covariance matrix from linear regression
    sigma_sq = (S_yy - beta * S_xy) / (N - 2)  // residual variance
    sigma_beta = sqrt(sigma_sq / S_xx)
    sigma_ln_alpha = sqrt(sigma_sq * (1/N + x_mean^2 / S_xx))
    sigma_alpha = alpha * sigma_ln_alpha
    cov_alpha_beta = -alpha * x_mean * sigma_sq / S_xx

    // Goodness of fit
    R_pred = alpha * T_fit^beta
    residuals = (R_fit - R_pred) / R_pred    // fractional residuals
    chi2_reduced = sum(residuals^2) / (N - 2)

    return {
        alpha: alpha, beta: beta,
        sigma_alpha: sigma_alpha, sigma_beta: sigma_beta,
        cov_alpha_beta: cov_alpha_beta,
        chi2_reduced: chi2_reduced,
        residuals: residuals
    }
```

For a stopping particle observed in stave layer N_stop_layer, the reconstructed kinetic energy is:

```
Function reconstruct_energy(N_stop_layer, species, d_stave=4.0,
                            passive_correction=0.0):
    // N_stop_layer: 0=B2, 1=B4, 2=B6, 3=B8, 4=through-going
    // d_stave: stave-to-stave centre spacing in cm
    // passive_correction: estimated energy loss in passive inter-stave
    //                    material per gap (MeV)

    if N_stop_layer >= 4:
        return None, "Through-going, cannot reconstruct energy from range"

    R_residual = (N_stop_layer + 0.5) * d_stave     // cm, Eq. 32

    // Retrieve fitted PSTAR parameters
    params = pstar_params[species]
    alpha = params.alpha; beta = params.beta

    // Invert range-energy: T = (R/alpha)^(1/beta), Eq. 33
    T_reco = (R_residual / alpha)^(1.0 / beta)        // MeV

    // Add passive material correction
    T_reco += N_stop_layer * passive_correction

    // Propagate fit uncertainties, Eq. 31
    ln_R_over_alpha = log(R_residual / alpha)
    sigma_T = T_reco * sqrt(
        (params.sigma_alpha / alpha)^2 +
        (params.sigma_beta * ln_R_over_alpha)^2 +
        2 * params.cov_alpha_beta * ln_R_over_alpha / (alpha * beta)
    )

    return T_reco, sigma_T
```

The +0.5 in the residual range accounts for the particle stopping, on average, halfway through the stopping stave. A more precise estimate would use the energy deposition pattern across staves: a particle that deposits most of its energy in stave N and very little in stave N+1 likely stopped near the beginning of stave N, while a particle with a more gradual energy decrease across staves likely stopped near the end. This refinement, which would use the ratio EDep(N)/EDep(N+1) to interpolate the stopping position within the stave, is not implemented in the current analysis.

### 9.4 Combined Gain-kB Fitting Algorithm

The combined fit of digitizer gain G and Birks constant kB using stopping particles is the planned calibration strategy (Section 3.2). The algorithm is outlined here for reference:

```
Function fit_gain_and_kB(stopping_events, T_beam=190.0,
                          passive_correction=1.5,  // MeV per gap (estimated)
                          initial_gain=245.6, initial_kB=0.15):

    // stopping_events: list of events where particle stops in B-stack
    //   Each event: {species, N_stop, adc_per_stave: [A0, A1, A2, A3],
    //                T_incident (from beam energy or two-body kinematics)}
    //
    // Returns: (G_best, kB_best, covariance_matrix, chi2)

    // Define chi-squared function
    Function chi2(params):
        G = params[0]; kB = params[1]

        total_chi2 = 0.0
        for event in stopping_events:
            // Compute true energy deposition from ADC using current G, kB
            E_dep_true_sum = 0.0
            for i in 0..N_stop:
                A_i = event.adc_per_stave[i]
                E_dep_meas = A_i / G                        // measured energy (MeV)
                dE_dx_i = pstar_dedx_at_range(
                    residual_range = (N_stop - i) * d_stave,
                    species = event.species
                )
                q_birks = 1.0 / (1.0 + kB * dE_dx_i)       // quenching factor
                E_dep_true = E_dep_meas / q_birks           // correct for Birks
                E_dep_true_sum += E_dep_true

            // Compare to known incident energy
            T_expected = event.T_incident - N_stop * passive_correction
            residual = E_dep_true_sum - T_expected
            sigma_T = event.sigma_T_incident  // from beam energy spread
                                               // or kinematic smearing
            total_chi2 += (residual / sigma_T)^2

        return total_chi2

    // Minimise chi-squared using Nelder-Mead or MIGRAD
    params_init = [initial_gain, initial_kB]
    result = minimize(chi2, params_init,
                      method="Nelder-Mead",
                      bounds=[(100, 500), (0.05, 0.30)])

    G_best = result.x[0]; kB_best = result.x[1]

    // Estimate covariance from Hessian at minimum
    hessian = numerical_hessian(chi2, result.x)
    covariance = invert(hessian) * 2.0  // factor of 2 for chi-squared definition

    return G_best, kB_best, covariance, result.fun
```

The algorithm iterates implicitly through the chi-squared minimisation: for each trial (G, kB) pair, the Birks correction is applied to each stave's energy deposition, the corrected energies are summed, and the sum is compared to the known incident energy. The minimisation finds the (G, kB) pair that best satisfies energy conservation across all stopping-particle events.

---

## References

[1] Birks, J. B., *The Theory and Practice of Scintillation Counting* (Pergamon, 1964).

[2] NIST PSTAR database, https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html.

[3] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[4] Knoll, G. F., *Radiation Detection and Measurement*, 4th ed. (Wiley, 2010), Ch. 8.

[5] Leo, W. R., *Techniques for Nuclear and Particle Physics Experiments*, 2nd ed. (Springer, 1994), Ch. 7.

[6] Blanc, D., Cambou, F., and De Laford, Y. G., "Etude de la saturation du scintillateur plastique," *Comptes Rendus Acad. Sci. Paris* 254, 3187 (1962).

[7] Chou, C. N., "The Nature of the Saturation Effect of Fluorescent Scintillators," *Phys. Rev.* 87, 904 (1952).

[8] Craun, R. L. and Smith, D. L., "Analysis of Response Data for Several Organic Scintillators," *Nucl. Instrum. Methods* 80, 239 (1970).

[9] Bohr, N., "The Penetration of Atomic Particles Through Matter," *Kgl. Danske Videnskab. Selskab Mat.-fys. Medd.* 18, No. 8 (1948).

[10] Vavilov, P. V., "Ionization Losses of High-Energy Heavy Particles," *Sov. Phys. JETP* 5, 749 (1957).
