"""Tests for Arcam FMJ button entities."""

from collections.abc import Generator
from unittest.mock import Mock, call, patch

from arcam.fmj.codecs import SourceCodes
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)

DAB_SCAN_ENTITY_ID = "button.arcam_fmj_127_0_0_1_dab_scan"
FM_SCAN_DOWN_ENTITY_ID = "button.arcam_fmj_127_0_0_1_fm_scan_down"
FM_SCAN_UP_ENTITY_ID = "button.arcam_fmj_127_0_0_1_fm_scan_up"
ENTITY_IDS = {
    DAB_SCAN_ENTITY_ID,
    FM_SCAN_DOWN_ENTITY_ID,
    FM_SCAN_UP_ENTITY_ID,
}


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Limit platform setup to button only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the button platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_press(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    """Test pressing scan buttons."""
    state_1.get_source.return_value = SourceCodes.FM

    for entity_id in (FM_SCAN_UP_ENTITY_ID, FM_SCAN_DOWN_ENTITY_ID):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    state_1.fm_scan.assert_has_awaits([call(up=True), call(up=False)])

    state_1.get_source.return_value = SourceCodes.DAB
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: DAB_SCAN_ENTITY_ID},
        blocking=True,
    )

    state_1.dab_scan.assert_awaited_once_with()


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_source_availability(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test scan buttons are available only on their tuner source."""
    state_1.get_source.return_value = SourceCodes.FM
    client.notify_data_updated()
    await hass.async_block_till_done()

    for entity_id, expected_state in (
        (FM_SCAN_UP_ENTITY_ID, STATE_UNKNOWN),
        (FM_SCAN_DOWN_ENTITY_ID, STATE_UNKNOWN),
        (DAB_SCAN_ENTITY_ID, STATE_UNAVAILABLE),
    ):
        entity_state = hass.states.get(entity_id)
        assert entity_state is not None
        assert entity_state.state == expected_state

    state_1.get_source.return_value = SourceCodes.DAB
    client.notify_data_updated()
    await hass.async_block_till_done()

    for entity_id, expected_state in (
        (FM_SCAN_UP_ENTITY_ID, STATE_UNAVAILABLE),
        (FM_SCAN_DOWN_ENTITY_ID, STATE_UNAVAILABLE),
        (DAB_SCAN_ENTITY_ID, STATE_UNKNOWN),
    ):
        entity_state = hass.states.get(entity_id)
        assert entity_state is not None
        assert entity_state.state == expected_state


@pytest.mark.parametrize("device_model", ["SA20"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_model_support(hass: HomeAssistant) -> None:
    """Test scan buttons are created only for supported models."""
    for entity_id in ENTITY_IDS:
        assert hass.states.get(entity_id) is None


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_zone_support(hass: HomeAssistant) -> None:
    """Test scan buttons are not created in unsupported zones."""
    assert not any(
        "_zone_2_" in state.entity_id for state in hass.states.async_all(BUTTON_DOMAIN)
    )
