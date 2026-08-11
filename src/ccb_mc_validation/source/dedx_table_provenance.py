"""Fail-closed provenance headers for CD2 stopping tables (#1058)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ccb_mc_validation.exceptions import ConfigurationError

REQUIRED_DEDX_HEADER_KEYS = frozenset(
    {
        "units_energy",
        "units_dedx",
        "material",
        "conversion_energy",
        "conversion_dedx",
        "source",
        "status",
    }
)


def parse_dedx_provenance_headers(lines: Iterable[str]) -> dict[str, str]:
    """Parse leading ``# key: value`` provenance headers from a stopping table."""
    headers: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("#"):
            break
        body = line[1:].strip()
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def require_dedx_provenance_headers(path: Path, *, authorising: bool = True) -> dict[str, str]:
    """Require complete provenance headers before authorising stopping use."""
    path = Path(path)
    if not path.is_file():
        raise ConfigurationError(f"dedx table missing: {path}")
    headers = parse_dedx_provenance_headers(path.read_text(encoding="utf-8", errors="replace").splitlines())
    missing = sorted(REQUIRED_DEDX_HEADER_KEYS - set(headers))
    if missing and authorising:
        raise ConfigurationError(
            f"dedx table {path} missing required provenance headers {missing}; "
            "stopping-corrected kinematics remain BLOCKED (#1058)"
        )
    if authorising and headers.get("status", "").upper() not in {"OK", "APPROVED", "VALIDATED"}:
        raise ConfigurationError(
            f"dedx table {path} provenance status={headers.get('status')!r} is not "
            "authorising; #1058 remains BLOCKED until sourced metadata is ledgered"
        )
    return headers
