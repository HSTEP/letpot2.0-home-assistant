"""The LetPot integration."""

import asyncio
import math

from letpot.client import LetPotClient
from letpot.converters import CONVERTERS, ISEConverter
from letpot.deviceclient import LetPotDeviceClient
from letpot.exceptions import LetPotAuthenticationException, LetPotException
from letpot.models import AuthenticationInfo, LetPotDeviceStatus, LetPotWateringSystemStatus

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Monkey-patch the library's ISEConverter.get_update_status_message to correct
# the bug in the parameter byte order (pump_cycle_on was incorrectly placed before
# pump_manual_duration, causing values to corrupt each other during write commands).
def _patched_get_update_status_message(self, status: LetPotDeviceStatus) -> list[int]:
    if not isinstance(status, LetPotWateringSystemStatus):
        raise TypeError("Expected LetPotWateringSystemStatus")
    return [
        65,
        2,
        1 if status.pump_mode > 0 else 0,
        math.floor((status.pump_manual_duration or 0) / 256),
        (status.pump_manual_duration or 0) % 256,
        1 if status.pump_cycle_on is True else 0,
        math.floor((status.pump_cycle_frequency or 0) / 256),
        (status.pump_cycle_frequency or 0) % 256,
        math.floor((status.pump_cycle_duration or 0) / 256),
        (status.pump_cycle_duration or 0) % 256,
        status.pump_cycle_mode or 0,
        math.floor((status.pump_cycle_workinginterval or 0) / 256),
        (status.pump_cycle_workinginterval or 0) % 256,
        math.floor((status.pump_cycle_restinterval or 0) / 256),
        (status.pump_cycle_restinterval or 0) % 256,
    ]

ISEConverter.get_update_status_message = _patched_get_update_status_message


from .const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_USER_ID,
)
from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: LetPotConfigEntry) -> bool:
    """Set up LetPot from a config entry."""

    auth = AuthenticationInfo(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        access_token_expires=entry.data[CONF_ACCESS_TOKEN_EXPIRES],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        refresh_token_expires=entry.data[CONF_REFRESH_TOKEN_EXPIRES],
        user_id=entry.data[CONF_USER_ID],
        email=entry.data[CONF_EMAIL],
    )
    websession = async_get_clientsession(hass)
    client = LetPotClient(websession, auth)

    if not auth.is_valid:
        try:
            auth = await client.refresh_token()
            hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_ACCESS_TOKEN: auth.access_token,
                    CONF_ACCESS_TOKEN_EXPIRES: auth.access_token_expires,
                    CONF_REFRESH_TOKEN: auth.refresh_token,
                    CONF_REFRESH_TOKEN_EXPIRES: auth.refresh_token_expires,
                    CONF_USER_ID: auth.user_id,
                    CONF_EMAIL: auth.email,
                },
            )
        except LetPotAuthenticationException as exc:
            raise ConfigEntryAuthFailed from exc

    try:
        devices = await client.get_devices()
    except LetPotAuthenticationException as exc:
        raise ConfigEntryAuthFailed from exc
    except LetPotException as exc:
        raise ConfigEntryNotReady from exc

    device_client = LetPotDeviceClient(auth)

    coordinators: list[LetPotDeviceCoordinator[LetPotDeviceStatus]] = [
        LetPotDeviceCoordinator[LetPotDeviceStatus](hass, entry, device, device_client)
        for device in devices
        if any(
            converter.supports_type(device.device_type)
            for converter in CONVERTERS
        )
    ]

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LetPotConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        for coordinator in entry.runtime_data:
            await coordinator.device_client.unsubscribe(
                coordinator.device.serial_number
            )
    return unload_ok
