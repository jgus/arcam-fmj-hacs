"""Tests for the Arcam FMJ config entry setup."""

from asyncio import CancelledError, StreamReader, StreamWriter
from contextlib import suppress
from unittest.mock import Mock, patch

from arcam.fmj.commands import (
    INCOMING_VIDEO_PARAMETERS,
    SOFTWARE_VERSION,
    SYSTEM_MODEL,
)
from arcam.fmj.errors import ConnectionFailed
from arcam.fmj.models import APIVERSION_ZONE2_SERIES
from arcam.fmj.server import Server, ServerContext
import pytest

from custom_components.arcam_fmj import _run_client
from custom_components.arcam_fmj.const import DOMAIN
from custom_components.arcam_fmj.coordinator import ArcamFmjRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from conftest import MOCK_DEVICE_REVISION, MOCK_SOFTWARE_VERSION, MOCK_UUID

from pytest_homeassistant_custom_component.common import MockConfigEntry


class _CleanDisconnectServer(Server):
    async def process(self, reader: StreamReader, writer: StreamWriter) -> None:
        with suppress(ConnectionFailed):
            await super().process(reader, writer)


async def test_client_retries_connection_error(
    hass: HomeAssistant,
    client: Mock,
) -> None:
    client.start.side_effect = [ConnectionRefusedError(), CancelledError()]

    with pytest.raises(CancelledError):
        await _run_client(hass, ArcamFmjRuntimeData(client, {}), 0)

    assert client.start.await_count == 2


@pytest.mark.usefixtures("player_setup")
async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the zone 2 device links to the zone 1 device via via_device_id."""
    zone1_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UUID), mock_config_entry.entry_id
    )
    assert zone1_device is not None

    zone2_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_UUID}-2"), mock_config_entry.entry_id
    )
    assert zone2_device is not None
    assert zone2_device.via_device_id == zone1_device.id


@pytest.mark.usefixtures("player_setup")
async def test_device_information(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device information from AMX and software version discovery."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UUID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Arcam"
    assert device.model == "AVR20"
    assert device.model_id is None
    assert device.hw_version == MOCK_DEVICE_REVISION
    assert device.sw_version == MOCK_SOFTWARE_VERSION


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_system_model_device_information(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test supported system model information and single-zone discovery."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UUID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "SA30"
    assert device.model_id == "SA30 system model"
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{MOCK_UUID}-2"), mock_config_entry.entry_id
        )
        is None
    )


@pytest.mark.parametrize("device_model", [None], indirect=True)
async def test_setup_retries_without_amx_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: Mock,
    client: Mock,
) -> None:
    """Test platform setup waits for an AMX model."""

    with (
        patch("custom_components.arcam_fmj.Client", return_value=client),
        patch("custom_components.arcam_fmj.coordinator.State", return_value=state_1),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("player_setup")
async def test_command_zone_support(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test command support uses discovered model and zone metadata."""
    coordinators = mock_config_entry.runtime_data.coordinators
    assert "AVR20" in APIVERSION_ZONE2_SERIES
    assert coordinators[1].supports_command(INCOMING_VIDEO_PARAMETERS)
    assert not coordinators[2].supports_command(INCOMING_VIDEO_PARAMETERS)


async def test_discovery_with_library_client(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    socket_enabled: None,
    unused_tcp_port: int,
) -> None:
    """Test discovery using the library client, state, and fake device."""
    server = _CleanDisconnectServer("127.0.0.1", unused_tcp_port, "SA30")
    server.register_handler(
        1, SOFTWARE_VERSION.cc, b"\xf0", lambda **kwargs: b"\x04\x05"
    )
    server.register_handler(
        1, SYSTEM_MODEL.cc, b"\xf0", lambda **kwargs: b"SA30 integrated amplifier"
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: unused_tcp_port},
        title="Arcam SA30",
        unique_id="sa30",
    )
    config_entry.add_to_hass(hass)

    async with ServerContext(server):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "sa30"), config_entry.entry_id
        )
        assert device is not None
        assert device.model == "SA30"
        assert device.model_id == "SA30 integrated amplifier"
        assert device.hw_version == "x.y.z"
        assert device.sw_version == "4.5"

        assert await hass.config_entries.async_unload(config_entry.entry_id)
