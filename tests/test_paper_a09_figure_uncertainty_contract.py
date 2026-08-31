from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PRODUCER = REPO / "scripts" / "single_stave" / "paper_a09_heldout_edep_reconstruction.py"


def test_a09_producer_has_no_fake_zero_errorbars():
    source = PRODUCER.read_text()
    compile(source, str(PRODUCER), "exec")

    assert "yerr=[[0], [0]]" not in source
    assert "median_bias_ci16_low_fraction" in source
    assert "median_bias_ci84_high_fraction" in source
    assert "sigma68_ci16_low_fraction" in source
    assert "sigma68_ci84_high_fraction" in source
    assert "ax_res.errorbar(" in source
    assert "_asymmetric_yerr" in source


def test_a09_plot_canvas_does_not_carry_governance_status():
    source = PRODUCER.read_text()
    assert "(MODEL-DEPENDENT OPTICAL MC)" not in source
    assert 'f"Held-out {energy_label} energy reconstruction"' in source
