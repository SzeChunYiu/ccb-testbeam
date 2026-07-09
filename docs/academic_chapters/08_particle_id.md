# Chapter 8: Particle Identification — Proton-Deuteron Separation by Delta-E/E

## Abstract

The HRD scintillator range telescopes function as deltaE-E detectors: the pattern of energy deposition across successive staves encodes the particle species through the Bethe-Bloch stopping power. This chapter presents the proton-deuteron separation analysis using the deltaE-E plane constructed from B2 (deltaE analogue) and B4 (E analogue) energy depositions, the stopping-depth method as an independent particle-ID observable, and the Monte Carlo truth ceiling for achievable separation performance. The traditional single-cut method achieves AUC = 0.891; logistic regression on energy deposition features reaches AUC = 0.963; and the Monte Carlo truth ceiling (histogram gradient boosting on truth features) reaches AUC = 0.986 with purity 0.964 at 90% deuteron efficiency. Data-only PID methods are limited by the absence of per-event truth labels and must rely on sample-level enrichment statistics.

---

## 1. The Delta-E/E Method

### 1.1 Physical principle

When a charged particle traverses a thin detector layer, the energy deposited in that layer (deltaE) is proportional to the specific energy loss dE/dx multiplied by the layer thickness. For particles of different mass but the same kinetic energy, the specific energy loss differs according to the Bethe-Bloch formula. In the non-relativistic limit (valid for 100-200 MeV protons and deuterons, where beta approximately 0.5-0.6):

dE/dx = (4 pi N_A r_e^2 m_e c^2 z^2 / beta^2) * (Z/A) * [ln(2 m_e c^2 beta^2 gamma^2 / I) - beta^2]

where z is the particle charge (z = 1 for both protons and deuterons), beta = v/c, gamma = 1/sqrt(1-beta^2), Z and A are the atomic number and mass of the absorber (Z approximately 5.4, A approximately 12 for BC-408 plastic scintillator), I is the mean excitation energy (approximately 65 eV for plastic scintillator), and the constants have their usual meanings.

For the same kinetic energy T, a deuteron has beta_d = sqrt(1 - (m_d c^2 / (T + m_d c^2))^2) = sqrt(1 - (1875.6 / (T + 1875.6))^2), while a proton has beta_p = sqrt(1 - (938.3 / (T + 938.3))^2). For T = 100 MeV, beta_d = 0.314 and beta_p = 0.428. The 1/beta^2 term in dE/dx gives (1/0.314^2) / (1/0.428^2) = 1.86: deuterons deposit approximately 1.86 times more energy per unit path length than protons at the same kinetic energy. This factor increases at lower energies (as both particles approach their Bragg peaks) and decreases at higher energies (as both approach minimum ionisation near beta approximately 0.96, where dE/dx is nearly species-independent).

The deltaE-E method exploits this mass-dependent energy loss: the energy deposited in the first traversed stave (B2, the deltaE analogue) is correlated with the residual range or the energy deposited in subsequent staves (B4, the E analogue), producing distinct loci for protons and deuterons in the deltaE-E plane.

### 1.2 Construction in the HRD B-stack

For the B-stack, the deltaE-E plane is constructed from per-event pairs of B2 and B4 pulse amplitudes. An event must have a selected pulse in both B2 and B4 to enter the deltaE-E plane. This requirement introduces a selection bias: events where the particle stops in B2 (no B4 hit) are excluded, removing the most heavily ionising deuterons (those at the Bragg peak in B2) from the deltaE-E sample. The B2-vs-B4 correlation is therefore dominated by through-going protons and the higher-energy tail of the deuteron distribution.

The B2 amplitude serves as the deltaE analogue because it is the first stave encountered by particles entering the B-stack. The B4 amplitude serves as the E analogue because particles that reach B4 have passed through B2 and the intervening passive material (B3), and their residual energy at B4 is correlated with their incident energy. The correlation between B2 and B4 amplitudes is modest (Pearson r approximately 0.50 for Sample II, 0.07 for Sample I) because of the large position-dependent light collection variations in the one-ended WLS readout, which uncorrelated the B2 and B4 amplitudes even for the same particle.

### 1.3 Traditional single-cut method

The simplest particle-ID method places a threshold on the B2 amplitude: pulses with B2 amplitude above the threshold are classified as deuterons (higher dE/dx -> larger B2 signal), and pulses below the threshold are classified as protons. The threshold is optimised on the full dataset by maximising the Fisher discriminant:

J(A_thr) = (mu_d - mu_p)^2 / (sigma_d^2 + sigma_p^2)

where mu_d and sigma_d are the mean and standard deviation of the log(B2 amplitude) for deuterons (identified by stopping in B2 or B4), and mu_p and sigma_p are the corresponding quantities for protons (identified by penetrating to B6 or B8). The log-transform reduces the skewness of the amplitude distribution.

The optimised threshold yields:

- AUC = 0.891 (area under the ROC curve for deuteron vs proton classification)
- Purity at 90% deuteron efficiency = 0.891

The single-cut method is limited by the overlap between the proton and deuteron B2 amplitude distributions: while deuterons do produce larger B2 signals on average, the position-dependent light collection in the one-ended readout broadens both distributions, and there is a substantial overlap region where the B2 amplitude alone cannot distinguish the species.

### 1.4 Multi-feature classification

Logistic regression trained on four features — B2 amplitude, B4 amplitude, total energy deposition (sum of B2+B4+B6+B8 where available), and stopping depth (deepest stave with signal above 1000 ADC) — achieves improved separation:

- AUC = 0.963
- Purity at 90% deuteron efficiency = 0.949

The improvement arises because the multi-feature classifier can exploit the correlations between staves: a particle with large B2 amplitude AND small B4 amplitude is likely a deuteron that stopped in or near B2, while a particle with moderate B2 amplitude AND substantial B4+B6+B8 signals is likely a through-going proton. The logistic regression learns the optimal linear combination of these features.

### 1.5 Monte Carlo truth ceiling

Study MV1 (Chapter 10) establishes the achievable ceiling for proton-deuteron separation by training a histogram gradient boosting classifier on MC truth features: EDep in layers 0-3, stopping layer, total EDep, and track length. The truth labels (PDG code) are known exactly from the GEANT4 simulation. The results:

- AUC = 0.986
- Purity at 90% deuteron efficiency = 0.964

The MC truth ceiling of AUC = 0.986 represents the best possible performance that any data-driven method can aspire to, given the intrinsic overlap between proton and deuteron energy deposition distributions arising from the continuous nature of the Bethe-Bloch energy loss, range straggling, and position-dependent light collection. The gap between the data-only logistic regression (AUC = 0.963) and the MC truth ceiling (AUC = 0.986) represents the irreducible loss from not having per-event truth labels in data.

---

## 2. Stopping-Depth Method

### 2.1 Independent PID observable

The stopping depth — the deepest stave in which a particle deposits energy above threshold — provides a particle-ID observable that is independent of the ADC amplitude and therefore robust against saturation and position-dependent light collection. The physical principle is the same as the range telescope: deuterons have shorter range than protons at the same kinetic energy, so a particle that stops in B2 or B4 is more likely to be a deuteron, while a particle that reaches B6 or B8 is more likely to be a proton.

### 2.2 Stopping-depth distributions

The Monte Carlo truth stopping-depth distributions for Sample I and Sample II (from the trigger-split analysis, `mc01_trigger_split_truth.py`) quantify the species separation:

**Sample I (coincidence trigger, deuteron-enriched):**
- Deuterons: mean stop layer = 0.8, distribution = {B2: 20,374, B4: 37,521, B6: 2,043, B8: 1,710 (sum of deeper)}
- Protons: mean stop layer = 2.6, distribution = {B2: 4,450, B4: 2,996, B6: 924, B8: 4,686}

**Sample II (single-B trigger, proton-dominated):**
- Deuterons: mean stop layer = 1.2, distribution = {B2: 38,021, B4: 71,139, B6: 9,010, B8: 27,664}
- Protons: mean stop layer = 4.3, distribution = {B2: 16,674, B4: 14,863, B6: 11,288, B8: 95,049}

In Sample I, deuterons are 4.6 times more numerous than protons among B2-stopping particles (20,374 / 4,450). In Sample II, deuterons are still 2.3 times more numerous (38,021 / 16,674) but the proton contamination at B2 is significantly larger. The stopping-depth method achieves its best separation in Sample I, where the coincidence trigger pre-enriches the deuteron population.

### 2.3 Combined PID strategy

The recommended particle-ID strategy for the HRD analysis combines the deltaE-E method and the stopping-depth method:

1. **Deuteron candidate:** Particle stops in B2 or B4 (stopping depth <= 1) AND has B2 amplitude above the optimised threshold OR the logistic regression deuteron probability > 0.5.
2. **Proton candidate:** Particle reaches B6 or B8 (stopping depth >= 2) OR has B2 amplitude below the optimised threshold AND the logistic regression proton probability > 0.5.
3. **Ambiguous:** Particles that satisfy neither criterion (approximately 5-10% of events) are excluded from particle-dependent analyses.

The combined method achieves purity > 0.90 at efficiency > 0.85 for both species in Sample I, and purity > 0.80 at efficiency > 0.80 in Sample II, where the lower deuteron enrichment makes the classification more challenging.

---

## References

[1] Bethe, H., "Zur Theorie des Durchgangs schneller Korpuskularstrahlen durch Materie," Ann. Phys. 397, 325-400 (1930).

[2] Goulding, F. S. and Harvey, B. G., "Identification of Nuclear Particles," Annu. Rev. Nucl. Sci. 25, 167-240 (1975).

[3] Particle Data Group, "Review of Particle Physics: Passage of Particles Through Matter," Prog. Theor. Exp. Phys. 2022, 083C01 (2022).
