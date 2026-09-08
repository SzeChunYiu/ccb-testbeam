#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Plot and report outputs for the historical timing-result audit."""
from timing_result_audit_core import *  # noqa: F403


def write_fraction_table(rows: list[dict[str, float]], path: Path) -> None:
    fieldnames = ["fraction", "sigma68_ns", "core_sigma_ns", "rms_ns", "chi2_ndf"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_figure(figure: plt.Figure, out: Path, stem: str) -> None:
    figure.tight_layout()
    figure.savefig(out / f"{stem}.png", dpi=180)
    figure.savefig(out / f"{stem}.svg")
    plt.close(figure)


def plot_width_scan(rows: list[dict[str, float]], out: Path) -> None:
    fractions = np.asarray([row["fraction"] for row in rows])
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.plot(fractions, [row["sigma68_ns"] for row in rows], marker="o", label="central 68% width")
    axis.plot(
        fractions,
        [row["core_sigma_ns"] for row in rows],
        marker="s",
        label="Gaussian-core sigma",
    )
    axis.plot(fractions, [row["rms_ns"] for row in rows], marker="^", label="full RMS")
    axis.set_yscale("log")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("reported residual scale (ns, log axis)")
    axis.set_title("Issue #1320: core narrows while the full distribution stays broad")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(figure, out, "01_reported_width_scan")


def plot_non_gaussianity(rows: list[dict[str, float]], out: Path) -> None:
    fractions = np.asarray([row["fraction"] for row in rows])
    ratios = np.asarray([row["rms_ns"] / row["sigma68_ns"] for row in rows])
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.plot(fractions, ratios, marker="o")
    axis.axhline(1.0, linestyle="--", linewidth=1.0, label="Gaussian-like scale agreement")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("RMS / central-68% width")
    axis.set_title("Large RMS/core mismatch: the residual is strongly non-Gaussian")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(figure, out, "02_non_gaussianity_ratio")


def plot_fit_quality(rows: list[dict[str, float]], out: Path) -> None:
    fractions = np.asarray([row["fraction"] for row in rows])
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.plot(fractions, [row["chi2_ndf"] for row in rows], marker="o")
    axis.axhline(1.0, linestyle="--", linewidth=1.0, label="ideal order of magnitude")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("Gaussian-core fit chi2 / ndf")
    axis.set_yscale("log")
    axis.set_title("The Gaussian-core model is rejected at every scanned fraction")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(figure, out, "03_gaussian_fit_quality")


def sigma68(values: np.ndarray) -> float:
    q16, q84 = np.quantile(values, [0.16, 0.84])
    return float(0.5 * (q84 - q16))


def plot_deconvolution_counterexamples(
    out: Path, seed: int = 20260831
) -> list[dict[str, float | str]]:
    rng = np.random.default_rng(seed)
    n = 400_000
    cases: list[tuple[str, np.ndarray, np.ndarray]] = []

    a = rng.normal(0.0, 1.0, n)
    b = rng.normal(0.0, 1.0, n)
    cases.append(("equal independent normal", a, b))

    a = rng.normal(0.0, 1.0, n)
    b = rng.normal(0.0, 2.0, n)
    cases.append(("unequal independent normal", a, b))

    common = rng.normal(0.0, 1.0, n)
    a = common + rng.normal(0.0, 1.0, n)
    b = common + rng.normal(0.0, 1.0, n)
    cases.append(("equal with common jitter", a, b))

    a = rng.laplace(0.0, 1.0, n)
    b = rng.laplace(0.0, 1.0, n)
    cases.append(("equal independent Laplace", a, b))

    records: list[dict[str, float | str]] = []
    for name, first, second in cases:
        pair = first - second
        naive = sigma68(pair) / math.sqrt(2.0)
        true_first = sigma68(first)
        records.append(
            {
                "case": name,
                "true_stave_A_sigma68": true_first,
                "pair_sigma68": sigma68(pair),
                "naive_pair_over_sqrt2": naive,
                "relative_error_percent": 100.0 * (naive / true_first - 1.0),
            }
        )

    labels = [str(record["case"]) for record in records]
    errors = [float(record["relative_error_percent"]) for record in records]
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    positions = np.arange(len(labels))
    axis.bar(positions, errors)
    axis.axhline(0.0, linewidth=1.0)
    axis.set_xticks(positions, labels, rotation=18, ha="right")
    axis.set_ylabel("error of pair sigma68 / sqrt(2) vs stave-A sigma68 (%)")
    axis.set_title("The sqrt(2) conversion is a special-case assumption, not a general estimator")
    axis.grid(True, axis="y", alpha=0.25)
    save_figure(figure, out, "04_sqrt2_counterexamples")
    return records


def plot_inference_gate(out: Path) -> None:
    figure, axis = plt.subplots(figsize=(9.2, 5.8))
    axis.set_axis_off()
    boxes = [
        (0.05, 0.76, "1. Validate raw frame shape, map status, and real pulse identity"),
        (0.05, 0.57, "2. Produce pair residuals with held-out cuts and full tail diagnostics"),
        (0.05, 0.38, "3. Measure at least 3 connected pairs or use a calibrated reference"),
        (0.05, 0.19, "4. Model covariance and close the estimator on simulation/injection"),
    ]
    for x, y, text in boxes:
        axis.text(
            x,
            y,
            text,
            transform=axis.transAxes,
            fontsize=11,
            va="center",
            bbox={"boxstyle": "round,pad=0.5", "facecolor": "none", "edgecolor": "black"},
        )
    for y_top, y_bottom in [(0.72, 0.63), (0.53, 0.44), (0.34, 0.25)]:
        axis.annotate(
            "",
            xy=(0.5, y_bottom),
            xytext=(0.5, y_top),
            xycoords="axes fraction",
            arrowprops={"arrowstyle": "->"},
        )
    axis.text(
        0.64,
        0.48,
        "Current Issue #1320 evidence stops here:\nretracted map + non-Gaussian pair only",
        transform=axis.transAxes,
        fontsize=11,
        va="center",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "none", "edgecolor": "black"},
    )
    axis.text(
        0.63,
        0.12,
        "Only after all gates pass:\nquote per-stave resolution with uncertainty",
        transform=axis.transAxes,
        fontsize=11,
        va="center",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "none", "edgecolor": "black"},
    )
    axis.set_title(
        "Fail-closed path from waveform samples to an intrinsic stave resolution",
        pad=18,
    )
    save_figure(figure, out, "05_resolution_inference_gate")


def write_markdown_summary(
    out: Path,
    rows_source: str,
    map_status: str | None,
    outcome: AuditOutcome,
    counterexamples: list[dict[str, float | str]],
) -> None:
    lines = [
        "# Generated timing-claim audit",
        "",
        f"- Fraction table source: `{rows_source}`",
        f"- Channel-map status: `{map_status}`",
        f"- Audit status: **{outcome.status}**",
        f"- Pair residual authorized as detector timing: **{outcome.pair_residual_authorized}**",
        f"- Single-stave resolution authorized: **{outcome.single_stave_resolution_authorized}**",
        "",
        "## Recommended headline",
        "",
        outcome.recommended_headline,
        "",
        "## Findings",
        "",
    ]
    for finding in outcome.findings:
        lines.extend(
            [
                f"### {finding.severity}: {finding.code}",
                "",
                finding.summary,
                "",
                "```json",
                json.dumps(finding.evidence, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Fixed-seed sqrt(2) counterexamples",
            "",
            "| case | true stave-A sigma68 | pair sigma68 | pair/sqrt(2) | relative error |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for record in counterexamples:
        lines.append(
            "| {case} | {true_stave_A_sigma68:.4f} | {pair_sigma68:.4f} | "
            "{naive_pair_over_sqrt2:.4f} | {relative_error_percent:+.2f}% |".format(
                **record
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This audit does not reprocess immutable ROOT inputs. It diagnoses the published "
            "result contract and demonstrates why the current pair statistic cannot be promoted "
            "to an intrinsic stave resolution. Raw-data promotion requires every gate in "
            "`diagnostic_plot_manifest.csv` to pass.",
            "",
        ]
    )
    (out / "AUDIT_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
