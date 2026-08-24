"""Arcam sensors for incoming stream info."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from arcam.fmj.codecs import (
    IncomingAudioConfig,
    IncomingAudioFormat,
    IncomingVideoAspectRatio,
    IncomingVideoColorspace,
    MenuCodes,
    TemperatureSensor,
)
from arcam.fmj.commands import (
    FM_GENRE,
    INCOMING_AUDIO_SAMPLE_RATE,
    INCOMING_AUDIO_FORMAT,
    INCOMING_VIDEO_PARAMETERS,
    LIFTER_TEMPERATURE,
    MENU,
    OUTPUT_TEMPERATURE,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfFrequency, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator
from .entity import (
    ArcamFmjCommandEntityDescription,
    ArcamFmjEntity,
    enum_options,
    enum_value,
    supported_entity_descriptions,
)

# Read-only, coordinator-driven entities; no per-entity I/O to bound.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ArcamFmjSensorEntityDescription(
    ArcamFmjCommandEntityDescription, SensorEntityDescription
):
    """Describes an Arcam FMJ sensor entity."""

    value_fn: Callable[[ArcamFmjCoordinator], int | float | str | None]


SENSORS: tuple[ArcamFmjSensorEntityDescription, ...] = (
    ArcamFmjSensorEntityDescription(
        key="fm_genre",
        command=FM_GENRE,
        translation_key="fm_genre",
        value_fn=lambda coordinator: coordinator.state.get(FM_GENRE),
    ),
    ArcamFmjSensorEntityDescription(
        key="menu",
        command=MENU,
        translation_key="menu",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(MenuCodes),
        value_fn=lambda coordinator: enum_value(coordinator.state.get(MENU)),
    ),
    ArcamFmjSensorEntityDescription(
        key="lifter_temperature",
        command=LIFTER_TEMPERATURE,
        translation_key="lifter_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        value_fn=lambda coordinator: coordinator.state.get(LIFTER_TEMPERATURE),
    ),
    ArcamFmjSensorEntityDescription(
        key="output_temperature",
        command=OUTPUT_TEMPERATURE,
        translation_key="output_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        value_fn=lambda coordinator: coordinator.state.get(OUTPUT_TEMPERATURE),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_horizontal_resolution",
        command=INCOMING_VIDEO_PARAMETERS,
        translation_key="incoming_video_horizontal_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda coordinator: (
            vp.horizontal_resolution
            if (vp := coordinator.state.get(INCOMING_VIDEO_PARAMETERS)) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_vertical_resolution",
        command=INCOMING_VIDEO_PARAMETERS,
        translation_key="incoming_video_vertical_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda coordinator: (
            vp.vertical_resolution
            if (vp := coordinator.state.get(INCOMING_VIDEO_PARAMETERS)) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_refresh_rate",
        command=INCOMING_VIDEO_PARAMETERS,
        translation_key="incoming_video_refresh_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        value_fn=lambda coordinator: (
            vp.refresh_rate
            if (vp := coordinator.state.get(INCOMING_VIDEO_PARAMETERS)) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_aspect_ratio",
        command=INCOMING_VIDEO_PARAMETERS,
        translation_key="incoming_video_aspect_ratio",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(IncomingVideoAspectRatio),
        value_fn=lambda coordinator: (
            enum_value(vp.aspect_ratio)
            if (vp := coordinator.state.get(INCOMING_VIDEO_PARAMETERS)) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_colorspace",
        command=INCOMING_VIDEO_PARAMETERS,
        translation_key="incoming_video_colorspace",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(IncomingVideoColorspace),
        value_fn=lambda coordinator: (
            enum_value(vp.colorspace)
            if (vp := coordinator.state.get(INCOMING_VIDEO_PARAMETERS)) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_format",
        command=INCOMING_AUDIO_FORMAT,
        translation_key="incoming_audio_format",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(IncomingAudioFormat),
        value_fn=lambda coordinator: enum_value(
            coordinator.state.get_incoming_audio_format()[0]
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_config",
        command=INCOMING_AUDIO_FORMAT,
        translation_key="incoming_audio_config",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(IncomingAudioConfig),
        value_fn=lambda coordinator: enum_value(
            coordinator.state.get_incoming_audio_format()[1]
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_sample_rate",
        command=INCOMING_AUDIO_SAMPLE_RATE,
        translation_key="incoming_audio_sample_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        value_fn=lambda coordinator: (
            None
            if (sample_rate := coordinator.state.get(INCOMING_AUDIO_SAMPLE_RATE)) == 0
            else sample_rate
        ),
    ),
)

LIFTER_TEMPERATURE_2_DESCRIPTION = ArcamFmjSensorEntityDescription(
    key="lifter_temperature_2",
    command=LIFTER_TEMPERATURE,
    translation_key="lifter_temperature_2",
    device_class=SensorDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=0,
    value_fn=lambda coordinator: coordinator.temperature_sensor_2_value(
        LIFTER_TEMPERATURE
    ),
)

OUTPUT_TEMPERATURE_2_DESCRIPTION = ArcamFmjSensorEntityDescription(
    key="output_temperature_2",
    command=OUTPUT_TEMPERATURE,
    translation_key="output_temperature_2",
    device_class=SensorDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=0,
    value_fn=lambda coordinator: coordinator.temperature_sensor_2_value(
        OUTPUT_TEMPERATURE
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ sensors from a config entry."""
    coordinators = config_entry.runtime_data.coordinators

    entities: list[ArcamFmjSensorEntity] = []
    for coordinator in coordinators.values():
        entities.extend(
            ArcamFmjSensorEntity(coordinator, description)
            for description in supported_entity_descriptions(coordinator, SENSORS)
        )
        if coordinator.supports_command(
            LIFTER_TEMPERATURE
        ) and TemperatureSensor.SENSOR_2 in LIFTER_TEMPERATURE.supported_sensors(
            coordinator.model
        ):
            entities.append(
                ArcamFmjSensorEntity(coordinator, LIFTER_TEMPERATURE_2_DESCRIPTION)
            )
        if coordinator.supports_command(
            OUTPUT_TEMPERATURE
        ) and TemperatureSensor.SENSOR_2 in OUTPUT_TEMPERATURE.supported_sensors(
            coordinator.model
        ):
            entities.append(
                ArcamFmjSensorEntity(coordinator, OUTPUT_TEMPERATURE_2_DESCRIPTION)
            )
    async_add_entities(entities)


class ArcamFmjSensorEntity(ArcamFmjEntity, SensorEntity):
    """Representation of an Arcam FMJ sensor."""

    entity_description: ArcamFmjSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
