import asyncio, struct, logging
import subprocess
import time
import os
from PIL import Image, ImageDraw, ImageFont, ImageColor
import math
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import HomeAssistant
import custom_components.weact_display.const as const
from .const import CLOCK_REMOVE_HANDLE

_LOGGER = logging.getLogger(__name__)

#CLOCK_REMOVE_HANDLE = None
CLOCK_MODE = "idle"


#************************************************************************
#        A N A L O G  C L O C K
#************************************************************************
# shows the analog clock
#************************************************************************
# m: hass
# m: serial_number
# o: scale-color
# o: hour-color
# o: minute-color
# o: scale-fill-color
# o: offset-hours
# o: scale-size
# o: horizontal-shift
# o: vertical-shift
# o: rotation
#************************************************************************
async def show_analog_clock(hass, serial_number, sc_color = (255, 255, 255), h_color = (255, 0, 0), m_color = (127, 127, 127), scf_color = (0, 0, 0), offset_hours = 0, scale_size = None, h_shift = 0, v_shift = 0, rotation = 0):
    """zeigt die analoge Uhr an"""
    _LOGGER.debug("analog clock...")

#    from .commands import set_orientation, normalize_color, send_bitmap
    from .commands import set_orientation, normalize_color, send_screen

    data = hass.data[const.DOMAIN][serial_number]
    width = data.get("width")
    height = data.get("height")
    serial_port = data.get("serial_port")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    if scale_size is None:
        scale_size = min(width, height)
        _LOGGER.debug(f"set scale-size to {scale_size} px as no parameter is given")

    _LOGGER.debug(f"some clock values: width={width}, height={height}, scale-size={scale_size}")

    # check rotation

    # check position_shift
#    if shift > 39 or shift < -40:
#        shift = 0
#        _LOGGER.debug("position shift out of expected range. Changed to 0.")
    if h_shift > (width // 2 - 1) or h_shift < -(width // 2):
        _LOGGER.debug(f"horizontal position shift {h_shift} out of expected range. Changed to 0.")
        h_shift = 0
    if v_shift > (height // 2 - 1) or v_shift < -(height // 2):
        _LOGGER.debug(f"vertical position shift {v_shift} out of expected range. Changed to 0.")
        v_shift = 0

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    sc_color = normalize_color(sc_color)
    scf_color = normalize_color(scf_color)
    h_color = normalize_color(h_color)
    m_color = normalize_color(m_color)

#    _LOGGER.debug(f"colors after normalize: scale={sc_color}, scale-frame={scf_color}, hours={h_color}, minutes={m_color}, background = {bg_color}")
    _LOGGER.debug(f"colors after normalize: scale={sc_color}, scale-frame={scf_color}, hours={h_color}, minutes={m_color}")

    # Instanzbild holen
#    img = Image.new("RGB", (width, height), (0, 0, 0))
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("read image from instance")
    # Neues 80x80 Displaybild erstellen
#    img = Image.new("RGB", (80, 80), bg_color)
#    draw = ImageDraw.Draw(img)
#    width, height = img.size

#    _LOGGER.debug("defined new image")

    # Kreis und 4 Striche malen
#    draw.ellipse((0, 0, 79, 78), outline = sc_color, width = 2)                                   # Äußerer Kreis
#    draw.ellipse((39, 39, 41, 41), outline = sc_color, width = 4)    # punkt in der Mitte
#    draw.line((39, 2, 39, 6), fill = sc_color, width = 1)         # 12
#    draw.line((79, 39, 75, 39), fill = sc_color, width = 1)    # 3
#    draw.line((39, 79, 39, 75), fill = sc_color, width = 1)      # 6
#    draw.line((2, 39, 6, 39), fill = sc_color, width = 1)      # 9

    draw.ellipse((0, 0, width - 1, height - 1), fill = sc_color, outline = scf_color, width = 2)                        # Äußerer Kreis
    draw.ellipse((width // 2 - 1, width // - 1, width // 2 + 1, width // 2 + 1), outline = scf_color, width = 4)        # punkt in der Mitte
    draw.line((width // 2 - 1, 2, width // 2 - 1, 6), fill = sc_color, width = 1)         # 12
    draw.line((width - 1, width // 2 - 1, width - 5, width // 2 - 1), fill = sc_color, width = 1)    # 3
    draw.line((width // 2 - 1, width - 1, width // 2 - 1, width - 5), fill = sc_color, width = 1)      # 6
    draw.line((2, width // 2 - 1, 6, width // 2 - 1), fill = sc_color, width = 1)      # 9

    _LOGGER.debug("drew the scale")

    # Zeiger malen
    # Mittelpunkt (Displaymitte)
    cx = width // 2 - 1 + h_shift
    cy = width // 2 - 1 + v_shift
#    hour_length = 22
#    minute_length = 35
    hour_length = int(scale_size / 3.6)
    minute_length = int(scale_size / 2.3)

    # aktuelle Zeit holen
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
#    draw.line((cx, cy, hx, hy), fill = h_color, width=3)
#    draw.line((cx, cy, mx, my), fill = m_color, width=2)
    draw.line((cx, cy, hx, hy), fill = h_color, width=scale_size // 30)
    draw.line((cx, cy, mx, my), fill = m_color, width=scale_size // 40)

    _LOGGER.debug("drew the pointers")

    # ggf das Datum, den WT oder die CPU Temp einpflanzen
    # Text
#    font = ImageFont.load_default()
#    draw.text((10, 30), "Hallo Welt", fill=(255, 255, 255), font=font)
#    _LOGGER.debug("wrote into the image")

    # bild ggf drehen
#    img = img.rotate(rotation, expand=True)

    await send_screen(hass, serial_number)
    
    # Bild extrahieren
#    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    # Save the image
#    try:
#        _LOGGER.debug(f"Saving analog clock to {const.IMG_PATH}")
#        await asyncio.to_thread(lambda: img.save(const.IMG_PATH / "a_clock.bmp"))
#    except Exception as e:
#        _LOGGER.error(f"[{const.DOMAIN}] error while saving the analog clock to {const.IMG_PATH}: {e}")
#
#    _LOGGER.debug(f"clock has {width}x{height} pixels")
#    px = width * height
#    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
#    _LOGGER.debug(f"expected analog clock size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
#    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
#    _LOGGER.debug(f"prepared {len(img_bytes)} analog clock bytes for {serial_port}: {hex_str} [...]")

#    xs = 39 + shift
#    xe = 119 + shift

    # Bild ans display schicken, hier auch noch mal den Versatz prüfen
#    await set_orientation(hass, serial_port, 2)
#    try:
#        await send_bitmap(hass, serial_port, xs, 0, xe, 79, bytes(img_bytes))
#    except Exception as e:
#        _LOGGER.error(f"[{const.DOMAIN}] error while sending the analog clock: {e}")


async def show_digital_clock(hass, serial_port, xs = 0, ys = 0, digit_size = 30, rotation = 0, d_color = (0, 255, 255), bg_color = (0, 0, 0), cf_color = (0, 255, 255), cf_width = 0, offset_hours = 0, am_pm = False):
    """zeigt die digitale Uhr an"""
    _LOGGER.debug("digital clock...")

    from .commands import set_orientation, normalize_color, send_bitmap

    # check rotation

    # check position_shift
    
    # Konvertiere mögliche Stringfarben in RGB-Tupel
    d_color = normalize_color(d_color)
    cf_color = normalize_color(cf_color)
    bg_color = normalize_color(bg_color)

    _LOGGER.debug(f"colors after normalize: digits={d_color}, clock-frame-color={cf_color}, clock-frame-width={cf_width}, background={bg_color}")

    disp_w = 160
    disp_h = 80
    state = hass.states.get("sensor.weact_display_info_2")
    if state:
        disp_w = state.attributes.get("width", 160)
        disp_h = state.attributes.get("height", 80)
        _LOGGER.debug(f"read values from display sensor: width={disp_w}, height={disp_h}")
    else:
        _LOGGER.error(f"error reading width and height from display sensor, falling back to 160x80 px.")
    
    # vertical value check
    dc_height = digit_size + 2 + cf_width
    if dc_height > disp_h:
        dc_height = disp_h
#    if font_size + 2 > cf_height:
#        font_size = cf_height - 2
    if digit_size + 2 + cf_width > dc_height:
        digit_size = dc_height - cf_width - 2
    if ys + dc_height > disp_h:
        ys = disp_h - dc_height

    _LOGGER.debug(f"values after vertical check: digital-clock-height={dc_height}, font-size={digit_size}, Y-Start={ys}")

    # aktuelle Zeit holen
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    if am_pm:
        hour = hour % 12
        if hour == 0:
            hour = 12
    time_str = f"{hour:02d}:{minute:02d}"

    _LOGGER.debug(f"time-string={time_str}")

    # horizontal value check
    try:
#        font = ImageFont.truetype("DejaVuSans-Bold.ttf", digit_size)
        font = await hass.async_add_executor_job(ImageFont.truetype, "DejaVuSans-Bold.ttf", digit_size)
    except Exception as e:
        font = ImageFont.load_default()
        _LOGGER.error(f"[{const.DOMAIN}] could not load TTF due to: {e}")

    # Textgröße messen
    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), time_str, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    _LOGGER.debug(f"time-string dimensions: width={text_w}, height={text_h} px")

    # Rahmen einberechnen
    dc_width = text_w + (cf_width * 2) + 4   # kleiner Puffer
    dc_height = text_h + (cf_width * 2) + 4

    # Begrenzen auf Display
    dc_width = min(dc_width, disp_w)
    dc_height = min(dc_height, disp_h)

    # Neues 80x80 Displaybild erstellen
    img = Image.new("RGB", (dc_width, dc_height), bg_color)
    i_width, i_height = img.size

    _LOGGER.debug("defined new image")

    draw = ImageDraw.Draw(img)
#    text_w, text_h = draw.textsize(value_str, font=font)

    if cf_width > 0:
        draw.rectangle((0, 0, dc_width - 1, dc_height - 1), outline=cf_color, width=cf_width)
#        draw.rectangle((0, 0, width, height), width = cf_width, outline = cf_color, fill = bg_color)

    _LOGGER.debug("drew the frame")

   # Text mittig
#    text_x = (dc_width - text_w) // 2
#    text_y = (dc_height - text_h) // 2
#    draw.text((text_x, text_y), time_str, fill=d_color, font=font)

    draw.text((0, 0), time_str, fill=d_color, font=font)

    _LOGGER.debug("wrote the time into the image")

    # bild ggf drehen
    img = img.rotate(rotation, expand=True)
    out_w, out_h = img.size
    
    # Save the image
    try:
        _LOGGER.debug(f"Saving digital clock to {const.IMG_PATH}")
        await asyncio.to_thread(lambda: img.save(const.IMG_PATH / "d_clock.bmp"))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while saving the digital clock to {const.IMG_PATH}: {e}")

    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    px = out_w * out_h
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected digital clock size from coordinates should be {out_w}x{out_h} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} digital clock bytes for {serial_port}: {hex_str} [...]")

    # Bild ans display schicken, hier auch noch mal den Versatz prüfen
    await set_orientation(hass, serial_port, 2)
    try:
#        await send_bitmap(hass, serial_port, 39 + position_shift, 0, 119 + position_shift, 79, bytes(img_bytes))
#        await send_bitmap(hass, serial_port, xs, ys, xs + width, ys + height, bytes(img_bytes))
        await send_bitmap(hass, serial_port, xs, ys, xs + out_w - 1, ys + out_h - 1, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the digital clock: {e}")

    # entsprechend versetzten Ausschnitt "befreien", ggf noch 1 px r/l mehr


    # timer setzen auf 60 Sekunden

    # Timer wird unterbrochen durch...?

async def show_rheinturm(hass, serial_port, rotation = 0):
    """zeigt die digitale Uhr an"""
    _LOGGER.debug("rheinturm...")

    from .commands import set_orientation, normalize_color, send_bitmap

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
    draw.ellipse((0, 0, 79, 78), outline = sc_color, width = 2)                                   # Äußerer Kreis
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
    await set_orientation(hass, serial_port, 2)
    try:
#        await send_bitmap(hass, serial_port, 39 + position_shift, 0, 119 + position_shift, 79, bytes(img_bytes))
        await send_bitmap(hass, serial_port, xs, 0, xe, 79, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the digital clock: {e}")

    # entsprechend versetzten Ausschnitt "befreien", ggf noch 1 px r/l mehr


    # timer setzen auf 60 Sekunden

    # Timer wird unterbrochen durch...?


async def stop_clock(hass, serial_number):
    """Beendet alle Uhr-Routinen"""
    _LOGGER.debug("stopping any running clock ...")

    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    _LOGGER.debug(f"actually running clock: '{CLOCK_MODE}'")

    if CLOCK_REMOVE_HANDLE is not None:
        CLOCK_REMOVE_HANDLE()
        CLOCK_REMOVE_HANDLE = None
        _LOGGER.debug("deleted CLOCK_HANDLE")
    else:
        _LOGGER.debug(f"unplanned call as no clock was active or planned call while startup")

    if CLOCK_MODE != "idle":
        CLOCK_MODE = "idle"
        _LOGGER.debug("clock schedule stopped")

#    hass.states.async_set("weact_display.clock_status", CLOCK_MODE)
    info_entity = hass.data[const.DOMAIN].get("info_entity")
    if info_entity:
        info_entity.set_clock_status(CLOCK_MODE)

#async def start_analog_clock(hass, serial_port, **kwargs):
async def start_analog_clock(hass, serial_number, **kwargs):
    """Startet die Analoguhr über den HA-Timer."""
    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    async def _update_analog(now):
        await show_analog_clock(hass, serial_number, **kwargs)

    clock_mode = hass.data[const.DOMAIN].get("clock_mode")
#    if CLOCK_REMOVE_HANDLE:
    if clock_mode is "analog":
        _LOGGER.debug(f"Clock for {serial_number} already running: {clock_mode}, stopping first")
        await stop_clock(hass, serial_number)

    await show_analog_clock(hass, serial_number, **kwargs)

    CLOCK_REMOVE_HANDLE = async_track_time_interval(hass, _update_analog, timedelta(minutes=1))
    hass.data[const.DOMAIN][serial_number]["clock_mode"] = "analog"

    _LOGGER.debug(f"set clock status from '{clock_mode}' to '{hass.data[const.DOMAIN][serial_number]["clock_mode"]}'")
    _LOGGER.warning("Analog clock update scheduled every minute")

async def start_digital_clock(hass, serial_port, **kwargs):
    """Startet die Digitaluhr über den HA-Timer."""
    _LOGGER.warning("Digital clock entry function")

    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    async def _update_digital(now):
        await show_digital_clock(hass, serial_port, **kwargs)

    if CLOCK_REMOVE_HANDLE:
        _LOGGER.debug(f"Clock already running: {CLOCK_MODE}, stopping first")
        await stop_clock(hass)

    await show_digital_clock(hass, serial_port, **kwargs)

    CLOCK_REMOVE_HANDLE = async_track_time_interval(hass, _update_digital, timedelta(minutes=1))
    CLOCK_MODE = "digital"
#    hass.states.async_set("weact_display.clock_status", CLOCK_MODE)
    info_entity = hass.data[const.DOMAIN].get("info_entity")
    if info_entity:
        info_entity.set_clock_status(CLOCK_MODE)

    _LOGGER.debug(f"set status to {CLOCK_MODE}")
    _LOGGER.warning("Digital clock update scheduled every minute")

async def _start_rheinturm_clock(hass, serial_port, **kwargs):
    """Startet die Rheinturm-Uhr über den HA-Timer."""
    _LOGGER.warning("Rheinturm entry function")

    global CLOCK_REMOVE_HANDLE, CLOCK_MODE

    async def _update_rheinturm(now):
        await show_rheinturm(hass, serial_port, **kwargs)

    if CLOCK_REMOVE_HANDLE:
        _LOGGER.warning(f"Clock already running: {CLOCK_MODE}")
        await stop_clock(hass)
#        return

    await show_digital_clock(hass, serial_port, **kwargs)

    CLOCK_REMOVE_HANDLE = async_track_time_interval(hass, _update_rheinturm, timedelta(seconds=1))
    CLOCK_MODE = "rheinturm"
#    hass.states.async_set("weact_display.clock_status", CLOCK_MODE)
    info_entity = hass.data[const.DOMAIN].get("info_entity")
    if info_entity:
        info_entity.set_clock_status(CLOCK_MODE)

    _LOGGER.debug(f"set status to {CLOCK_MODE}")
    _LOGGER.warning("Rheinturm update scheduled every second")


