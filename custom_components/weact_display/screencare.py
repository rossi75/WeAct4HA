import asyncio
import logging
import random
import zoneinfo

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from datetime import datetime, timedelta
from .commands import send_screen
import custom_components.weact_display.const as const

_LOGGER = logging.getLogger(__name__)

async def setup_screencare(hass, serial_number):
    device = hass.data[const.DOMAIN]["devices"][serial_number]

    @callback
    async def _screencare_callback(now):
        _LOGGER.debug(f"screencare triggered for {serial_number}")

        entry_id = device.get("entry_id")
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            _LOGGER.error(f"no config entry for serial {serial_number}")
            return

        if not entry.options.get("screencare", False):
            _LOGGER.debug(f"screencare not set for serial {serial_number}, aborting")
            return
        else:
            _LOGGER.info(f"running screencare for serial {serial_number}")

        try:
            hass.async_create_task(run_screencare(hass, serial_number))
        except Exception as e:
            _LOGGER.exception(f"screencare callback failed with {e}")
        
        await setup_screencare(hass, serial_number)              # direkt nächsten Tag planen

    await asyncio.sleep(2)
    now = datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
    #target = now.replace(hour=10, minute=19, second=2, microsecond=0)
    target = now.replace(hour=3, minute=37, second=2, microsecond=0)

    if target <= now:
        target += timedelta(days=1)

    offset_seconds = int(serial_number[-1:], 16)                  # Offset aus Seriennummer
    target += timedelta(seconds=offset_seconds)

    screencare_handle = async_track_point_in_time(hass, _screencare_callback, target)

    device["screencare_target"] = target

    _LOGGER.info(f"set next screencare trigger for serial {serial_number} to {target}")
    _LOGGER.debug(f"screencare trigger configured with handle {screencare_handle}")

async def run_screencare(hass, serial_number):
    device = hass.data[const.DOMAIN]["devices"][serial_number]
    entry_id = device.get("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)

    # backup ziehen
    shadow = device.get("shadow")
    backup = shadow.copy()

    # screencare
    for i in range(6):
        await generate_random(hass, serial_number, suppress_delete=True)
        await asyncio.sleep(6)

    # restore
    device["shadow"] = backup
    await send_screen(hass, serial_number)

    _LOGGER.debug(f"screencare finished for serial {serial_number}")
