"""
Figure 05 — PCA vs Autoencoder Pulse Shape Compression (Chapter 7).

Core conclusion: AE dominates at d=2–4, PCA wins at d=8; 8 components
capture 99.7% of variance — pulses are simple shapes.

Archetype: quantitative grid.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig, despine
from ..data import get_pca_ae


def build() -> str:
    pa = get_pca_ae()

    fig, ax = new_fig(7, 4.2)
    despine(ax)

    dims = pa.latent_dims
    x = np.arange(len(dims))
    width = 0.32

    bars_pca = ax.bar(x - width / 2, pa.pca_mse, width,
                      label="PCA", color=PALETTE["traditional"],
                      edgecolor="white", linewidth=0.3, alpha=0.9)
    bars_ae = ax.bar(x + width / 2, pa.ae_mse, width,
                     label="Autoencoder", color=PALETTE["ml"],
                     edgecolor="white", linewidth=0.3, alpha=0.9)

    # Annotate winners
    winners = ["AE +51%", "AE +41%", "AE +40%", "PCA +76%"]
    for i, (bp, ba, w) in enumerate(zip(bars_pca, bars_ae, winners)):
        winner = bp if "PCA" in w else ba
        ax.text(winner.get_x() + winner.get_width() / 2,
                max(bp.get_height(), ba.get_height()) + 0.0012,
                w, ha="center", fontsize=6.5, fontweight="bold",
                color=PALETTE["neutral_dark"])

    ax.set_xticks(x)
    ax.set_xticklabels([f"d = {d}" for d in dims], fontsize=7.5)
    ax.set_ylabel("Reconstruction MSE", fontweight="bold", fontsize=7.5)
    ax.set_xlabel("Latent Dimension", fontweight="bold", fontsize=7.5)
    ax.legend(loc="upper right", fontsize=7, handlelength=1.2)
    ax.yaxis.grid(True, alpha=0.2)

    # Variance explained annotation
    ax.text(0.98, 0.95,
            f"3 PCA components: {pa.pca_components_3:.0f}% variance\n"
            f"8 PCA components: {pa.pca_components_8:.1f}% variance",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=6.5, color=PALETTE["neutral_mid"])

    ax.set_title("Pulse Shape Compression: PCA vs Autoencoder",
                 fontweight="bold", fontsize=9, pad=12)

    plt.tight_layout(pad=0.8)
    name = "05_pca_vs_ae"
    save_pub(fig, name)
    return name
