from homeassistant.helpers.entity import Entity
import re
import asyncio, datetime, glob, os, logging
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers import entity_registry as er
from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    _LOGGER.warning("called async_setup_entry, for later with config flow")

# Initialisiert den Sensor für das WeAct Display
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
#async def async_setup_platform(hass, config, async_add_entities, discovery_info | None = None):
    _LOGGER.debug("setting up platform Sensors for WeAct Display")

    registry = er.async_get(hass)
    sensors = []
    devices = hass.data[const.DOMAIN]

    _LOGGER.debug(f"found {len(devices)} displays: {list(devices.keys())}")

    for serial_number, dev in devices.items():
        # prüfen ob sensor existiert
        unique_id = f"weact_display_{serial_number}"
        _LOGGER.debug(f"checking for platform sensor {unique_id}")
        if registry.async_get_entity_id("sensor", const.DOMAIN, unique_id):
            _LOGGER.debug(f"Sensor already exists for {serial_number}, skipping")
            continue
        else:
            _LOGGER.debug(f"adding new platform sensor to list: {serial_number}")
            sensors.append(WeActDisplaySensor(hass, serial_number))

    _LOGGER.debug(f"adding {len(sensors)} display sensors: {list(sensors)}")

    async_add_entities(sensors, True)

class WeActDisplaySensor(SensorEntity):
    # Ein Sensor pro Display. Enthält alle Attribute
    def __init__(self, hass: HomeAssistant, serial_number):
        self._hass = hass
        self._attr_unique_id = serial_number
        model = self._hass.data[const.DOMAIN][serial_number]["model"]
        self._attr_name = f"WeAct Display {model} {serial_number}"
        self._serial_number = serial_number                                  # damit es für alle Funktionen verfügbar ist

    # Hauptstatus
    @property
    def state(self):
        state = self._hass.data[const.DOMAIN][self._serial_number]["state"]
        return state

    # Attribute aus hass.data
    @property
    def extra_state_attributes(self):
        data = self._hass.data[const.DOMAIN][self._serial_number]
        attr = {
            "port": data.get("port"),                      #                  # only friendly name, not serial_port with its attributes !!
            "model": data.get("model"),
            "serial_number": data.get("serial_number"),
            "start_time": data.get("start_time"),          #
            "width": data.get("width"),
            "height": data.get("height"),
            "orientation": data.get("orientation"),
            "humiture": data.get("humiture"),              #
            "clock_mode": data.get("clock_mode")
        }
        if data.get("humiture") is True:
            attr["humidity"] = data.get("humidity")
            attr["temperature"] = data.get("temperature")
            attr["temperature_unit"] = data.get("temperature_unit")
#        if _LOGGER.getEffectiveLevel() == logging.DEBUG:
#            attr["port"] = data.get("port")                                        # only friendly name, not serial_port with its attributes !!
#            attr["start_time"] = data.get("start_time")
#            attr["orientation_value"] = data.get("orientation_value")
#            attr["humiture"] = data.get("humiture")
        return attr
