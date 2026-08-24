"""Tests for Arcam FMJ switch entities."""

from collections.abc import Generator
from unittest.mock import Mock, call, patch

from arcam.fmj.codecs import ZoneOsd
from arcam.fmj.commands import (
    DIRECT_MODE,
    DOLBY_PLIIX_PANORAMA,
    HEADPHONES_OVERRIDE,
    ZONE_1_OSD_ON_OFF,
)
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)

ENTITY_IDS = {
    DIRECT_MODE: "switch.arcam_fmj_127_0_0_1_direct_mode",
    DOLBY_PLIIX_PANORAMA: "switch.arcam_fmj_127_0_0_1_dolby_pliix_panorama",
    ZONE_1_OSD_ON_OFF: "switch.arcam_fmj_127_0_0_1_zone_1_osd",
}
HEADPHONES_OVERRIDE_ENTITY_ID = "switch.arcam_fmj_127_0_0_1_headphone_override"


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Limit platform setup to switch only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the switch platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_read_and_write(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test reading and writing direct switches."""
    state_1.command_values.update(
        {
            DIRECT_MODE: True,
            DOLBY_PLIIX_PANORAMA: False,
            ZONE_1_OSD_ON_OFF: ZoneOsd.ON,
        }
    )
    client.notify_data_updated()
    await hass.async_block_till_done()

    for command, expected_state in (
        (DIRECT_MODE, STATE_ON),
        (DOLBY_PLIIX_PANORAMA, STATE_OFF),
        (ZONE_1_OSD_ON_OFF, STATE_ON),
    ):
        entity_state = hass.states.get(ENTITY_IDS[command])
        assert entity_state is not None
        assert entity_state.state == expected_state

    for command, entity_id in ENTITY_IDS.items():
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert state_1.set.await_args_list == [
        call(DIRECT_MODE, True),
        call(DIRECT_MODE, False),
        call(DOLBY_PLIIX_PANORAMA, True),
        call(DOLBY_PLIIX_PANORAMA, False),
        call(ZONE_1_OSD_ON_OFF, ZoneOsd.ON),
        call(ZONE_1_OSD_ON_OFF, ZoneOsd.OFF),
    ]


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_headphones_override(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    """Test the write-only headphone override switch."""
    entity_state = hass.states.get(HEADPHONES_OVERRIDE_ENTITY_ID)
    assert entity_state is not None
    assert entity_state.state == STATE_UNKNOWN
    assert entity_state.attributes[ATTR_ASSUMED_STATE]

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HEADPHONES_OVERRIDE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HEADPHONES_OVERRIDE_ENTITY_ID},
        blocking=True,
    )

    assert state_1.set.await_args_list == [
        call(HEADPHONES_OVERRIDE, True),
        call(HEADPHONES_OVERRIDE, False),
    ]


@pytest.mark.parametrize("device_model", ["PA240"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_model_support(hass: HomeAssistant) -> None:
    """Test switches are created only for supported models."""
    for entity_id in ENTITY_IDS.values():
        assert hass.states.get(entity_id) is None
    assert hass.states.get(HEADPHONES_OVERRIDE_ENTITY_ID) is None


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_zone_support(hass: HomeAssistant) -> None:
    """Test switches are created only in supported zones."""
    assert {
        state.entity_id
        for state in hass.states.async_all(SWITCH_DOMAIN)
        if "_zone_2_" in state.entity_id
    } == {"switch.arcam_fmj_127_0_0_1_zone_2_headphone_override"}
