from __future__ import annotations

import voluptuous as vol
import logging
import asyncio
from datetime import datetime, timedelta
from homeassistant import config_entries
from homeassistant.components import usb
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector
from homeassistant.loader import async_get_integration
from .commands import normalize_color
import custom_components.weact_display.const as const

_LOGGER = logging.getLogger(__name__)

class WeActDisplayConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        _LOGGER.debug(f"step-user, user-input={user_input}")

        errors = {}

        # Alle USB-Serial-Devices scannen
        usb_devices = usb.scan_serial_ports()
        if not usb_devices:
            return self.async_abort(reason="no_serial_ports")

        # Bereits konfigurierte Seriennummern
        existing_serials = {
            entry.data.get("serial_number")
            for entry in self._async_current_entries()
        }

        # Auswahl: Anzeige → interne Daten
        devices: dict[str, dict] = {}
        options: dict[str, str] = {}

        # Device Registry zu Rate ziehen
        device_registry = dr.async_get(self.hass)

        for dev in usb_devices:
            _LOGGER.debug(f"dev={dev}")
            serial_number = getattr(dev, "serial_number", None)
            device_path = getattr(dev, "device", None)
            description = getattr(dev, "description", None)
            manufacturer = getattr(dev, "manufacturer", None)

            if not serial_number or not device_path:
                continue
            if serial_number in existing_serials:
                _LOGGER.debug(f"Skipping serial {serial_number}, already configured in weact_display")
                continue

            # Bereits als Device in irgendeiner Integration verwendet ?
            already_registered = False
            for device in device_registry.devices.values():
                for domain, identifier in device.identifiers:
                    if identifier == serial_number:
                        already_registered = True
                        _LOGGER.debug(f"Skipping {serial_number}, already used by integration {domain}")
                        break
                if already_registered:
                    break
            if already_registered:
                continue

            options[device_path] = description
            devices[device_path] = {
                "device_path":   device_path,
                "serial_number": serial_number,
                "description":   description,
                "manufacturer":  manufacturer
            }

            _LOGGER.debug(f"found device: serial={serial_number}, device-path={device_path}, description={description}, options={options}, devices={devices}")

        if not devices:
            return self.async_abort(reason="no_new_devices")

        _LOGGER.debug(f"options={options}, devices={devices}")

        schema = vol.Schema(
            {
                vol.Required("device_path"): vol.In(options),
                vol.Optional("orientation_text", default="landscape"): selector.SelectSelector(selector.SelectSelectorConfig(options=list(const.ORIENTATION_MAP.keys()),mode="dropdown")),
                vol.Optional("brightness", default=const.DEFAULT_BRIGHTNESS): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=255, mode="slider")),
                vol.Optional("background_color", default=[0, 0, 0]): selector.ColorRGBSelector(),
                vol.Optional("screencare", default=True): selector.BooleanSelector(),
                #vol.Optional("fastlz", default=False): selector.BooleanSelector(),
            }
        )

        if user_input is not None:
            device_path               = user_input["device_path"]
            selection                 = devices[device_path]
            serial_number             = selection.get("serial_number")
            brightness                = user_input["brightness"]
            background_color          = user_input["background_color"]
            screencare                = user_input["screencare"]
            #fastlz                    = user_input["fastlz"]
            fastlz                    = False
            orientation_text          = user_input["orientation_text"]
            orientation_value         = const.ORIENTATION_MAP[orientation_text]

            _LOGGER.debug(f"user input: selection={selection}, serial-number={serial_number}, device-path={device_path}, orientation-text={orientation_text}, orientation-value={orientation_value}, brightness={brightness}, background={background_color}, screencare={screencare}, fastlz={fastlz}")

            if not selection.get("device_path"):
                _LOGGER.error("device does not have a device-path")
                errors["base"] = "no_device_path"
                return self.async_show_form(
                    step_id     = "user",
                    data_schema = schema,
                    errors      = errors,
                )

            if not serial_number:
                _LOGGER.error("device does not have a serial-number")
                return self.async_abort(reason="no_serial_number")

            serial_parts = device_path.split("_")
            if len(serial_parts) > 3:
                model = "_".join(serial_parts[3:-1]).replace("_", " ") 
            else:
                model = "unknown"
            _LOGGER.debug(f"serial-parts={serial_parts}, model={model}")

            integration = await async_get_integration(self.hass, const.DOMAIN)
            version = integration.version
            data = {
                "device_path"  : device_path,
                "serial_number": serial_number,
                "model"        : model,
                "setup_dt"     : datetime.now().isoformat(timespec="seconds"),
                "setup_version": version
            }

            _LOGGER.debug(f"data={data}")

            options = {
                "brightness"        : int(brightness),
                "orientation_value" : orientation_value,
                "background_color"  : normalize_color(tuple(background_color)),  # wichtig!
                "screencare"        : screencare,
                "fastlz"            : fastlz
            }

            _LOGGER.debug(f"options={options}")

            _LOGGER.debug(f"setting unique-ID {serial_number}...")
            await self.async_set_unique_id(serial_number)
            _LOGGER.debug("...done !")
            self._abort_if_unique_id_configured()
            _LOGGER.debug("not aborted due to unique-ID is available")

            return self.async_create_entry(
                title = f"WeAct Display {serial_number}",
                data = data,
                options = options
            )

        return self.async_show_form(
            step_id = "user",
            data_schema = schema,
            errors = errors,
            description_placeholders={"info": "please choose one not recognized device to add"},
        )
