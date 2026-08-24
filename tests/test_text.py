"""Tests for Arcam FMJ text entities."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from arcam.fmj.commands import FRIENDLY_NAME
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)

ENTITY_ID = "text.arcam_fmj_127_0_0_1_friendly_name"


@pytest.fixture(autouse=True)
def text_only() -> Generator[None]:
    """Limit platform setup to text only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.TEXT]):
        yield


@pytest.mark.parametrize("device_model", ["SA20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the text platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_model", ["SA20"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_read_and_write(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test reading and writing the friendly name."""
    state_1.command_values[FRIENDLY_NAME] = "Living Room"
    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "Living Room"

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: "Music Room"},
        blocking=True,
    )
    state_1.set.assert_awaited_once_with(FRIENDLY_NAME, "Music Room")


@pytest.mark.usefixtures("player_setup")
async def test_model_support(hass: HomeAssistant) -> None:
    """Test friendly name is created only for supported models."""
    assert hass.states.get(ENTITY_ID) is None
