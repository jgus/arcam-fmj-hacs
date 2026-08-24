"""Arcam component."""

import asyncio
from asyncio import timeout
from contextlib import AsyncExitStack
import logging

from arcam.fmj.client import Client, ClientContext
from arcam.fmj.errors import ConnectionFailed
from arcam.fmj.models import APIVERSION_ZONE2_SERIES

from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DISCOVERY_TIMEOUT
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator, ArcamFmjRuntimeData

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.BINARY_SENSOR, Platform.MEDIA_PLAYER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ArcamFmjConfigEntry) -> bool:
    """Set up config entry."""
    client = Client(entry.data[CONF_HOST], entry.data[CONF_PORT])

    zone1_coordinator = ArcamFmjCoordinator(hass, entry, client, 1)
    try:
        async with timeout(DISCOVERY_TIMEOUT):
            async with ClientContext(client), zone1_coordinator.state:
                await zone1_coordinator.async_config_entry_first_refresh()
        model, revision, software_version, system_model = (
            zone1_coordinator.discovered_device_metadata()
        )
    except (ConnectionFailed, OSError, TimeoutError, UpdateFailed) as err:
        raise ConfigEntryNotReady from err
    zone1_coordinator.set_device_metadata(
        model, revision, software_version, system_model
    )

    coordinators = {1: zone1_coordinator}
    if model in APIVERSION_ZONE2_SERIES:
        zone2_coordinator = ArcamFmjCoordinator(hass, entry, client, 2)
        zone2_coordinator.set_device_metadata(
            model, revision, software_version, system_model
        )
        coordinators[2] = zone2_coordinator

    device_registry = dr.async_get(hass)
    zone1_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **coordinators[1].device_info,
    )
    for zone, coordinator in coordinators.items():
        if zone != 1:
            coordinator.device_info["via_device_id"] = zone1_device.id

    entry.runtime_data = ArcamFmjRuntimeData(client, coordinators)

    entry.async_create_background_task(
        hass,
        _run_client(hass, entry.runtime_data, DEFAULT_SCAN_INTERVAL),
        "arcam_fmj",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArcamFmjConfigEntry) -> bool:
    """Cleanup before removing config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _run_client(
    hass: HomeAssistant,
    runtime_data: ArcamFmjRuntimeData,
    interval: float,
) -> None:
    client = runtime_data.client
    coordinators = runtime_data.coordinators

    while True:
        try:
            async with AsyncExitStack() as stack:
                async with timeout(interval):
                    await client.start()
                stack.push_async_callback(client.stop)

                _LOGGER.debug("Client connected %s", client.host)

                try:
                    for coordinator in coordinators.values():
                        await stack.enter_async_context(
                            coordinator.async_monitor_client()
                        )

                    await client.process()
                finally:
                    _LOGGER.debug("Client disconnected %s", client.host)

        except (ConnectionFailed, OSError):
            pass
        except TimeoutError:
            continue
        except Exception:
            _LOGGER.exception("Unexpected exception, aborting arcam client")
            return

        await asyncio.sleep(interval)
