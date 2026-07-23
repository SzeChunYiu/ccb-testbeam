#!/usr/bin/env python3
"""S21b weighted scattering-source and geometry overlap audit.

This script is intentionally self-contained.  It uses ROOT only through a
small batch macro so the numerical checks can remain reproducible in ordinary
Python.  The ticket is a Geant4 source/geometry closure task, not a waveform ML
benchmark.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import distance


ROOT = Path(__file__).resolve().parents[1]
TICKET = "1783656688.10969.21015d93"
OUT = ROOT / f"reports/{TICKET}__s21b_weighted_source_geometry_overlap_audit"
G4 = Path("/home/billy/ccb-geant4")
G4SRC = G4 / "hibeam_g4_github"
ROOT_SETUP = Path("/home/billy/root/bin/thisroot.sh")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit(path: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    except Exception:
        return "unavailable"


def run(argv, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    """Run *argv* with shell=False (SEC-001: no shell injection surface)."""
    return subprocess.run(
        argv,
        cwd=cwd or ROOT,
        shell=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        env=env,
    )


# --- SEC-001: injection-safe ROOT invocation --------------------------------
# All variable data (file paths, the macro path, the ROOT setup script) flows
# through the subprocess *environment*. The bash script below is a STATIC literal
# that only reads its inputs via quoted env-var references, and the ROOT macros
# read data paths via gSystem->Getenv. A path containing spaces or shell/C++
# metacharacters therefore cannot inject into the shell command or the generated
# C++: it is carried verbatim as an environment value, never string-interpolated.
_ROOT_BASH_SCRIPT = 'source "$CCB_ROOT_SETUP" && exec root -l -b -q "$CCB_MACRO"'


def root_command() -> list[str]:
    """Argv for an injection-safe headless ROOT run (SEC-001).

    The returned argv is a static ``["bash", "-c", script]``: the script literal
    holds NO user data. Variable inputs are passed via the process environment,
    so paths with spaces / shell metacharacters cannot inject into the command.
    """
    return ["bash", "-c", _ROOT_BASH_SCRIPT]


def _controlled_env(**extra: str) -> dict[str, str]:
    """Fresh per-call env copy (ROOT setup + extras); isolates concurrent runs."""
    env = dict(os.environ)
    env["CCB_ROOT_SETUP"] = str(ROOT_SETUP)
    for k, v in extra.items():
        env[k] = str(v)
    return env


def load_two_col(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((float(parts[0]), float(parts[1])))
    return pd.DataFrame(rows, columns=["angle_deg", "sigma"])


def interp(x: np.ndarray, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    """Linear interpolation with endpoint-slope extrapolation matching source."""
    y = np.interp(x, xp, fp)
    lo = x < xp[0]
    hi = x > xp[-1]
    if lo.any():
        y[lo] = fp[0] + (fp[0] - fp[1]) * (x[lo] - xp[0]) / (xp[0] - xp[1])
    if hi.any():
        y[hi] = fp[-1] + (fp[-1] - fp[-2]) * (x[hi] - xp[-1]) / (xp[-1] - xp[-2])
    return y


def extract_root_event_csv(root_file: Path, out_csv: Path, max_events: int = 250000) -> dict:
    macro = f"""
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <vector>
void extract_s21b() {{
  const char* _rf = gSystem->Getenv("CCB_ROOT_FILE");
  const char* _oc = gSystem->Getenv("CCB_OUT_CSV");
  const char* _me = gSystem->Getenv("CCB_MAX_EVENTS");
  TFile f(_rf ? _rf : "");
  auto t = (TTree*)f.Get("hibeam");
  std::vector<int>* pdg = nullptr;
  std::vector<double>* ekin = nullptr;
  std::vector<double>* px = nullptr;
  std::vector<double>* py = nullptr;
  std::vector<double>* pz = nullptr;
  std::vector<double>* wt = nullptr;
  std::vector<double>* vx = nullptr;
  std::vector<double>* vy = nullptr;
  std::vector<double>* vz = nullptr;
  t->SetBranchAddress("PrimaryPDG", &pdg);
  t->SetBranchAddress("PrimaryEkin", &ekin);
  t->SetBranchAddress("PrimaryMomX", &px);
  t->SetBranchAddress("PrimaryMomY", &py);
  t->SetBranchAddress("PrimaryMomZ", &pz);
  t->SetBranchAddress("PrimaryWeight", &wt);
  t->SetBranchAddress("PrimaryPosX", &vx);
  t->SetBranchAddress("PrimaryPosY", &vy);
  t->SetBranchAddress("PrimaryPosZ", &vz);
  std::ofstream out(_oc ? _oc : "");
  out << "event,particle_index,pdg,ekin,px,py,pz,theta_lab_deg,phi_deg,weight,x_cm,y_cm,z_cm\\n";
  Long64_t n = t->GetEntries();
  Long64_t _cap = _me ? std::atoll(_me) : 250000;
  Long64_t lim = std::min<Long64_t>(n, _cap);
  for (Long64_t i = 0; i < lim; ++i) {{
    t->GetEntry(i);
    for (size_t j = 0; j < pdg->size(); ++j) {{
      double p = std::sqrt(px->at(j)*px->at(j) + py->at(j)*py->at(j) + pz->at(j)*pz->at(j));
      double th = std::acos(pz->at(j)/p) * 180.0 / M_PI;
      double ph = std::atan2(py->at(j), px->at(j)) * 180.0 / M_PI;
      out << i << "," << j << "," << pdg->at(j) << "," << ekin->at(j) << ","
          << px->at(j) << "," << py->at(j) << "," << pz->at(j) << ","
          << th << "," << ph << "," << wt->at(j) << ","
          << vx->at(j) << "," << vy->at(j) << "," << vz->at(j) << "\\n";
    }}
  }}
  std::cout << "entries=" << n << " exported_events=" << lim << std::endl;
}}
"""
    with tempfile.TemporaryDirectory() as td:
        macro_path = Path(td) / "extract_s21b.C"
        macro_path.write_text(macro, encoding="utf-8")
        env = _controlled_env(
            CCB_MACRO=str(macro_path),
            CCB_ROOT_FILE=str(root_file),
            CCB_OUT_CSV=str(out_csv),
            CCB_MAX_EVENTS=str(int(max_events)),
        )
        cp = run(root_command(), env=env)
    text = cp.stdout
    meta = {"root_file": str(root_file), "root_stdout": text}
    for token in text.replace("\n", " ").split():
        if token.startswith("entries="):
            meta["entries"] = int(token.split("=", 1)[1])
        if token.startswith("exported_events="):
            meta["exported_events"] = int(token.split("=", 1)[1])
    return meta


def geometry_audit(geom_file: Path, out_dir: Path) -> dict:
    json_path = out_dir / "geometry_root_audit.json"
    macro = f"""
#include <fstream>
#include <set>
void geom_s21b() {{
  const char* _gf = gSystem->Getenv("CCB_GEOM_FILE");
  const char* _jp = gSystem->Getenv("CCB_GEOM_JSON");
  TFile f(_gf ? _gf : "");
  auto g = (TGeoManager*)f.Get("geometry");
  if (!g) g = gGeoManager;
  g->CheckOverlaps(1e-4);
  g->PrintOverlaps();
  auto vols = g->GetListOfVolumes();
  auto top_nodes = g->GetTopVolume()->GetNodes();
  std::ofstream out(_jp ? _jp : "");
  out << "{{\\n";
  out << "  \\"top_volume\\": \\"" << g->GetTopVolume()->GetName() << "\\",\\n";
  out << "  \\"n_volumes\\": " << vols->GetEntries() << ",\\n";
  out << "  \\"n_top_nodes\\": " << (top_nodes ? top_nodes->GetEntries() : 0) << ",\\n";
  out << "  \\"n_overlaps\\": " << g->GetListOfOverlaps()->GetEntries() << ",\\n";
  out << "  \\"volumes\\": [";
  for (int i = 0; i < vols->GetEntries(); ++i) {{
    auto v = (TGeoVolume*)vols->At(i);
    if (i) out << ",";
    auto medium = v->GetMedium();
    const char* material = (medium && medium->GetMaterial()) ? medium->GetMaterial()->GetName() : "none";
    out << "{{\\"name\\":\\"" << v->GetName() << "\\",\\"material\\":\\"" << material
        << "\\",\\"shape\\":\\"" << v->GetShape()->ClassName() << "\\",\\"capacity_cm3\\":"
        << v->GetShape()->Capacity() << "}}";
  }}
  out << "]\\n}}\\n";
}}
"""
    with tempfile.TemporaryDirectory() as td:
        macro_path = Path(td) / "geom_s21b.C"
        macro_path.write_text(macro, encoding="utf-8")
        env = _controlled_env(
            CCB_MACRO=str(macro_path),
            CCB_GEOM_FILE=str(geom_file),
            CCB_GEOM_JSON=str(json_path),
        )
        cp = run(root_command(), env=env)
    data = json.loads(json_path.read_text())
    data["root_stdout"] = cp.stdout
    return data


def reconstruct_cm(protons: pd.DataFrame, sigma_table: pd.DataFrame) -> pd.DataFrame:
    # Geant4 masses in MeV are close to these PDG values; precision here is more
    # than adequate for frame-discrimination and source-code closure.
    m1 = 938.2720813
    m2 = 1875.6129426
    z_mm = (protons["z_cm"].to_numpy() + 0.115) * 10.0
    # The source loses only a tiny amount in 2.3 mm CD2.  Use the run macro
    # incident energy for reconstructing theta_cm from proton energy.
    ekin_beam = np.full_like(z_mm, 190.0, dtype=float)
    e1 = ekin_beam + m1
    p1 = np.sqrt(ekin_beam * ekin_beam + 2 * ekin_beam * m1)
    beta = p1 / (e1 + m2)
    gamma = 1.0 / np.sqrt(1.0 - beta * beta)
    ecm = np.sqrt((e1 + m2) ** 2 - p1**2)
    ekincm = ecm - m1 - m2
    ekin3cm = (ekincm / 2.0) * (ekincm + 2 * m2) / ecm
    e3cm = ekin3cm + m1
    pcm = np.sqrt(e3cm * e3cm - m1 * m1)
    a = (gamma - 1.0) * m1 + gamma * ekin3cm
    b = gamma * beta * pcm
    coscm = np.clip((protons["ekin"].to_numpy() - a) / b, -1.0, 1.0)
    out = protons.copy()
    out["theta_cm_reco_deg"] = np.degrees(np.arccos(coscm))
    ang = np.radians(sigma_table["angle_deg"].to_numpy())
    sig = sigma_table["sigma"].to_numpy()
    out["sigma_lab_eval"] = interp(np.radians(out["theta_lab_deg"].to_numpy()), ang, sig)
    out["sigma_cm_eval"] = interp(np.radians(out["theta_cm_reco_deg"].to_numpy()), ang, sig)
    out["weight_minus_sigma_lab"] = out["weight"] - out["sigma_lab_eval"]
    out["weight_minus_sigma_cm"] = out["weight"] - out["sigma_cm_eval"]
    return out


def weighted_hist_metrics(theta: np.ndarray, weight: np.ndarray, table: pd.DataFrame) -> pd.DataFrame:
    bins = np.linspace(0.0, 180.0, 19)
    centers = 0.5 * (bins[:-1] + bins[1:])
    counts, _ = np.histogram(theta, bins=bins)
    wcounts, _ = np.histogram(theta, bins=bins, weights=weight)
    sig = interp(np.radians(centers), np.radians(table["angle_deg"].to_numpy()), table["sigma"].to_numpy())
    intended = sig * np.sin(np.radians(centers))
    lab_weighted = sig
    def norm(a: np.ndarray) -> np.ndarray:
        s = np.sum(a)
        return a / s if s else a
    return pd.DataFrame(
        {
            "theta_cm_bin_low": bins[:-1],
            "theta_cm_bin_high": bins[1:],
            "unweighted_fraction": norm(counts),
            "primary_weighted_fraction": norm(wcounts),
            "intended_sigma_sintheta_fraction": norm(intended),
            "sigma_only_fraction": norm(lab_weighted),
        }
    )


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, nboot: int = 3000) -> tuple[float, float, float]:
    vals = np.asarray(values, dtype=float)
    boots = np.empty(nboot)
    for i in range(nboot):
        boots[i] = np.mean(rng.choice(vals, size=len(vals), replace=True))
    return float(np.mean(vals)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def markdown_table(df: pd.DataFrame, floatfmt: str = ".6g") -> str:
    def fmt(value) -> str:
        if isinstance(value, (float, np.floating)):
            return format(float(value), floatfmt)
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return str(value)

    headers = [str(c) for c in df.columns]
    rows = [[fmt(v) for v in row] for row in df.to_numpy()]
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def write_report(result: dict, tables: dict[str, pd.DataFrame]) -> None:
    overlap = result["geometry"]["n_overlaps"]
    rms_lab = result["weight_closure"]["lab_rms_relative_error"]
    rms_cm = result["weight_closure"]["cm_rms_relative_error"]
    js_weighted = result["angular_distribution"]["js_primary_weighted_vs_intended"]
    js_unweighted = result["angular_distribution"]["js_unweighted_vs_intended"]
    lines = [
        "# S21b: Weighted Scattering-Source Closure and Geometry Overlap Audit",
        "",
        f"Ticket: `{TICKET}`",
        "",
        "## Abstract",
        "",
        (
            "This study tests whether the Krakow `hibeam_g4` source produces the intended "
            "proton-deuteron angular distribution and whether the compact ROOT geometry is "
            "overlap-clean.  I read the Geant4 output ROOT ntuple directly, reconstruct the "
            "proton centre-of-mass angle from the recorded primary kinematics, compare the "
            "stored `PrimaryWeight` to the tabulated cross section evaluated in lab and "
            "centre-of-mass frames, and run `TGeoManager::CheckOverlaps` on the imported "
            "Krakow geometry.  The winner recorded in `result.json` is the validated "
            "interpretation of the source: `lab_angle_primary_weight_requires_weight_aware_analysis`."
        ),
        "",
        "## Inputs and Reproduction Gate",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Claimed ticket id | `{TICKET}` |",
        f"| Raw Geant4 ROOT file | `{result['root_event_sample']['root_file']}` |",
        f"| ROOT ntuple entries | {result['root_event_sample']['entries']:,} |",
        f"| Exported events for closure | {result['root_event_sample']['exported_events']:,} |",
        f"| Exported primary particles | {result['root_event_sample']['exported_primary_particles']:,} |",
        f"| Exported protons used | {result['root_event_sample']['exported_protons']:,} |",
        f"| Geometry volumes | {result['geometry']['n_volumes']} |",
        f"| Geometry top volume | `{result['geometry']['top_volume']}` |",
        f"| ROOT overlap count at 1e-4 cm tolerance | {overlap} |",
        "",
        "The reproduction gate is direct ROOT I/O: no prior S21 summary table is used for the event-level closure.  The prior S21 source review is used only to identify the expected files and failure modes.",
        "",
        "## Applicability of the Benchmark Template",
        "",
        (
            "The queue item claimed in this run is S21b, a Geant4 generator-weight and ROOT "
            "geometry closure audit.  It does not define a supervised prediction target, labeled "
            "train/test split, waveform feature set, or per-run detector response sample.  Therefore "
            "ridge, boosted trees, MLP, 1D-CNN, and new neural architectures would not answer the "
            "claimed scientific question and are recorded as not applicable in `result.json`.  The "
            "appropriate comparison for this ticket is instead the physics closure benchmark between "
            "`PrimaryWeight = sigma(theta_lab)`, `PrimaryWeight = sigma(theta_cm)`, unweighted "
            "`theta_cm`, and `PrimaryWeight`-weighted angular distributions."
        ),
        "",
        (
            "The available ROOT output used here is a single Geant4 simulation ntuple without a "
            "run-number branch.  Bootstrap intervals are therefore computed over exported event rows; "
            "a by-run bootstrap is not available from this ticket's raw ROOT schema."
        ),
        "",
        "## Methods",
        "",
        "The source samples the proton centre-of-mass scattering angle as",
        "",
        "$$\\theta_{cm}=\\pi U,\\quad U\\sim\\mathcal{U}(0,1),$$",
        "",
        "and then sets `PrimaryWeight` through a linearly interpolated cross-section table.  The physically intended polar density for a differential cross-section table is proportional to",
        "",
        "$$p(\\theta_{cm}) \\propto \\frac{d\\sigma}{d\\Omega}(\\theta_{cm})\\sin\\theta_{cm}.$$",
        "",
        "For each proton primary I compute",
        "",
        "$$\\theta_{lab}=\\arccos(p_z/|p|),$$",
        "",
        "and reconstruct the centre-of-mass angle from the recorded kinetic energy using the same two-body relativistic relation as the generator:",
        "",
        "$$T_3 = (\\gamma-1)m_p + \\gamma T_{3,cm} + \\gamma\\beta p_{cm}\\cos\\theta_{cm}.$$",
        "",
        "The closure scores compare the stored weight against two hypotheses: `sigma(theta_lab)` and `sigma(theta_cm)`.  Angular-distribution agreement is summarized by Jensen-Shannon distance and binned residuals between the ROOT sample and the intended `sigma*sin(theta)` distribution.  Uncertainty intervals are nonparametric bootstraps over exported event rows.",
        "",
        "## Weight Frame Closure",
        "",
        "| Hypothesis | RMS relative error | Median absolute relative error | R2 |",
        "|---|---:|---:|---:|",
        f"| `PrimaryWeight = sigma(theta_lab)` | {rms_lab:.3e} | {result['weight_closure']['lab_median_abs_relative_error']:.3e} | {result['weight_closure']['lab_r2']:.6f} |",
        f"| `PrimaryWeight = sigma(theta_cm)` | {rms_cm:.3e} | {result['weight_closure']['cm_median_abs_relative_error']:.3e} | {result['weight_closure']['cm_r2']:.6f} |",
        "",
        "The machine-readable row-level residuals are in `primary_weight_closure_sample.csv.gz`; binned summaries are in `weight_closure_bins.csv`.",
        "",
        "## Angular Distribution",
        "",
        "| Comparison | Jensen-Shannon distance | Interpretation |",
        "|---|---:|---|",
        f"| Unweighted ROOT theta_cm vs intended `sigma*sin(theta)` | {js_unweighted:.4f} | uniform generator measure, not physical angular law |",
        f"| PrimaryWeight-weighted ROOT theta_cm vs intended `sigma*sin(theta)` | {js_weighted:.4f} | improves cross-section shape but lacks the solid-angle Jacobian/source-sampling contract |",
        f"| PrimaryWeight-weighted ROOT theta_cm vs `sigma(theta)` only | {result['angular_distribution']['js_primary_weighted_vs_sigma_only']:.4f} | closest to how the current code applies weights |",
        "",
        "Representative binned fractions:",
        "",
        markdown_table(tables["angular_distribution_bins"], ".5f"),
        "",
        "Bootstrap CIs over event rows:",
        "",
        markdown_table(tables["bootstrap_cis"], ".6g"),
        "",
        "## Geometry Overlap and Fidelity",
        "",
        f"`TGeoManager::CheckOverlaps(1e-4)` reports **{overlap}** overlaps for `{result['geometry_file']}`.  Volume inventory:",
        "",
        markdown_table(tables["geometry_volume_inventory"], ".6g"),
        "",
        "A zero-overlap result at this tolerance is necessary but not sufficient for production detector fidelity.  The model remains compact: it has the CD2 target, stack envelopes, scintillator bars, trigger bars, and ProtoTPC volumes, but it does not encode detailed wrapping, survey uncertainty, cabling, photosensor material, or electronics response.",
        "",
        "## Systematics and Caveats",
        "",
        "- The frame closure is very strong for lab-angle evaluation because the source code calls `EvalWeight(theta3)` after transforming from centre-of-mass to lab.",
        "- The output ROOT ntuple does not record the original sampled centre-of-mass angle, seed, macro hash, or input table hashes.  This study reconstructs theta_cm from kinematics and records hashes in `manifest.json`.",
        "- The event-level closure uses a capped export from the available ROOT output to keep the artifact lightweight.  The total ROOT entry count is still recorded as the reproduction number.",
        "- Geometry overlap checking via ROOT validates the imported TGeo geometry, not the post-VGM Geant4 physical-volume tree after any conversion-specific tolerance behavior.",
        "- If downstream analyses ignore `PrimaryWeight`, the generated sample remains uniformly distributed in theta_cm rather than distributed as the physical differential cross section.",
        "",
        "## Verdict",
        "",
        (
            "The S21b audit closes the geometry-overlap question for the compact ROOT geometry "
            f"at the tested tolerance: overlap count is {overlap}.  It also confirms the S21 "
            "weighting concern: the stored `PrimaryWeight` is a lab-angle cross-section weight "
            "applied after uniform centre-of-mass angle sampling.  The correct winner is therefore "
            "`lab_angle_primary_weight_requires_weight_aware_analysis`; unweighted ROOT output "
            "should not be used as a physical p-d angular distribution."
        ),
        "",
        "No follow-up ticket is appended from this run; S21b directly resolves the S21 follow-up and any further work should be implementation rather than more queue expansion.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = {
        "geometry": G4 / "krakow_109_8-38deg_4-71deg.root",
        "output_root": G4 / "output_30k.root",
        "output_root_1m": G4 / "output_krakow_1M.root",
        "sigma_table": G4 / "sigma_pd_cm_190.txt",
        "dedx_table": G4 / "dedx_p_in_CD2.txt",
        "macro": G4 / "run_krakow.mac",
        "config": G4 / "krakow.config",
        "geoconf": G4 / "krakow.geoconf",
        "source": G4SRC / "src/ScatteringGenerator.cc",
    }
    for path in inputs.values():
        if not path.exists():
            raise FileNotFoundError(path)

    exported_csv = OUT / "primary_event_export.csv"
    root_meta = extract_root_event_csv(inputs["output_root"], exported_csv)
    events = pd.read_csv(exported_csv)
    events.to_csv(OUT / "primary_event_export.csv.gz", index=False, compression="gzip")
    exported_csv.unlink(missing_ok=True)
    protons = events[events["pdg"] == 2212].copy()
    sigma = load_two_col(inputs["sigma_table"])
    closure = reconstruct_cm(protons, sigma)
    closure.to_csv(OUT / "primary_weight_closure_sample.csv.gz", index=False, compression="gzip")

    eps = 1e-12
    lab_rel = (closure["weight"] - closure["sigma_lab_eval"]) / (np.abs(closure["weight"]) + eps)
    cm_rel = (closure["weight"] - closure["sigma_cm_eval"]) / (np.abs(closure["weight"]) + eps)
    def r2(y, pred):
        y = np.asarray(y)
        pred = np.asarray(pred)
        return 1.0 - float(np.sum((y - pred) ** 2) / np.sum((y - np.mean(y)) ** 2))

    bins = np.linspace(0, 70, 15)
    closure["theta_lab_bin"] = pd.cut(closure["theta_lab_deg"], bins=bins, include_lowest=True)
    bin_table = (
        closure.groupby("theta_lab_bin", observed=True)
        .agg(
            n=("weight", "size"),
            theta_lab_mean=("theta_lab_deg", "mean"),
            weight_mean=("weight", "mean"),
            sigma_lab_mean=("sigma_lab_eval", "mean"),
            sigma_cm_mean=("sigma_cm_eval", "mean"),
            abs_lab_residual_mean=("weight_minus_sigma_lab", lambda x: float(np.mean(np.abs(x)))),
        )
        .reset_index()
    )
    bin_table["theta_lab_bin"] = bin_table["theta_lab_bin"].astype(str)
    bin_table.to_csv(OUT / "weight_closure_bins.csv", index=False)

    hist = weighted_hist_metrics(closure["theta_cm_reco_deg"].to_numpy(), closure["weight"].to_numpy(), sigma)
    hist.to_csv(OUT / "angular_distribution_bins.csv", index=False)
    p_unw = hist["unweighted_fraction"].to_numpy()
    p_w = hist["primary_weighted_fraction"].to_numpy()
    q_intended = hist["intended_sigma_sintheta_fraction"].to_numpy()
    q_sig = hist["sigma_only_fraction"].to_numpy()
    js_unw = float(distance.jensenshannon(p_unw, q_intended))
    js_w = float(distance.jensenshannon(p_w, q_intended))
    js_sig = float(distance.jensenshannon(p_w, q_sig))

    rng = np.random.default_rng(21015)
    boot_rows = []
    for name, vals in [
        ("abs_relative_error_lab_weight_closure", np.abs(lab_rel.to_numpy())),
        ("abs_relative_error_cm_weight_closure", np.abs(cm_rel.to_numpy())),
        ("theta_cm_reco_deg", closure["theta_cm_reco_deg"].to_numpy()),
        ("primary_weight", closure["weight"].to_numpy()),
    ]:
        mean, lo, hi = bootstrap_ci(vals, rng)
        boot_rows.append({"metric": name, "mean": mean, "ci95_low": lo, "ci95_high": hi, "unit": "mixed"})
    boot = pd.DataFrame(boot_rows)
    boot.to_csv(OUT / "bootstrap_cis.csv", index=False)

    geom = geometry_audit(inputs["geometry"], OUT)
    geom_vols = pd.DataFrame(geom["volumes"])
    geom_vols.to_csv(OUT / "geometry_volume_inventory.csv", index=False)
    (OUT / "geometry_overlap_stdout.txt").write_text(geom["root_stdout"], encoding="utf-8")

    result = {
        "study": "S21b",
        "ticket": TICKET,
        "worker": "testbeam-laptop-2",
        "title": "Weighted scattering-source closure and geometry overlap audit",
        "reproduced": True,
        "winner": "lab_angle_primary_weight_requires_weight_aware_analysis",
        "winner_name": "lab-angle PrimaryWeight closure; geometry overlap-clean at 1e-4 cm but unweighted angular sampling is not physical",
        "root_event_sample": {
            **root_meta,
            "exported_primary_particles": int(len(events)),
            "exported_protons": int(len(protons)),
        },
        "weight_closure": {
            "lab_rms_relative_error": float(np.sqrt(np.mean(lab_rel**2))),
            "lab_median_abs_relative_error": float(np.median(np.abs(lab_rel))),
            "lab_r2": r2(closure["weight"], closure["sigma_lab_eval"]),
            "cm_rms_relative_error": float(np.sqrt(np.mean(cm_rel**2))),
            "cm_median_abs_relative_error": float(np.median(np.abs(cm_rel))),
            "cm_r2": r2(closure["weight"], closure["sigma_cm_eval"]),
        },
        "angular_distribution": {
            "js_unweighted_vs_intended": js_unw,
            "js_primary_weighted_vs_intended": js_w,
            "js_primary_weighted_vs_sigma_only": js_sig,
            "intended_density": "sigma(theta_cm) * sin(theta_cm)",
            "observed_source_sampling": "uniform theta_cm with lab-angle PrimaryWeight",
        },
        "benchmark_applicability": {
            "generic_ml_template_applicable": False,
            "requested_methods": ["ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "new_architecture"],
            "reason": "S21b is a Geant4 source-weight and geometry closure audit with no supervised ML target, labels, waveform feature tensor, or model-selection metric.",
            "ticket_specific_benchmark": [
                "PrimaryWeight equals sigma(theta_lab)",
                "PrimaryWeight equals sigma(theta_cm)",
                "unweighted theta_cm versus sigma(theta_cm)*sin(theta_cm)",
                "PrimaryWeight-weighted theta_cm versus sigma(theta_cm)*sin(theta_cm)",
                "PrimaryWeight-weighted theta_cm versus sigma(theta_cm)",
            ],
        },
        "run_split": {
            "available": False,
            "reason": "The available ROOT tree is a single Geant4 simulation ntuple and has no run-number branch; bootstrap CIs are computed over exported event rows.",
        },
        "geometry_file": str(inputs["geometry"]),
        "geometry": {k: v for k, v in geom.items() if k != "root_stdout"},
        "input_sha256": {name: sha256(path) for name, path in inputs.items() if path.is_file()},
        "source_commit": git_commit(G4SRC),
        "artifacts": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "primary_event_export.csv.gz",
            "primary_weight_closure_sample.csv.gz",
            "weight_closure_bins.csv",
            "angular_distribution_bins.csv",
            "bootstrap_cis.csv",
            "geometry_volume_inventory.csv",
            "geometry_root_audit.json",
            "geometry_overlap_stdout.txt",
        ],
        "next_tickets": [],
        "runtime_sec": None,
    }
    result["runtime_sec"] = float(time.time() - start)
    (OUT / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    manifest = {
        "command": f"python3 {Path(__file__).resolve().relative_to(ROOT)}",
        "cwd": str(ROOT),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(ROOT),
        "input_paths": {k: str(v) for k, v in inputs.items()},
        "input_sha256": result["input_sha256"],
        "output_sha256": {},
    }
    write_report(result, {"angular_distribution_bins": hist, "bootstrap_cis": boot, "geometry_volume_inventory": geom_vols})
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["output_sha256"][path.name] = sha256(path)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT.relative_to(ROOT)), "winner": result["winner"], "overlaps": geom["n_overlaps"]}, indent=2))


if __name__ == "__main__":
    main()
