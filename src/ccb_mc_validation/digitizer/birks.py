"""Birks quenching for heavy ions."""

from __future__ import annotations

import numpy as np


def birks_quench(
    edep_mev: float,
    *,
    step_length_cm: float | None = None,
    dedx_mev_per_cm: float | None = None,
    k_b_cm_per_mev: float = 0.008,
) -> float:
    """Apply Birks' law: ``L = E / (1 + k_B * dE/dx)``.

    NOTE (#1079): the ``0.008 cm/MeV`` default exists only for low-level unit
    tests of the algebraic form. Production callers (``DigitizerPipeline``)
    must pass an explicit unit-tagged kB; do not treat this default as the
    validated detector response identity.

    Birks' quenching requires the specific energy loss ``dE/dx`` (units
    ``MeV/cm``), with ``k_B`` in ``cm/MeV``.  It cannot be inferred from the
    total energy deposit alone -- a step length or an explicit ``dE/dx`` is
    mandatory.  Callers must therefore supply either ``step_length_cm`` (from
    which ``dE/dx = E / step_length`` is formed) or ``dedx_mev_per_cm``
    directly; omitting both is a hard error rather than a silent default.

    Parameters
    ----------
    edep_mev
        Energy deposit in the step (MeV).
    step_length_cm, dedx_mev_per_cm
        Provide exactly one.  ``step_length_cm`` yields ``dE/dx = E/dx``; use
        ``dedx_mev_per_cm`` to pass a measured/table value directly.
    k_b_cm_per_mev
        Birks constant in ``cm/MeV``.
    """
    if step_length_cm is None and dedx_mev_per_cm is None:
        raise ValueError(
            "birks_quench requires step_length_cm or dedx_mev_per_cm; "
            "dE/dx cannot be inferred from total edep alone (dimensionally invalid)"
        )
    if step_length_cm is not None and dedx_mev_per_cm is not None:
        raise ValueError(
            "birks_quench: provide exactly one of step_length_cm / dedx_mev_per_cm, not both"
        )
    edep = float(edep_mev)
    if not np.isfinite(edep) or edep < 0.0:
        raise ValueError(f"edep_mev must be finite and non-negative, got {edep_mev!r}")
    if step_length_cm is not None:
        dx = float(step_length_cm)
        if not np.isfinite(dx) or dx <= 0.0:
            raise ValueError(f"step_length_cm must be positive and finite, got {step_length_cm!r}")
        dedx = edep / dx
    else:
        dedx = float(dedx_mev_per_cm)  # type: ignore[arg-type]
        if not np.isfinite(dedx) or dedx < 0.0:
            raise ValueError(
                f"dedx_mev_per_cm must be finite and non-negative, got {dedx_mev_per_cm!r}"
            )
    return edep / (1.0 + float(k_b_cm_per_mev) * dedx)
