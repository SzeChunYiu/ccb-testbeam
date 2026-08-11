"""Unit tests for --sipm-n-cells square-grid factorization policy (#974)."""
from __future__ import annotations

import math


def factorize_square_cells(n_cells: int) -> int:
    """Mirror EventAction::ApplySipmCellCount: require perfect square."""
    if n_cells <= 0:
        raise ValueError("n_cells must be > 0")
    side = int(round(math.sqrt(n_cells)))
    if side <= 0 or side * side != n_cells:
        raise ValueError(f"not a perfect square: {n_cells}")
    return side


def test_grid_points_are_perfect_squares():
    for n in (1600, 2500, 3600, 4900, 6400):
        side = factorize_square_cells(n)
        assert side * side == n


def test_non_square_rejected():
    for n in (1800, 3601, 1000):
        try:
            factorize_square_cells(n)
            raise AssertionError(f"expected rejection for {n}")
        except ValueError:
            pass


def test_representative_3600_is_60():
    assert factorize_square_cells(3600) == 60
