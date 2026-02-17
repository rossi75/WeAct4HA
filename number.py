from __future__ import annotations

import logging
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .commands import set_brightness
import custom_components.weact_display.const as const
from .const import DOMAIN, DEFAULT_BRIGHTNESS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    serial_number = entry.data["serial_number"]
    _LOGGER.debug(f"adding brightness entity and slider for serial {serial_number}")
    async_add_entities([Set_Brightness(hass, serial_number)])

class Set_Brightness(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1

#    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, serial_number: str):
    def __init__(self, hass, serial_number):
        self._hass = hass
#        self._entry = entry
        self.serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_brightness"
        self._attr_name = "Brightness"
#        self._attr_device_info = {
#            "identifiers": {(DOMAIN, serial_number)},
#        }
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {hass.data[const.DOMAIN][serial_number].get("model")}",
        )

        _LOGGER.debug(f"reading actual brightness")

        value = hass.data[const.DOMAIN][serial_number].get("brightness")
        if not isinstance(value, int):
            value = 10
        self._value = value

        _LOGGER.debug(f"init-brightness for serial {self.serial_number} set to {self._value}")

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value_f: float) -> None:
        """Handle slider change."""
        value = max(0, min(255, int(round(value_f))))

        _LOGGER.debug(f"received new brightness [{value}] for serial {self.serial_number}")

        await set_brightness(self.hass, self.serial_number, value)
        self._attr_current_option = self.hass.data[const.DOMAIN][self.serial_number].get("brightness")
        self.async_write_ha_state()
