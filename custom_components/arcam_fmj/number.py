"""Arcam number entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

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

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfSoundPressure, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ArcamFmjConfigEntry
from .entity import (
    ArcamFmjCommandEntityDescription,
    ArcamFmjEntity,
    convert_exception,
    supported_entity_descriptions,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ArcamFmjNumberEntityDescription(
    ArcamFmjCommandEntityDescription, NumberEntityDescription
):
    """Describes an Arcam FMJ number entity."""

    command: ReadWriteCommand[Any]
    set_value_fn: Callable[[float], int | float] = float


NUMBERS: tuple[ArcamFmjNumberEntityDescription, ...] = (
    ArcamFmjNumberEntityDescription(
        key="treble_equalization",
        command=TREBLE_EQUALIZATION,
        translation_key="treble_equalization",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-12,
        native_max_value=12,
        native_step=1,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    ),
    ArcamFmjNumberEntityDescription(
        key="bass_equalization",
        command=BASS_EQUALIZATION,
        translation_key="bass_equalization",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-12,
        native_max_value=12,
        native_step=1,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    ),
    ArcamFmjNumberEntityDescription(
        key="dolby_volume_calibration_offset",
        command=DOLBY_VOLUME_CALIBRATION_OFFSET,
        translation_key="dolby_volume_calibration_offset",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-15,
        native_max_value=15,
        native_step=1,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    ),
    ArcamFmjNumberEntityDescription(
        key="balance",
        command=BALANCE,
        translation_key="balance",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-6,
        native_max_value=6,
        native_step=1,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    ),
    ArcamFmjNumberEntityDescription(
        key="dolby_pliix_centre_width",
        command=DOLBY_PLIIX_CENTRE_WIDTH,
        translation_key="dolby_pliix_centre_width",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=7,
        native_step=1,
        set_value_fn=int,
    ),
    ArcamFmjNumberEntityDescription(
        key="subwoofer_trim",
        command=SUBWOOFER_TRIM,
        translation_key="subwoofer_trim",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-10,
        native_max_value=10,
        native_step=0.5,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    ),
    ArcamFmjNumberEntityDescription(
        key="lipsync_delay",
        command=LIPSYNC_DELAY,
        translation_key="lipsync_delay",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=0,
        native_max_value=250,
        native_step=5,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
    ),
    ArcamFmjNumberEntityDescription(
        key="sub_stereo_trim",
        command=SUB_STEREO_TRIM,
        translation_key="sub_stereo_trim",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-10,
        native_max_value=0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    ),
    ArcamFmjNumberEntityDescription(
        key="video_brightness",
        command=VIDEO_BRIGHTNESS,
        translation_key="video_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-50,
        native_max_value=50,
        native_step=1,
    ),
    ArcamFmjNumberEntityDescription(
        key="video_contrast",
        command=VIDEO_CONTRAST,
        translation_key="video_contrast",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-50,
        native_max_value=50,
        native_step=1,
    ),
    ArcamFmjNumberEntityDescription(
        key="video_colour",
        command=VIDEO_COLOUR,
        translation_key="video_colour",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-50,
        native_max_value=50,
        native_step=1,
    ),
    ArcamFmjNumberEntityDescription(
        key="video_edge_enhancement",
        command=VIDEO_EDGE_ENHANCEMENT,
        translation_key="video_edge_enhancement",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=1,
        set_value_fn=int,
    ),
    ArcamFmjNumberEntityDescription(
        key="processor_mode_volume",
        command=PROCESSOR_MODE_VOLUME,
        translation_key="processor_mode_volume",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        set_value_fn=int,
    ),
    ArcamFmjNumberEntityDescription(
        key="max_turn_on_volume",
        command=MAX_TURN_ON_VOLUME,
        translation_key="max_turn_on_volume",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        set_value_fn=int,
    ),
    ArcamFmjNumberEntityDescription(
        key="max_volume",
        command=MAX_VOLUME,
        translation_key="max_volume",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        set_value_fn=int,
    ),
    ArcamFmjNumberEntityDescription(
        key="max_streaming_volume",
        command=MAX_STREAMING_VOLUME,
        translation_key="max_streaming_volume",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        set_value_fn=int,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ numbers from a config entry."""
    async_add_entities(
        ArcamFmjNumberEntity(coordinator, description)
        for coordinator in config_entry.runtime_data.coordinators.values()
        for description in supported_entity_descriptions(coordinator, NUMBERS)
    )


class ArcamFmjNumberEntity(ArcamFmjEntity, NumberEntity):
    """Representation of an Arcam FMJ number."""

    entity_description: ArcamFmjNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the number value."""
        return self.coordinator.state.get(self.entity_description.command)

    @convert_exception
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        await self.coordinator.state.set(
            self.entity_description.command,
            self.entity_description.set_value_fn(value),
        )
        self.async_write_ha_state()
