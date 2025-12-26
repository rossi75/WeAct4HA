from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from .commands import display_selftest
import custom_components.weact_display.const as const
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    serial_number = entry.data["serial_number"]
    async_add_entities([Button_DisplayTest(hass, serial_number)])
    _LOGGER.debug(f"adding button for display test for serial {serial_number}")


class Button_DisplayTest(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, hass, serial_number):
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_displaytest"
        self._attr_name = "Display Test"

        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {hass.data[const.DOMAIN][self.serial_number].get("model")}",
        )

    async def async_press(self):
        await display_selftest(self.hass, self.serial_number)        
