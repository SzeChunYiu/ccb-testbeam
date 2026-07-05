"""
Figure 20 — Key Results Summary Dashboard (Chapter 12).

NEW FIGURE — compact dashboard summarising the 5 main results
with uncertainties, verdicts, and open items.

Core conclusion: σ₆₈=0.55 ns, R_max=3.05 MHz, AUC=0.986,
C12=0.32%, syst. total ~12% — geometry fix is critical blocker.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig


def build() -> str:
    fig, ax = new_fig(11, 5)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")

    ax.text(5.5, 5.7, "CCB Test-Beam: Key Results Dashboard",
            ha="center", fontsize=11, fontweight="bold", color=PALETTE["neutral_black"])

    # Five result cards
    cards = [
        (0.2, 3.0, 3.2, 2.0,
         "Timing\nResolution",
         "σ₆₈(B6) = 0.72 ns\nσ₆₈(comb) = 0.55 ns",
         "B2 excluded (terminal d)\nCovariance validated\nAnalytic = ML (tied)",
         PALETTE["pass_green"], "PASS"),
        (3.8, 3.0, 3.2, 2.0,
         "Pile-up\nTolerance",
         "R_max = 3.05 MHz\nτ_eff = 124.8 ns",
         "Corrected from 4.22 MHz\nDownstream excess: 30.8%\nML score ratio: 1.30",
         PALETTE["pass_green"], "PASS"),
        (7.4, 3.0, 3.2, 2.0,
         "Particle\nIdentification",
         "AUC = 0.986 (MC ceiling)\nData within 0.5%",
         "HGB classifier validated\nLeakage-safe proxies\nRange-energy confirmed",
         PALETTE["pass_green"], "PASS"),
        (0.2, 0.3, 5.0, 2.0,
         "MC Validation\n& Systematics",
         "MV3: STRUCTURAL FAIL\nχ²/ndf = 68,269",
         "MV0: 92±28 ADC/MeV (30% sys.)\nMV4: +2.68σ tension (digitizer)\n"
         "Syst. total: ~12% on d-fraction",
         PALETTE["fail_red"], "BLOCKED"),
        (5.6, 0.3, 5.0, 2.0,
         "Anomaly\nDiscovery",
         "C12 recoils: 0.32%\n(MC-calibrated)",
         "Unsupervised cluster: ~4%\nFactor-12.5 discrepancy\n"
         "<0.1% impact on d-count",
         PALETTE["tension_orange"], "OPEN"),
    ]

    for x, y, w, h, title, big_num, detail, color, verdict in cards:
        ax.add_patch(plt.Rectangle((x, y), w, h,
                     facecolor=PALETTE["bg_light"],
                     edgecolor=PALETTE["neutral_light"], lw=0.8))
        # Verdict stripe
        ax.add_patch(plt.Rectangle((x, y + h - 0.25), w, 0.25,
                     facecolor=color, edgecolor="none", alpha=0.85))
        ax.text(x + w / 2, y + h - 0.13, verdict, ha="center", fontsize=6,
                fontweight="bold", color="white")

        ax.text(x + 0.15, y + h - 0.55, title, fontsize=7.5, fontweight="bold",
                color=PALETTE["neutral_black"])
        ax.text(x + 0.15, y + h - 1.2, big_num, fontsize=8.5, fontweight="bold",
                color=PALETTE["b2"])
        ax.text(x + 0.15, y + 0.05, detail, fontsize=5.5,
                color=PALETTE["neutral_mid"], va="bottom")

    # Critical blocker
    ax.text(5.5, 5.35,
            "Critical blocker: MV3 geometry fix (PR #8) → new MC production → "
            "re-run all Tier 2 validations",
            ha="center", fontsize=6.5, color=PALETTE["fail_red"], fontweight="bold")

    name = "20_key_results"
    save_pub(fig, name)
    return name
