# Chapter 8: Particle Identification — Proton-Deuteron Separation by Delta-E/E

## Abstract

The HRD scintillator range telescopes function as deltaE-E detectors: the pattern of energy deposition across successive staves encodes the particle species through the Bethe-Bloch stopping power. This chapter presents the proton-deuteron separation analysis for the CCB test beam using three complementary approaches: (1) the traditional deltaE-E method with a single-cut threshold on the B2 amplitude, (2) multi-feature logistic regression on energy deposition observables, and (3) the stopping-depth method as an independent particle-ID observable orthogonal to ADC amplitude. The Bethe-Bloch formula is derived in full and evaluated numerically for protons and deuterons at the beam energy (190 MeV) and at their Bragg peaks. The deltaE-E plane is constructed from correlated B2 (deltaE analogue) and B4 (E analogue) pulse amplitudes; the selection bias introduced by requiring hits in both staves is quantified. The single-cut threshold is optimised via Fisher discriminant on log-transformed B2 amplitudes, yielding AUC = 0.891. Logistic regression trained on four features (B2 amplitude, B4 amplitude, total deposited energy, and stopping depth) achieves AUC = 0.963. The Monte Carlo truth ceiling, established by training a histogram gradient boosting classifier on GEANT4 truth features with known PDG labels (Study MV1, Chapter 10), reaches AUC = 0.986 with purity 0.964 at 90% deuteron efficiency. The stopping-depth method, analysed from MC truth distributions produced by `mc01_trigger_split_truth.py`, provides an independent PID handle: deuterons peak at mean stop layer 0.8 (Sample I) or 1.2 (Sample II), while protons peak at 2.6 (Sample I) or 4.3 (Sample II). A combined decision-tree strategy integrates deltaE-E and stopping-depth information, achieving purity above 0.90 at efficiency above 0.85 for both species in the deuteron-enriched Sample I. Data-only PID methods are limited by the absence of per-event truth labels and must rely on sample-level enrichment statistics; the gap between data-only logistic regression (AUC = 0.963) and the MC truth ceiling (AUC = 0.986) represents the irreducible information loss from not having per-event truth labels.

---

## 1. Theoretical Foundation: The Bethe-Bloch Formula

### 1.1 Full formula and term-by-term decomposition

The mean rate of energy loss per unit path length for a heavy charged particle traversing matter is given by the Bethe-Bloch formula. For moderately relativistic particles (beta-gamma between approximately 0.1 and 1000), where density-effect and shell corrections are small, the full expression reads:

$$\left\langle -\frac{dE}{dx} \right\rangle = K z^2 \frac{Z}{A} \frac{1}{\beta^2} \left[ \frac{1}{2} \ln\left(\frac{2 m_e c^2 \beta^2 \gamma^2 T_{\text{max}}}{I^2}\right) - \beta^2 - \frac{\delta(\beta\gamma)}{2} - \frac{C}{Z} \right]$$

where the prefactor is:

$$K = 4\pi N_A r_e^2 m_e c^2$$

The terms are, in order of appearance:

- **K (constant prefactor):** $K = 4\pi N_A r_e^2 m_e c^2 = 0.307075$ MeV cm^2 mol^{-1}. Here $N_A = 6.02214 \times 10^{23}$ mol^{-1} is Avogadro's number, $r_e = e^2/(4\pi\varepsilon_0 m_e c^2) = 2.81794 \times 10^{-15}$ m is the classical electron radius, and $m_e c^2 = 0.510999$ MeV is the electron rest energy. This prefactor collects the fundamental constants governing electromagnetic interactions between the projectile and atomic electrons.

- **z (projectile charge):** The charge number of the incident particle in units of the elementary charge. For both protons and deuterons, z = 1. The quadratic dependence, $z^2$, means that particles with the same charge but different masses experience the same Bethe-Bloch energy loss at the same velocity beta. The mass enters indirectly through the relationship between kinetic energy and beta.

- **Z (target atomic number):** The mean atomic number of the absorber material. For BC-408 plastic scintillator (polyvinyltoluene base, chemical formula approximately CH_{1.1}), the effective Z is approximately 3.4, calculated as the number-of-electrons-weighted average: $Z_{\text{eff}} = \sum_i w_i Z_i$, where the sum runs over all elements weighted by their electron fraction.

- **A (target atomic mass):** The mean atomic mass of the absorber, approximately 6.4 g/mol for BC-408. The $Z/A$ ratio is approximately 0.53 for BC-408, close to the value of 0.5 expected for hydrogen-rich organic materials.

- **beta = v/c:** The projectile velocity in units of the speed of light. The dominant $1/\beta^2$ term means that slower particles deposit more energy per unit path length. This is the physical origin of the Bragg peak: as the particle slows down near the end of its range, beta decreases sharply and dE/dx rises rapidly. In the non-relativistic limit, beta is related to kinetic energy T by:

  $$\beta = \sqrt{1 - \left(\frac{m c^2}{T + m c^2}\right)^2}$$

  For a proton of rest mass $m_p c^2 = 938.272$ MeV at T = 190 MeV, $\beta_p = \sqrt{1 - (938.272 / 1128.272)^2} = 0.546$. For a deuteron of rest mass $m_d c^2 = 1875.613$ MeV at the same kinetic energy, $\beta_d = \sqrt{1 - (1875.613 / 2065.613)^2} = 0.380$. The ratio of $1/\beta^2$ values is $(1/0.380^2) / (1/0.546^2) = 2.07$: deuterons deposit approximately twice as much energy per unit path length as protons at 190 MeV, solely from the beta-dependence of the Bethe-Bloch formula.

- **$T_{\text{max}}$ (maximum energy transfer):** The maximum kinetic energy that can be imparted to a free electron in a single collision, given in the relativistic limit by:

  $$T_{\text{max}} = \frac{2 m_e c^2 \beta^2 \gamma^2}{1 + 2\gamma m_e/m + (m_e/m)^2}$$

  For proton impacts on electrons, the denominator is dominated by the electron-to-projectile mass ratio. At T = 190 MeV ($\beta_p = 0.546$, $\gamma_p = 1.191$): $T_{\text{max}} \approx 2 \times 0.511 \times 0.546^2 \times 1.191^2 / 0.001089 \approx 415$ keV. For deuterons at the same kinetic energy ($\beta_d = 0.380$, $\gamma_d = 1.081$): $T_{\text{max}} \approx 2 \times 0.511 \times 0.380^2 \times 1.081^2 / 0.000545 \approx 335$ keV. The smaller $T_{\text{max}}$ for deuterons arises from the smaller beta at equal kinetic energy.

- **I (mean excitation energy):** The mean excitation energy of the absorber, representing the geometric mean of all atomic transition energies weighted by oscillator strength. For plastic scintillator, I is approximately 64.7 eV, calculated via the Bragg additivity rule: $\ln I = \sum_i w_i \ln I_i$, where $w_i$ are the electron fractions and $I_i$ are the elemental excitation energies ($I_H = 19.2$ eV, $I_C = 78.0$ eV). The logarithmic dependence on I means that the energy loss is only weakly sensitive to the precise value of this parameter (a 10% error in I produces approximately a 1% error in dE/dx at beta = 0.5).

- **delta(beta-gamma)/2 (density-effect correction):** The density effect arises from the polarisation of the medium by the projectile's electric field, which screens the distant collisions and reduces the energy loss. The correction becomes significant above beta-gamma of approximately 3-4. At the beam energy of 190 MeV, $\beta\gamma_p = 0.546 \times 1.191 = 0.650$ and $\beta\gamma_d = 0.380 \times 1.081 = 0.411$. Both values are well below the threshold where the density effect becomes appreciable (typically beta-gamma > 2-3 for plastics), so $\delta/2 \approx 0$ for the present analysis. We neglect this correction throughout.

- **C/Z (shell correction):** The shell correction accounts for the breakdown of the free-electron approximation when the projectile velocity is comparable to or less than the orbital velocities of the target electrons. At beta = 0.5, the shell correction is approximately 0.02-0.05 for carbon, i.e. a 2-5% reduction in dE/dx. For the CCB analysis, shell corrections are included implicitly through the GEANT4 simulation (which uses a parametrised implementation) but are omitted from the analytic estimates below for clarity.

### 1.2 Numerical evaluation at 190 MeV and at the Bragg peak

Applying the Bethe-Bloch formula with shell and density corrections set to zero, and taking Z/A = 0.53 and I = 64.7 eV:

**Proton at T = 190 MeV** ($\beta_p = 0.546$, $\gamma_p = 1.191$, $\beta\gamma_p = 0.650$):

$$\left\langle -\frac{dE}{dx} \right\rangle_p = 0.3071 \times 1^2 \times 0.53 \times \frac{1}{0.546^2} \left[ \frac{1}{2} \ln\left(\frac{2 \times 0.511 \times 0.546^2 \times 1.191^2 \times 0.415}{64.7^2 \times 10^{-12}}\right) - 0.546^2 \right]$$

Evaluating the logarithmic argument: $2 \times 0.511 \times 0.546^2 \times 1.191^2 \times 0.415 / (4.186 \times 10^{-9}) \approx 1.45 \times 10^7$. Then $\frac{1}{2}\ln(1.45 \times 10^7) = 8.23$, and subtracting $\beta^2 = 0.298$ gives the bracketed term $8.23 - 0.298 = 7.93$. Multiplying through: $0.3071 \times 0.53 \times (1/0.298) \times 7.93 = 0.3071 \times 0.53 \times 3.36 \times 7.93 = 4.33$ MeV cm^2/g.

Converting to linear energy loss in BC-408 (density $\rho = 1.032$ g/cm^3): $dE/dx = 4.33 \times 1.032 = 4.47$ MeV/cm. For a stave thickness of approximately 2.0 cm, the expected energy deposition is approximately 8.9 MeV for a minimum-ionising-like proton at 190 MeV, assuming perpendicular incidence.

**Deuteron at T = 190 MeV** ($\beta_d = 0.380$, $\gamma_d = 1.081$, $\beta\gamma_d = 0.411$):

The slower velocity enters via $1/\beta^2 = 1/0.1446 = 6.92$, giving a mass stopping power approximately 2.06 times larger than for protons at the same kinetic energy. However, the logarithmic term also shifts: the smaller $T_{\text{max}}$ (335 keV vs 415 keV) reduces the log argument, while the smaller $\beta\gamma$ further compresses the relativistic rise. Evaluating: bracketed term $\approx 7.65$, giving $0.3071 \times 0.53 \times 6.92 \times 7.65 \approx 8.63$ MeV cm^2/g, and $dE/dx \approx 8.63 \times 1.032 = 8.91$ MeV/cm. For the same 2.0 cm stave, the expected energy deposition is approximately 17.8 MeV -- roughly twice the proton value.

**At the Bragg peak:** As the particle approaches the end of its range, beta drops to approximately 0.05-0.10, and $1/\beta^2$ grows to 100-400. The Bethe-Bloch formula in this regime (beta < 0.1) requires the low-energy correction, where the simple $z^2$ proportionality breaks down due to charge exchange (electron capture and loss). The practical result is that the Bragg peak dE/dx is approximately 5-8 times the value at the beam entrance energy. For a 190 MeV proton, the Bragg peak occurs at a residual range of approximately 0.05 mm in BC-408, with $dE/dx_{\text{peak}} \approx 25$ MeV/cm. For a deuteron of 190 MeV, the Bragg peak occurs at a much shorter residual range because deuterons have only approximately half the range of protons at the same kinetic energy (range scales approximately as $m/z^2$ in the non-relativistic regime: $R_d/R_p \approx (m_d/m_p) \times (z_p/z_d)^2 = 2.0$).

### 1.3 The mass-dependent separation principle

The essential point for particle identification is that for a given kinetic energy T, the energy deposition ratio between deuterons and protons is:

$$\frac{(dE/dx)_d}{(dE/dx)_p} \approx \frac{\beta_p^2}{\beta_d^2} \times \frac{[\ln(...) - \beta_d^2]}{[\ln(...) - \beta_p^2]}$$

The dominant factor is $\beta_p^2 / \beta_d^2$, which for a given T is:

$$\frac{\beta_p^2}{\beta_d^2} = \frac{1 - \left(\frac{m_p c^2}{T + m_p c^2}\right)^2}{1 - \left(\frac{m_d c^2}{T + m_d c^2}\right)^2}$$

In the low-energy limit ($T \ll m c^2$), $\beta \approx \sqrt{2T/m}$ and the ratio approaches $m_d/m_p = 2.0$. In the high-energy limit ($T \gg m c^2$), $\beta \to 1$ for both species and the separation disappears -- all singly charged particles converge to the minimum-ionising value of approximately 2 MeV cm^2/g at $\beta\gamma \approx 3-4$. The CCB test beam operates in the intermediate regime where the mass separation is approximately a factor of 2, providing usable but incomplete separation between proton and deuteron energy deposition distributions.

---

## 2. The Delta-E/E Method

### 2.1 Physical principle and kinematic mapping

The delta-E/E method, originally developed for silicon detector telescopes (Goulding and Harvey, 1975), identifies particle species by measuring the differential energy loss $\Delta E$ in a thin transmission detector followed by the residual energy $E$ in a thick stopping detector. The product $\Delta E \times E$ is approximately proportional to $m z^2$, providing a mass-identifying signature independent of the incident kinetic energy (over a limited range).

In the HRD B-stack, the method is adapted to the multi-layer scintillator geometry. A particle traversing the first instrumented stave (B2) deposits a fraction of its kinetic energy proportional to $dE/dx \times t_{\text{eff}}$, where $t_{\text{eff}}$ is the effective path length through the scintillator (including the effect of incidence angle). The residual energy available for deposition in subsequent staves (B4, B6, B8) is the original kinetic energy minus the energy lost in all preceding material. If the particle stops before reaching B4, no B4 signal is produced; if it punches through to B8, the pattern of energy deposition across the B2-B4-B6-B8 chain encodes the incident kinetic energy and particle species.

For a particle of mass m and kinetic energy $T_0$ entering B2, the energy deposited in B2 is $\Delta E = (dE/dx)|_{T_0} \times t_{\text{B2}}$, and the residual energy at the exit of B2 is $T_1 = T_0 - \Delta E - \Delta E_{\text{passive}}$, where $\Delta E_{\text{passive}}$ accounts for energy lost in the inter-stave air gaps (approximately 5 mm), the scintillator wrapping, and the B3 passive stave. The energy deposited in B4 is then $E_{\text{B4}} = (dE/dx)|_{T_1} \times t_{\text{B4}}$.

For a thin transmission detector where $\Delta E \ll T_0$, the Bethe-Bloch formula can be Taylor-expanded to give:

$$\Delta E \cdot E \propto m z^2 \times f(T_0)$$

where $f(T_0)$ is a slowly varying function of the incident energy. This product rule is approximate for thick scintillator staves where $\Delta E$ can be a substantial fraction of $T_0$ (up to 50% for low-energy deuterons stopping in B4), but the qualitative separation -- deuterons produce larger $\Delta E$ in B2 and smaller $E$ in B4 for a given total kinetic energy -- remains valid.

### 2.2 Construction in the HRD B-stack

The deltaE-E plane is constructed from per-event pairs of B2 and B4 pulse amplitudes. B2 (the first instrumented stave in the B-stack; B0 is the passive trigger scintillator) serves as the deltaE analogue because it is the first scintillator layer encountered by particles entering the B-stack. B4 (two staves downstream, behind the passive B3) serves as the E analogue because it samples the residual energy after passage through B2 and the intervening material.

The assignment B2 = deltaE and B4 = E is a geometric convention of the B-stack numbering: B0 is a trigger scintillator (not in the data stream for the HRD DAQ), B1 does not exist in the naming scheme (the staves are numbered B0, B2, B4, B6, B8 in the hardware convention), B2 is the first HRD-instrumented stave, B3 is a passive (uninstrumented) stave, and B4 is the second instrumented stave. The one-stave gap between B2 and B4 is intrinsic to the hardware design and means that B4 does not measure the immediate post-B2 residual energy but rather the energy after passage through one additional passive layer.

An event must have a selected pulse in both B2 and B4 to enter the deltaE-E plane. This requirement introduces a selection bias of two kinds:

1. **Stopping deuteron exclusion:** Deuterons that stop in B2 (i.e. whose range is insufficient to reach B4) produce a large B2 signal but no B4 signal. These are the most heavily ionising deuterons, those at or near their Bragg peak in B2, and their exclusion from the deltaE-E sample removes the very events that would provide the cleanest deuteron signature. In Sample I (MC truth), approximately 33% of deuterons stop in B2 (stop layer 0); only those that punch through to B4 or beyond enter the deltaE-E plane.

2. **Angular and geometric acceptance:** Particles with shallow incidence angles may traverse B2 but miss B4 due to the finite transverse size of the staves or the inter-stave alignment. This introduces an acceptance function that depends on the beam optics and contributes a systematic uncertainty to the species fractions extracted from the deltaE-E plane.

The consequence of this selection bias is visible in the correlation structure of the deltaE-E plane. For Sample I (coincidence trigger, deuteron-enriched), the B2-B4 Pearson correlation coefficient is $r \approx 0$ (MC truth, `mc01_trigger_split_truth.py`). This near-zero correlation is a direct consequence of the selection bias: deuterons that punch through B2 to reach B4 are a narrow sub-population with energy deposition near the minimum-ionising end of the B2 distribution, and their B2 energy deposition is essentially uncorrelated with their B4 deposition because both are near the minimum in dE/dx (where the dependence on beta is weakest). For Sample II (single-B trigger, proton-dominated), the B2-B4 correlation is $r \approx 0.5$, because through-going protons produce a genuine kinematic correlation between the energy deposited in successive staves.

Figure 1 (`docs/figures_ch1/deltaE_E_overview.png`) shows the deltaE-E scatter plot with colour-coded species labels from MC truth, illustrating the separation between the proton and deuteron loci and the substantial overlap region.

### 2.3 Traditional single-cut method

The simplest particle-ID method places a threshold on the B2 amplitude: pulses with B2 amplitude above the threshold are classified as deuterons (higher dE/dx yields larger B2 signal), and pulses below the threshold are classified as protons. This method is the baseline against which all more sophisticated classifiers are compared.

#### 2.3.1 Fisher discriminant derivation

The optimal single-cut threshold is found by maximising the Fisher discriminant ratio:

$$J(A_{\text{thr}}) = \frac{(\mu_d - \mu_p)^2}{\sigma_d^2 + \sigma_p^2}$$

where $\mu_d$ and $\sigma_d$ are the mean and standard deviation of the log-transformed B2 amplitude for deuteron-labelled events, and $\mu_p$ and $\sigma_p$ are the corresponding quantities for proton-labelled events. The log-transform is applied because the B2 amplitude distribution is positively skewed for both species (the Landau-like tail of the energy loss distribution plus the exponential tail from the WLS light collection); the log-transform symmetrises the distributions and makes the Gaussian-separation assumption of the Fisher discriminant more appropriate.

Why the log-transform? The energy loss distribution for a thin detector is described by a Landau distribution (or the Vavilov distribution for intermediate thickness), which has a long tail toward high energy depositions from rare large-energy-transfer collisions. The convolution with the exponential WLS light-collection distribution (the one-ended readout produces a position-dependent amplitude scaling that is approximately exponential in the distance from the SiPM) produces a distribution that is log-normal to first order. Taking the logarithm converts the multiplicative readout variations into additive offsets and compresses the high-energy tail.

Let $x = \ln(\text{B2 amplitude})$. The threshold $x_{\text{thr}}$ that maximises $J$ is:

$$x_{\text{thr}} = \frac{\mu_d \sigma_p^2 - \mu_p \sigma_d^2}{\sigma_p^2 - \sigma_d^2} + \sqrt{\frac{\sigma_p^2 \sigma_d^2 (\mu_d - \mu_p)^2}{(\sigma_p^2 - \sigma_d^2)^2} + \frac{2 \sigma_p^2 \sigma_d^2}{\sigma_p^2 - \sigma_d^2} \ln\left(\frac{\sigma_p}{\sigma_d}\right)}$$

In the equal-variance limit ($\sigma_p = \sigma_d$), this reduces to the midpoint: $x_{\text{thr}} = (\mu_d + \mu_p)/2$. In practice, the deuteron distribution is wider ($\sigma_d > \sigma_p$) because the B2 energy deposition for deuterons spans a larger dynamic range (from minimum-ionising punch-through deuterons to stopping deuterons near their Bragg peak), so the optimal threshold is shifted slightly below the midpoint to capture more of the broad deuteron distribution.

#### 2.3.2 Results

The optimised threshold applied to the data yields:

- **AUC = 0.891** (area under the ROC curve for deuteron vs proton classification, evaluated against sample-level enrichment labels where the "truth" is defined by the trigger condition: Sample I events are predominantly deuteron, Sample II events are predominantly proton)
- **Purity at 90% deuteron efficiency = 0.891**

The single-cut method is limited by two factors. First, the B2 amplitude distributions for protons and deuterons overlap substantially because the continuously varying energy loss (even for a single species at a single energy, the Landau fluctuations produce an approximately 20% RMS spread) broadens each distribution. Second, the position-dependent light collection in the one-ended WLS readout introduces an additional multiplicative spread of approximately 30-40% (Chapter 7), further smearing the distributions. The combination produces an overlap region where B2 amplitude alone cannot distinguish the species.

---

## 3. Multi-Feature Classification via Logistic Regression

### 3.1 Feature engineering

Logistic regression extends the single-cut method by incorporating additional observables that carry species-discriminating information. Four features are constructed per event:

1. **B2 amplitude (deltaE analogue):** The pulse amplitude in ADC counts in the B2 stave. This is the same observable used in the single-cut method, capturing the specific energy loss in the first traversed stave.

2. **B4 amplitude (E analogue):** The pulse amplitude in ADC counts in the B4 stave. For particles that reach B4, this carries information about the residual energy after B2 and the intervening material. Deuterons that punch through to B4 typically have smaller B4 amplitudes than through-going protons of the same incident energy, because the deuteron's larger dE/dx in B2 leaves less residual energy for B4.

3. **Total energy deposition:** The sum of pulse amplitudes across B2, B4, B6, and B8 (where available; missing staves contribute zero). This approximates the total energy deposited in the B-stack and is correlated with the incident kinetic energy. For stopping particles, the total deposited energy is equal to the incident kinetic energy (plus the energy lost in passive material). For through-going particles, it is the energy lost in the instrumented portion of the stack.

4. **Stopping depth:** The deepest stave with a pulse amplitude above threshold (1000 ADC, approximately 4 MeV equivalent). Encoded as an integer: 0 = B2, 1 = B4, 2 = B6, 3 = B8, 4 = beyond B8. This is the categorical analogue of the continuous range measurement and provides species information independent of the ADC amplitude (being determined by the pattern of which staves fire, not by how much energy they record).

### 3.2 Training protocol

The logistic regression is trained using a leave-one-run-out (LORO) cross-validation protocol. The dataset comprises N runs from the CCB test-beam campaign. For each fold i:

1. **Training set:** All events from all runs except run i.
2. **Validation set:** All events from run i.
3. **Model:** Logistic regression (scikit-learn `LogisticRegression`, L2 regularisation with $C = 1.0$, `lbfgs` solver, maximum 1000 iterations).
4. **Labels:** Because per-event truth labels do not exist in data, the training uses run-level enrichment as a proxy: events from Sample I runs (coincidence trigger) are labelled as deuteron (class 1), and events from Sample II runs (single-B trigger) are labelled as proton (class 0). This label assignment is correct for approximately 80-85% of events (the purity of the trigger selection, as estimated from MC truth), meaning the logistic regression is trained on noisy labels and its performance is inherently limited by the label purity.
5. **Evaluation:** The trained model predicts class probabilities for the held-out run. The ROC curve, AUC, and purity-vs-efficiency curves are computed from the LORO predictions pooled across all folds.

The LORO protocol is chosen over k-fold cross-validation because runs are temporally separated and may differ in beam conditions (rate, energy spread, detector gain drift). Mixing events from the same run across train and validation splits would inflate the apparent performance by allowing the model to memorise run-specific features (e.g., a gain shift). LORO ensures that the evaluation measures genuine generalisation to unseen run conditions.

### 3.3 Results

The logistic regression classifier achieves:

- **AUC = 0.963**
- **Purity at 90% deuteron efficiency = 0.949**

The improvement over the single-cut method (AUC 0.891 to 0.963) arises from the model's ability to exploit correlations between staves. Consider two event topologies:

- A particle with large B2 amplitude AND small B4 amplitude AND stopping in B4: the logistic regression assigns high deuteron probability because all three features point toward a high-dE/dx, short-range particle.

- A particle with moderate B2 amplitude AND substantial B4+B6+B8 signals AND stopping beyond B8: the logistic regression assigns high proton probability because the long range and moderate energy deposition in each stave are characteristic of a minimum-ionising through-going proton.

The single-cut method, using only B2 amplitude, cannot distinguish these topologies because the B2 amplitude alone does not encode whether the particle stopped or punched through. The logistic regression learns the optimal linear combination of features that maximises the Fisher separation in the four-dimensional feature space, equivalent to finding the hyperplane that best separates the deuteron and proton populations under the noisy-label constraint.

---

## 4. Monte Carlo Truth Ceiling

### 4.1 Study MV1 overview

Study MV1 (Chapter 10, Section 2) establishes the achievable ceiling for proton-deuteron separation by training classifiers on Monte Carlo truth features with exact per-event species labels (PDG code from GEANT4). This removes the label-noise limitation of data-only methods and answers the question: how well could we separate protons and deuterons if we knew the species of every event?

### 4.2 HGB architecture and hyperparameters

The MV1 classifier is a histogram gradient boosting (HGB) model, chosen for its ability to capture non-linear feature interactions without the extensive hyperparameter tuning required by deep neural networks. HGB bins continuous features into histograms (256 bins per feature) and builds an ensemble of decision trees via gradient boosting on the logistic loss. The architecture and hyperparameters:

- **Base estimator:** Histogram-based gradient boosting classifier (`scikit-learn HistGradientBoostingClassifier`)
- **Loss function:** Binary cross-entropy (logistic loss)
- **Learning rate:** 0.1
- **Maximum iterations:** 100 (with early stopping on a 20% validation split, patience = 10)
- **Maximum depth:** None (trees are grown until leaves are pure, with `min_samples_leaf = 20` providing the stopping criterion)
- **L2 regularisation:** 0.0 (no explicit regularisation; early stopping and the `min_samples_leaf` constraint provide implicit regularisation)
- **Maximum bins:** 255 (the default; each continuous feature is binned into at most 255 unique values for split finding)
- **Feature set:** EDep in layers 0-3 (B2, B4, B6, B8 energy deposition in MeV), stopping layer (integer 0-7), total EDep (sum of energy depositions in MeV), and track length (total path length through the scintillator in mm)

### 4.3 Training data and evaluation

The training data consist of 1 million GEANT4 events processed through the B-stack truth tree, filtered to require at least one charged hit in B2. The train/test split is 80/20, stratified by PDG code to preserve the natural species proportions. The evaluation is performed on the held-out test set, where the truth labels are known exactly.

### 4.4 Results and interpretation

The HGB classifier achieves:

- **AUC = 0.986**
- **Purity at 90% deuteron efficiency = 0.964**

The AUC of 0.986 means that for a randomly chosen deuteron and a randomly chosen proton, the classifier assigns a higher deuteron probability to the deuteron 98.6% of the time. This is the maximum achievable separation given the intrinsic overlap between proton and deuteron energy deposition distributions. The remaining 1.4% of AUC shortfall (from the perfect value of 1.000) represents the irreducible confusion arising from three sources:

1. **Landau fluctuations:** The continuous nature of the Bethe-Bloch energy loss means that a proton can, with low probability, deposit as much energy in a given layer as a typical deuteron (the high-energy tail of the proton Landau distribution overlapping with the core of the deuteron distribution).

2. **Range straggling:** The statistical nature of energy loss produces an approximately 2-3% (RMS/mean) spread in the range of mono-energetic particles. This means that a proton with a downward fluctuation in total energy loss can stop at the same depth as a typical deuteron, and vice versa.

3. **Position-dependent light collection:** Even in the MC (where the light collection model is simplified compared to the full digitizer), the geometric acceptance and energy deposition variations with incidence angle produce event-to-event fluctuations that degrade the separation.

The gap between the data-only logistic regression (AUC = 0.963) and the MC truth ceiling (AUC = 0.986) represents the combined cost of: (a) noisy training labels (run-level enrichment instead of per-event truth), (b) ADC-based features instead of energy-calibrated features, and (c) the linear decision boundary of logistic regression versus the non-linear decision boundary of HGB. Of these, the noisy-label cost is the dominant term (estimated at approximately 0.015-0.020 AUC units), followed by the linear-vs-nonlinear cost (approximately 0.005-0.008 AUC units). The ADC-vs-energy cost is small in the MC (where the digitizer provides energy-calibrated ADC), but in data the 30% gain calibration uncertainty (Chapter 7) introduces additional systematic spread.

---

## 5. Stopping-Depth Method

### 5.1 Physical principle

The stopping depth -- the deepest stave in which a particle deposits energy above threshold -- provides a particle-ID observable that is independent of the ADC amplitude. Unlike the deltaE-E method, which relies on energy deposition magnitudes and is therefore sensitive to position-dependent light collection, gain variations, and saturation, the stopping depth is a binary yes/no observable at each stave: did the particle fire this stave or not? The only free parameter is the firing threshold (set at 1000 ADC, approximately 4 MeV, well above the SiPM dark-count baseline of approximately 50 ADC equivalent but well below the minimum energy deposition of a minimum-ionising particle traversing 2 cm of BC-408, approximately 4-5 MeV), and the result is robust to gain drifts of up to a factor of 2 (as long as the threshold remains between the noise floor and the minimum signal).

The physical principle is the range-energy relation: deuterons, with their larger energy loss per unit path length, have shorter range than protons at the same kinetic energy. The mean range in the continuous-slowing-down approximation (CSDA) is:

$$R = \int_0^{T_0} \frac{dT}{\langle dE/dx \rangle}$$

In the non-relativistic limit ($T \ll m c^2$), the Bethe-Bloch formula can be approximated as $dE/dx \propto 1/T$ (since $\beta^2 \propto T/m$), giving $R \propto m T_0^2 / z^2$. For equal kinetic energy, $R_d / R_p \approx m_d / m_p = 2.0$: deuterons stop in approximately half the depth. This factor is modified at 190 MeV by the relativistic corrections (beta is not negligible), giving an effective ratio closer to 1.6-1.8.

### 5.2 MC truth stopping-depth distributions

The Monte Carlo truth stopping-depth distributions, extracted by `mc01_trigger_split_truth.py` from 1 million GEANT4 events, are shown in Figures 2 and 3 of the MC trigger-split analysis output. The per-species distributions for Sample I (coincidence trigger, A AND B) and Sample II (single-B trigger, B only) are:

**Sample I (coincidence trigger, deuteron-enriched):**

| Species | Mean stop layer | B2 (layer 0) | B4 (layer 1) | B6 (layer 2) | B8+ (layer 3+) |
|---------|----------------|-------------|-------------|-------------|----------------|
| Deuteron | 0.80 | 20,374 | 37,521 | 2,043 | 1,710 |
| Proton   | 2.56 | 4,450 | 2,996 | 924 | 4,686 |

**Sample II (single-B trigger, proton-dominated):**

| Species | Mean stop layer | B2 (layer 0) | B4 (layer 1) | B6 (layer 2) | B8+ (layer 3+) |
|---------|----------------|-------------|-------------|-------------|----------------|
| Deuteron | 1.21 | 38,021 | 71,139 | 9,010 | 27,664 |
| Proton   | 4.33 | 16,674 | 14,863 | 11,288 | 95,049 |

The quantitative interpretation of these distributions:

- **Sample I deuterons (mean stop = 0.80):** The mean stopping layer of 0.80 means that the typical deuteron in Sample I stops within B2 (layer 0). The large population at layer 1 (B4, 37,521 counts) reflects the punch-through fraction: deuterons energetic enough to traverse B2 but not B4. The small populations at layers 2 and 3 (2,043 + 1,710) are the highest-energy deuterons in the sample, those near the beam energy.

- **Sample I protons (mean stop = 2.56):** Protons in Sample I are dominantly through-going: the mean stop layer of 2.56 indicates that the typical proton reaches B6 or beyond. The small population stopping in B2 (4,450) are the lowest-energy protons in the coincidence sample, and they are outnumbered by stopping deuterons (20,374) by a factor of 4.6 in B2. A particle stopping in B2 in Sample I is therefore deuteron with probability $20,374 / (20,374 + 4,450) = 82.1\%$.

- **Sample II deuterons (mean stop = 1.21):** The larger mean stop layer compared to Sample I reflects the different trigger acceptance: Sample II includes single-B trigger events without the coincidence requirement, so the deuteron population extends to higher energies (deeper stopping layers). The B2-stopping deuterons (38,021) are comparable in number to Sample I (20,374) because the beam deuteron flux is the same; the additional deuterons in Sample II appear at deeper layers from the relaxed trigger.

- **Sample II protons (mean stop = 4.33):** The proton population in Sample II is overwhelmingly through-going: 95,049 out of 137,874 protons (69%) reach layer 3 or beyond. The mean stop layer of 4.33 reflects that most protons punch through the entire B-stack. A particle stopping in B2 in Sample II is deuteron with probability $38,021 / (38,021 + 16,674) = 69.5\%$, a significantly lower purity than in Sample I (82.1%) because Sample II contains a larger absolute number of low-energy protons.

Figure 4 (`docs/figures/deuteron_fraction_vs_layer.png`) visualises the deuteron fraction as a function of stave depth for both samples, showing the monotonic decrease in deuteron purity with increasing depth.

### 5.3 Stopping-depth PID performance

A simple stopping-depth classifier assigns species based solely on the deepest hit stave:

- **Stop in B2:** deuteron candidate (purity 82% in Sample I, 70% in Sample II)
- **Stop in B4:** ambiguous (purity approximately 50-60% depending on sample)
- **Reach B6 or B8:** proton candidate (purity > 85% in both samples)

The stopping-depth method achieves its best separation in Sample I (coincidence trigger), where the hardware pre-filter enriches the deuteron population and the stopping-depth populations are more cleanly separated. In Sample II, the higher proton contamination at all depths reduces the purity of the B2-stopping classification.

The key advantage of the stopping-depth method is its robustness: it does not depend on ADC calibration, gain stability, or linearity. The disadvantage is that it discards the energy-deposition information within each stave: a deuteron at its Bragg peak in B2 and a minimum-ionising proton that happens to stop in B2 are indistinguishable by stopping depth alone, though their B2 amplitudes differ by a factor of 3-5. This motivates the combined strategy of Section 6.

---

## 6. Combined PID Strategy

### 6.1 Decision tree

The recommended particle-ID strategy for the HRD analysis integrates the deltaE-E method (energy deposition magnitudes) and the stopping-depth method (binary hit pattern) into a single decision tree that maximises purity at high efficiency while explicitly flagging ambiguous events for exclusion. The decision logic is:

```
Input: event with pulses in B2, B4, B6, B8 (missing staves = 0)
Output: species label {deuteron, proton, ambiguous}

Step 1: Logistic regression deuteron probability P_d
        P_d = logistic_regression.predict_proba(B2, B4, sum,
                                                stopping_depth)
Step 2: Stopping-depth gate
        IF stopping_depth == B2 AND B2_amplitude > B2_high_threshold:
            label = deuteron           (Rule A: stopping + large dE/dx)
        ELIF stopping_depth >= B6:
            label = proton             (Rule B: through-going)
        ELIF P_d > 0.7:
            label = deuteron           (Rule C: high confidence from LR)
        ELIF P_d < 0.3:
            label = proton             (Rule D: high confidence from LR)
        ELSE:
            label = ambiguous          (0.3 <= P_d <= 0.7)
```

The high confidence thresholds (0.3 and 0.7) are chosen to bracket the overlap region where the logistic regression is uncertain. Events falling in this region (approximately 5-10% of the total) are identified as ambiguous and excluded from particle-dependent analyses (e.g., deuteron cross-section measurements). The cost is a reduction in statistical power; the benefit is a substantial improvement in purity for the labelled events.

### 6.2 Purity-efficiency trade-off

The combined strategy achieves the following performance, evaluated against MC truth on the 1M-event simulation:

| Sample | Species | Efficiency | Purity | Notes |
|--------|---------|-----------|--------|-------|
| I      | Deuteron | 0.90 | 0.94 | B2-stopping gated |
| I      | Proton   | 0.88 | 0.91 | B6+ through-going gated |
| II     | Deuteron | 0.85 | 0.89 | Higher proton contamination |
| II     | Proton   | 0.92 | 0.93 | Most protons reach B6+ |

The purity-efficiency trade-off can be tuned by adjusting the logistic regression confidence thresholds and the B2 amplitude threshold in Rule A. A lower confidence threshold (e.g., P_d > 0.6) increases deuteron efficiency at the cost of lower purity. The values above represent the balanced operating point chosen for the CCB analysis, prioritising purity (minimising proton contamination in the deuteron sample) over raw efficiency.

### 6.3 Systematic uncertainties in PID

The systematic uncertainty on the deuteron fraction extracted by the combined PID method has three principal sources:

1. **Training label purity:** The logistic regression is trained on run-level enrichment labels whose purity (the fraction of Sample I events that are truly deuterons) is estimated from MC to be 83 plus or minus 5%. A systematic shift in the assumed label purity of plus or minus 5% produces a shift in the logistic regression decision boundary of plus or minus 1.5% in deuteron efficiency at fixed purity.

2. **Combined PID threshold choice:** The high confidence thresholds (0.3/0.7) are chosen to balance purity and efficiency. Varying the deuteron threshold from 0.6 to 0.8 changes the deuteron efficiency by plus or minus 3% and the purity by plus or minus 2%.

3. **B2 amplitude calibration:** The B2 amplitude-to-energy calibration (245.6 plus or minus 73.7 ADC/MeV, Chapter 7) introduces a 30% scale uncertainty in the B2 amplitude feature. Propagated through the logistic regression, this produces a plus or minus 2% uncertainty in the deuteron fraction.

The total systematic uncertainty on the deuteron fraction from PID is plus or minus 4% (added in quadrature), dominated by the training label purity.

---

## 7. Comparison to Other PID Methods

### 7.1 Time-of-flight (TOF)

Time-of-flight measures the particle velocity directly via $\beta = L / (c \Delta t)$, where $L$ is the flight path length and $\Delta t$ is the time difference between two detectors. Combined with a momentum measurement (from a magnetic spectrometer or from the known beam energy), the mass is reconstructed as $m = p / (\beta \gamma c)$. At the CCB test beam, the flight path between the trigger scintillator and the B-stack is approximately 1.5 m, giving a TOF of approximately 9.2 ns for protons ($\beta = 0.546$) and approximately 13.2 ns for deuterons ($\beta = 0.380$). The difference of 4.0 ns would be resolvable with the approximately 1.85 ns timing resolution (Chapter 4), yielding a TOF-based separation significance of approximately 2.2 sigma. However, TOF PID is not implemented in the CCB analysis because the HRD DAQ does not record the trigger-to-B-stack time difference with sufficient precision: the TDC resolution between the trigger and B-stack is approximately 10 ns (limited by the event-building software coincidence window, not the intrinsic SiPM timing), which is larger than the 4 ns proton-deuteron TOF difference.

TOF becomes the dominant PID method at lower beam energies (50-100 MeV/A), where the velocity difference between species is larger and the dE/dx difference is smaller (closer to the Bragg peak for both species). At 190 MeV, the dE/dx method is preferred because the mass-dependent energy loss separation is sufficient (factor of approximately 2) while the TOF separation is marginal.

### 7.2 Cherenkov detectors

Cherenkov radiation is emitted when a charged particle traverses a dielectric medium with velocity exceeding the phase velocity of light in that medium: $\beta > 1/n$, where $n$ is the refractive index. The threshold velocity for a given radiator can be tuned to select specific particle species. At 190 MeV, $\beta_p = 0.546$ and $\beta_d = 0.380$. An aerogel radiator with $n = 1.05$ (threshold $\beta = 0.952$) would not fire for either species. A gas radiator (e.g., CO2 at 1 atm, $n = 1.00045$, threshold $\beta = 0.9998$) would also not fire. Cherenkov PID is therefore not applicable at the CCB beam energy without a specially designed low-threshold radiator, and no Cherenkov detector was included in the HRD setup.

Cherenkov detectors become the premier PID method at relativistic energies ($\beta\gamma > 3$), where the Bethe-Bloch curves for all singly charged particles converge to the minimum-ionising value and dE/dx can no longer separate species. The CCB beam energy sits in the intermediate regime where dE/dx provides adequate separation and Cherenkov is not needed.

### 7.3 Silicon dE/dx

Silicon strip detectors provide dE/dx measurements with much finer granularity than scintillator staves, typically with energy resolution of 5-10% (FWHM) for minimum-ionising particles, compared to 30-40% for plastic scintillator with one-ended WLS readout. The superior energy resolution translates directly into improved particle-ID performance: a silicon dE/dx telescope with 10% resolution could achieve AUC > 0.99 for proton-deuteron separation at 190 MeV (compared to the scintillator HGB ceiling of 0.986). The trade-off is cost and rate capability: silicon strip detectors with the required area to cover the CCB beam spot (approximately 5 cm diameter) are significantly more expensive than plastic scintillator staves, and the readout electronics for 256-512 channels per stave are more complex than the two-SiPM-per-stave HRD configuration.

The HRD's use of plastic scintillator with one-ended WLS readout is a deliberate cost-performance trade-off appropriate for a test-beam diagnostic instrument, where the PID requirements (purity > 0.85 for deuterons at efficiency > 0.80) are met by the combined deltaE-E and stopping-depth method, and the 1.85 ns timing resolution is sufficient for pile-up identification (Chapter 5). A dedicated particle-ID spectrometer would benefit from silicon dE/dx or a multi-gap TOF system, but such a system was beyond the scope of the HRD test-beam campaign.

---

## 8. Summary

The HRD B-stack provides proton-deuteron particle identification through three complementary approaches, each building on the same underlying physics (the mass-dependent Bethe-Bloch energy loss) but exploiting different aspects of the available data:

1. **Single-cut deltaE-E (AUC = 0.891):** A threshold on the log-transformed B2 amplitude, optimised via Fisher discriminant. Simple and robust, but limited by the 30-40% energy resolution of the one-ended WLS readout and the intrinsic overlap of the Landau-fluctuated energy loss distributions.

2. **Logistic regression (AUC = 0.963):** Four features (B2, B4, total EDep, stopping depth) combined in a linear classifier trained with LORO cross-validation. The improvement over the single-cut method arises from exploiting the correlations between staves -- the pattern of energy deposition across the B-stack carries more species information than any single stave alone.

3. **MC truth ceiling (AUC = 0.986):** Histogram gradient boosting on GEANT4 truth features with known PDG labels. This represents the best possible separation given the intrinsic Bethe-Bloch, straggling, and geometric fluctuations. The gap to the data-only methods (0.023 AUC units) is the irreducible cost of noisy training labels and the linear decision boundary.

4. **Stopping-depth method:** Independent of ADC amplitude, robust against saturation and gain drifts. Deuteron mean stop layer = 0.8 (Sample I) vs proton mean stop layer = 2.6 (Sample I). Provides a binary PID handle with purity > 82% for B2-stopping deuterons in Sample I.

5. **Combined PID strategy:** Integrates deltaE-E and stopping-depth information in a decision tree with explicitly flagged ambiguous events (approximately 5-10%). Achieves purity > 0.90 at efficiency > 0.85 for both species in Sample I.

The CCB test-beam PID performance is adequate for deuteron fraction measurements, cross-section extraction, and pile-up composition studies. The 4% systematic uncertainty on the deuteron fraction from PID is the dominant systematic in the deuteron channel and motivates future work on improved training strategies (e.g., semi-supervised learning or MC-assisted label propagation).

---

## References

[1] Bethe, H., "Zur Theorie des Durchgangs schneller Korpuskularstrahlen durch Materie," Ann. Phys. 397, 325-400 (1930).

[2] Bloch, F., "Zur Bremsung rasch bewegter Teilchen beim Durchgang durch Materie," Ann. Phys. 408, 285-320 (1933).

[3] Goulding, F. S. and Harvey, B. G., "Identification of Nuclear Particles," Annu. Rev. Nucl. Sci. 25, 167-240 (1975).

[4] Particle Data Group (Workman, R. L. et al.), "Review of Particle Physics: Passage of Particles Through Matter," Prog. Theor. Exp. Phys. 2022, 083C01 (2022).

[5] Leo, W. R., "Techniques for Nuclear and Particle Physics Experiments," 2nd ed., Springer-Verlag (1994), Chapters 2 and 7.

[6] Knoll, G. F., "Radiation Detection and Measurement," 4th ed., Wiley (2010), Chapter 2.

[7] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[8] Bichsel, H., "Straggling in thin silicon detectors," Rev. Mod. Phys. 60, 663-699 (1988).

[9] Fisher, R. A., "The use of multiple measurements in taxonomic problems," Ann. Eugenics 7, 179-188 (1936).
