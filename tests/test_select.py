"""Tests for Arcam FMJ select entities."""

from collections.abc import Generator
from unittest.mock import Mock, call, patch

from arcam.fmj.codecs import (
    AutoShutdown,
    CompressionMode,
    DabDisplayInfoType,
    DisplayInfoType,
    DisplayBrightness,
    DolbyAudioMode,
    FmDisplayInfoType,
    HdmiOutput,
    ImaxEnhancedMode,
    NetworkDisplayInfoType,
    RoomEqMode,
    SourceCodes,
    VideoFilmMode,
    VideoNoiseReduction,
    VideoSelection,
)
from arcam.fmj.commands import (
    AUTO_SHUTDOWN_CONTROL,
    COMPRESSION,
    DISPLAY_BRIGHTNESS,
    DISPLAY_INFO_TYPE,
    DOLBY_AUDIO,
    IMAX_ENHANCED,
    ROOM_EQUALIZATION,
    ROOM_EQ_NAMES,
    VIDEO_FILM_MODE,
    VIDEO_MPEG_NOISE_REDUCTION,
    VIDEO_NOISE_REDUCTION,
    VIDEO_OUTPUT_SWITCHING,
    VIDEO_SELECTION,
    ReadWriteCommand,
)
from arcam.fmj.models import IntOrTypeEnum
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)

ENTITY_IDS = {
    DISPLAY_BRIGHTNESS: "select.arcam_fmj_127_0_0_1_front_panel_display_brightness",
    DISPLAY_INFO_TYPE: "select.arcam_fmj_127_0_0_1_vfd_information",
    VIDEO_SELECTION: "select.arcam_fmj_127_0_0_1_legacy_video_selection",
    IMAX_ENHANCED: "select.arcam_fmj_127_0_0_1_imax_enhanced_mode",
    ROOM_EQUALIZATION: "select.arcam_fmj_127_0_0_1_room_equalization",
    DOLBY_AUDIO: "select.arcam_fmj_127_0_0_1_dolby_audio_mode",
    COMPRESSION: "select.arcam_fmj_127_0_0_1_dynamic_range_compression",
    VIDEO_FILM_MODE: "select.arcam_fmj_127_0_0_1_video_film_mode",
    VIDEO_NOISE_REDUCTION: "select.arcam_fmj_127_0_0_1_video_noise_reduction",
    VIDEO_MPEG_NOISE_REDUCTION: "select.arcam_fmj_127_0_0_1_mpeg_noise_reduction",
    VIDEO_OUTPUT_SWITCHING: "select.arcam_fmj_127_0_0_1_hdmi_output",
    AUTO_SHUTDOWN_CONTROL: "select.arcam_fmj_127_0_0_1_auto_shutdown_interval",
}

AVR450_COMMANDS = {
    DISPLAY_BRIGHTNESS,
    DISPLAY_INFO_TYPE,
    VIDEO_SELECTION,
    DOLBY_AUDIO,
    COMPRESSION,
    VIDEO_FILM_MODE,
    VIDEO_NOISE_REDUCTION,
    VIDEO_MPEG_NOISE_REDUCTION,
    VIDEO_OUTPUT_SWITCHING,
    ROOM_EQUALIZATION,
}
AVR20_COMMANDS = {
    DISPLAY_BRIGHTNESS,
    DISPLAY_INFO_TYPE,
    IMAX_ENHANCED,
    DOLBY_AUDIO,
    COMPRESSION,
    VIDEO_OUTPUT_SWITCHING,
    ROOM_EQUALIZATION,
}
SA20_COMMANDS = {DISPLAY_BRIGHTNESS, AUTO_SHUTDOWN_CONTROL}


@pytest.fixture(autouse=True)
def select_only() -> Generator[None]:
    """Limit platform setup to select only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.parametrize("device_model", ["AVR450", "AVR20", "SA20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshots of the select platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_model", "command", "value"),
    [
        ("AVR450", DISPLAY_BRIGHTNESS, DisplayBrightness.L2),
        ("AVR450", VIDEO_SELECTION, VideoSelection.PVR),
        ("AVR20", IMAX_ENHANCED, ImaxEnhancedMode.AUTO),
        ("AVR20", DOLBY_AUDIO, DolbyAudioMode.NIGHT),
        ("AVR450", COMPRESSION, CompressionMode.HIGH),
        ("AVR450", VIDEO_FILM_MODE, VideoFilmMode.OFF),
        ("AVR450", VIDEO_NOISE_REDUCTION, VideoNoiseReduction.LOW),
        ("AVR450", VIDEO_MPEG_NOISE_REDUCTION, VideoNoiseReduction.MEDIUM),
        ("AVR450", VIDEO_OUTPUT_SWITCHING, HdmiOutput.OUT_1_2),
        ("SA20", AUTO_SHUTDOWN_CONTROL, AutoShutdown.HOURS_2),
    ],
    indirect=["device_model"],
)
@pytest.mark.usefixtures("player_setup")
async def test_read_and_write(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
    command: ReadWriteCommand[IntOrTypeEnum],
    value: IntOrTypeEnum,
) -> None:
    """Test reading and writing direct selects."""
    state_1.command_values[command] = value
    client.notify_data_updated()
    await hass.async_block_till_done()

    entity_id = ENTITY_IDS[command]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == value.name.lower()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: value.name.lower()},
        blocking=True,
    )

    state_1.set.assert_awaited_once_with(command, value)


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_display_info_type(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test source-dependent VFD information choices."""
    entity_id = ENTITY_IDS[DISPLAY_INFO_TYPE]
    cases = (
        (
            SourceCodes.BD,
            DisplayInfoType.PROCESSING,
            "processing",
            ["processing"],
        ),
        (
            SourceCodes.FM,
            FmDisplayInfoType.PROGRAMME_TYPE,
            "programme_type",
            ["processing", "radio_text", "programme_type", "signal_strength"],
        ),
        (
            SourceCodes.DAB,
            DabDisplayInfoType.BIT_RATE,
            "bit_rate",
            [
                "processing",
                "radio_text",
                "genre",
                "signal_quality",
                "bit_rate",
            ],
        ),
        (
            SourceCodes.NET,
            NetworkDisplayInfoType.ALBUM,
            "album",
            [
                "processing",
                "track",
                "artist",
                "album",
                "audio_type",
                "sample_rate",
            ],
        ),
        (
            SourceCodes.USB,
            NetworkDisplayInfoType.SAMPLE_RATE,
            "sample_rate",
            [
                "processing",
                "track",
                "artist",
                "album",
                "audio_type",
                "sample_rate",
            ],
        ),
        (
            SourceCodes.NET_USB,
            NetworkDisplayInfoType.TRACK,
            "track",
            [
                "processing",
                "track",
                "artist",
                "album",
                "audio_type",
                "sample_rate",
            ],
        ),
    )

    for source, value, current_option, options in cases:
        state_1.get_source.return_value = source
        state_1.command_values[DISPLAY_INFO_TYPE] = value
        client.notify_data_updated()
        await hass.async_block_till_done()

        entity_state = hass.states.get(entity_id)
        assert entity_state is not None
        assert entity_state.state == current_option
        assert entity_state.attributes["options"] == options

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: current_option},
            blocking=True,
        )

    assert state_1.set.await_args_list == [
        call(DISPLAY_INFO_TYPE, value) for _, value, _, _ in cases
    ]


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_room_equalization_names(
    hass: HomeAssistant,
    state_1: State,
    state_2: State,
    client: Mock,
) -> None:
    """Test configured Room EQ names and the read-only state."""
    state_1.command_values.update(
        {
            ROOM_EQ_NAMES: ["Movie", "Music", "Night"],
            ROOM_EQUALIZATION: RoomEqMode.EQ2,
        }
    )
    state_2.command_values[ROOM_EQUALIZATION] = RoomEqMode.EQ3
    client.notify_data_updated()
    await hass.async_block_till_done()

    entity_id = ENTITY_IDS[ROOM_EQUALIZATION]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == "Music"
    assert entity_state.attributes["options"] == ["off", "Movie", "Music", "Night"]

    zone_2_state = hass.states.get(
        "select.arcam_fmj_127_0_0_1_zone_2_room_equalization"
    )
    assert zone_2_state is not None
    assert zone_2_state.state == "Night"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Movie"},
        blocking=True,
    )
    state_1.set.assert_awaited_once_with(ROOM_EQUALIZATION, RoomEqMode.EQ1)

    state_1.command_values[ROOM_EQUALIZATION] = RoomEqMode.NOT_CALCULATED
    client.notify_data_updated()
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == "not_calculated"
    assert entity_state.attributes["options"] == [
        "off",
        "Movie",
        "Music",
        "Night",
        "not_calculated",
    ]

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "not_calculated"},
            blocking=True,
        )


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_room_equalization_fallback_names(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test Room EQ fallback names when configured names are unavailable."""
    state_1.command_values[ROOM_EQUALIZATION] = RoomEqMode.EQ1
    client.notify_data_updated()
    await hass.async_block_till_done()

    entity_state = hass.states.get(ENTITY_IDS[ROOM_EQUALIZATION])
    assert entity_state is not None
    assert entity_state.state == "eq1"
    assert entity_state.attributes["options"] == ["off", "eq1", "eq2", "eq3"]


@pytest.mark.parametrize(
    ("device_model", "expected_commands"),
    [
        ("AVR450", AVR450_COMMANDS),
        ("AVR20", AVR20_COMMANDS),
        ("SA20", SA20_COMMANDS),
    ],
    indirect=["device_model"],
)
@pytest.mark.usefixtures("player_setup")
async def test_model_support(
    hass: HomeAssistant,
    expected_commands: set[ReadWriteCommand[IntOrTypeEnum]],
) -> None:
    """Test selects are created only for supported models."""
    for command, entity_id in ENTITY_IDS.items():
        assert (hass.states.get(entity_id) is not None) == (
            command in expected_commands
        )


@pytest.mark.parametrize(
    ("device_model", "command", "expected_options"),
    [
        ("AVR450", DOLBY_AUDIO, ["off", "movie"]),
        ("AVR20", DOLBY_AUDIO, ["off", "movie", "music", "night"]),
        (
            "SA20",
            AUTO_SHUTDOWN_CONTROL,
            ["disabled", "minutes_30", "hour_1", "hours_2", "hours_4"],
        ),
        (
            "SA30",
            AUTO_SHUTDOWN_CONTROL,
            [
                "disabled",
                "minutes_20",
                "minutes_30",
                "hour_1",
                "hours_2",
                "hours_4",
            ],
        ),
    ],
    indirect=["device_model"],
)
@pytest.mark.usefixtures("player_setup")
async def test_model_options(
    hass: HomeAssistant,
    command: ReadWriteCommand[IntOrTypeEnum],
    expected_options: list[str],
) -> None:
    """Test select options are filtered for the model."""
    entity_state = hass.states.get(ENTITY_IDS[command])
    assert entity_state is not None
    assert entity_state.attributes["options"] == expected_options


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_zone_support(hass: HomeAssistant) -> None:
    """Test selects are created only in supported zones."""
    entity_ids = {state.entity_id for state in hass.states.async_all(SELECT_DOMAIN)}
    assert "select.arcam_fmj_127_0_0_1_zone_2_dolby_audio_mode" in entity_ids
    assert "select.arcam_fmj_127_0_0_1_zone_2_vfd_information" in entity_ids
    assert "select.arcam_fmj_127_0_0_1_zone_2_dynamic_range_compression" in entity_ids
    assert "select.arcam_fmj_127_0_0_1_zone_2_room_equalization" in entity_ids
    assert not any(
        entity_id.startswith(
            "select.arcam_fmj_127_0_0_1_zone_2_front_panel_display_brightness"
        )
        for entity_id in entity_ids
    )
