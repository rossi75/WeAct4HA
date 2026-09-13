import re
import asyncio, datetime, glob, os, logging
import logging
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from .entity import WeActAvailabilityMixin
from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    _LOGGER.debug(f"async_setup_entry for serial-number {entry.data["serial_number"]}")

    serial_number = entry.data["serial_number"]
    device = hass.data[const.DOMAIN]["devices"][serial_number]

    # bestehender Display-Sensor (falls vorhanden)
    entities = []
    entities.append(WeActDisplaySensor(hass, serial_number))

    # HUMITURE optional
    if device.get("humiture") is True:
        _LOGGER.debug(f"Humiture enabled for {serial_number}, adding its sensors")
        entities.append(WeActTemperatureSensor(hass, serial_number))
        entities.append(WeActHumiditySensor(hass, serial_number))
    else:
        _LOGGER.debug(f"no Humiture sensor for {serial_number}, discarding")

    async_add_entities(entities)

class WeActTemperatureSensor(WeActAvailabilityMixin, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = "Temperature"

    def __init__(self, hass, serial_number):
        device = hass.data[const.DOMAIN]["devices"][serial_number]
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_temperature"

        self._attr_device_info = DeviceInfo(
            identifiers = {(const.DOMAIN, serial_number)},
            manufacturer = "WeAct Studio",
            model = f"Display {device.get("model")}",
        )

    @property
    def native_value(self):
        device = self.hass.data[const.DOMAIN]["devices"][self.serial_number]
        value = device.get("temperature")
        if value is None:
            return None
        return round(float(value), 1)


class WeActHumiditySensor(WeActAvailabilityMixin, SensorEntity):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_name = "Humidity"

    def __init__(self, hass, serial_number):
        device = hass.data[const.DOMAIN]["devices"][serial_number]
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_humidity"

        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model=f"Display {device.get('model')}",
        )

    @property
    def native_value(self):
        device = self.hass.data[const.DOMAIN]["devices"][self.serial_number]
        value = device.get("humidity")
        if value is None:
            return None
        return round(float(value))


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):

    _LOGGER.debug("setting up platform Sensors for WeAct Display")

    registry = er.async_get(hass)
    new_sensors = []
    devices = {
        k: v for k, v in hass.data[const.DOMAIN]["devices"].items()
        if k not in ("entries")
    }
    _LOGGER.debug(f"found {len(devices)} displays: {list(devices.keys())}")

    for serial_number, dev in devices.items():
        # prüfen ob sensor existiert
        unique_id = f"weact_display_{serial_number}"
        _LOGGER.debug(f"checking for platform sensor {unique_id}")
        if registry.async_get_entity_id("sensor", const.DOMAIN, unique_id):
            _LOGGER.debug(f"Sensor already exists for {serial_number}, skipping")
            continue
        else:
            _LOGGER.debug(f"adding new platform sensor to device: {serial_number}")
            new_sensors.append(WeActDisplaySensor(hass, serial_number))

    _LOGGER.debug(f"adding {len(new_sensors)} display sensors: {list(new_sensors)}")

    async_add_entities(new_sensors, True)
    for entity in new_sensors:
        hass.data[const.DOMAIN]["devices"][serial_number]["entity"] = entity


class WeActDisplaySensor(WeActAvailabilityMixin, SensorEntity):
    def __init__(self, hass: HomeAssistant, serial_number):
        device = hass.data[const.DOMAIN]["devices"][serial_number]
        self.hass = hass
        self.serial_number = serial_number                                  # damit es für alle Funktionen verfügbar ist
        self._attr_unique_id = serial_number
        model = device["model"]
        self._attr_name = f"WeAct Display {model} {serial_number}"

    # Hauptstatus
    @property
    def state(self):
        device = self.hass.data[const.DOMAIN]["devices"][self.serial_number]
        state = device["state"]
        return state

    # Attribute aus hass.data
    @property
    def extra_state_attributes(self):
        device = self.hass.data[const.DOMAIN]["devices"][self.serial_number]
        attr = {
            "model"            : device.get("model"),
            "serial_number"    : device.get("unique_id"),
            "brightness"       : device.get("brightness"),
            "width"            : device.get("width"),
            "height"           : device.get("height"),
            "orientation"      : const.ORIENTATION_MAP_INV[device.get("orientation_value", 2)],
            "screencare"       : device.get("screencare"),
            "fastlz"           : device.get("fastlz"),
            "clock_mode"       : device.get("clock_mode"),
            "background_color" : device.get("background_color")
        }
        if _LOGGER.getEffectiveLevel() == logging.DEBUG:
            if device.get("humiture") is True:
                attr["dbg_humidity"]         = device.get("humidity")
                attr["dbg_temperature"]      = device.get("temperature")
                attr["dbg_temperature_unit"] = "°C"
            attr["dbg_setup_dt"]             = device.get("setup_dt")
            attr["dbg_setup_version"]        = device.get("setup_version")
            attr["dbg_device_path"]          = device.get("device_path")      # only friendly name, not serial_port with its attributes !!
            attr["dbg_who_am_i"]             = device.get("who_am_i")
            attr["dbg_firmware_version"]     = device.get("firmware_version")
            attr["dbg_orientation_value"]    = device.get("orientation_value")
            attr["dbg_humiture"]             = device.get("humiture")
            attr["dbg_entry_id"]             = device.get("entry_id")
            attr["dbg_device_id"]            = device.get("device_id")
            attr["dbg_start_time"]           = device.get("start_time")
        return attr

    # online ?
    @property
    def available(self) -> bool:
        data = self.hass.data[const.DOMAIN]["devices"].get(self.serial_number, {})
        return data.get("online", False)
