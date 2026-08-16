"""Fail-closed digitizer rise/decay constants (#1075)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from ccb_mc_validation.digitizer.scintillation import (
    exponential_kernel_cdf,
    exponential_kernel_pdf,
    normalized_exponential_kernel,
)


@pytest.mark.parametrize(
    "bad",
    [0.0, -1.0, -10.0, float("nan"), float("inf"), -float("inf")],
)
@pytest.mark.parametrize(
    "fn",
    [exponential_kernel_pdf, exponential_kernel_cdf, normalized_exponential_kernel],
)
def test_rejects_nonphysical_tau_rise(fn, bad):
    t = np.linspace(0.0, 100.0, 51)
    with pytest.raises(ValueError, match="tau_rise_ns"):
        fn(t, bad, 35.0)


@pytest.mark.parametrize(
    "bad",
    [0.0, -1.0, -10.0, float("nan"), float("inf")],
)
@pytest.mark.parametrize(
    "fn",
    [exponential_kernel_pdf, exponential_kernel_cdf, normalized_exponential_kernel],
)
def test_rejects_nonphysical_tau_decay(fn, bad):
    t = np.linspace(0.0, 100.0, 51)
    with pytest.raises(ValueError, match="tau_decay_ns"):
        fn(t, 2.0, bad)


def test_nominal_kernel_still_integrates():
    t = np.linspace(0.0, 500.0, 5001)
    pdf = exponential_kernel_pdf(t, 2.0, 35.0)
    assert math.isfinite(float(pdf.sum()))
    assert pdf.min() >= -1e-15
    cdf = exponential_kernel_cdf(np.array([0.0, 1e6]), 2.0, 35.0)
    assert abs(float(cdf[0])) < 1e-12
    assert abs(float(cdf[1]) - 1.0) < 1e-6
