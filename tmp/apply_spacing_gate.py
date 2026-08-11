from pathlib import Path

reg = Path("src/ccb_mc_validation/geometry/registry.py")
text = reg.read_text(encoding="utf-8")
if "require_spacing_hypothesis_for_tof" not in text:
    if "Mapping" not in text:
        text = text.replace("from typing import Any", "from typing import Any, Mapping", 1)
    text = text.rstrip() + """

def require_spacing_hypothesis_for_tof(config: Mapping[str, Any] | None) -> GeometryProfile:
    \"\"\"Fail closed for TOF/range claims that need analysed-stave spacing (#992).

    Both 2 cm and 4 cm profiles remain HYPOTHESIS / non-authorising until a
    hardware-backed APPROVED spacing profile exists. Callers must still name an
    explicit ``geometry_profile_id``; this helper additionally rejects profiles
    that do not declare ``analysed_stave_spacing_cm`` and rejects any attempt to
    treat a HYPOTHESIS spacing profile as claim-authorising.
    \"\"\"
    profile = require_geometry_profile(config)
    spacing = profile.parameters.get("analysed_stave_spacing_cm")
    if spacing is None:
        raise ConfigurationError(
            f"geometry profile {profile.profile_id!r} does not declare "
            "analysed_stave_spacing_cm; refuse TOF/range spacing use (#992)"
        )
    if profile.claims_authorized:
        return profile
    raise ConfigurationError(
        f"geometry profile {profile.profile_id!r} has analysed_stave_spacing_cm="
        f"{spacing} but claims_authorized=false (status={profile.status}); "
        "TOF/range claims remain BLOCKED pending hardware ledger closure (#992)"
    )
"""
    reg.write_text(text + "\n", encoding="utf-8")

init = Path("src/ccb_mc_validation/geometry/__init__.py")
it = init.read_text(encoding="utf-8")
if "require_spacing_hypothesis_for_tof" not in it:
    it = it.replace(
        "require_geometry_profile,\n)",
        "require_geometry_profile,\n    require_spacing_hypothesis_for_tof,\n)",
    )
    it = it.replace(
        '"require_geometry_profile",\n]',
        '"require_geometry_profile",\n    "require_spacing_hypothesis_for_tof",\n]',
    )
    init.write_text(it, encoding="utf-8")
print("patched registry")
