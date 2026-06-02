# open_serial wird nach tools verschoben
# normalize und wird nach tools verschoben
# neue fkt send_command für einfache direkte Kommandos
# https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
#     await asyncio.sleep(4)                   # kleine Pause um direkt auf einmal verschiedene Funktionen zu testen

# https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html

import ast
import asyncio, struct, logging
import io
import math
import os
import qrcode
import random
import subprocess
import serial
import time
import zlib  # V1

import custom_components.weact_display.const as const
from PIL import Image, ImageDraw, ImageFont, ImageColor
from datetime import datetime, timedelta
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from pathlib import Path
from .iconutils import load_icon
from .models import DISPLAY_MODELS

_LOGGER = logging.getLogger(__name__)

#************************************************************************
#        O P E N  S E R I A L
#************************************************************************
# initializes the serial port via STTY and opens it
#************************************************************************
# m: port
#************************************************************************
def open_serial(device_path: str):
    _LOGGER.debug(f"initializing serial port {device_path} ...")

    if not os.path.exists(device_path):
        _LOGGER.error(f"serial-port {device_path} does not exist")
        return None

    try:
        serial_port = serial.Serial(
            port=device_path,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            write_timeout=1,
            xonxoff=False,           # +
            rtscts=False,            # +
            dsrdtr=False             # +
        )

        if serial_port.is_open:
            _LOGGER.debug(f"opened serial-port {serial_port} with device-path {device_path}")
        else:
            _LOGGER.warning(f"could not open serial-port {serial_port} with device-path {device_path}")
            return None

        return serial_port

    except serial.SerialException as e:
        _LOGGER.error(f"error while opening port {device_path}: {e}")
        return None

    except Exception as e:
        _LOGGER.error(f"Unexpected error initializing port {device_path}: {e}")
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

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    width = device.get("width")
    height = device.get("height")

    img = device.get("shadow")
    i_width, i_height = img.size
    img_bytes = img.tobytes()       # Bild extrahieren, ergibt z.B. 160 * 80 * 3 = 38400 Bytes (RGB888)

    px = i_width * i_height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    _LOGGER.debug(f"image size is {i_width}x{i_height}={px} px, RGB888={rgb888} bytes")
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
# and afterwards polls the actual brightness 
#************************************************************************
# m: hass
# m: serial_number
# m: brightness
#************************************************************************
async def set_brightness(hass, serial_number, target_brightness):
    """setzt die Lautstärke"""
    _LOGGER.debug("setting brightness...")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
        return

    # entry-data lookup
    entry_id = device.get("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        _LOGGER.error(f"no config entry found for serial {serial_number}")
        return

    # Config aktualisieren, runtime wird durchs Polling erledigt
    new_options = {
        **entry.options,
        "brightness": target_brightness,
    }
    hass.config_entries.async_update_entry(entry, options=new_options)

    _LOGGER.debug(f"stored new brightness-value for serial {serial_number} to {entry.options.get("brightness")}")

    packet = struct.pack(
        "<BBHB",
        0x03, target_brightness, 0x3500, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)

    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)

    packet = struct.pack("<BB", 0x83, 0x0A)                   # Brightness Request
    hex_str = " ".join(f"{b:02X}" for b in packet)

    _LOGGER.debug(f"prepared polling with {len(packet)} Bytes for {serial_number}: {hex_str}")

    timeout = 15    # Sekunden
    start = time.monotonic()
    while True:
        # Helligkeit abfragen
        _LOGGER.debug("requesting brightness...")

        await hass.async_add_executor_job(serial_port.write, packet)
        await asyncio.sleep(1)
        current_brightness = device.get("brightness")

        _LOGGER.debug(f"polled brightness for serial {serial_number}: target-brightness={target_brightness}, current-brightness={current_brightness}")

        if current_brightness == target_brightness:
            _LOGGER.info(f"Target brightness of {current_brightness} reached for serial {serial_number}")
            break

        if time.monotonic() - start > timeout:
            _LOGGER.warning(f"brightness fade timeout reached for serial {serial_number}")
            break

    _LOGGER.debug("brightness done")


#************************************************************************
#        O R I E N T A T I O N
#************************************************************************
# sets the orientation
#************************************************************************
# m: hass
# m: serial_number
# m: orientation, default = 2 (landscape)
# o: force, default = false, no check for actual orientation if set (startup)
#************************************************************************
async def set_orientation(hass, serial_number, orientation_value, force = False):
    _LOGGER.debug("setting orientation")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    model = device.get("model")

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
        return

    if device.get("orientation_value") == orientation_value:
        _LOGGER.debug(f"old ({device.get("orientation_value")}) and new orientation ({orientation_value}) are the same, nothing to change. Aborting orientation command!")
        if force is False:
            return
        else:
            _LOGGER.debug(f"oops, I was forced to override the orientation check, continuing")

    params = DISPLAY_MODELS.get(model, None)
    if orientation_value in (2, 3):                                                                   # Landscape
        device["width"] = params["large"]
        device["height"] = params["small"]
    elif orientation_value in (0, 1):                                                                  # Portrait
        device["width"] = params["small"]
        device["height"] = params["large"]
    else:
        _LOGGER.error(f"unknown orientation_value {orientation_value}, not changing anything")
        return

    # array-table [old][new]: [[0,2,3,1],[2,0,1,3],[1,3,0,2],[3,1,2,0]], see internal_struct.md for evidence
    img = device.get("shadow")
    _LOGGER.debug("read image from instance")
    rotations = const.ORIENTATION_CONVERSION_MAP[device.get("orientation_value")][orientation_value]
    img = img.rotate(-90 * rotations, expand = True)
    _LOGGER.debug(f"rotated the BMP {rotations} times counterclockwise by 90° = {-90 * rotations}°")
    device["shadow"] = img
    _LOGGER.debug("stored rotated image back into instance")

    device["orientation_value"] = orientation_value
    _LOGGER.debug(f"new orientation-value={orientation_value}, {device.get("width")}x{device.get("height")} px")

    # entry-data lookup
    entry_id = device.get("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        _LOGGER.error(f"no config entry found for serial {serial_number}")
        return

    # Config aktualisieren, runtime wird durchs Polling erledigt
    new_options = {
        **entry.options,
        "orientation_value": orientation_value,
    }
    hass.config_entries.async_update_entry(entry, options=new_options)

    _LOGGER.debug(f"stored new orientation-value for serial {serial_number} to {entry.options.get("orientation_value")}")

    packet = struct.pack(
        "<BBB",
        0x02, orientation_value, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)
    await asyncio.sleep(0.1)
    await send_screen(hass, serial_number)

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

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
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
#        R E A D  F I R M W A R E  V E R S I O N
#************************************************************************
# reads firmware version from display
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
async def read_firmware_version(hass, serial_number):
    _LOGGER.debug("requesting firmware version")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
        return

    packet = struct.pack(
        "<BB",
        0xC2, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)
    await asyncio.sleep(0.1)


#************************************************************************
#        R E A D  W H O  A M  I
#************************************************************************
# reads who-am-i description from display
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
async def read_who_am_i(hass, serial_number):
    _LOGGER.debug("requesting who-am-i from display")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
        return

    packet = struct.pack(
        "<BB",
        0x81, 0x0A
    )

    # das hier nachher in send_data verschieben
    hex_str = " ".join(f"{b:02X}" for b in packet)
    _LOGGER.debug(f"having {len(packet)} Bytes for {serial_number}: {hex_str}")

    await hass.async_add_executor_job(serial_port.write, packet)
    await asyncio.sleep(0.1)


#************************************************************************
#        P A C K E T  P A R S E R
#************************************************************************
# parses the packets received from a display
#************************************************************************
# m: packet-Bytes
# r: True if packet could be parsed, False if any error occured
#************************************************************************
def parse_packet(hass, serial_number, packet: bytes):
    # Mindestlänge: Start + Endbyte
    if not packet or len(packet) < 2:
        _LOGGER.info(f"Received an empty packet or packet-length < 2 Bytes from serial {serial_number}: Packet-length={len(packet)}, discarding packet bytes")
        return False

    # Endbyte prüfen
    if packet[-1] != 0x0A:
        _LOGGER.info(f"Last byte is not 0x0A, so the end of the packet cannot be determined and all bytes received from serial {serial_number} must be discarded")
        return False

    device = hass.data[const.DOMAIN]["devices"][serial_number]
    cmd = packet[0]
    try:
        # -----------------------------
        # PARSE HUMITURE REPORT (0x86)
        # [0x86] [T_low] [T_high] [H_low] [H_high] [0A]
        # -----------------------------
        if cmd == 0x86:
            if len(packet) != 6:
                return False

            t_low  = packet[1]
            t_high = packet[2]
            h_low  = packet[3]
            h_high = packet[4]

            temp_raw = (t_high << 8) | t_low
            hum_raw  = (h_high << 8) | h_low

            device["temperature"] = temp_raw / 100.0
            device["humidity"]    = hum_raw / 100.0

            entity = device.get("entity")
            if entity:
                hass.loop.call_soon_threadsafe(entity.async_write_ha_state)
    
            _LOGGER.info(f"received humiture values for serial {serial_number}: {device["temperature"]:.2f} °C, {device["humidity"]:.2f} %")

            return True

        # -----------------------------
        # PARSE SYSTEM VERSION (0xC2)
        # -----------------------------
        elif cmd == 0xC2:
            firmware_version = packet[1:-1].decode(errors="ignore").strip()
            if not firmware_version:
                return False
            device["firmware_version"] = firmware_version
            device_registry = dr.async_get(hass)

            dev_reg = device_registry.async_get_device(identifiers={(const.DOMAIN, serial_number)})

            hass.loop.call_soon_threadsafe(
                lambda: hass.async_create_task(
                    _async_update_firmware_device(
                        hass,
                        serial_number,
                        firmware_version,
                    )
                )
            )
            
            _LOGGER.info(f"Firmware version for serial {serial_number}: {device["firmware_version"]}")

            return True

        # -----------------------------
        # PARSE WHO AM I (0x81)
        # -----------------------------
        elif cmd == 0x81:
            who_am_i = packet[1:-1].decode(errors="ignore").strip()
            if not who_am_i:
                return False

            device["who_am_i"] = who_am_i

            _LOGGER.info(f"Device description for serial {serial_number}: {device["who_am_i"]}")

            return True

        # -----------------------------
        # PARSE BRIGHTNESS (0x83)
        # -----------------------------
        elif cmd == 0x83:
            if len(packet) != 3:
                return False

            brightness = packet[1]
            if not brightness:
                return False

            device["brightness"] = brightness

            _LOGGER.info(f"received new brightness from serial {serial_number}: {device["brightness"]}")

            return True

        # -----------------------------
        # PARSE UNKNOWN COMMAND
        # -----------------------------
        else:
            _LOGGER.info(f"unrecognized answer from serial {serial_number}: {cmd.hex()}")
            return False

    except Exception as e:
        _LOGGER.error(f"Error while parsing a packet from serial {serial_number}: {e}")
        return False


#************************************************************************
#        S E N D  B I T M A P
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
    _LOGGER.debug("finally sending bitmap...")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    #fastlz = device.get("fastlz", False)
    #fastlz = True
    fastlz = False              # mandatory NO !

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
        return

    width = xe - xs
    height = ye - ys
    px = width * height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)
    rgb565 = px * 2  # anzahl bytes RGB565 (8-3 + 8-3 + 8-3 = 16 bit = 2 byte pro pixel)

    _LOGGER.debug(f"expected bitmap size from coordinates should be {width}x{height}={px} px. RGB888={rgb888} bytes, RGB565={rgb565} bytes")

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

    if fastlz is True:
        command = const.CMD_SET_BITMAP_FASTLZ
        CHUNK_SIZE = width * 4
        _LOGGER.debug(f"using FASTLZ for serial communication")
    else:
        command = const.CMD_SET_BITMAP
        CHUNK_SIZE = width * 2  # empirisch aus USB-Sniffing
        _LOGGER.debug(f"using classic data transmission speed for serial communication")

    _LOGGER.debug(f"chunk size is {CHUNK_SIZE} bytes per write")

    header = struct.pack("<BHHHHB", command, xs, ys, xe-1, ye-1, 0x0A)

    hex_str = " ".join(f"{b:02X}" for b in header)
    _LOGGER.debug(f"need to send {len(header)} header bytes for {serial_number}: {hex_str}")
    hex_str = " ".join(f"{b:02X}" for b in data_565[:40])
    _LOGGER.debug(f"... and {len(data_565)} bitmap bytes as RGB565 for {serial_number}: {hex_str} [...]")

    if not await _wait_for_display(hass, serial_number):                 # Display sperren
        _LOGGER.error(f"seems that display {serial_number} is permanently blocked. Please restart integration")
        return

    await hass.async_add_executor_job(serial_port.write, header)
    _LOGGER.debug("header write done")
    await hass.async_add_executor_job(serial_port.flush)
    _LOGGER.debug("header flush done")

    # Nun die Bilddaten in Blöcken senden
    await asyncio.sleep(0.05)
    j = 1
    if fastlz is True:
        compressed_len = 0
        for i in range(0, len(data_565), CHUNK_SIZE):
            chunk = data_565[i:i + CHUNK_SIZE]
            compressed_chunk  = zlib.compress(chunk)
            compressed_len   += len(compressed_chunk)
            chunk_with_header = struct.pack("<HH", len(chunk), len(compressed_chunk[4:])) + compressed_chunk[4:]
            await hass.async_add_executor_job(serial_port.write, chunk_with_header)
            j += 1
        _LOGGER.debug(f"Sent {compressed_len} bytes in {j} chunks of {CHUNK_SIZE} bytes")
    else:
        for i in range(0, len(data_565), CHUNK_SIZE):
            chunk = data_565[i:i + CHUNK_SIZE]
            await hass.async_add_executor_job(serial_port.write, chunk)
            await hass.async_add_executor_job(serial_port.flush)
            await asyncio.sleep(0.001)  # kleine Pause zwischen den Chunks
            j += 1
        _LOGGER.debug(f"Sent {len(data_565)} bytes in {j} chunks of {CHUNK_SIZE} bytes")

    await _release_display(hass, serial_number)               # Display wieder freigeben


async def _wait_for_display(hass, serial_number, timeout=5.0):
    dev = hass.data[const.DOMAIN]["devices"][serial_number]
    lock = dev["lock"]

    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        dev["state"] = "busy"
        _LOGGER.debug(f"locked display {serial_number}")
    except asyncio.TimeoutError:
        dev["state"] = "timeout error"
        _LOGGER.error(f"{serial_number}: display busy timeout → switching to ERROR")
        return False

    # erfolgreich gelockt → Busy setzen
    dev["state"] = "busy"
    return True

async def _release_display(hass, serial_number):
    dev = hass.data[const.DOMAIN]["devices"][serial_number]
    lock = dev["lock"]

    if lock.locked():
        lock.release()
        _LOGGER.debug(f"released display {serial_number}")

    dev["state"] = "ready"


#************************************************************************
#        S H O W  B M P
#************************************************************************
# shows the a given BMP or the file testbild.bmp
#************************************************************************
# m: hass
# m: serial_number
# o: xs = X-Start
# o: xs = X-Start
# o: filepath
#************************************************************************
# reads a BMP-file and sends it out to the WeAct Display
#************************************************************************
async def show_bmp(hass, serial_number, xs = None, ys = None, filepath = None):
    _LOGGER.debug("show a bmp file...")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    d_width  = device.get("width")
    d_height = device.get("height")
    shadow   = device.get("shadow")

    # Path handling
    if filepath:
        path = Path(filepath)
        if not path.is_absolute():
            path = Path(hass.config.path(filepath))
    else:
        path = Path(hass.config.path("custom_components","weact_display","testbild.bmp"))

    if not path.exists():
        _LOGGER.error(f"File not found: {path}")
        return
    else:
        _LOGGER.debug(f"Using file: {path}")

    # load BMP
    def _load_image():
        img = Image.open(path).convert("RGB")
        return img

    try:
        img = await hass.async_add_executor_job(_load_image)
        _LOGGER.debug("opened file {path}")
    except Exception as e:
        _LOGGER.error(f"[{const.DOMAIN}] error while opening the image {path}: {e}")

    i_width, i_height = img.size
    px = i_width * i_height
    rgb888 = px * 3  # anzahl bytes RGB888 (8 + 8 + 8 = 24 bit = 3 byte pro pixel)

    _LOGGER.debug(f"bmp has {i_width}x{i_height} pixels, means {px} pixels and {rgb888} RGB888 bytes. Display has {d_width}x{d_height} pixels")

    if i_width > d_width or i_height > d_height:
        def _resize():
            img.thumbnail((d_width, d_height), Image.LANCZOS)
            return img

        img = await hass.async_add_executor_job(_resize)
        i_width, i_height = img.size

        _LOGGER.debug(f"Image resized to {i_width}x{i_height}")

    # Positionierung
    if xs is None:
        xs = (d_width - i_width) // 2
    if ys is None:
        ys = (d_height - i_height) // 2
    xs = max(0, xs)
    ys = max(0, ys)

    _LOGGER.debug(f"Image will be placed at {xs}|{ys}")

    shadow.paste(img, (xs, ys))

    _LOGGER.debug("pasted image into instance")
                        
    await send_screen(hass, serial_number)


#************************************************************************
#        F U L L  C O L O R
#************************************************************************
# shows the complete screen in one color
# direct function, does NOT write into shadow memory
#************************************************************************
# m: hass
# m: serial_number
# m: color
#************************************************************************
async def send_full_color(hass, serial_number, color):
    _LOGGER.debug("filling display with one-color...")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
        return

    width = device.get("width")
    height = device.get("height")

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
#        R E P L A C E  B A C K G R O U N D  C O L O R
#************************************************************************
# replaces all pixels with the old color to the new color.
# no need to supply the new color as it is within the data struct,
# but the old color we do not know...
#************************************************************************
# m: hass
# m: serial_number
# m: old_color
#************************************************************************
async def replace_bg_color(hass, serial_number, old_color):
    _LOGGER.debug("Replacing background")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    old_color = normalize_color(old_color)
    bg_color = normalize_color(device.get("background_color"))
    _LOGGER.debug(f"colors after normalize: old-color={old_color}, bg-color={bg_color}")

    # Schattenbild abholen
    img = device.get("shadow")
    _LOGGER.debug("fetched image from instance")

    pixels = img.load()
    i = 1
    for y in range(img.height):
        for x in range(img.width):
            if pixels[x, y] == old_color:
                pixels[x, y] = bg_color
                i += 1
    _LOGGER.debug(f"replaced {i} background px for serial {serial_number}")

    await send_screen(hass, serial_number)

#************************************************************************
#        S E L F  T E S T
#************************************************************************
# shows black, all native colors, white, background-color
#************************************************************************
# m: hass
# m: serial_number
#************************************************************************
async def display_selftest(hass, serial_number: str):
    _LOGGER.debug("Starting display self test")

    background_color = hass.data[const.DOMAIN]["devices"][serial_number].get("background_color")     # hier steht definitv schon ein Fallback-Wert drin !
    colors = [
        (0, 0, 0),                           # Schwarz (Start)
        (255, 0, 0),                         # Rot
        (0, 255, 0),                         # Grün
        (0, 0, 255),                         # Blau
        (255, 255, 255),                     # Weiß
        normalize_color(background_color)    # Background-Color = Finale
    ]

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
# o: suppress_delete
#************************************************************************
async def generate_random(hass, serial_number, suppress_delete=False):
#def generate_random(hass, serial_number):
    _LOGGER.debug("raising random bitmap")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    width = device.get("width")
    height = device.get("height")

    # delete screen
    if not suppress_delete:
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

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    serial_port = device.get("serial_port")           # check needed due to direct command
    if not serial_port:
        _LOGGER.warning(f"Display {serial_number} not connected")
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
# o: rotation
#************************************************************************
# rotate from: https://stackoverflow.com/questions/45179820/draw-text-on-an-angle-rotated-in-python
#************************************************************************
async def show_icon(hass, serial_number, i_name: str, xs, ys, i_size = 32, i_color = (255, 255, 255), rotation = 0):
    _LOGGER.debug("show icon...")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if i_color is None:
        i_color = (255, 255, 255)
        _LOGGER.debug(f"set icon-color to {i_color} as no parameter is given")
    else:
        i_color = normalize_color(i_color)
    _LOGGER.debug(f"colors after normalize: icon-color={i_color}")

    icon = await load_icon(hass, i_name = i_name, i_size = i_size, i_color = i_color, rotation = rotation)
    icon = icon.convert("RGBA")

    _LOGGER.debug(f"icon parameters: xs={xs}, ys={ys}, icon-size={i_size}x{i_size}, rotation={rotation}, icon-bytes={len(icon.tobytes())}")

    shadow = device.get("shadow")

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

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    l_color = normalize_color(l_color)

    _LOGGER.debug(f"l_color_after={l_color}")

    img = device.get("shadow")
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
# o: ellipse, set to radius if not given
# o: circle-color, default = white (255, 255, 255)
# o: fill-color, default = red (255, 0, 0)
# o: circle-frame width, default = 1
#************************************************************************
async def draw_circle(hass, serial_number, xp, yp, r, e = None, c_color = (255, 255, 255), f_color = (255, 0, 0), cf_width = 0):
    _LOGGER.info("draw a circle ...")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    width = device.get("width")
    height = device.get("height")

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
    img = device.get("shadow")
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

    device = hass.data[const.DOMAIN]["devices"][serial_number]

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

    _LOGGER.debug(f"colors after normalize: rectangle-frame-color={rf_color}, fill-color={f_color}")

    # Schattenbild abholen
    img = device.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    # Rahmen & Füllung zeichnen
    draw.rectangle((xs, ys, xe, ye), width = rf_width, outline = rf_color)
    _LOGGER.debug(f"drew rectangle with xs={xs}, ys={ys}, xe={xe}, ye={ye}, rf-width={rf_width}, rf-color={rf_color}")
    if f_color is not None:
        draw.rectangle((xs + rf_width, ys + rf_width, xe - rf_width, ye - rf_width), fill = f_color)
        _LOGGER.debug(f"filled rectangle with rf-width={rf_width}, f-color={f_color}")

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

    device = hass.data[const.DOMAIN]["devices"][serial_number]

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
    img = device.get("shadow")
    draw = ImageDraw.Draw(img)

    _LOGGER.debug("fetched image from instance")

    triangle_points = [(xa, ya),
                  (xb, yb),
                  (xc, yc)]
    draw.polygon(triangle_points, fill = t_color, outline = tf_color, width = tf_width)

    _LOGGER.debug(f"drew polygon points: {triangle_points}")

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
# o: background-color
# o: text-color, default = white (255, 255, 255)
# o: rotation
#************************************************************************
async def write_text(hass, serial_number, text, xs, ys, xe, ye, font_size = 15, t_color = None, bg_color = None, rotation = 0):
    _LOGGER.debug(f"writing some text with values given: serial-number={serial_number}, text={text}, xs={xs}, ys={ys}, xe={xe}, ye={ye}, font-size={font_size}, text-color={t_color}, background-color={bg_color}, rotation={rotation}")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    if t_color is None:
        t_color = (255, 255, 255)
        _LOGGER.debug(f"set text-color to {t_color} as no parameter is given")
    else:
        t_color = normalize_color(t_color)
    if bg_color is None:
        bg_color = normalize_color(device.get("background_color"))
        _LOGGER.debug(f"set background-color to displays' default bg-color {bg_color} as no parameter is given")
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

    img = device.get("shadow")
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
# o: background-color
# o: rotation, default = 90
#************************************************************************
async def draw_progress_bar(hass, serial_number, xs, ys, xe, ye, bar_value=None, min_value=0, max_value=100, bf_width=1, bf_color=None, b_color=(255, 255, 255), bg_color=None, rotation = 90, show_value=False, val_appendix=""):
    _LOGGER.debug(f"doing a progress with the values given: xs={xs}, ys={ys}, xe={xe}, ye={ye}, bar-value={bar_value}, min-value={min_value}, max-value={max_value}, bar-frame-width={bf_width}, bar-color={b_color}, bar-frame-color={bf_color}, background-color={bg_color}, rotation={rotation}, show-value={show_value}, value-appendix={val_appendix}")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    if bf_color is None:
        bf_color = b_color
        _LOGGER.debug("no value given for bar-frame-color, taking bar-color for frame")
    if bg_color is None:
        bg_color = normalize_color(device.get("background_color"))
        _LOGGER.debug(f"set background-color to displays' default bg-color {bg_color} as no parameter is given")

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
    img = device.get("shadow")
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
#        value_str = f"{int(bar_value)}%" + val_appendix
        value_str = f"{int(bar_value)}" + val_appendix
        font_size = int(bar_h - bf_width - bf_width - 2)
        try:
#            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(bar_h * 0.5))                # warum hier ein Faktor von 0,5? Ich würde ja eher sagen -4, oder?
#            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(bar_h - bf_width - bf_width - 2))                # warum hier ein Faktor von 0,5? Ich würde ja eher sagen -4, oder?
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)                # warum hier ein Faktor von 0,5? Ich würde ja eher sagen -4, oder?
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), value_str, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = (bar_w - text_w) // 2
        ty = (bar_h - text_h) // 2

        _LOGGER.debug(f"show_value for '{value_str}' is given: text-width={text_w} px, text-height={text_h} px, at x={tx}, y={ty}")

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
# o: size
# o: qr-color, default = white (255, 255, 255)
# o: background-color
#************************************************************************
async def generate_qr(hass, serial_number, data, xs, ys, size=None, qr_color=None, bg_color=None):
    _LOGGER.info(f"generating a qr code")
    _LOGGER.debug(f"given values: data={data}, xs={xs}, ys={ys}, size={size}, qr-color={qr_color}, background-color={bg_color}")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    if qr_color is None:
        qr_color = (255, 255, 255)
        _LOGGER.debug(f"set qr-color to {qr_color} as no parameter is given")
    if bg_color is None:
        bg_color = normalize_color(device.get("background_color"))
        _LOGGER.debug(f"set background-color to displays' default bg-color {bg_color} as no parameter is given")

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    qr_color = normalize_color(qr_color)
    bg_color = normalize_color(bg_color)                     
    _LOGGER.debug(f"colors after normalize: qr-color={qr_color}, background-color={bg_color}")

    qr = qrcode.QRCode(border=1, box_size=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color = qr_color, back_color = bg_color).convert("RGB")     # take a look at the colors, but they need to be in that order !
    _LOGGER.debug(f"produced QR code, fc=qr, bc=bg")

    # check boundaries
    qr_width, qr_height = img.size
    if size is None:
        size = qr_width
        _LOGGER.debug(f"set qr size to same as qr-width ({qr_width}), as no value is given for size")
    scale_x = size // qr_width
    scale_y = size // qr_height
    scale = min(scale_x, scale_y)
    _LOGGER.debug(f"dimensions: qr-width={qr_width}, qr-height={qr_height}, scale-x={scale_x}, scale-y={scale_y}, scale={scale}")

    if (scale < 1):
        _LOGGER.warning(f"for the given data ({data}) we would need {qr_width} x {qr_height} px, but this does not fit into given size of {size} x {size} px")
        return False
    if (xs + size) > device.get("width"):
        _LOGGER.warning(f"At this X-position ({xs}), the QR image ({size} px) would exceed the image width dimensions ({device.get("width")} px), cancelling !")
        return False
    if (ys + size) > device.get("height"):
        _LOGGER.warning(f"At this Y-position ({ys}), the QR image ({size} px) would exceed the image width dimensions ({device.get("height")} px), cancelling !")
        return False

    img = img.resize((qr_width * scale, qr_height * scale), Image.NEAREST)
    qr_width_resized, qr_height_resized = img.size
    _LOGGER.debug(f"dimensions after resize: qr-width={qr_width_resized}, qr-height={qr_height_resized}")

    shadow = device.get("shadow")
    _LOGGER.debug("read image from instance")

    shadow.paste(img, (xs, ys))
    _LOGGER.debug(f"pasted QR code into image")
    
    await send_screen(hass, serial_number)


#************************************************************************
#        D R A W  A  L I N E  C H A R T
#************************************************************************
# draws a line chart
#************************************************************************
# m: hass
# m: serial_number
# m: data
# m: xs
# m: ys
# m: xe
# m: ye
# m: line_values
# m: line_width
# o: line_color
# o: bg_color
# o: mark_points
# o: show_axis
#************************************************************************
async def draw_line_chart(hass, serial_number, xs, ys, xe, ye, line_values, line_width=None, line_color=None, axis_color=None, bg_color=None, mark_points=None, show_axis=None, ground_to_zero=None):
    _LOGGER.info(f"drawing a line chart")
    _LOGGER.debug(f"given values: xs={xs}, ys={ys}, xe={xe}, ye={ye}, line-values={line_values}, line-width={line_width}, line-color={line_color}, axis-color={axis_color}, background-color={bg_color}, mark-points={mark_points}, show-axis={show_axis}, ground-to-zero={ground_to_zero}")

    device = hass.data[const.DOMAIN]["devices"][serial_number]

    if line_color is None:
        line_color = (255, 255, 255)
        _LOGGER.debug(f"set line-color to {line_color} as no parameter is given")
    if line_width is None:
        line_width = 1
        _LOGGER.debug(f"set line-width to {line_width} as no parameter is given")
    if bg_color is None:
        bg_color = normalize_color(device.get("background_color"))
        _LOGGER.debug(f"set background-color to displays' default bg-color {bg_color} as no parameter is given")
    if axis_color is None:
        axis_color = (128, 128, 128)
        _LOGGER.debug(f"set axis-color to {axis_color} as no parameter is given")
    if mark_points is None:
        mark_points = False
        _LOGGER.debug(f"set mark-points to {mark_points} as no parameter is given")
    if show_axis is None:
        show_axis = False
        _LOGGER.debug(f"set show-axis to {show_axis} as no parameter is given")
    if ground_to_zero is None:
        ground_to_zero = True
        _LOGGER.debug(f"set ground-to-zero to {ground_to_zero} as no parameter is given")

    # Konvertiere mögliche Stringfarben in RGB-Tupel
    line_color = normalize_color(line_color)
    bg_color = normalize_color(bg_color)                     
    _LOGGER.debug(f"colors after normalize: line-color={line_color}, background-color={bg_color}")

    # Konvertiere mögliche Line_value-Strings in Line_value-Tupel
    _LOGGER.debug(f"BEFORE CONVERT: line_values={line_values!r}, type={type(line_values)}")
    line_values = ast.literal_eval(line_values)
    _LOGGER.debug(f"AFTER CONVERT: line_values={line_values!r}, type={type(line_values)}")

    values_min = min(line_values)
    values_max = max(line_values)
    _LOGGER.debug(f"value-boundaries: min={values_min}, max={values_max}")
    if values_min == values_max:
        values_max += 1
        _LOGGER.debug(f"min and max are the same, adding 1 to max-value: {values_max}")
    if ground_to_zero is True:
        if values_min > 0:
            values_min = 0
            _LOGGER.debug(f"forced values_min to {values_min}")

    step_size = (xe - xs) / (len(line_values) - 1)
    chart_height = ye - ys
    _LOGGER.debug(f"calculated step-size to {step_size} and chart-height to {chart_height}")

    line_chart_points = []
    for idx, value in enumerate(line_values):
        px = xs + idx * step_size
        py = ye - ((value - values_min) / (values_max - values_min) * chart_height)
        line_chart_points.append((px, py))
    _LOGGER.debug(f"accumulated points: {line_chart_points}")

    # Schattenbild abholen
    img = device.get("shadow")
    draw = ImageDraw.Draw(img)
    _LOGGER.debug("fetched image from instance")

    draw.line(line_chart_points, fill=line_color, width=line_width)
    _LOGGER.debug(f"drew line chart points: {line_chart_points}")

    if mark_points is True:
        for px, py in line_chart_points:
            draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=line_color)
        _LOGGER.debug(f"marked points")

    if show_axis is True:
        draw.line((xs, ys, xs, ye), fill=axis_color)           # Y-Axis
        draw.line((xs, ye, xe, ye), fill=axis_color)           # X-Axis
        _LOGGER.debug(f"drew axis")

    await send_screen(hass, serial_number)


async def _async_update_firmware_device(hass, serial_number, firmware_version):
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(const.DOMAIN, serial_number)})

    if not device:
        return

    device_registry.async_update_device(device.id, sw_version=firmware_version)
