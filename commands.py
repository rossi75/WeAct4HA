# protocol wird nachher umbenannt in commands
# open_serial wird nach tools verschoben

# +------------------------------+
# +80                            + 
# +y                             + ###########
# +y                             + ########
# +y                             + ########
# +y                             + ###########
# +0 xxxxxxxxxxxxxxxxxxxxxxxx 160+
# +------------------------------+

import asyncio, struct, logging
import subprocess
import serial
import time
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageColor
import io
from .iconutils import load_icon
import math
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "weact_display"
SERIAL = None
CLOCK_REMOVE_HANDLE = None

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


async def set_brightness(hass, serial_port, brightness):
    """setzt die Lautstärke"""
    _LOGGER.debug("setting volume [brightness]...")

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

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



async def send_bitmap(hass, serial_port, xs, ys, xe, ye, data_888: bytes):
    """Sendet ein Bitmap an das Display (CMD 0x05)."""
    _LOGGER.debug("finally sending bitmap...")

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


#async def write_text(hass, serial_port, text, xs, ys, font_size = 15, font = None, align = "left", t_color = (255, 255, 255), bg_color = (0, 0, 0), rotation = 0):
async def write_text(hass, serial_port, text, xs, ys, xe, ye, font_size = 15, t_color = (255, 255, 255), bg_color = (0, 0, 0), rotation = 0):
    _LOGGER.debug(f"writing some text")
    _LOGGER.debug(f"given values: text={text}, xs={xs}, ys={ys}, xe={xe}, ye={ye}, font_size={font_size}, text-color={t_color}, background-color={bg_color}, rotation={rotation}")

    await set_orientation(hass, serial_port, 2)

    # 
#    font = ImageFont.load_default()
#    draw.text((10, 30), "Hallo Welt", fill=(255, 255, 255), font=font)


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

    width = xe - xs + 1
    height = ye - ys + 1

    # Neues 80x80 Displaybild erstellen
#    img = Image.new("RGB", (80, 80), bg_color)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    i_width, i_height = img.size

    _LOGGER.debug("defined new image")

    # ggf das Datum, den WT oder die CPU Temp einpflanzen
    # Text
    font = ImageFont.load_default()
    draw.text((xs, ys), text, fill = t_color, font = font)
    _LOGGER.debug("wrote into the image")

    # bild ggf drehen
    img = img.rotate(rotation, expand=True)
    
    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    _LOGGER.debug(f"text {width}x{height} pixels")
    px = i_width * i_height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected text size from coordinates should be {i_width}x{i_height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} text bytes for {serial_port}: {hex_str} [...]")

    try:
        await send_bitmap(hass, serial_port, xs, ys, xe, ye, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending the text: {e}")


#    try:
#        bmp = text_to_bitmap_bytes(
#            text,
#            width=width,
#            height=height,
#            t_color=t_color,
#            bg_color=bgcolor,
#            align=align,
#            font_size=font_size,
#            font=font
#        )
#        await send_bitmap(SERIAL, x, y, width - 1, height - 1, bmp)
#        _LOGGER.debug(f"text received: '%s' (%dx%d, fg=%s, bg=%s, align=%s)",                     text, width, height, color, bgcolor, align)
#    except Exception as e:
#        _LOGGER.error(f"[{DOMAIN}] error while sending or rendering the image: {e}")


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
    


async def send_full_color(hass, serial_port, color, width = 80, height = 160):
    """Füllt das Display komplett mit einer Farbe."""
    _LOGGER.debug("filling display with one-color...")

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

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


async def generate_random(hass, serial_port):
    """show random pixels"""
    _LOGGER.debug("raising random bitmap")

    await set_orientation(hass, serial_port, 2)

    # delete screen
    _LOGGER.debug("clearing screen")
    black = [0, 0, 0]
    await send_full_color(hass, serial_port, black, width = 160, height = 80)

    width = 160
    height = 80

    try:
        _LOGGER.debug(f"generating random image with {width} x {height} pixel")
        buf = bytearray()
        for _ in range(width * height):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            buf += struct.pack("<BBB", r, g, b)

        hex_str = " ".join(f"{b:02X}" for b in buf[:40])
        _LOGGER.debug(f"generated {len(buf)} Bytes for {serial_port}: {hex_str} [...]")

        await send_bitmap(hass, serial_port, 0, 0, width, height, bytes(buf))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending (or generating?) the image: {e}")


async def show_init_screen(hass, serial_port):
    """initialen Bildschirm anzeigen"""
    _LOGGER.debug("show up initial screen")

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

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

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    packet = struct.pack(
        "<BBB",
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


#async def show_icon(icon_name: str, color="#FFFFFF", size=(48, 48), bg_color="#000000"):
async def show_icon(hass, serial_port, icon_name: str, icon_color = (255, 255, 255), bg_color = (0, 0, 0), x_position = 0, y_position = 0, size = 32, rotation = 0):
    """
    Lädt ein MDI-Icon, rendert es als RGB888-Bitmap und gibt Bytes zurück.
    """
    _LOGGER.debug("show icon...")

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

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


async def draw_line(hass, serial_port, xs, ys, xe, ye, l_color = (255, 255, 255), l_width = 1):
    _LOGGER.debug("draw a line ...")

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    await set_orientation(hass, serial_port, 2)

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    l_color = normalize_color(l_color)

    _LOGGER.debug(f"l_color_after = {l_color}")

    # Bereich berechnen
#    min_x = min(x1, x2)
#    max_x = max(x1, x2)
#    min_y = min(y1, y2)
#    max_y = max(y1, y2)
    min_x = min(xs, xe)
    max_x = max(xs, xe)
    min_y = min(ys, ye)
    max_y = max(ys, ye)
    width = max_x - min_x + 1
    height = max_y - min_y + 1

    _LOGGER.debug(f"calculated area: min_x = {min_x}, max_x = {max_x}, min_y = {min_y}, max_y = {max_y}, width = {width}, height = {height}")

    if l_color == (0, 0, 0):
        l_color = (1, 1, 1)
        _LOGGER.debug("needed to switch to safe color mode, due to a black line")

    # check that l_width is smaller than width and/or height
    

    # Lokales Bild
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
#    i_width, i_height = img.size

    _LOGGER.debug("defined new image")

    # Linie mit angepassten Koordinaten zeichnen
#    draw.line([(x1 - min_x, y1 - min_y), (x2 - min_x, y2 - min_y)], fill = l_color, width = l_width)
    draw.line([(xs - min_x, ys - min_y), (xe - min_x, ye - min_y)], fill = l_color, width = l_width)

    _LOGGER.debug("drew the line")

    _LOGGER.debug(f"line has {width}x{height} pixels")
    px = width * height
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected line size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} line bytes for {serial_port}: {hex_str} [...]")

    # Zeilenweise senden
    pixels = img.load()
    for y in range(height):
        line_bytes = bytes()
        for x in range(width):
            r, g, b = pixels[x, y]
            line_bytes += bytes([r, g, b])
            min_y_shift = min_y + y
            max_y_shift = max_y + y
        try:
#            await send_bitmap(hass, serial_port, xs = min_x, ys = min_y + y, xe = max_x, ye = min_y + y, bytes(line_bytes))
#            await send_bitmap(hass, serial_port, xs = min_x, ys = min_y + y, xe = max_x, ye = min_y + y, line_bytes)
            await send_bitmap(hass, serial_port, min_x, min_y_shift, max_x, max_y_shift, line_bytes)
#        await send_bitmap(hass, serial_port, 0, 0, width, height, bytes(buf))
        except Exception as e:
            _LOGGER.error(f"[{DOMAIN}] error while sending the line: {e}")



    # Neues 80x80 Displaybild erstellen
#    img = Image.new("RGB", (80, l_width), background_color)
#    draw = ImageDraw.Draw(img)
#    width, height = img.size


    # Linie zeichnen
#    draw.line((xs, ys, xe, ye), fill = l_color, width = l_width)         # 12
#    draw.line((0, 0, xe - xs + 1, ye - ys + 1), fill = l_color, width = l_width)         # 12

#    _LOGGER.debug("drew the line")

#    _LOGGER.debug(f"line has {width}x{height} pixels")
#    px = width * height
#    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
#    _LOGGER.debug(f"expected clock size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
#    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
#    _LOGGER.debug(f"prepared {len(img_bytes)} clock bytes for {serial_port}: {hex_str} [...]")

#    try:
#        await send_bitmap(hass, serial_port, xs, ys, xe, ye, bytes(img_bytes))
#    except Exception as e:
#        _LOGGER.error(f"[{DOMAIN}] error while sending the line: {e}")


async def draw_circle(hass, serial_port, xp, yp, r, bg_color = (0, 0, 0), c_color = (255, 255, 255), f_color = (255, 0, 0), cf_width = 1, e = None):
    _LOGGER.debug("draw a circle ...")

    await set_orientation(hass, serial_port, 2)

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    bg_color = normalize_color(bg_color)
    c_color = normalize_color(c_color)
    f_color = normalize_color(f_color)

    _LOGGER.debug(f"colors after normalize: bg_color={bg_color}, c_color={c_color}, f_color={f_color}")

    if e is None:
        e = r
        _LOGGER.debug("no value given for ellipse, taking radius as second circle factor")
    _LOGGER.debug(f"given circle: radius={r}, ellipse={e}")

    # calculate the place to be
    xs = xp - r
    ys = yp - e
    xe = xp + r
    ye = yp + e

    _LOGGER.debug(f"calculated where to place the circle image: xs={xs}, ys={ys}, xe={xe}, ye={ye}")

    # check for ranges out-of-display
    xs = max(xs, 0)
    ys = max(ys, 0)
    xe = min(159, xe)
    ye = min(79, ye)

    _LOGGER.debug(f" corrected where to place the circle image: xs={xs}, ys={ys}, xe={xe}, ye={ye}")

    # Neues Displaybild erstellen
    img = Image.new("RGB", (r * 2, e * 2), bg_color)
    draw = ImageDraw.Draw(img)
    i_width, i_height = img.size

    _LOGGER.debug(f"defined new image with {i_width}x{i_height} px")

    # Kreis zeichnen
    draw.ellipse((0, 0, r * 2,e * 2), outline = c_color, width = cf_width, fill = f_color)                                   # Äußerer Kreis

    _LOGGER.debug("drew the circle")

    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    _LOGGER.debug(f"circle has a radius of {r} pixels (with an ellipse of {e} pixels)")
    px = r * 2 * r * 2
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected circle size from coordinates should be {i_width}x{i_height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} circle bytes for {serial_port}: {hex_str} [...]")

    try:
        await send_bitmap(hass, serial_port, xs, ys, xe, ye, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending the circle: {e}")


async def draw_rectangle(hass, serial_port, xs, ys, xe, ye, rf_width = 1, r_color = (0, 0, 0), f_color = None):
    _LOGGER.debug("draw a rectangle ...")

    await set_orientation(hass, serial_port, 2)

    if f_color is None:
        f_color = r_color
        _LOGGER.debug("no value given for f-color, taking r-color for filling")

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    r_color = normalize_color(r_color)                     
    f_color = normalize_color(f_color)

    _LOGGER.debug(f"colors after normalize: rectangle-color={r_color}, frame-color={f_color}")

    width = xe - xs + 1
    height = ye - ys + 1

    _LOGGER.debug(f"calculated width x height = {width}x{height}")

    # Bild erzeugen
    img = Image.new("RGB", (width, height), f_color)
    draw = ImageDraw.Draw(img)
    i_width, i_height = img.size

    _LOGGER.debug("defined new image")

    # Rahmen & Füllung zeichnen
    draw.rectangle(xs, ys, xe, ye, width = rf_width, outline = r_color)

    # Bild extrahieren
    img_bytes = img.tobytes()  # ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    _LOGGER.debug(f"rectangle has square of {width}x{height} px")
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected rectangle size from coordinates should be {i_width}x{i_height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} rectangle bytes for {serial_port}: {hex_str} [...]")

    # Bitmap an Display senden
    try:
        await send_bitmap(hass, serial_port, xs, ys, xe, ye, bytes(img_bytes))
    except Exception as e:
        _LOGGER.error(f"[{DOMAIN}] error while sending the rectangle: {e}")


#def draw_triangle(draw, xa, ya, xb, yb, xc, yc, outline_color=(255,255,255), fill_color=None, width=1):
#        await draw_triangle( bg_color, t_color, f_color, tf_width, xa, ya, xb, yb, xc, yc)

#def draw_triangle(hass, SERIAL, xa, ya, xb, yb, xc, yc, outline_color=(255,255,255), fill_color=None, width=1):
async def draw_triangle(hass, SERIAL, xa, ya, xb, yb, xc, yc, bg_color = (0, 0, 0), t_color = (255,255,255), f_color = None, tf_width = 1):
    """
    Zeichnet ein Dreieck mit Rahmen und optionaler Füllung.
    
    draw: PIL.ImageDraw.Draw-Objekt
    xa, ya, xb, yb, xc, yc: Koordinaten der drei Punkte
    bg_color: Farbe des Hintergrundes (tuple RGB)
    t_color: Farbe des Rahmens (tuple RGB)
    f_color: Füllfarbe (tuple RGB) oder None
    tf_width: Dreieck-Rahmenbreite
    """
    _LOGGER.debug("draw a triangle ...")

    if not serial_port:
        _LOGGER.warning("Display not connected")
        return

    await set_orientation(hass, serial_port, 2)

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    bg_color = normalize_color(bg_color)                     
    t_color = normalize_color(t_color)
    f_width = normalize_color(f_width)

    _LOGGER.debug(f"colors after normalize: background-color={r_color}, triangle-color={t_color}, frame-color={f_color}, triangle-frame-width={tf_width}")

#    points = [(xa, ya), (xb, yb), (xc, yc)]
#    draw.polygon(points, outline=outline_color, fill=fill_color)
#    if width > 1:
#        # Rahmen mehrfach zeichnen für breiteren Rand
#        for i in range(1, width):
#            draw.polygon(
#                [(xa+i, ya+i), (xb+i, yb+i), (xc+i, yc+i)],
#                outline=outline_color
#            )


              #          outline_color=(255,255,255),
              #          fill_color=None, width=1):

    # 1️⃣ Bereich berechnen
    min_x = min(xa, xb, xc)
    max_x = max(xa, xb, xc)
    min_y = min(ya, yb, yc)
    max_y = max(ya, yb, yc)

    width = max_x - min_x + 1
    height = max_y - min_y + 1

    _LOGGER.debug(f"limitations: min-X = {min_x}, max-X = {max_x}, min-Y = {min_y}, max-Y = {max_y}, width = {width}, height = {height}")

    # Lokales Bild erzeugen
#    img = Image.new("RGB", (w, h), (0, 0, 0))
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Koordinaten anpassen (verschieben)
    adj_points = [(xa - min_x, ya - min_y),
                  (xb - min_x, yb - min_y),
                  (xc - min_x, yc - min_y)]
    draw.polygon(adj_points, outline = t_color, fill = f_color)

#    # Rahmen mehrfach zeichnen für breiteren Rand
#    if width > 1:
#        for i in range(1, width):
#            draw.polygon([(xa+i, ya+i), (xb+i, yb+i), (xc+i, yc+i)], outline=t_color, fill = f_color)

    # RGB-Daten erzeugen
    img_bytes = img.tobytes()

    _LOGGER.debug(f"circle has a radius of {radius} pixels")
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"expected triangle size from coordinates should be {width}x{height} = {px} px. RGB888 = {rgb888} bytes")
    hex_str = " ".join(f"{b:02X}" for b in img_bytes[:40])
    _LOGGER.debug(f"prepared {len(img_bytes)} triangle bytes for {serial_port}: {hex_str} [...]")

    # An Display senden (nur relevanten Bereich)
    await send_bitmap(hass, serial_port, min_x, min_y, max_x, max_y, img_bytes)






