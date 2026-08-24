"""Arcam button entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from arcam.fmj.commands import DAB_SCAN, FM_SCAN, Command
from arcam.fmj.state import State

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
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


async def _fm_scan_up(state: State) -> None:
    await state.fm_scan(up=True)


async def _fm_scan_down(state: State) -> None:
    await state.fm_scan(up=False)


async def _dab_scan(state: State) -> None:
    await state.dab_scan()


@dataclass(frozen=True, kw_only=True)
class ArcamFmjButtonEntityDescription(
    ArcamFmjCommandEntityDescription, ButtonEntityDescription
):
    """Describes an Arcam FMJ button entity."""

    command: Command[Any]
    press_fn: Callable[[State], Awaitable[None]]


BUTTONS: tuple[ArcamFmjButtonEntityDescription, ...] = (
    ArcamFmjButtonEntityDescription(
        key="fm_scan_up",
        command=FM_SCAN,
        translation_key="fm_scan_up",
        press_fn=_fm_scan_up,
    ),
    ArcamFmjButtonEntityDescription(
        key="fm_scan_down",
        command=FM_SCAN,
        translation_key="fm_scan_down",
        press_fn=_fm_scan_down,
    ),
    ArcamFmjButtonEntityDescription(
        key="dab_scan",
        command=DAB_SCAN,
        translation_key="dab_scan",
        press_fn=_dab_scan,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ buttons from a config entry."""
    async_add_entities(
        ArcamFmjButtonEntity(coordinator, description)
        for coordinator in config_entry.runtime_data.coordinators.values()
        for description in supported_entity_descriptions(coordinator, BUTTONS)
    )


class ArcamFmjButtonEntity(ArcamFmjEntity, ButtonEntity):
    """Representation of an Arcam FMJ button."""

    entity_description: ArcamFmjButtonEntityDescription

    @convert_exception
    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.coordinator.state)
