from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation import s00_publication as pub


def test_staging_directory_itself_cannot_be_a_symlink(tmp_path: Path) -> None:
    root = tmp_path / "generations"
    root.mkdir()
    pointer = tmp_path / "CURRENT.json"

    outside = tmp_path / "outside-staging"
    outside.mkdir()
    (outside / "manifest.json").write_text("outside\n", encoding="utf-8")

    staging = root / ".staging-alias"
    staging.symlink_to(outside, target_is_directory=True)

    with pytest.raises(pub.S00PublicationError, match="staging_dir itself"):
        pub.publish_generation(
            staging,
            root,
            pointer,
            generation_id="gen1",
            artifacts={"manifest": "manifest.json"},
            model_identity={},
        )

    assert not pointer.exists()
    assert not (root / "gen1").exists()
    assert (outside / "manifest.json").read_text(encoding="utf-8") == "outside\n"
