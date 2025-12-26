from __future__ import annotations

import voluptuous as vol
import logging
import asyncio

from homeassistant import config_entries
from homeassistant.components import usb
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class WeActDisplayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        _LOGGER.debug(f"step-user, user-input={user_input}")
        errors = {}

        # Alle USB-Serial-Devices scannen
        ports = usb.scan_serial_ports()

        if not ports:
            return self.async_abort(reason="no_serial_ports")

        # Nur Ports ohne bestehenden ConfigEntry
        existing_serials = {
            entry.data.get("serial_number")
            for entry in self._async_current_entries()
        }

        available_ports = {}
        for dev in ports:
            serial = dev.serial_number
            if not serial:
                continue
            if serial in existing_serials:
                continue

            available_ports[f"{dev.device} ({serial})"] = {
                "device": dev.device,
                "serial_number": serial,
                "vid": dev.vid,
                "pid": dev.pid,
                "manufacturer": dev.manufacturer,
                "source": "user",
            }

        if not available_ports:
            return self.async_abort(reason="no_new_devices")

        if user_input is not None:
            selection = available_ports[user_input["port"]]
            return self.async_create_entry(
                title=f"WeAct Display {selection['serial_number']}",
                data=selection,
            )

        schema = vol.Schema({
            vol.Required("port"): vol.In(available_ports.keys())
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


    async def _get_serial_ports(self) -> dict[str, str]:
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
                title="WeAct Display",
                data={
                    "port": self.port,
#                    "created_by": "manually",
                    "source": "usually",
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "port": self.port
            },
            data_schema=vol.Schema({}),
        )


    async def async_step_serial(self, user_input=None):
        _LOGGER.debug(f"async_step_serial with user-input {user_input}")
        errors = {}

        if user_input is not None:
            serial_number = user_input["serial_number"]

            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"WeAct Display {serial_number}",
                data={
                    "serial_number": serial_number,
                    "port": self.port,
#                    "created_by": "manual_serial",
                    "source": "user_serial",
                },
            )

        schema = vol.Schema({
            vol.Required("serial_number"): str,
        })

        return self.async_show_form(
            step_id="serial",
            data_schema=schema,
            errors=errors,
        )


    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo):
        _LOGGER.debug(f"USB discovery: vid={discovery_info.vid}, pid={discovery_info.pid}, serial={discovery_info.serial_number}, device={discovery_info.device}")

        serial_number = discovery_info.serial_number
        device_path = discovery_info.device

        if not serial_number:
            _LOGGER.warning("no serial-number found for device, aborting USB discovery")
            return self.async_abort(reason="no_serial")

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        # Automatisch Entry anlegen
        return self.async_create_entry(
            title=f"WeAct Display {serial_number}",
            data={
                "serial_number": serial_number,
                "device": device_path,
                "vid": discovery_info.vid,
                "pid": discovery_info.pid,
#                "created_by": "_usb",
                "source": "usb",
            },
        )





