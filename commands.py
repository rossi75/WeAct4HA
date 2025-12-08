# open_serial wird nach tools verschoben
# normalize und wird nach tools verschoben
# neue fkt send_command für einfache direkte Kommandos
# erst in den speicher schreiben, dann das komplette bild übertragen
# https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
#     await asyncio.sleep(4)                   # kleine Pause um direkt auf einmal verschiedene Funktionen zu testen

# https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html

# +----------------------------------------------------------------+
# +0 xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx 160+
# +y                                                               + 
# +y                                                               + ###########
# +y                                                               + ########
# +y                                                               + ########
# +y                                                               + ###########
# +y                                                               + 
# +80                                                              + 
# +----------------------------------------------------------------+

# +----------------------------------------------+
# +0 xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx 480+
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +y                                             + 
# +320                                           + 
# +----------------------------------------------+

import asyncio, struct, logging
import subprocess
import serial
import time
import os
import random
import io
import math
import qrcode
import custom_components.weact_display.const as const
from PIL import Image, ImageDraw, ImageFont, ImageColor
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_time_interval
from pathlib import Path
from .iconutils import load_icon
from .models import DISPLAY_MODELS
#from .const import MAX_BMP_FILES

_LOGGER = logging.getLogger(__name__)

#************************************************************************
#        O P E N  S E R I A L
#************************************************************************
# initializes the serial port via STTY and opens it
#************************************************************************
# m: port
#************************************************************************
def open_serial(port: str):
    _LOGGER.debug(f"initializing serial port {port} ...")

    if not os.path.exists(port):
        _LOGGER.error(f"Port {port} does not exist")
        return None

    # ---- STTY-Setup ----
    try:
        subprocess.run([
            "stty", "-F", port,
            "115200", "cs8", "-cstopb", "-parenb",
            "-crtscts", "-hupcl", "min", "1", "time", "1"
        ], check=True)
        _LOGGER.debug(f"STTY Setup successfully done")
    except subprocess.CalledProcessError as e:
        _LOGGER.warning(f"STTY Setup has some issue: {e}")

    # Seriellen Port öffnen
    try:
        serial_port = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            write_timeout=1
        )

        if serial_port.is_open:
            _LOGGER.debug(f"opened port: {port}")
        else:
            _LOGGER.warning(f"could not open port {port}")
            return None

        _LOGGER.debug(f"successfully opened and initialized serial port {port}")

        return serial_port

    except serial.SerialException as e:
        _LOGGER.error(f"error while opening port {port}: {e}")
        return None

    except Exception as e:
        _LOGGER.error(f"Unexpected error initializing port {port}: {e}")
        return None


#************************************************************************
#        N O R M A L I Z E  C O L O R
#************************************************************************
# converts a string or a list or a tupel of colors into a tupel of colors
#************************************************************************
# m: value
# expamples
# - #FF7F00
# - [255, 127, 0]
# - (255, 127, 0)
# return format is always
# - (x, y, z)
#************************************************************************
def normalize_color(value):
    if isinstance(value, str):                                        # "#FF0000"
        return ImageColor.getrgb(value)
    elif isinstance(value, (list, tuple)) and len(value) == 3:        # [255, 0, 0] oder (255, 0, 0)
        return tuple(value)
    else:
        raise ValueError(f"Unsupported color format: {value}")


#************************************************************************
#        S E N D  S C R E E N
#************************************************************************
# sends the saved shadow image to the display
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
async def send_screen(hass, serial_number):
    _LOGGER.debug(f"flushing the display for serial-number={serial_number}")

    data = hass.data[const.DOMAIN][serial_number]
    width = data.get("width")
    height = data.get("height")

    img = data.get("shadow")
    i_width, i_height = img.size
    img_bytes = img.tobytes()       # Bild extrahieren, ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    px = i_width * i_height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"image size is {i_width}x{i_height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} image bytes for {serial_number}: {hex_str} [...]")

    try:
        await send_bitmap(hass, serial_number, 0, 0, width, height, bytes(img_bytes))  # original
    except Exception as e:
        _LOGGER.error(f"error while sending the content: {e}")

    # Save the image, maybe later only if debugging is set
    timestamp = datetime.now().strftime("%H%M%S")
    file_name = f"{serial_number}_{timestamp}.bmp"
    try:
        _LOGGER.debug(f"Saving image to {const.IMG_PATH}/{file_name}")
        await asyncio.to_thread(lambda: img.save(const.IMG_PATH / file_name))
    except Exception as e:
        _LOGGER.error(f"error while saving the image to {const.IMG_PATH}: {e}")

    # logrotate
    max_files = const.MAX_BMP_FILES
    try:
        files = await hass.async_add_executor_job(
            lambda: [
                os.path.join(const.IMG_PATH, f)
                for f in os.listdir(const.IMG_PATH)
                if f.lower().endswith(".bmp")
                and os.path.isfile(os.path.join(const.IMG_PATH, f))
            ]
        )

        _LOGGER.debug(f"found {len(files)} files in {const.IMG_PATH}/")

        files.sort(key=os.path.getmtime)        # nach Änderungszeit sortieren (älteste zuerst)
        files_to_delete = files[:-max_files]        # alles außer den letzten x löschen

        _LOGGER.debug(f"deleting {len(files_to_delete)} files in {const.IMG_PATH}/")

        for f in files_to_delete:
            try:
                os.remove(f)
            except Exception as e:
                _LOGGER.warning(f"Could not delete old debug file {f}: {e}")
    except Exception as e:
        _LOGGER.error(f"Cleanup error in debug dir: {e}")


#************************************************************************
#        B R I G H T N E S S
#************************************************************************
# changes the brightness of the display
#************************************************************************
# m: hass
# m: serial_number
# m: brightness
#************************************************************************
async def set_brightness(hass, serial_number, brightness):
    """setzt die Lautstärke"""
    _LOGGER.debug("setting volume [brightness]...")

    data = hass.data[const.DOMAIN][serial_number]
#    state = data.get("state")
#    if state is "busy":
#        _LOGGER.debug("Display busy, waiting 3 seconds")
#        return
#    state = busy
#    display.busy = True

    serial_port = data.get("serial_port")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    packet = struct.pack(
        "<BBHB",
        0x03, brightness, 0x3500, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)

    _LOGGER.debug("brightness done")


#************************************************************************
#        O R I E N T A T I O N
#************************************************************************
# sets the orientation
#************************************************************************
# m: hass
# m: serial_number
# o: orientation, default = 2 (landscape)
#************************************************************************
async def set_orientation(hass, serial_number, orientation_value):
    _LOGGER.debug("setting orientation")

    data = hass.data[const.DOMAIN][serial_number]
    serial_port = data.get("serial_port")
    model = data.get("model")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    params = DISPLAY_MODELS.get(model, None)
    if orientation_value in (2, 3):                                                                   # 0 oder 180°
        hass.data[const.DOMAIN][serial_number]["width"] = params["large"]
        hass.data[const.DOMAIN][serial_number]["height"] = params["small"]
    elif orientation_value in (0, 1):                                                                  # 90° oder 270°
        hass.data[const.DOMAIN][serial_number]["width"] = params["small"]
        hass.data[const.DOMAIN][serial_number]["height"] = params["large"]
    else:
        _LOGGER.error(f"unknown orientation_value {orientation_value}, not changing anything")
        return

    hass.data[const.DOMAIN][serial_number]["orientation_value"] = orientation_value
    hass.data[const.DOMAIN][serial_number]["orientation"] = const.ORIENTATION_NAMES[orientation_value]

    _LOGGER.debug(f"new orientation: {data.get("orientation")} [{orientation_value}], {data.get("width")}x{data.get("height")} px")

    packet = struct.pack(
        "<BBB",
        0x02, orientation_value, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)
    await asyncio.sleep(0.1)

    _LOGGER.debug("orientation done")


#************************************************************************
#        H U M I T U R E
#************************************************************************
# enables the humiture reports for a display
#************************************************************************
# m: hass
# m: serial_number
# o: time_interval, default = 60
#************************************************************************
async def enable_humiture_reports(hass, serial_number, time_interval = None):
    _LOGGER.debug("enabling humiture reports")

    data = hass.data[const.DOMAIN][serial_number]
    serial_port = data.get("serial_port")
    humiture = data.get("humiture")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return
    if time_interval is None:
        time_interval = 60
        _LOGGER.debug("no value given for time-interval, set to 60 seconds")
    time_interval = time_interval * 1000              # von s in ms

    packet = struct.pack(
        "<BHB",
        0x06, time_interval, 0x0A                             # alle 60 Sekunden
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)
    await asyncio.sleep(0.1)

    _LOGGER.debug("enabled humiture report")

#************************************************************************
#        H U M I T U R E  P A R S E R
#************************************************************************
# parses the humiture reports from a display
#    Erwartet ein Paket:
#    [86] [T_low] [T_high] [H_low] [H_high] [0A]
#************************************************************************
# m: packet-Bytes
# r: temp_celsius, humidity_percent or None if error
#************************************************************************
def parse_humiture_packet(packet: bytes):
    if len(packet) != 6:
        return None
    if packet[0] != 0x86:     # Startbyte prüfen
        return None
    if packet[5] != 0x0A:         # Endbyte prüfen
        return None

    # Temperatur extrahieren
    t_low  = packet[1]
    t_high = packet[2]
    temp_raw = (t_high << 8) | t_low
    temp_c = temp_raw / 100.0  # Anzeige in °C

    # Humidity extrahieren
    h_low  = packet[3]
    h_high = packet[4]
    hum_raw = (h_high << 8) | h_low
    hum_percent = hum_raw / 100.0

    return temp_c, hum_percent


#************************************************************************
#        B I T M A P
#************************************************************************
# sends out a bitmap
#************************************************************************
# m: hass
# m: serial_number
# m: X start
# m: Y start
# m: X end
# m: Y end
# m: data_888, RGB888-data
#************************************************************************
async def send_bitmap(hass, serial_number, xs, ys, xe, ye, data_888: bytes):
    """Sendet ein Bitmap an das Display (CMD 0x05)."""
    _LOGGER.debug("finally sending bitmap...")

    data = hass.data[const.DOMAIN][serial_number]
    serial_port = data.get("serial_port")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    header = struct.pack(
        "<BHHHHB",
        0x05, xs, ys, xe-1, ye-1, 0x0A
    )

    width = xe - xs
    height = ye - ys
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    rgb565 = px * 2  # anzahl bytes RGB565 (8-3 + 8-3 + 8-3 = 16 bit = 2 byte pro pixel)
    CHUNK_SIZE = width * 2  # empirisch aus USB-Sniffing

    _LOGGER.debug(f"expected bitmap size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes, RGB565 = {rgb565} bytes")
    _LOGGER.debug(f"chunk size is {CHUNK_SIZE} bytes per write")

    # data: bytes oder bytearray mit RGB888 (R,G,B) Werten
    # erzeugt data_565: bytes in RGB565 little-endian
    _LOGGER.debug(f"transforming from RGB888 to RGB565")
    data_565 = bytearray()
    for i in range(0, len(data_888), 3):
        r = data_888[i]
        g = data_888[i + 1]
        b = data_888[i + 2]
        # 8-Bit nach 5-6-5 Bit skalieren
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        # little-endian (LSB zuerst)
        data_565.append(rgb565 & 0xFF)
        data_565.append((rgb565 >> 8) & 0xFF)

    hex_str = " ".join(f"{b:02X}" for b in header)
    _LOGGER.debug(f"need to send {len(header)} header bytes for {serial_number}: {hex_str}")
    hex_str = " ".join(f"{b:02X}" for b in data_565[:40])
    _LOGGER.debug(f"... and {len(data_565)} bitmap bytes as RGB565 for {serial_number}: {hex_str} [...]")

    await hass.async_add_executor_job(serial_port.write, header)
    _LOGGER.debug("header write done")
    await hass.async_add_executor_job(serial_port.flush)
    _LOGGER.debug("header flush done")

    # Nun die Bilddaten in 640-Byte-Blöcken senden
    await asyncio.sleep(0.05)
    for i in range(0, len(data_565), CHUNK_SIZE):
        chunk = data_565[i:i + CHUNK_SIZE]
        await hass.async_add_executor_job(serial_port.write, chunk)
        await hass.async_add_executor_job(serial_port.flush)
        await asyncio.sleep(0.001)  # kleine Pause zwischen den Chunks

    _LOGGER.debug(f"Sent {len(data_565)} bytes in chunks of {CHUNK_SIZE} bytes")


#************************************************************************
#        T E S T B I L D
#************************************************************************
# shows the testbild.bmp
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
# reads a BMP-Datei and sends it out to the WeAct Display
#************************************************************************
async def show_testbild(hass, serial_number):
    bmp_path = "testbild.bmp"
    _LOGGER.debug(f"searching for file: {bmp_path}")

    if not os.path.exists(bmp_path):
        _LOGGER.error(f"Datei nicht gefunden: {bmp_path}")
        return

    _LOGGER.debug("file found")

    # BMP öffnen
    try:
        img = Image.open(bmp_path).convert("RGB")

        _LOGGER.debug("opened file and loaded into memory")

        width, height = img.size
        px = width * height
        rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
        
        _LOGGER.debug(f"picture has {width}x{height} pixels")
        hex_str = " ".join(f"{b:02X}" for b in img[:40])
        _LOGGER.debug(f"expected testbild size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
        hex_str = " ".join(f"{b:02X}" for b in img[:40])
        _LOGGER.debug(f"need to send {len(img)} testbild Bytes for {serial_number}: {hex_str} [...]")

#        await send_bitmap(hass, SERIAL, 0, 0, width, height, bytes(img))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the testbild: {e}")

    _LOGGER.debug(f"Testbild sent with {len(img)} Bytes")


#************************************************************************
#        F U L L  C O L O R
#************************************************************************
# shows a section ot the complete screen in one color
#************************************************************************
# m: hass
# m: serial_number
# m: color
# o: width
# o: height
#************************************************************************
async def send_full_color(hass, serial_number, color):
    _LOGGER.debug("filling display with one-color...")

    data = hass.data[const.DOMAIN][serial_number]
    serial_port = data.get("serial_port")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    width = data.get("width")
    height = data.get("height")

    r, g, b = color

    # verschieben um aus RGB888 ein RGB565 zu machen
    r >>= 3
    g >>= 2
    b >>= 3
    rgb565 = ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F)

    packet = struct.pack(
        "<BHHHHHB",
        0x04, 0x0000, 0x0000, width - 1, height - 1, rgb565, 0x0A
    )

    # das hier nachher in send_command verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)


#************************************************************************
#        S E L F  T E S T
#************************************************************************
# shows all native colors, white and black
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
async def display_selftest(hass, serial_number: str):
    _LOGGER.debug("Starting display self test")

    colors = [
        (0, 0, 0),        # Schwarz (Start)
        (255, 0, 0),      # Rot
        (0, 255, 0),      # Grün
        (0, 0, 255),      # Blau
        (255, 255, 255),  # Weiß
        (0, 0, 0)         # Schwarz (Ende)
    ]

    await set_orientation(hass, serial_number, 2)                   # o=2, w=160, h=80 --> komplettes Display wird getestet

    for color in colors:
        await send_full_color(hass, serial_number, color)
        await asyncio.sleep(0.6)

    _LOGGER.debug("display selftest done")

#************************************************************************
#        R A N D O M  S C R E E N
#************************************************************************
# shows a picture with full of random pixels
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
async def generate_random(hass, serial_number):
    _LOGGER.debug("raising random bitmap")

    data = hass.data[const.DOMAIN][serial_number]
    serial_port = data.get("serial_port")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return
    width = data.get("width")
    height = data.get("height")

    # delete screen
    _LOGGER.debug("clearing screen")
    black = [0, 0, 0]
    await send_full_color(hass, serial_number, black)

    _LOGGER.debug(f"generating random image with {width} x {height} pixel")
    try:
        buf = bytearray()
        for _ in range(width * height):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            buf += struct.pack("<BBB", r, g, b)

        hex_str = " ".join(f"{b:02X}" for b in buf[:40])
        _LOGGER.debug(f"generated {len(buf)} Bytes for {serial_number}: {hex_str} [...]")

        await set_orientation(hass, serial_number, 2)
        await send_bitmap(hass, serial_number, 0, 0, width, height, bytes(buf))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending (or generating?) the image: {e}")


#************************************************************************
#        I N I T  S C R E E N
#************************************************************************
# shows the initial screen
#************************************************************************
# m: hass
# m: serial_number
# after issuing the command, display does not respond for 1 second
#************************************************************************
async def show_init_screen(hass, serial_number):
    _LOGGER.debug("show up initial screen")

#    data = self._hass.data[const.DOMAIN][serial_number].get(self._device_id, {})
    data = hass.data[const.DOMAIN][serial_number]
    serial_port = data.get("serial_port")
    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    packet = struct.pack(
        "<BB",
        0x07, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)

    _LOGGER.debug("initial screen done")


#************************************************************************
#        I C O N
#************************************************************************
# loads an MDI-Icon and renders as RGB888-Bitmap
#************************************************************************
# m: hass
# m: serial_number
# m: icon name
# m: X start
# m: Y start
# o: size, 32 px if no value given
# o: icon-color, default = white (255, 255, 255)
# o: background-color, default = black (0, 0, 0)
# o: rotation
#************************************************************************
# rotate from: https://stackoverflow.com/questions/45179820/draw-text-on-an-angle-rotated-in-python
#************************************************************************
#sync def show_icon(hass, serial_number, i_name: str, xs, ys, i_size = 32, i_color = (255, 255, 255), bg_color = (0, 0, 0), rotation = 0):
async def show_icon(hass, serial_number, i_name: str, xs, ys, i_size = 32, i_color = (255, 255, 255), rotation = 0):
    _LOGGER.debug("show icon...")

    data = hass.data[const.DOMAIN][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if i_color is None:
        i_color = (255, 255, 255)
        _LOGGER.debug(f"set icon-color to {i_color} as no parameter is given")
    else:
        i_color = normalize_color(i_color)
#   if bg_color is None:
#       bg_color = (255, 255, 255)
#       _LOGGER.debug(f"set background-color to {bg_color} as no parameter is given")
#   else:
#       bg_color = normalize_color(bg_color)

#   _LOGGER.debug(f"colors after normalize: icon-color={i_color}, background-color={bg_color}")
    _LOGGER.debug(f"colors after normalize: icon-color={i_color}")

#   icon = await load_icon(hass, i_name = i_name, i_size = i_size, i_color = i_color, bg_color = bg_color, rotation = rotation)
    icon = await load_icon(hass, i_name = i_name, i_size = i_size, i_color = i_color, rotation = rotation)
    icon = icon.convert("RGBA")

    _LOGGER.debug(f"icon parameters: xs={xs}, ys={ys}, icon-size={i_size}x{i_size}, rotation={rotation}, icon-bytes={len(icon.tobytes())}")

    shadow = data.get("shadow")

    _LOGGER.debug("read image from instance")

    shadow.paste(icon, (xs, ys), icon)   # 3. Parameter geht nur wenn das Bild einen Alphakanal hat

    _LOGGER.debug("pasted icon into instance")
    
    await send_screen(hass, serial_number)


#************************************************************************
#        L I N E
#************************************************************************
# draws a line
#************************************************************************
# m: hass
# m: serial_number
# m: X start
# m: Y start
# m: X end
# m: Y end
# o: line-color, default = white (255, 255, 255)
# o: line width, default = 1
#************************************************************************
async def draw_line(hass, serial_number, xs, ys, xe, ye, l_color = (255, 255, 255), l_width = 1):
    _LOGGER.info("draw a line ...")

    data = hass.data[const.DOMAIN][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    l_color = normalize_color(l_color)

    _LOGGER.debug(f"l_color_after = {l_color}")

    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("read image from instance")

    # Linie mit angepassten Koordinaten zeichnen
    draw.line([(xs, ys), (xe, ye)], fill = l_color, width = l_width)

    _LOGGER.debug("drew the line")

    await send_screen(hass, serial_number)
    

#************************************************************************
#        C I R C L E
#************************************************************************
# draws a circle or an ellipse
#************************************************************************
# m: hass
# m: serial_number
# m: X center point
# m: Y center point
# m: radius
# o: background-color, default = black (0, 0, 0)
# o: circle-color, default = white (255, 255, 255)
# o: fill-color, default = red (255, 0, 0)
# o: circle-frame width, default = 1
# o: ellipse, set to radius if not given
#************************************************************************
async def draw_circle(hass, serial_number, xp, yp, r, c_color = (255, 255, 255), f_color = (255, 0, 0), cf_width = 0, e = None):
    _LOGGER.info("draw a circle ...")

    data = hass.data[const.DOMAIN][serial_number]
    width = data.get("width")
    height = data.get("height")

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    c_color = normalize_color(c_color)
    f_color = normalize_color(f_color)

    _LOGGER.debug(f"colors after normalize: c_color={c_color}, f_color={f_color}")

    if e is None:
        e = r
        _LOGGER.debug("no value given for ellipse, taking radius as second circle factor")
    if cf_width is None:
        cf_width = 0
        _LOGGER.debug("no value given for circle-frame, set to 0")
    _LOGGER.debug(f"given circle: radius={r}, ellipse={e}, circle-frame-width={cf_width}")

    # calculate the place to be
    xs = xp - r
    ys = yp - e
    xe = xp + r
    ye = yp + e

    _LOGGER.debug(f"calculated where to place the circle: xs={xs}, ys={ys}, xe={xe}, ye={ye}")

    # Schattenbild abholen
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    # Kreis zeichnen
    draw.ellipse((xs, ys, xe, ye), outline = c_color, width = cf_width, fill = f_color)

    _LOGGER.debug("drew the circle")

    await send_screen(hass, serial_number)


#************************************************************************
#        R E C T A N G L E
#************************************************************************
# draws a rectangle
#************************************************************************
# m: hass
# m: serial_number
# m: X start
# m: Y start
# m: X end
# m: Y end
# o: rectangle-frame width, default = 1
# o: rectangle-frame-color, default = white (255, 255, 255)
# o: fill-color, default = None, if no value given, same as the frame color
#************************************************************************
async def draw_rectangle(hass, serial_number, xs, ys, xe, ye, rf_width = 1, rf_color = (255, 255, 255), f_color = None):
    _LOGGER.info("draw a rectangle ...")

    data = hass.data[const.DOMAIN][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if rf_width is None:
        _LOGGER.debug(f"set rectangle-frame-width to {rf_width} as no parameter is given")
        rf_width = 1
    if rf_color is None:
        rf_color = (255, 255, 255)
        _LOGGER.debug(f"set rectangle-frame-color to {rf_color} as no parameter is given")
    else:
        rf_color = normalize_color(rf_color)
    if f_color is not None:
        f_color = normalize_color(f_color)

    _LOGGER.debug(f"colors after normalize: rectangle-frame-color={rf_color}, fill-color={f_color} + rectangle-frame-width={rf_width}")

    # Schattenbild abholen
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    # Rahmen & Füllung zeichnen
    draw.rectangle((xs, ys, xe, ye), width = rf_width, outline = rf_color)
    if f_color is not None:
        draw.rectangle((xs + rf_width, ys + rf_width, xe - rf_width, ye - rf_width), fill = f_color)

    await send_screen(hass, serial_number)


#************************************************************************
#        T R I A N G L E
#************************************************************************
# draws a triangle
#************************************************************************
# m: hass
# m: serial_number
# m: X1
# m: Y1
# m: X2
# m: Y2
# m: X3
# m: Y3
# o: triangle-color, default = white (255, 255, 255)
# o: triangle-frame-color, default = None, if no value given, same as the border
# o: triangle-frame width, default = None
#************************************************************************
async def draw_triangle(hass, serial_number, xa, ya, xb, yb, xc, yc, t_color = None, tf_color = None, tf_width = None):
    _LOGGER.info("draw a triangle ...")

    data = hass.data[const.DOMAIN][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if tf_width is None:
        tf_width = 0
    if t_color is None:
        t_color = (255, 255, 255)
        _LOGGER.debug(f"set triangle-color to {t_color} as no parameter is given")
    else:
        t_color = normalize_color(t_color)
    if tf_color is None:
        tf_color = (0, 0, 0)
        _LOGGER.debug(f"set triangle-frame-color to {tf_color} as no parameter is given")
    else:
        tf_color = normalize_color(tf_color)

    _LOGGER.debug(f"colors after normalize: triangle-color={t_color}, triangle-frame-color={tf_color} + triangle-frame-width={tf_width}")

    # Schattenbild abholen
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    # Koordinaten anpassen (verschieben)
    adj_points = [(xa - min_x, ya - min_y),
                  (xb - min_x, yb - min_y),
                  (xc - min_x, yc - min_y)]
    draw.polygon(adj_points, fill = t_color, outline = tf_color, width = tf_width)

    _LOGGER.debug(f"drew polygon points: {adj_points}")

    await send_screen(hass, serial_number)


#************************************************************************
#        T E X T
#************************************************************************
# writes a text
#************************************************************************
# rotate from: https://stackoverflow.com/questions/45179820/draw-text-on-an-angle-rotated-in-python
# or           https://stackoverflow.com/questions/245447/how-do-i-draw-text-at-an-angle-using-pythons-pil
#************************************************************************
# m: hass
# m: serial_number
# m: X start
# m: Y start
# m: X end
# m: Y end
# end to optional if calculated
# o: font size
# o: background-color, default = black (0, 0, 0)
# o: text-color, default = white (255, 255, 255)
# o: rotation
#************************************************************************
#async def write_text(hass, serial_port, text, xs, ys, font_size = 15, font = None, align = "left", t_color = (255, 255, 255), bg_color = (0, 0, 0), rotation = 0):
#async def write_text(hass, serial_number, text, xs, ys, xe, ye = None, font_size = 15, t_color = (255, 255, 255), bg_color = (0, 0, 0), rotation = 0):
#async def write_text(hass, serial_number, text, xs, ys, xe, ye = None, font_size = 15, t_color = None, bg_color = None, rotation = 0):
async def write_text(hass, serial_number, text, xs, ys, xe, ye, font_size = 15, t_color = None, bg_color = None, rotation = 0):
    _LOGGER.debug(f"writing some text with values given: serial-number={serial_number}, text={text}, xs={xs}, ys={ys}, xe={xe}, ye={ye}, font-size={font_size}, text-color={t_color}, background-color={bg_color}, rotation={rotation}")

    data = hass.data[const.DOMAIN][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if t_color is None:
        t_color = (255, 255, 255)
        _LOGGER.debug(f"set text-color to {t_color} as no parameter is given")
    else:
        t_color = normalize_color(t_color)
    if bg_color is None:
        bg_color = (0, 0, 0)
        _LOGGER.debug(f"set background-color to {bg_color} as no parameter is given")
    else:
        bg_color = normalize_color(bg_color)

    _LOGGER.debug(f"colors after normalize: background-color={bg_color}, text-color={t_color}")

    # Textgröße berechnen
#    lines = text.splitlines() or [text]
#    line_heights = []
#    max_width = 0
#    for line in lines:
#        w, h = draw.textsize(line, font=fnt)
#        line_heights.append(h)
#        max_width = max(max_width, w)

#    total_height = sum(line_heights)
#    y = (height - total_height) // 2 if align == "center" else 0

#    for i, line in enumerate(lines):
#        w, h = draw.textsize(line, font=fnt)
#        if align == "right":
#            x = width - w
#        elif align == "center":
#            x = (width - w) // 2
#        else:
#            x = 0
#        draw.text((x, y), line, font=fnt, fill=color)
#        y += h

#    width = abs(xe - xs + 1)
#    height = abs(ye - ys + 1)

    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    # Text
    font = ImageFont.load_default(size = font_size)
    draw.rectangle((xs, ys, xe, ye), fill = bg_color)
    draw.text((xs, ys), text, fill = t_color, font = font)
    _LOGGER.debug("wrote text into the image")

    # bild ggf drehen
#    img = img.rotate(rotation, expand=True)
#    i_width, i_height = img.size

    await send_screen(hass, serial_number)


#************************************************************************
#        P R O G R E S S  B A R
#************************************************************************
# shows a progress bar
# idea from: https://github.com/mathoudebine/turing-smart-screen-python/wiki/Control-screen-from-your-own-code
# rotate from: https://stackoverflow.com/questions/45179820/draw-text-on-an-angle-rotated-in-python
#************************************************************************
# m: hass
# m: serial_number
# m: X start
# m: Y start
# o: X end
# o: Y end
# o: bar-value
# o: min-value, default = 0
# o: max-value, default = 100
# o: bar-color, default = white (255, 255, 255)
# o: bar-outline, default = True
# o: background-color, default = black (0, 0, 0)
# o: rotation, default = 90
#************************************************************************
async def draw_progress_bar(hass, serial_number, xs, ys, xe, ye, bar_value=None, min_value=0, max_value=100, bf_width=1, bf_color=None, b_color=(255, 255, 255), bg_color=(0, 0, 0), rotation = 90, show_value=False, val_appendix=""):
    _LOGGER.debug(f"doing a progress with the values given: xs={xs}, ys={ys}, xe={xe}, ye={ye}, bar-value={bar_value}, min-value={min_value}, max-value={max_value}, bar-frame-width={bf_width}, bar-color={b_color}, bar-frame-color={bf_color}, background-color={bg_color}, rotation={rotation}, show-value={show_value}, value-appendix={val_appendix}")

    data = hass.data[const.DOMAIN][serial_number]

    if bf_color is None:
        bf_color = b_color
        _LOGGER.debug("no value given for bar-frame-color, taking bar-color for frame")

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    b_color = normalize_color(b_color)
    bf_color = normalize_color(bf_color)
    bg_color = normalize_color(bg_color)                     

    _LOGGER.debug(f"colors after normalize: bar-color={b_color}, bar-frame-color={bf_color}, background-color={bg_color}")

    # check for dimensions out-of-range
    bar_w = xe - xs
    bar_h = ye - ys
    p_bar_w = bar_w - bf_width - bf_width

    _LOGGER.debug(f"final bar dimensions: bar-width={bar_w}, height-height={bar_h}, progress-bar-width={p_bar_w}")

    # Prozentwert clampen ---
    if bar_value < min_value:
        bar_value = min_value
    if bar_value > max_value:
        bar_value = max_value

    _LOGGER.debug(f"bar-value after min/max range check: {bar_value}")

    # Balkenfüllstand berechnen
    fill_ratio = (bar_value - min_value) / (max_value - min_value)
    fill_w = int(p_bar_w * fill_ratio)

    _LOGGER.debug(f"fill-ratio={fill_ratio}, fill-width={fill_w}")

    # Bild aus der Instanz ziehen
    img = data.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    # Rahmen zeichnen
    draw.rectangle((xs, ys, xs + bar_w, ys + bar_h), width = bf_width, outline = bf_color, fill = bg_color)

    _LOGGER.debug(f"drew the frame")

    # Füllung zeichnen
    draw.rectangle((xs + bf_width, ys + bf_width, xs + bf_width + fill_w, ys + bar_h - bf_width), fill=b_color)

    _LOGGER.debug(f"drew the bar")

    # ggf Wert einzeichnen
    if show_value:
        value_str = f"{int(bar_value)}%" + val_appendix
        try:
#            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(bar_h * 0.5))                # warum hier ein Faktor von 0,5? Ich würde ja eher sagen -4, oder?
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(bar_h - bf_width - bf_width - 2))                # warum hier ein Faktor von 0,5? Ich würde ja eher sagen -4, oder?
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), value_str, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = (bar_w - text_w) // 2
        ty = (bar_h - text_h) // 2

        _LOGGER.debug(f"show_value is given: text-width={text_w} px, text-height={text_h} px, at x={tx}, y={ty}")

        # Overlay: Wir schreiben zwei Versionen — überlagert, getrennt
        # Erst die invertierte (über gefülltem Teil)
        if fill_w > 0:
            mask_img = Image.new("L", (bar_w, bar_h), 0)
            mask_draw = ImageDraw.Draw(mask_img)
            mask_draw.rectangle([0, 0, fill_w, bar_h], fill=255)
            draw.text((tx, ty), value_str, font=font, fill=bg_color)
            _LOGGER.debug(f"drew the filled bar text")
        # Dann der Rest (noch nicht gefüllt)
        if fill_w < bar_w:
            draw.text((tx, ty), value_str, font=font, fill=b_color)
            _LOGGER.debug(f"drew the unfilled bar text")

    # --- Rotation (optional) ---
#    img = img.rotate(rotation, expand=True)
#    i_width, i_height = img.size

#    _LOGGER.debug(f"rotated the image for {rotation} degrees")

    await send_screen(hass, serial_number)


#************************************************************************
#        Q R  C O D E
#************************************************************************
# generates a QR code
#************************************************************************
# m: hass
# m: serial_number
# m: data
# m: xs
# m: ys
# o: pixel_size (1-4)
# o: show_data
# o: qr-color, default = white (255, 255, 255)
# o: background-color, default = black (0, 0, 0)
#************************************************************************
# QR code with Progress bar with solid background and outline
#************************************************************************
async def generate_qr(hass, serial_number, data, xs, ys, show_data=False, qr_color=(255, 255, 255), bg_color=(0, 0, 0)):
    _LOGGER.info(f"generating a qr code")
    _LOGGER.debug(f"given values: data={data}, xs={xs}, ys={ys}, show-data={show_data}, qr-color={qr_color}, background-color={bg_color}")

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    qr_color = normalize_color(qr_color)
    bg_color = normalize_color(bg_color)                     

    _LOGGER.debug(f"colors after normalize: qr-color={qr_color}, background-color={bg_color}")

    # Autoselect QR version (up to v13)
    qr = qrcode.QRCode(
        version=None,         # auto
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=1,
#        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    version = qr.version
    if version > 13:
        raise ValueError(f"QR version {version} is needed for the amount of data, which is too large for 80x80 display. Try shorter text.")

    _LOGGER.debug(f"Selected QR version {version}")

    # Create 1px QR matrix
#    qr_img = qr.make_image(fill_color="white", back_color="black")
    qr_img = qr.make_image(fill_color=qr_color, back_color=bg_color)
    qr_img = qr_img.convert("RGB")

    # Calculate pixel_size to fit in 80px
    modules = qr_img.size[0]
#    total = modules + 8  # border*2
    total = modules + 2 # border*2

    max_pixel_size = 80 // total
    if max_pixel_size < 1:
        raise ValueError("QR code cannot fit even with pixel_size=1")

    pixel_size = max_pixel_size
    _LOGGER.debug(f"pixel-size selected: {pixel_size}")

    # Scale QR
    qr_scaled = qr_img.resize((modules * pixel_size, modules * pixel_size), Image.NEAREST)

    # Optional: add text underneath
    if show_text:
        font = ImageFont.load_default()
        text_h = 12
        new_h = qr_scaled.height + text_h
        img = Image.new("RGB", (qr_scaled.width, new_h), (0,0,0))
        img.paste(qr_scaled, (0, 0))

        draw = ImageDraw.Draw(img)
        draw.text((0, qr_scaled.height), data[:20], fill=(255,255,255), font=font)
    else:
        img = qr_scaled

    # Convert to bytes + debug save
    i_width, i_height = img.size
    img_bytes = img.tobytes()

    # Save the image
    try:
        _LOGGER.debug(f"Saving qr code to {const.IMG_PATH}")
        await asyncio.to_thread(lambda: final.save(const.IMG_PATH / "qr.bmp"))
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while saving the qr code to {const.IMG_PATH}: {e}")

    _LOGGER.debug(f"qr code has {i_width}x{i_height} pixels")
    px = i_width * i_height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected qr code size from coordinates should be {i_width}x{i_height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} qr code bytes for {serial_port}: {hex_str} [...]")

    # Send to display
    await set_orientation(hass, serial_port, 2)
    try:
        await send_bitmap(hass, serial_port, xs, ys, xs + i_width, ys + i_height, bytes(img_bytes))  # original
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while sending the qr code: {e}")









#data = hass.data[const.DOMAIN][serial_number]
#data.state = busy
#if display.busy:
#    _LOGGER.debug("Display busy, skipping draw")
#    return
#display.busy = True

#try:
    # zeichne ins display
#finally:
#    display.busy = False


