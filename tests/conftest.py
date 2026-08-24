"""Tests for the arcam_fmj component."""

from asyncio import CancelledError, Queue
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

from arcam.fmj.client import Client
from arcam.fmj.commands import (
    INCOMING_AUDIO_SAMPLE_RATE,
    INCOMING_VIDEO_PARAMETERS,
    MUTE,
    POWER,
    VOLUME,
)
from arcam.fmj.packets import ResponsePacket
from arcam.fmj.state import State
import pytest

from custom_components.arcam_fmj.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 50000
MOCK_TURN_ON = {
    "service": "switch.turn_on",
    "data": {"entity_id": "switch.test"},
}
MOCK_ENTITY_ID = "media_player.arcam_fmj_127_0_0_1"
MOCK_UUID = "456789abcdef"
MOCK_UDN = f"uuid:01234567-89ab-cdef-0123-{MOCK_UUID}"
MOCK_NAME = f"{DEFAULT_NAME} ({MOCK_HOST})"
MOCK_CONFIG_ENTRY = {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}


@pytest.fixture(name="client")
def client_fixture() -> Generator[Mock]:
    """Get a mocked client."""
    client = Mock(Client)
    client.host = MOCK_HOST
    client.port = MOCK_PORT

    queue = Queue[BaseException | None]()
    listeners = set()

    async def _start():
        client.connected = True

    async def _process():
        result = await queue.get()
        client.connected = False
        if isinstance(result, BaseException):
            raise result

    @contextmanager
    def _listen(listener):
        listeners.add(listener)
        yield client
        listeners.remove(listener)

    @callback
    def _notify_data_updated(zn=1):
        packet = Mock(ResponsePacket)
        packet.zn = zn
        for listener in listeners:
            listener(packet)

    @callback
    def _notify_connection(exception: Exception | None = None):
        queue.put_nowait(exception)

    client.start.side_effect = _start
    client.process.side_effect = _process
    client.listen.side_effect = _listen
    client.notify_data_updated = _notify_data_updated
    client.notify_connection = _notify_connection

    yield client

    queue.put_nowait(CancelledError())


@pytest.fixture(name="state_1")
def state_1_fixture(client: Mock) -> State:
    """Get a mocked state."""
    state = Mock(State)
    state.client = client
    state.zn = 1
    state.command_values = {
        INCOMING_AUDIO_SAMPLE_RATE: 0,
        INCOMING_VIDEO_PARAMETERS: None,
        MUTE: None,
        POWER: True,
        VOLUME: 0,
    }
    state.get.side_effect = state.command_values.get
    state.get_source.return_value = None
    state.get_source_list.return_value = []
    state.get_incoming_audio_format.return_value = (None, None)
    state.get_decode_modes.return_value = []
    state.get_decode_mode.return_value = None
    state.__aenter__ = AsyncMock()
    state.__aexit__ = AsyncMock()
    return state


@pytest.fixture(name="state_2")
def state_2_fixture(client: Mock) -> State:
    """Get a mocked state."""
    state = Mock(State)
    state.client = client
    state.zn = 2
    state.command_values = {
        INCOMING_AUDIO_SAMPLE_RATE: 0,
        INCOMING_VIDEO_PARAMETERS: None,
        MUTE: None,
        POWER: True,
        VOLUME: 0,
    }
    state.get.side_effect = state.command_values.get
    state.get_source.return_value = None
    state.get_source_list.return_value = []
    state.get_incoming_audio_format.return_value = (None, None)
    state.get_decode_modes.return_value = []
    state.get_decode_mode.return_value = None
    state.__aenter__ = AsyncMock()
    state.__aexit__ = AsyncMock()
    return state


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Get a mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY,
        title=MOCK_NAME,
        unique_id=MOCK_UUID,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="player_setup")
async def player_setup_fixture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
    state_2: State,
    client: Mock,
) -> AsyncGenerator[None]:
    """Get standard player."""

    def state_mock(cli, zone):
        if zone == 1:
            return state_1
        if zone == 2:
            return state_2
        raise ValueError(f"Unknown player zone: {zone}")

    await async_setup_component(hass, "homeassistant", {})

    with (
        patch("custom_components.arcam_fmj.Client", return_value=client),
        patch(
            "custom_components.arcam_fmj.coordinator.State",
            side_effect=state_mock,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield
