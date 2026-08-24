"""Tests for Arcam FMJ entity icons."""

import json
from pathlib import Path

INTEGRATION_PATH = Path(__file__).parents[1] / "custom_components" / "arcam_fmj"


def test_entity_icons() -> None:
    """Test every translated entity has a default icon."""
    strings = json.loads(
        (INTEGRATION_PATH / "strings.json").read_text(encoding="utf-8")
    )
    icons = json.loads((INTEGRATION_PATH / "icons.json").read_text(encoding="utf-8"))

    string_entities = strings["entity"]
    icon_entities = icons["entity"]
    assert string_entities.keys() == icon_entities.keys()

    for platform, entities in string_entities.items():
        platform_icons = icon_entities[platform]
        assert entities.keys() == platform_icons.keys()
        for entity_icons in platform_icons.values():
            assert entity_icons["default"].startswith("mdi:")
