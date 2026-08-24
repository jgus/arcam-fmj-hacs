"""Tests for arcam fmj receivers."""

from collections.abc import Generator
from math import isclose
from unittest.mock import Mock, PropertyMock, patch

from arcam.fmj.codecs import (
    BluetoothAudioStatus,
    DecodeMode2CH,
    DecodeModeMCH,
    NetworkPlaybackStatus,
    NowPlayingEncoder,
    NowPlayingInfo,
    SourceCodes,
)
from arcam.fmj.commands import (
    CURRENT_SOURCE,
    DAB_STATION,
    DLS_PDT,
    FM_GENRE,
    MUTE,
    NETWORK_PLAYBACK_STATUS,
    POWER,
    RDS_INFORMATION,
    TUNER_PRESET,
    VOLUME,
)
from arcam.fmj.errors import ConnectionFailed, NotConnectedException
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from custom_components.arcam_fmj.media_player import (
    ATTR_MEDIA_CODEC,
    ATTR_MEDIA_ENCODER,
    ATTR_MEDIA_GENRE,
    ATTR_MEDIA_SAMPLE_RATE,
    ArcamFmj,
)
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.media_player import (
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State as CoreState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from conftest import MOCK_ENTITY_ID

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def platform_fixture() -> Generator[None]:
    """Only test single platform."""
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.MEDIA_PLAYER]):
        yield


@pytest.mark.usefixtures("player_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup creates expected entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_supported_features_by_model(hass: HomeAssistant) -> None:
    """Test media player features use command model metadata."""
    state = hass.states.get(MOCK_ENTITY_ID)
    assert state is not None
    features = MediaPlayerEntityFeature(state.attributes["supported_features"])
    assert features & MediaPlayerEntityFeature.SELECT_SOURCE
    assert features & MediaPlayerEntityFeature.VOLUME_SET
    assert features & MediaPlayerEntityFeature.VOLUME_MUTE
    assert not features & MediaPlayerEntityFeature.PLAY_MEDIA
    assert not features & MediaPlayerEntityFeature.SELECT_SOUND_MODE


@pytest.mark.usefixtures("player_setup")
async def test_source_gated_features(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
) -> None:
    """Test source-specific controls are unavailable outside their source."""
    state_1.get_source.return_value = SourceCodes.DAB
    state = await update(hass, client, MOCK_ENTITY_ID)
    features = MediaPlayerEntityFeature(state.attributes["supported_features"])
    assert not features & MediaPlayerEntityFeature.PLAY_MEDIA
    assert not features & MediaPlayerEntityFeature.BROWSE_MEDIA

    state_1.get_source.return_value = SourceCodes.FM
    state = await update(hass, client, MOCK_ENTITY_ID)
    features = MediaPlayerEntityFeature(state.attributes["supported_features"])
    assert features & MediaPlayerEntityFeature.PLAY_MEDIA
    assert features & MediaPlayerEntityFeature.BROWSE_MEDIA


@pytest.mark.usefixtures("player_setup")
async def test_disconnect(hass: HomeAssistant, client: Mock) -> None:
    """Test a disconnection is detected."""
    data = hass.states.get(MOCK_ENTITY_ID)
    assert data
    assert data.state != STATE_UNAVAILABLE

    client.notify_connection(ConnectionFailed())
    await hass.async_block_till_done()

    data = hass.states.get(MOCK_ENTITY_ID)
    assert data
    assert data.state == STATE_UNAVAILABLE


async def update(hass: HomeAssistant, client: Mock, entity_id: str) -> CoreState:
    """Force a update of player and return current state data."""
    client.notify_data_updated()
    await hass.async_block_till_done()
    data = hass.states.get(entity_id)
    assert data
    return data


@pytest.mark.usefixtures("player_setup")
async def test_powered_off(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test properties in powered off state."""
    state_1.get_source.return_value = None
    state_1.command_values[POWER] = False

    data = await update(hass, client, MOCK_ENTITY_ID)
    assert "source" not in data.attributes
    assert data.state == "off"


@pytest.mark.usefixtures("player_setup")
async def test_power_unknown(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test that an unreported power state surfaces as unknown, not off."""
    state_1.get_source.return_value = None
    state_1.command_values[POWER] = None

    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.state == "unknown"


@pytest.mark.usefixtures("player_setup")
async def test_powered_on(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test properties in powered on state."""
    state_1.get_source.return_value = SourceCodes.PVR
    state_1.command_values[POWER] = True

    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes["source"] == "PVR"
    assert data.state == "on"


@pytest.mark.parametrize(
    ("playback_status", "expected_state"),
    [
        (NetworkPlaybackStatus.STOPPED, "idle"),
        (NetworkPlaybackStatus.TRANSITIONING, "buffering"),
        (NetworkPlaybackStatus.PLAYING, "playing"),
        (NetworkPlaybackStatus.PAUSED, "paused"),
        (None, "on"),
    ],
)
@pytest.mark.parametrize(
    "source", [SourceCodes.NET, SourceCodes.USB, SourceCodes.NET_USB]
)
@pytest.mark.usefixtures("player_setup")
async def test_network_playback_state(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    source: SourceCodes,
    playback_status: NetworkPlaybackStatus | None,
    expected_state: str,
) -> None:
    """Test network playback state mapping."""
    state_1.get_source.return_value = source
    state_1.command_values[NETWORK_PLAYBACK_STATUS] = playback_status

    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.state == expected_state


@pytest.mark.usefixtures("player_setup")
async def test_network_playback_state_is_source_gated(
    hass: HomeAssistant, client: Mock, state_1: State
) -> None:
    """Test stale network playback state is hidden on other sources."""
    state_1.get_source.return_value = SourceCodes.PVR
    state_1.command_values[NETWORK_PLAYBACK_STATUS] = NetworkPlaybackStatus.PLAYING

    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.state == "on"


@pytest.mark.parametrize(
    ("playback_status", "expected_state"),
    [
        (BluetoothAudioStatus.NO_CONNECTION, "idle"),
        (BluetoothAudioStatus.PAUSED, "paused"),
        (BluetoothAudioStatus.PLAYING_SBC, "playing"),
        (BluetoothAudioStatus.PLAYING_AAC, "playing"),
        (BluetoothAudioStatus.PLAYING_APTX, "playing"),
        (BluetoothAudioStatus.PLAYING_APTX_HD, "playing"),
        (None, "on"),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_bluetooth_playback_state(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    playback_status: BluetoothAudioStatus | None,
    expected_state: str,
) -> None:
    """Test Bluetooth playback state mapping."""
    state_1.get_source.return_value = SourceCodes.BT
    state_1.get_bluetooth_status.return_value = playback_status, "Track"

    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.state == expected_state


@pytest.mark.usefixtures("player_setup")
async def test_bluetooth_playback_state_is_source_gated(
    hass: HomeAssistant, client: Mock, state_1: State
) -> None:
    """Test stale Bluetooth playback state is hidden on other sources."""
    state_1.get_source.return_value = SourceCodes.BT
    state_1.get_bluetooth_status.return_value = (
        BluetoothAudioStatus.PLAYING_AAC,
        "Track",
    )
    bluetooth_data = await update(hass, client, MOCK_ENTITY_ID)
    assert bluetooth_data.state == "playing"

    state_1.get_source.return_value = SourceCodes.PVR
    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.state == "on"


@pytest.mark.usefixtures("player_setup")
async def test_powered_off_ignores_network_playback_state(
    hass: HomeAssistant, client: Mock, state_1: State
) -> None:
    """Test power state takes precedence over network playback state."""
    state_1.get_source.return_value = SourceCodes.NET
    state_1.command_values[POWER] = False
    state_1.command_values[NETWORK_PLAYBACK_STATUS] = NetworkPlaybackStatus.PLAYING

    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.state == "off"


@pytest.mark.usefixtures("player_setup")
async def test_turn_on(hass: HomeAssistant, state_1: State) -> None:
    """Test turn on service."""
    state_1.command_values[POWER] = None
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.set.assert_not_called()

    state_1.command_values[POWER] = False
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.set.assert_called_with(POWER, True)


@pytest.mark.usefixtures("player_setup")
async def test_turn_off(hass: HomeAssistant, state_1: State) -> None:
    """Test command to turn off."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.set.assert_called_with(POWER, False)


@pytest.mark.parametrize("mute", [True, False])
@pytest.mark.usefixtures("player_setup")
async def test_mute_volume(hass: HomeAssistant, state_1: State, mute: bool) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: mute},
        blocking=True,
    )
    state_1.set.assert_called_with(MUTE, mute)


@pytest.mark.usefixtures("player_setup")
async def test_update(hass: HomeAssistant, state_1: State) -> None:
    """Test update."""
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.update.assert_called_with()


@pytest.mark.parametrize(
    "update_exception",
    [ConnectionFailed, NotConnectedException],
)
@pytest.mark.usefixtures("player_setup")
async def test_update_lost(
    hass: HomeAssistant,
    state_1: State,
    caplog: pytest.LogCaptureFixture,
    update_exception: type[Exception],
) -> None:
    """Test update, with connection loss is ignored."""
    state_1.update.side_effect = update_exception()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.update.assert_called_with()


@pytest.mark.parametrize(
    ("source", "value"),
    [("PVR", SourceCodes.PVR), ("BD", SourceCodes.BD)],
)
@pytest.mark.usefixtures("player_setup")
async def test_select_valid_source(
    hass: HomeAssistant,
    state_1: State,
    source: str,
    value: SourceCodes,
) -> None:
    """Test selection of source."""
    await hass.services.async_call(
        "media_player",
        SERVICE_SELECT_SOURCE,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    state_1.set_source.assert_called_with(value)


@pytest.mark.usefixtures("player_setup")
async def test_select_invalid_source(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    """Test selection of source."""
    with pytest.raises(
        ServiceValidationError,
        check=lambda e: (
            e.translation_domain == "arcam_fmj"
            and e.translation_key == "unsupported_source"
        ),
    ):
        await hass.services.async_call(
            "media_player",
            SERVICE_SELECT_SOURCE,
            service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_INPUT_SOURCE: "INVALID"},
            blocking=True,
        )
    state_1.set_source.assert_not_called()


@pytest.mark.usefixtures("player_setup")
async def test_source_list(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test source list."""
    state_1.get_source_list.return_value = [SourceCodes.BD]
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes["source_list"] == ["BD"]


@pytest.mark.parametrize(
    "mode",
    [
        "STEREO",
        "DOLBY_PL",
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_select_sound_mode(
    hass: HomeAssistant, state_1: State, mode: str
) -> None:
    """Test selection sound mode."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_SOUND_MODE: mode},
        blocking=True,
    )
    state_1.set_decode_mode.assert_called_with(mode)


@pytest.mark.usefixtures("player_setup")
async def test_select_invalid_sound_mode(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    """Test selection of source."""
    state_1.set_decode_mode.side_effect = KeyError()
    with pytest.raises(
        ServiceValidationError,
        check=lambda e: (
            e.translation_domain == "arcam_fmj"
            and e.translation_key == "unsupported_sound_mode"
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_SOUND_MODE: "INVALID"},
            blocking=True,
        )


@pytest.mark.usefixtures("player_setup")
async def test_volume_up(hass: HomeAssistant, state_1: State) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.inc.assert_called_with(VOLUME)


@pytest.mark.usefixtures("player_setup")
async def test_volume_down(hass: HomeAssistant, state_1: State) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.dec.assert_called_with(VOLUME)


@pytest.mark.usefixtures("player_setup")
async def test_play_media(hass: HomeAssistant, state_1: State) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        service_data={
            ATTR_ENTITY_ID: MOCK_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "preset:1",
        },
        blocking=True,
    )
    state_1.set.assert_called_with(TUNER_PRESET, 1)


@pytest.mark.usefixtures("player_setup")
async def test_play_media_invalid(hass: HomeAssistant, state_1: State) -> None:
    """Test mute functionality."""
    with pytest.raises(
        ServiceValidationError,
        check=lambda e: (
            e.translation_domain == "arcam_fmj"
            and e.translation_key == "unsupported_media"
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            service_data={
                ATTR_ENTITY_ID: MOCK_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "invalid",
            },
            blocking=True,
        )
    state_1.set.assert_not_called()


async def test_browse_media_without_presets(state_1: State) -> None:
    coordinator = Mock()
    coordinator.state = state_1
    coordinator.device_info = {}
    coordinator.zone_unique_id = "zone-1"
    coordinator.device_name = "Arcam FMJ"
    state_1.get_preset_details.return_value = None

    result = await ArcamFmj(coordinator).async_browse_media()

    assert result.children == []


@pytest.mark.parametrize(
    ("mode", "mode_enum"),
    [
        ("STEREO", DecodeMode2CH.STEREO),
        ("STEREO_DOWNMIX", DecodeModeMCH.STEREO_DOWNMIX),
        (None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_sound_mode(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    mode: str | None,
    mode_enum: DecodeMode2CH | DecodeModeMCH | None,
) -> None:
    """Test selection sound mode."""
    state_1.get_decode_mode.return_value = mode_enum
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_SOUND_MODE) == mode


@pytest.mark.parametrize(
    ("modes", "modes_enum"),
    [
        (["STEREO", "DOLBY_PL"], [DecodeMode2CH.STEREO, DecodeMode2CH.DOLBY_PL]),
        (["STEREO_DOWNMIX"], [DecodeModeMCH.STEREO_DOWNMIX]),
        (None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_sound_mode_list(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    modes: list[str] | None,
    modes_enum: list[DecodeMode2CH] | list[DecodeModeMCH] | None,
) -> None:
    """Test sound mode list."""
    state_1.get_decode_modes.return_value = modes_enum
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_SOUND_MODE_LIST) == modes


@pytest.mark.usefixtures("player_setup")
async def test_is_volume_muted(
    hass: HomeAssistant, client: Mock, state_1: State
) -> None:
    """Test muted."""
    state_1.command_values[MUTE] = True
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True

    state_1.command_values[MUTE] = False
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False

    state_1.command_values[MUTE] = None
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is None


@pytest.mark.usefixtures("player_setup")
async def test_volume_level(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test volume."""
    state_1.command_values[VOLUME] = 0
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert isclose(data.attributes[ATTR_MEDIA_VOLUME_LEVEL], 0.0)

    state_1.command_values[VOLUME] = 50
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert isclose(data.attributes[ATTR_MEDIA_VOLUME_LEVEL], 50.0 / 99)

    state_1.command_values[VOLUME] = 99
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert isclose(data.attributes[ATTR_MEDIA_VOLUME_LEVEL], 1.0)

    state_1.command_values[VOLUME] = None
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert ATTR_MEDIA_VOLUME_LEVEL not in data.attributes


@pytest.mark.parametrize(("volume", "call"), [(0.0, 0), (0.5, 50), (1.0, 99)])
@pytest.mark.usefixtures("player_setup")
async def test_set_volume_level(
    hass: HomeAssistant, state_1: State, volume: float, call: int
) -> None:
    """Test setting volume."""
    await hass.services.async_call(
        "media_player",
        SERVICE_VOLUME_SET,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: volume},
        blocking=True,
    )

    state_1.set.assert_called_with(VOLUME, call)


@pytest.mark.parametrize(
    "set_exception",
    [ConnectionFailed, NotConnectedException],
)
@pytest.mark.usefixtures("player_setup")
async def test_set_volume_level_lost(
    hass: HomeAssistant,
    state_1: State,
    set_exception: type[Exception],
) -> None:
    """Test setting volume, with a lost connection."""

    state_1.set.side_effect = set_exception()

    with pytest.raises(
        HomeAssistantError,
        check=lambda e: (
            e.translation_domain == "arcam_fmj"
            and e.translation_key == "connection_failed"
        ),
    ):
        await hass.services.async_call(
            "media_player",
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.0},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("source", "media_content_type"),
    [
        (SourceCodes.DAB, MediaType.MUSIC),
        (SourceCodes.FM, MediaType.MUSIC),
        (SourceCodes.NET, MediaType.MUSIC),
        (SourceCodes.USB, MediaType.MUSIC),
        (SourceCodes.NET_USB, MediaType.MUSIC),
        (SourceCodes.BT, MediaType.MUSIC),
        (SourceCodes.PVR, None),
        (None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_media_content_type(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    source: SourceCodes | None,
    media_content_type: MediaType | None,
) -> None:
    """Test content type deduction."""
    state_1.get_source.return_value = source
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == media_content_type


@pytest.mark.parametrize(
    ("source", "dab", "rds", "channel"),
    [
        (SourceCodes.DAB, "dab", "rds", "dab"),
        (SourceCodes.DAB, None, None, None),
        (SourceCodes.FM, "dab", "rds", "rds"),
        (SourceCodes.FM, None, None, None),
        (SourceCodes.PVR, "dab", "rds", None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_media_channel(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    source: SourceCodes,
    dab: str | None,
    rds: str | None,
    channel: str | None,
) -> None:
    """Test media channel."""
    state_1.command_values[DAB_STATION] = dab
    state_1.command_values[RDS_INFORMATION] = rds
    state_1.get_source.return_value = source
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_CHANNEL) == channel


@pytest.mark.parametrize(
    ("source", "dls", "artist"),
    [
        (SourceCodes.DAB, "dls", "dls"),
        (SourceCodes.FM, "dls", None),
        (SourceCodes.DAB, None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_media_artist(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    source: SourceCodes,
    dls: str | None,
    artist: str | None,
) -> None:
    """Test media artist."""
    state_1.command_values[DLS_PDT] = dls
    state_1.get_source.return_value = source
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_ARTIST) == artist


@pytest.mark.parametrize(
    ("source", "channel", "title"),
    [
        (SourceCodes.DAB, "channel", "DAB - channel"),
        (SourceCodes.DAB, None, "DAB"),
        (None, None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_media_title(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    source: SourceCodes | None,
    channel: str | None,
    title: str | None,
) -> None:
    """Test media title."""
    state_1.get_source.return_value = source
    with patch.object(
        ArcamFmj, "media_channel", new_callable=PropertyMock
    ) as media_channel:
        media_channel.return_value = channel
        data = await update(hass, client, MOCK_ENTITY_ID)
        assert data.attributes.get(ATTR_MEDIA_TITLE) == title


@pytest.mark.parametrize(
    "source", [SourceCodes.NET, SourceCodes.USB, SourceCodes.NET_USB]
)
@pytest.mark.usefixtures("player_setup")
async def test_network_now_playing_metadata(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    source: SourceCodes,
) -> None:
    """Test network and USB now-playing metadata."""
    state_1.get_source.return_value = source
    state_1.get_now_playing.return_value = NowPlayingInfo(
        track="The Chain",
        artist="Fleetwood Mac",
        album="Rumours",
        application="Qobuz",
        encoder=NowPlayingEncoder.FLAC,
        sample_rate=96000,
    )

    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.attributes[ATTR_MEDIA_TITLE] == "The Chain"
    assert data.attributes[ATTR_MEDIA_ARTIST] == "Fleetwood Mac"
    assert data.attributes[ATTR_MEDIA_ALBUM_NAME] == "Rumours"
    assert data.attributes[ATTR_APP_NAME] == "Qobuz"
    assert data.attributes[ATTR_MEDIA_ENCODER] == "FLAC"
    assert data.attributes[ATTR_MEDIA_SAMPLE_RATE] == 96000


@pytest.mark.usefixtures("player_setup")
async def test_network_now_playing_metadata_is_source_gated(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
) -> None:
    """Test stale network metadata is hidden on other sources."""
    state_1.get_source.return_value = SourceCodes.NET
    state_1.get_now_playing.return_value = NowPlayingInfo(
        track="The Chain",
        artist="Fleetwood Mac",
        album="Rumours",
        application="Qobuz",
        encoder=NowPlayingEncoder.FLAC,
        sample_rate=96000,
    )

    network_data = await update(hass, client, MOCK_ENTITY_ID)
    assert network_data.attributes[ATTR_MEDIA_TITLE] == "The Chain"

    state_1.get_source.return_value = SourceCodes.PVR
    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.attributes[ATTR_MEDIA_TITLE] == "PVR"
    assert ATTR_MEDIA_ARTIST not in data.attributes
    assert ATTR_MEDIA_ALBUM_NAME not in data.attributes
    assert ATTR_APP_NAME not in data.attributes
    assert ATTR_MEDIA_ENCODER not in data.attributes
    assert ATTR_MEDIA_SAMPLE_RATE not in data.attributes


@pytest.mark.parametrize(
    ("playback_status", "codec"),
    [
        (BluetoothAudioStatus.PLAYING_SBC, "SBC"),
        (BluetoothAudioStatus.PLAYING_AAC, "AAC"),
        (BluetoothAudioStatus.PLAYING_APTX, "aptX"),
        (BluetoothAudioStatus.PLAYING_APTX_HD, "aptX HD"),
        (BluetoothAudioStatus.PAUSED, None),
        (BluetoothAudioStatus.NO_CONNECTION, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_bluetooth_metadata(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
    playback_status: BluetoothAudioStatus,
    codec: str | None,
) -> None:
    """Test Bluetooth track and codec metadata."""
    state_1.get_source.return_value = SourceCodes.BT
    state_1.get_bluetooth_status.return_value = playback_status, "The Chain"

    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.attributes[ATTR_MEDIA_TITLE] == "The Chain"
    if codec is None:
        assert ATTR_MEDIA_CODEC not in data.attributes
    else:
        assert data.attributes[ATTR_MEDIA_CODEC] == codec
    assert ATTR_MEDIA_ARTIST not in data.attributes
    assert ATTR_MEDIA_ALBUM_NAME not in data.attributes
    assert ATTR_APP_NAME not in data.attributes
    assert ATTR_MEDIA_ENCODER not in data.attributes
    assert ATTR_MEDIA_SAMPLE_RATE not in data.attributes


@pytest.mark.usefixtures("player_setup")
async def test_bluetooth_metadata_is_source_gated(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
) -> None:
    """Test stale Bluetooth metadata is hidden on other sources."""
    state_1.get_source.return_value = SourceCodes.BT
    state_1.get_bluetooth_status.return_value = (
        BluetoothAudioStatus.PLAYING_APTX_HD,
        "The Chain",
    )
    bluetooth_data = await update(hass, client, MOCK_ENTITY_ID)
    assert bluetooth_data.attributes[ATTR_MEDIA_TITLE] == "The Chain"
    assert bluetooth_data.attributes[ATTR_MEDIA_CODEC] == "aptX HD"

    state_1.get_source.return_value = SourceCodes.PVR
    data = await update(hass, client, MOCK_ENTITY_ID)

    assert data.attributes[ATTR_MEDIA_TITLE] == "PVR"
    assert ATTR_MEDIA_CODEC not in data.attributes


@pytest.mark.usefixtures("player_setup")
async def test_fm_genre_metadata_is_source_gated(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
) -> None:
    """Test FM genre metadata follows the current source."""
    state_1.get_source.return_value = SourceCodes.FM
    state_1.command_values[FM_GENRE] = "Alternative"

    fm_data = await update(hass, client, MOCK_ENTITY_ID)
    assert fm_data.attributes[ATTR_MEDIA_GENRE] == "Alternative"

    state_1.get_source.return_value = SourceCodes.PVR
    data = await update(hass, client, MOCK_ENTITY_ID)

    assert ATTR_MEDIA_GENRE not in data.attributes


@pytest.mark.usefixtures("player_setup")
async def test_configured_input_name_is_cached_after_source_changes(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
) -> None:
    """Test configured input names are fetched only after source changes."""
    state_1.get_input_name.reset_mock()
    state_1.get_source.return_value = SourceCodes.PVR
    state_1.get_input_name.return_value = "Television"

    client.notify_data_updated(cc=CURRENT_SOURCE.cc)
    await hass.async_block_till_done()

    data = hass.states.get(MOCK_ENTITY_ID)
    assert data is not None
    assert data.attributes[ATTR_MEDIA_TITLE] == "Television"
    state_1.get_input_name.assert_awaited_once_with()

    client.notify_data_updated(cc=CURRENT_SOURCE.cc)
    await hass.async_block_till_done()
    await update(hass, client, MOCK_ENTITY_ID)
    state_1.get_input_name.assert_awaited_once_with()

    state_1.get_source.return_value = SourceCodes.BD
    state_1.get_input_name.return_value = "Blu-ray Player"
    client.notify_data_updated(cc=CURRENT_SOURCE.cc)
    await hass.async_block_till_done()

    data = hass.states.get(MOCK_ENTITY_ID)
    assert data is not None
    assert data.attributes[ATTR_MEDIA_TITLE] == "Blu-ray Player"
    assert state_1.get_input_name.await_count == 2

    state_1.get_source.return_value = SourceCodes.FM
    state_1.command_values[RDS_INFORMATION] = "KEXP"
    state_1.get_input_name.return_value = "Radio"
    client.notify_data_updated(cc=CURRENT_SOURCE.cc)
    await hass.async_block_till_done()

    data = hass.states.get(MOCK_ENTITY_ID)
    assert data is not None
    assert data.attributes[ATTR_MEDIA_TITLE] == "Radio - KEXP"
    assert state_1.get_input_name.await_count == 3


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_configured_input_name_model_support(
    hass: HomeAssistant,
    client: Mock,
    state_1: State,
) -> None:
    """Test configured input names are fetched only on supported models."""
    state_1.get_input_name.reset_mock()
    state_1.get_source.return_value = SourceCodes.PVR

    client.notify_data_updated(cc=CURRENT_SOURCE.cc)
    await hass.async_block_till_done()

    data = hass.states.get(MOCK_ENTITY_ID)
    assert data is not None
    assert data.attributes[ATTR_MEDIA_TITLE] == "PVR"
    state_1.get_input_name.assert_not_awaited()


@pytest.mark.usefixtures("player_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_configured_input_name_zone_support(
    hass: HomeAssistant,
    client: Mock,
    state_2: State,
) -> None:
    """Test configured input names are fetched only in supported zones."""
    entity_id = f"{MOCK_ENTITY_ID}_zone_2"
    state_2.get_input_name.reset_mock()
    state_2.get_source.return_value = SourceCodes.PVR

    client.notify_data_updated(zn=2, cc=CURRENT_SOURCE.cc)
    await hass.async_block_till_done()

    data = hass.states.get(entity_id)
    assert data is not None
    assert data.attributes[ATTR_MEDIA_TITLE] == "PVR"
    state_2.get_input_name.assert_not_awaited()
