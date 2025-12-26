"""
WeAct Display FS Integration for Home Assistant

toDo:
+ random bitmap P1
- testbild
+ umbau für public/github
- qr code
~ send text with font/size/pos/t-color/bg-color/orientation/...
~ draw lines, circles, rectangles, triangles
+ show icon
+ clear screen
+ analog/digital clock, wird solange minütlich aktualisiert bis ein neues Kommando kommt
- Rheinturm wird sekündlich neu gemacht, allerdings auch nur der untere Teil mit den Sekunden. Der Rest minütlich
- pic from file
+ set orientation
+ lautstärke
+ temp/humid
+ UI reload
+ scan for new devices regularly, list of known devices needed
+ was passiert wenn ab und dran?
+ multiple displays
- 
- Dokumentation der initialen Funktionsweise, der Sensoren, der verfügbaren Aktionen, ...
"""

import asyncio
import datetime
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

from PIL import Image
from pathlib import Path
from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
#from homeassistant.helpers.event import async_track_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.discovery import async_load_platform

import custom_components.weact_display.const as const
from .models import DISPLAY_MODELS
from .clock import stop_clock, start_analog_clock, start_digital_clock
#from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_testbild, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr, enable_humiture_reports, parse_packet
from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_testbild, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr, enable_humiture_reports, parse_packet, read_firmware_version, read_who_am_i
#from .commands import send_bitmap, send_full_color, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_testbild, enable_humiture_reports
#from .draws import write_text, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, draw_progress_bar, generate_qr
#from .clock import stop_clock, start_analog_clock, start_digital_clock, start_rheinturm


#from .const import DOMAIN, LOGGER
#from .clock import stop_clock, CLOCK_MODE


# ------------------------------------------------------------
# Initialisierung
# ------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("async_setup_entry called for weact_display")

    serial_number = entry.data["serial_number"]
    device_path = entry.data["device"]

    hass.data.setdefault(const.DOMAIN, {})
    hass.data[const.DOMAIN].setdefault(serial_number, {})
    hass.data[const.DOMAIN][serial_number]["device"] = device_path
    hass.data[const.DOMAIN][serial_number]["entry_id"] = entry.entry_id


    # === DEVICE REGISTRY ===
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id = entry.entry_id,
        identifiers = {(const.DOMAIN, serial_number)},
        manufacturer = "WeAct Studio",
        model = f"WeAct Display type {hass.data[const.DOMAIN][serial_number].get("model")}",
        sw_version = hass.data[const.DOMAIN][serial_number].get("firmware_version"),
        name = f"WeAct Display {serial_number}",
    )

    _LOGGER.debug(f"Registered device: name={device.name}, identifiers={device.identifiers}, manufacturer={device.manufacturer}, model={device.model}, sw_version={device.sw_version}")

    # === interne Datenstruktur ===
    hass.data[const.DOMAIN][serial_number]["device_id"] = device.id
    hass.data[const.DOMAIN][serial_number]["entry_id"] = entry.entry_id
    hass.data[const.DOMAIN][serial_number]["online"] = True
    _LOGGER.debug(f"Device-ID={hass.data[const.DOMAIN][serial_number]["device_id"]}, Entry-ID={hass.data[const.DOMAIN][serial_number]["device_id"]}")

    # Plattformen laden
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "select"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    # alle displays durchgehen, ob die clock auf IDLE steht. Wenn nicht, diese gezielt eliminieren
#    await stop_clock(hass)
#    LOGGER.debug("WeAct Display clock stopped during unload.")
    hass.data[const.DOMAIN].pop(entry.entry_id, None)
    return True


async def async_setup(hass: HomeAssistant, config):
    _LOGGER.info("Starting WeAct Display integration via async_setup")

    # BMP/ICON Filepath
    const.IMG_PATH.mkdir(parents=True, exist_ok=True)
    const.ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _LOGGER.debug(f"image path set to: {const.IMG_PATH}, icon path set to: {const.ICON_CACHE_DIR}")

    # Display-Suche
    ports = await asyncio.to_thread(glob.glob, "/dev/serial/by-id/*WeAct*")
    if not ports:
        _LOGGER.debug("could not find any WeAct Display")
#        return
        return False
#        return True

    hass.data[const.DOMAIN] = {}
    hass.data.setdefault(const.DOMAIN, {})

    for idx, port in enumerate(ports):
        serial_full = os.path.basename(port)
        serial_parts = serial_full.split("_")
        if len(serial_parts) > 3:
            model = "_".join(serial_parts[3:-1]).replace("_", " ") 
        else:
            model = "unknown"
        if len(serial_parts) > 1:
            serial_number = re.sub(r"-if\d+$", "", serial_parts[-1])
        else:
            serial_number = "n/a"

        _LOGGER.debug(f"found new display #{idx} with: port={port}, model={model}, serial_number={serial_number}")

        # Parameter abfragen
        params = DISPLAY_MODELS.get(model, None)
        if params is None:
            _LOGGER.error(f"unknown display type: {model}. Please ask developer or enhance models.py by yourself")
            width = 1
            height = 1
            humiture = False
        else:
            width = params["large"]
            height = params["small"]
            humiture = params["humiture"]
            _LOGGER.debug(f"read model parameters: width={width}, height={height}, humiture={humiture}")

        # Globale Datenstruktur
        hass.data[const.DOMAIN][serial_number] = {
            "state": "initializing",
            "port": port,
            "model": model,
            "serial_number": serial_number,
            "firmware_version": None,
            "who_am_i": None,
            "start_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "width": width,
            "height": height,
            "orientation_value": 2,     # hier später aus dem Speicher lesen
#            "orientation": None,
            "humiture": humiture,
            "temperature": None,
            "humidity": None,
            "clock_handle": None,
            "clock_mode": "idle",
            "lock": asyncio.Lock(),
            "shadow": Image.new("RGB", (width, height))
        }

        _LOGGER.debug(f"shadow image has a size of {width * height * 3} bytes")

        try:
            _LOGGER.debug(f"Opening display on port {port}")

            serial_port = await hass.async_add_executor_job(open_serial, port)
            if serial_port is None:
                _LOGGER.error(f"serial port {port} could not be opened.")
                hass.data[const.DOMAIN][serial_number]["state"] = "port error"
                return False

            _LOGGER.debug(f"successfully opened serial-port {port}")

            hass.data[const.DOMAIN][serial_number]["serial_port"] = serial_port
            hass.data[const.DOMAIN][serial_number]["state"] = "ready"

            hass.bus.async_fire("weact_display", {"have fun with the new display at": hass.data[const.DOMAIN][serial_number]["port"]})

        except Exception as e:
            _LOGGER.error(f"Error while initializing display: {e}")
            return False

        _LOGGER.info(f"WeAct Display {model} is now waiting for some commands at {port}")

    # Sensor-Plattform laden (Erzeugt die Entity!)
    await async_load_platform(hass, "sensor", const.DOMAIN, {}, config)

    hass.loop.create_task(post_startup(hass))


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
        if serial not in hass.data[const.DOMAIN]:
            return

        _LOGGER.warning(f"USB device removed: serial={serial}, device={device.device}")

        hass.data[const.DOMAIN][serial]["online"] = False                        # mark device as offline

        # Entities informieren
        entity = hass.data[const.DOMAIN][serial].get("entity")
        if entity:
            entity.async_write_ha_state()

    hass.bus.async_listen("usb_device_removed", _usb_removed)


    # --------------------------------------------------------
    # Service: Text anzeigen
    # --------------------------------------------------------
    async def handle_send_text(call: ServiceCall):
        _LOGGER.debug("called service to scribble some text")

        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
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

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, text={text}, xs={xs}, ys={ys}, xe={xe}, ye={ye}, font-size={font_size}, t-color={t_color}, bg-color={bg_color}, rotation={rotation}")

        await write_text(hass, serial_number, text, xs, ys, xe, ye, font_size = font_size, t_color = t_color, bg_color = bg_color, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "write_text", handle_send_text)


    # --------------------------------------------------------
    # Service: Zufallsbild anzeigen
    # --------------------------------------------------------
    async def handle_show_random(call: ServiceCall):
        _LOGGER.debug("called service for random bmp")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        await generate_random(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "show_random", handle_show_random)


    # --------------------------------------------------------
    # Service: Selbsttest aufrufen
    # --------------------------------------------------------
    async def handle_start_selftest(call: ServiceCall):
        _LOGGER.debug("called service for display selftest")

        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        
        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        await display_selftest(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "start_selftest", handle_start_selftest)


    # --------------------------------------------------------
    # Service: Display Neustart
    # --------------------------------------------------------
    async def handle_restart_display(call: ServiceCall):
        _LOGGER.debug("called service for display restart")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return

        await display_restart(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "restart_display", handle_restart_display)


    # --------------------------------------------------------
    # Service: Initiale Displayanzeige aufrufen
    # --------------------------------------------------------
    async def handle_show_init_screen(call: ServiceCall):
        _LOGGER.debug("called service for initial screen")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        await show_init_screen(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "show_init_screen", handle_show_init_screen)


    # --------------------------------------------------------
    # Service: Ausrichtung setzen
    # --------------------------------------------------------
    async def handle_set_orientation(call: ServiceCall):
        _LOGGER.debug("called service for orientation")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        orientation_value = int(call.data.get("orientation"))

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, orientation={orientation_value}")

        await set_orientation(hass, serial_number, orientation_value)

    hass.services.async_register(const.DOMAIN, "set_orientation", handle_set_orientation)

    # --------------------------------------------------------
    # Service: Lautstärke festlegen
    # --------------------------------------------------------
    async def handle_set_brightness(call: ServiceCall):
        _LOGGER.debug("called service for brightness")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        brightness_value = call.data.get("brightness")

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, brightness={brightness_value}")

        await set_brightness(hass, serial_number, brightness_value)

    hass.services.async_register(const.DOMAIN, "set_brightness", handle_set_brightness)


    # --------------------------------------------------------
    # Service: Full color
    # --------------------------------------------------------
    async def handle_set_full_color(call: ServiceCall):
        _LOGGER.debug("called service for one color")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        color_value = call.data.get("color")

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, color={color_value}")

        await send_full_color(hass, serial_number, color_value)

    hass.services.async_register(const.DOMAIN, "set_full_color", handle_set_full_color)


    # --------------------------------------------------------
    # Service: Testbild
    # --------------------------------------------------------
    async def handle_show_testbild(call: ServiceCall):
        _LOGGER.debug("called service for testbild")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        await show_testbild(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "show_testbild", handle_show_testbild)


    # --------------------------------------------------------
    # Service: Stop clock
    # --------------------------------------------------------
    async def handle_stop_clock(call: ServiceCall):
        _LOGGER.debug("called service for stopping any running clock")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        await stop_clock(hass, serial_number)

    hass.services.async_register(const.DOMAIN, "stop_clock", handle_stop_clock)


    # --------------------------------------------------------
    # Service: Analog clock
    # --------------------------------------------------------
    async def handle_start_analog_clock(call: ServiceCall):
        _LOGGER.debug("called service for analog clock")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
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

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, scale-color={sc_color}, scale-frame-color={scf_color}, hour-color={h_color}, minute-color={m_color}, offset={offset_hours}, h-shift={h_shift}, v-shift={v_shift}, scale-size={scale_size}, rotation={rotation}")

        await start_analog_clock(hass, serial_number, sc_color = sc_color, scf_color = scf_color, h_color = h_color, m_color = m_color, offset_hours = offset_hours, h_shift = h_shift, v_shift = v_shift, scale_size = scale_size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "start_analog_clock", handle_start_analog_clock)


    # --------------------------------------------------------
    # Service: Digital clock
    # --------------------------------------------------------
    async def handle_start_digital_clock(call: ServiceCall):
        _LOGGER.debug("called service for digital clock")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
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

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, x={xs}, y={ys}, background-color={bg_color}, digit-color={d_color}, offset={offset_hours}, digit-size={digit_size},  rotation={rotation}")

        await start_digital_clock(hass, serial_number, xs = xs, ys = ys, bg_color = bg_color, d_color = d_color, cf_color = cf_color, cf_width = cf_width, offset_hours = offset_hours, digit_size = digit_size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "start_digital_clock", handle_start_digital_clock)


    # --------------------------------------------------------
    # Service: Rheinturm
    # --------------------------------------------------------
    async def handle_start_rheinturm(call: ServiceCall):
        _LOGGER.debug("called service for rheinturm")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        rotation = call.data.get("rotation", None)

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, rotation={rotation}")

        await start_rheinturm(hass, serial_number, rotation = rotation)

#    hass.services.async_register(const.DOMAIN, "start_rheinturm", handle_start_rheinturm)

    # --------------------------------------------------------
    # Service: Show Icon
    # --------------------------------------------------------
    async def handle_show_icon(call: ServiceCall):
        _LOGGER.debug("called service for icon")
        
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        i_name = call.data.get("icon_name")
        i_color = call.data.get("icon_color")
        xs = call.data.get("xs")
        ys = call.data.get("ys")
        i_size = call.data.get("icon_size")
        rotation = call.data.get("rotation")

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, icon-name={i_name}, icon-color={i_color}, x-start={xs}, y-start={ys}, size={i_size}, rotation={rotation}")

        await show_icon(hass, serial_number, i_name = i_name, i_color = i_color, xs = xs, ys = ys, i_size = i_size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "show_icon", handle_show_icon)


    # --------------------------------------------------------
    # Service: draw circle
    # --------------------------------------------------------
    async def handle_draw_circle(call: ServiceCall):
        _LOGGER.debug("called service to draw a circle")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        xp = call.data.get("x_position")
        yp = call.data.get("y_position")
        r = call.data.get("radius")
        c_color = call.data.get("c_color")
        f_color = call.data.get("f_color")
        cf_width = call.data.get("cf_width")
        e = call.data.get("ellipse")

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, X-pos={xp}, Y-pos={yp}, radius={r}, circle-color={c_color}, fill-color={f_color}, circle-frame-width={cf_width}, ellipse={e}")

        await draw_circle(hass, serial_number, xp, yp, r, c_color, f_color, cf_width, e)

    hass.services.async_register(const.DOMAIN, "draw_circle", handle_draw_circle)


    # --------------------------------------------------------
    # Service: draw rectangle
    # --------------------------------------------------------
    async def handle_draw_rectangle(call: ServiceCall):
        _LOGGER.debug("called service to draw a rectangle")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        xs = call.data.get("x_start")
        ys = call.data.get("y_start")
        xe = call.data.get("x_end")
        ye = call.data.get("y_end")
        rf_width = call.data.get("rf_width", None)
        rf_color = call.data.get("rf_color", None)
        f_color = call.data.get("f_color", None)

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, X-start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, rectangle-frame-width={rf_width}, rectangle-frame-color={rf_color}, fill-color={f_color}")

        await draw_rectangle(hass, serial_number, xs, ys, xe, ye, rf_width, rf_color, f_color,)

    hass.services.async_register(const.DOMAIN, "draw_rectangle", handle_draw_rectangle)


    # --------------------------------------------------------
    # Service: draw triangle
    # --------------------------------------------------------
    async def handle_draw_triangle(call: ServiceCall):
        _LOGGER.debug("called service to draw a triangle")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        xa = call.data.get("x_a")
        ya = call.data.get("y_a")
        xb = call.data.get("x_b")
        yb = call.data.get("y_b")
        xc = call.data.get("x_c")
        yc = call.data.get("y_c")
        bg_color = call.data.get("bg_color")
        t_color = call.data.get("t_color")
        f_color = call.data.get("f_color")
        tf_width = call.data.get("tf_width")

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, bg-color={bg_color}, triangle-color={t_color}, fill-color={f_color}, triangle-frame-width={rf-width}, X-A={xa}, Y-A={ya}, X-B={xb}, Y-B={yb}, X-C={xc}, Y-C={yc}")

        await draw_triangle(hass, serial_number, bg_color, t_color, f_color, tf_width, xa, ya, xb, yb, xc, yc)

    hass.services.async_register(const.DOMAIN, "draw_triangle", handle_draw_triangle)


    # --------------------------------------------------------
    # Service: draw line
    # --------------------------------------------------------
    async def handle_draw_line(call: ServiceCall):
        _LOGGER.debug("called service to draw a line")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        xs = call.data.get("xs_position")
        ys = call.data.get("ys_position")
        xe = call.data.get("xe_position")
        ye = call.data.get("ye_position")
        l_color = call.data.get("l_color")
        l_width = call.data.get("l_width")

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, X-Start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, line-color={l_color}, line-width={l_width}")

        await draw_line(hass, serial_number, xs, ys, xe, ye, l_color, l_width)

    hass.services.async_register(const.DOMAIN, "draw_line", handle_draw_line)


    # --------------------------------------------------------
    # Service: draw progress bar
    # --------------------------------------------------------
    async def handle_draw_progress_bar(call: ServiceCall):
        _LOGGER.debug("called service to draw a progress bar")
 
        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
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

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, X-start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, width={width}, height={height}, bar-min={bar_min}, bar-value={bar_value}, bar-max={bar_max}, bar-frame-width={bf_width}, bar-frame-color={bf_color}, bar-color={b_color}, background-color={bg_color}, rotation={rotation}, show_value={show_value}")
        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, X-start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, bar-min={bar_min}, bar-value={bar_value}, bar-max={bar_max}, bar-frame-width={bf_width}, bar-frame-color={bf_color}, bar-color={b_color}, background-color={bg_color}, rotation={rotation}, show_value={show_value}")

        await draw_progress_bar(hass, serial_number, xs, ys, xe, ye, min_value=bar_min, bar_value=bar_value, max_value=bar_max, bf_width=bf_width, b_color=b_color, bf_color=bf_color, bg_color=bg_color, rotation=rotation, show_value=show_value)

    hass.services.async_register(const.DOMAIN, "draw_progress_bar", handle_draw_progress_bar)


    # --------------------------------------------------------
    # Service: generate qr code
    # --------------------------------------------------------
    async def handle_generate_qr(call: ServiceCall):
        _LOGGER.debug("called service to generate a qr code")

        device = call.data.get("display", None)
        if device is None:
            _LOGGER.error("missing mandatory entity id")
            return
        data = call.data.get("data")
        xs = call.data.get("xs", 0)
        ys = call.data.get("ys", 0)
        show_data = call.data.get("show_data", False)
        qr_color = call.data.get("qr_color", None)
        bg_color = call.data.get("bg_color", None)

        # entity registry lookup
        registry = er.async_get(hass)
        entry = registry.async_get(device)
        serial_number = entry.unique_id

        _LOGGER.debug(f"values given: device={device}, serial-number={serial_number}, Data={data}, X-start={xs}, Y-Start={ys}, show-data={show_data}, qr-color={qr_color}, background-color={bg_color}")

        await generate_qr(hass, serial_number, data, xs, ys, show_data, qr_color, bg_color)

    hass.services.async_register(const.DOMAIN, "generate_qr", handle_generate_qr)


    # --------------------------------------------------------
    #   T H E   E N D  !
    # --------------------------------------------------------
    return True

 
async def post_startup(hass: HomeAssistant):
    await asyncio.sleep(0.1)  # kleinen Yield geben
    _LOGGER.debug("post-startup")

    for serial_number, data in hass.data[const.DOMAIN].items():
        _LOGGER.info(f"initializing display with serial-number {serial_number}")
#        await set_orientation(hass, serial_number, 2)                      # landscape setzen
        await set_orientation(hass, serial_number, hass.data[const.DOMAIN][serial_number].get("orientation_value"))
        await set_brightness(hass, serial_number, 7)
        await start_serial_reader_thread(hass, serial_number)
        await asyncio.sleep(0.1)                                         # nur mal kurz die Welt retten
        if hass.data[const.DOMAIN][serial_number]["humiture"]:
            await enable_humiture_reports(hass, serial_number)
        await read_who_am_i(hass, serial_number)
        await read_firmware_version(hass, serial_number)
        await display_selftest(hass, serial_number)
 
    _LOGGER.debug("post-startup done for all actually known displays")
 
 
async def start_serial_reader_thread(hass, serial_number):
    device = hass.data[const.DOMAIN][serial_number]
    serial_port = device["serial_port"]
    if serial_port is None:
        _LOGGER.error(f"No serial-port for {serial_number}")
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
                    _LOGGER.warning(f"could not parse the packet {data.hex(' ')} on port {serial_port}")

            except Exception as e:
                _LOGGER.error(f"Thread error for serial-port {serial_port}: {e}")
                break

        _LOGGER.warning(f"serial reader stopped for port {serial_port} (should never reach this point !!)")
 
    t = threading.Thread(target=reader, daemon=True)
    t.start()

