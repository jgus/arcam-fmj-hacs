from pathlib import Path

from arcam.fmj.errors import CommandInvalidAtThisTime, NotConnectedException
from arcam.fmj.state import State
import pytest
import voluptuous as vol

from custom_components.arcam_fmj.const import (
    DOMAIN,
    SERVICE_RESTORE_SETTINGS,
    SERVICE_SAVE_SETTINGS,
)
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_PIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.util.yaml.loader import load_yaml

from pytest_homeassistant_custom_component.common import MockConfigEntry

SERVICES_PATH = (
    Path(__file__).parents[1] / "custom_components" / "arcam_fmj" / "services.yaml"
)


def _service_data(
    config_entry: MockConfigEntry,
    **values: object,
) -> dict[str, object]:
    return {
        ATTR_CONFIG_ENTRY_ID: config_entry.entry_id,
        CONF_PIN: "0123",
        **values,
    }


@pytest.mark.usefixtures("player_setup")
async def test_services_and_descriptions(
    hass: HomeAssistant,
) -> None:
    assert hass.services.has_service(DOMAIN, SERVICE_SAVE_SETTINGS)
    assert hass.services.has_service(DOMAIN, SERVICE_RESTORE_SETTINGS)

    descriptions = load_yaml(SERVICES_PATH)
    save_fields = descriptions[SERVICE_SAVE_SETTINGS]["fields"]
    restore_fields = descriptions[SERVICE_RESTORE_SETTINGS]["fields"]

    assert save_fields[CONF_PIN]["selector"] == {"text": {"type": "password"}}
    assert restore_fields[CONF_PIN]["selector"] == {"text": {"type": "password"}}


@pytest.mark.usefixtures("player_setup")
async def test_save_and_restore_settings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_SETTINGS,
        _service_data(mock_config_entry),
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTORE_SETTINGS,
        _service_data(mock_config_entry),
        blocking=True,
    )

    state_1.save_settings.assert_awaited_once_with((0, 1, 2, 3))
    state_1.restore_settings.assert_awaited_once_with((0, 1, 2, 3))


@pytest.mark.parametrize("pin", ["", "123", "12345", "12a4", "１２３４"])
@pytest.mark.usefixtures("player_setup")
async def test_pin_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pin: str,
) -> None:
    with pytest.raises(vol.Invalid, match="PIN must contain exactly four digits"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_SETTINGS,
            _service_data(mock_config_entry, **{CONF_PIN: pin}),
            blocking=True,
        )


@pytest.mark.parametrize("device_model", ["SA30"], indirect=True)
@pytest.mark.usefixtures("player_setup")
async def test_unsupported_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_SETTINGS,
            _service_data(mock_config_entry),
            blocking=True,
        )

    assert error.value.translation_key == "settings_backup_unsupported"
    state_1.save_settings.assert_not_awaited()


@pytest.mark.usefixtures("player_setup")
async def test_restore_without_backup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    state_1.restore_settings.side_effect = CommandInvalidAtThisTime()

    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTORE_SETTINGS,
            _service_data(mock_config_entry),
            blocking=True,
        )

    assert error.value.translation_key == "settings_backup_unavailable"


@pytest.mark.usefixtures("player_setup")
async def test_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    state_1.save_settings.side_effect = NotConnectedException()

    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_SETTINGS,
            _service_data(mock_config_entry),
            blocking=True,
        )

    assert error.value.translation_key == "connection_failed"


@pytest.mark.usefixtures("player_setup")
async def test_services_require_admin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    await hass.auth.async_create_user("Admin", group_ids=[GROUP_ID_ADMIN])
    user = await hass.auth.async_create_user("User", group_ids=[GROUP_ID_USER])

    for action, data in (
        (SERVICE_SAVE_SETTINGS, _service_data(mock_config_entry)),
        (SERVICE_RESTORE_SETTINGS, _service_data(mock_config_entry)),
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                action,
                data,
                blocking=True,
                context=Context(user_id=user.id),
            )

    state_1.save_settings.assert_not_awaited()
    state_1.restore_settings.assert_not_awaited()
