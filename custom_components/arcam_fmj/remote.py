"""Arcam remote entities."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from enum import Enum
from functools import partial
from typing import Any, override

from arcam.fmj.commands import POWER, SIMULATE_RC5_IR_COMMAND
from arcam.fmj.models import APIVERSION_RC5_NUMERIC_SERIES, ApiModel
from arcam.fmj.rc5 import (
    RC5CODE_COLOR,
    RC5CODE_MENU_ACCESS,
    RC5CODE_NAVIGATION,
    RC5CODE_PLAYBACK,
    RC5CODE_TOGGLE,
    RC5CodeMenuAccess,
)
from arcam.fmj.state import State

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
    RemoteEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator
from .entity import ArcamFmjEntity, convert_exception

PARALLEL_UPDATES = 1

REMOTE_DESCRIPTION = RemoteEntityDescription(
    key="remote",
    translation_key="remote",
)

type RemoteAction = Callable[[], Awaitable[None]]


def _command_name(command: Enum) -> str:
    if command is RC5CodeMenuAccess.LIPSYNC:
        return "lip_sync"
    return command.name.lower()


def _add_rc5_commands[_Command: Enum](
    commands: dict[str, RemoteAction],
    state: State,
    table: Mapping[tuple[ApiModel, int], Mapping[_Command, bytes]],
    sender: Callable[[_Command], Awaitable[None]],
) -> None:
    supported = table.get((state.api_model, state.zn))
    if supported is None:
        return
    commands.update(
        (_command_name(command), partial(sender, command)) for command in supported
    )


def _remote_commands(state: State) -> dict[str, RemoteAction]:
    commands: dict[str, RemoteAction] = {}
    _add_rc5_commands(commands, state, RC5CODE_NAVIGATION, state.send_navigation)
    _add_rc5_commands(commands, state, RC5CODE_PLAYBACK, state.send_playback)
    _add_rc5_commands(commands, state, RC5CODE_TOGGLE, state.send_toggle)
    _add_rc5_commands(commands, state, RC5CODE_MENU_ACCESS, state.send_menu_access)
    _add_rc5_commands(commands, state, RC5CODE_COLOR, state.send_color)
    if state.zn == 1 and state.model in APIVERSION_RC5_NUMERIC_SERIES:
        commands.update(
            (str(digit), partial(state.send_numeric, digit)) for digit in range(10)
        )
    return commands


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ remote entities from a config entry."""
    entities: list[ArcamFmjRemoteEntity] = []
    for coordinator in config_entry.runtime_data.coordinators.values():
        if not coordinator.supports_command(SIMULATE_RC5_IR_COMMAND):
            continue
        commands = _remote_commands(coordinator.state)
        if commands:
            entities.append(ArcamFmjRemoteEntity(coordinator, commands))
    async_add_entities(entities)


class ArcamFmjRemoteEntity(ArcamFmjEntity, RemoteEntity):
    """Representation of an Arcam FMJ remote."""

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        commands: dict[str, RemoteAction],
    ) -> None:
        """Initialize the remote."""
        super().__init__(coordinator, REMOTE_DESCRIPTION)
        self._commands = commands

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the zone is powered on."""
        return self.coordinator.state.get(POWER)

    @convert_exception
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.coordinator.state.set(POWER, True)
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.coordinator.state.set(POWER, False)
        self.async_write_ha_state()

    @convert_exception
    @override
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands supported by the detected model and zone."""
        actions: list[RemoteAction] = []
        for name in command:
            if (action := self._commands.get(name.casefold())) is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_remote_command",
                    translation_placeholders={"command": name},
                )
            actions.append(action)

        num_repeats: int = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay: float = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for repeat in range(num_repeats):
            for action in actions:
                await action()
            if repeat < num_repeats - 1:
                await asyncio.sleep(delay)
