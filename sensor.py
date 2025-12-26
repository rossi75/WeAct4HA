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
from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    _LOGGER.debug(f"async_setup_entry for serial-number {entry.data["serial_number"]}")

    serial_number = entry.data["serial_number"]
    device = hass.data[const.DOMAIN][serial_number]

    entities = []

    # bestehender Display-Sensor (falls vorhanden)
    entities.append(WeActDisplaySensor(hass, serial_number))

    # 👉 HUMITURE optional
    if device.get("humiture") is True:
        _LOGGER.debug(f"Humiture enabled for {serial_number}, adding its sensors")
        entities.append(WeActTemperatureSensor(hass, serial_number))
        entities.append(WeActHumiditySensor(hass, serial_number))
    else:
        _LOGGER.debug(f"no Humiture sensor for {serial_number}, discarding")

    async_add_entities(entities)

class WeActTemperatureSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = "Temperature"

    def __init__(self, hass, serial_number):
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_temperature"

        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model=f"Display {hass.data[const.DOMAIN][serial_number].get('model')}",
        )

    @property
    def native_value(self):
        try:
            return round(self.hass.data[const.DOMAIN][self.serial_number].get("temperature"), 0)
        except Exception:
            return self.hass.data[const.DOMAIN][self.serial_number].get("temperature")           # Null


class WeActHumiditySensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_name = "Humidity"

    def __init__(self, hass, serial_number):
        self.hass = hass
        self.serial_number = serial_number
        self._attr_unique_id = f"weact_{serial_number}_humidity"

        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, serial_number)},
            manufacturer="WeAct Studio",
            model=f"Display {hass.data[const.DOMAIN][serial_number].get('model')}",
        )

    @property
    def native_value(self):
        try:
            return round(self.hass.data[const.DOMAIN][self.serial_number].get("humidity"), 0)
        except Exception:
            return self.hass.data[const.DOMAIN][self.serial_number].get("humidity")


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):

    _LOGGER.debug("setting up platform Sensors for WeAct Display")

    registry = er.async_get(hass)
    new_sensors = []
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
            new_sensors.append(WeActDisplaySensor(hass, serial_number))

    _LOGGER.debug(f"adding {len(new_sensors)} display sensors: {list(new_sensors)}")

    async_add_entities(new_sensors, True)
    for entity in new_sensors:
        hass.data[const.DOMAIN][serial_number]["entity"] = entity


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
        _LOGGER.debug(f"serial-number={self._serial_number}, orientation-value={data.get("orientation_value")}")
        attr = {
            "model": data.get("model"),
            "serial_number": data.get("serial_number"),
            "width": data.get("width"),
            "height": data.get("height"),
#            "orientation": data.get("orientation"),
            "orientation": const.ORIENTATION_MAP_INV[data.get("orientation_value", 3)],
#            "orientation": const.ORIENTATION_MAP_INV[data.get("orientation_value", "Null")],
            "clock_mode": data.get("clock_mode")
        }
        if data.get("humiture") is True:
            attr["humidity"] = data.get("humidity")
            attr["temperature"] = data.get("temperature")
            attr["temperature_unit"] = "°C"
        if _LOGGER.getEffectiveLevel() == logging.DEBUG:
            attr["dbg_port"] = data.get("port")                                        # only friendly name, not serial_port with its attributes !!
            attr["dbg_who_am_i"] = data.get("who_am_i")
            attr["dbg_firmware_version"] = data.get("firmware_version")
            attr["dbg_orientation_value"] = data.get("orientation_value")
            attr["dbg_humiture"] = data.get("humiture")
            attr["dbg_device_id"] = data.get("device_id")
            attr["dbg_entry_id"] = data.get("entry_id")
        if True:
            attr["dbg_source"] = data.get("source")
            attr["dbg_start_time"] = data.get("start_time")
        return attr

    # online ?
    @property
    def available(self) -> bool:
        data = self.hass.data[const.DOMAIN].get(self._serial_number, {})
        return data.get("online", False)
