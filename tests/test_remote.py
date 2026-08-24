from collections.abc import Generator
from unittest.mock import call, patch

from arcam.fmj.commands import POWER
from arcam.fmj.rc5 import (
    RC5CodeColor,
    RC5CodeMenuAccess,
    RC5CodeNavigation,
    RC5CodePlayback,
    RC5CodeToggle,
)
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)

REMOTE_ENTITY_ID = "remote.arcam_fmj_127_0_0_1_remote"
ZONE_2_REMOTE_ENTITY_ID = "remote.arcam_fmj_127_0_0_1_zone_2_remote"


@pytest.fixture(autouse=True)
def remote_only() -> Generator[None]:
    with patch("custom_components.arcam_fmj.PLATFORMS", [Platform.REMOTE]):
        yield


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_model", "expected_entities"),
    [
        ("AVR20", {REMOTE_ENTITY_ID, ZONE_2_REMOTE_ENTITY_ID}),
        ("AVR450", {REMOTE_ENTITY_ID, ZONE_2_REMOTE_ENTITY_ID}),
        ("SA30", {REMOTE_ENTITY_ID}),
        ("ST60", set()),
        ("PA720", set()),
    ],
    indirect=["device_model"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_model_and_zone_support(
    hass: HomeAssistant,
    expected_entities: set[str],
) -> None:
    assert {
        state.entity_id for state in hass.states.async_all(REMOTE_DOMAIN)
    } == expected_entities


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_send_commands(hass: HomeAssistant, state_1: State) -> None:
    navigation = [
        ("up", RC5CodeNavigation.UP),
        ("down", RC5CodeNavigation.DOWN),
        ("left", RC5CodeNavigation.LEFT),
        ("right", RC5CodeNavigation.RIGHT),
        ("ok", RC5CodeNavigation.OK),
        ("menu", RC5CodeNavigation.MENU),
        ("home", RC5CodeNavigation.HOME),
        ("return", RC5CodeNavigation.RETURN),
    ]
    playback = [
        ("play", RC5CodePlayback.PLAY),
        ("pause", RC5CodePlayback.PAUSE),
        ("stop", RC5CodePlayback.STOP),
        ("skip_forward", RC5CodePlayback.SKIP_FORWARD),
        ("skip_back", RC5CodePlayback.SKIP_BACK),
        ("fast_forward", RC5CodePlayback.FAST_FORWARD),
        ("rewind", RC5CodePlayback.REWIND),
        ("random", RC5CodePlayback.RANDOM),
        ("repeat", RC5CodePlayback.REPEAT),
        ("eject", RC5CodePlayback.EJECT),
    ]
    toggles = [
        ("standby", RC5CodeToggle.STANDBY),
        ("mute", RC5CodeToggle.MUTE),
        ("mode", RC5CodeToggle.MODE),
        ("info", RC5CodeToggle.INFO),
        ("display_brightness", RC5CodeToggle.DISPLAY_BRIGHTNESS),
        ("direct_mode", RC5CodeToggle.DIRECT_MODE),
        ("dolby_audio", RC5CodeToggle.DOLBY_AUDIO),
        ("room_eq", RC5CodeToggle.ROOM_EQ),
        ("radio", RC5CodeToggle.RADIO),
        ("dts_dialog_control", RC5CodeToggle.DTS_DIALOG_CONTROL),
        ("follow_zone_1", RC5CodeToggle.FOLLOW_ZONE_1),
        ("next_zone", RC5CodeToggle.NEXT_ZONE),
    ]
    menu_access = [
        ("bass", RC5CodeMenuAccess.BASS),
        ("treble", RC5CodeMenuAccess.TREBLE),
        ("lip_sync", RC5CodeMenuAccess.LIPSYNC),
        ("sub_trim", RC5CodeMenuAccess.SUB_TRIM),
        ("speaker_trim", RC5CodeMenuAccess.SPEAKER_TRIM),
    ]
    colors = [
        ("red", RC5CodeColor.RED),
        ("green", RC5CodeColor.GREEN),
        ("yellow", RC5CodeColor.YELLOW),
        ("blue", RC5CodeColor.BLUE),
    ]
    digits = [str(digit) for digit in range(10)]
    commands = [
        name
        for group in (navigation, playback, toggles, menu_access)
        for name, _ in group
    ]
    commands.extend(digits)
    commands.extend(name for name, _ in colors)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
            ATTR_COMMAND: commands,
        },
        blocking=True,
    )

    state_1.send_navigation.assert_has_awaits(
        [call(command) for _, command in navigation]
    )
    state_1.send_playback.assert_has_awaits([call(command) for _, command in playback])
    state_1.send_toggle.assert_has_awaits([call(command) for _, command in toggles])
    state_1.send_menu_access.assert_has_awaits(
        [call(command) for _, command in menu_access]
    )
    state_1.send_numeric.assert_has_awaits([call(digit) for digit in range(10)])
    state_1.send_color.assert_has_awaits([call(command) for _, command in colors])


@pytest.mark.parametrize("device_model", ["AVR450"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_cycle_output_resolution(hass: HomeAssistant, state_1: State) -> None:
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
            ATTR_COMMAND: "cycle_output_resolution",
        },
        blocking=True,
    )

    state_1.send_toggle.assert_awaited_once_with(RC5CodeToggle.CYCLE_OUTPUT_RESOLUTION)


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_repeat_and_case_insensitive_command(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
            ATTR_COMMAND: "Play",
            ATTR_NUM_REPEATS: 2,
            ATTR_DELAY_SECS: 0,
        },
        blocking=True,
    )

    state_1.send_playback.assert_has_awaits(
        [call(RC5CodePlayback.PLAY), call(RC5CodePlayback.PLAY)]
    )


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_reject_unsupported_command_before_sending(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["up", "cycle_output_resolution"],
            },
            blocking=True,
        )

    state_1.send_navigation.assert_not_awaited()
    state_1.send_toggle.assert_not_awaited()


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_reject_zone_2_command(
    hass: HomeAssistant,
    state_2: State,
) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: ZONE_2_REMOTE_ENTITY_ID,
                ATTR_COMMAND: "up",
            },
            blocking=True,
        )

    state_2.send_navigation.assert_not_awaited()


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_zone_2_commands(
    hass: HomeAssistant,
    state_2: State,
) -> None:
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: ZONE_2_REMOTE_ENTITY_ID,
            ATTR_COMMAND: ["mute", "next_zone"],
        },
        blocking=True,
    )

    state_2.send_toggle.assert_has_awaits(
        [call(RC5CodeToggle.MUTE), call(RC5CodeToggle.NEXT_ZONE)]
    )


@pytest.mark.parametrize("device_model", ["AVR20"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_power(hass: HomeAssistant, state_1: State) -> None:
    for service in (SERVICE_TURN_OFF, SERVICE_TURN_ON):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: REMOTE_ENTITY_ID},
            blocking=True,
        )

    state_1.set.assert_has_awaits([call(POWER, False), call(POWER, True)])
