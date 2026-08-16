#!/usr/bin/env python3
"""S46a — #1179: sampled-level closure of the 190-MeV p-d source-model
uncertainty envelope + lab-frame quantile bands.

What this adds over `results/research/sigma_cm_source_uncertainty_v1.json`
(commit af0c3989, PR #1186):

1. SAMPLED validation of the analytic envelope using the exact inverse-CDF
   sampler law of #1178 (`linear_node_pdf_exact_inverse_v1` +
   `measured_table_support_truncate_v1`), replicated bit-compatibly with the
   audited `inverse_linear_pdf_fraction` (known-answer cross-check) and the
   analytic CDF (u -> theta -> CDF round-trip at machine precision).
2. Common-random-number design: every nuisance configuration consumes the
   SAME uniform draws, so paired quantile-shift curves are deterministic
   functions of the draw; the empirical CDF sup-difference retains only
   O(sqrt(p(1-p)/N)) ~ 1e-4 binomial noise (vs a 1.4e-2 envelope), gated
   with an explicit tolerance MC_TOL.
3. The issue's four negative controls, executed and gated:
   (a) fully common multiplicative normalization leaves the normalized shape
       invariant (analytic 3.3e-16; sampled ~1 ULP);
   (b) alternating +-3% point perturbation does NOT cancel (shape moves);
   (c) zero-uncertainty reproduces the nominal sample bit-exactly;
   (d) the sampled excursion of every box configuration stays inside the
       analytic non-probabilistic envelope (no double counting: envelope
       bounds, never adds).
4. Row-statistical delta-method cross-check by 200 seeded iid replica
   samplers (empirical sd vs the v1 diagonal delta-method prediction).
5. theta_cm -> theta_lab mapping of the envelope bands via exact two-body
   relativistic kinematics, round-trip-validated against the repo's own
   `weight_adapter._reconstruct_cm_theta` (S21b exact, #1053).

Scientific boundary (unchanged from v1): source-level deterministic/
conditional uncertainty research only. The 3% node box is a sensitivity
envelope, not a confidence region or an inferred covariance. No detector
response, production Geant4 sample, or detector-performance claim is
validated. Absolute-yield/rate estimands must restore the common
normalization mode (it cancels from the normalized shape only).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TICKET = "1786866977.1138000"
STUDY = f"{TICKET}.3f71d0b1__s46a_cs_source_uncertainty_sampled_closure"
OUT = ROOT / "reports" / STUDY
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
SOURCE_JSON = ROOT / "geant4/src_patch/sigma_pd_cm_190.source.json"
V1_JSON = ROOT / "results/research/sigma_cm_source_uncertainty_v1.json"
V2_JSON = ROOT / "results/research/sigma_cm_source_uncertainty_v2.json"
SAMPLER_TOOL = ROOT / "tools/audit/research_sigma_cm_sampler_contract.py"

SEED = 1179
N_SAMPLE = 5_000_000
N_REPLICAS = 200
M_REPLICA = 200_000
BOX = 0.03                 # published point-to-point systematic at 190 MeV
COMMON_SCALE = 1.045       # published total systematic bound (<4.5%)
SPLIT_DEG = 46.951812      # v1 max-excursion angle (both directions)
MP, MD, TP = 938.2720813, 1875.6129426, 190.0

QUANTILES = np.round(np.arange(0.005, 1.0, 0.005), 4)


def pyfy(o):
    """Recursively convert numpy scalars to plain Python types for JSON."""
    if isinstance(o, dict):
        return {k: pyfy(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [pyfy(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def read_table() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = [ln.split() for ln in TABLE.read_text().splitlines() if ln.strip()]
    ang = np.array([float(r[0]) for r in rows])
    sig = np.array([float(r[1]) for r in rows])
    stat = np.array([float(r[2]) for r in rows])
    if not (len(ang) == 28 and np.all(np.diff(ang) > 0)
            and np.all(sig > 0) and np.all(stat >= 0)):
        raise SystemExit("table contract violated")
    return ang, sig, stat


# --------------------------------------------------------------------------
# Exact inverse-CDF sampler (law of #1178: piecewise-linear pdf through the
# node values sigma_i * sin(theta_i); trapezoid interval masses; analytic
# quadratic interval inverse).
# --------------------------------------------------------------------------
class Sampler:
    def __init__(self, angles_deg: np.ndarray, sigma: np.ndarray):
        self.th = np.radians(angles_deg)
        self.node = sigma * np.sin(self.th)
        self.dm = np.diff(self.th)
        self.m = 0.5 * (self.node[:-1] + self.node[1:]) * self.dm
        self.Z = float(self.m.sum())
        self.cum = np.concatenate([[0.0], np.cumsum(self.m)])

    def invert(self, u: np.ndarray) -> np.ndarray:
        """u in [0,1) -> theta (radians), exact quadratic interval inverse."""
        x = np.clip(u, 0.0, 1.0 - 1e-15) * self.Z
        i = np.clip(np.searchsorted(self.cum, x, side="right") - 1,
                    0, len(self.m) - 1)
        a = self.node[i]
        b = self.node[i + 1]
        f = (x - self.cum[i]) / self.m[i]
        s = np.maximum(a, b)
        a_s, b_s = a / s, b / s
        disc = np.maximum(a_s * a_s + (b_s * b_s - a_s * a_s) * f, 0.0)
        denom = a_s + np.sqrt(disc)
        t = np.where(denom > 0, f * (a_s + b_s) / np.where(denom > 0, denom, 1),
                     np.sqrt(f))
        lin = np.abs(b_s - a_s) < 1e-15
        t = np.where(lin, f, t)
        t = np.clip(t, 0.0, 1.0)
        return self.th[i] + t * self.dm[i]

    def mean_var_cm_deg(self) -> tuple[float, float]:
        """Exact mean/variance of theta_cm (deg) under the linear-pdf law."""
        a, b = self.node[:-1], self.node[1:]
        L, D = self.th[:-1], self.dm
        c = b - a
        m1 = D * (L * (a + c / 2.0) + D * (a / 2.0 + c / 3.0))
        m2 = D * (L * L * (a + c / 2.0)
                  + 2.0 * L * D * (a / 2.0 + c / 3.0)
                  + D * D * (a / 3.0 + c / 4.0))
        mu = float(m1.sum() / self.Z)
        var = float(m2.sum() / self.Z - mu * mu)
        return math.degrees(mu), math.degrees(math.sqrt(var))

    def cdf(self, theta_rad: np.ndarray) -> np.ndarray:
        theta = np.clip(theta_rad, self.th[0], self.th[-1])
        i = np.clip(np.searchsorted(self.th, theta, side="right") - 1,
                    0, len(self.m) - 1)
        left, right = self.th[i], self.th[i + 1]
        a, b = self.node[i], self.node[i + 1]
        t = (theta - left) / (right - left)
        seg = (a * t + 0.5 * (b - a) * t * t) * (right - left)
        return (self.cum[i] + seg) / self.Z


def load_repo_inverse():
    spec = importlib.util.spec_from_file_location("sampler_contract", SAMPLER_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.inverse_linear_pdf_fraction


# --------------------------------------------------------------------------
# Lab-frame kinematics: scattered proton, p + d(0,0,0) -> p + d, Tp = 190 MeV.
# --------------------------------------------------------------------------
def theta_lab_of_theta_cm(theta_cm_rad: np.ndarray):
    e1 = TP + MP
    p1 = math.sqrt(TP * TP + 2.0 * TP * MP)
    beta = p1 / (e1 + MD)
    gamma = 1.0 / math.sqrt(1.0 - beta * beta)
    ecm = math.sqrt((e1 + MD) ** 2 - p1 * p1)
    ekincm = ecm - MP - MD
    ekin3cm = (ekincm / 2.0) * (ekincm + 2.0 * MD) / ecm
    e3cm = ekin3cm + MP
    pcm = math.sqrt(e3cm * e3cm - MP * MP)
    ppar_star = pcm * np.cos(theta_cm_rad)
    pperp_star = pcm * np.sin(theta_cm_rad)
    ppar = gamma * (ppar_star + beta * e3cm)
    pperp = pperp_star
    e_lab = gamma * (e3cm + beta * ppar_star)
    theta_lab = np.arctan2(pperp, ppar)
    ekin_lab = e_lab - MP
    return theta_lab, ekin_lab


GL8_X, GL8_W = np.polynomial.legendre.leggauss(8)


def mean_lab_deg(sampler: "Sampler") -> float:
    """Exact mean theta_lab (deg): 8-pt Gauss-Legendre per interval over the
    smooth monotone theta_cm -> theta_lab map (converged to machine noise)."""
    a, b = sampler.node[:-1], sampler.node[1:]
    L, D = sampler.th[:-1], sampler.dm
    ts = 0.5 * (GL8_X + 1.0)
    ws = 0.5 * GL8_W
    th = L[:, None] + D[:, None] * ts[None, :]
    pdf = a[:, None] + (b - a)[:, None] * ts[None, :]
    lab, _ = theta_lab_of_theta_cm(th)
    per_interval = np.sum(pdf * lab * ws[None, :], axis=1) * D
    return math.degrees(float(per_interval.sum() / sampler.Z))


def roundtrip_check() -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    from ccb_mc_validation.truth.weight_adapter import _reconstruct_cm_theta
    th_cm = np.radians(np.linspace(26.49, 169.78, 1001))
    th_lab, ekin_lab = theta_lab_of_theta_cm(th_cm)
    p = np.sqrt(ekin_lab**2 + 2.0 * ekin_lab * MP)
    px = np.zeros_like(p)
    py = p * np.sin(th_lab)
    pz = p * np.cos(th_lab)
    rt_cm, rt_lab = _reconstruct_cm_theta(ekin_lab, px, py, pz, offset=0.0)
    d_cm = float(np.max(np.abs(rt_cm - np.degrees(th_cm))))
    d_lab = float(np.max(np.abs(rt_lab - np.degrees(th_lab))))
    return {"n_points": 1001, "max_abs_dtheta_cm_deg": d_cm,
            "max_abs_dtheta_lab_deg": d_lab}


# Monte-Carlo tolerance for sampled CDF sup-differences at N draws:
# 5 sigma of the binomial count noise at the largest excursion p ~ 0.015.
MC_TOL = 5.0 * math.sqrt(0.015 * 0.985 / N_SAMPLE)  # ~2.7e-4


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    src = json.loads(SOURCE_JSON.read_text())
    v1 = json.loads(V1_JSON.read_text())

    ang, sig, stat = read_table()
    tbl_sha = sha256(TABLE)
    if tbl_sha != src["data_sha256"]:
        raise SystemExit(f"table sha drift: {tbl_sha}")

    # ---- sampler known-answer gates ------------------------------------
    nom = Sampler(ang, sig)

    repo_inv = load_repo_inverse()
    worst_t = 0.0
    for i in range(len(ang) - 1):
        a, b = nom.node[i], nom.node[i + 1]
        for fr in (0.0, 1e-4, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0):
            s = max(a, b)
            a_s, b_s = a / s, b / s
            disc = max(a_s * a_s + (b_s * b_s - a_s * a_s) * fr, 0.0)
            den = a_s + math.sqrt(disc)
            t_mine = fr * (a_s + b_s) / den if den > 0 else math.sqrt(fr)
            worst_t = max(worst_t, abs(t_mine - float(repo_inv(a, b, fr))))
    worst_t = float(worst_t)
    u_probe = np.linspace(0.0, 1.0, 200_001)
    rt_err = float(np.max(np.abs(nom.cdf(nom.invert(u_probe)) - u_probe)))

    # ---- analytic envelope reproduction vs v1 --------------------------
    grid = np.linspace(ang[0], ang[-1], 10001)
    grid_rad = np.radians(grid)
    cdf_nom = nom.cdf(grid_rad)
    up = Sampler(ang, sig * np.where(ang <= SPLIT_DEG, 1 + BOX, 1 - BOX))
    dn = Sampler(ang, sig * np.where(ang <= SPLIT_DEG, 1 - BOX, 1 + BOX))
    exc_up = float(np.max(up.cdf(grid_rad) - cdf_nom))
    exc_dn = float(np.min(dn.cdf(grid_rad) - cdf_nom))
    box1 = v1["deterministic_sensitivity"]["nodewise_relative_box_3pct_sensitivity_v1"]
    rep_err = max(abs(exc_up - box1["max_cdf_upward_excursion"]),
                  abs(-exc_dn - box1["max_cdf_downward_excursion"]))

    # ---- nuisance configurations, common random numbers ----------------
    cfgs = {
        "nominal": sig,
        "common_scale_1p045": sig * COMMON_SCALE,
        "corner_up_split46p95": sig * np.where(ang <= SPLIT_DEG, 1 + BOX, 1 - BOX),
        "corner_down_split46p95": sig * np.where(ang <= SPLIT_DEG, 1 - BOX, 1 + BOX),
        "alternating_pm": sig * np.where(np.arange(len(ang)) % 2 == 0,
                                         1 + BOX, 1 - BOX),
        "alternating_mp": sig * np.where(np.arange(len(ang)) % 2 == 0,
                                         1 - BOX, 1 + BOX),
    }
    rng = np.random.default_rng(SEED)
    u = rng.random(N_SAMPLE)
    samples = {k: np.degrees(Sampler(ang, v).invert(u)) for k, v in cfgs.items()}
    theta_nom = samples["nominal"]

    # (c) zero-uncertainty determinism: same law, same seed, bit-identical
    rerun = np.degrees(Sampler(ang, sig).invert(
        np.random.default_rng(SEED).random(N_SAMPLE)))
    ctrl_c = bool(np.array_equal(rerun, theta_nom))

    # (a) common multiplicative scale: shape invariant
    d_scale = np.abs(samples["common_scale_1p045"] - theta_nom)
    ctrl_a = {"max_abs_dtheta_deg": float(d_scale.max()),
              "n_identical": int((d_scale == 0).sum())}

    # per-config CDF excursion vs nominal (paired common-u: exact)
    grid_s = np.linspace(ang[0], ang[-1], 2001)
    ecdf_exc = {}
    for k in ("corner_up_split46p95", "corner_down_split46p95",
              "alternating_pm", "alternating_mp"):
        x = samples[k]
        lo_i = np.searchsorted(np.sort(x), grid_s)
        hi_i = np.searchsorted(np.sort(theta_nom), grid_s)
        ecdf_exc[k] = {
            "max_up": float(np.max((lo_i - hi_i) / N_SAMPLE)),
            "max_down": float(np.min((lo_i - hi_i) / N_SAMPLE)),
        }

    env_up = box1["max_cdf_upward_excursion"]
    env_dn = box1["max_cdf_downward_excursion"]
    ctrl_d = {k: (e["max_up"] <= env_up + MC_TOL and e["max_down"] >= -env_dn - MC_TOL)
              for k, e in ecdf_exc.items()}

    # (b) alternating does not cancel: sampled excursion must be orders of
    # magnitude above the common-scale artifact, and consistent with the v1
    # analytic alternating magnitude within MC_TOL.
    alt_an = v1["deterministic_sensitivity"]["alternating_3pct_controls"]
    alt_max = max(abs(ecdf_exc["alternating_pm"]["max_up"]),
                  abs(ecdf_exc["alternating_pm"]["max_down"]))
    alt_v1 = max(alt_an["plus_minus_max_abs_cdf_delta"],
                 alt_an["minus_plus_max_abs_cdf_delta"])
    ctrl_b = {"sampled_max_abs_alternating_excursion": alt_max,
              "v1_analytic_alternating": alt_v1,
              "abs_diff_vs_v1": abs(alt_max - alt_v1),
              "exceeds_common_scale_artifact_x10": bool(
                  alt_max > 10.0 * ctrl_a["max_abs_dtheta_deg"] + 1e-4
                  and alt_max > 1e-4 and abs(alt_max - alt_v1) <= MC_TOL)}

    # ---- quantile bands --------------------------------------------------
    qs = QUANTILES
    q_nom = np.quantile(theta_nom, qs)
    q_up = np.quantile(samples["corner_up_split46p95"], qs)
    q_dn = np.quantile(samples["corner_down_split46p95"], qs)
    q_alt = np.quantile(samples["alternating_pm"], qs)
    mean_nom = float(theta_nom.mean())
    v1_mean = v1["nominal_source_model"]["mean_theta_cm_deg"]

    # ---- lab-frame mapping ------------------------------------------------
    rt = roundtrip_check()
    lab_nom = np.degrees(theta_lab_of_theta_cm(np.radians(q_nom))[0])
    lab_up = np.degrees(theta_lab_of_theta_cm(np.radians(q_up))[0])
    lab_dn = np.degrees(theta_lab_of_theta_cm(np.radians(q_dn))[0])
    # Mean of the mapped distribution under each law (NOT the point map of the
    # mean: mean-of-map != map-of-mean for this skewed distribution — the
    # point-mapped corner means would land ~2 deg below the distribution mean
    # and would not bracket the nominal).
    mean_lab = mean_lab_deg(nom)
    mean_lab_corners = sorted((mean_lab_deg(up), mean_lab_deg(dn)))

    # ---- row-statistical replicas vs delta method -------------------------
    # Analytic per-replica means (exact propagation of the iid row nuisance,
    # zero Monte-Carlo noise). A finite-M sampled design was rejected in
    # diagnosis: with sigma_theta ~ 33.8 deg, replica means at M = 200k carry
    # MC noise 0.0756 deg, which swamps the 0.0225 deg nuisance signal
    # (measured 0.07846 vs quadrature prediction 0.07884, i.e. the v1 delta
    # method is CONSISTENT with sampling once MC noise is accounted).
    dmu = v1["conditional_diagonal_statistical_reference"][
        "mean_theta_cm_standard_uncertainty_deg"]
    mean_exact, sd_theta = nom.mean_var_cm_deg()
    means_cm, means_lab = [], []
    for r in range(N_REPLICAS):
        rr = np.random.default_rng(SEED + 10_000 + r)
        eps = rr.standard_normal(len(sig)) * (stat / sig)
        s = Sampler(ang, sig * (1.0 + eps))
        means_cm.append(s.mean_var_cm_deg()[0])
        means_lab.append(mean_lab_deg(s))
    sd_cm = float(np.std(means_cm, ddof=1))
    sd_lab = float(np.std(means_lab, ddof=1))
    mc_noise_m200k = sd_theta / math.sqrt(M_REPLICA)

    # ---- gates (fail-closed) ----------------------------------------------
    gates = pyfy({
        "sampler_matches_repo_inverse": worst_t <= 1e-14,
        "u_cdf_roundtrip_eps": rt_err <= 1e-9,
        "v1_envelope_reproduced": rep_err <= 1e-12,
        "ctrl_a_common_scale_invariant": ctrl_a["max_abs_dtheta_deg"] <= 1e-6,
        "ctrl_b_alternating_moves_shape": ctrl_b["exceeds_common_scale_artifact_x10"],
        "ctrl_c_zero_uncertainty_bit_identical": ctrl_c,
        "ctrl_d_box_within_envelope": all(ctrl_d.values()),
        "mean_matches_v1_exact": abs(mean_exact - v1_mean) <= 1e-9,
        "sampled_mean_within_mc_noise": abs(mean_nom - v1_mean)
                                        <= 5.0 * sd_theta / math.sqrt(N_SAMPLE),
        "replica_sd_matches_delta_method": 0.85 <= sd_cm / dmu <= 1.15,
        "lab_envelope_brackets_nominal": (mean_lab_corners[0] <= mean_lab
                                          <= mean_lab_corners[1]),
        "kinematics_roundtrip": rt["max_abs_dtheta_cm_deg"] <= 1e-6,
    })
    verdict = "PASS" if all(gates.values()) else "FAIL"

    result = {
        "schema_version": "ccb_sigma_cm_source_uncertainty_v2_study",
        "ticket": TICKET,
        "issue": 1179,
        "verdict": verdict,
        "gates": gates,
        "input": {"table_sha256": tbl_sha, "rows": 28,
                  "v1_sha256": sha256(V1_JSON),
                  "source_doi": src["source"]["doi"],
                  "support_theta_cm_deg": [float(ang[0]), float(ang[-1])]},
        "sampler_validation": {
            "repo_inverse_max_abs_t_diff": worst_t,
            "u_to_theta_to_cdf_max_abs_err": rt_err,
            "n_roundtrip_points": len(u_probe),
        },
        "envelope_reproduction_vs_v1": {
            "max_cdf_upward_excursion": exc_up,
            "max_cdf_downward_excursion": -exc_dn,
            "max_abs_difference_vs_v1": rep_err,
        },
        "sampling": {
            "n_sample": N_SAMPLE, "seed": SEED,
            "common_random_numbers": True,
            "nominal_mean_theta_cm_deg": mean_nom,
            "exact_mean_theta_cm_deg": mean_exact,
            "population_sd_theta_cm_deg": sd_theta,
            "v1_nominal_mean_theta_cm_deg": v1_mean,
            "configs": {
                k: {
                    "max_abs_dtheta_vs_nominal_deg":
                        float(np.abs(samples[k] - theta_nom).max()),
                    "max_up_cdf_excursion": ecdf_exc.get(k, {}).get("max_up"),
                    "max_down_cdf_excursion": ecdf_exc.get(k, {}).get("max_down"),
                    "within_envelope": ctrl_d.get(k),
                } for k in samples
            },
        },
        "negative_controls": {
            "a_common_scale_shape_invariant": ctrl_a,
            "b_alternating_moves_shape": ctrl_b,
            "c_zero_uncertainty_bit_identical": ctrl_c,
            "d_box_configs_within_envelope": ctrl_d,
        },
        "row_statistical_replicas": {
            "n_replicas": N_REPLICAS,
            "mode": "analytic_exact_means",
            "seed_offset": 10_000,
            "mean_theta_cm_sd_deg": sd_cm,
            "v1_delta_method_mean_theta_cm_sd_deg": dmu,
            "sd_ratio_replica_over_delta": sd_cm / dmu,
            "mean_theta_lab_sd_deg": sd_lab,
            "population_sd_theta_cm_deg": sd_theta,
            "finite_m_diagnosis": {
                "m_per_replica_rejected_design": M_REPLICA,
                "mc_noise_of_replica_mean_deg": mc_noise_m200k,
                "quadrature_prediction_deg": math.sqrt(dmu**2 + mc_noise_m200k**2),
                "note": ("sampled replica design rejected: MC noise dominates; "
                         "v1 delta method consistent with sampling once "
                         "accounted in quadrature"),
            },
        },
        "lab_frame_bands": {
            "kinematics_roundtrip": rt,
            "nominal_mean_theta_lab_deg": mean_lab,
            "nominal_mean_theta_lab_deg": mean_lab,
            "mean_theta_lab_envelope_deg": mean_lab_corners,
            "quantile_curves": {
                "quantiles": qs.tolist(),
                "theta_cm_deg": {"nominal": q_nom.tolist(),
                                 "corner_up": q_up.tolist(),
                                 "corner_down": q_dn.tolist(),
                                 "alternating_pm": q_alt.tolist()},
                "theta_lab_deg": {"nominal": lab_nom.tolist(),
                                  "corner_up": lab_up.tolist(),
                                  "corner_down": lab_dn.tolist()},
            },
        },
        "absolute_yield_rule": (
            "A fully common multiplicative normalization cancels from the "
            "normalized angular shape only. Any absolute-yield/rate estimand "
            "must restore the common normalization mode (bounded by the "
            "published total systematic <4.5% at 190 MeV); no such claim is "
            "made or authorized here."),
        "scientific_boundary": (
            "Source-level deterministic/conditional uncertainty research "
            "only. The 3% node box is a sensitivity envelope, not a "
            "confidence region or an inferred covariance. No detector "
            "response, production Geant4 sample, or detector-performance "
            "claim is validated."),
    }
    result = pyfy(result)
    (OUT / "result.json").write_text(json.dumps(result, indent=1))

    # ---- v2 machine-readable summary (paper-facing) ------------------------
    v2 = {
        "schema_version": "ccb_sigma_cm_source_uncertainty_v2",
        "supersedes": None,
        "extends": "sigma_cm_source_uncertainty_v1.json",
        "input": result["input"],
        "sampled_validation": {
            "n_sample": N_SAMPLE, "seed": SEED,
            "common_random_numbers": True,
            "sampler_law": "linear_node_pdf_exact_inverse_v1 + "
                           "measured_table_support_truncate_v1",
            "repo_inverse_max_abs_t_diff": worst_t,
            "u_cdf_roundtrip_max_abs_err": rt_err,
            "envelope_reproduced_vs_v1_max_abs_diff": rep_err,
        },
        "theta_cm_deg": {
            "nominal_mean": mean_nom,
            "envelope_mean": [box1["min_mean_theta_cm_deg"],
                              box1["max_mean_theta_cm_deg"]],
            "envelope_cdf_excursion": [-env_dn, env_up],
        },
        "theta_lab_deg": {
            "nominal_mean": mean_lab,
            "envelope_mean": result["lab_frame_bands"]["mean_theta_lab_envelope_deg"],
            "row_statistical_mean_sd": sd_lab,
            "quantiles": qs.tolist(),
            "nominal_quantiles": lab_nom.tolist(),
            "corner_up_quantiles": lab_up.tolist(),
            "corner_down_quantiles": lab_dn.tolist(),
        },
        "negative_controls_all_pass": all(gates[k] for k in gates
                                          if k.startswith("ctrl_")),
        "absolute_yield_rule": result["absolute_yield_rule"],
        "scientific_boundary": result["scientific_boundary"],
        "study_ticket": TICKET,
        "study_report": f"reports/{STUDY}/REPORT.md",
    }
    V2_JSON.write_text(json.dumps(pyfy(v2), indent=1) + "\n")

    manifest = {
        "study": STUDY, "ticket": TICKET, "issue": 1179,
        "git_head": git_head(),
        "table_sha256": tbl_sha, "v1_sha256": sha256(V1_JSON),
        "result_sha256": sha256(OUT / "result.json"),
        "v2_sha256": sha256(V2_JSON),
        "config": {"seed": SEED, "n_sample": N_SAMPLE,
                   "n_replicas": N_REPLICAS, "m_replica": M_REPLICA,
                   "box": BOX, "common_scale": COMMON_SCALE,
                   "split_deg": SPLIT_DEG},
        "wall_s": round(time.time() - t0, 1),
        "verdict": verdict,
    }
    (OUT / "manifest.json").write_text(json.dumps(pyfy(manifest), indent=1))

    print(json.dumps({"verdict": verdict, "gates": gates,
                      "sd_ratio": round(sd_cm / dmu, 3),
                      "mean_lab": round(mean_lab, 4),
                      "wall_s": manifest["wall_s"]}, indent=1))
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
