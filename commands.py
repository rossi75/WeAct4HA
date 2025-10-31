# protocol wird nachher umbenannt in commands
# open_serial wird nach tools verschoben

import asyncio, struct, logging
import subprocess
import serial
import time
import os
import random
#import logging
from PIL import Image, ImageDraw, ImageFont, ImageColor
#from materialdesignicons import MDI
#import cairosvg
import io
from .iconutils import load_icon
import math
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

DOMAIN = "weact_display"
SERIAL = None

def open_serial(port: str):
    """Initialisiert den seriellen Port mit stty und öffnet ihn."""
    _LOGGER.debug(f"[{DOMAIN}] initializing serial port {port} ...")

    if not os.path.exists(port):
        _LOGGER.error(f"[{DOMAIN}] Port {port} does not exist")
        return None

    # ---- STTY-Setup ----
    try:
        subprocess.run([
            "stty", "-F", port,
            "115200", "cs8", "-cstopb", "-parenb",
            "-crtscts", "-hupcl", "min", "1", "time", "1"
        ], check=True)
        _LOGGER.debug(f"[{DOMAIN}] STTY Setup successfully done")
    except subprocess.CalledProcessError as e:
        _LOGGER.warning(f"[{DOMAIN}] STTY Setup has some issue: {e}")

    # ---- Seriellen Port öffnen ----
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
            _LOGGER.debug(f"[{DOMAIN}] opened port: {port}")
        else:
            _LOGGER.warning(f"[{DOMAIN}] could not open port {port}")
            return None

        _LOGGER.debug(f"[{DOMAIN}] successfully opened and initialized serial port {port}")

        return serial_port

    except serial.SerialException as e:
        _LOGGER.error(f"[{DOMAIN}] error while opening port {port}: {e}")
        return None

    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] Unexpected error initializing port {port}: {e}")
        return None


async def show_testbild(hass, serial_port):
    """Liest eine 160x80 BMP-Datei und sendet sie an das WeAct Display."""
    bmp_path = "testbild.bmp"
    _LOGGER.debug(f"searching for file: {bmp_path}")

    if not os.path.exists(bmp_path):
        _LOGGER.debug(f"Datei nicht gefunden: {bmp_path}")
        return

    _LOGGER.debug("file found")

    # 1️⃣ BMP öffnen
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
        _LOGGER.debug(f"need to send {len(img)} testbild Bytes to {serial_port}: {hex_str} [...]")

        await send_bitmap(hass, SERIAL, 0, 0, width, height, bytes(img))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending the testbild: {e}")

    _LOGGER.debug(f"Testbild sent with {len(img)} Bytes")
    

async def send_bitmap(hass, serial_port, xs, ys, xe, ye, data_888: bytes):
    """Sendet ein Bitmap an das Display (CMD 0x05)."""
    _LOGGER.debug("finally sending bitmap...")

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
    _LOGGER.debug(f"need to send {len(header)} header bytes to {serial_port}: {hex_str}")
    hex_str = " ".join(f"{b:02X}" for b in data_565[:40])
    _LOGGER.debug(f"... and {len(data_565)} bitmap bytes as RGB565 to {serial_port}: {hex_str} [...]")

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


async def display_selftest(hass, serial_port):
    """Kurzer Farbtest zur Initialisierung."""
    _LOGGER.debug("Starting display self test")

    colors = [
        (0, 0, 0),        # Schwarz (Start)
        (255, 0, 0),      # Rot
        (0, 255, 0),      # Grün
        (0, 0, 255),      # Blau
        (255, 255, 255),  # Weiß
        (0, 0, 0)         # Schwarz (Ende)
    ]

    await set_orientation(hass, serial_port, 0)

    for color in colors:
        await send_full_color(hass, serial_port, color, width=80, height=160)
        await asyncio.sleep(0.6)

    _LOGGER.debug("display selftest done")


async def send_full_color(hass, serial_port, color, width = 80, height = 160):
    """Füllt das Display komplett mit einer Farbe."""
    _LOGGER.debug("filling display with one-color...")

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

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_port}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)


async def set_brightness(hass, serial_port, brightness):
    """setzt die Lautstärke"""
    _LOGGER.debug("setting volume [brightness]...")

    packet = struct.pack(
#        "<BBB",
#        0x10, brightness, 0x0A
        "<BBHB",
        0x03, brightness, 0x3500, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_port}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)

    _LOGGER.debug("orientation done")


async def send_text(text, width, height, color, bgcolor, align, font_size, font):
    _LOGGER.debug(f"sendtext: {text}, {width}, {height}, {color}, {bgcolor}, {align}, {font_size}, {font}")

    # 

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
        _LOGGER.debug(f"text received: '%s' (%dx%d, fg=%s, bg=%s, align=%s)",
                     text, width, height, color, bgcolor, align)
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending or rendering the image: {e}")


async def generate_random(hass, call, SERIAL):
    """show random pixels"""
    _LOGGER.debug("raising random bitmap")

    # delete screen
    _LOGGER.debug("clearing screen")
    black = [0, 0, 0]
    await send_full_color(hass, SERIAL, black, width=80, height=160)

    width = int(call.data.get("width", 79))
    height = int(call.data.get("height", 159))

    try:
        _LOGGER.debug(f"generating random image with {width} x {height} pixel")
        buf = bytearray()
        for _ in range(width * height):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            buf += struct.pack("<BBB", r, g, b)

        hex_str = " ".join(f"{b:02X}" for b in buf[:40])
        _LOGGER.debug(f"generated {len(buf)} Bytes for {SERIAL}: {hex_str} [...]")

        await send_bitmap(hass, SERIAL, 0, 0, width, height, bytes(buf))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending (or generating?) the image: {e}")

async def show_init_screen(hass, serial_port):
    """initialen Bildschirm anzeigen"""
    _LOGGER.debug("show up initial screen")

    packet = struct.pack(
        "<BB",
        0x07, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_port}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)

    _LOGGER.debug("initial screen done")


async def set_orientation(hass, serial_port, orientation = 0):
    """sets the orienation of the display"""
    _LOGGER.debug("setting orientation")

    packet = struct.pack(
        "<BBB",
#        0x02, 0x00, 0x0A
        0x02, orientation, 0x0A
    )

    _LOGGER.debug(f"new orientation: {orientation}")

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_port}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)
    await asyncio.sleep(0.1)

    _LOGGER.debug("orientation done")


def normalize_color(value):
    """Wandelt Strings, Listen oder Tupel in ein RGB-Tupel um"""
    if isinstance(value, str):
        # z. B. "#FF0000"
        return ImageColor.getrgb(value)
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        # z. B. [255, 0, 0] oder (255, 0, 0)
        return tuple(value)
    else:
        raise ValueError(f"Unsupported color format: {value}")


#async def show_analog_clock(hass, serial_port,  scale_color = 0xFFFFFF, hour_color = 0xFF0000, minute_color = 0x7F7F7F, background_color = 0x000000, offset_hours = 0, position_value = 0, orientation_value = 0):
async def show_analog_clock(hass, serial_port,  scale_color = (255, 255, 255), hour_color = (255, 0, 0), minute_color = (127, 127, 127), background_color = (0, 0, 0), offset_hours = 0, position_value = 0, orientation_value = 0):
    """zeigt die analoge Uhr an"""
    _LOGGER.debug("analog clock...")

    await set_orientation(hass, serial_port, 2)

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    scale_color = normalize_color(scale_color)
    hour_color = normalize_color(hour_color)
    minute_color = normalize_color(minute_color)
    background_color = normalize_color(background_color)

    _LOGGER.debug(f"scale_color_after = {scale_color}")

    # Neues 80x80 Displaybild erstellen
    img = Image.new("RGB", (80, 80), background_color)
    draw = ImageDraw.Draw(img)
    width, height = img.size

    _LOGGER.debug("defined new image")

    # Kreis und 4 Striche malen
    draw.ellipse((0, 0, 79, 79), outline = scale_color, width = 2)                                   # Äußerer Kreis
    draw.ellipse((39, 39, 41, 41), outline = scale_color, width = 4)    # punkt in der Mitte
    draw.line((39, 2, 39, 6), fill = scale_color, width = 1)         # 12
    draw.line((79, 39, 75, 39), fill = scale_color, width = 1)    # 3
    draw.line((39, 79, 39, 75), fill = scale_color, width = 1)      # 6
    draw.line((2, 39, 6, 39), fill = scale_color, width = 1)      # 9

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
    draw.line((cx, cy, hx, hy), fill = hour_color, width=3)
    draw.line((cx, cy, mx, my), fill = minute_color, width=2)

    _LOGGER.debug("drew the pointers")

    # ggf das Datum einpflanzen
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
    _LOGGER.debug(f"expected clock size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} clock bytes for {serial_port}: {hex_str} [...]")

    try:
        await send_bitmap(hass, serial_port, 39 + position_value, 0, 119 + position_value, 79, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending the analog clock: {e}")

    # entsprechend versetzten Ausschnitt "befreien", ggf noch 1 px r/l mehr

    # Bild ans display schicken, hier auch noch mal den Versatz prüfen

    # timer setzen auf 60 Sekunden

    # Timer wird unterbrochen durch...?


#async def show_icon(icon_name: str, color="#FFFFFF", size=(48, 48), bg_color="#000000"):
async def show_icon(hass, serial_port, icon_name: str, icon_color = (255, 255, 255), bg_color = (0, 0, 0), x_position = 0, y_position = 0, size = 32, rotation = 0):
    """
    Lädt ein MDI-Icon, rendert es als RGB888-Bitmap und gibt Bytes zurück.
    """
    _LOGGER.debug("show icon...")

    await set_orientation(hass, serial_port, 2)

#    await load_icon_as_rgb888(icon_name: str, color = icon_color, size = size, rotation = rotation)
    rgb_data = await load_icon(icon_name = icon_name, icon_color = icon_color, icon_size = size, bg_color = bg_color, rotation = rotation)



#    svg_data = MDI.get_svg(icon_name)
#    if not svg_data:
#        raise ValueError(f"Icon '{icon_name}' not found")

#    _LOGGER.debug("icon found")

#    svg_data = svg_data.replace('fill="currentColor"', f'fill="{icon_color}"')                  # Farbe ersetzen (im SVG alle fill="" Attribute anpassen)
#    _LOGGER.debug("changed icon color to {icon_color}")
#    png_bytes = cairosvg.svg2png(bytestring=svg_data, output_width=size, output_height=size)      # Mit CairoSVG in PNG rendern (als Bytes)
#    _LOGGER.debug("rendered to PNG")
#    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")                      # In PIL laden
#    _LOGGER.debug("loaded in IMG")
#    img = img.rotate(rotation)
#    _LOGGER.debug(f"rotated {rotation} degrees")
#    bg = Image.new("RGB", img.size, bg_color)                                   # Hintergrundfarbe anwenden
#    _LOGGER.debug("created new background image")
#    bg.paste(img, mask=None)
#    _LOGGER.debug("pasted IMG into background image")
#    rgb_data = bg.tobytes()  # → R, G, B Bytefolge (RGB888)                     # RGB888 Bytes extrahieren
    

    px = size * size
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected icon size from coordinates should be {size}x{size} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in rgb_data[:40])
    _LOGGER.debug(f"prepared {len(rgb_data)} icon bytes for {serial_port}: {hex_str} [...]")

    try:
        await send_bitmap(hass, serial_port, x_position, y_position, x_position + size, y_position + size, bytes(rgb_data))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending the icon: {e}")





