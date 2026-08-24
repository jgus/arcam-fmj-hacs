"""Arcam select entities."""

from dataclasses import dataclass
from typing import Any, override

from arcam.fmj.codecs import (
    SA_SOURCE_MAPPING,
    AutoShutdown,
    CompressionMode,
    DacFilter,
    DisplayInfoTypeValue,
    DisplayBrightness,
    DolbyAudioMode,
    DolbyLeveler,
    HdmiOutput,
    ImaxEnhancedMode,
    RoomEqMode,
    VideoFilmMode,
    VideoNoiseReduction,
    VideoSelection,
    display_info_types_for_source,
)
from arcam.fmj.commands import (
    AUTO_SHUTDOWN_CONTROL,
    COMPRESSION,
    DAC_FILTER,
    DISPLAY_BRIGHTNESS,
    DISPLAY_INFO_TYPE,
    DOLBY_AUDIO,
    DOLBY_LEVELER,
    IMAX_ENHANCED,
    PROCESSOR_MODE_INPUT,
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

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
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
    ArcamFmjSelectEntityDescription(
        key="dac_filter",
        command=DAC_FILTER,
        translation_key="dac_filter",
        entity_category=EntityCategory.CONFIG,
        enum_type=DacFilter,
    ),
)

ROOM_EQUALIZATION_DESCRIPTION = ArcamFmjSelectEntityDescription(
    key="room_equalization",
    command=ROOM_EQUALIZATION,
    translation_key="room_equalization",
    entity_category=EntityCategory.CONFIG,
    enum_type=RoomEqMode,
)

DISPLAY_INFO_TYPE_DESCRIPTION = ArcamFmjCommandEntityDescription(
    key="display_info_type",
    command=DISPLAY_INFO_TYPE,
    translation_key="display_info_type",
    entity_category=EntityCategory.CONFIG,
)

PROCESSOR_MODE_INPUT_DESCRIPTION = ArcamFmjCommandEntityDescription(
    key="processor_mode_input",
    command=PROCESSOR_MODE_INPUT,
    translation_key="processor_mode_input",
    entity_category=EntityCategory.CONFIG,
)

DOLBY_LEVELER_DESCRIPTION = ArcamFmjSelectEntityDescription(
    key="dolby_leveler",
    command=DOLBY_LEVELER,
    translation_key="dolby_leveler",
    entity_category=EntityCategory.CONFIG,
    enum_type=DolbyLeveler,
)
_PROCESSOR_MODE_INPUT_OPTIONS = {
    "disabled": None,
    **{source.name.lower(): source for source in SA_SOURCE_MAPPING},
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ selects from a config entry."""
    coordinators = config_entry.runtime_data.coordinators
    entities: list[SelectEntity] = [
        ArcamFmjSelectEntity(coordinator, description)
        for coordinator in config_entry.runtime_data.coordinators.values()
        for description in supported_entity_descriptions(coordinator, SELECTS)
    ]
    room_eq_names_coordinator = coordinators[1]
    entities.extend(
        ArcamFmjRoomEqSelectEntity(
            coordinator,
            ROOM_EQUALIZATION_DESCRIPTION,
            room_eq_names_coordinator,
        )
        for coordinator in coordinators.values()
        if coordinator.supports_command(ROOM_EQUALIZATION)
    )
    entities.extend(
        ArcamFmjDisplayInfoSelectEntity(
            coordinator,
            DISPLAY_INFO_TYPE_DESCRIPTION,
        )
        for coordinator in coordinators.values()
        if coordinator.supports_command(DISPLAY_INFO_TYPE)
    )
    entities.extend(
        ArcamFmjProcessorModeInputSelectEntity(
            coordinator,
            PROCESSOR_MODE_INPUT_DESCRIPTION,
        )
        for coordinator in coordinators.values()
        if coordinator.supports_command(PROCESSOR_MODE_INPUT)
    )
    entities.extend(
        ArcamFmjDolbyLevelerSelectEntity(
            coordinator,
            DOLBY_LEVELER_DESCRIPTION,
        )
        for coordinator in coordinators.values()
        if coordinator.supports_command(DOLBY_LEVELER)
    )
    async_add_entities(entities)


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


class ArcamFmjRoomEqSelectEntity(ArcamFmjSelectEntity):
    """Representation of an Arcam FMJ Room EQ select."""

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: ArcamFmjSelectEntityDescription,
        room_eq_names_coordinator: ArcamFmjCoordinator,
    ) -> None:
        """Initialize the Room EQ select."""
        super().__init__(coordinator, description)
        self._room_eq_names_coordinator = room_eq_names_coordinator

    async def async_added_to_hass(self) -> None:
        """Subscribe to Room EQ name updates."""
        await super().async_added_to_hass()
        if self._room_eq_names_coordinator is not self.coordinator:
            self.async_on_remove(
                self._room_eq_names_coordinator.async_add_listener(
                    self._handle_room_eq_names_update
                )
            )

    @callback
    def _handle_room_eq_names_update(self) -> None:
        self.async_write_ha_state()

    def _room_eq_option_values(self) -> dict[str, RoomEqMode]:
        names = self._room_eq_names_coordinator.state.get(ROOM_EQ_NAMES) or []
        option_values = {"off": RoomEqMode.OFF}
        for index, mode in enumerate((RoomEqMode.EQ1, RoomEqMode.EQ2, RoomEqMode.EQ3)):
            option = (
                names[index]
                if index < len(names) and names[index]
                else mode.name.lower()
            )
            if option in option_values:
                option = f"{option} ({index + 1})"
            option_values[option] = mode
        return option_values

    @property
    @override
    def options(self) -> list[str]:
        """Return selectable Room EQ options and any read-only current state."""
        options = list(self._room_eq_option_values())
        if self.coordinator.state.get(ROOM_EQUALIZATION) is RoomEqMode.NOT_CALCULATED:
            options.append("not_calculated")
        return options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected Room EQ option."""
        value = self.coordinator.state.get(ROOM_EQUALIZATION)
        if value is None:
            return None
        if value is RoomEqMode.NOT_CALCULATED:
            return "not_calculated"
        return next(
            (
                option
                for option, option_value in self._room_eq_option_values().items()
                if option_value is value
            ),
            None,
        )

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select a Room EQ option."""
        option_values = self._room_eq_option_values()
        if option not in option_values:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="room_eq_state_read_only",
                translation_placeholders={"state": option},
            )
        await self.coordinator.state.set(ROOM_EQUALIZATION, option_values[option])
        self.async_write_ha_state()


class ArcamFmjDisplayInfoSelectEntity(ArcamFmjEntity, SelectEntity):
    """Representation of a source-dependent VFD information select."""

    def _option_values(self) -> dict[str, DisplayInfoTypeValue]:
        return {
            value.name.lower(): value
            for value in display_info_types_for_source(
                self.coordinator.state.get_source()
            )
        }

    @property
    @override
    def options(self) -> list[str]:
        """Return the VFD information choices for the current source."""
        return list(self._option_values())

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected VFD information type."""
        return enum_value(self.coordinator.state.get(DISPLAY_INFO_TYPE))

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select a VFD information type."""
        await self.coordinator.state.set(
            DISPLAY_INFO_TYPE, self._option_values()[option]
        )
        self.async_write_ha_state()


class ArcamFmjProcessorModeInputSelectEntity(ArcamFmjEntity, SelectEntity):
    """Representation of an SA processor-mode-input select."""

    _attr_options = list(_PROCESSOR_MODE_INPUT_OPTIONS)

    @property
    @override
    def current_option(self) -> str:
        """Return the processor-mode input or Disabled."""
        value = self.coordinator.state.get(PROCESSOR_MODE_INPUT)
        return "disabled" if value is None else value.name.lower()

    @convert_exception
    @override
    async def async_select_option(self, option: str) -> None:
        """Select or disable the processor-mode input."""
        await self.coordinator.state.set(
            PROCESSOR_MODE_INPUT, _PROCESSOR_MODE_INPUT_OPTIONS[option]
        )
        self.async_write_ha_state()


class ArcamFmjDolbyLevelerSelectEntity(ArcamFmjSelectEntity):
    """Representation of a Dolby leveler select with an Off state."""

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: ArcamFmjSelectEntityDescription,
    ) -> None:
        """Initialize the Dolby leveler select."""
        super().__init__(coordinator, description)
        self._option_values = {
            "off": DolbyLeveler.OFF,
            **self._option_values,
        }
        self._attr_options = list(self._option_values)
