"""
WeAct Display FS Integration for Home Assistant

toDo:
+ random bitmap P1
+ testbild
+ umbau für public/github
- qr code
~ send text with font/size/pos/t-color/bg-color/orientation/...
~ draw lines, circles, rectangles, triangles
+ show icon
+ clear screen
+ analog/digital clock, wird solange minütlich aktualisiert bis ein neues Kommando kommt
- Rheinturm wird sekündlich neu gemacht, allerdings auch nur der untere Teil mit den Sekunden. Der Rest minütlich
+ pic from file
+ set orientation
+ lautstärke
+ temp/humid
+ UI reload
+ scan for new devices regularly, list of known devices needed
+ was passiert wenn ab und dran?
+ multiple displays
- real supported und stabiler ConfigFlow, kein Crash wenn kein Display angesteckt, keine Meldung wg inkorrekter unique-ID
- Dokumentation der initialen Funktionsweise, der Sensoren, der verfügbaren Aktionen, ...
"""

import asyncio
#import datetime
import glob
import logging
import os
import pathlib
import random
import re
import serial
import struct
import threading
import time
import zoneinfo

from PIL import Image
from pathlib import Path
from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback, EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.discovery import async_load_platform
#from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import ConfigType
#from datetime import datetime, time, timedelta
from datetime import datetime, timedelta

import custom_components.weact_display.const as const
from .models import DISPLAY_MODELS
from .clock import start_analog_clock, start_digital_clock, stop_clock
from .commands import normalize_color
#from .clock import stop_clock, start_analog_clock, start_digital_clock, start_rheinturm
#from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_testbild, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr, enable_humiture_reports, parse_packet
#from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_testbild, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr, enable_humiture_reports, parse_packet, read_firmware_version, read_who_am_i
#from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_bmp, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr, enable_humiture_reports, parse_packet, read_firmware_version, read_who_am_i
from .commands import display_selftest, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, enable_humiture_reports, generate_random, generate_qr, open_serial, parse_packet, read_firmware_version, read_who_am_i, send_full_color, send_screen, set_brightness, set_orientation, show_bmp, show_icon, show_init_screen, write_text
#from .draws import write_text, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr

# ------------------------------------------------------------
# Initialisierung
# ------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Setting up WeAct Display integration via async_setup_entry (from Config Flow)")
    # reales Display beim Startup:
    # 2025-12-28 23:45:37.658 DEBUG (MainThread) [custom_components.weact_display] async_setup_entry called for weact_display, entry=<ConfigEntry entry_id=01KDDSQP0NMRXTP0DQF45ZPAD2 version=1 domain=weact_display title=WeAct Display addec74db14d state=ConfigEntryState.SETUP_IN_PROGRESS unique_id=addec74db14d>
    # Fake Display manuell:
    # 2025-12-28 23:59:11.478 DEBUG (MainThread) [custom_components.weact_display] async_setup_entry called for weact_display, entry=<ConfigEntry entry_id=01KDKJZSZPNXN4CKQ03KYA1BEK version=1 domain=weact_display title=SMLIGHT SLZB-07p7 state=ConfigEntryState.SETUP_IN_PROGRESS unique_id=None>
    _LOGGER.debug(f"entry={entry}")
 
    domain_data   = hass.data.setdefault(const.DOMAIN, {})
    devices       = domain_data.setdefault("devices", {})
    device_id_map = domain_data.setdefault("device_id_map", {})

    serial_number     = entry.unique_id
    device_path       = entry.data.get("device_path", None)
    model             = entry.data.get("model", None)
    setup_dt          = entry.data.get("setup_dt", None)
    setup_version     = entry.data.get("setup_version", None)
    orientation_value = entry.options.get("orientation_value", None)
    brightness        = entry.options.get("brightness", None)
    background_color  = entry.options.get("background_color", None)
    screencare        = entry.options.get("screencare", None)

    _LOGGER.debug(f"read values from entry-data: model={model}, device-path={device_path}, background-color={background_color}, brightness={brightness}, orientation-value={orientation_value}, screencare={screencare}")

    if device_path is None:
        _LOGGER.error(f"could not find any device-path in ConfigEntry datastore (={device_path}), aborting !")
        return False
    if model is None:
        _LOGGER.error(f"could not find any model in ConfigEntry datastore (={model}), aborting !")
        return False
    if orientation_value is None:
        orientation_value = 2
        _LOGGER.debug(f"could not find any valid value for orientation-value in ConfigEntry datastore, set to {orientation_value}")
    if brightness is None:
        brightness = int(const.DEFAULT_BRIGHTNESS)
        _LOGGER.debug(f"could not find any valid value for brightness in ConfigEntry datastore, set to {brightness}")
    if background_color is None:
        background_color = (0, 0, 0)
        _LOGGER.debug(f"could not find any valid value for background-color in ConfigEntry datastore, set to {background_color}")
    background_color = normalize_color(background_color)
    if screencare is None:
        screencare = True
        _LOGGER.debug(f"could not find any valid value for screencare in ConfigEntry datastore, set to {screencare}")

    # Parameter abfragen
    params   = DISPLAY_MODELS.get(model, None)
    width    = None
    height   = None
    humiture = None
    if params is None:
        _LOGGER.error(f"unknown display type: {model}. Please ask developer or enhance models.py by yourself")
        width = 1
        height = 1
        humiture = False
    else:
        humiture = params["humiture"]
        large = params["large"]
        small = params["small"]
        _LOGGER.debug(f"read model parameters: large={large}, small={small}, humiture={humiture}")
        if orientation_value in [2, 3]:       # Landscape
            width = large
            height = small
        else:                                         # Portrait
            width = small
            height = large
        _LOGGER.debug(f"configured orientation [{orientation_value}] to width={width}, height={height}")

    # runtime Daten
    _LOGGER.debug(f"setting up runtime values for entry-id {entry.entry_id}, serial-number {serial_number}")
    devices.setdefault(serial_number, {})
    devices[serial_number]["entry_id"]                  = entry.entry_id
    devices[serial_number]["device_path"]               = device_path
    devices[serial_number]["unique_id"]                 = entry.unique_id
    devices[serial_number]["model"]                     = model
    devices[serial_number]["setup_dt"]                  = setup_dt
    devices[serial_number]["setup_version"]             = setup_version
    devices[serial_number]["firmware_version"]          = None
    devices[serial_number]["who_am_i"]                  = None
    devices[serial_number]["state"]                     = "initializing"
    devices[serial_number]["start_time"]                = datetime.now().isoformat(timespec="seconds")
    devices[serial_number]["background_color"]          = background_color
    devices[serial_number]["screencare"]                = screencare
    devices[serial_number]["brightness"]                = brightness
    devices[serial_number]["orientation_value"]         = orientation_value
    devices[serial_number]["width"]                     = width
    devices[serial_number]["height"]                    = height
    devices[serial_number]["humiture"]                  = humiture
    devices[serial_number]["temperature"]               = None
    devices[serial_number]["humidity"]                  = None
    devices[serial_number]["clock_mode"]                = "idle"
    devices[serial_number]["clock_handle"]              = None
    devices[serial_number]["screencare_handle"]         = None
    devices[serial_number]["lock"]                      = asyncio.Lock()
    devices[serial_number]["shadow"]                    = Image.new("RGB", (width, height))
    _LOGGER.debug(f"devices={devices}")

    # === DEVICE REGISTRY ===
    _LOGGER.debug(f"registering device for {serial_number}")
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id = entry.entry_id,
        identifiers = {(const.DOMAIN, serial_number)},
        manufacturer = "WeAct Studio",
        model = f"WeAct Display type {hass.data[const.DOMAIN]["devices"][serial_number].get("model")}",
        sw_version = hass.data[const.DOMAIN]["devices"][serial_number].get("firmware_version"),
        name = f"WeAct Display {serial_number}",
    )
    devices[serial_number]["device_id"] = device.id

    _LOGGER.debug(f"Registered device={device}")

    # === DEVICE MAPPING ===
    _LOGGER.debug(f"adding device-id-mapping for {serial_number} to lookup via device-id")
    device_id_map.setdefault(device.id, {})
    device_id_map[device.id]["serial_number"] = serial_number
    _LOGGER.debug(f"new device-id-map={device_id_map}")

    # === ENTITY MAPPING ===
#    _LOGGER.debug(f"adding serial-mapping for {serial_number} to lookup via entry.entry-id")
#    serial_map[entry.entry_id] = serial_number
#    _LOGGER.debug(f"serial-map={serial_map}")

    # Plattformen laden
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "select", "number", "switch"])

    devices[serial_number]["online"] = True

    hass.loop.create_task(post_startup(hass, entry))            # serielle Schnittstelle(n) initialisieren

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    serial_number = entry.data.get("serial_number")

    _LOGGER.info(f"Unloading WeAct Display for serial {serial_number}")
    
    # Uhr anhalten
    await stop_clock(hass, serial_number)
    # Plattformen entladen
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "select", "number", "switch"],)

    if unload_ok and serial_number:
        hass.data[const.DOMAIN]["devices"].pop(serial_number, None)

    return unload_ok


async def async_setup(hass: HomeAssistant, config):
    _LOGGER.info("Setting up WeAct Display integration via async_setup (from Startup)")

    # BMP/ICON Filepath
    const.IMG_PATH.mkdir(parents=True, exist_ok=True)
    const.ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _LOGGER.debug(f"image path set to: {const.IMG_PATH}, icon path set to: {const.ICON_CACHE_DIR}")

    # Sensor-Plattform laden (Erzeugt die Entity!)
    await async_load_platform(hass, "sensor", const.DOMAIN, {}, config)



###
# ab hier die Dienste
###
    # --------------------------------------------------------
    # Service: USB remove detektieren
    # --------------------------------------------------------
    async def _usb_removed(event):
        device = event.data
        serial = device.get("serial_number")
        if not serial:
            return
        if serial not in hass.data[const.DOMAIN]["devices"]:
            return

        _LOGGER.warning(f"USB device removed: serial={serial}, device={device.device}")

        hass.data[const.DOMAIN]["devices"][serial]["online"] = False                        # mark device as offline

        # Entities informieren
        entity = hass.data[const.DOMAIN]["devices"][serial].get("entity")
        if entity:
            entity.async_write_ha_state()

    hass.bus.async_listen("usb_device_removed", _usb_removed)


    # --------------------------------------------------------
    # Service: Text anzeigen
    # --------------------------------------------------------
    async def handle_send_text(call: ServiceCall):
        _LOGGER.debug("called service to scribble some text")

        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        text = call.data.get("text", None)
        xs = call.data.get("x_start", None)
        ys = call.data.get("y_start", None)
        xe = call.data.get("x_end", None)
        ye = call.data.get("y_end", None)
        font_size = call.data.get("font_size", None)
        t_color = call.data.get("t_color", None)
        bg_color = call.data.get("bg_color", None)
        rotation = call.data.get("rotation", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, text={text}, xs={xs}, ys={ys}, xe={xe}, ye={ye}, font-size={font_size}, t-color={t_color}, bg-color={bg_color}, rotation={rotation}")

        await write_text(hass, serial_number, text, xs, ys, xe, ye, font_size = font_size, t_color = t_color, bg_color = bg_color, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "write_text", handle_send_text)

    # --------------------------------------------------------
    # Service: Zufallsbild anzeigen
    # --------------------------------------------------------
    async def handle_show_random(call: ServiceCall):
        _LOGGER.debug("called service for random bmp")

        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}")
    
        await generate_random(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "show_random", handle_show_random)


    # --------------------------------------------------------
    # Service: Selbsttest aufrufen
    # --------------------------------------------------------
    async def handle_start_selftest(call: ServiceCall):
        _LOGGER.debug("called service for display selftest")

        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return
        
        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}")

        await display_selftest(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "start_selftest", handle_start_selftest)


    # --------------------------------------------------------
    # Service: Display Neustart
    # --------------------------------------------------------
    async def handle_restart_display(call: ServiceCall):
        _LOGGER.debug("called service for display restart")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}")

        await display_restart(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "restart_display", handle_restart_display)


    # --------------------------------------------------------
    # Service: Initiale Displayanzeige aufrufen
    # --------------------------------------------------------
    async def handle_show_init_screen(call: ServiceCall):
        _LOGGER.debug("called service for initial screen")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}")

        await show_init_screen(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "show_init_screen", handle_show_init_screen)


    # --------------------------------------------------------
    # Service: Ausrichtung setzen
    # --------------------------------------------------------
    async def handle_set_orientation(call: ServiceCall):
        _LOGGER.debug("called service for orientation")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        orientation_value = int(call.data.get("orientation"))

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, orientation={orientation_value}")

        await set_orientation(hass, serial_number, orientation_value)

    hass.services.async_register(const.DOMAIN, "set_orientation", handle_set_orientation)

    # --------------------------------------------------------
    # Service: Lautstärke festlegen
    # --------------------------------------------------------
    async def handle_set_brightness(call: ServiceCall):
        _LOGGER.debug("called service for brightness")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        brightness = call.data.get("brightness")            # aus dem übergebenen Wert lesen, kein Fallback, der kommt erst im set_brightness

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, brightness={brightness}")

        await set_brightness(hass, serial_number, brightness)

    hass.services.async_register(const.DOMAIN, "set_brightness", handle_set_brightness)


    # --------------------------------------------------------
    # Service: Full color
    # --------------------------------------------------------
    async def handle_set_full_color(call: ServiceCall):
        _LOGGER.debug("called service for one color")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        color_value = call.data.get("color")

        # entity registry lookup
#        registry = er.async_get(hass)
#        entry = registry.async_get(device)
#        serial_number = entry.unique_id

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, color={color_value}")

        await send_full_color(hass, serial_number, color_value)

    hass.services.async_register(const.DOMAIN, "set_full_color", handle_set_full_color)


    # --------------------------------------------------------
    # Service: Testbild
    # --------------------------------------------------------
    async def handle_show_testbild(call: ServiceCall):
        _LOGGER.debug("called service for testbild")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}")

        await show_bmp(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "show_testbild", handle_show_testbild)


    # --------------------------------------------------------
    # Service: Show BMP
    # --------------------------------------------------------
    async def handle_show_bmp(call: ServiceCall):
        _LOGGER.debug("called service for bmp")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        filepath = call.data.get("filepath", None)
        xs = call.data.get("xs", None)
        ys = call.data.get("ys", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, X-Start={xs}, Y-Start={ys}, filepath={filepath}")

        await show_bmp(hass, serial_number, xs = xs, ys = ys, filepath = filepath)

    hass.services.async_register(const.DOMAIN, "show_bmp", handle_show_bmp)


    # --------------------------------------------------------
    # Service: Stop clock
    # --------------------------------------------------------
    async def handle_stop_clock(call: ServiceCall):
        _LOGGER.debug("called service for stopping any running clock")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}")

        await stop_clock(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "stop_clock", handle_stop_clock)


    # --------------------------------------------------------
    # Service: Analog clock
    # --------------------------------------------------------
    async def handle_start_analog_clock(call: ServiceCall):
        _LOGGER.debug(f"called service for analog clock")

 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        sc_color = call.data.get("sc_color")
        scf_color = call.data.get("scf_color")
        h_color = call.data.get("hh_color")
        m_color = call.data.get("mm_color")
        offset_hours = call.data.get("offset")
        h_shift = call.data.get("h_shift")
        v_shift = call.data.get("v_shift")
        scale_size = call.data.get("scale_size")
        rotation = call.data.get("rotation")

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, scale-color={sc_color}, scale-frame-color={scf_color}, hour-color={h_color}, minute-color={m_color}, offset={offset_hours}, h-shift={h_shift}, v-shift={v_shift}, scale-size={scale_size}, rotation={rotation}")

        await start_analog_clock(hass, serial_number, sc_color = sc_color, scf_color = scf_color, h_color = h_color, m_color = m_color, offset_hours = offset_hours, h_shift = h_shift, v_shift = v_shift, scale_size = scale_size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "start_analog_clock", handle_start_analog_clock)


    # --------------------------------------------------------
    # Service: Digital clock
    # --------------------------------------------------------
    async def handle_start_digital_clock(call: ServiceCall):
        _LOGGER.debug("called service for digital clock")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        xs = call.data.get("xs")
        ys = call.data.get("ys")
        d_color = call.data.get("d_color")
        bg_color = call.data.get("bg_color")
        cf_color = call.data.get("cf_color")
        cf_width = call.data.get("cf_width")
        offset_hours = call.data.get("offset")
        digit_size = call.data.get("digit_size")
        rotation = call.data.get("rotation", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, xs={xs}, ys={ys}, background-color={bg_color}, digit-color={d_color}, offset={offset_hours}, digit-size={digit_size},  rotation={rotation}")

        await start_digital_clock(hass, serial_number, xs = xs, ys = ys, bg_color = bg_color, d_color = d_color, cf_color = cf_color, cf_width = cf_width, offset_hours = offset_hours, digit_size = digit_size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "start_digital_clock", handle_start_digital_clock)


    # --------------------------------------------------------
    # Service: Rheinturm
    # --------------------------------------------------------
    async def handle_start_rheinturm(call: ServiceCall):
        _LOGGER.debug("called service for rheinturm")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        rotation = call.data.get("rotation", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, rotation={rotation}")

        await start_rheinturm(hass, serial_number, rotation = rotation)

#    hass.services.async_register(const.DOMAIN, "start_rheinturm", handle_start_rheinturm)

    # --------------------------------------------------------
    # Service: Show Icon
    # --------------------------------------------------------
    async def handle_show_icon(call: ServiceCall):
        _LOGGER.debug("called service for icon")
        
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        i_name = call.data.get("icon_name")
        i_color = call.data.get("icon_color")
        xs = call.data.get("xs")
        ys = call.data.get("ys")
        i_size = call.data.get("icon_size")
        rotation = call.data.get("rotation")

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, icon-name={i_name}, icon-color={i_color}, x-start={xs}, y-start={ys}, size={i_size}, rotation={rotation}")

        await show_icon(hass, serial_number, i_name = i_name, i_color = i_color, xs = xs, ys = ys, i_size = i_size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "show_icon", handle_show_icon)


    # --------------------------------------------------------
    # Service: draw circle
    # --------------------------------------------------------
    async def handle_draw_circle(call: ServiceCall):
        _LOGGER.debug("called service to draw a circle")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        xp = call.data.get("x_position")
        yp = call.data.get("y_position")
        r = call.data.get("radius")
        c_color = call.data.get("c_color")
        f_color = call.data.get("f_color")
        cf_width = call.data.get("cf_width")
        e = call.data.get("ellipse")

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, X-pos={xp}, Y-pos={yp}, radius={r}, circle-color={c_color}, fill-color={f_color}, circle-frame-width={cf_width}, ellipse={e}")

        await draw_circle(hass, serial_number, xp, yp, r, c_color, f_color, cf_width, e)

    hass.services.async_register(const.DOMAIN, "draw_circle", handle_draw_circle)


    # --------------------------------------------------------
    # Service: draw rectangle
    # --------------------------------------------------------
    async def handle_draw_rectangle(call: ServiceCall):
        _LOGGER.debug("called service to draw a rectangle")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        xs = call.data.get("x_start")
        ys = call.data.get("y_start")
        xe = call.data.get("x_end")
        ye = call.data.get("y_end")
        rf_width = call.data.get("rf_width", None)
        rf_color = call.data.get("rf_color", None)
        f_color = call.data.get("f_color", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, X-Start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, rectangle-frame-width={rf_width}, rectangle-frame-color={rf_color}, fill-color={f_color}")

        await draw_rectangle(hass, serial_number, xs, ys, xe, ye, rf_width, rf_color, f_color)

    hass.services.async_register(const.DOMAIN, "draw_rectangle", handle_draw_rectangle)


    # --------------------------------------------------------
    # Service: draw triangle
    # --------------------------------------------------------
    async def handle_draw_triangle(call: ServiceCall):
        _LOGGER.debug("called service to draw a triangle")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        xa = call.data.get("x_a")
        ya = call.data.get("y_a")
        xb = call.data.get("x_b")
        yb = call.data.get("y_b")
        xc = call.data.get("x_c")
        yc = call.data.get("y_c")
        t_color = call.data.get("t_color", None)
        tf_color = call.data.get("tf_color", None)
        tf_width = call.data.get("tf_width", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, X-A={xa}, Y-A={ya}, X-B={xb}, Y-B={yb}, X-C={xc}, Y-C={yc}, triangle-color={t_color}, triange-frame-color={tf_color}, triangle-frame-width={tf_width}")

        await draw_triangle(hass, serial_number, xa, ya, xb, yb, xc, yc, t_color, tf_color, tf_width)

    hass.services.async_register(const.DOMAIN, "draw_triangle", handle_draw_triangle)


    # --------------------------------------------------------
    # Service: draw line
    # --------------------------------------------------------
    async def handle_draw_line(call: ServiceCall):
        _LOGGER.debug("called service to draw a line")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        xs = call.data.get("xs_position")
        ys = call.data.get("ys_position")
        xe = call.data.get("xe_position")
        ye = call.data.get("ye_position")
        l_color = call.data.get("l_color")
        l_width = call.data.get("l_width")

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, X-Start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, line-color={l_color}, line-width={l_width}")

        await draw_line(hass, serial_number, xs, ys, xe, ye, l_color, l_width)

    hass.services.async_register(const.DOMAIN, "draw_line", handle_draw_line)


    # --------------------------------------------------------
    # Service: draw progress bar
    # --------------------------------------------------------
    async def handle_draw_progress_bar(call: ServiceCall):
        _LOGGER.debug("called service to draw a progress bar")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        bar_min = call.data.get("bar_min")
        bar_value = call.data.get("bar_value")
        bar_max = call.data.get("bar_max")
        xs = call.data.get("x_start")
        ys = call.data.get("y_start")
        xe = call.data.get("x_end", None)
        ye = call.data.get("y_end", None)
        bf_width = call.data.get("bf_width", None)
        b_color = call.data.get("b_color", None)
        bf_color = call.data.get("bf_color", None)
        bg_color = call.data.get("bg_color", None)
        rotation = call.data.get("rotation", None)
        show_value = call.data.get("show_value", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, X-start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, bar-min={bar_min}, bar-value={bar_value}, bar-max={bar_max}, bar-frame-width={bf_width}, bar-frame-color={bf_color}, bar-color={b_color}, background-color={bg_color}, rotation={rotation}, show_value={show_value}")

        await draw_progress_bar(hass, serial_number, xs, ys, xe, ye, min_value=bar_min, bar_value=bar_value, max_value=bar_max, bf_width=bf_width, b_color=b_color, bf_color=bf_color, bg_color=bg_color, rotation=rotation, show_value=show_value)

    hass.services.async_register(const.DOMAIN, "draw_progress_bar", handle_draw_progress_bar)

    # --------------------------------------------------------
    # Service: change screencare option
    # --------------------------------------------------------
    async def handle_change_screencare_option(call: ServiceCall):
        _LOGGER.debug("called service to change screencare option")
 
        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        screencare_option = call.data.get("screencare_option", None)
        if screencare_option is None:
            _LOGGER.error("missing mandatory screencare option")
            return

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        device = hass.data[const.DOMAIN]["devices"][serial_number]

        # entry-data lookup
        entry_id = device.get("entry_id")
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            _LOGGER.error(f"no config entry found for serial {serial_number}")
            return

        # Config + runtime aktualisieren
        new_options = {
            **entry.options,
            "screencare": value,
        }
        hass.config_entries.async_update_entry(entry, options=new_options)
        device["screencare"] = value

        _LOGGER.debug(f"values given: device-id={device_id}, serial-number={serial_number}, screencare={screencare_option}")

    hass.services.async_register(const.DOMAIN, "change_screencare_option", handle_change_screencare_option)


    # --------------------------------------------------------
    # Service: generate qr code
    # --------------------------------------------------------
    async def handle_generate_qr(call: ServiceCall):
        _LOGGER.debug("called service to generate a qr code")

        device_id = call.data.get("display", None)
        if device_id is None:
            _LOGGER.error("missing mandatory device id")
            return

        data = call.data.get("data")
        xs = call.data.get("xs", 0)
        ys = call.data.get("ys", 0)
        show_data = call.data.get("show_data", False)
        qr_color = call.data.get("qr_color", None)
        bg_color = call.data.get("bg_color", None)

        # device registry lookup
        serial_number = hass.data[const.DOMAIN]["device_id_map"][device_id].get("serial_number")
        if not serial_number:
            _LOGGER.error(f"no serial_number found in device mapping for device-id {device_id}")
            return

        _LOGGER.debug(f"values given: device={device_id}, serial-number={serial_number}, Data={data}, X-start={xs}, Y-Start={ys}, show-data={show_data}, qr-color={qr_color}, background-color={bg_color}")

        await generate_qr(hass, serial_number, data, xs, ys, show_data, qr_color, bg_color)

    hass.services.async_register(const.DOMAIN, "generate_qr", handle_generate_qr)


    # --------------------------------------------------------
    #   T H E   E N D  !
    # --------------------------------------------------------
    return True

 
async def post_startup(hass: HomeAssistant, entry):
    await asyncio.sleep(0.1)  # kleinen Yield geben
    _LOGGER.debug("post-startup")

    serial_number = entry.unique_id
    device_path = entry.data.get("device_path")
    model = entry.data.get("model")
    device = hass.data[const.DOMAIN]["devices"][serial_number]

    _LOGGER.info(f"Initializing display {model} with serial {serial_number} on {device_path}")

    try:
        _LOGGER.debug(f"Opening display on port {device_path}")
        serial_port = await hass.async_add_executor_job(open_serial, device_path)
        if serial_port is None:
            _LOGGER.error(f"serial port {port} could not be opened.")
            hass.data[const.DOMAIN]["devices"][serial_number]["state"] = "port error"
            return False

        _LOGGER.debug(f"successfully opened serial-port {device_path}")

        device["serial_port"] = serial_port
        device["state"]       = "ready"

        hass.bus.async_fire("weact_display", {"have fun with the new display at": hass.data[const.DOMAIN]["devices"][serial_number]["device_path"]})

    except Exception as e:
        _LOGGER.error(f"Error while initializing display: {e}")
        return False

    await start_serial_reader_thread(hass, serial_number)
    await asyncio.sleep(0.1)  # kleinen Yield geben
    await set_orientation(hass, serial_number, int(device.get("orientation_value")), force = True)
    await set_brightness(hass, serial_number, int(device.get("brightness")))
    await asyncio.sleep(0.1)                                         # nur mal kurz die Welt retten
    if hass.data[const.DOMAIN]["devices"][serial_number]["humiture"]:
        await enable_humiture_reports(hass, serial_number)
    await read_who_am_i(hass, serial_number)
    await read_firmware_version(hass, serial_number)
    await display_selftest(hass, serial_number)
    width  = device.get("width")
    height = device.get("height")
    background_color = device.get("background_color")
    await draw_rectangle(hass, serial_number, xs=0, ys=0, xe=width-1, ye=height-1, rf_width=0, rf_color=background_color, f_color=background_color)
    await setup_screencare(hass, serial_number)

    _LOGGER.info(f"post-startup done for serial {serial_number} on {device_path}, WeAct Display {model} is now waiting for some commands")


async def start_serial_reader_thread(hass, serial_number):
    _LOGGER.debug(f"starting serial-reader-thread for serial {serial_number}")
    device = hass.data[const.DOMAIN]["devices"][serial_number]
    _LOGGER.debug(f"device={device}")
    device_path = device["device_path"]
    serial_port = device["serial_port"]

    if device_path is None:
        _LOGGER.error(f"No device-path for {serial_number}")
        return
 
    def reader():
        _LOGGER.debug(f"enabling serial reader for serial-number {serial_number}")

        while True:
            try:
                data = serial_port.read(64)   # blockiert bis timeout oder Daten
                if not data:
                    continue  # Timeout → ruhig weiter

                _LOGGER.debug(f"RX [{serial_number}]: {data.hex(' ')}")                       # Zeige rohe Daten an (Hex + ASCII)

                if not parse_packet(hass, serial_number, packet=data):
                    _LOGGER.warning(f"could not parse the packet {data.hex(' ')} from {device_path}")

            except serial.SerialException:
                _LOGGER.warning(f"WeAct Display {serial_number} disconnected")
                hass.data[const.DOMAIN]["devices"][serial_number]["online"] = False
                hass.data[const.DOMAIN]["devices"][serial_number]["state"] = "port error"
                break

            except Exception as e:
                _LOGGER.error(f"Thread error for serial-port {device_path}: {e}")
                break

        _LOGGER.warning(f"serial reader stopped for serial-port {device_path} (This should only be reached while unloading !!)")
 
    t = threading.Thread(target=reader, daemon=True)
    t.start()


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
