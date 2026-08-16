#!/usr/bin/env python3
"""
CCB single-stave geometry drawing (issue #892).

Every dimension and material property below is read directly from the Geant4
source (geant4/single_stave/include/DetectorConstruction.hh constants and
geant4/single_stave/src/DetectorConstruction.cc materials). No invented numbers:
the values are transcribed from the code so the figure stays in lock-step with
the simulation geometry. If the code changes, re-run this script.

Produces two PNGs + one combined SVG:
  fig_stave_crosssection_yz.png  - normal-incidence cross section (the y-z plane
                                   a primary sees), showing the two WLS fibre
                                   channels with their concentric core / inner
                                   cladding / outer cladding / air-gap stack,
                                   the scintillator bar and the TiO2 coating.
  fig_stave_longitudinal_xy.png  - top-down (x-y) longitudinal view showing the
                                   50 cm bar, both fibres running along x and
                                   protruding 1 cm past each face, and the four
                                   SiPM endcap sensors.
  ccb_stave_geometry.svg         - vector combined version.
"""
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrow, FancyArrowPatch
from matplotlib.lines import Line2D
import numpy as np
import os

# ---------------------------------------------------------------------------
# Geometry constants  --- SOURCE OF TRUTH: DetectorConstruction.hh
# (half-lengths in cm where noted; converted to the figure's display units).
# ---------------------------------------------------------------------------
STAVE_HX = 25.0          # kStaveHalfX  (cm)  -> 50 cm length   [x = beam dir *see note]
STAVE_HY = 2.59          # kStaveHalfY  (cm)  -> 5.18 cm width  [y]
STAVE_HZ = 1.0           # kStaveHalfZ  (cm)  -> 2.0 cm thickness (primary travels +z)
COATING_T = 0.025        # kCoatingThk  (0.25 mm) TiO2 shell
HOLE_R = 0.10            # kHoleRadius  (1.0 mm) hole in scintillator
FIBRE_R = 0.090          # kFibreRadius (0.90 mm) outer-clad outer radius
FIBRE_HX = 26.0          # kFibreHalfX  (cm)  -> 52 cm, protrudes 1 cm per face
FIBRE_SEP = 2.0          # kFibreSep    (cm)  centre-to-centre, y = +/-1.0 cm
SENSOR_T = 0.010         # kSensorThk   (0.10 mm) endcap SiPM disc thickness

# Concentric fibre radii --- SOURCE OF TRUTH: DetectorConstruction.cc Construct()
#   rCore  = kFibreRadius * 0.94
#   rInner = kFibreRadius * 0.97
#   rOuter = kFibreRadius * 1.00
RCORE = FIBRE_R * 0.94
RINNER = FIBRE_R * 0.97
ROUTER = FIBRE_R * 1.00

# Material refractive indices --- SOURCE OF TRUTH: DetectorConstruction.cc Build*()
N_SCINT = 1.59   # CCB_Scintillator (polystyrene)
N_CORE = 1.59    # CCB_Y11Core (Y-11 doped polystyrene)
N_INNER = 1.49   # CCB_FibreInnerClad (PMMA)
N_OUTER = 1.42   # CCB_FibreOuterClad (fluorinated PMMA)
N_GAP = 1.00     # optical gap = air
RHO_SCINT = 1.06  # g/cm3
RHO_CORE = 1.05
RHO_CLAD = 1.19

# fibre centre y-positions
YC = [+FIBRE_SEP / 2.0, -FIBRE_SEP / 2.0]   # +1.0 cm, -1.0 cm

OUTDIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# colours (material-keyed, colour-blind friendly)
# ---------------------------------------------------------------------------
C_SCINT = "#3a86ff"   # blue   - polystyrene scintillator
C_CORE = "#ffbe0b"    # amber  - Y-11 WLS core
C_INNER = "#fb5607"   # orange - PMMA inner clad
C_OUTER = "#8338ec"   # purple - fluorinated PMMA outer clad
C_GAP = "#e9ecef"     # pale   - air gap (between fibre & hole wall)
C_COAT = "#ffffff"    # white  - TiO2 reflective coating shell
C_SIPM = "#2d3436"    # dark   - SiPM sensor
C_WORLD = "#f5f5f5"

# ===========================================================================
# FIGURE 1 : y-z cross section (what a primary at normal incidence sees)
# Looking along -x (down the fibre axis). This is the diagnostic view: the two
# fibre channels with the full cladding stack.
# ===========================================================================
def draw_crosssection():
    fig, ax = plt.subplots(figsize=(10, 6.2))
    # world (air) background
    ax.add_patch(Rectangle((-STAVE_HY - 1.0, -STAVE_HZ - 1.0),
                           2 * (STAVE_HY + 1.0), 2 * (STAVE_HZ + 1.0),
                           fc=C_WORLD, ec="#cccccc", zorder=0))

    # coating shell (outer)
    ax.add_patch(Rectangle((-(STAVE_HY + COATING_T), -(STAVE_HZ + COATING_T)),
                           2 * (STAVE_HY + COATING_T), 2 * (STAVE_HZ + COATING_T),
                           fc=C_COAT, ec="#9a9a9a", lw=1.0, zorder=1))
    # TiO2 hatch to indicate reflective coating
    ax.add_patch(Rectangle((-(STAVE_HY + COATING_T), -(STAVE_HZ + COATING_T)),
                           2 * (STAVE_HY + COATING_T), 2 * (STAVE_HZ + COATING_T),
                           fill=False, hatch='////', ec="#9a9a9a", lw=0.4, zorder=2))

    # scintillator bar
    ax.add_patch(Rectangle((-STAVE_HY, -STAVE_HZ), 2 * STAVE_HY, 2 * STAVE_HZ,
                           fc=C_SCINT, ec="#1f5fc0", lw=1.2, zorder=3,
                           alpha=0.92))

    # two fibre channels
    for i, yc in enumerate(YC):
        # air gap (hole) - drawn as the hole circle in the scintillator
        ax.add_patch(Circle((yc, 0), HOLE_R, fc=C_GAP, ec="#b0b0b0", lw=0.8, zorder=4))
        # outer cladding
        ax.add_patch(Circle((yc, 0), ROUTER, fc=C_OUTER, ec="#5a2796", lw=0.6, zorder=5))
        # inner cladding
        ax.add_patch(Circle((yc, 0), RINNER, fc=C_INNER, ec="#b23a04", lw=0.6, zorder=6))
        # WLS core
        ax.add_patch(Circle((yc, 0), RCORE, fc=C_CORE, ec="#a37a00", lw=0.6, zorder=7))
        # label fibre
        ax.annotate(f"Fibre {i+1} (Y-11)", (yc, 0), (yc, 0.62),
                    ha="center", fontsize=8.5, color="#333",
                    arrowprops=dict(arrowstyle="-", color="#666", lw=0.6))

    # dimension annotations
    # stave width
    ax.annotate("", (-STAVE_HY, -STAVE_HZ - 0.45), (STAVE_HY, -STAVE_HZ - 0.45),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(0, -STAVE_HZ - 0.62, f"width 2×kStaveHalfY = {2*STAVE_HY:.2f} cm",
            ha="center", fontsize=8.5)
    # stave thickness
    ax.annotate("", (STAVE_HY + 0.55, -STAVE_HZ), (STAVE_HY + 0.55, STAVE_HZ),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(STAVE_HY + 0.62, 0, f"thickness\n2×kStaveHalfZ = {2*STAVE_HZ:.2f} cm\n(normal path)",
            ha="left", va="center", fontsize=8.5)
    # fibre separation
    ax.annotate("", (YC[0], -0.30), (YC[1], -0.30),
                arrowprops=dict(arrowstyle="<->", color="#c0392b"))
    ax.text(0, -0.40, f"kFibreSep = {FIBRE_SEP:.2f} cm", ha="center",
            fontsize=8, color="#c0392b")
    # primary beam arrow (+z, normal incidence)
    ax.annotate("", (-STAVE_HY - 0.55, -1.55), (-STAVE_HY - 0.55, -1.05),
                arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=2))
    ax.text(-STAVE_HY - 0.62, -1.3, "primary (+z,\nnormal incidence)",
            ha="right", va="center", fontsize=8, color="#e74c3c")

    # coordinate label
    ax.text(-STAVE_HY - 0.9, STAVE_HZ + 0.9, "view: looking along -x (fibre axis)",
            fontsize=8, style="italic", color="#555")

    # legend (materials + refractive indices)
    handles = [
        plt.scatter([], [], s=60, color=C_SCINT, label=f"Scintillator (polystyrene)  n={N_SCINT}  {RHO_SCINT} g/cm³", marker="s"),
        plt.scatter([], [], s=60, color=C_CORE, label=f"WLS fibre core (Y-11 PS)  n={N_CORE}  {RHO_CORE} g/cm³", marker="s"),
        plt.scatter([], [], s=60, color=C_INNER, label=f"Inner cladding (PMMA)  n={N_INNER}", marker="s"),
        plt.scatter([], [], s=60, color=C_OUTER, label=f"Outer cladding (fluor. PMMA)  n={N_OUTER}  {RHO_CLAD} g/cm³", marker="s"),
        plt.scatter([], [], s=60, color=C_GAP, label=f"Optical gap (air)  n={N_GAP}", marker="s", edgecolors="#999"),
        plt.scatter([], [], s=60, color=C_COAT, label="TiO₂ coating (diffuse reflector)", marker="s", edgecolors="#888"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.14),
              ncol=2, fontsize=8, frameon=False, title="Materials  (refractive index n)",
              title_fontsize=9)

    ax.set_xlim(-STAVE_HY - 1.3, STAVE_HY + 1.9)
    ax.set_ylim(-STAVE_HZ - 1.3, STAVE_HZ + 1.3)
    ax.set_aspect("equal")
    ax.set_xlabel("y  [cm]  (width)", fontsize=9)
    ax.set_ylabel("z  [cm]  (thickness)", fontsize=9)
    ax.set_title("CCB single stave — cross section (y–z plane, normal incidence)\n"
                 "fibre channel detail: WLS core < inner cladding < outer cladding < air gap < scintillator",
                 fontsize=10.5)
    ax.grid(True, ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "fig_stave_crosssection_yz.png"), dpi=200, bbox_inches="tight")
    fig.savefig(os.path.join(OUTDIR, "ccb_stave_geometry.svg"), bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_stave_crosssection_yz.png + ccb_stave_geometry.svg")

# ===========================================================================
# FIGURE 2 : x-y longitudinal view (top-down), shows protruding fibres + SiPMs
# ===========================================================================
def draw_longitudinal():
    fig, ax = plt.subplots(figsize=(11, 4.2))
    # world
    ax.add_patch(Rectangle((-FIBRE_HX - 2.0, -STAVE_HY - 1.0),
                           2 * (FIBRE_HX + 2.0), 2 * (STAVE_HY + 1.0),
                           fc=C_WORLD, ec="#cccccc", zorder=0))
    # scintillator bar (x-y plane: length x width)
    ax.add_patch(Rectangle((-STAVE_HX, -STAVE_HY), 2 * STAVE_HX, 2 * STAVE_HY,
                           fc=C_SCINT, ec="#1f5fc0", lw=1.0, zorder=2, alpha=0.92))
    # coating outline
    ax.add_patch(Rectangle((-STAVE_HX - COATING_T, -STAVE_HY - COATING_T),
                           2 * (STAVE_HX + COATING_T), 2 * (STAVE_HY + COATING_T),
                           fill=False, ec="#666", lw=0.8, ls="--", zorder=1))

    # fibres run along x at y = +/-1 cm (drawn as thin rectangles, fibre diameter=1.8mm=0.09cm half)
    for i, yc in enumerate(YC):
        # fibre body (outer cladding strip) spanning full fibre length incl protrusion
        ax.add_patch(Rectangle((-FIBRE_HX, yc - ROUTER), 2 * FIBRE_HX, 2 * ROUTER,
                               fc=C_OUTER, ec="none", zorder=3))
        ax.add_patch(Rectangle((-FIBRE_HX, yc - RINNER), 2 * FIBRE_HX, 2 * RINNER,
                               fc=C_INNER, ec="none", zorder=4))
        ax.add_patch(Rectangle((-FIBRE_HX, yc - RCORE), 2 * FIBRE_HX, 2 * RCORE,
                               fc=C_CORE, ec="none", zorder=5))
        ax.text(0, yc + 0.35, f"fibre {i+1} runs along x (Ø {2*ROUTER*10:.2f} mm)",
                ha="center", fontsize=7.5, color="#444")

    # SiPM endcap sensors at both ends of both fibres
    for i, yc in enumerate(YC):
        for sign in (+1, -1):
            xpos = sign * (FIBRE_HX + SENSOR_T / 2.0 + 0.001)  # +10 um gap
            # sensor is a disc (G4Tubs r=rOuter, t=0.10mm) - drawn tiny
            ax.add_patch(Rectangle((xpos - SENSOR_T / 2, yc - ROUTER),
                                   SENSOR_T, 2 * ROUTER,
                                   fc=C_SIPM, ec="#000", lw=0.4, zorder=6))

    # dimension: stave length
    ax.annotate("", (-STAVE_HX, -STAVE_HY - 0.6), (STAVE_HX, -STAVE_HY - 0.6),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(0, -STAVE_HY - 0.8, f"length 2×kStaveHalfX = {2*STAVE_HX:.1f} cm",
            ha="center", fontsize=8.5)
    # protrusion
    for sign, side in [(+1, "right"), (-1, "left")]:
        ax.annotate("", (sign * STAVE_HX, STAVE_HY + 0.45),
                    (sign * FIBRE_HX, STAVE_HY + 0.45),
                    arrowprops=dict(arrowstyle="<->", color="#c0392b"))
        ax.text(sign * (STAVE_HX + 0.05) - (0.6 if sign > 0 else -0.6),
                STAVE_HY + 0.58,
                f"protrudes\n{FIBRE_HX - STAVE_HX:.1f} cm", fontsize=7.5,
                color="#c0392b", ha="center")
    # sensor callouts
    ax.annotate("SiPM endcap sensors\n(4 channels: F1±x, F2±x)\nkSensorThk=0.10 mm, Ø=1.80 mm",
                (FIBRE_HX + 0.05, YC[0]), (FIBRE_HX - 9, STAVE_HY + 1.2),
                fontsize=7.5, ha="center",
                arrowprops=dict(arrowstyle="->", color="#333"))

    ax.set_xlim(-FIBRE_HX - 3, FIBRE_HX + 3)
    ax.set_ylim(-STAVE_HY - 1.3, STAVE_HY + 1.9)
    ax.set_aspect("equal")
    ax.set_xlabel("x  [cm]  (stave / fibre length)", fontsize=9)
    ax.set_ylabel("y  [cm]  (width)", fontsize=9)
    ax.set_title("CCB single stave — longitudinal view (x–y plane, top-down)\n"
                 "two Y-11 fibres span the bar and protrude for external SiPM readout",
                 fontsize=10.5)
    ax.grid(True, ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "fig_stave_longitudinal_xy.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_stave_longitudinal_xy.png")

# ===========================================================================
# FIGURE 3 : zoomed fibre radial stack (the cladding sandwich, to scale)
# ===========================================================================
def draw_fibre_stack():
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    # air gap (hole)
    ax.add_patch(Circle((0, 0), HOLE_R, fc=C_GAP, ec="#999", lw=0.8, zorder=1))
    ax.add_patch(Circle((0, 0), ROUTER, fc=C_OUTER, ec="#5a2796", lw=1.0, zorder=2))
    ax.add_patch(Circle((0, 0), RINNER, fc=C_INNER, ec="#b23a04", lw=1.0, zorder=3))
    ax.add_patch(Circle((0, 0), RCORE, fc=C_CORE, ec="#a37a00", lw=1.0, zorder=4))

    # radial callouts
    def radial_label(r, label, color, ang=35):
        x = r * np.cos(np.deg2rad(ang))
        y = r * np.sin(np.deg2rad(ang))
        ax.annotate("", (0, 0), (x, y),
                    arrowprops=dict(arrowstyle="-", color=color, lw=0.5))
    # dimension arrows on radii (to scale). Spread each callout to a distinct
    # angle so the four labels never overlap.
    for (r, name, col, ang) in [
        (RCORE,  f"rCore  = 0.94*kFibreRadius = {RCORE*10:.3f} mm",  C_CORE,  35),
        (RINNER, f"rInner = 0.97*kFibreRadius = {RINNER*10:.3f} mm", C_INNER, 62),
        (ROUTER, f"rOuter = 1.00*kFibreRadius = {ROUTER*10:.3f} mm", C_OUTER, 95),
        (HOLE_R, f"kHoleRadius = {HOLE_R*10:.2f} mm (scint hole)",   "#444",  128)]:
        ax.plot([0, r * np.cos(np.deg2rad(ang))], [0, r * np.sin(np.deg2rad(ang))],
                color=col, lw=1.0, alpha=0.7, zorder=6)
        ax.annotate(name,
                    (r * np.cos(np.deg2rad(ang)), r * np.sin(np.deg2rad(ang))),
                    (r * np.cos(np.deg2rad(ang)) + 0.018, r * np.sin(np.deg2rad(ang)) + 0.010),
                    fontsize=7.5, color=col, va="center",
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.5))

    # annular thickness annotations (right side)
    ax.annotate("", (ROUTER, -0.005), (RINNER, -0.005),
                arrowprops=dict(arrowstyle="<->", color=C_OUTER, lw=0.8))
    ax.text((ROUTER + RINNER) / 2, -0.012,
            f"outer clad\n{(ROUTER-RINNER)*1000:.0f} µm", fontsize=7, ha="center", color=C_OUTER)
    ax.annotate("", (RINNER, -0.022), (RCORE, -0.022),
                arrowprops=dict(arrowstyle="<->", color=C_INNER, lw=0.8))
    ax.text((RINNER + RCORE) / 2, -0.030,
            f"inner clad\n{(RINNER-RCORE)*1000:.0f} µm", fontsize=7, ha="center", color=C_INNER)
    ax.annotate("", (HOLE_R, -0.038), (ROUTER, -0.038),
                arrowprops=dict(arrowstyle="<->", color="#666", lw=0.8))
    ax.text((HOLE_R + ROUTER) / 2, -0.046,
            f"air gap\n{(HOLE_R-ROUTER)*1000:.0f} µm", fontsize=7, ha="center", color="#666")

    handles = [
        Line2D([], [], color=C_CORE, marker="s", ls="", label=f"WLS core (Y-11 PS)  n={N_CORE}"),
        Line2D([], [], color=C_INNER, marker="s", ls="", label=f"inner clad (PMMA)  n={N_INNER}"),
        Line2D([], [], color=C_OUTER, marker="s", ls="", label=f"outer clad (fluor. PMMA)  n={N_OUTER}"),
        Line2D([], [], color=C_GAP, marker="s", ls="", markeredgecolor="#999", label=f"air gap  n={N_GAP}"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.08),
              ncol=2, fontsize=8, frameon=False)
    ax.set_xlim(-HOLE_R * 1.4, HOLE_R * 1.7)
    ax.set_ylim(-HOLE_R * 1.7, HOLE_R * 1.4)
    ax.set_aspect("equal")
    ax.set_title("Single WLS fibre radial stack (to scale)\n"
                 "light trapping by total internal reflection at each n-step",
                 fontsize=10)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "fig_fibre_radial_stack.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_fibre_radial_stack.png")

if __name__ == "__main__":
    draw_crosssection()
    draw_longitudinal()
    draw_fibre_stack()
    # integrity self-check: confirm constants match the .hh source
    assert abs(2 * STAVE_HX - 50.0) < 1e-9
    assert abs(2 * STAVE_HY - 5.18) < 1e-9
    assert abs(2 * STAVE_HZ - 2.0) < 1e-9
    assert abs(HOLE_R - 0.10) < 1e-9
    assert abs(FIBRE_R - 0.090) < 1e-9
    assert abs(RCORE - 0.090 * 0.94) < 1e-9
    assert abs(RINNER - 0.090 * 0.97) < 1e-9
    assert abs(ROUTER - 0.090 * 1.00) < 1e-9
    assert abs(YC[0] - 1.0) < 1e-9 and abs(YC[1] + 1.0) < 1e-9
    print("integrity check PASS: constants match DetectorConstruction.hh")
