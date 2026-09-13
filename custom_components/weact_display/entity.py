#######################################################################
# Gemeinsame availability-Logik für alle WeAct-Display-Entities
#######################################################################
import custom_components.weact_display.const as const
import logging
_LOGGER = logging.getLogger(__name__)

class WeActAvailabilityMixin:
    _last_available = None  # Klassenattribut als Fallback-Default

    @property
    def available(self) -> bool:
        data = self.hass.data[const.DOMAIN]["devices"].get(self.serial_number, {})
        is_available = data.get("online", False)

        if is_available != self._last_available:
            entity_label = getattr(self, "name", None) or getattr(self, "_attr_name", None) or self.__class__.__name__
            if is_available:
                _LOGGER.debug(f"entity '{entity_label}' for serial {self.serial_number} is available again")
            else:
                _LOGGER.debug(f"entity '{entity_label}' for serial {self.serial_number} became unavailable")
            self._last_available = is_available

        return is_available


