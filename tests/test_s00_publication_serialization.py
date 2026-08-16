from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation import s00_publication as pub


def test_unserializable_model_identity_fails_before_generation_move(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generations"
    pointer = tmp_path / "CURRENT.json"
    staging = pub.create_staging_directory(root, token="gen1")
    (staging / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(pub.S00PublicationError, match="not JSON-serializable"):
        pub.publish_generation(
            staging,
            root,
            pointer,
            generation_id="gen1",
            artifacts={"manifest": "manifest.json"},
            model_identity={"invalid": {1, 2, 3}},
        )

    assert staging.is_dir()
    assert not (root / "gen1").exists()
    assert not pointer.exists()
