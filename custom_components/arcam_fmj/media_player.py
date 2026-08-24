"""Arcam media player."""

import logging
from typing import Any, override

from arcam.fmj.codecs import (
    BluetoothAudioStatus,
    NetworkPlaybackStatus,
    NowPlayingInfo,
    SourceCodes,
)
from arcam.fmj.commands import (
    CURRENT_SOURCE,
    DAB_STATION,
    DECODE_MODE_2CH,
    DLS_PDT,
    FM_GENRE,
    MUTE,
    NETWORK_PLAYBACK_STATUS,
    POWER,
    RDS_INFORMATION,
    SIMULATE_RC5_IR_COMMAND,
    TUNER_PRESET,
    VOLUME,
)
from arcam.fmj.rc5 import RC5CODE_PLAYBACK, RC5CodePlayback

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, EVENT_TURN_ON
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator
from .entity import ArcamFmjEntity, convert_exception

_LOGGER = logging.getLogger(__name__)

ATTR_MEDIA_CODEC = "media_codec"
ATTR_MEDIA_ENCODER = "media_encoder"
ATTR_MEDIA_GENRE = "media_genre"
ATTR_MEDIA_SAMPLE_RATE = "media_sample_rate"

_NETWORK_SOURCES = frozenset({SourceCodes.NET, SourceCodes.USB, SourceCodes.NET_USB})
_TRANSPORT_SOURCES = _NETWORK_SOURCES | {SourceCodes.BT}
_MUSIC_SOURCES = _NETWORK_SOURCES | {
    SourceCodes.BT,
    SourceCodes.DAB,
    SourceCodes.FM,
}
_NETWORK_STATES = {
    NetworkPlaybackStatus.STOPPED: MediaPlayerState.IDLE,
    NetworkPlaybackStatus.TRANSITIONING: MediaPlayerState.BUFFERING,
    NetworkPlaybackStatus.PLAYING: MediaPlayerState.PLAYING,
    NetworkPlaybackStatus.PAUSED: MediaPlayerState.PAUSED,
}
_BLUETOOTH_STATES = {
    BluetoothAudioStatus.NO_CONNECTION: MediaPlayerState.IDLE,
    BluetoothAudioStatus.PAUSED: MediaPlayerState.PAUSED,
    BluetoothAudioStatus.PLAYING_SBC: MediaPlayerState.PLAYING,
    BluetoothAudioStatus.PLAYING_AAC: MediaPlayerState.PLAYING,
    BluetoothAudioStatus.PLAYING_APTX: MediaPlayerState.PLAYING,
    BluetoothAudioStatus.PLAYING_APTX_HD: MediaPlayerState.PLAYING,
}
_BLUETOOTH_CODECS = {
    BluetoothAudioStatus.PLAYING_SBC: "SBC",
    BluetoothAudioStatus.PLAYING_AAC: "AAC",
    BluetoothAudioStatus.PLAYING_APTX: "aptX",
    BluetoothAudioStatus.PLAYING_APTX_HD: "aptX HD",
}
_TRANSPORT_FEATURES = {
    RC5CodePlayback.PLAY: MediaPlayerEntityFeature.PLAY,
    RC5CodePlayback.PAUSE: MediaPlayerEntityFeature.PAUSE,
    RC5CodePlayback.STOP: MediaPlayerEntityFeature.STOP,
    RC5CodePlayback.SKIP_FORWARD: MediaPlayerEntityFeature.NEXT_TRACK,
    RC5CodePlayback.SKIP_BACK: MediaPlayerEntityFeature.PREVIOUS_TRACK,
}

# arcam-fmj serializes commands on a single TCP writer at the library
# layer; serialize at HA's layer to match the device's contract.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinators = config_entry.runtime_data.coordinators

    async_add_entities(
        [
            ArcamFmj(coordinator)
            for coordinator in coordinators.values()
            if coordinator.supports_command(POWER)
        ],
    )


class ArcamFmj(ArcamFmjEntity, MediaPlayerEntity):
    """Representation of a media device."""

    def __init__(self, coordinator: ArcamFmjCoordinator) -> None:
        """Initialize device."""
        super().__init__(coordinator)
        self._state = coordinator.state

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return features supported by the discovered model, zone, and source."""
        features = MediaPlayerEntityFeature(0)
        if self.coordinator.supports_command(POWER):
            features |= (
                MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON
            )
        if self.coordinator.supports_command(CURRENT_SOURCE):
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.coordinator.supports_command(VOLUME):
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.coordinator.supports_command(MUTE):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self.coordinator.supports_command(
            TUNER_PRESET
        ) and self._state.supported_on_source(TUNER_PRESET):
            features |= (
                MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.BROWSE_MEDIA
            )
        if self.coordinator.supports_command(DECODE_MODE_2CH):
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        transport_codes = self._supported_transport_codes()
        for code, feature in _TRANSPORT_FEATURES.items():
            if code in transport_codes:
                features |= feature
        return features

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device.

        ``None`` is returned (surfaced as ``unknown``) when the device has
        not yet reported a power state; this is distinct from a real
        powered-off state and must not be collapsed to ``OFF``.
        """
        power = self._state.get(POWER)
        if power is None:
            return None
        if not power:
            return MediaPlayerState.OFF
        source = self._state.get_source()
        if source in _NETWORK_SOURCES:
            return _NETWORK_STATES.get(
                self._state.get(NETWORK_PLAYBACK_STATUS), MediaPlayerState.ON
            )
        if source is SourceCodes.BT:
            status, _ = self._state.get_bluetooth_status()
            return _BLUETOOTH_STATES.get(status, MediaPlayerState.ON)
        return MediaPlayerState.ON

    @convert_exception
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._state.set(MUTE, mute)
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_select_source(self, source: str) -> None:
        """Select a specific source."""
        try:
            value = SourceCodes[source]
        except KeyError as exception:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_source",
                translation_placeholders={"source": source},
            ) from exception

        await self._state.set_source(value)
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a specific source."""
        try:
            await self._state.set_decode_mode(sound_mode)
        except (KeyError, ValueError) as exception:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_sound_mode",
                translation_placeholders={"sound_mode": sound_mode},
            ) from exception

        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._state.set(VOLUME, round(volume * 99.0))
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self._state.inc(VOLUME)
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_volume_down(self) -> None:
        """Turn volume up for media player."""
        await self._state.dec(VOLUME)
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._state.send_playback(RC5CodePlayback.PLAY)

    @convert_exception
    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._state.send_playback(RC5CodePlayback.PAUSE)

    @convert_exception
    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._state.send_playback(RC5CodePlayback.STOP)

    @convert_exception
    @override
    async def async_media_next_track(self) -> None:
        """Send skip-forward command."""
        await self._state.send_playback(RC5CodePlayback.SKIP_FORWARD)

    @convert_exception
    @override
    async def async_media_previous_track(self) -> None:
        """Send skip-back command."""
        await self._state.send_playback(RC5CodePlayback.SKIP_BACK)

    @convert_exception
    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        if self._state.get(POWER) is not None:
            _LOGGER.debug("Turning on device using connection")
            await self._state.set(POWER, True)
        else:
            _LOGGER.debug("Firing event to turn on device")
            self.hass.bus.async_fire(EVENT_TURN_ON, {ATTR_ENTITY_ID: self.entity_id})

    @convert_exception
    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._state.set(POWER, False)

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        if media_content_id not in (None, "root"):
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )

        presets = self._state.get_preset_details() or {}

        radio = [
            BrowseMedia(
                title=preset.name,
                media_class=MediaClass.MUSIC,
                media_content_id=f"preset:{preset.index}",
                media_content_type=MediaType.MUSIC,
                can_play=True,
                can_expand=False,
            )
            for preset in presets.values()
        ]

        return BrowseMedia(
            title=self.coordinator.device_name,
            media_class=MediaClass.DIRECTORY,
            media_content_id="root",
            media_content_type="library",
            can_play=False,
            can_expand=True,
            children=radio,
        )

    @convert_exception
    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""

        if media_id.startswith("preset:"):
            preset = int(media_id[7:])
            await self._state.set(TUNER_PRESET, preset)
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_media",
                translation_placeholders={"media": media_id},
            )

    @property
    @override
    def source(self) -> str | None:
        """Return the current input source."""
        if (value := self._state.get_source()) is None:
            return None
        return value.name

    @property
    @override
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return [x.name for x in self._state.get_source_list()]

    @property
    @override
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        if (value := self._state.get_decode_mode()) is None:
            return None
        return value.name

    @property
    @override
    def sound_mode_list(self) -> list[str] | None:
        """List of available sound modes."""
        if (values := self._state.get_decode_modes()) is None:
            return None
        return [x.name for x in values]

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if (value := self._state.get(MUTE)) is None:
            return None
        return value

    @property
    @override
    def volume_level(self) -> float | None:
        """Volume level of device."""
        if (value := self._state.get(VOLUME)) is None:
            return None
        return value / 99.0

    @property
    @override
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        source = self._state.get_source()
        if source in _MUSIC_SOURCES:
            value = MediaType.MUSIC
        else:
            value = None
        return value

    @property
    @override
    def media_content_id(self) -> str | None:
        """Content type of current playing media."""
        source = self._state.get_source()
        if source in (SourceCodes.DAB, SourceCodes.FM):
            if preset := self._state.get(TUNER_PRESET):
                value = f"preset:{preset}"
            else:
                value = None
        else:
            value = None

        return value

    @property
    @override
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        source = self._state.get_source()
        if source is SourceCodes.DAB:
            value = self._state.get(DAB_STATION)
        elif source is SourceCodes.FM:
            value = self._state.get(RDS_INFORMATION)
        else:
            value = None
        return value

    @property
    @override
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if self._state.get_source() is SourceCodes.DAB:
            value = self._state.get(DLS_PDT)
        elif (now_playing := self._network_now_playing()) is not None:
            value = now_playing.artist
        else:
            value = None
        return value

    @property
    @override
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if (now_playing := self._network_now_playing()) is None:
            return None
        return now_playing.album

    @property
    @override
    def app_name(self) -> str | None:
        """Name of the current running app."""
        if (now_playing := self._network_now_playing()) is None:
            return None
        return now_playing.application

    @property
    @override
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if (source := self._state.get_source()) is None:
            return None

        source_name = self.coordinator.input_name_for(source) or source.name
        if source is SourceCodes.BT:
            _, track = self._state.get_bluetooth_status()
            if track is not None:
                value = track
            else:
                value = source_name
        elif (
            now_playing := self._network_now_playing()
        ) is not None and now_playing.track is not None:
            value = now_playing.track
        elif channel := self.media_channel:
            value = f"{source_name} - {channel}"
        else:
            value = source_name
        return value

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return playback details."""
        source = self._state.get_source()
        if source is SourceCodes.FM:
            if (genre := self._state.get(FM_GENRE)) is None:
                return None
            return {ATTR_MEDIA_GENRE: genre}

        if source is SourceCodes.BT:
            status, _ = self._state.get_bluetooth_status()
            if (codec := _BLUETOOTH_CODECS.get(status)) is None:
                return None
            return {ATTR_MEDIA_CODEC: codec}

        if (now_playing := self._network_now_playing()) is None:
            return None

        attributes: dict[str, Any] = {}
        if now_playing.encoder is not None:
            attributes[ATTR_MEDIA_ENCODER] = now_playing.encoder.name
        if now_playing.sample_rate:
            attributes[ATTR_MEDIA_SAMPLE_RATE] = now_playing.sample_rate
        return attributes or None

    def _network_now_playing(self) -> NowPlayingInfo | None:
        if self._state.get_source() not in _NETWORK_SOURCES:
            return None
        return self._state.get_now_playing()

    def _supported_transport_codes(self) -> frozenset[RC5CodePlayback]:
        if (
            self._state.get_source() not in _TRANSPORT_SOURCES
            or not self.coordinator.supports_command(SIMULATE_RC5_IR_COMMAND)
        ):
            return frozenset()
        return frozenset(
            RC5CODE_PLAYBACK.get((self._state.api_model, self._state.zn), ())
        )
