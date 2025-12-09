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

_LOGGER = logging.getLogger(__name__)

async def stop_clock(hass, serial_number):
    """Beendet alle Uhr-Routinen"""
    _LOGGER.debug(f"stopping any running clock for serial {serial_number}...")

    data = hass.data[const.DOMAIN][serial_number]
    clock_mode = data.get("clock_mode")
    clock_handle = data.get("clock_handle")

    _LOGGER.debug(f"actually running clock-mode is {clock_mode}")

    if clock_handle is not None:
        clock_handle()
        data["clock_handle"] = None
        data["clock_mode"] = None
        _LOGGER.debug(f"deleted clock_handle")
    else:
        _LOGGER.debug(f"unplanned call as no clock was active or planned call while startup")


async def start_analog_clock(hass, serial_number, **kwargs):

    async def _update_analog(now):
        await show_analog_clock(hass, serial_number, **kwargs)

    clock_mode = hass.data[const.DOMAIN][serial_number].get("clock_mode")
    if clock_mode is not None:
        _LOGGER.debug(f"Clock for {serial_number} already running as {clock_mode}, stopping first")
        await stop_clock(hass, serial_number)

    hass.data[const.DOMAIN][serial_number]["clock_mode"] = "analog"
    await show_analog_clock(hass, serial_number, **kwargs)

    async def _task():
        seconds_to_wait = 60 - datetime.now().second
        _LOGGER.debug(f"need to wait {seconds_to_wait} seconds for the next minute")
        await asyncio.sleep(seconds_to_wait)
        await show_analog_clock(hass, serial_number, **kwargs)
        hass.data[const.DOMAIN][serial_number]["clock_handle"] = async_track_time_interval(hass, _update_analog, timedelta(minutes=1))
    asyncio.create_task(_task())

    _LOGGER.debug(f"set clock-mode from {clock_mode} to {hass.data[const.DOMAIN][serial_number]["clock_mode"]}")
    _LOGGER.warning("Analog clock update scheduled every minute")

async def start_digital_clock(hass, serial_number, **kwargs):

    async def _update_digital(now):
        await show_digital_clock(hass, serial_number, **kwargs)

    clock_mode = hass.data[const.DOMAIN][serial_number].get("clock_mode")
    if clock_mode is not None:
        _LOGGER.debug(f"Clock for {serial_number} already running as {clock_mode}, stopping first")
        await stop_clock(hass, serial_number)

    await show_digital_clock(hass, serial_number, **kwargs)

    hass.data[const.DOMAIN][serial_number]["clock_handle"] = async_track_time_interval(hass, _update_digital, timedelta(minutes=1))
    hass.data[const.DOMAIN][serial_number]["clock_mode"] = "digital"

    _LOGGER.debug(f"set clock-mode from {clock_mode} to {hass.data[const.DOMAIN][serial_number]["clock_mode"]}")
    _LOGGER.warning("Digital clock update scheduled every minute")

async def _start_rheinturm_clock(hass, serial_number, **kwargs):

    async def _update_rheinturm(now):
        await show_rheinturm(hass, serial_number, **kwargs)

    clock_mode = hass.data[const.DOMAIN][serial_number].get("clock_mode")
    if clock_mode is not None:
        _LOGGER.debug(f"Clock for {serial_number} already running: {clock_mode}, stopping first")
        await stop_clock(hass, serial_number)

    await show_rheinturm(hass, serial_number, **kwargs)

    hass.data[const.DOMAIN][serial_number]["clock_handle"] = async_track_time_interval(hass, _update_digital, timedelta(minutes=1))
    hass.data[const.DOMAIN][serial_number]["clock_mode"] = "Rheinturm"

    _LOGGER.debug(f"set clock-mode from {clock_mode} to {hass.data[const.DOMAIN][serial_number]["clock_mode"]}")

    _LOGGER.debug(f"set status to {CLOCK_MODE}")
    _LOGGER.warning("Rheinturm update scheduled every second")


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
async def show_analog_clock(hass, serial_number, sc_color = None, h_color = None, m_color = None, scf_color = None, offset_hours = 0, scale_size = None, h_shift = 0, v_shift = 0, rotation = 0):
    _LOGGER.debug("analog clock...")

#    from .commands import set_orientation, normalize_color, send_screen
    from .commands import normalize_color, send_screen

    data = hass.data[const.DOMAIN][serial_number]
    d_width = data.get("width")
    d_height = data.get("height")

    if scale_size is None:
        scale_size = min(d_width, d_height)
        _LOGGER.debug(f"set scale-size to {scale_size} px as no size parameter is given")
    elif scale_size < 80:
        scale_size = 80                                                   # one lonely hard-coded value

    _LOGGER.debug(f"some clock values: display-width={d_width}, display-height={d_height}, scale-size={scale_size}")

    # check rotation

    # check position_shift
    _LOGGER.debug(f"position shifts given: h-shift={h_shift}, v-shift={v_shift}")
    if h_shift > (d_width // 2 - 1) or h_shift < -(d_width // 2):
        _LOGGER.debug(f"horizontal position shift {h_shift} out of expected range. Changed to 0.")
        h_shift = 0
    if v_shift > (d_height // 2 - 1) or v_shift < -(d_height // 2):
        _LOGGER.debug(f"vertical position shift {v_shift} out of expected range. Changed to 0.")
        v_shift = 0
        
    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if sc_color is None:
        sc_color = (255, 255, 255)
        _LOGGER.debug(f"set scale-color to {sc_color} as no parameter is given")
    else:
        sc_color = normalize_color(sc_color)
    if scf_color is None:
        #scf_color = (0, 0, 0)
        scf_color = (255 - sc_color[0], 255 - sc_color[1], 255 - sc_color[2])                       # Komplementärfarbe bilden
        _LOGGER.debug(f"set scale-frame-color to {scf_color} as no parameter is given")
    else:
        scf_color = normalize_color(scf_color)
    if h_color is None:
        h_color = (255, 0, 0)
        _LOGGER.debug(f"set hour-color to {h_color} as no parameter is given")
    else:
        h_color = normalize_color(h_color)
    if m_color is None:
        m_color = (127, 127, 127)
        _LOGGER.debug(f"set minute-color to {m_color} as no parameter is given")
    else:
        m_color = normalize_color(m_color)

    _LOGGER.debug(f"colors after normalize: scale={sc_color}, scale-frame={scf_color}, hours={h_color}, minutes={m_color}")

    # Instanzbild holen
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("read image from instance")

    # Kreis und 4 Striche malen
    draw.ellipse((0 + h_shift, 0 + v_shift, scale_size - 1 + h_shift, scale_size - 1 + v_shift), fill = sc_color, outline = scf_color, width = 3)                            # Äußerer Kreis
    draw.line((scale_size // 2 - 1 + h_shift, 2 + v_shift, scale_size // 2 - 1 + h_shift, 6 + v_shift), fill = scf_color, width = 3)                                          # 12
    draw.line((scale_size - 1 + h_shift, scale_size // 2 - 1 + v_shift, scale_size - 5 + h_shift, scale_size // 2 - 1 + v_shift), fill = scf_color, width = 1)                # 3
    draw.line((scale_size // 2 - 1 + h_shift, scale_size - 1 + v_shift, scale_size // 2 - 1 + h_shift, scale_size - 5 + v_shift), fill = scf_color, width = 1)                # 6
    draw.line((2 + h_shift, scale_size // 2 - 1 + v_shift, 6 + h_shift, scale_size // 2 - 1 + v_shift), fill = scf_color, width = 1)                                          # 9

    _LOGGER.debug("drew the scale")

    # aktuelle Zeit holen
    now = datetime.now() + timedelta(hours=offset_hours)
    hour = now.hour
    minute = now.minute

    # Zeiger-Endpunkte berechnen und einzeichnen
    cx = scale_size // 2 - 1 + h_shift
    cy = scale_size // 2 - 1 + v_shift
    hour_length = int(scale_size / 3.6)
    minute_length = int(scale_size / 2.3)
    hour_angle = (hour % 12) * 30 + (minute / 60) * 30 - 90 + rotation
    minute_angle = minute * 6 - 90 + rotation

    hx = int(cx + hour_length * math.cos(math.radians(hour_angle)))
    hy = int(cy + hour_length * math.sin(math.radians(hour_angle)))
    mx = int(cx + minute_length * math.cos(math.radians(minute_angle)))
    my = int(cy + minute_length * math.sin(math.radians(minute_angle)))
    draw.line((cx, cy, hx, hy), fill = h_color, width = scale_size // 25)             # Stundenzeiger
    draw.line((cx, cy, mx, my), fill = m_color, width = scale_size // 40)             # Minutenzeiger
    _LOGGER.debug(f"center: cx={cx}, cy={cy}, pointers endpoints: hx={hx}, hy={hy}, mx={mx}, my={my}")

    # Mittelpunkt zeichnen
    point_size = scale_size // 25
    xs=cx - (point_size // 2) + h_shift
    ys=cy - (point_size // 2) + v_shift
    xe=cx + (point_size // 2) + h_shift
    ye=cy + (point_size // 2) + v_shift
    draw.ellipse((xs, ys, xe, ye), fill = scf_color)                                  # punkt in der Mitte
    _LOGGER.debug(f"middle point circumstances: point-size={point_size}, xs={xs}, ys={ys}, xe={xe}, ye={ye}")

    # ggf das Datum, den WT oder die CPU Temp einpflanzen
    # Text
#    font = ImageFont.load_default()
#    draw.text((10, 30), "Hallo Welt", fill=(255, 255, 255), font=font)
#    _LOGGER.debug("wrote into the image")

    await send_screen(hass, serial_number)


#************************************************************************
#        D I G I T A L  C L O C K
#************************************************************************
# shows the digital clock
#************************************************************************
# m: hass
# m: serial_number
# o: xs
# o: ys
# o: digit-size
# o: rotation
# o: digit-color
# o: background-color
# o: clock-frame-color
# o: clock-frame-width
# o: offset-hours
# o: am/pm
#************************************************************************
#async def show_digital_clock(hass, serial_port, xs = 0, ys = 0, digit_size = 30, rotation = 0, d_color = (0, 255, 255), bg_color = (0, 0, 0), cf_color = (0, 255, 255), cf_width = 0, offset_hours = 0, am_pm = False):
async def show_digital_clock(hass, serial_number, xs = None, ys = None, digit_size = 30, rotation = 0, d_color = (0, 255, 255), bg_color = (0, 0, 0), cf_color = (0, 255, 255), cf_width = 0, offset_hours = None, am_pm = False):
    _LOGGER.debug("digital clock...")

#    from .commands import set_orientation, normalize_color, send_bitmap
    from .commands import normalize_color, send_screen

    data = hass.data[const.DOMAIN][serial_number]
#    d_width = data.get("width")
#    d_height = data.get("height")
    # check rotation

    # check position_shift
    if offset_hours is None:
        offset_hours = 0
        _LOGGER.debug(f"offset-hours set to {offset_hours} as no value was given")
    if cf_width is None:
        cf_width = 0
        _LOGGER.debug(f"cf-width set to {cf_width} as no value was given")
        
    # Konvertiere mögliche Stringfarben in RGB-Tupel
    d_color = normalize_color(d_color)
    cf_color = normalize_color(cf_color)
    bg_color = normalize_color(bg_color)

    _LOGGER.debug(f"colors after normalize: digits={d_color}, clock-frame-color={cf_color}, clock-frame-width={cf_width}, background={bg_color}")

    # vertical value check
#    dc_width = digit_size * 3
    dc_width = int(digit_size * 2.6)
    dc_height = digit_size + 2 + cf_width              
#    if dc_height > d_height:
#        dc_height = d_height - 2 - cf_width
#    if font_size + 2 > cf_height:
#        font_size = cf_height - 2
#    if font_size + 2 + cf_width > dc_height:
#        font_size = dc_height - cf_width - 2
#    if ys + dc_height > disp_h:
#        ys = disp_h - dc_height

#    _LOGGER.debug(f"values after vertical check: digital-clock-height={dc_height}, font-size={font_size}, Y-Start={ys}")
    _LOGGER.debug(f"values after vertical check: digit-size={digit_size}, digital-clock-height={dc_height}, digital-clock-width={dc_width}")

    # aktuelle Zeit holen
    now = datetime.now() + timedelta(hours=offset_hours)
    hour = now.hour
    minute = now.minute
    if am_pm:
        hour = hour % 12
        if hour == 0:
            hour = 12
    time_str = f"{hour:02d}:{minute:02d}"

    _LOGGER.debug(f"time-string={time_str}")

    try:
        font = ImageFont.load_default(size = digit_size)
    except Exception as e:
        font = ImageFont.load_default()
        _LOGGER.error(f"[{const.DOMAIN}] could not load TTF due to: {e}")

    # Textgröße messen
    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), time_str, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    _LOGGER.debug(f"bbox: 0={bbox[0]}, 1={bbox[1]}, 2={bbox[2]}, 3={bbox[3]}")
    _LOGGER.debug("text_w = [2] - [0] = {text_w}, text_h = [3] - [1] = {text_h}")

#    _LOGGER.debug(f"time-string dimensions: width={text_w}, height={text_h} px")

    # Rahmen einberechnen
#    dc_width = text_w + (cf_width * 2) + 4   # kleiner Puffer
#    dc_height = text_h + (cf_width * 2) + 4

    # Begrenzen auf Display
#    dc_width = min(dc_width, disp_w)
#    dc_height = min(dc_height, disp_h)
#    dc_width = min(dc_width, d_width)
#    dc_height = min(dc_height, d_height)

    # Instanzbild holen
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("read image from instance")

#    if cf_width > 0:
#        draw.rectangle((xs, ys, xs + dc_width - 1, ys + dc_height - 1), fill = bg_color, outline=cf_color, width=cf_width)
    draw.rectangle((xs, ys, xs + dc_width - 1, ys + dc_height - 1), fill = bg_color, outline=cf_color, width=cf_width)

    _LOGGER.debug("drew the frame")

   # Text mittig
#    text_x = (dc_width - text_w) // 2
#    text_y = (dc_height - text_h) // 2
#    draw.text((text_x, text_y), time_str, fill=d_color, font=font)

#    draw.text((xs + cf_width, ys + cf_width), time_str, fill=d_color, font=font)
    draw.text((xs, ys), time_str, fill=d_color, font=font)

    _LOGGER.debug("wrote the time into the image")

    # bild ggf drehen
#    img = img.rotate(rotation, expand=True)
#    out_w, out_h = img.size

    await send_screen(hass, serial_number)

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

    # calculate need dimensions
    

