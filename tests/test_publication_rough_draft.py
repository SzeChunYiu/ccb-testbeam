from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PUB = REPO / "publication"


def test_rough_build_is_separate_and_fail_safe():
    main = (PUB / "main.tex").read_text()
    makefile = (PUB / "Makefile").read_text()
    wrapper = (PUB / "rough.tex").read_text()

    assert "\\ifdefined\\RoughPaperFigures" in main
    assert "PRELIMINARY / GATED -- internal rough-draft view only" in main
    assert "candidate omitted because the artifact is unavailable" in main
    assert "\\input{chapters/C_rough_figure_inventory}" in main
    assert "\\def\\RoughPaperFigures{1}" in wrapper
    assert "rough: validate" in makefile
    assert "rough-paper.pdf" in makefile


def test_rough_inventory_covers_nonchapter_candidate_families():
    inventory = (PUB / "chapters" / "C_rough_figure_inventory.tex").read_text()
    expected = {
        "figures/gated/fig08_mc_deltaE_E_I.png",
        "figures/gated/fig08_mc_deltaE_E_II.png",
        "figures/gated/fig_b2_b4_two_channel_diagnostic.png",
        "figures/gated/selected_pulse_inventory.png",
        "figures/model_diagnostics/timing_mc_method_closure.png",
        "figures/model_diagnostics/pid_mc_validation.png",
        "figures/model_diagnostics/adc_mc_calibration.png",
        "figures/model_diagnostics/birks_mc_comparison.png",
        "figures/model_diagnostics/pileup_digitizer_mc.png",
        "../docs/figures/paper/anomaly_truth_mc.png",
        "../docs/figures/paper/pca_truth_mc.png",
        "../docs/figures/paper/stopping_b8_tension.png",
        "../docs/figures/paper/systematic_sensitivity_inputs.png",
        "figures/illustrative/03_waveform_annotated.png",
        "figures/illustrative/06_timewalk_explained.png",
    }
    for path in expected:
        assert path in inventory


def test_rough_numbers_table_exposes_key_diagnostic_values_with_boundaries():
    inventory = (PUB / "chapters" / "C_rough_figure_inventory.tex").read_text()

    # Values are deliberately source-table-bound diagnostics, not promoted claims.
    for token in (
        "0.0893",
        "0.8976",
        "119.168",
        "0.01562",
        "0.605",
        "0.323\\%",
        "72.5\\%",
        "22.29\\%",
        "reflectivity 3.484",
    ):
        assert token in inventory

    assert "not canonical detector $R_{\\max}$" in inventory
    assert "Truth-level MC only" in inventory
    assert "Legacy gated data/MC diagnostic" in inventory
    assert "not propagated systematic uncertainties" in inventory


def test_canonical_build_does_not_define_rough_mode():
    build = (PUB / "build.sh").read_text()
    assert "RoughPaperFigures" not in build
    assert "main.tex" in build
