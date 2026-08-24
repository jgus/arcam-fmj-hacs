"""Arcam text entities."""

from dataclasses import dataclass
from typing import override

from arcam.fmj.commands import FRIENDLY_NAME, ReadWriteCommand

from homeassistant.components.text import TextEntity, TextEntityDescription
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
class ArcamFmjTextEntityDescription(
    ArcamFmjCommandEntityDescription, TextEntityDescription
):
    """Describes an Arcam FMJ text entity."""

    command: ReadWriteCommand[str]


TEXT_ENTITIES: tuple[ArcamFmjTextEntityDescription, ...] = (
    ArcamFmjTextEntityDescription(
        key="friendly_name",
        command=FRIENDLY_NAME,
        translation_key="friendly_name",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ text entities from a config entry."""
    async_add_entities(
        ArcamFmjTextEntity(coordinator, description)
        for coordinator in config_entry.runtime_data.coordinators.values()
        for description in supported_entity_descriptions(coordinator, TEXT_ENTITIES)
    )


class ArcamFmjTextEntity(ArcamFmjEntity, TextEntity):
    """Representation of an Arcam FMJ text entity."""

    entity_description: ArcamFmjTextEntityDescription

    @property
    @override
    def native_value(self) -> str | None:
        """Return the text value."""
        return self.coordinator.state.get(self.entity_description.command)

    @convert_exception
    @override
    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        await self.coordinator.state.set(self.entity_description.command, value)
        self.async_write_ha_state()
