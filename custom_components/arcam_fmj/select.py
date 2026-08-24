"""Arcam select entities."""

from dataclasses import dataclass
from typing import Any, override

from arcam.fmj.codecs import (
    AutoShutdown,
    CompressionMode,
    DisplayBrightness,
    DolbyAudioMode,
    HdmiOutput,
    ImaxEnhancedMode,
    VideoFilmMode,
    VideoNoiseReduction,
    VideoSelection,
)
from arcam.fmj.commands import (
    AUTO_SHUTDOWN_CONTROL,
    COMPRESSION,
    DISPLAY_BRIGHTNESS,
    DOLBY_AUDIO,
    IMAX_ENHANCED,
    VIDEO_FILM_MODE,
    VIDEO_MPEG_NOISE_REDUCTION,
    VIDEO_NOISE_REDUCTION,
    VIDEO_OUTPUT_SWITCHING,
    VIDEO_SELECTION,
    ReadWriteCommand,
)
from arcam.fmj.models import IntOrTypeEnum

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator
from .entity import (
    ArcamFmjCommandEntityDescription,
    ArcamFmjEntity,
    convert_exception,
    enum_options_for_model,
    enum_value,
    supported_entity_descriptions,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ArcamFmjSelectEntityDescription(
    ArcamFmjCommandEntityDescription, SelectEntityDescription
):
    """Describes an Arcam FMJ select entity."""

    command: ReadWriteCommand[Any]
    enum_type: type[IntOrTypeEnum]


SELECTS: tuple[ArcamFmjSelectEntityDescription, ...] = (
    ArcamFmjSelectEntityDescription(
        key="display_brightness",
        command=DISPLAY_BRIGHTNESS,
        translation_key="display_brightness",
        entity_category=EntityCategory.CONFIG,
        enum_type=DisplayBrightness,
    ),
    ArcamFmjSelectEntityDescription(
        key="video_selection",
        command=VIDEO_SELECTION,
        translation_key="video_selection",
        entity_category=EntityCategory.CONFIG,
        enum_type=VideoSelection,
    ),
    ArcamFmjSelectEntityDescription(
        key="imax_enhanced",
        command=IMAX_ENHANCED,
        translation_key="imax_enhanced",
        entity_category=EntityCategory.CONFIG,
        enum_type=ImaxEnhancedMode,
    ),
    ArcamFmjSelectEntityDescription(
        key="dolby_audio",
        command=DOLBY_AUDIO,
        translation_key="dolby_audio",
        entity_category=EntityCategory.CONFIG,
        enum_type=DolbyAudioMode,
    ),
    ArcamFmjSelectEntityDescription(
        key="compression",
        command=COMPRESSION,
        translation_key="compression",
        entity_category=EntityCategory.CONFIG,
        enum_type=CompressionMode,
    ),
    ArcamFmjSelectEntityDescription(
        key="video_film_mode",
        command=VIDEO_FILM_MODE,
        translation_key="video_film_mode",
        entity_category=EntityCategory.CONFIG,
        enum_type=VideoFilmMode,
    ),
    ArcamFmjSelectEntityDescription(
        key="video_noise_reduction",
        command=VIDEO_NOISE_REDUCTION,
        translation_key="video_noise_reduction",
        entity_category=EntityCategory.CONFIG,
        enum_type=VideoNoiseReduction,
    ),
    ArcamFmjSelectEntityDescription(
        key="video_mpeg_noise_reduction",
        command=VIDEO_MPEG_NOISE_REDUCTION,
        translation_key="video_mpeg_noise_reduction",
        entity_category=EntityCategory.CONFIG,
        enum_type=VideoNoiseReduction,
    ),
    ArcamFmjSelectEntityDescription(
        key="video_output_switching",
        command=VIDEO_OUTPUT_SWITCHING,
        translation_key="video_output_switching",
        entity_category=EntityCategory.CONFIG,
        enum_type=HdmiOutput,
    ),
    ArcamFmjSelectEntityDescription(
        key="auto_shutdown_control",
        command=AUTO_SHUTDOWN_CONTROL,
        translation_key="auto_shutdown_control",
        entity_category=EntityCategory.CONFIG,
        enum_type=AutoShutdown,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ selects from a config entry."""
    async_add_entities(
        ArcamFmjSelectEntity(coordinator, description)
        for coordinator in config_entry.runtime_data.coordinators.values()
        for description in supported_entity_descriptions(coordinator, SELECTS)
    )


class ArcamFmjSelectEntity(ArcamFmjEntity, SelectEntity):
    """Representation of an Arcam FMJ select."""

    entity_description: ArcamFmjSelectEntityDescription

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: ArcamFmjSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, description)
        self._option_values = enum_options_for_model(
            description.enum_type, coordinator.model
        )
        self._attr_options = list(self._option_values)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected option."""
        return enum_value(self.coordinator.state.get(self.entity_description.command))

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.coordinator.state.set(
            self.entity_description.command, self._option_values[option]
        )
        self.async_write_ha_state()
