from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from .commands import set_orientation
from .entity import WeActAvailabilityMixin
import custom_components.weact_display.const as const
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    serial_number = entry.data["serial_number"]
    _LOGGER.debug(f"adding screencare switch for serial {serial_number}")
    async_add_entities([WeActScreenCareSwitch(hass, entry)])
    _LOGGER.debug(f"adding fastlz switch for serial {serial_number}")
    async_add_entities([WeActFastLZSwitch(hass, entry)])

class WeActScreenCareSwitch(WeActAvailabilityMixin, SwitchEntity):

    def __init__(self, hass, entry):
        self.hass = hass
        self.serial_number = entry.unique_id
        self._attr_unique_id = f"weact_{self.serial_number}_screencare"
        self._attr_name = "Screencare"
        self._entry = entry
        device = hass.data[const.DOMAIN]["devices"][self.serial_number]
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, self.serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {device.get("model")}",
        )

        screencare = device.get("screencare")
        if not isinstance(screencare, bool):
            screencare = True
        self.value = screencare

        _LOGGER.debug(f"init-screencare for serial {self.serial_number} set to {self.value}")

    @property
    def is_on(self):
        """Return True if entity is on."""
        screencare = self._entry.options.get("screencare")
        return screencare

    # Attribute aus hass.data
    @property
    def extra_state_attributes(self):
        device = self.hass.data[const.DOMAIN]["devices"][self.serial_number]
        screencare = device.get("screencare")
        if screencare is True:
            return {"next_screencare" : device.get("screencare_target")}
        else:
            return {}

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug(f"enabled screencare for serial {self.serial_number}")
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug(f"disabled screencare for serial {self.serial_number}")
        await self._set_state(False)

    async def _set_state(self, value: bool):          # write into persistent memory
        device = self.hass.data[const.DOMAIN]["devices"][self.serial_number]
        new_options = {
            **self._entry.options,
            "screencare": value,
        }
        self.hass.config_entries.async_update_entry(
            self._entry,
            options=new_options
        )
        device["screencare"] = value

        _LOGGER.debug(f"stored new screencare option for serial {self.serial_number} to {self._entry.options.get("screencare")}")


class WeActFastLZSwitch(WeActAvailabilityMixin, SwitchEntity):

    def __init__(self, hass, entry):
        self.hass = hass
        self.serial_number = entry.unique_id
        self._attr_unique_id = f"weact_{self.serial_number}_fastlz"
        self._attr_name = "FastLZ"
        self._entry = entry
        device = hass.data[const.DOMAIN]["devices"][self.serial_number]
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, self.serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {device.get("model")}",
        )

        fastlz = device.get("fastlz")
        if not isinstance(fastlz, bool):
            fastlz = False
        self.value = fastlz

        _LOGGER.debug(f"init-fastlz for serial {self.serial_number} set to {self.value}")

    @property
    def is_on(self):
        """Return True if entity is on."""
        fastlz = self._entry.options.get("fastlz")
        return fastlz

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug(f"enabled fastlz for serial {self.serial_number}")
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug(f"disabled fastlz for serial {self.serial_number}")
        await self._set_state(False)

    async def _set_state(self, value: bool):          # write into persistent memory
        device = self._hass.data[const.DOMAIN]["devices"][self.serial_number]
        new_options = {
            **self._entry.options,
            "fastlz": value,
        }
        self.hass.config_entries.async_update_entry(
            self._entry,
            options=new_options
        )
        device["fastlz"] = value
        _LOGGER.debug(f"stored new fastlz option for serial {self.serial_number} to {self._entry.options.get("fastlz")}")
