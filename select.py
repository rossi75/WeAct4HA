from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from .commands import set_orientation
from .clock import stop_clock, start_analog_clock, start_digital_clock
import custom_components.weact_display.const as const
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    serial_number = entry.data["serial_number"]
    _LOGGER.debug(f"adding orientation select for serial {serial_number}")
    async_add_entities([Select_Orientation(hass, serial_number)])
    _LOGGER.debug(f"adding clock mode select for serial {serial_number}")
    async_add_entities([Select_ClockMode(hass, serial_number)])


class Select_Orientation(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Orientation"
    _attr_options = [
        name for name, _ in sorted(
            const.ORIENTATION_MAP.items(), key=lambda i: i[1]
        )
    ]

    _LOGGER.debug(f"found {len(_attr_options)} orientation options: {list(_attr_options)}")

    def __init__(self, hass, serial_number):
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_orientation"
        self._attr_name = "Orientation"

        _LOGGER.debug(f"reading actual orientation")

        value = hass.data[const.DOMAIN][serial_number].get("orientation_value")
        if not isinstance(value, int) or value not in const.ORIENTATION_MAP_INV:
            value = 0  # Default: Portrait
        self._value = value
        self._attr_current_option = const.ORIENTATION_MAP_INV[value]

        _LOGGER.debug(f"init-orientation for serial {self.serial_number} set to {self._attr_current_option} [{self._value}]")

        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {hass.data[const.DOMAIN][serial_number].get("model")}",
        )

    async def async_select_option(self, option: str):
        _LOGGER.debug(f"received any new orientation")
        value = const.ORIENTATION_MAP[option]

        _LOGGER.debug(f"received new orientation {option} [{value}] for serial {self.serial_number}")

        await set_orientation(self.hass, self.serial_number, value)

        self._attr_current_option = const.ORIENTATION_MAP_INV[self.hass.data[const.DOMAIN][self.serial_number].get("orientation_value")]
        self.async_write_ha_state()


class Select_ClockMode(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Clock Mode"
    _attr_options = ["idle", "digital", "analog"]

    def __init__(self, hass, serial_number):
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_clock"
        self._attr_name = "Clock Mode"
        self._attr_current_option = hass.data[const.DOMAIN][serial_number].get("clock_mode", "idle")
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {hass.data[const.DOMAIN][serial_number].get("model")}",
        )

    async def async_select_option(self, option: str):
        _LOGGER.debug(f"received clock-mode {option} for serial {self.serial_number}")
        if option == "analog":
            await start_analog_clock(self.hass, self.serial_number)
        elif option == "digital":
            await start_digital_clock(self.hass, self.serial_number)
        elif option == "rheinturm":
            start_rheinturm(self.hass, self.serial_number)
        elif option == "idle":
            await stop_clock(self.hass, self.serial_number)
            



