from homeassistant.components.sensor import SensorEntity
import re
import asyncio, datetime, glob, os, logging
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WeActDisplayStatusSensor(hass)], True)

class WeActDisplayStatusSensor(SensorEntity):
    def __init__(self, hass):
        self._attr_name = "WeAct Display Status"
        self._hass = hass

    @property
    def native_value(self):
        data = self._hass.data.get("weact_display", {})
        return "ready" if data.get("ready") else "initializing"

    @property
    def extra_state_attributes(self):
        data = self._hass.data.get("weact_display", {})
        return {
            "start_time": data.get("start_time"),
            "device_id": data.get("device_id"),
        }

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setzt den WeAct Display Info-Sensor auf."""
    paths = await asyncio.to_thread(glob.glob, "/dev/serial/by-id/*WeAct*")
    if not paths:
        _LOGGER.warning("could not find any WeAct Display")
        return

    path = paths[0]
    serial_name = os.path.basename(path)
    serial_parts = serial_name.split("_")
    model = "_".join(serial_parts[2:-1]).replace("_", " ") if len(serial_parts) > 3 else "Unbekannt"
    serial = serial_parts[-1] if len(serial_parts) > 1 else "n/a"
    serial = re.sub(r"-if\d+$", "", serial)
    start_time = datetime.datetime.now().isoformat(timespec="seconds")
    clock_status = "idle"

#    async_add_entities([WeActDisplayInfoEntity(path, serial, model, start_time)])
    async_add_entities([WeActDisplayInfoEntity(path, serial, model, start_time, clock_status)])


class WeActDisplayInfoEntity(Entity):
    """Entity mit Startzeit und Geräteinformationen."""

#    def __init__(self, path, serial, model, start_time):
    def __init__(self, path, serial, model, start_time, clock_status, width = 160, height = 80, humiture = False):
        self._path = path
        self._serial = serial
        self._model = model
        self._start_time = start_time
        self._clock_status = clock_status
        self._width = width
        self._height = height
        self._humiture_available = humiture

    @property
    def name(self):
        return "WeAct Display Info"

    @property
    def unique_id(self):
        return f"weact_display_{self._serial}"

    @property
    def state(self):
        return "ready"

    @property
    def extra_state_attributes(self):
        return {
            "device_path": self._path,
            "model": self._model,
            "serial": self._serial,
            "start_time": self._start_time,
            "clock_status": self._clock_status,
            "width": self._width,
            "height": self._height,
            "humiture_available": self._humiture_available
        }

    def set_clock_status(self, status):
        """Extern aufrufbar, um den clock_status zu aktualisieren."""
        self._attr_extra_state_attributes["clock_status"] = status
        self.async_write_ha_state()

    def set_resolution(self, px_width, px_height):
        """Extern aufrufbar, um den clock_status zu aktualisieren."""
        self._attr_extra_state_attributes["width"] = px_width
        self._attr_extra_state_attributes["height"] = px_height
        self.async_write_ha_state()
