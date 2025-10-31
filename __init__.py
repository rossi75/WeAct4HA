"""
WeAct Display FS Integration for Home Assistant

toDo:
- random bitmap P1
- testbild
- umbau für public/github
- qr code
- send text with font/size/pos/ft-color/bg-color/orientation/...
- draw lines and circles
- clear screen
- analog/digital clock, wird solange minütlich aktualisiert bis ein neues Kommando kommt
- pic from file
- set orientation
- lautstärke
- trigger testen
- temp/humid
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
from .commands import send_bitmap, send_full_color, send_text, generate_random, open_serial, display_selftest, show_init_screen, set_orientation, show_analog_clock, set_brightness, show_testbild, show_icon
from .bitmap import text_to_bitmap_bytes

DOMAIN = "weact_display"
_LOGGER = logging.getLogger(__name__)

SERIAL = None

# ------------------------------------------------------------
# Initialisierung
# ------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Setup der WeAct Display Integration."""
    _LOGGER.debug(f"starting up weact display FS V1")

    global SERIAL

    # Sensor-Plattform laden
    await async_load_platform(hass, "sensor", DOMAIN, {}, config)
    hass.data[DOMAIN] = {
        "ready": False,
        "start_time": datetime.datetime.now().isoformat(),
        "device_id": None,
    }

    _LOGGER.debug(f"Sensor platform loaded")

    # Gerät automatisch suchen
    paths = await asyncio.to_thread(glob.glob, "/dev/serial/by-id/*WeAct*")
    port = paths[0] if paths else "/dev/ttyACM0"

    _LOGGER.debug(f"found {paths}, shoud be equal to {port}")

    hass.data[DOMAIN]["device_id"] = os.path.basename(port)

    try:
        _LOGGER.debug(f"opening serial port {port}")

        SERIAL = await hass.async_add_executor_job(open_serial, port)
        if SERIAL is None:
            _LOGGER.warning(f"[{DOMAIN}] Abbruch: Serial port konnte nicht geöffnet werden!")
            return False

        _LOGGER.debug(f"[{DOMAIN}] selftest...")

        await display_selftest(hass, SERIAL)
        hass.data[DOMAIN]["ready"] = True
        hass.bus.async_fire("weact_display_ready", {"timestamp": hass.data[DOMAIN]["start_time"]})          # das Event auf welches abgefragt werden kann

        _LOGGER.warning(f"[{DOMAIN}] Display at {port} is now ready")

    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] Error while initializing display: %s", e)
        return False

    # --------------------------------------------------------
    # Service: Text anzeigen
    # --------------------------------------------------------
    async def handle_send_text(call: ServiceCall):
        """Render Text und sende als Bitmap."""
        if not SERIAL:
            _LOGGER.warning(f"[{DOMAIN}] Display nicht verbunden")
            return

        text = call.data.get("text", "")
        color = tuple(call.data.get("color", [255, 255, 255]))
        bgcolor = tuple(call.data.get("bgcolor", [0, 0, 0]))
        width = int(call.data.get("width", 160))
        height = int(call.data.get("height", 80))
        align = call.data.get("align", "left")
        font_size = int(call.data.get("font_size", 16))
        font = call.data.get("font", None)

        try:
            bmp = text_to_bitmap_bytes(
                text,
                width=width,
                height=height,
                color=color,
                bgcolor=bgcolor,
                align=align,
                font_size=font_size,
                font=font
            )
            await send_bitmap(SERIAL, 0, 0, width - 1, height - 1, bmp)
            _LOGGER.warning("Text angezeigt: '%s' (%dx%d, fg=%s, bg=%s, align=%s)",
                         text, width, height, color, bgcolor, align)
        except Exception as e:
            _LOGGER.error("Fehler beim Rendern/Senden des Textes: %s", e)

    hass.services.async_register(DOMAIN, "send_text", handle_send_text)


    # --------------------------------------------------------
    # Service: Zufallsbild anzeigen
    # --------------------------------------------------------
    async def handle_show_random(call: ServiceCall):
        """Erzeugt ein zufälliges Bitmap und sendet es an das Display."""
        _LOGGER.debug("called service for random bmp")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        await generate_random(hass, call, SERIAL)

    hass.services.async_register(DOMAIN, "show_random", handle_show_random)


    # --------------------------------------------------------
    # Service: Selbsttest aufrufen
    # --------------------------------------------------------
    async def handle_start_selftest(call: ServiceCall):
        """startet den Selbsttest wie bei der Initialisierung"""
        _LOGGER.debug("called service for display selftest")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        await display_selftest(hass, SERIAL)

    hass.services.async_register(DOMAIN, "start_selftest", handle_start_selftest)


    # --------------------------------------------------------
    # Service: Display Neustart
    # --------------------------------------------------------
    async def handle_restart_display(call: ServiceCall):
        """startet das Display neu"""
        _LOGGER.debug("called service for display restart")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        await display_restart(hass, SERIAL)

    hass.services.async_register(DOMAIN, "restart_display", handle_restart_display)


    # --------------------------------------------------------
    # Service: Initiale Displayanzeige aufrufen
    # --------------------------------------------------------
    async def handle_show_init_screen(call: ServiceCall):
        """startet den Selbsttest wie bei der Initialisierung"""
        _LOGGER.debug("called service for initial screen")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        await show_init_screen(hass, SERIAL)

    hass.services.async_register(DOMAIN, "show_init_screen", handle_show_init_screen)


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

    hass.services.async_register(DOMAIN, "set_orientation", handle_set_orientation)

    # --------------------------------------------------------
    # Service: Lautstärke festlegen
    # --------------------------------------------------------
    async def handle_set_brightness(call: ServiceCall):
        """Erzeugt ein zufälliges Bitmap und sendet es an das Display."""
        _LOGGER.debug("called service for brightness")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        brightness_value = call.data.get("brightness")
        _LOGGER.debug(f"value given: brightness={brightness_value}")
        await set_brightness(hass, SERIAL, brightness_value)

    hass.services.async_register(DOMAIN, "set_brightness", handle_set_brightness)

    # --------------------------------------------------------
    # Service: Full color
    # --------------------------------------------------------
    async def handle_set_full_color(call: ServiceCall):
        """display in ONE color"""
        _LOGGER.debug("called service for one color")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        color_value = call.data.get("color")
        _LOGGER.debug(f"value given: color={color_value}")
        await send_full_color(hass, SERIAL, color_value)

    hass.services.async_register(DOMAIN, "set_full_color", handle_set_full_color)

    # --------------------------------------------------------
    # Service: Testbild
    # --------------------------------------------------------
    async def handle_show_testbild(call: ServiceCall):
        """display in ONE color"""
        _LOGGER.debug("called service for testbild")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        await show_testbild(hass, SERIAL)

    hass.services.async_register(DOMAIN, "show_testbild", handle_show_testbild)


    # --------------------------------------------------------
    # Service: Analoguhr
    # --------------------------------------------------------
    async def handle_show_analog_clock(call: ServiceCall):
        """legt die Ausrichtung fest"""
        _LOGGER.debug("called service for analog clock")
 
        scale_color = call.data.get("sc_color")
        hour_color = call.data.get("hh_color")
        minute_color = call.data.get("mm_color")
        background_color = call.data.get("bg_color")
        offset_hours = call.data.get("offset")
        position_value = call.data.get("position")
        orientation_value = call.data.get("orientation")
        opcode = 0

        _LOGGER.debug(f"values given: orientation={orientation_value}, position={position_value}, offset={offset_hours}, bg-color={background_color}, minute-color={minute_color}, hour-color={hour_color}, scale-color={scale_color}")

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

        await show_analog_clock(hass, SERIAL, scale_color, hour_color, minute_color, background_color, offset_hours, position_value, orientation_value)

    hass.services.async_register(DOMAIN, "show_analog_clock", handle_show_analog_clock)


    # --------------------------------------------------------
    # Service: Show Icon
    # --------------------------------------------------------
    async def handle_show_icon(call: ServiceCall):
        """display in ONE color"""
        _LOGGER.debug("called service for icon")
        if not SERIAL:
            _LOGGER.warning("Display not connected")
            return
        
        icon_name = call.data.get("icon_name")
        bg_color = call.data.get("bg_color")
        icon_color = call.data.get("icon_color")
        x_position = call.data.get("x_position")
        y_position = call.data.get("y_position")
        size = call.data.get("size")
        rotation = call.data.get("rotation")

        _LOGGER.debug(f"values given: icon={icon_name}, bg_color={bg_color}, icon_color={icon_color}, ={x_position}, ={y_position}, ={size}, ={rotation}")

        #async def show_icon
        #(hass, serial_port, icon_name: str, bg_color = (0, 0, 0), icon_color = (0, 0, 0), x_position = 0, y_position = 0, size = 32, orientation = 0):
        #        await show_icon(hass, SERIAL, call)
        #async def show_icon(icon_name: str, color="#FFFFFF", size=(48, 48), bg_color="#000000"):
        await show_icon(hass, SERIAL, icon_name = icon_name, bg_color = bg_color, icon_color = icon_color, x_position = x_position, y_position = y_position, size = size, rotation = rotation)

    hass.services.async_register(DOMAIN, "show_icon", handle_show_icon)

    return True




