"""Base entity for Arcam FMJ integration."""

from collections.abc import Callable, Coroutine, Iterable, Iterator
from dataclasses import dataclass
import functools
import logging
from typing import Any, override

from arcam.fmj.commands import Command
from arcam.fmj.errors import ConnectionFailed, NotConnectedException
from arcam.fmj.models import IntOrTypeEnum

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArcamFmjCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ArcamFmjCommandEntityDescription(EntityDescription):
    """Associates an entity description with an Arcam command."""

    command: Command[Any]


def enum_options(value: type[IntOrTypeEnum]) -> list[str]:
    """Return Home Assistant options for known protocol enum values."""
    return [
        member.name.lower() for member in value if not member.name.startswith("CODE_")
    ]


def enum_options_for_model(
    value: type[IntOrTypeEnum], model: str | None
) -> dict[str, IntOrTypeEnum]:
    """Return writable Home Assistant options supported by a model."""
    options: dict[str, IntOrTypeEnum] = {}
    for member in value:
        if member.name.startswith("CODE_") or (
            member.version is not None and model not in member.version
        ):
            continue
        try:
            member.to_bytes_for_model(model)
        except ValueError:
            continue
        options[member.name.lower()] = member
    return options


def enum_value(value: IntOrTypeEnum | None) -> str | None:
    """Convert a protocol enum value to a Home Assistant state."""
    if value is None:
        return None

    if value.name.startswith("CODE_"):
        _LOGGER.debug("Undefined enum value %s ignored", value)
        return None

    return value.name.lower()


def supported_entity_descriptions[
    _Description: ArcamFmjCommandEntityDescription,
](
    coordinator: ArcamFmjCoordinator,
    descriptions: Iterable[_Description],
) -> Iterator[_Description]:
    """Iterate entity descriptions supported by a coordinator."""
    return (
        description
        for description in descriptions
        if coordinator.supports_command(description.command)
    )


def convert_exception[**_P, _R](
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Convert a connection failure into a translated HomeAssistantError."""

    @functools.wraps(func)
    async def _convert_exception(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except (ConnectionFailed, NotConnectedException) as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_failed"
            ) from exception

    return _convert_exception


class ArcamFmjEntity(CoordinatorEntity[ArcamFmjCoordinator]):
    """Base entity for Arcam FMJ."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_entity_registry_enabled_default = coordinator.state.zn == 1
        self._attr_unique_id = coordinator.zone_unique_id
        if description is not None:
            self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
            self.entity_description = description
        self._command = (
            description.command
            if isinstance(description, ArcamFmjCommandEntityDescription)
            else None
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available or not self.coordinator.client.connected:
            return False
        if self._command is None:
            return True
        return self.coordinator.supports_command(
            self._command
        ) and self.coordinator.state.supported_on_source(self._command)
