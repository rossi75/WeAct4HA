#from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from .commands import set_orientation
from .clock import stop_clock, start_analog_clock, start_digital_clock
from .const import DOMAIN
import custom_components.weact_display.const as const
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    serial_number = entry.data["serial_number"]
    _LOGGER.debug(f"adding screencare switch for serial {serial_number}")
    data = hass.data[DOMAIN]["devices"][serial_number]
    async_add_entities([WeActScreenCareSwitch(hass, entry, data)])

    # für um Updates auch zu erhalten wenn es vom Service gesetzt wird
#    entity = Select_ClockMode(hass, serial_number)
#    async_add_entities([entity])

class WeActScreenCareSwitch(SwitchEntity):

    def __init__(self, hass, entry, data):
        self._hass = hass
        self._serial_number = entry.unique_id
        self._attr_unique_id = f"weact_{self._serial_number}_screencare"
        self._attr_name = "Screen Care"
        self._entry = entry
        self._entry_id = hass.data[const.DOMAIN]["devices"][self._serial_number].get("entry_id")
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, self._serial_number)},
            manufacturer="WeAct Studio",
            model = f"Display {hass.data[const.DOMAIN]["devices"][self._serial_number].get("model")}",
        )

        value = hass.data[const.DOMAIN]["devices"][self._serial_number].get("screencare")
        if not isinstance(value, bool):
            value = True
        self._value = value

        _LOGGER.debug(f"init-screencare for serial {self._serial_number} set to {self._value}")

    @property
    def is_on(self):
        """Return True if entity is on."""
        screencare = self._entry.options.get("screencare")
        return screencare

    # Attribute aus hass.data
    @property
    def extra_state_attributes(self):
        if _LOGGER.getEffectiveLevel() == logging.DEBUG:
            data = self._hass.data[DOMAIN]["devices"].get(self._serial_number, {})
            return {
                "dbg_next_screencare": data.get("screencare_target")
            }
        else:
            return {}
#            data = self._hass.data[const.DOMAIN]["devices"][self._serial_number]
#            attr = {
#                "dbg_screencare_target" : data.get("screencare_target")
#            }

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug(f"enabled screencare for serial {self._serial_number}")
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug(f"disabled screencare for serial {self._serial_number}")
        await self._set_state(False)

    async def _set_state(self, value: bool):          # write into persistent memory
        new_options = {
            **self._entry.options,
            "screencare": value,
        }
        self._hass.config_entries.async_update_entry(
            self._entry,
            options=new_options
        )

        _LOGGER.debug(f"stored new screencare value for serial {self.serial_number} to {self._entry.options.get("screencare")}")
