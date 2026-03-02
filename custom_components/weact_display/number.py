from __future__ import annotations

import logging
from homeassistant.components.number import NumberEntity, NumberMode
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

    def __init__(self, hass, serial_number):
        self._hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_brightness"
        self._attr_name = "Brightness"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 255
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {hass.data[const.DOMAIN][serial_number].get("model")}",
        )

        value = hass.data[const.DOMAIN][serial_number].get("brightness")
        if not isinstance(value, int):
            value = DEFAULT_BRIGHTNESS
        self._value = value

        _LOGGER.debug(f"init-brightness for serial {self.serial_number} set to {self._value}")

    @property
    def native_value(self):
        return self.hass.data[DOMAIN][self.serial_number].get("brightness")

    async def async_set_native_value(self, value_f: float) -> None:
        """Handle slider change."""
        value = max(0, min(255, int(round(value_f))))

        _LOGGER.debug(f"received new target brightness {value} for serial {self.serial_number}")

        await set_brightness(self.hass, self.serial_number, value)
