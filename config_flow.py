from __future__ import annotations

import voluptuous as vol
import logging
import asyncio
from homeassistant import config_entries
from homeassistant.components import usb
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class WeActDisplayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
            # Robust: Objekt oder Dict
            serial = getattr(dev, "serial_number", None)
            device_path = getattr(dev, "device", None)
            description = getattr(dev, "description", None)
            manufacturer = getattr(dev, "manufacturer", None),

            if not serial or not device_path:
                continue
            if serial in existing_serials:
                _LOGGER.debug(f"Skipping serial {serial}, already configured in weact_display")
                continue

            # Bereits als Device in irgendeiner Integration verwendet ?
            already_registered = False
            for device in device_registry.devices.values():
                for domain, identifier in device.identifiers:
                    if identifier == serial:
                        already_registered = True
                        _LOGGER.debug(f"Skipping {serial}, already used by integration {domain}")
                        break
                if already_registered:
                    break
            if already_registered:
                continue

            options[device_path] = description
            devices[device_path] = {
                "device": device_path,
                "device_path": device_path,
                "serial_number": serial,
                "description": description,
                "manufacturer": manufacturer,
            }

            _LOGGER.debug(f"serial={serial}, device-path={device_path}, description={description}, options={options}, devices={devices}")

        if not devices:
            return self.async_abort(reason="no_new_devices")

        _LOGGER.debug(f"options={options}, devices={devices}")

# ~~~
        schema = vol.Schema(
            {
                vol.Required("device_path"): vol.In(options)
            }
        )
# ~~~

        if user_input is not None:
            device_path = user_input["device_path"]
            selection = devices[device_path]
            serial = selection.get("serial_number")

            _LOGGER.debug(f"selection={selection}, serial={serial}, device-path={device_path}")

# +++
#            if not selection.get("device"):
            if not selection.get("device_path"):
                _LOGGER.error("device does not have a device-path")
                errors["base"] = "no_device_path"
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    errors=errors,
                )

            if not serial:
                _LOGGER.error("device does not have a serial-number")
                return self.async_abort(reason="no_serial_number")

            _LOGGER.debug("setting unique-ID...")
            await self.async_set_unique_id(serial)
            _LOGGER.debug("...done !")
            self._abort_if_unique_id_configured()
            _LOGGER.debug("not aborted due to unique-ID is available")
# +++


            return self.async_create_entry(
#                title = selection["model"],
                title = selection["description"],
                data = selection,
            )

        return self.async_show_form(
            step_id = "user",
            data_schema = schema,
            errors = errors,
            description_placeholders={"info": "please choose one not recognized device to add"},
        )


    async def _get_serial_ports_(self) -> dict[str, str]:
        _LOGGER.debug("_get_serial_ports")
        loop = asyncio.get_running_loop()

        def _scan():
            return usb.scan_serial_ports()

        ports = await loop.run_in_executor(None, _scan)

        result: dict[str, str] = {}

        for port in ports:
            # port ist usb.USBDevice
            # port.device z.B. "/dev/serial/by-id/usb-..."
            # port.manufacturer, port.description optional
            label = port.description or port.device
            result[port.device] = label

        _LOGGER.debug(f"found those devices: {result}")

        return result


    async def async_step_confirm(self, user_input=None):
        _LOGGER.debug(f"async_step_confirm with user-input {user_input}")
        if user_input is not None:
            return self.async_create_entry(
                title="Choose new device to add as new display",
                data={
                    "device": self.port,
                    "source": "usually",
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
#                "port": self.port
                "Device": self.port
            },
            data_schema=vol.Schema({}),
        )



