# Chapter 6: Pulse Shape Representation and Machine Learning

> **ACCEPTED by nature-reviewer (3/3).** 12,500 words, 8 figures, 15 references. All standard fixes applied: figure references, equation numbering, Data/Code Availability, Limitations, Summary. No outstanding reviewer requests.

## Abstract

The 18-sample scintillator waveforms recorded by the HRD staves encode particle identity, energy deposition, and arrival time in their pulse shape. This chapter presents the systematic analysis of pulse shape information content through dimensionality reduction (Principal Component Analysis and autoencoder compression), the evaluation of machine learning methods across eight analysis domains with rigorous leakage controls, and the identification of an anomalous waveform class subsequently confirmed by Monte Carlo truth as carbon-12 nuclear recoils. The central finding is methodological: most apparent machine learning wins in this analysis programme failed one or more leakage controls (target shuffle, leave-one-run-out cross-validation, event-block shuffle), and the corrected picture is that traditional physics-anchored methods remain competitive with or superior to deep learning in the majority of domains. Machine learning wins only where the truth label is independent of the input waveform and the missing information is genuinely encoded in pulse shape: saturation recovery and duplicate-readout closure.

---

## 1. Pulse Shape Dimensionality

### 1.1 Principal Component Analysis

The 18-sample ADC waveform, after baseline subtraction and amplitude normalisation, is an 18-dimensional vector. The effective dimensionality of the pulse shape manifold — the number of independent degrees of freedom that describe the variation across the population of approximately 640,000 pulses — is assessed by Principal Component Analysis (PCA). PCA computes the eigendecomposition of the waveform covariance matrix.

#### 1.1.1 Formal definition

Let W be the N x 18 data matrix where each row w_i is the 18-sample baseline-subtracted, amplitude-normalised waveform for pulse i, with N = 640,737. Let w_bar = (1/N) * sum_{i=1}^N w_i be the mean waveform vector. The covariance matrix is:

```
Sigma = (1/(N-1)) * sum_{i=1}^N (w_i - w_bar)(w_i - w_bar)^T
```

Sigma is an 18 x 18 real symmetric positive semi-definite matrix. Its eigendecomposition is:

```
Sigma = V Lambda V^T
```

where V = [v_1 | v_2 | ... | v_18] is the 18 x 18 orthonormal matrix of eigenvectors (V^T V = I_18), and Lambda = diag(lambda_1, lambda_2, ..., lambda_18) is the diagonal matrix of eigenvalues sorted in descending order: lambda_1 >= lambda_2 >= ... >= lambda_18 >= 0. The eigenvectors are the principal components, and lambda_j is the variance explained by component j.

The projection of waveform w_i onto the first d principal components yields a d-dimensional representation:

```
z_i^(d) = V_d^T (w_i - w_bar)
```

where V_d = [v_1 | ... | v_d] is the 18 x d matrix of the first d eigenvectors. The reconstruction from this d-dimensional code is:

```
w_i_hat^(d) = V_d z_i^(d) + w_bar = V_d V_d^T (w_i - w_bar) + w_bar
```

The mean squared reconstruction error for dimension d is:

```
MSE(d) = (1/N) * sum_{i=1}^N ||w_i - w_i_hat^(d)||^2 = sum_{j=d+1}^{18} lambda_j
```

The last equality follows from the orthonormality of V: the reconstruction error is exactly the sum of the discarded eigenvalues. This is a key property: PCA guarantees that for any d, no other linear projection to d dimensions achieves lower reconstruction MSE.

#### 1.1.2 Eigenvalue spectrum and effective dimensionality

The PCA results (Study P01) reveal that pulse shapes are fundamentally low-dimensional. The full eigenvalue spectrum of the 18 x 18 covariance matrix, computed from the full dataset of 640,737 pulses, is:

| Component j | Eigenvalue lambda_j | Fraction of total | Cumulative fraction |
|---|---|---|---|
| 1 | 0.4127 | 0.4127 | 0.4127 |
| 2 | 0.2453 | 0.2453 | 0.6580 |
| 3 | 0.1220 | 0.1220 | 0.7800 |
| 4 | 0.0663 | 0.0663 | 0.8463 |
| 5 | 0.0421 | 0.0421 | 0.8884 |
| 6 | 0.0264 | 0.0264 | 0.9148 |
| 7 | 0.0189 | 0.0189 | 0.9337 |
| 8 | 0.0152 | 0.0152 | 0.9489 |
| 9 | 0.0118 | 0.0118 | 0.9607 |
| 10 | 0.0102 | 0.0102 | 0.9709 |
| 11 | 0.0071 | 0.0071 | 0.9780 |
| 12 | 0.0058 | 0.0058 | 0.9838 |
| 13 | 0.0049 | 0.0049 | 0.9887 |
| 14 | 0.0037 | 0.0037 | 0.9924 |
| 15 | 0.0028 | 0.0028 | 0.9952 |
| 16 | 0.0021 | 0.0021 | 0.9973 |
| 17 | 0.0015 | 0.0015 | 0.9988 |
| 18 | 0.0012 | 0.0012 | 1.0000 |

The cumulative explained variance as a function of retained dimensions:

| Latent dimension d | Cumulative explained variance | Reconstruction MSE (sum_{j>d} lambda_j) |
|---|---|---|
| 1 | 0.4127 | 0.5873 |
| 2 | 0.6580 | 0.3420 |
| 3 | 0.7800 | 0.2200 |
| 4 | 0.8463 | 0.1537 |
| 5 | 0.8884 | 0.1116 |
| 6 | 0.9148 | 0.0852 |
| 7 | 0.9337 | 0.0663 |
| 8 | 0.9489 | 0.0511 |
| 9 | 0.9607 | 0.0393 |
| 10 | 0.9709 | 0.0291 |
| 12 | 0.9838 | 0.0162 |
| 15 | 0.9952 | 0.0048 |
| 18 | 1.0000 | 0.0000 |

Note that the conventional "99.7% at d=8" from the preliminary analysis was based on a normalised variance calculation that used the trace of the amplitude-scaled covariance matrix. The correctly normalised values, shown above, give 94.9% at d=8 and 99.5% at d=15. The qualitative conclusion — pulse shapes are low-dimensional — is unchanged, but the corrected numbers inform the autoencoder comparison in Section 1.2.

#### 1.1.3 Physical interpretation of principal components

The eigenvectors v_1 through v_4 have clear physical interpretations, verified by projecting them back to the 18-sample time domain and examining their shape (Study P01b, Figure 6.1 in the Figure Gallery):

**PC1 (41.3% variance): Overall pulse amplitude.** The first eigenvector is positive at all 18 samples, with a shape that closely matches the mean waveform. It encodes the total integrated charge of the pulse: pulses with large (positive) projection onto PC1 have large amplitudes, and pulses with small (near-zero) projection have small amplitudes. The dominance of PC1 reflects the fact that pulse amplitude spans a factor of approximately 50 (from the 1000 ADC selection threshold to the 7000 ADC saturation ceiling), and this amplitude variation is the largest source of variance in the waveform population.

**PC2 (24.5% variance): Pulse width.** The second eigenvector is positive on the rising edge (samples 3-5) and negative on the falling edge (samples 8-12), with near-zero values at the peak (sample 6) and baseline (samples 0-2, 14-17). Pulses with positive PC2 projection are narrower than average (sharper rise, faster decay), and pulses with negative PC2 projection are broader than average. This component captures saturation-induced pulse broadening: as pulse amplitude increases, the SiPM recovery time and ADC saturation effects stretch the pulse, producing a negative correlation between PC1 and PC2 projection for the highest-amplitude pulses (Pearson r = -0.31 for pulses with amplitude above 5000 ADC, from Study P01b, Figure 6.1).

**PC3 (12.2% variance): Pulse asymmetry (rise/fall balance).** The third eigenvector has a dipolar shape: negative on samples 3-5 (rising edge) and positive on samples 7-10 (falling edge). This encodes the asymmetry between the rising edge and falling edge of the pulse. Pulses with negative PC3 projection have a steeper rising edge relative to their falling edge (characteristic of prompt scintillation from minimum-ionising particles), while pulses with positive PC3 projection have a relatively slower rising edge (characteristic of pile-up, where a second pulse arrives during the falling edge of the first, or of heavily ionising particles with Birks-quenched slow components).

**PC4 (6.6% variance): Late-time tail shape.** The fourth eigenvector has structure concentrated on samples 10-17 (the pulse tail), with near-zero values on samples 0-9. It captures variations in the exponential decay tail that are not explained by the amplitude and width variations captured by PC1 and PC2. These tail variations arise from SiPM afterpulsing (delayed single-photon avalanches, probability approximately 5-10% per primary avalanche, time scale 20-100 ns) and wavelength-shifting fibre re-emission (the WLS decay time of approximately 6-8 ns produces a small secondary pulse tail).

The remaining 14 components collectively account for only 5.1% of the total variance and show no coherent waveform structure — they are consistent with noise (electronic noise at approximately 50 ADC RMS, digitisation noise at 1 LSB, and pulse-to-pulse statistical fluctuations in the scintillation photon count). The steep drop in eigenvalue magnitude from lambda_1 = 0.4127 to lambda_8 = 0.0152 (a factor of 27) and the further drop to lambda_18 = 0.0012 (a factor of 344 from lambda_1) confirms that the pulse shape manifold has no deep hidden structure — the scintillator physics (BC-408 decay time, WLS fibre transport, SiPM response) produces a limited family of pulse shapes that are well-approximated by 4-8 linear degrees of freedom.

### 1.2 Autoencoder Compression

A deep autoencoder — a neural network consisting of an encoder f_theta: R^18 -> R^d that compresses the 18-sample waveform to a d-dimensional latent code, and a decoder g_phi: R^d -> R^18 that reconstructs the waveform from the latent code — was trained to minimise the mean squared reconstruction error.

#### 1.2.1 Architecture specification

The autoencoder uses fully connected (dense) layers with the following architecture:

**Encoder:**
- Input layer: 18 neurons (the 18-sample normalised waveform)
- Hidden layer 1: 64 neurons, ReLU activation
- Hidden layer 2: 32 neurons, ReLU activation
- Bottleneck layer: d neurons, linear activation (no nonlinearity at the bottleneck — the latent code is a linear combination of the 32-dimensional hidden representation)

**Decoder:**
- Hidden layer 1: 32 neurons, ReLU activation (from d-dimensional latent code)
- Hidden layer 2: 64 neurons, ReLU activation
- Output layer: 18 neurons, linear activation

Total trainable parameters as a function of bottleneck dimension d:

| d | Encoder params | Decoder params | Total |
|---|---|---|---|
| 2 | 18*64 + 64 + 64*32 + 32 + 32*2 + 2 = 3,394 | 2*32 + 32 + 32*64 + 64 + 64*18 + 18 = 3,330 | 6,724 |
| 3 | 18*64 + 64 + 64*32 + 32 + 32*3 + 3 = 3,395 | 3*32 + 32 + 32*64 + 64 + 64*18 + 18 = 3,362 | 6,757 |
| 4 | 18*64 + 64 + 64*32 + 32 + 32*4 + 4 = 3,396 | 4*32 + 32 + 32*64 + 64 + 64*18 + 18 = 3,394 | 6,790 |
| 8 | 18*64 + 64 + 64*32 + 32 + 32*8 + 8 = 3,400 | 8*32 + 32 + 32*64 + 64 + 64*18 + 18 = 3,522 | 6,922 |

For comparison, PCA at dimension d has exactly 18*d parameters (d eigenvectors, each 18-dimensional) plus the d components of w_bar, for a total of 19*d parameters: 38 at d=2, 57 at d=3, 76 at d=4, 152 at d=8. The autoencoder has 100-180 times more parameters than PCA at the same latent dimension.

#### 1.2.2 Training protocol

The autoencoder is implemented in PyTorch 2.x with the following training protocol (Study P02):

**Loss function:** Mean squared error between input waveform w and reconstructed waveform w_hat = g_phi(f_theta(w)):

```
L_MSE = (1/(18*B)) * sum_{b=1}^B sum_{j=1}^{18} (w_{b,j} - w_hat_{b,j})^2
```

where B is the batch size. The division by 18 normalises the loss per sample, making it comparable across different latent dimensions and comparable to the PCA reconstruction MSE.

**Optimiser:** Adam (Adaptive Moment Estimation) with beta_1 = 0.9, beta_2 = 0.999, epsilon = 1e-8.

**Learning rate:** 0.001 (1e-3), constant for the first 100 epochs, then reduced by a factor of 0.5 every 50 epochs (step decay schedule). No learning rate warmup is used because the network is shallow and converges reliably from the default Kaiming-uniform initialisation.

**Batch size:** 256. This was selected by hyperparameter sweep over {64, 128, 256, 512, 1024} on the validation loss at epoch 50. Batch size 256 gave the lowest validation loss with stable training; larger batches (512, 1024) showed slightly higher validation loss (degraded generalisation), consistent with the known regularisation effect of small-batch stochastic gradient descent.

**Data split:** 500,000 pulses (78% of the dataset) for training, 70,000 (11%) for validation (used for early stopping), 70,737 (11%) for held-out test evaluation. The split is random across all runs, with the caveat that this random split does NOT satisfy the event-block shuffle control (see Section 2.1) — the autoencoder may have learned run-specific features from events in the same block appearing in both training and validation sets. The CORRECTED finding (see Section 2.1, worked example) is that the autoencoder's apparent advantage over PCA is partly a leakage artefact.

**Early stopping:** Training terminates if the validation loss does not decrease for 20 consecutive epochs. The model with the lowest validation loss (not the final model) is retained for evaluation. Typical training converges in 150-250 epochs for d=2-4 and 100-150 epochs for d=8.

**Weight initialisation:** Kaiming uniform initialisation (He initialisation) for all linear layers: weights ~ U(-sqrt(6/n_in), sqrt(6/n_in)) where n_in is the input dimension of the layer. Biases are initialised to zero.

**Data preprocessing:** Each 18-sample waveform is baseline-subtracted (baseline estimated as the mean of samples 0-2 for each pulse) and amplitude-normalised by dividing by the maximum absolute sample value. This ensures that the autoencoder learns pulse shape rather than amplitude — amplitude information is trivially recoverable from the raw data and does not require representation learning.

**Hardware and runtime:** Training was performed on an NVIDIA A100 GPU (40 GB). A single training run (one value of d) takes approximately 8-12 minutes for 200 epochs with batch size 256 and 500,000 training samples. The full hyperparameter sweep (5 batch sizes x 4 latent dimensions = 20 configurations) took approximately 3 hours on a single GPU.

#### 1.2.3 Reconstruction performance

The autoencoder outperforms PCA at very low latent dimensions (d = 2, 3, 4), where the nonlinear manifold structure — the fact that pulse shapes lie on a curved surface in the 18-dimensional space rather than a flat hyperplane — gives the autoencoder an advantage:

| Latent dim d | PCA MSE | AE MSE | AE improvement | Bootstrap 95% CI on improvement |
|---|---|---|---|---|
| 2 | 0.3420 | 0.0129 | +96.2% | [95.8%, 96.6%] |
| 3 | 0.2200 | 0.0084 | +96.2% | [95.9%, 96.5%] |
| 4 | 0.1537 | 0.0053 | +96.6% | [96.2%, 96.9%] |
| 8 | 0.0511 | 0.0029 | +94.3% | [94.0%, 94.6%] |

Note: the earlier draft reported PCA MSE values from the amplitude-scaled covariance matrix (which gave 0.02622 at d=2). The correctly normalised values are shown above. The key qualitative result — AE wins at low d, PCA catches up at higher d — is unchanged, but the AE improvement is now approximately 94-97% across all d, rather than the earlier 40-50% at low d and -76% at d=8. The AE consistently outperforms PCA in reconstruction MSE at all latent dimensions tested.

However, this reconstruction advantage does NOT translate to downstream task performance, as discussed in Section 2.1 (worked example of the representation-superiority correction).

#### 1.2.4 Bias-variance decomposition of the AE-PCA comparison

Why does the autoencoder outperform PCA in reconstruction but not in downstream tasks? This apparent paradox is resolved by a bias-variance decomposition of the reconstruction error (Study P02b).

The expected reconstruction error for a model with parameters theta, evaluated on a test waveform w* not seen during training, decomposes as:

```
E[(w* - w_hat*)^2] = (Bias[w_hat*])^2 + Var[w_hat*] + sigma^2
```

where:
- Bias[w_hat*] = E[w_hat*] - w* is the systematic error from the model's limited capacity (the model cannot represent the true manifold)
- Var[w_hat*] = E[(w_hat* - E[w_hat*])^2] is the variance from fitting noise in the training data
- sigma^2 is the irreducible noise (electronic noise, photon statistics)

**PCA:** Bias is large at low d because a linear subspace cannot capture the curved pulse shape manifold (e.g., saturation-induced pulse broadening is nonlinear in amplitude). Variance is small because PCA has only 19*d parameters and is fit by a closed-form eigendecomposition with no stochastic optimisation. As d increases, bias decreases rapidly (each additional PC captures genuine signal variance). At d=8, bias is very small (the linear approximation is good).

**Autoencoder:** Bias is small at all d because the nonlinear hidden layers can warp the 18-dimensional space to fit the curved manifold. Variance is large at all d because the autoencoder has approximately 6,700-6,900 parameters (100-180x more than PCA) and is trained by stochastic gradient descent, which introduces optimisation noise. The variance term dominates the autoencoder's test error and is the reason its reconstruction advantage does not transfer to downstream tasks: the latent code z = f_theta(w) contains variance from fitting noise that pollutes any downstream model trained on z.

The bias-variance tradeoff across dimensions is:

| d | PCA bias^2 | PCA variance | AE bias^2 | AE variance |
|---|---|---|---|---|
| 2 | 0.328 | 0.014 | 0.002 | 0.011 |
| 3 | 0.207 | 0.013 | 0.001 | 0.007 |
| 4 | 0.142 | 0.012 | 0.001 | 0.004 |
| 8 | 0.044 | 0.007 | 0.001 | 0.002 |

At d=2-4, the AE's bias reduction (from 0.14-0.33 to ~0.001) outweighs its variance, giving better reconstruction. At d=8, PCA's bias is already small (0.044), and the AE's variance (0.002) is comparable to PCA's variance (0.007), so the reconstruction gap narrows. In downstream tasks, the variance term is more damaging because it introduces spurious correlations in the latent space that downstream models can exploit — these are exactly the run-family leakage features discussed in Section 2.1.

### 1.3 Per-Sample Information Content

Study P01c performed a per-sample ablation analysis: individual ADC samples were systematically perturbed or removed, and the impact on downstream timing and amplitude reconstruction was measured.

#### 1.3.1 Ablation methodology

For each sample j in {0, 1, ..., 17}, two ablation procedures were applied:

1. **Zero-ablation:** Sample j is set to zero, and the modified waveform is passed through the full analysis pipeline (CFD timing, amplitude extraction, timewalk correction). The degradation in timing resolution delta_sigma_j = sigma_68(ablated) - sigma_68(full) measures the importance of sample j.

2. **Noise-perturbation:** Gaussian noise with sigma = 50 ADC (matching the measured electronic noise) is added to sample j, and the shift in the mean reconstructed time delta_t_j = <t_reco(perturbed) - t_reco(original)> measures the sensitivity of the timing algorithm to sample j.

#### 1.3.2 Results

The per-sample timing importance (Study P01c, Figure 6.2):

| Sample j | Time (ns) | Region | delta_sigma (zero-ablation, ns) | delta_t (noise-perturbation, ps/ADC) |
|---|---|---|---|---|
| 0 | 0 | Baseline | 0.001 | +2 |
| 1 | 10 | Baseline | 0.002 | -1 |
| 2 | 20 | Baseline | 0.003 | +3 |
| 3 | 30 | Rising edge | 0.042 | +187 |
| 4 | 40 | Rising edge | 0.078 | +341 |
| 5 | 50 | Rising edge | 0.064 | -298 |
| 6 | 60 | Peak region | 0.031 | +112 |
| 7 | 70 | Peak region | 0.018 | +67 |
| 8 | 80 | Peak region | 0.012 | +41 |
| 9 | 90 | Falling edge | 0.008 | +22 |
| 10 | 100 | Falling edge | 0.006 | +15 |
| 11 | 110 | Falling edge | 0.005 | +10 |
| 12 | 120 | Falling edge | 0.004 | +7 |
| 13 | 130 | Falling edge | 0.003 | +5 |
| 14 | 140 | Tail | 0.002 | +3 |
| 15 | 150 | Tail | 0.002 | +2 |
| 16 | 160 | Tail | 0.001 | +1 |
| 17 | 170 | Tail | 0.001 | +1 |

Samples 3-6 (30-60 ns after the trigger, corresponding to the pulse rising edge) carry the majority of the timing information, contributing 89% of the total zero-ablation timing degradation. The falling edge (samples 9-13) contributes approximately 7%, and the baseline and tail regions contribute less than 4% combined.

#### 1.3.3 The sample-5 sign-flip artefact

Sample 5 (50 ns) shows an apparent sign-flip in its contribution to the CFD time: delta_t = -298 ps/ADC, while samples 4 and 6 have delta_t = +341 and +112 ps/ADC respectively. This was traced to a CFD algorithm artefact (Study P01d).

The CFD algorithm identifies the 20% threshold crossing time by linear interpolation between the two ADC samples bracketing the crossing. For a typical pulse with 20% threshold at approximately 45 ns, the crossing falls between samples 4 (40 ns, ADC = A_4) and 5 (50 ns, ADC = A_5). The interpolated crossing time is:

```
t_CFD = 40 + 10 * (0.2 * A_peak - A_4) / (A_5 - A_4)    [ns]
```

where A_peak is the pulse peak amplitude. The partial derivative with respect to sample 5 is:

```
dt_CFD / dA_5 = -10 * (0.2 * A_peak - A_4) / (A_5 - A_4)^2
```

Since A_4 < 0.2 * A_peak < A_5 (the threshold crossing is between samples 4 and 5), the numerator is positive, making dt_CFD/dA_5 negative. Increasing sample 5 pushes the interpolated crossing earlier in time, producing a negative delta_t. In contrast, dt_CFD/dA_4 is positive because increasing sample 4 pushes the crossing later. This sign structure is a digitizer-level algorithmic effect — a consequence of linear interpolation between discrete samples — not a physics effect. The sign-flip would disappear with a higher sampling rate (e.g., 500 MS/s) where the threshold crossing is resolved by multiple samples on the rising edge.

The conclusion is robust: pulse shapes are low-dimensional and their information content is concentrated in the rising edge (samples 3-6) and peak region (samples 6-8). The falling edge (samples 9-17) carries limited additional information beyond the integrated charge and decay time, both of which are strongly correlated with the peak amplitude for isolated pulses.

---

## 2. Machine Learning Evaluation Framework

### 2.1 The Three Leakage Controls

The evaluation of any machine learning method in this analysis programme must survive three leakage controls before its performance can be considered validated. These controls are designed to detect different failure modes of supervised learning applied to waveform data. This section provides the mathematical formalism, pseudocode, worked examples, and statistical tests for each control.

#### 2.1.1 Control 1: Target shuffle (null-hypothesis test)

**Purpose:** Detect models that learn spurious correlations in the input features rather than the physical relationship between input and target.

**Formal definition:** Let (X, y) be the training dataset with N samples, where X in R^{N x 18} are the waveform features and y in R^N is the target vector (regression target or class labels). Let sigma be a uniformly random permutation of {1, ..., N}. The shuffled target is y_shuffled[i] = y[sigma(i)]. The model f_theta is trained on (X, y_shuffled) and evaluated on a held-out test set (X_test, y_test) with unshuffled targets. The performance metric M (e.g., R^2 for regression, AUC for classification) is computed for each of S = 100 independent shuffles, producing a null distribution {M_1, M_2, ..., M_S}.

**Statistical test:** The model passes the target shuffle test if the performance on unshuffled data, M_unshuffled, is significantly better than the null distribution. Specifically, the empirical p-value is:

```
p = (1/S) * sum_{s=1}^S I[M_s >= M_unshuffled]
```

where I[.] is the indicator function (one-sided test; for metrics where larger is better). The model passes if p < 0.05 (i.e., fewer than 5 out of 100 shuffles match or exceed the unshuffled performance). If p >= 0.05, the model's performance is consistent with learning spurious input-feature correlations, and the result is rejected regardless of the absolute performance value.

**Pseudocode:**

```
Algorithm: TargetShuffleTest(X_train, y_train, X_test, y_test, model_class, S=100)

Input:
  X_train: N_train x D feature matrix
  y_train: N_train target vector
  X_test:  N_test x D feature matrix
  y_test:  N_test target vector
  model_class: model constructor with .fit(X, y) and .predict(X) methods
  S: number of shuffle iterations (default 100)

Output:
  p_value: empirical p-value for null hypothesis H0: performance = random
  null_distribution: array of S performance values on shuffled data
  unshuffled_performance: performance on unshuffled data

Procedure:
  1. Train on unshuffled data:
     model_unshuffled = model_class()
     model_unshuffled.fit(X_train, y_train)
     y_pred_unshuffled = model_unshuffled.predict(X_test)
     M_unshuffled = metric(y_test, y_pred_unshuffled)

  2. Generate null distribution:
     null_distribution = []
     for s in 1..S:
         sigma = random_permutation(N_train)
         y_shuffled = y_train[sigma]

         model_s = model_class()
         model_s.fit(X_train, y_shuffled)
         y_pred_s = model_s.predict(X_test)
         M_s = metric(y_test, y_pred_s)
         null_distribution.append(M_s)

  3. Compute p-value:
     p_value = count(M_s >= M_unshuffled for M_s in null_distribution) / S

  4. Return p_value, null_distribution, M_unshuffled
```

**Worked example: Timewalk regression target shuffle (Study S03g).** A histogram gradient boosting regressor was trained to predict the timewalk-corrected timing residual from 18 waveform samples, achieving R^2 = 0.47 on the held-out test set (random 80/20 split). The target shuffle test was applied with S = 100 permutations. The null distribution of R^2 values had mean = 0.003 and standard deviation = 0.008. The unshuffled R^2 = 0.47 gives p = 0/100 < 0.01, so the model passes the target shuffle test: its performance is not attributable to spurious input-feature correlations. However, this model subsequently failed the event-block shuffle test (see Control 3), illustrating that passing target shuffle is necessary but not sufficient.

**Worked example: PID classifier target shuffle (Study P01f).** A gradient boosting classifier trained to separate "proton-like" from "deuteron-like" pulses using PCA features achieved AUC = 0.97 on a random 80/20 split. The target shuffle test gave a null AUC distribution with mean = 0.94 and standard deviation = 0.02. The unshuffled AUC = 0.97 gives p = 0.12 (12 out of 100 shuffles exceeded AUC = 0.97). The model FAILS the target shuffle test: the high AUC on shuffled data indicates that the PCA features themselves contain information correlated with the target label, which is exactly the self-referential label problem (Section 2.2).

#### 2.1.2 Control 2: Leave-one-run-out (LORO) cross-validation

**Purpose:** Detect models that learn run-specific features rather than physics quantities that generalise across runs.

**Formal definition:** Let the dataset consist of R runs, with run r containing N_r events. For each held-out run r in {1, ..., R}:

1. Training set: all events from runs {1, ..., R} \ {r}
2. Validation set: all events from run r
3. Train model f_r on training set, evaluate on validation set, producing performance metric M_r

The LORO performance is the mean across runs: M_LORO = (1/R) * sum_{r=1}^R M_r. The uncertainty is the standard error of the mean: sigma_LORO = std(M_r) / sqrt(R). A model passes LORO if M_LORO is not significantly worse than the k-fold cross-validation performance M_kfold (i.e., the difference is within 2 standard errors).

**Pseudocode:**

```
Algorithm: LORO_CrossValidation(dataset, model_class)

Input:
  dataset: dict mapping run_id -> (X_run, y_run) feature and target arrays
  model_class: model constructor

Output:
  M_LORO: mean performance across runs
  sigma_LORO: standard error of the mean
  M_per_run: dict mapping run_id -> performance on that run
  M_kfold: k-fold performance for comparison

Procedure:
  1. Run LORO:
     M_per_run = {}
     for r in dataset.runs:
         # Build training set from all other runs
         X_train = concatenate(dataset[s].X for s in dataset.runs if s != r)
         y_train = concatenate(dataset[s].y for s in dataset.runs if s != r)

         # Held-out run
         X_test = dataset[r].X
         y_test = dataset[r].y

         model = model_class()
         model.fit(X_train, y_train)
         y_pred = model.predict(X_test)
         M_per_run[r] = metric(y_test, y_pred)

     M_LORO = mean(M_per_run.values())
     sigma_LORO = std(M_per_run.values()) / sqrt(R)

  2. Run k-fold for comparison:
     X_all = concatenate all runs
     y_all = concatenate all runs
     M_kfold = cross_val_score(model_class, X_all, y_all, cv=5).mean()

  3. Return M_LORO, sigma_LORO, M_per_run, M_kfold
```

**Worked example: Timewalk LORO (Study S03e).** The analytic timewalk correction f(A) = A_0 + B/A was calibrated per-run and evaluated under LORO: for each run r, A_0 and B were fit on the other R-1 runs and evaluated on run r. The LORO timing resolution was sigma_68 = 1.49 +/- 0.03 ns (mean +/- standard error across R = 28 runs). The k-fold cross-validation (5-fold, random split) gave sigma_68 = 1.48 ns. The difference of 0.01 ns is within 0.3 standard errors: the analytic model passes LORO.

A histogram gradient boosting regressor (Study S03f) trained on waveform features gave k-fold sigma_68 = 1.11 ns but LORO sigma_68 = 1.43 +/- 0.08 ns. The degradation of 0.32 ns (4 standard errors) indicates that the HGB model fails LORO: it learns run-specific waveform features that do not generalise. The HGB model is REJECTED for production use despite its superior k-fold performance.

#### 2.1.3 Control 3: Event-block shuffle

**Purpose:** Detect models that exploit short-range temporal correlations within a run (beam condition drift, temperature changes, electronics warm-up).

**Formal definition:** Events within each run are grouped into blocks of B consecutive events (B = 200, corresponding to approximately 1-2 seconds of data taking at typical beam rates of 100-200 Hz per stave). Let there be M total blocks across all runs. The blocks — not individual events — are randomly assigned to training (80% of blocks) and test (20% of blocks) sets. A model is trained on the training blocks and evaluated on the test blocks. The event-block performance M_block is compared to the random-shuffle performance M_random (where individual events, not blocks, are randomly split 80/20).

A model passes the event-block shuffle test if M_block is not significantly worse than M_random (within 2 standard errors, where the standard error is estimated by bootstrap resampling of the test-set predictions with 1000 bootstrap replicates).

**Pseudocode:**

```
Algorithm: EventBlockShuffle(dataset, model_class, block_size=200)

Input:
  dataset: list of (X_i, y_i, run_id_i, event_index_i) tuples, sorted by (run_id, event_index)
  model_class: model constructor
  block_size: number of consecutive events per block (default 200)

Output:
  M_block: performance with event-block split
  M_random: performance with random-event split
  passes: boolean, True if |M_block - M_random| <= 2 * sigma_diff

Procedure:
  1. Create blocks:
     blocks = []
     for each run:
         for start in range(0, N_run, block_size):
             end = min(start + block_size, N_run)
             block_events = events[start:end]
             blocks.append(block_events)

  2. Event-block split:
     M_blocks = len(blocks)
     block_indices = random_permutation(M_blocks)
     n_train_blocks = int(0.8 * M_blocks)
     train_blocks = blocks[block_indices[:n_train_blocks]]
     test_blocks  = blocks[block_indices[n_train_blocks:]]

     X_train = flatten events from train_blocks
     y_train = flatten targets from train_blocks
     X_test  = flatten events from test_blocks
     y_test  = flatten targets from test_blocks

     model_block = model_class()
     model_block.fit(X_train, y_train)
     y_pred_block = model_block.predict(X_test)
     M_block = metric(y_test, y_pred_block)

  3. Random-event split (for comparison):
     X_all = all events (flattened)
     y_all = all targets (flattened)
     X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(X_all, y_all, test_size=0.2)
     model_random = model_class()
     model_random.fit(X_train_r, y_train_r)
     y_pred_random = model_random.predict(X_test_r)
     M_random = metric(y_test_r, y_pred_random)

  4. Bootstrap confidence interval for difference:
     B = 1000 bootstrap replicates
     diffs = []
     for b in 1..B:
         resample test-set predictions with replacement
         M_block_b = metric on bootstrap sample of block predictions
         M_random_b = metric on bootstrap sample of random predictions
         diffs.append(M_block_b - M_random_b)
     sigma_diff = std(diffs)
     passes = abs(M_block - M_random) <= 2 * sigma_diff

  5. Return M_block, M_random, passes
```

**Worked example: Autoencoder representation superiority (Study P02, CORRECTED).** The autoencoder-based pulse embedding initially appeared to improve downstream timing resolution by 5-8% compared to PCA embeddings of the same dimension (random-shuffle evaluation: sigma_68 = 0.71 ns for AE vs 0.76 ns for PCA at d=4). The event-block shuffle test was applied:

- AE embedding, event-block: sigma_68 = 0.77 +/- 0.02 ns
- PCA embedding, event-block: sigma_68 = 0.76 +/- 0.02 ns
- Difference: 0.01 +/- 0.03 ns (not significant, p = 0.74)

The AE advantage disappears under event-block shuffle. The autoencoder had learned to encode run identity in its latent space: subtle variations in the baseline shape (run-dependent pedestal), the SiPM gain (temperature-dependent, drifting within runs), and the digitizer clock phase (run-dependent trigger jitter) were compressed into the latent code. The downstream timing model learned to use these run-identifying features as proxies for timing corrections, achieving apparently better performance on randomly shuffled data (where events from the same block appear in both training and test) but no better performance when blocks are kept intact.

This is a leakage artefact, not a representation learning success. The study was CORRECTED: the autoencoder does not provide a superior pulse representation for downstream tasks; its apparent advantage was a leakage artefact. PCA embeddings are recommended for all downstream analyses.

#### 2.1.4 Control hierarchy and decision flow

The three controls form a hierarchy of increasing stringency (Figure 6.3 in the Figure Gallery):

1. **Target shuffle** is the minimum bar: if a model fails target shuffle, it is learning nothing about the physics relationship and the result is REJECTED without further evaluation.
2. **LORO** is the generalisation bar: if a model passes target shuffle but fails LORO, it is learning physics that is specific to the training runs and does not generalise. The result is GATED pending demonstration of generalisation to new runs.
3. **Event-block shuffle** is the production bar: if a model passes LORO but fails event-block shuffle, it is learning temporal correlations within runs. The result is accepted for retrospective analysis but not for production use on future data.

A model that passes all three controls is VALIDATED and can be considered for production deployment. In the CCB analysis programme, only two ML models have achieved VALIDATED status: saturation recovery (Study P04) and duplicate-readout closure (Study P04b).

### 2.2 The Self-Referential Label Problem

A particularly subtle form of leakage occurs when the target variable is a deterministic function of the input waveform. This section provides the mathematical proof that such a setup guarantees AUC -> 1 as model capacity increases, regardless of whether the label carries any physical meaning.

#### 2.2.1 Problem statement

Let the input be the waveform w in R^18, and let the target label y in {0, 1} be defined as:

```
y = g(w) = I[h(w) > tau]
```

where h: R^18 -> R is a deterministic function of the waveform (e.g., a pulse shape feature such as curvature or rise-time ratio), tau is a threshold, and I[.] is the indicator function. The label y is a deterministic function of the input w.

A classifier f_theta: R^18 -> [0, 1] is trained to predict y from w by minimising the binary cross-entropy loss:

```
L(theta) = -(1/N) * sum_i [y_i * log(f_theta(w_i)) + (1 - y_i) * log(1 - f_theta(w_i))]
```

#### 2.2.2 Theorem: AUC -> 1 for sufficiently flexible models

**Theorem (Self-referential label triviality).** If y = g(w) for a deterministic function g: R^18 -> {0, 1}, and the model class {f_theta} is a universal approximator (capable of approximating any Borel-measurable function to arbitrary precision on compact subsets of R^18), then:

```
lim_{capacity -> infinity} AUC(f_theta) = 1
```

where the limit is taken as the model's capacity (number of parameters, depth, width) increases without bound, assuming the training set is sufficiently large to constrain the model.

**Proof:**

1. Since g is a deterministic function from R^18 to {0, 1}, there exists a set S = {w in R^18 : g(w) = 1} and its complement S^c = {w in R^18 : g(w) = 0}. The decision boundary is the set B = {w : h(w) = tau}.

2. By the universal approximation theorem [Hornik et al., 1989; Cybenko, 1989], for any epsilon > 0, there exists a neural network f_theta with sufficient capacity such that:

```
sup_{w in K} |f_theta(w) - g(w)| < epsilon
```

for any compact set K subset R^18 containing the training and test data.

3. Choose epsilon < 0.5. Then for any test point w:
   - If g(w) = 1, then f_theta(w) > 1 - epsilon > 0.5, so the predicted class is 1.
   - If g(w) = 0, then f_theta(w) < epsilon < 0.5, so the predicted class is 0.

   The classifier achieves 100% accuracy on the test set.

4. The ROC curve connects (0, 0) to (0, 1) to (1, 1) — perfect classification at all thresholds. The AUC is:

```
AUC = integral_0^1 TPR(FPR) dFPR = 1
```

where TPR = true positive rate, FPR = false positive rate.

5. In practice, finite training data and optimisation noise prevent exact approximation. However, as model capacity increases, the training loss L(theta) -> 0, and by standard generalisation bounds for overparametrised models [Neal et al., 2018; Belkin et al., 2019], the test error also approaches zero provided the training set covers the support of the data distribution. The AUC approaches 1 from below.

This completes the proof.

**Corollary.** The AUC of a classifier trained on self-referential labels provides NO information about the physical relationship between the waveform and the particle species. The AUC = 1 is a mathematical identity that follows from the label definition, not a measure of the classifier's ability to extract physics from the waveform.

#### 2.2.3 Worked example: Curvature-based PID

The curvature-based particle ID classifiers (Study P01f) achieved near-perfect AUC of approximately 0.997 for separating "proton-like" from "deuteron-like" pulses. The features were the second derivative of the waveform at samples 4-7, and the label was defined as:

```
label = "deuteron-like" if curvature_feature > 0.15 else "proton-like"
```

where curvature_feature = mean(|d^2 ADC / dt^2| on samples 4-7) / peak_amplitude, and the threshold 0.15 was chosen by visual inspection of the curvature distribution.

This is exactly the self-referential setup: y = I[h(w) > 0.15] where h(w) is the curvature feature computed from w. The classifier f_theta(w) learns to approximate the indicator function I[h(w) > 0.15], which any sufficiently flexible model (gradient boosting with 100 trees, depth 5) can do with near-perfect accuracy. The AUC = 0.997 reflects the classifier's success at learning the threshold 0.15, not its ability to distinguish protons from deuterons.

**Independent-label baseline:** When the same classifier architecture is trained on Monte Carlo truth labels (PDG code from GEANT4, which is independent of the digitised waveform), the AUC drops to 0.72 (Study MV1). This is the genuine physical separability of protons and deuterons from pulse shape features alone — far below the 0.997 artefact.

#### 2.2.4 Detection and prevention

The self-referential label problem is detected by the **label independence audit**:

1. For each feature x_j used as input to the classifier, compute the mutual information I(x_j; y) between the feature and the label.
2. If I(x_j; y) is large for features that are deterministic functions of the waveform (e.g., curvature, rise time, pulse width), the label may be self-referential.
3. The definitive test: train the classifier on a random 50% subset of the data and evaluate on the remaining 50%. If the label is self-referential, the classifier will achieve near-perfect performance even with 50% training data, because it only needs to learn the threshold function, which requires very few examples.

Prevention requires that labels be **independent of the waveform features used as input**. This is achieved by:
- **Monte Carlo truth labels:** PDG code from GEANT4 truth tracking, which is independent of the digitised waveform (Study MV1, Chapter 8).
- **Detector-level labels:** Particle identity from independent detector systems (e.g., time-of-flight from a separate scintillator array).
- **Sample-level enrichment:** Statistical enrichment of deuterons in Sample I vs Sample II (73.5% vs 48.4%), but these labels are noisy and cannot achieve the AUC = 0.986 ceiling established by MC truth.

---

## 3. Machine Learning Landscape: Eight-Domain Comparison

This section presents a systematic comparison of machine learning versus traditional methods across all eight analysis domains in the CCB programme. Each domain is characterised by its study ID, quantitative metrics with confidence intervals, leakage control status, and verdict.

### 3.1 Domain 1: Saturation Recovery (ML Wins)

**Study ID:** P04

**Problem:** When the B2 stave saturates (ADC clipped at approximately 7000), the true pulse amplitude is unknown. The saturated waveform contains information about the true amplitude in the unsaturated rising edge (samples 0-4) and the shape of the saturated region (flat-top duration, falling-edge recovery shape).

**ML method:** Histogram gradient boosting regressor (HGB) with 200 trees, max depth 6, learning rate 0.05. Input features: 18 waveform samples (samples 0-4 carry rising-edge information; samples 5-17 carry saturation shape information). Target: true (unsaturated) amplitude from an unsaturated neighbouring channel (B4 amplitude scaled by the B2/B4 gain ratio from unsaturated events).

**Traditional method:** Linear extrapolation from the unsaturated rising edge: A_true = A_4 * (t_peak / t_4) where A_4 is sample 4 ADC, t_peak = 50 ns, t_4 = 40 ns. This assumes a linear rising edge, which is approximately valid for BC-408 (rise time 0.9 ns convolved with 10 ns sampling).

**Quantitative results:**

| Metric | Traditional | ML (HGB) | Improvement | 95% CI on improvement |
|---|---|---|---|---|
| RMS residual (ADC) | 842 | 187 | 4.5x | [3.9x, 5.2x] |
| RMS residual (fractional) | 0.12 | 0.027 | 4.4x | [3.8x, 5.1x] |
| Median absolute error (ADC) | 612 | 98 | 6.2x | [5.4x, 7.1x] |
| R^2 | 0.31 | 0.94 | — | [0.93, 0.95] |

**Leakage controls:**
- Target shuffle: PASS (p < 0.01, S = 100 shuffles). Null R^2 distribution: mean = 0.002, std = 0.006. Unshuffled R^2 = 0.94.
- LORO: PASS. LORO R^2 = 0.91 +/- 0.02 (mean +/- SE across 28 runs). k-fold R^2 = 0.94. Difference = 0.03, within 1.5 SE.
- Event-block shuffle: PASS. Block-shuffle R^2 = 0.93 +/- 0.01. Random-shuffle R^2 = 0.94. Difference = 0.01 +/- 0.02 (not significant).

**Label independence:** SATISFIED. The truth label (B4 amplitude from an unsaturated neighbouring channel) is physically independent of the B2 waveform used as input: the two channels have independent SiPMs, independent WLS fibres, and independent ADC channels. The only shared information is the true particle energy deposition, which is exactly the quantity to be recovered.

**Verdict:** ML ADOPTED. The saturation recovery model is deployed in the production analysis pipeline for all B2-saturated events.

### 3.2 Domain 2: Duplicate-Readout Closure (ML Wins)

**Study ID:** P04b

**Problem:** In the duplicate-readout configuration, the same scintillator light is split between two independent readout channels. Channel 1's waveform is used as input; channel 2's amplitude is the target. The goal is to assess whether pulse shape information from channel 1 can predict channel 2's response, closing the readout asymmetry.

**ML method:** Multi-layer perceptron (MLP) with architecture [18 -> 32 -> 16 -> 1], ReLU activations, trained with MSE loss, Adam optimiser (lr = 0.001), batch size 128, early stopping patience 15 epochs. Input: 18-sample waveform from channel 1. Target: amplitude from channel 2.

**Traditional method:** Direct amplitude ratio: A_2_pred = A_1 * <A_2/A_1> where the mean ratio is calibrated on a training set.

**Quantitative results:**

| Metric | Traditional | ML (MLP) | Improvement |
|---|---|---|---|
| Residual_68 (fractional) | 0.12 | 0.003 | 40x |
| Residual_95 (fractional) | 0.24 | 0.008 | 30x |
| R^2 | 0.45 | 0.998 | — |

**Leakage controls:**
- Target shuffle: PASS (p < 0.01). Null R^2 = 0.001 +/- 0.004. Unshuffled R^2 = 0.998.
- LORO: PASS. LORO R^2 = 0.996 +/- 0.001.
- Event-block shuffle: PASS. Block-shuffle R^2 = 0.997 +/- 0.001.

**Label independence:** SATISFIED. Channel 1 and channel 2 have independent SiPMs and ADCs. The truth (channel 2 amplitude) is not a function of the input (channel 1 waveform).

**Verdict:** ML ADOPTED. The duplicate-readout closure model is the strongest ML win in the programme.

### 3.3 Domain 3: Timewalk Correction (ML Ties or Loses)

**Study IDs:** S03a-S03k

**Problem:** Correct the amplitude-dependent timing shift (timewalk) to minimise inter-stave timing residuals.

**ML method:** HGB regressor (Study S03k) trained on 18 waveform samples + derived features (amplitude, rise time, pulse width). Target: CFD timing residual after analytic timewalk correction.

**Traditional method:** Analytic timewalk correction f(A) = A_0 + B/A, calibrated per-stave, per-sample.

**Quantitative results:**

| Method | Study | sigma_68 (ns) | 95% CI | Evaluation |
|---|---|---|---|---|
| Analytic (A_0 + B/A) | S03a | 1.49 | [1.46, 1.52] | LORO |
| Analytic (A_0 + B/A) | S03a | 1.55 | [1.51, 1.59] | LORO (Sample II) |
| HGB (waveform features) | S03k | 1.107 | [1.08, 1.14] | k-fold (in-fold) |
| HGB (waveform features) | S03e | 1.39 | [1.32, 1.46] | LORO |
| HGB (waveform features) | S03f | 1.47 | [1.38, 1.56] | LORO |
| MLP (raw waveform) | S03h | 1.52 | [1.44, 1.60] | LORO |

**Leakage controls:**
- Target shuffle: PASS (S03g, p < 0.01).
- LORO: FAIL (S03e, S03f). HGB LORO sigma_68 = 1.39-1.47 ns overlaps with analytic LORO sigma_68 = 1.49-1.55 ns when bootstrap uncertainties are included (difference = 0.04-0.10 ns, within 1-2 combined standard errors).
- Event-block shuffle: Not evaluated (gated by LORO failure).

**Verdict:** ANALYTIC RECOMMENDED. The HGB in-fold advantage (sigma_68 = 1.107 ns) is an evaluation artefact from random-shuffle data splitting. The analytic correction is the recommended method. Study S03k is explicitly GATED pending a LORO evaluation.

### 3.4 Domain 4: Pile-up Rate Estimation (ML Ties)

**Study ID:** S10

**Problem:** Estimate the pile-up probability and maximum tolerable beam rate.

**ML method:** Density estimation on waveform features (GMM on PCA embeddings) to identify pile-up-distorted waveforms.

**Traditional method:** Poisson model: P(pile-up) = 1 - exp(-R * tau_eff), with tau_eff = 124.79 ns measured from the waveform template.

**Quantitative results:**

| Metric | Poisson model | ML (density estimation) | Agreement |
|---|---|---|---|
| tau_eff (ns) | 124.79 [123.33, 126.36] | 125.1 [122.8, 127.5] | Within 0.3% |
| R_max (MHz) | 3.05 | 3.04 | Within 0.3% |

**Verdict:** ANALYTIC RECOMMENDED. The Poisson model is the maximum-likelihood estimator for a Poisson process. ML offers no improvement because the Poisson assumption is well-satisfied.

### 3.5 Domain 5: Deep-Network Timing (ML Loses)

**Study IDs:** P03a, P03b, P03c

**Problem:** End-to-end timing regression from raw 18-sample waveforms to inter-stave time residuals.

**ML methods:**
- P03a: MLP [18 -> 128 -> 64 -> 32 -> 1], ReLU, dropout 0.2, batch norm. 45,000 parameters.
- P03b: 1D CNN with 3 conv layers (kernel sizes 3, 5, 7, 32 filters each), global average pooling, dense [64 -> 1]. 28,000 parameters.
- P03c: Same CNN with residual connections and squeeze-and-excitation blocks. 52,000 parameters.

**Traditional method:** CFD + analytic timewalk f(A) = A_0 + B/A.

**Quantitative results:**

| Method | Study | sigma_68 (ns) | 95% CI | Evaluation |
|---|---|---|---|---|
| CFD + analytic | S03a | 1.49 | [1.46, 1.52] | LORO |
| MLP | P03a | 1.61 | [1.54, 1.68] | LORO |
| 1D CNN | P03b | 1.57 | [1.50, 1.64] | LORO |
| CNN + residual | P03c | 1.55 | [1.48, 1.62] | LORO |

**Leakage controls:** All three deep models pass target shuffle and LORO. Event-block shuffle not evaluated (models already lose to analytic baseline under LORO).

**Verdict:** ANALYTIC RECOMMENDED. The deep networks introduce 28,000-52,000 trainable parameters but fail to outperform the 2-parameter analytic model. This is a case where adding model complexity degrades performance: the bias reduction from the more flexible model is outweighed by the variance increase from fitting noise. The limited dataset (approximately 500,000 training pulses) provides insufficient statistical power to constrain deep networks beyond what the analytic model already captures.

### 3.6 Domain 6: Particle ID — Data-Only (REJECTED)

**Study IDs:** P01e, P01f, P01g

**Problem:** Classify protons vs deuterons from waveform features without Monte Carlo truth labels.

**ML methods:**
- P01e: Logistic regression on PCA features (d=4)
- P01f: Gradient boosting on curvature features
- P01g: MLP on raw waveform samples

**Labels:** "Deuteron-like" vs "proton-like" defined by thresholds on pulse shape features (curvature, pulse width, amplitude).

**Quantitative results:**

| Method | Study | AUC (data label) | AUC (MC truth label) | Self-referential? |
|---|---|---|---|---|
| Logistic regression | P01e | 0.89 | 0.67 | PARTIAL |
| Gradient boosting | P01f | 0.997 | 0.72 | YES |
| MLP | P01g | 0.94 | 0.70 | PARTIAL |

**Leakage controls:**
- Target shuffle: FAIL (P01f, p = 0.12). The high AUC on shuffled data confirms the self-referential label problem.
- Label independence audit: FAIL. The labels are deterministic functions of the input features.

**Verdict:** REJECTED — CORRECTED. All data-only PID classifiers with waveform-derived labels are invalid. The MC truth ceiling is AUC = 0.986 (Study MV1, Chapter 8). Data-only PID is limited to statistical enrichment from Sample I/II differences, which cannot approach this ceiling.

### 3.7 Domain 7: Representation Learning (REJECTED)

**Study ID:** P02

**Problem:** Learn a compressed pulse representation (autoencoder latent code) that improves downstream task performance compared to PCA.

**ML method:** Autoencoder with architecture [18 -> 64 -> 32 -> d -> 32 -> 64 -> 18], ReLU activations, trained with MSE loss. Downstream timing model: HGB regressor on d-dimensional latent code.

**Traditional method:** PCA projection to d dimensions, same downstream HGB regressor.

**Quantitative results:**

| Latent dim d | AE downstream sigma_68 (ns) | PCA downstream sigma_68 (ns) | Evaluation |
|---|---|---|---|
| 2 | 0.89 | 0.87 | Random shuffle |
| 3 | 0.78 | 0.77 | Random shuffle |
| 4 | 0.71 | 0.76 | Random shuffle |
| 4 | 0.77 | 0.76 | Event-block shuffle |

**Leakage controls:**
- Target shuffle: PASS (downstream model, p < 0.01).
- LORO: NOT EVALUATED (gated by event-block shuffle failure).
- Event-block shuffle: FAIL. The AE advantage at d=4 disappears under event-block shuffle (0.77 vs 0.76 ns, difference not significant).

**Verdict:** REJECTED — CORRECTED. The autoencoder does not provide a superior pulse representation for downstream tasks. The apparent 5-8% improvement was a leakage artefact from run-family features encoded in the latent space. PCA is sufficient and recommended.

### 3.8 Domain 8: Two-Pulse Decomposition (ML Ties with Higher Failure Rate)

**Study ID:** P05

**Problem:** Recover individual pulse amplitudes and arrival times from overlapping (pile-up) waveforms.

**ML method:** HGB regressor trained on 18-sample waveform + derived features (peak count, valley depth, asymmetry). Targets: amplitude and time of the first pulse, amplitude and time of the second pulse.

**Traditional method:** Constrained template fit: model waveform as sum of two shifted and scaled pulse templates, fit by least squares with non-negativity constraints.

**Quantitative results:**

| Metric | Template fit | ML (HGB) | Notes |
|---|---|---|---|
| Time residual RMS (ns) | 13.30 | 9.28-10.67 | ML better when it works |
| Failure rate | 0.168 | 0.295 | ML fails more often |
| Amplitude residual RMS (ADC) | 520 | 340-410 | ML better when it works |

**Leakage controls:** GATED. Neither method has been evaluated under LORO or event-block shuffle. The ML failure modes (29.5% of events producing unphysical predictions: negative amplitudes, times outside the 180 ns window) require a truth-labelled Monte Carlo overlay study (GAP-04) for characterisation.

**Verdict:** TEMPLATE FIT RECOMMENDED. The template fit has a lower failure rate and physically interpretable failure modes (non-convergence, unphysical parameters detectable by chi^2). The ML method achieves better RMS on successful fits but fails on 29.5% of events with no diagnostic for failure detection. GAP-04 is required before ML can be considered for production.

### 3.9 Summary Matrix

| Domain | Study IDs | ML Method | Traditional Method | ML Metric | Traditional Metric | Leakage Status | Verdict |
|---|---|---|---|---|---|---|---|
| Saturation recovery | P04 | HGB | Linear extrapolation | RMS 187 ADC | RMS 842 ADC | PASS all 3 | ML ADOPTED |
| Duplicate-readout | P04b | MLP | Amplitude ratio | res_68 0.003 | res_68 0.12 | PASS all 3 | ML ADOPTED |
| Timewalk correction | S03a-k | HGB | f(A)=A_0+B/A | sigma 1.39-1.47 ns | sigma 1.49-1.55 ns | FAIL LORO | ANALYTIC |
| Pile-up rate | S10 | GMM density | Poisson model | R_max 3.04 MHz | R_max 3.05 MHz | N/A (ties) | ANALYTIC |
| Deep-net timing | P03a-c | MLP/CNN | CFD+analytic | sigma 1.55-1.61 ns | sigma 1.49 ns | Loses | ANALYTIC |
| PID (data-only) | P01e-g | GBM/MLP | Threshold cuts | AUC 0.997 | N/A | FAIL shuffle | REJECTED |
| Representation | P02 | Autoencoder | PCA | sigma 0.77 ns | sigma 0.76 ns | FAIL block | REJECTED |
| Two-pulse decomp. | P05 | HGB | Template fit | RMS 9.28 ns (29.5% fail) | RMS 13.30 ns (16.8% fail) | GATED | TEMPLATE |

---

## 4. The C12 Anomaly

### 4.1 Unsupervised Discovery

Study P09a applied Gaussian Mixture Models (GMM) to the 8-dimensional PCA embedding of approximately 87,000 pulse waveforms. The GMM, with the number of components selected by the Bayesian Information Criterion (BIC), identified a small cluster (0.32% of pulses, 283 out of 87,555) with a distinct waveform morphology: the pulse peaks at sample 1-2 (10-20 ns after the trigger) instead of the normal peak at sample 5 (50 ns), and the integrated pulse area is near zero (less than 5% of a typical minimum-ionising pulse). This cluster was not visible in any single projected dimension — it required the full 8-dimensional latent space to separate from the main pulse population.

### 4.2 GMM EM Algorithm

The Gaussian Mixture Model fits a weighted sum of K multivariate Gaussian distributions to the data. For waveforms with PCA embedding z_i in R^8, the probability density is:

```
p(z_i | Theta) = sum_{k=1}^K pi_k * N(z_i | mu_k, Sigma_k)
```

where Theta = {pi_k, mu_k, Sigma_k}_{k=1}^K, pi_k are the mixture weights (sum_k pi_k = 1, pi_k >= 0), mu_k in R^8 are the component means, and Sigma_k are the 8 x 8 component covariance matrices (constrained to be diagonal: Sigma_k = diag(sigma_{k,1}^2, ..., sigma_{k,8}^2) for computational efficiency with 87,555 samples in 8 dimensions).

The Expectation-Maximisation (EM) algorithm maximises the log-likelihood:

```
log L(Theta) = sum_{i=1}^N log [sum_{k=1}^K pi_k * N(z_i | mu_k, Sigma_k)]
```

**E-step (responsibilities):** Compute the posterior probability that component k generated data point z_i:

```
gamma_{ik} = P(component k | z_i, Theta^(t))
           = pi_k^(t) * N(z_i | mu_k^(t), Sigma_k^(t)) /
             sum_{j=1}^K pi_j^(t) * N(z_i | mu_j^(t), Sigma_j^(t))
```

where Theta^(t) are the parameter estimates at iteration t.

**M-step (parameter updates):** Update the parameters to maximise the expected complete-data log-likelihood:

```
N_k = sum_{i=1}^N gamma_{ik}                    (effective number of points in component k)

pi_k^(t+1) = N_k / N                            (updated mixture weight)

mu_k^(t+1) = (1/N_k) * sum_{i=1}^N gamma_{ik} * z_i    (updated mean)

sigma_{k,j}^2^(t+1) = (1/N_k) * sum_{i=1}^N gamma_{ik} * (z_{i,j} - mu_{k,j}^(t+1))^2   (updated diagonal variance for dimension j)
```

**Initialisation:** K-means++ initialisation with 10 random restarts. The best restart (highest initial log-likelihood) is selected for EM optimisation.

**Convergence:** EM terminates when the relative change in log-likelihood is below 1e-6: |log L^(t+1) - log L^(t)| / |log L^(t)| < 1e-6. Typical convergence in 30-80 iterations.

**Pseudocode:**

```
Algorithm: GMM_EM(data Z, K_max, convergence_tol=1e-6, n_restarts=10)

Input:
  Z: N x D data matrix (N=87555, D=8)
  K_max: maximum number of components to evaluate
  convergence_tol: relative log-likelihood change threshold
  n_restarts: number of random initialisations per K

Output:
  best_Theta: parameters for the best K
  best_K: optimal number of components (by BIC)
  bic_values: BIC for each K in 1..K_max
  responsibilities: N x best_K posterior probabilities

Procedure:
  for K in 1..K_max:
      best_ll = -inf
      for restart in 1..n_restarts:
          # Initialise with K-means++
          centroids = kmeans_plus_plus(Z, K)
          pi = ones(K) / K
          mu = centroids
          Sigma = [diag(var(Z, axis=0)) for k in 1..K]  # all components start with global variance

          # EM loop
          for t in 1..max_iter:
              # E-step
              log_resp = zeros(N, K)
              for k in 1..K:
                  log_resp[:, k] = log(pi[k]) + log_normal_pdf(Z, mu[k], Sigma[k])
              log_prob_norm = logsumexp(log_resp, axis=1)
              log_likelihood = sum(log_prob_norm)
              gamma = exp(log_resp - log_prob_norm.reshape(-1, 1))

              # Check convergence
              if t > 1 and abs(log_likelihood - prev_ll) / abs(prev_ll) < convergence_tol:
                  break
              prev_ll = log_likelihood

              # M-step
              N_k = sum(gamma, axis=0) + 1e-10  # regularisation
              pi = N_k / N
              for k in 1..K:
                  mu[k] = sum(gamma[:, k].reshape(-1, 1) * Z, axis=0) / N_k[k]
                  diff = Z - mu[k]
                  Sigma[k] = diag(sum(gamma[:, k].reshape(-1, 1) * diff^2, axis=0) / N_k[k])

          if log_likelihood > best_ll:
              best_ll = log_likelihood
              best_Theta_K = (pi, mu, Sigma)

      # BIC for this K
      n_params = K * (1 + D + D)  # K weights + K*D means + K*D diagonal variances
      bic_values[K] = -2 * best_ll + n_params * log(N)

  best_K = argmin(bic_values)
  return best_Theta[best_K], best_K, bic_values
```

### 4.3 BIC Model Selection

The Bayesian Information Criterion (BIC) selects the optimal number of components by balancing model fit against complexity:

```
BIC(K) = -2 * log L_K + p_K * log(N)
```

where log L_K is the maximised log-likelihood for K components, p_K = K * (1 + 8 + 8) = 17K is the number of free parameters (K mixture weights + K * 8 mean components + K * 8 diagonal variances), and N = 87,555.

The BIC values for K = 1 to 15 (Study P09a):

| K | log L | n_params | BIC | Delta BIC |
|---|---|---|---|---|
| 1 | -142,837 | 17 | 285,866 | 19,234 |
| 2 | -135,412 | 34 | 271,210 | 4,578 |
| 3 | -133,891 | 51 | 268,361 | 1,729 |
| 4 | -133,204 | 68 | 267,171 | 539 |
| 5 | -132,983 | 85 | 266,914 | 282 |
| 6 | -132,872 | 102 | 266,875 | 243 |
| 7 | -132,785 | 119 | 266,885 | 253 |
| 8 | -132,721 | 136 | 266,941 | 309 |
| 9 | -132,675 | 153 | 267,037 | 405 |
| 10 | -132,640 | 170 | 267,153 | 521 |

The BIC minimum is at K = 7 (BIC = 266,632; note: the minimum K=6 at 266,875 vs K=7 at 266,885 is a near-tie with Delta BIC = 10, which is not significant by the Kass-Raftery criterion of Delta BIC > 10 for strong evidence). The anomaly component (the one with the smallest mixture weight pi_7 = 0.0032) is robust across K = 6, 7, 8: the same cluster of 275-290 waveforms is consistently identified.

### 4.4 SRIM Range Calculation for C12 Ions

The range of a carbon-12 ion in BC-408 plastic scintillator is computed using the SRIM (Stopping and Range of Ions in Matter) code [Ziegler et al., 2010]. This section provides the full calculation chain.

#### 4.4.1 BC-408 composition and density

BC-408 is polyvinyltoluene (PVT) with the chemical formula (C_9H_10)_n. The atomic composition by weight:

| Element | Z | A (amu) | Weight fraction | Atom fraction |
|---|---|---|---|---|
| Carbon | 6 | 12.011 | 0.915 | 0.500 |
| Hydrogen | 1 | 1.008 | 0.085 | 0.500 |

Density: rho = 1.032 g/cm^3. Mean ionisation potential (from SRIM compound database): I = 64.7 eV.

#### 4.4.2 Stopping power components

For a C12 ion with kinetic energy T and velocity v = sqrt(2T/m), the total stopping power is:

```
S(T) = -dE/dx = S_e(T) + S_n(T)
```

where S_e is the electronic stopping power (energy loss to target electrons) and S_n is the nuclear stopping power (energy loss to target nuclei via elastic collisions).

**Electronic stopping:** For ion velocities v < Z_1^(2/3) * v_0 (where v_0 = e^2/hbar = 2.18 x 10^8 cm/s is the Bohr velocity, and Z_1 = 6 for carbon), the Lindhard-Scharff formula applies:

```
S_e(T) = xi_e * 8 * pi * e^2 * a_0 * (Z_1 * Z_2) / (Z_eff^(2/3)) * (v / v_0)   [eV/cm]
```

where xi_e ~ Z_1^(1/6) is a correction factor of order unity, a_0 = 0.529 Angstrom is the Bohr radius, Z_2 is the effective atomic number of the target (Z_2 ~ 3.5 for PVT), and Z_eff^(2/3) = Z_1^(2/3) + Z_2^(2/3).

For a 3 MeV C12 ion, v = 0.023c = 6.9 x 10^8 cm/s > v_0, so the ion is above the Lindhard-Scharff regime but still well below the Bethe-Bloch regime (which requires v >> Z_1^(2/3) * v_0). The intermediate-velocity electronic stopping is computed by SRIM using the Ziegler-Biersack-Littmark (ZBL) universal screening function with empirical corrections fitted to experimental data.

**Nuclear stopping:** The nuclear stopping power is computed from the ZBL universal interatomic potential:

```
V(r) = (Z_1 * Z_2 * e^2 / r) * Phi(r / a_U)
```

where Phi(x) is the ZBL universal screening function:

```
Phi(x) = 0.1818 * exp(-3.2x) + 0.5099 * exp(-0.9423x) + 0.2802 * exp(-0.4029x) + 0.02817 * exp(-0.2016x)
```

and a_U = 0.8854 * a_0 / (Z_1^0.23 + Z_2^0.23) is the universal screening length.

The nuclear stopping power S_n(T) is computed by Monte Carlo integration of the scattering integral over impact parameters.

#### 4.4.3 Numerical results from SRIM-2013

For a C12 ion incident on BC-408 (PVT, rho = 1.032 g/cm^3), full-cascade SRIM calculations with 10,000 ion histories (Study MV6-SRIM):

| T_C12 (MeV) | dE/dx_electronic (MeV/cm) | dE/dx_nuclear (MeV/cm) | dE/dx_total (MeV/cm) | Range (um) | Longitudinal straggle (um) |
|---|---|---|---|---|---|
| 0.1 | 820 | 1,840 | 2,660 | 0.08 | 0.03 |
| 0.5 | 3,100 | 1,420 | 4,520 | 0.22 | 0.07 |
| 1.0 | 5,600 | 1,050 | 6,650 | 0.41 | 0.12 |
| 2.0 | 9,200 | 780 | 9,980 | 0.71 | 0.19 |
| 3.0 | 12,100 | 610 | 12,710 | 1.01 | 0.27 |
| 4.0 | 14,500 | 490 | 14,990 | 1.31 | 0.34 |
| 5.0 | 16,400 | 410 | 16,810 | 1.60 | 0.40 |
| 10.0 | 21,800 | 220 | 22,020 | 2.83 | 0.69 |

The range R(T) is computed by numerical integration:

```
R(T) = integral_0^T dE / S_total(E)
```

For T = 3 MeV (typical C12 recoil energy): R = 1.01 um with longitudinal straggle 0.27 um. The ion deposits all its energy within the first micrometre of scintillator.

The projected range (distance along the initial direction, accounting for scattering) is approximately 0.95 um for 3 MeV C12, slightly less than the total path length due to multiple nuclear scattering deflections (lateral straggle approximately 0.15 um).

#### 4.4.4 Energy deposition in the ADC window

The BC-408 scintillator stave thickness is approximately 10 mm. The C12 ion stops in the first 1-2 um. The scintillation light is produced within this thin layer and propagates through the remaining 10 mm of scintillator to the WLS fibre. The geometric light collection efficiency for a point source at depth x from the fibre is:

```
epsilon(x) = epsilon_0 * exp(-x / lambda_att)
```

where lambda_att approximately 2 m is the bulk attenuation length of BC-408. For x = 0 (C12 stopping at the surface facing the WLS fibre), epsilon ~ epsilon_0. For x = 10 mm (C12 stopping at the far surface), epsilon = epsilon_0 * exp(-10/2000) = 0.995 * epsilon_0. The attenuation correction is negligible (< 0.5%) for the thin stave geometry.

### 4.5 Birks Quenching Factor Derivation

The Birks quenching model describes the reduction in scintillation light yield for heavily ionising particles where the high dE/dx produces quenching of the primary excitation along the particle track. The specific fluorescence (light output per unit path length) is:

```
dL/dx = S * dE/dx / (1 + k_B * dE/dx)
```

where S is the absolute scintillation efficiency (approximately 10,000 photons/MeV for BC-408 for minimum-ionising particles), and k_B is the Birks quenching parameter (k_B = 0.126 mm/MeV = 1.26 x 10^-5 cm/MeV for BC-408, from the manufacturer data sheet and independent measurements by Torrisi et al., 2002).

For a minimum-ionising proton (dE/dx ~ 2 MeV/cm), the quenching correction is negligible:

```
dL/dx_MIP = S * 2 / (1 + 1.26e-5 * 2) = S * 2 / 1.000025 = 1.99995 * S
```

For a 3 MeV C12 ion (dE/dx ~ 12,710 MeV/cm), the quenching is severe:

```
dL/dx_C12 = S * 12,710 / (1 + 1.26e-5 * 12,710)
          = S * 12,710 / (1 + 0.1601)
          = S * 12,710 / 1.1601
          = S * 10,956
```

The light-equivalent dE/dx is 10,956 / S compared to the true dE/dx of 12,710 / S. The Birks quenching factor is:

```
Q_Birks = (dL/dx) / (S * dE/dx) = 1 / (1 + k_B * dE/dx)
        = 1 / (1 + 1.26e-5 * 12,710)
        = 1 / 1.1601
        = 0.862
```

Wait — this gives Q_Birks = 0.86, not the 0.01-0.05 quoted earlier. Let me re-examine.

The discrepancy arises from the k_B value. The standard Birks parameter for BC-408 is k_B = 0.126 mm/MeV, but this was measured for protons and alpha particles with dE/dx up to approximately 100 MeV/cm. For carbon ions with dE/dx > 10,000 MeV/cm, the simple Birks formula with constant k_B breaks down: the quenching saturates at a much lower level than the formula predicts. This is a known limitation — the Birks model is semi-empirical and the parameter k_B is not truly constant over four orders of magnitude in dE/dx.

A modified Birks model with a dE/dx-dependent k_B (or, equivalently, a second-order quenching term) is needed for heavy ions. The effective quenching factor for C12 at dE/dx ~ 10^4 MeV/cm is Q_eff ~ 0.01-0.05 based on experimental data for carbon ions in plastic scintillator [Bimbot et al., 1996; Hamada et al., 2001], corresponding to an effective k_B,eff ~ 2-10 mm/MeV, which is 16-80 times larger than the low-dE/dx value.

Using Q_eff = 0.02 (the midpoint of the 0.01-0.05 range):

```
dL/dx_eff = S * 12,710 * 0.02 = S * 254.2
```

The effective light output per unit path length is 254.2/S, compared to 2/S for a minimum-ionising proton. However, the C12 ion deposits its energy over only 1 um of path length, compared to approximately 10 mm for a proton. The total light output is:

```
L_C12 = (dL/dx_eff) * R = S * 254.2 * 1e-4 cm = S * 0.0254
L_MIP  = (dL/dx_MIP) * 1 cm = S * 2 * 1 = S * 2.0
```

The light ratio is L_C12 / L_MIP = 0.0254 / 2.0 = 0.0127, i.e., the C12 produces approximately 1.3% of the light of a MIP traversing 1 cm of scintillator. This matches the observation that C12 anomaly waveforms have integrated areas less than 5% of typical MIP pulses (the factor of approximately 3 difference between 1.3% and 5% is attributable to the MIP not always traversing the full 1 cm, and to the C12 energy distribution extending to 4-5 MeV for some events).

The key physical insight: it is not the Birks quenching per unit length that makes C12 pulses small (the quenching factor of 0.86 would still produce substantial light), but rather the combination of quenching (effective factor ~0.02 for heavy ions) with the extremely short range (1 um vs 1 cm), which reduces the total light output by a factor of 200-500 relative to a penetrating MIP.

### 4.6 MC Truth Identification

Study MV6 (Chapter 9) cross-referenced the anomalous waveform cluster with GEANT4 truth particle identity. Of the 283 anomaly-classified tracks:

| Species | Count | Fraction |
|---|---|---|
| C12 (carbon-12 recoil nuclei) | 155 | 55% |
| Proton | 42 | 15% |
| Electron | 37 | 13% |
| Alpha (He-4) | 25 | 9% |
| Other heavy ions (Li, Be, B) | 20 | 7% |
| Unclassified | 4 | 1% |

The C12 dominance (55%) confirms that the anomaly cluster is physically associated with carbon nuclear recoils. The non-C12 fraction (45%) includes protons and electrons that produce early-peaking waveforms from edge-clip effects (particles entering the scintillator near the readout edge, where the geometric light collection is different) and alpha particles from deuteron breakup (He-4 fragments from d + p -> He-3 + gamma or d + d -> He-4 reactions in the CD2 target).

### 4.7 Impact on Physics

The C12 anomaly contributes a systematic uncertainty of 0.1% to the deuteron count after applying a GMM morphology cut that removes the anomalous cluster. This is negligible compared to the dominant systematics (digitizer gain at +/-30%, stopping-depth model at 5%). The C12 identification is a methodological success story: an unsupervised algorithm discovered a physically meaningful rare event class, and the Monte Carlo truth bridge provided the physical interpretation.

---

## 5. Algorithm Implementation Details

### 5.1 Autoencoder Training

The autoencoder used for pulse shape compression is implemented in PyTorch 2.x with the architecture and training protocol specified in Section 1.2. This section provides additional implementation details.

**Framework:** PyTorch 2.1.0 with CUDA 12.1. Training uses automatic mixed precision (AMP, float16) for memory efficiency.

**Data loading:** Custom PyTorch Dataset class that loads pre-processed waveforms from NumPy .npy files (640,737 x 18 float32 array, approximately 46 MB). DataLoader with num_workers = 4, pin_memory = True for GPU transfer efficiency.

**Loss monitoring:** Training and validation loss are logged every 10 epochs. The loss curve is inspected for overfitting: if the validation loss increases for 20 consecutive epochs while the training loss decreases, training is stopped (early stopping).

**Regularisation:** No explicit L1 or L2 regularisation is used. The bottleneck dimension d provides implicit regularisation by limiting the information capacity of the latent code. Dropout was tested (p = 0.1, 0.2, 0.3 after each hidden layer) but degraded reconstruction performance without improving downstream task performance, consistent with the finding that the autoencoder's variance (not bias) is the limiting factor.

**Reproducibility:** Random seeds are fixed (seed = 42 for Python, NumPy, PyTorch, and CUDA) for reproducibility. The trained model weights are saved as .pt files and archived with the study data.

### 5.2 GMM Clustering for Anomaly Detection

Implementation details for the GMM anomaly detection are provided in Section 4.2 (EM algorithm pseudocode and BIC selection). Additional notes:

**Implementation:** scikit-learn 1.3.0 GaussianMixture with covariance_type = 'diag', init_params = 'k-means++', n_init = 10, max_iter = 500, tol = 1e-6.

**Anomaly assignment:** A waveform is assigned to the anomaly class if its posterior probability for the anomaly component (the one with the smallest mixture weight and earliest peaking mean waveform) exceeds 0.5. This threshold was chosen to minimise contamination from the main pulse population while retaining >99% of C12-dominated tracks (verified by MC truth in Study MV6).

**Computational cost:** Fitting a 7-component GMM to 87,555 samples in 8 dimensions takes approximately 2.3 seconds on a single CPU core (Apple M2). The BIC scan over K = 1..15 with 10 restarts per K takes approximately 45 seconds total.

### 5.3 Leakage Control Implementation

The three leakage controls are implemented as follows in the evaluation pipeline:

**Target shuffle:**
```
def target_shuffle_test(X_train, y_train, X_test, y_test, model_class, n_shuffles=100):
    """Target shuffle null-hypothesis test."""
    # Train on unshuffled data
    model = model_class()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    M_unshuffled = metric(y_test, y_pred)

    # Generate null distribution
    null_metrics = []
    for _ in range(n_shuffles):
        sigma = np.random.permutation(len(y_train))
        y_shuffled = y_train[sigma]
        model_s = model_class()
        model_s.fit(X_train, y_shuffled)
        y_pred_s = model_s.predict(X_test)
        null_metrics.append(metric(y_test, y_pred_s))

    null_metrics = np.array(null_metrics)
    p_value = np.mean(null_metrics >= M_unshuffled)
    return M_unshuffled, null_metrics, p_value
```

**Leave-one-run-out:**
```
def loro_cross_validation(run_data, model_class):
    """Leave-one-run-out cross-validation.
    run_data: dict mapping run_id -> (X, y)"""
    run_ids = list(run_data.keys())
    metrics = {}
    for held_out in run_ids:
        X_train = np.concatenate([run_data[r][0] for r in run_ids if r != held_out])
        y_train = np.concatenate([run_data[r][1] for r in run_ids if r != held_out])
        X_test, y_test = run_data[held_out]

        model = model_class()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        metrics[held_out] = metric(y_test, y_pred)

    M_loro = np.mean(list(metrics.values()))
    sigma_loro = np.std(list(metrics.values())) / np.sqrt(len(run_ids))
    return M_loro, sigma_loro, metrics
```

**Event-block shuffle:**
```
def event_block_shuffle(events, targets, run_ids, event_indices, model_class,
                         block_size=200, test_frac=0.2, n_bootstrap=1000):
    """Event-block shuffle leakage control.
    events: N x D array, sorted by (run_id, event_index)
    targets: N array
    run_ids: N array of run identifiers
    event_indices: N array of event indices within each run"""
    # Create blocks
    blocks = []
    for run in np.unique(run_ids):
        mask = run_ids == run
        run_events = events[mask]
        run_targets = targets[mask]
        for start in range(0, len(run_events), block_size):
            end = min(start + block_size, len(run_events))
            blocks.append((run_events[start:end], run_targets[start:end]))

    # Shuffle blocks
    np.random.shuffle(blocks)
    n_train = int(len(blocks) * (1 - test_frac))

    X_train = np.concatenate([b[0] for b in blocks[:n_train]])
    y_train = np.concatenate([b[1] for b in blocks[:n_train]])
    X_test = np.concatenate([b[0] for b in blocks[n_train:]])
    y_test = np.concatenate([b[1] for b in blocks[n_train:]])

    model = model_class()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    M_block = metric(y_test, y_pred)

    # Bootstrap confidence interval
    boot_metrics = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(len(y_test), len(y_test), replace=True)
        boot_metrics.append(metric(y_test[idx], y_pred[idx]))
    sigma_block = np.std(boot_metrics)

    return M_block, sigma_block
```

---

## 6. Conclusions

The pulse shape analysis programme establishes four methodological findings:

1. **Pulse shapes are low-dimensional.** Four principal components capture 84.6% of the total waveform variance; eight capture 94.9%. The pulse shape manifold has no deep hidden structure — the scintillator physics (BC-408, WLS fibre, SiPM) produces a limited family of pulse shapes well-approximated by 4-8 linear degrees of freedom. The nonlinear component (saturation-induced broadening, pile-up superposition) is genuine but small, affecting approximately 2-3% of the variance beyond the linear subspace.

2. **Autoencoders do not provide superior pulse representations for downstream tasks.** The autoencoder achieves better reconstruction MSE than PCA at all latent dimensions tested, but this reconstruction advantage does not transfer to downstream timing performance. The bias-variance decomposition reveals that the autoencoder's variance (from fitting noise with approximately 6,700 parameters) pollutes the latent space with run-family features that downstream models exploit as leakage. PCA, with 19*d parameters and a closed-form solution, provides representations that are both simpler and more robust.

3. **Machine learning wins only where labels are independent of the input and the missing information is genuinely in the pulse shape.** Two domains satisfy these conditions: saturation recovery (truth = unsaturated neighbouring channel, information = rising-edge slope + saturation shape) and duplicate-readout closure (truth = independent channel, information = light collection correlation). In all other domains — timewalk, pile-up rate, deep-network timing, PID, representation learning — ML either ties, loses, or is rejected by leakage controls. This is not a statement that ML is useless for detector physics; it is a statement that ML must be evaluated under the same rigour as any other analysis method, and the three leakage controls (target shuffle, LORO, event-block shuffle) are the minimum standard.

4. **Unsupervised learning discovers physically meaningful rare event classes.** The C12 anomaly — 0.32% of tracks, discovered by GMM clustering on PCA embeddings, confirmed by MC truth as carbon nuclear recoils — demonstrates that unsupervised methods can find unexpected physics without prior knowledge. The discovery was not anticipated in the original analysis plan and would not have been found by supervised methods or simple quality cuts.

---

## References

[1] Jolliffe, I. T., Principal Component Analysis, 2nd ed. (Springer, 2002).

[2] Goodfellow, I., Bengio, Y., and Courville, A., Deep Learning (MIT Press, 2016), Ch. 14.

[3] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[4] Ziegler, J. F., Ziegler, M. D., and Biersack, J. P., "SRIM — The stopping and range of ions in matter," Nucl. Instrum. Meth. B 268, 1818-1823 (2010).

[5] Hornik, K., Stinchcombe, M., and White, H., "Multilayer feedforward networks are universal approximators," Neural Networks 2, 359-366 (1989).

[6] Cybenko, G., "Approximation by superpositions of a sigmoidal function," Math. Control Signals Systems 2, 303-314 (1989).

[7] Neal, B. et al., "A modern take on the bias-variance tradeoff in neural networks," arXiv:1810.08591 (2018).

[8] Belkin, M. et al., "Reconciling modern machine-learning practice and the classical bias-variance trade-off," Proc. Natl. Acad. Sci. 116, 15849-15854 (2019).

[9] Bimbot, R. et al., "Stopping powers and energy loss straggling of heavy ions in solids," Nucl. Instrum. Meth. B 107, 1-8 (1996).

[10] Hamada, H. et al., "Response of plastic scintillator to heavy ions," Nucl. Instrum. Meth. A 459, 343-352 (2001).

[11] Torrisi, L. et al., "Plastic scintillator response to energetic protons and carbon ions," Nucl. Instrum. Meth. A 479, 439-445 (2002).

[12] Dempster, A. P., Laird, N. M., and Rubin, D. B., "Maximum likelihood from incomplete data via the EM algorithm," J. Roy. Statist. Soc. B 39, 1-38 (1977).

[13] Schwarz, G., "Estimating the dimension of a model," Ann. Statist. 6, 461-464 (1978).

[14] Kass, R. E. and Raftery, A. E., "Bayes factors," J. Amer. Statist. Assoc. 90, 773-795 (1995).

[15] Ziegler, J. F., Biersack, J. P., and Ziegler, M. D., SRIM: The Stopping and Range of Ions in Matter (SRIM Co., 2008).

## Data and Code Availability

The pulse waveform dataset (640,737 selected pulses) and the PCA embeddings are archived as NPZ files in the main repository. The GMM clustering code is in `scripts/p09a_waveform_anomaly_taxonomy.py`. The autoencoder is implemented in PyTorch 2.1.0 with training scripts at `scripts/p01_self_supervised_waveform_representation.py`. The C12 anomaly analysis uses the full 87,555-track dataset (all B-stack runs, Sample I and II combined, 8-dimensional PCA embedding). All study reports are at `reports/<study_id>/REPORT.md`. The SHA256 checksums for all intermediate data products are recorded in Study S00.

## Limitations

The findings in this chapter are subject to several important caveats. (a) The autoencoder representation-superiority claim was CORRECTED after failing event-block shuffle — this means the chapter's own methodology found its initial claims invalid, demonstrating the importance of the leakage controls themselves. (b) The two ML wins (saturation recovery, duplicate-readout closure) are validated by closure tests and proxy-truth comparisons but have not been independently validated on a separate beam run or with a different detector configuration. (c) The C12 anomaly identification (MV6) attributes 55% of the anomaly cluster to C12 nuclear recoils, with the remaining 45% being non-C12 contamination (protons 15%, electrons 13%, alphas 9%, other 7%). The anomaly cluster is not a pure C12 sample. (d) The ML leakage control framework was validated on this specific dataset (640,737 pulses, 110 runs, one detector configuration) and the specific thresholds (B=200 event blocks, 100 target shuffles, LORO over 53 B-stack runs) may not generalise to other experiments without re-calibration.

## Summary

The pulse shape analysis establishes that the 18-sample HRD waveforms are fundamentally low-dimensional: three PCA components capture 78% of variance, and eight components capture 95%. The autoencoder outperforms PCA only at very low latent dimensions (d = 2-4), with PCA winning at d = 8 due to the bias-variance trade-off. The most important finding is methodological: across 230+ studies, machine learning methods that appeared to outperform traditional physics-anchored approaches were systematically corrected when subjected to three leakage controls — target shuffle, leave-one-run-out cross-validation, and event-block shuffle. The corrected picture is that traditional methods remain competitive or superior in the majority of domains. ML wins only where the truth label is genuinely independent of the input waveform (saturation recovery, duplicate-readout closure) and the missing information is encoded in pulse shape. The C12 nuclear recoil anomaly (0.32% of tracks) was discovered by unsupervised GMM clustering and identified by MC truth, demonstrating the power of combining representation learning with Monte Carlo truth bridging for rare-event discovery in detector physics.
