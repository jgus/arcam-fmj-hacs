"""Tests for Arcam FMJ sensor entities."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from arcam.fmj.codecs import (
    IncomingAudioConfig,
    IncomingAudioFormat,
    IncomingVideoAspectRatio,
    IncomingVideoColorspace,
    MenuCodes,
    SourceCodes,
    TemperatureSensor,
)
from arcam.fmj.commands import (
    FM_GENRE,
    INCOMING_AUDIO_SAMPLE_RATE,
    INCOMING_VIDEO_PARAMETERS,
    LIFTER_TEMPERATURE,
    MENU,
    OUTPUT_TEMPERATURE,
)
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Limit platform setup to sensor only."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the sensor platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("player_setup")
async def test_sensor_video_parameters(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test video parameter sensors with actual data."""
    video_params = Mock()
    video_params.horizontal_resolution = 1920
    video_params.vertical_resolution = 1080
    video_params.refresh_rate = 60.0
    video_params.aspect_ratio = IncomingVideoAspectRatio.ASPECT_16_9
    video_params.colorspace = IncomingVideoColorspace.HDR10

    state_1.command_values[INCOMING_VIDEO_PARAMETERS] = video_params
    client.notify_data_updated()
    await hass.async_block_till_done()

    expected = {
        "incoming_video_horizontal_resolution": "1920",
        "incoming_video_vertical_resolution": "1080",
        "incoming_video_refresh_rate": "60.0",
        "incoming_video_aspect_ratio": "aspect_16_9",
        "incoming_video_colorspace": "hdr10",
    }
    for key, value in expected.items():
        state = hass.states.get(f"sensor.arcam_fmj_127_0_0_1_{key}")
        assert state is not None, f"State missing for {key}"
        assert state.state == value, f"Expected {value} for {key}, got {state.state}"


@pytest.mark.usefixtures("player_setup")
async def test_sensor_audio_parameters(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test audio parameter sensors with actual data."""
    state_1.get_incoming_audio_format.return_value = (
        IncomingAudioFormat.PCM,
        IncomingAudioConfig.STEREO_ONLY,
    )
    state_1.command_values[INCOMING_AUDIO_SAMPLE_RATE] = 48000

    client.notify_data_updated()
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_format").state
        == "pcm"
    )
    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_configuration").state
        == "stereo_only"
    )
    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_sample_rate").state
        == "48000"
    )


@pytest.mark.usefixtures("player_setup")
async def test_sensor_enum_unknown(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test parameter sensors with unknown data."""
    video_params = Mock()
    video_params.horizontal_resolution = 0
    video_params.vertical_resolution = 0
    video_params.refresh_rate = 0
    video_params.aspect_ratio = IncomingVideoAspectRatio.from_int(0x99)
    video_params.colorspace = IncomingVideoColorspace.from_int(0x99)

    state_1.command_values[INCOMING_VIDEO_PARAMETERS] = video_params
    state_1.get_incoming_audio_format.return_value = (
        None,
        IncomingAudioConfig.from_int(0x99),
    )

    client.notify_data_updated()
    await hass.async_block_till_done()

    def _get(key: str) -> str:
        state = hass.states.get(f"sensor.arcam_fmj_127_0_0_1_{key}")
        assert state
        return state.state

    assert _get("incoming_audio_format") == "unknown"
    assert _get("incoming_audio_configuration") == "unknown"
    assert _get("incoming_video_aspect_ratio") == "unknown"
    assert _get("incoming_video_colorspace") == "unknown"


@pytest.mark.usefixtures("player_setup")
async def test_fm_genre_and_menu(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test FM genre and menu sensor values."""
    state_1.get_source.return_value = SourceCodes.FM
    state_1.command_values[FM_GENRE] = "Rock"
    state_1.command_values[MENU] = MenuCodes.TUNER

    client.notify_data_updated()
    await hass.async_block_till_done()

    genre = hass.states.get("sensor.arcam_fmj_127_0_0_1_fm_genre")
    menu = hass.states.get("sensor.arcam_fmj_127_0_0_1_menu")
    assert genre is not None
    assert genre.state == "Rock"
    assert menu is not None
    assert menu.state == "tuner"

    state_1.get_source.return_value = SourceCodes.DAB
    client.notify_data_updated()
    await hass.async_block_till_done()

    genre = hass.states.get("sensor.arcam_fmj_127_0_0_1_fm_genre")
    assert genre is not None
    assert genre.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_sensor_zone_support(hass: HomeAssistant) -> None:
    """Test command zone metadata filters sensor creation."""
    assert hass.states.get("sensor.arcam_fmj_127_0_0_1_zone_2_fm_genre") is not None
    assert hass.states.get("sensor.arcam_fmj_127_0_0_1_zone_2_menu") is None


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_temperature_sensors(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test amplifier temperature sensors."""
    state_1.command_values[LIFTER_TEMPERATURE] = 42
    state_1.command_values[OUTPUT_TEMPERATURE] = 51

    client.notify_data_updated()
    await hass.async_block_till_done()

    expected = {
        "lifter_temperature_1": "42",
        "output_stage_temperature_1": "51",
    }
    for key, value in expected.items():
        state = hass.states.get(f"sensor.arcam_fmj_127_0_0_1_{key}")
        assert state is not None
        assert state.state == value
        assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_zone_2_lifter_temperature_1")
        is None
    )


@pytest.mark.parametrize("device_model", ["PA240"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_lifter_temperature_sensor_2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    """Test coordinator polling for the second lifter temperature sensor."""
    state_1.get_lifter_temperature.reset_mock()
    state_1.get_lifter_temperature.return_value = 43

    coordinator = mock_config_entry.runtime_data.coordinators[1]
    await coordinator.async_refresh()

    state_1.get_lifter_temperature.assert_awaited_once_with(TemperatureSensor.SENSOR_2)
    state = hass.states.get("sensor.arcam_fmj_127_0_0_1_lifter_temperature_2")
    assert state is not None
    assert state.state == "43"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_lifter_temperature_sensor_2_model_support(
    hass: HomeAssistant,
) -> None:
    """Test the second lifter sensor is limited to multi-sensor models."""
    assert hass.states.get("sensor.arcam_fmj_127_0_0_1_lifter_temperature_2") is None


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_sensor_model_support(hass: HomeAssistant) -> None:
    """Test sensors are created only for supported models."""
    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_sample_rate")
        is not None
    )
    assert (
        hass.states.get(
            "sensor.arcam_fmj_127_0_0_1_incoming_video_horizontal_resolution"
        )
        is None
    )


@pytest.mark.parametrize("device_model", ["PA410"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_output_temperature_sensor_2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    """Test coordinator polling for the second output temperature sensor."""
    state_1.get_output_temperature.reset_mock()
    state_1.get_output_temperature.return_value = 52

    coordinator = mock_config_entry.runtime_data.coordinators[1]
    await coordinator.async_refresh()

    state_1.get_output_temperature.assert_awaited_once_with(TemperatureSensor.SENSOR_2)
    state = hass.states.get("sensor.arcam_fmj_127_0_0_1_output_stage_temperature_2")
    assert state is not None
    assert state.state == "52"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    assert hass.states.get("sensor.arcam_fmj_127_0_0_1_lifter_temperature_2") is None


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_output_temperature_sensor_2_model_support(
    hass: HomeAssistant,
) -> None:
    """Test the second output sensor is limited to multi-sensor models."""
    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_output_stage_temperature_2") is None
    )
