"""Arcam switch entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from arcam.fmj.codecs import ZoneOsd
from arcam.fmj.commands import (
    DIRECT_MODE,
    DOLBY_PLIIX_PANORAMA,
    HEADPHONES_OVERRIDE,
    ZONE_1_OSD_ON_OFF,
    WriteCommand,
)
from arcam.fmj.state import State

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
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
class ArcamFmjSwitchEntityDescription(
    ArcamFmjCommandEntityDescription, SwitchEntityDescription
):
    """Describes an Arcam FMJ switch entity."""

    command: WriteCommand[Any]
    value_fn: Callable[[State], bool | None] | None = None
    on_value: Any = True
    off_value: Any = False
    assumed: bool = False


SWITCHES: tuple[ArcamFmjSwitchEntityDescription, ...] = (
    ArcamFmjSwitchEntityDescription(
        key="direct_mode",
        command=DIRECT_MODE,
        translation_key="direct_mode",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.get(DIRECT_MODE),
    ),
    ArcamFmjSwitchEntityDescription(
        key="dolby_pliix_panorama",
        command=DOLBY_PLIIX_PANORAMA,
        translation_key="dolby_pliix_panorama",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.get(DOLBY_PLIIX_PANORAMA),
    ),
    ArcamFmjSwitchEntityDescription(
        key="zone_1_osd",
        command=ZONE_1_OSD_ON_OFF,
        translation_key="zone_1_osd",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: (
            None
            if (value := state.get(ZONE_1_OSD_ON_OFF)) is None
            else value is ZoneOsd.ON
        ),
        on_value=ZoneOsd.ON,
        off_value=ZoneOsd.OFF,
    ),
    ArcamFmjSwitchEntityDescription(
        key="headphones_override",
        command=HEADPHONES_OVERRIDE,
        translation_key="headphones_override",
        entity_category=EntityCategory.CONFIG,
        assumed=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ switches from a config entry."""
    async_add_entities(
        ArcamFmjSwitchEntity(coordinator, description)
        for coordinator in config_entry.runtime_data.coordinators.values()
        for description in supported_entity_descriptions(coordinator, SWITCHES)
    )


class ArcamFmjSwitchEntity(ArcamFmjEntity, SwitchEntity):
    """Representation of an Arcam FMJ switch."""

    entity_description: ArcamFmjSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the switch state."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.state)

    @property
    @override
    def assumed_state(self) -> bool:
        """Return whether the switch state is assumed."""
        return self.entity_description.assumed

    @convert_exception
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.state.set(
            self.entity_description.command, self.entity_description.on_value
        )
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.state.set(
            self.entity_description.command, self.entity_description.off_value
        )
        self.async_write_ha_state()
