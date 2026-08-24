"""Tests for shared Arcam FMJ entity infrastructure."""

from arcam.fmj.codecs import SourceCodes
from arcam.fmj.commands import FM_GENRE
import pytest

from custom_components.arcam_fmj.coordinator import ArcamFmjConfigEntry
from custom_components.arcam_fmj.entity import (
    ArcamFmjCommandEntityDescription,
    ArcamFmjEntity,
)


@pytest.mark.usefixtures("player_setup")
async def test_source_gated_availability(
    mock_config_entry: ArcamFmjConfigEntry,
) -> None:
    """Test command entities are unavailable outside their supported source."""
    coordinator = mock_config_entry.runtime_data.coordinators[1]
    entity = ArcamFmjEntity(
        coordinator,
        ArcamFmjCommandEntityDescription(key="fm_genre", command=FM_GENRE),
    )

    coordinator.state.get_source.return_value = SourceCodes.FM
    assert entity.available

    coordinator.state.get_source.return_value = SourceCodes.DAB
    assert not entity.available
