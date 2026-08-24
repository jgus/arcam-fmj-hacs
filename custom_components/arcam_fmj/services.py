"""Services for Arcam FMJ devices."""

from typing import Any

from arcam.fmj.commands import SAVE_RESTORE_COPY_OF_SETTINGS
from arcam.fmj.errors import CommandInvalidAtThisTime
from arcam.fmj.state import State
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import (
    DOMAIN,
    SERVICE_RESTORE_SETTINGS,
    SERVICE_SAVE_SETTINGS,
)
from .coordinator import ArcamFmjConfigEntry
from .entity import convert_exception


def _validate_pin(value: Any) -> str:
    pin = cv.string(value)
    if len(pin) != 4 or not pin.isascii() or not pin.isdigit():
        raise vol.Invalid("PIN must contain exactly four digits")
    return pin


_SETTINGS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_PIN): _validate_pin,
    }
)


def _settings_state(call: ServiceCall) -> State:
    entry: ArcamFmjConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    coordinator = entry.runtime_data.coordinators[1]
    if not coordinator.supports_command(SAVE_RESTORE_COPY_OF_SETTINGS):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="settings_backup_unsupported",
        )
    return coordinator.state


def _pin_digits(call: ServiceCall) -> tuple[int, int, int, int]:
    pin: str = call.data[CONF_PIN]
    return (int(pin[0]), int(pin[1]), int(pin[2]), int(pin[3]))


@convert_exception
async def _async_save_settings(call: ServiceCall) -> None:
    await _settings_state(call).save_settings(_pin_digits(call))


@convert_exception
async def _async_restore_settings(call: ServiceCall) -> None:
    try:
        await _settings_state(call).restore_settings(_pin_digits(call))
    except CommandInvalidAtThisTime as exception:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="settings_backup_unavailable",
        ) from exception


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Arcam FMJ services."""
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SAVE_SETTINGS,
        _async_save_settings,
        schema=_SETTINGS_SERVICE_SCHEMA,
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RESTORE_SETTINGS,
        _async_restore_settings,
        schema=_SETTINGS_SERVICE_SCHEMA,
    )
