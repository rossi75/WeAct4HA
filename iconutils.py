import io
import os
import requests
from pathlib import Path
from typing import Tuple
#from PIL import Image, ImageOps
from PIL import Image, ImageOps, ImageColor, ImageEnhance
#import cairosvg
import logging
#from svglib.svglib import svg2rlg
#from reportlab.graphics import renderPM

_LOGGER = logging.getLogger(__name__)

# Lokaler Cache-Ordner für heruntergeladene SVGs
ICON_CACHE_DIR = Path(__file__).parent / "icons"
ICON_CACHE_DIR.mkdir(exist_ok=True)

# Basis-URL der offiziellen Material Design Icons
MDI_BASE_URL = "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg"


def _ensure_icon_available(icon_name: str) -> Path:
    """
    Stellt sicher, dass das gewünschte mdi:-Icon als SVG-Datei lokal verfügbar ist.
    Lädt es automatisch herunter, falls es nicht existiert.
    """
    clean_name = icon_name.replace("mdi:", "").strip()
    local_svg = ICON_CACHE_DIR / f"{clean_name}.svg"

    if not local_svg.exists():
        try:
            _LOGGER.info(f"[ICON] Lade {icon_name} von GitHub...")
            download_mdi_icon(clean_name, local_svg)
        except Exception as e:
            _LOGGER.error(f"[ICON] Fehler beim Laden von {icon_name}: {e}")
            raise

    return local_svg


async def download_mdi_icon(icon_name: str, save_path: Path):
    """Lädt ein SVG aus dem offiziellen MaterialDesignIcons-Repository."""
    url = f"{MDI_BASE_URL}/{icon_name}.svg"
    _LOGGER.debug(f"loading from {url}")
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        save_path.write_bytes(response.content)
        _LOGGER.info(f"[ICON] {icon_name}.svg gespeichert unter {save_path}")
    else:
        raise FileNotFoundError(f"could not find '{icon_name}' in '{MDI_BASE_URL}'. HTTP response code: {response.status_code})")


def _svg_to_image(svg_path: Path, size: Tuple[int, int] = (64, 64)) -> Image.Image:
    """
    Konvertiert ein SVG in ein Pillow-Image (RGB).
    Standardgröße: 64x64 Pixel (anpassbar).
    """
    png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=size[0], output_height=size[1])
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return img


def _image_to_rgb888_bytes(img: Image.Image) -> bytes:
    """
    Gibt die Bilddaten als RGB888-Bytefolge zurück (für das Display).
    """
    return img.tobytes()


def _tint_image(img: Image.Image, color: Tuple[int, int, int]) -> Image.Image:
    """
    Färbt ein Icon ein, indem die Helligkeit des Originals mit der neuen Farbe kombiniert wird.
    """
    r, g, b = color
    _LOGGER.debug(f"[ICON] Färbe Icon mit Farbe {color}")
    color_layer = Image.new("RGB", img.size, (r, g, b))
    img_gray = ImageOps.grayscale(img)
    tinted = Image.composite(color_layer, img, img_gray)
    return tinted


#def load_icon_as_rgb888(icon_name: str, color: Tuple[int, int, int] = (255, 255, 255), size: Tuple[int, int] = (64, 64)) -> bytes:
#async def load_icon_as_rgb888(icon_name: str, color = (255, 255, 255), size = (32), rotation = 0) -> bytes:
async def load_icon(icon_name: str, icon_color = (255, 255, 255), icon_size = (32), bg_color = (0, 0, 0), rotation = 0) -> bytes:
    """
    High-Level-Funktion:
    Lädt ein Icon (mdi:...), cached es, färbt es ein und gibt RGB888-Daten zurück.
    """
#    svg_path = ensure_icon_available(icon_name)
    clean_name = icon_name.replace("mdi:", "").strip()
    local_svg = ICON_CACHE_DIR / f"{clean_name}.svg"

    if not local_svg.exists():
        try:
            _LOGGER.debug(f"need to download icon '{icon_name}' from GitHub...")
            await download_mdi_icon(clean_name, local_svg)
        except Exception as e:
            _LOGGER.error(f"error while downloading {icon_name}: {e}")
            raise

#    return local_svg

#def svg_to_rgb_bytes(svg_path: str, size=(32, 32)) -> bytes:
#    drawing = svg2rlg(svg_path)
#    png_io = io.BytesIO()
#    renderPM.drawToFile(drawing, png_io, fmt="PNG")
#    img = Image.open(io.BytesIO(png_io.getvalue())).convert("RGB")
#    img = img.resize(size)
#    img = img.rotate(rotation)
#    return img.tobytes()


#    img = Image.open(io.BytesIO(png_io.getvalue())).convert("RGB")
#    img = Image.open(io.BytesIO(png_io.getvalue())).convert("RGBA")

    try:
        img = Image.open(io.BytesIO(local_svg.getvalue())).convert("RGBA")
        _LOGGER.debug("loaded from SVG")
    except Exception as e:
        img = Image.new("RGBA", (icon_size, icon_size), (255, 255, 255, 0))
        _LOGGER.error(f"error while loading {icon_name}: {e}")

    _LOGGER.debug("SVG -> PNG")


    _LOGGER.debug("PNG -> IMG")

    img = img.resize(icon_size)
    _LOGGER.debug("resized")

    tinted = tinted.rotate(rotation, expand=True)
    img = img.rotate(rotation, expand=True)
    _LOGGER.debug("rotated")

    # --- Einfärben ---
    # Transparente Flächen als Maske nutzen
    mask = img.split()[-1]  # Alpha-Kanal als Maske
    color_layer = Image.new("RGBA", img.size, icon_color + (255,))
    _LOGGER.debug("made anything with Alpha (do not understand what!)")

    # Nur dort einfärben, wo das Icon nicht transparent ist
    tinted = Image.composite(color_layer, Image.new("RGBA", img.size, (0, 0, 0, 0)), mask)
    _LOGGER.debug("tinted Alpha")


    # --- Hintergrundfarbe hinzufügen ---
    bg = Image.new("RGBA", tinted.size, bg_color + (255,))
    _LOGGER.debug("new background")

    bg.paste(tinted, (0, 0), tinted)
    _LOGGER.debug("merged background + tinted")
#    return img.tobytes()

#    img = svg_to_image(svg_path, size=size)
    #img = svg_to_image(local_svg, size = size)
#    png_bytes = cairosvg.svg2png(url = str(svg_path), output_width = size[0], output_height=size[1])
#    png_bytes = cairosvg.svg2png(url = str(svg_path), output_width = size, output_height=size)
#    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
#    return img

#    svg_data = svg_data.replace('fill="currentColor"', f'fill="{icon_color}"')                  # Farbe ersetzen (im SVG alle fill="" Attribute anpassen)
#    _LOGGER.debug("changed icon color to {icon_color}")
#    png_bytes = cairosvg.svg2png(bytestring=svg_data, output_width=size, output_height=size)      # Mit CairoSVG in PNG rendern (als Bytes)
#    _LOGGER.debug("loaded from PNG")

#    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")                      # In PIL laden
#    _LOGGER.debug("converted to IMG")

#    r, g, b = icon_color
#    color_layer = Image.new("RGB", img.size, (r, g, b))
#    img_gray = ImageOps.grayscale(img)
#    tinted = Image.composite(color_layer, img, img_gray)
#    img = Image.composite(color_layer, img, img_gray)
#    _LOGGER.debug(f"tinted with {icon_color}")

#    bg = Image.new("RGB", img.size, bg_color)                                   # Hintergrundfarbe anwenden
#    _LOGGER.debug("created new background image")
#    bg.paste(img, mask=None)
#    _LOGGER.debug("pasted IMG into background image")
#    rgb_data = bg.tobytes()  # → R, G, B Bytefolge (RGB888)                     # RGB888 Bytes extrahieren



#    img = img.rotate(rotation)
#    tinted = tinted.rotate(rotation)
#    _LOGGER.debug(f"rotated {rotation} degrees")

#    bg = Image.new("RGB", img.size, bg_color)                                   # Hintergrundfarbe anwenden
#    bg = Image.new("RGB", tinted.size, bg_color)                                   # Hintergrundfarbe anwenden
#    _LOGGER.debug("created new background image")

#    bg.paste(img, mask=None)
#    bg.paste(tinted, mask=None)
#    _LOGGER.debug("pasted IMG into background image")

    rgb_data = bg.tobytes()  # → R, G, B Bytefolge (RGB888)                     # RGB888 Bytes extrahieren

#    img = tint_image(img, color)
#    r, g, b = color
#    _LOGGER.debug(f"[ICON] Färbe Icon mit Farbe {color}")
#    color_layer = Image.new("RGB", img.size, (r, g, b))
#    img_gray = ImageOps.grayscale(img)
#    tinted = Image.composite(color_layer, img, img_gray)
#    return tinted

#    data = image_to_rgb888_bytes(img)

    _LOGGER.debug(f"generated {len(rgb_data)} bytes in RGB888 for {icon_name}")

    return rgb_data
