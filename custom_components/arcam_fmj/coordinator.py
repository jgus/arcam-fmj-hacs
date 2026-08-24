"""Coordinator for Arcam FMJ integration."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
from typing import Any, override

from arcam.fmj.client import Client
from arcam.fmj.codecs import TemperatureSensor
from arcam.fmj.commands import (
    LIFTER_TEMPERATURE,
    OUTPUT_TEMPERATURE,
    SOFTWARE_VERSION,
    SYSTEM_MODEL,
    Command,
    CommandFlags,
    ReadCommand,
)
from arcam.fmj.errors import (
    ConnectionFailed,
    NotConnectedException,
    ResponseException,
)
from arcam.fmj.packets import AmxDuetResponse, ResponsePacket
from arcam.fmj.state import State

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ArcamFmjRuntimeData:
    """Runtime data for Arcam FMJ integration."""

    client: Client
    coordinators: dict[int, "ArcamFmjCoordinator"]


type ArcamFmjConfigEntry = ConfigEntry[ArcamFmjRuntimeData]


class ArcamFmjCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for a single Arcam FMJ zone."""

    config_entry: ArcamFmjConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ArcamFmjConfigEntry,
        client: Client,
        zone: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Arcam FMJ zone {zone}",
        )
        self.client = client
        self.state = State(client, zone)
        self.update_in_progress = False
        self.model: str | None = None
        self._temperature_sensor_2_values: dict[ReadCommand[int], int | None] = {}

        device_name = config_entry.title
        unique_id = config_entry.unique_id or config_entry.entry_id
        unique_id_device = unique_id
        if zone != 1:
            unique_id_device += f"-{zone}"
            device_name += f" Zone {zone}"

        self.device_name = device_name
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id_device)},
            manufacturer="Arcam",
            name=device_name,
        )
        self.zone_unique_id = f"{unique_id}-{zone}"

    def supports_command(self, command: Command[Any]) -> bool:
        """Return whether the discovered model and zone support a command."""
        if self.model is None:
            return False
        if command.version is not None and self.model not in command.version:
            return False
        if self.state.zn != 1 and not command.flags & CommandFlags.ZONE_SUPPORT:
            return False
        return self.state.is_command_supported(command)

    def set_device_metadata(
        self,
        model: str,
        revision: str | None,
        software_version: str | None,
        system_model: str | None,
    ) -> None:
        """Set device information discovered before platform setup."""
        self.model = model
        self.device_info.update(
            model=model,
            hw_version=revision,
            sw_version=software_version,
        )
        if system_model is not None:
            self.device_info["model_id"] = system_model

    def discovered_device_metadata(
        self,
    ) -> tuple[str, str | None, str | None, str | None]:
        """Return device metadata from AMX discovery and typed commands."""
        model = self.state.model
        if model is None:
            raise UpdateFailed("AMX device model unavailable")

        self.model = model
        system_model = (
            self.state.get(SYSTEM_MODEL)
            if self.supports_command(SYSTEM_MODEL)
            else None
        )
        return (
            model,
            self.state.revision,
            self.state.get(SOFTWARE_VERSION),
            system_model,
        )

    def temperature_sensor_2_value(self, command: ReadCommand[int]) -> int | None:
        """Return a coordinator-polled secondary temperature."""
        return self._temperature_sensor_2_values.get(command)

    async def _async_poll_temperature_sensor_2(
        self,
        command: ReadCommand[int],
        read_temperature: Callable[[TemperatureSensor], Awaitable[int | None]],
    ) -> None:
        try:
            value = await read_temperature(TemperatureSensor.SENSOR_2)
        except ResponseException as err:
            _LOGGER.debug("Response error polling %s sensor 2: %s", command, err.ac)
            self._temperature_sensor_2_values[command] = None
        except TimeoutError:
            _LOGGER.error("Timeout polling %s sensor 2", command)
            self._temperature_sensor_2_values[command] = None
        else:
            self._temperature_sensor_2_values[command] = value

    @override
    async def _async_update_data(self) -> None:
        """Fetch data for manual refresh."""
        try:
            self.update_in_progress = True
            await self.state.update()
            if (
                self.state.zn == 1
                and TemperatureSensor.SENSOR_2
                in LIFTER_TEMPERATURE.supported_sensors(self.state.model)
                and self.state.is_command_supported(LIFTER_TEMPERATURE)
            ):
                await self._async_poll_temperature_sensor_2(
                    LIFTER_TEMPERATURE, self.state.get_lifter_temperature
                )
            if (
                self.state.zn == 1
                and TemperatureSensor.SENSOR_2
                in OUTPUT_TEMPERATURE.supported_sensors(self.state.model)
                and self.state.is_command_supported(OUTPUT_TEMPERATURE)
            ):
                await self._async_poll_temperature_sensor_2(
                    OUTPUT_TEMPERATURE, self.state.get_output_temperature
                )
        except (ConnectionFailed, NotConnectedException) as err:
            raise UpdateFailed(
                f"Connection failed during update for zone {self.state.zn}"
            ) from err
        finally:
            self.update_in_progress = False

    @callback
    def _async_notify_packet(self, packet: ResponsePacket | AmxDuetResponse) -> None:
        """Packet callback to detect changes to state."""
        if (
            not isinstance(packet, ResponsePacket)
            or packet.zn != self.state.zn
            or self.update_in_progress
        ):
            return

        self.async_update_listeners()

    @asynccontextmanager
    async def async_monitor_client(self) -> AsyncGenerator[None]:
        """Monitor a client and state for changes while connected."""
        async with self.state:
            self.hass.async_create_task(self.async_refresh())
            try:
                with self.client.listen(self._async_notify_packet):
                    yield
            finally:
                self.hass.async_create_task(self.async_refresh())
