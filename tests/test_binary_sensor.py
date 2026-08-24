"""Tests for Arcam FMJ binary sensor entities."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from arcam.fmj.commands import (
    DC_OFFSET,
    HEADPHONES,
    INPUT_DETECT,
    INCOMING_VIDEO_PARAMETERS,
    SHORT_CIRCUIT_STATUS,
)
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Limit platform setup to binary_sensor only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the binary sensor platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_none(
    hass: HomeAssistant,
) -> None:
    """Test binary sensor when video parameters are None."""
    state = hass.states.get(
        "binary_sensor.arcam_fmj_127_0_0_1_incoming_video_interlaced"
    )
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_interlaced(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test binary sensor reports on when video is interlaced."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.command_values[INCOMING_VIDEO_PARAMETERS] = video_params

    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.arcam_fmj_127_0_0_1_incoming_video_interlaced"
    )
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_not_interlaced(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test binary sensor reports off when video is not interlaced."""
    video_params = Mock()
    video_params.interlaced = False
    state_1.command_values[INCOMING_VIDEO_PARAMETERS] = video_params

    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.arcam_fmj_127_0_0_1_incoming_video_interlaced"
    )
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_amplifier_binary_sensors(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test amplifier status and fault binary sensors."""
    state_1.command_values.update(
        {
            HEADPHONES: True,
            DC_OFFSET: True,
            SHORT_CIRCUIT_STATUS: False,
            INPUT_DETECT: True,
        }
    )

    client.notify_data_updated()
    await hass.async_block_till_done()

    expected = {
        "headphones_connected": STATE_ON,
        "dc_offset_fault": STATE_ON,
        "short_circuit_fault": STATE_OFF,
        "active_input_detected": STATE_ON,
    }
    for key, value in expected.items():
        state = hass.states.get(f"binary_sensor.arcam_fmj_127_0_0_1_{key}")
        assert state is not None
        assert state.state == value

    assert (
        hass.states.get("binary_sensor.arcam_fmj_127_0_0_1_zone_2_headphones") is None
    )


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_model_support(hass: HomeAssistant) -> None:
    """Test binary sensors are created only for supported models."""
    assert (
        hass.states.get("binary_sensor.arcam_fmj_127_0_0_1_headphones_connected")
        is not None
    )
    assert hass.states.get("binary_sensor.arcam_fmj_127_0_0_1_dc_offset_fault") is None
