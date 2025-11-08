import asyncio, struct, logging
import subprocess
import time
import os
from PIL import Image, ImageDraw, ImageFont, ImageColor
import math
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import HomeAssistant
from .const import CLOCK_REMOVE_HANDLE

_LOGGER = logging.getLogger(__name__)

#CLOCK_REMOVE_HANDLE = None
CLOCK_MODE = "idle"

async def show_analog_clock(hass, serial_port, sc_color = (255, 255, 255), h_color = (255, 0, 0), m_color = (127, 127, 127), bg_color = (0, 0, 0), offset_hours = 0, shift = 0, rotation = 0):
    """zeigt die analoge Uhr an"""
    _LOGGER.debug("analog clock...")

    from .commands import set_orientation, normalize_color, send_bitmap

    await set_orientation(hass, serial_port, 2)

    # check rotation

    # check position_shift
    if shift > 39 or shift < -39:
        shift = 0
        _LOGGER.debug("position shift out of expected range. Changed to 0.")
        
    
    # Konvertiere mögliche Stringfarben in RGB-Tupel
    sc_color = normalize_color(sc_color)
    h_color = normalize_color(h_color)
    m_color = normalize_color(m_color)
    bg_color = normalize_color(bg_color)

    _LOGGER.debug(f"colors after normalize: scale = {sc_color}, hours = {h_color}, minutes = {m_color}, background = {bg_color}")

    # Neues 80x80 Displaybild erstellen
    img = Image.new("RGB", (80, 80), bg_color)
    draw = ImageDraw.Draw(img)
    width, height = img.size

    _LOGGER.debug("defined new image")

    # Kreis und 4 Striche malen
    draw.ellipse((0, 0, 79, 79), outline = sc_color, width = 2)                                   # Äußerer Kreis
    draw.ellipse((39, 39, 41, 41), outline = sc_color, width = 4)    # punkt in der Mitte
    draw.line((39, 2, 39, 6), fill = sc_color, width = 1)         # 12
    draw.line((79, 39, 75, 39), fill = sc_color, width = 1)    # 3
    draw.line((39, 79, 39, 75), fill = sc_color, width = 1)      # 6
    draw.line((2, 39, 6, 39), fill = sc_color, width = 1)      # 9

    _LOGGER.debug("drew the scale")

    # Zeiger malen
    cx = 39        # Mittelpunkt (Displaymitte)
    cy = 39
    hour_length = 22
    minute_length = 35

    # aktuelle Zeit holen (oder fest vorgeben)
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # Winkel berechnen (12 Uhr = -90°)
    hour_angle = (hour % 12) * 30 + (minute / 60) * 30 - 90
    minute_angle = minute * 6 - 90

    # Zeiger-Endpunkte berechnen
    hx = cx + hour_length * math.cos(math.radians(hour_angle))
    hy = cy + hour_length * math.sin(math.radians(hour_angle))
    mx = cx + minute_length * math.cos(math.radians(minute_angle))
    my = cy + minute_length * math.sin(math.radians(minute_angle))

    # Zeiger zeichnen
    draw.line((cx, cy, hx, hy), fill = h_color, width=3)
    draw.line((cx, cy, mx, my), fill = m_color, width=2)

    _LOGGER.debug("drew the pointers")

    # ggf das Datum, den WT oder die CPU Temp einpflanzen
    # Text
#    font = ImageFont.load_default()
#    draw.text((10, 30), "Hallo Welt", fill=(255, 255, 255), font=font)
#    _LOGGER.debug("wrote into the image")

    # bild ggf drehen
    img = img.rotate(rotation, expand=True)
    
    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    _LOGGER.debug(f"clock has {width}x{height} pixels")
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected analog clock size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} analog clock bytes for {serial_port}: {hex_str} [...]")

    xs = 39 + shift
    xe = 119 + shift

    # Bild ans display schicken, hier auch noch mal den Versatz prüfen
    try:
        await send_bitmap(hass, serial_port, xs, 0, xe, 79, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the analog clock: {e}")


#async def show_digital_clock(hass, serial_port, xs, ys, font_size = 30, rotation = 0, h_color = (0, 255, 255), p_color = (0, 255, 255), m_color = (0, 255, 255), bg_color = (0, 0, 0), offset_hours = 0, frame = 0, font = None):
#async def show_digital_clock(hass, serial_port, xs, ys, font_size = 30, rotation = 0, h_color = (0, 255, 255), p_color = (0, 255, 255), m_color = (0, 255, 255), bg_color = (0, 0, 0)):
async def show_digital_clock(hass, serial_port, xs, ys, font_size = 30, rotation = 0, d_color = (0, 255, 255), bg_color = (0, 0, 0)):
    """zeigt die digitale Uhr an"""
    _LOGGER.debug("digital clock...")

    from .commands import set_orientation, normalize_color, send_bitmap

    await set_orientation(hass, serial_port, 2)

    # check rotation

    # check position_shift
    
    # Konvertiere mögliche Stringfarben in RGB-Tupel
    d_color = normalize_color(d_color)
    bg_color = normalize_color(bg_color)

#    _LOGGER.debug(f"colors after normalize: hours = {h_color}, pointer = {p_color}, minutes = {m_color}, background = {bg_color}")
    _LOGGER.debug(f"colors after normalize: digits = {d_color}, background = {bg_color}")

    # calculate need dimensions
    

    # Neues 80x80 Displaybild erstellen
    img = Image.new("RGB", (80, 80), bg_color)
    draw = ImageDraw.Draw(img)
    i_width, i_height = img.size

    _LOGGER.debug("defined new image")

    # Kreis und 4 Striche malen
    draw.ellipse((0, 0, 79, 79), outline = sc_color, width = 2)                                   # Äußerer Kreis
    draw.ellipse((39, 39, 41, 41), outline = sc_color, width = 4)    # punkt in der Mitte
    draw.line((39, 2, 39, 6), fill = sc_color, width = 1)         # 12
    draw.line((79, 39, 75, 39), fill = sc_color, width = 1)    # 3
    draw.line((39, 79, 39, 75), fill = sc_color, width = 1)      # 6
    draw.line((2, 39, 6, 39), fill = sc_color, width = 1)      # 9

    _LOGGER.debug("drew the scale")

    # Zeiger malen
    cx = 39        # Mittelpunkt (Displaymitte)
    cy = 39
    hour_length = 22
    minute_length = 35

    # aktuelle Zeit holen (oder fest vorgeben)
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # Winkel berechnen (12 Uhr = -90°)
    hour_angle = (hour % 12) * 30 + (minute / 60) * 30 - 90
    minute_angle = minute * 6 - 90

    # Zeiger-Endpunkte berechnen
    hx = cx + hour_length * math.cos(math.radians(hour_angle))
    hy = cy + hour_length * math.sin(math.radians(hour_angle))
    mx = cx + minute_length * math.cos(math.radians(minute_angle))
    my = cy + minute_length * math.sin(math.radians(minute_angle))

    # Zeiger zeichnen
    draw.line((cx, cy, hx, hy), fill = h_color, width=3)
    draw.line((cx, cy, mx, my), fill = m_color, width=2)

    _LOGGER.debug("drew the pointers")

    # ggf das Datum, den WT oder die CPU Temp einpflanzen
    # Text
#    font = ImageFont.load_default()
#    draw.text((10, 30), "Hallo Welt", fill=(255, 255, 255), font=font)
#    _LOGGER.debug("wrote into the image")

    # bild ggf drehen
    img = img.rotate(rotation, expand=True)
    
    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    _LOGGER.debug(f"clock has {width}x{height} pixels")
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected digital clock size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} digital clock bytes for {serial_port}: {hex_str} [...]")

    xs = 39 + shift
    xe = 119 + shift

    # Bild ans display schicken, hier auch noch mal den Versatz prüfen
    try:
#        await send_bitmap(hass, serial_port, 39 + position_shift, 0, 119 + position_shift, 79, bytes(img_bytes))
        await send_bitmap(hass, serial_port, xs, 0, xe, 79, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the digital clock: {e}")

    # entsprechend versetzten Ausschnitt "befreien", ggf noch 1 px r/l mehr


    # timer setzen auf 60 Sekunden

    # Timer wird unterbrochen durch...?

async def show_rheinturm(hass, serial_port, rotation = 0):
    """zeigt die digitale Uhr an"""
    _LOGGER.debug("rheinturm...")

    from .commands import set_orientation, normalize_color, send_bitmap

    await set_orientation(hass, serial_port, 2)

    # check for first call
      # draw the tower
      
      # set all digits to off
    
      # draw digits
    
      # time to digits

    # get now()

    # check for s = 0
      # draw hour and minute
      
    # draw seconds
    
    # check rotation

    # convert colors 888>565

    # transfer image to display

    # calculate need dimensions
    
    # Neues 80x80 Displaybild erstellen
    img = Image.new("RGB", (80, 80), bg_color)
    draw = ImageDraw.Draw(img)
    i_width, i_height = img.size

    _LOGGER.debug("defined new image")

    # Kreis und 4 Striche malen
    draw.ellipse((0, 0, 79, 79), outline = sc_color, width = 2)                                   # Äußerer Kreis
    draw.ellipse((39, 39, 41, 41), outline = sc_color, width = 4)    # punkt in der Mitte
    draw.line((39, 2, 39, 6), fill = sc_color, width = 1)         # 12
    draw.line((79, 39, 75, 39), fill = sc_color, width = 1)    # 3
    draw.line((39, 79, 39, 75), fill = sc_color, width = 1)      # 6
    draw.line((2, 39, 6, 39), fill = sc_color, width = 1)      # 9

    _LOGGER.debug("drew the scale")

    # Zeiger malen
    cx = 39        # Mittelpunkt (Displaymitte)
    cy = 39
    hour_length = 22
    minute_length = 35

    # aktuelle Zeit holen (oder fest vorgeben)
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # Winkel berechnen (12 Uhr = -90°)
    hour_angle = (hour % 12) * 30 + (minute / 60) * 30 - 90
    minute_angle = minute * 6 - 90

    # Zeiger-Endpunkte berechnen
    hx = cx + hour_length * math.cos(math.radians(hour_angle))
    hy = cy + hour_length * math.sin(math.radians(hour_angle))
    mx = cx + minute_length * math.cos(math.radians(minute_angle))
    my = cy + minute_length * math.sin(math.radians(minute_angle))

    # Zeiger zeichnen
    draw.line((cx, cy, hx, hy), fill = h_color, width=3)
    draw.line((cx, cy, mx, my), fill = m_color, width=2)

    _LOGGER.debug("drew the pointers")

    # ggf das Datum, den WT oder die CPU Temp einpflanzen
    # Text
#    font = ImageFont.load_default()
#    draw.text((10, 30), "Hallo Welt", fill=(255, 255, 255), font=font)
#    _LOGGER.debug("wrote into the image")

    # bild ggf drehen
    img = img.rotate(rotation, expand=True)
    
    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    _LOGGER.debug(f"clock has {width}x{height} pixels")
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected digital clock size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} digital clock bytes for {serial_port}: {hex_str} [...]")

    xs = 39 + shift
    xe = 119 + shift

    # Bild ans display schicken, hier auch noch mal den Versatz prüfen
    try:
#        await send_bitmap(hass, serial_port, 39 + position_shift, 0, 119 + position_shift, 79, bytes(img_bytes))
        await send_bitmap(hass, serial_port, xs, 0, xe, 79, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the digital clock: {e}")

    # entsprechend versetzten Ausschnitt "befreien", ggf noch 1 px r/l mehr


    # timer setzen auf 60 Sekunden

    # Timer wird unterbrochen durch...?


async def stop_clock(hass):
    """Beendet alle Uhr-Routinen"""
    _LOGGER.debug("stopping any running clock ...")

    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    if CLOCK_REMOVE_HANDLE is not None:
        _LOGGER.debug(f"actually running clock: '{CLOCK_MODE}'")
        CLOCK_REMOVE_HANDLE()
        CLOCK_REMOVE_HANDLE = None
        CLOCK_MODE = "idle"
#        hass.states.async_set("weact_display.clock_status", state)
#        hass.states.async_set("weact_display.clock_status", CLOCK_MODE)
        _LOGGER.debug("clock schedule stopped")
#    await update_clock_sensor(hass, CLOCK_MODE)
#        _LOGGER.warning(f"Clock mode set to {CLOCK_MODE}")
#    _LOGGER.warning("disabled any running clocks '{}'")
    else:
        _LOGGER.debug(f"unplanned call as no clock was active or planned while startup")

async def start_analog_clock(hass, serial_port, **kwargs):
    """Startet die Analoguhr über den HA-Timer."""
    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    async def _update_analog(now):
        await show_analog_clock(hass, serial_port, **kwargs)

    if CLOCK_REMOVE_HANDLE:
        _LOGGER.warning(f"Clock already running: {CLOCK_MODE}")
        return

    CLOCK_REMOVE_HANDLE = async_track_time_interval(hass, _update_analog, timedelta(minutes=1))
    CLOCK_MODE = "analog"
#    hass.states.async_set("weact_display.clock_status", CLOCK_MODE)

    _LOGGER.warning("Analog clock update scheduled every minute")

async def start_digital_clock(hass, serial_port, **kwargs):
    """Startet die Digitaluhr über den HA-Timer."""
    _LOGGER.warning("Digital clock update scheduled every minute")

    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    async def _update_digital(now):
        await show_digital_clock(hass, serial_port, **kwargs)

    if CLOCK_REMOVE_HANDLE:
        _LOGGER.warning(f"Clock already running: {CLOCK_MODE}")
        return

    CLOCK_REMOVE_HANDLE = async_track_time_interval(hass, _update_digital, timedelta(minutes=1))
    CLOCK_MODE = "digital"
#    hass.states.async_set("weact_display.clock_status", CLOCK_MODE)

    _LOGGER.warning("Digital clock update scheduled every minute")

async def _start_rheinturm_clock(hass, serial_port, **kwargs):
    """Startet die Rheinturm-Uhr über den HA-Timer."""
    _LOGGER.warning("Rheinturm clock update scheduled every minute")

    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    async def _update_rheinturm(now):
        await show_rheinturm(hass, serial_port, **kwargs)

    if CLOCK_REMOVE_HANDLE:
        _LOGGER.warning(f"Clock already running: {CLOCK_MODE}")
        return

    CLOCK_REMOVE_HANDLE = async_track_time_interval(hass, _update_rheinturm, timedelta(seconds=1))
    CLOCK_MODE = "rheinturm"
#    hass.states.async_set("weact_display.clock_status", CLOCK_MODE)

    _LOGGER.warning("rheinturm update scheduled every second")


