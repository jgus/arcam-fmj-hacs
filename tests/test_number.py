"""Tests for Arcam FMJ number entities."""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

from arcam.fmj.commands import (
    BALANCE,
    BASS_EQUALIZATION,
    DOLBY_PLIIX_CENTRE_WIDTH,
    DOLBY_VOLUME_CALIBRATION_OFFSET,
    LIPSYNC_DELAY,
    MAX_STREAMING_VOLUME,
    MAX_TURN_ON_VOLUME,
    MAX_VOLUME,
    PROCESSOR_MODE_VOLUME,
    SUB_STEREO_TRIM,
    SUBWOOFER_TRIM,
    TREBLE_EQUALIZATION,
    VIDEO_BRIGHTNESS,
    VIDEO_COLOUR,
    VIDEO_CONTRAST,
    VIDEO_EDGE_ENHANCEMENT,
    ReadWriteCommand,
)
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfSoundPressure,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)

ENTITY_IDS = {
    TREBLE_EQUALIZATION: "number.arcam_fmj_127_0_0_1_treble",
    BASS_EQUALIZATION: "number.arcam_fmj_127_0_0_1_bass",
    DOLBY_VOLUME_CALIBRATION_OFFSET: (
        "number.arcam_fmj_127_0_0_1_dolby_volume_calibration_offset"
    ),
    BALANCE: "number.arcam_fmj_127_0_0_1_balance",
    DOLBY_PLIIX_CENTRE_WIDTH: ("number.arcam_fmj_127_0_0_1_dolby_pliix_center_width"),
    SUBWOOFER_TRIM: "number.arcam_fmj_127_0_0_1_subwoofer_trim",
    LIPSYNC_DELAY: "number.arcam_fmj_127_0_0_1_lip_sync_delay",
    SUB_STEREO_TRIM: "number.arcam_fmj_127_0_0_1_sub_stereo_trim",
    VIDEO_BRIGHTNESS: "number.arcam_fmj_127_0_0_1_legacy_video_brightness",
    VIDEO_CONTRAST: "number.arcam_fmj_127_0_0_1_legacy_video_contrast",
    VIDEO_COLOUR: "number.arcam_fmj_127_0_0_1_legacy_video_colour",
    VIDEO_EDGE_ENHANCEMENT: (
        "number.arcam_fmj_127_0_0_1_legacy_video_edge_enhancement"
    ),
    PROCESSOR_MODE_VOLUME: "number.arcam_fmj_127_0_0_1_processor_mode_volume",
    MAX_TURN_ON_VOLUME: "number.arcam_fmj_127_0_0_1_maximum_turn_on_volume",
    MAX_VOLUME: "number.arcam_fmj_127_0_0_1_maximum_volume",
    MAX_STREAMING_VOLUME: "number.arcam_fmj_127_0_0_1_maximum_streaming_volume",
}

NUMBER_CASES = [
    (
        "AVR450",
        TREBLE_EQUALIZATION,
        3.0,
        -12,
        12,
        1,
        UnitOfSoundPressure.DECIBEL,
    ),
    (
        "AVR450",
        BASS_EQUALIZATION,
        -2.0,
        -12,
        12,
        1,
        UnitOfSoundPressure.DECIBEL,
    ),
    (
        "AVR450",
        DOLBY_VOLUME_CALIBRATION_OFFSET,
        -5.0,
        -15,
        15,
        1,
        UnitOfSoundPressure.DECIBEL,
    ),
    ("SA20", BALANCE, 2.0, -6, 6, 1, UnitOfSoundPressure.DECIBEL),
    ("AVR450", DOLBY_PLIIX_CENTRE_WIDTH, 5, 0, 7, 1, None),
    (
        "AVR450",
        SUBWOOFER_TRIM,
        0.5,
        -10,
        10,
        0.5,
        UnitOfSoundPressure.DECIBEL,
    ),
    ("AVR450", LIPSYNC_DELAY, 25.0, 0, 250, 5, UnitOfTime.MILLISECONDS),
    (
        "AVR450",
        SUB_STEREO_TRIM,
        -2.5,
        -10,
        0,
        0.5,
        UnitOfSoundPressure.DECIBEL,
    ),
    ("AVR450", VIDEO_BRIGHTNESS, 10.0, -50, 50, 1, None),
    ("AVR450", VIDEO_CONTRAST, -10.0, -50, 50, 1, None),
    ("AVR450", VIDEO_COLOUR, 5.0, -50, 50, 1, None),
    ("AVR450", VIDEO_EDGE_ENHANCEMENT, 20, 0, 50, 1, None),
    ("SA20", PROCESSOR_MODE_VOLUME, 40, 0, 99, 1, None),
    ("SA30", MAX_TURN_ON_VOLUME, 60, 0, 99, 1, None),
    ("SA30", MAX_VOLUME, 70, 0, 99, 1, None),
    ("SA30", MAX_STREAMING_VOLUME, 50, 0, 99, 1, None),
]

AVR450_COMMANDS = {
    TREBLE_EQUALIZATION,
    BASS_EQUALIZATION,
    DOLBY_VOLUME_CALIBRATION_OFFSET,
    BALANCE,
    DOLBY_PLIIX_CENTRE_WIDTH,
    SUBWOOFER_TRIM,
    LIPSYNC_DELAY,
    SUB_STEREO_TRIM,
    VIDEO_BRIGHTNESS,
    VIDEO_CONTRAST,
    VIDEO_COLOUR,
    VIDEO_EDGE_ENHANCEMENT,
}
AVR20_COMMANDS = {
    TREBLE_EQUALIZATION,
    BASS_EQUALIZATION,
    DOLBY_VOLUME_CALIBRATION_OFFSET,
    BALANCE,
    SUBWOOFER_TRIM,
    LIPSYNC_DELAY,
    SUB_STEREO_TRIM,
}
SA20_COMMANDS = {BALANCE, PROCESSOR_MODE_VOLUME}
SA30_COMMANDS = {
    BALANCE,
    PROCESSOR_MODE_VOLUME,
    MAX_TURN_ON_VOLUME,
    MAX_VOLUME,
    MAX_STREAMING_VOLUME,
}


@pytest.fixture(autouse=True)
def number_only() -> Generator[None]:
    """Limit platform setup to number only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.parametrize("device_model", ["AVR450", "SA30"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshots of the number platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_model", "command", "value", "minimum", "maximum", "step", "unit"),
    NUMBER_CASES,
    indirect=["device_model"],
)
@pytest.mark.usefixtures("player_setup")
async def test_read_and_write(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
    command: ReadWriteCommand[Any],
    value: int | float,
    minimum: float,
    maximum: float,
    step: float,
    unit: str | None,
) -> None:
    """Test reading and writing direct numbers."""
    state_1.command_values[command] = value
    client.notify_data_updated()
    await hass.async_block_till_done()

    entity_id = ENTITY_IDS[command]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert float(entity_state.state) == value
    assert entity_state.attributes["min"] == minimum
    assert entity_state.attributes["max"] == maximum
    assert entity_state.attributes["step"] == step
    assert entity_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    state_1.set.assert_awaited_once_with(command, value)


@pytest.mark.parametrize(
    ("device_model", "expected_commands"),
    [
        ("AVR450", AVR450_COMMANDS),
        ("AVR20", AVR20_COMMANDS),
        ("SA20", SA20_COMMANDS),
        ("SA30", SA30_COMMANDS),
    ],
    indirect=["device_model"],
)
@pytest.mark.usefixtures("player_setup")
async def test_model_support(
    hass: HomeAssistant,
    expected_commands: set[ReadWriteCommand[Any]],
) -> None:
    """Test numbers are created only for supported models."""
    for command, entity_id in ENTITY_IDS.items():
        assert (hass.states.get(entity_id) is not None) == (
            command in expected_commands
        )


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_zone_support(hass: HomeAssistant) -> None:
    """Test numbers are created only in supported zones."""
    zone_2_entity_ids = {
        state.entity_id
        for state in hass.states.async_all(NUMBER_DOMAIN)
        if "_zone_2_" in state.entity_id
    }
    assert zone_2_entity_ids == {
        "number.arcam_fmj_127_0_0_1_zone_2_balance",
        "number.arcam_fmj_127_0_0_1_zone_2_bass",
        "number.arcam_fmj_127_0_0_1_zone_2_dolby_volume_calibration_offset",
        "number.arcam_fmj_127_0_0_1_zone_2_lip_sync_delay",
        "number.arcam_fmj_127_0_0_1_zone_2_subwoofer_trim",
        "number.arcam_fmj_127_0_0_1_zone_2_treble",
    }
