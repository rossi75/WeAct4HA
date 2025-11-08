"""
WeAct Display FS Integration for Home Assistant

toDo:
+ random bitmap P1
- testbild
- umbau für public/github
- qr code
- send text with font/size/pos/ft-color/bg-color/orientation/...
- draw lines, circles, rectangles, triangles
+ clear screen
- analog/digital clock, wird solange minütlich aktualisiert bis ein neues Kommando kommt
- Rheinturm wird sekündlich neu gemacht, allerdings auch nur der untere Teil mit den Sekunden. Der Rest minütlich
- pic from file
+ set orientation
+ lautstärke
- trigger testen
/ temp/humid
- UI reload
- scan for new devices regularly, list of known devices needed
- was passiert wenn ab und dran?
- multiple displays
- 
- Dokumentation der initialen Funktionsweise, der Sensoren, der verfügbaren Aktionen, ...
"""

import asyncio
import datetime
import time
import glob
import logging
import os
import struct
import random

from homeassistant.helpers.discovery import async_load_platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
#from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, start_analog_clock, set_brightness, show_testbild, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle, stop_clock
from .commands import send_bitmap, send_full_color, write_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, set_brightness, show_testbild, show_icon, draw_circle, draw_line, draw_rectangle, draw_triangle
from .bitmap import text_to_bitmap_bytes
#from .clock import stop_clock, start_analog_clock, start_digital_clock, start_rheinturm
from .clock import stop_clock, start_analog_clock, start_digital_clock
from pathlib import Path
#from .const import DOMAIN, IMG_PATH, CLOCK_REMOVE_HANDLE
from .const import CLOCK_REMOVE_HANDLE
import pathlib
import custom_components.weact_display.const as const

#DOMAIN = "weact_display"
_LOGGER = logging.getLogger(__name__)
SERIAL = None  # = const.SERIAL
#IMG_PATH = None
#CLOCK_REMOVE_HANDLE = None

# ------------------------------------------------------------
# Initialisierung
# ------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Setup der WeAct Display Integration."""
    _LOGGER.debug(f"starting up weact display FS V1")

    global SERIAL
    global CLOCK_REMOVE_HANDLE
#    global IMG_PATH

    const.IMG_PATH = pathlib.Path(hass.config.path()) / "custom_components" / "weact_display" / "bmp"
    const.IMG_PATH.mkdir(parents=True, exist_ok=True)
    #IMG_PATH.parent.mkdir(parents=True, exist_ok=True)
#    IMG_PATH = Path(hass.config.path()) / "custom_components" / "weact_display"
    _LOGGER.debug(f"image path set to: {const.IMG_PATH}")

    # Sensor-Plattform laden
    await async_load_platform(hass, "sensor", const.DOMAIN, {}, config)
    hass.data[const.DOMAIN] = {
        "ready": False,
        "start_time": datetime.datetime.now().isoformat(),
        "device_id": None,
    }

    _LOGGER.debug(f"Sensor platform loaded")

    # Gerät automatisch suchen
    paths = await asyncio.to_thread(glob.glob, "/dev/serial/by-id/*WeAct*")
    port = paths[0] if paths else "/dev/ttyACM0"

    _LOGGER.debug(f"found {paths}, shoud be equal to {port}")

    hass.data[const.DOMAIN]["device_id"] = os.path.basename(port)

    try:
        _LOGGER.debug(f"opening serial port {port}")

        SERIAL = await hass.async_add_executor_job(open_serial, port)
        if SERIAL is None:
            _LOGGER.warning(f"[{const.DOMAIN}] Abbruch: Serial port konnte nicht geöffnet werden!")
            return False

        _LOGGER.debug(f"[{const.DOMAIN}] selftest...")

        await display_selftest(hass, SERIAL)
        hass.data[const.DOMAIN]["ready"] = True
        hass.bus.async_fire("weact_display_ready", {"timestamp": hass.data[const.DOMAIN]["start_time"]})          # das Event auf welches abgefragt werden kann

#        _LOGGER.warning(f"[{const.DOMAIN}] Display at {port} is now ready")

    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] Error while initializing display: %s", e)
        return False

    """Setup for WeAct Display Integration."""

    # Beim Start sicherstellen, dass keine alte Uhr mehr läuft
    if CLOCK_REMOVE_HANDLE:
        _LOGGER.debug("Stopping leftover clock task from previous session...")
        await stop_clock(hass)

    _LOGGER.warning(f"[{const.DOMAIN}] Display at {port} is now ready")


    # --------------------------------------------------------
    # Service: Text anzeigen
    # --------------------------------------------------------
    async def handle_send_text(call: ServiceCall):
        _LOGGER.debug("called service to scribble some text")
        """Render Text und sende als Bitmap."""

        text = call.data.get("text", None)
        xs = call.data.get("x_start", None)
        ys = call.data.get("y_start", None)
        xe = call.data.get("x_end", None)
        ye = call.data.get("y_end", None)
#        font_size = int(call.data.get("font_size", None))
        font_size = call.data.get("font_size", None)
        t_color = call.data.get("t_color", None)
        bg_color = call.data.get("bg_color", None)
#        rotation = int(call.data.get("rotation", None))
        rotation = call.data.get("rotation", None)

        _LOGGER.debug(f"values given: text={text}, xs={xs}, ys={ys}, xe={xe}, ye={ye}, font_size={font_size}, t_color={t_color}, bg_color={bg_color}, rotation={rotation}")

        await write_text(hass, SERIAL, text, xs, ys, xe, ye, font_size = font_size, t_color = t_color, bg_color = bg_color, rotation = rotation)


#        try:
#            bmp = text_to_bitmap_bytes(
#                text,
#                width=width,
#                height=height,
#                color=color,
#                bgcolor=bgcolor,
#                align=align,
#                font_size=font_size,
#                font=font
#            )
#            await send_bitmap(SERIAL, 0, 0, width - 1, height - 1, bmp)
#            _LOGGER.warning("Text angezeigt: '%s' (%dx%d, fg=%s, bg=%s, align=%s)",
#                         text, width, height, color, bgcolor, align)
#        except Exception as e:
#            _LOGGER.error("Fehler beim Rendern/Senden des Textes: %s", e)

    hass.services.async_register(const.DOMAIN, "write_text", handle_send_text)


    # --------------------------------------------------------
    # Service: Zufallsbild anzeigen
    # --------------------------------------------------------
    async def handle_show_random(call: ServiceCall):
        """Erzeugt ein zufälliges Bitmap und sendet es an das Display."""
        _LOGGER.debug("called service for random bmp")
        
        await generate_random(hass, SERIAL)

    hass.services.async_register(const.DOMAIN, "show_random", handle_show_random)


    # --------------------------------------------------------
    # Service: Selbsttest aufrufen
    # --------------------------------------------------------
    async def handle_start_selftest(call: ServiceCall):
        """startet den Selbsttest wie bei der Initialisierung"""
        _LOGGER.debug("called service for display selftest")
        
        await display_selftest(hass, SERIAL)

    hass.services.async_register(const.DOMAIN, "start_selftest", handle_start_selftest)


    # --------------------------------------------------------
    # Service: Display Neustart
    # --------------------------------------------------------
    async def handle_restart_display(call: ServiceCall):
        """startet das Display neu"""
        _LOGGER.debug("called service for display restart")
        
        await display_restart(hass, SERIAL)

    hass.services.async_register(const.DOMAIN, "restart_display", handle_restart_display)


    # --------------------------------------------------------
    # Service: Initiale Displayanzeige aufrufen
    # --------------------------------------------------------
    async def handle_show_init_screen(call: ServiceCall):
        _LOGGER.debug("called service for initial screen")
        
        await show_init_screen(hass, SERIAL)

    hass.services.async_register(const.DOMAIN, "show_init_screen", handle_show_init_screen)


    # --------------------------------------------------------
    # Service: Ausrichtung setzen
    # --------------------------------------------------------
    async def handle_set_orientation(call: ServiceCall):
        """legt die Ausrichtung fest"""
        _LOGGER.debug("called service for orientation")
 
        orientation_value = call.data.get("orientation")
        opcode = 0

        _LOGGER.debug(f"value given: {orientation_value}")

        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return

        if orientation_value is None:
            raise ValueError(f"missing mandatory orientation value")
           
        # Falls string: in lowercase und Leerzeichen entfernen
        if isinstance(orientation_value, str):
            v = orientation_value.strip().lower()
            _LOGGER.debug("mapping text to opcode")

            # Texte
            mapping = {
                "portrait": 0,
                "landscape": 2,
                "portrait_r": 1,
                "landscape_r": 3,
            }
            if v in mapping:
                opcode = mapping[v]
                _LOGGER.debug(f"mapping set orientation to [{opcode}]")

        # Falls Zahl:
        elif isinstance(orientation_value, (int, float)):
            _LOGGER.debug("found any integer")
            val = int(orientation_value) % 360
            angle_to_opcode = {
                0: 0,   # portrait
                90: 2,  # landscape
                180: 1, # reverse portrait
                270: 3, # reverse landscape
            }

            # Direkter Opcode (0–3)
            if orientation_value in (0, 1, 2, 3):
                opcode = int(orientation_value)
            # Winkel (0|90|180|270)
            elif val in angle_to_opcode:
                opcode = angle_to_opcode[val]
                _LOGGER.debug("mapping angle to opcode")
            else:
                raise ValueError(f"invalid orientation: {orientation_value}")
        else:
            raise ValueError(f"invalid orientation: {orientation_value}")

        _LOGGER.debug(f"final opcode: {opcode}")

        await set_orientation(hass, SERIAL, opcode)

    # das setzen wir erst einmal hart aus !
#    hass.services.async_register(const.DOMAIN, "set_orientation", handle_set_orientation)

    # --------------------------------------------------------
    # Service: Lautstärke festlegen
    # --------------------------------------------------------
    async def handle_set_brightness(call: ServiceCall):
        _LOGGER.debug("called service for brightness")
        
        brightness_value = call.data.get("brightness")

        _LOGGER.debug(f"value given: brightness={brightness_value}")

        await set_brightness(hass, SERIAL, brightness_value)

    hass.services.async_register(const.DOMAIN, "set_brightness", handle_set_brightness)


    # --------------------------------------------------------
    # Service: Full color
    # --------------------------------------------------------
    async def handle_set_full_color(call: ServiceCall):
        """display in ONE color"""
        _LOGGER.debug("called service for one color")
        
        color_value = call.data.get("color")

        _LOGGER.debug(f"value given: color={color_value}")

        await send_full_color(hass, SERIAL, color_value)

    hass.services.async_register(const.DOMAIN, "set_full_color", handle_set_full_color)


    # --------------------------------------------------------
    # Service: Testbild
    # --------------------------------------------------------
    async def handle_show_testbild(call: ServiceCall):
        """display in ONE color"""
        _LOGGER.debug("called service for testbild")
        
        await show_testbild(hass, SERIAL)

    hass.services.async_register(const.DOMAIN, "show_testbild", handle_show_testbild)


    # --------------------------------------------------------
    # Service: Stop clock
    # --------------------------------------------------------
    async def handle_stop_clock(call: ServiceCall):
        _LOGGER.debug("called service for stopping any running clock")
        
#        await stop_clock(hass, SERIAL)
        await stop_clock(hass)

    hass.services.async_register(const.DOMAIN, "stop_clock", handle_stop_clock)


    # --------------------------------------------------------
    # Service: Analog clock
    # --------------------------------------------------------
    async def handle_start_analog_clock(call: ServiceCall):
        _LOGGER.debug("called service for analog clock")
 
        sc_color = call.data.get("sc_color", None)
        bg_color = call.data.get("bg_color", None)
        h_color = call.data.get("hh_color", None)
        m_color = call.data.get("mm_color", None)
        offset_hours = call.data.get("offset", None)
        shift = call.data.get("shift", None)
        rotation = call.data.get("rotation", None)
        opcode = 0

        _LOGGER.debug(f"values given: scale-color = {sc_color}, background-color = {bg_color}, hour-color = {h_color}, minute-color = {m_color}, offset = {offset_hours}, shift = {shift},  rotation = {rotation}")

        await start_analog_clock(hass, SERIAL, sc_color = sc_color, h_color = h_color, m_color = m_color, bg_color = bg_color, offset_hours = offset_hours, shift = shift, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "start_analog_clock", handle_start_analog_clock)


    # --------------------------------------------------------
    # Service: Digital clock
    # --------------------------------------------------------
    async def handle_start_digital_clock(call: ServiceCall):
        _LOGGER.debug("called service for digital clock")
 
        x_position = call.data.get("x_position")
        y_position = call.data.get("y_position")
        hm_color = call.data.get("hm_color", None)
        bg_color = call.data.get("bg_color", None)
        offset_hours = call.data.get("offset", None)
        digit_size = call.data.get("digit_size", None)
        rotation = call.data.get("rotation", None)

        _LOGGER.debug(f"values given: x={x_position}, y={y_position}, background-color={bg_color}, hour-minute-color = {hm_color}, offset = {offset_hours}, digit-size = {digit_size},  rotation = {rotation}")

        await start_digital_clock(hass, SERIAL, x_position, y_position, bg_color = bg_color, hm_color = hm_color, offset_hours = offset_hours, digit_size = digit_size, rotation = rotation)

#    hass.services.async_register(const.DOMAIN, "start_digital_clock", handle_start_digital_clock)


    # --------------------------------------------------------
    # Service: Rheinturm
    # --------------------------------------------------------
    async def handle_start_rheinturm(call: ServiceCall):
        _LOGGER.debug("called service for rheinturm")
 
        rotation = call.data.get("rotation", None)

        _LOGGER.debug(f"values given: rotation = {rotation}")

        await start_rheinturm(hass, SERIAL, rotation = rotation)

#    hass.services.async_register(const.DOMAIN, "start_rheinturm", handle_start_rheinturm)

    # --------------------------------------------------------
    # Service: Show Icon
    # --------------------------------------------------------
    async def handle_show_icon(call: ServiceCall):
        """display in ONE color"""
        _LOGGER.debug("called service for icon")
        
        icon_name = call.data.get("icon_name")
        bg_color = call.data.get("bg_color")
        icon_color = call.data.get("icon_color")
        x_position = call.data.get("x_position")
        y_position = call.data.get("y_position")
        size = call.data.get("size")
        rotation = call.data.get("rotation")

        _LOGGER.debug(f"values given: icon={icon_name}, bg_color={bg_color}, icon_color={icon_color}, ={x_position}, ={y_position}, ={size}, ={rotation}")

        await show_icon(hass, SERIAL, icon_name = icon_name, bg_color = bg_color, icon_color = icon_color, x_position = x_position, y_position = y_position, size = size, rotation = rotation)

    hass.services.async_register(const.DOMAIN, "show_icon", handle_show_icon)


    # --------------------------------------------------------
    # Service: draw circle
    # --------------------------------------------------------
    async def handle_draw_circle(call: ServiceCall):
        _LOGGER.debug("called service to draw a circle")
 
        xp = call.data.get("x_position")
        yp = call.data.get("y_position")
        r = call.data.get("radius")
        bg_color = call.data.get("bg_color", None)
        c_color = call.data.get("c_color", None)
        f_color = call.data.get("f_color", None)
        cf_width = call.data.get("cf_width", None)
        e = call.data.get("ellipse", None)

        _LOGGER.debug(f"values given: X-pos={xp}, Y-pos={yp}, radius={r}, bg-color={bg_color}, circle-color={c_color}, fill-color={f_color}, circle-frame-width={cf_width}, ellipse={e}")

        await draw_circle(hass, SERIAL, xp, yp, r, bg_color, c_color, f_color, cf_width, e)

    hass.services.async_register(const.DOMAIN, "draw_circle", handle_draw_circle)


    # --------------------------------------------------------
    # Service: draw rectangle
    # --------------------------------------------------------
    async def handle_draw_rectangle(call: ServiceCall):
        _LOGGER.debug("called service to draw a rectangle")
 
        xs = call.data.get("x_start")
        ys = call.data.get("y_start")
        xe = call.data.get("x_end")
        ye = call.data.get("y_end")
        rf_width = call.data.get("rf_width", None)
        rf_color = call.data.get("rf_color", None)
        f_color = call.data.get("f_color", None)

        _LOGGER.debug(f"values given: X-start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, rectangle-frame-width={rf_width}, rectangle-frame-color={rf_color}, fill-color={f_color}")

        await draw_rectangle(hass, SERIAL, xs, ys, xe, ye, rf_width, rf_color, f_color,)

    hass.services.async_register(const.DOMAIN, "draw_rectangle", handle_draw_rectangle)


    # --------------------------------------------------------
    # Service: draw triangle
    # --------------------------------------------------------
    async def handle_draw_triangle(call: ServiceCall):
        _LOGGER.debug("called service to draw a triangle")
 
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

        _LOGGER.debug(f"values given: bg-color={bg_color}, triangle-color={t_color}, fill-color={f_color}, triangle-frame-width={rf-width}, X-A={xa}, Y-A={ya}, X-B={xb}, Y-B={yb}, X-C={xc}, Y-C={yc}")

        await draw_triangle(hass, SERIAL, bg_color, t_color, f_color, tf_width, xa, ya, xb, yb, xc, yc)

    hass.services.async_register(const.DOMAIN, "draw_triangle", handle_draw_triangle)


    # --------------------------------------------------------
    # Service: draw line
    # --------------------------------------------------------
    async def handle_draw_line(call: ServiceCall):
        _LOGGER.debug("called service to draw a line")
 
        xs = call.data.get("xs_position")
        ys = call.data.get("ys_position")
        xe = call.data.get("xe_position")
        ye = call.data.get("ye_position")
        l_color = call.data.get("l_color")
        l_width = call.data.get("l_width")

        _LOGGER.debug(f"values given: X-Start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, line-color={l_color}, line-width={l_width}")

        await draw_line(hass, SERIAL, xs, ys, xe, ye, l_color, l_width)

    hass.services.async_register(const.DOMAIN, "draw_line", handle_draw_line)


    # --------------------------------------------------------
    # Service: draw progress bar
    # --------------------------------------------------------
    async def handle_draw_progress_bar(call: ServiceCall):
        _LOGGER.debug("called service to draw a progress bar")
 
        bar_min = call.data.get("bar_min")
        bar_value = call.data.get("bar_value")
        bar_max = call.data.get("bar_max")
        xs = call.data.get("x_start")
        ys = call.data.get("y_start")
        xe = call.data.get("x_end", None)
        ye = call.data.get("y_end", None)
        width = call.data.get("width", None)
        height = call.data.get("height", None)
        bf_width = call.data.get("bf_width", None)
        b_color = call.data.get("b_color", None)
        bf_color = call.data.get("bf_color", None)
        bg_color = call.data.get("bg_color", None)
        rotation = call.data.get("rotation", None)
        show_value = call.data.get("show_value", None)

        _LOGGER.debug(f"values given: X-start={xs}, Y-Start={ys}, X-End={xe}, Y-End={ye}, width={width}, height={height}, bar-frame-width={bf_width}, bar-frame-color={bf_color}, bar-color={b_color}, background-color={bg_color}, rotation={rotation}, show_value={show_value}")

        await draw_progress_bar(hass, SERIAL, xs, ys, xe=xe, ye=ye, width=width, height=height, bf_width=bf_width, b_color=b_color, bf_color=bf_color, bg_color=bg_color, rotation=rotation, show_value=show_value)

    hass.services.async_register(const.DOMAIN, "draw_progress_bar", handle_draw_progress_bar)


    # --------------------------------------------------------
    #   T H E   E N D  !
    # --------------------------------------------------------
    return True




