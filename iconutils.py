import io, asyncio
import os
import requests
from pathlib import Path
import math
import logging
from svgpathtools import parse_path
import custom_components.weact_display.const as const
from typing import Tuple, Optional, List
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)

#************************************************************************
#        L O A D  I C O N
#************************************************************************
# - loads an icon from local or web
# - caches it as SVG or BMP
# - tints the icon
# - rotates the icon
# - return the IMG as RGB888 data
#************************************************************************
# m: icon_name
# o: i_size
# o: i_color
# o: rotation
#************************************************************************
#sync def load_icon(hass, i_name: str, i_size = 32, i_color = (255, 255, 255), bg_color = (0, 0, 0), rotation = 0) -> bytes:
async def load_icon(hass, i_name: str, i_size = 32, i_color = (255, 255, 255), rotation = 0) -> bytes:
    from .commands import normalize_color, send_screen

    clean_name = f"{i_name.replace("mdi:", "").strip()}.svg"
    svg_path = const.ICON_CACHE_DIR / f"{clean_name}"

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
    if rotation not in (0, 90, 180, 270):
        raise ValueError("rotation must be one of 0, 90, 180, 270")

    _LOGGER.debug(f"looking local for icon {svg_path}")

    if not svg_path.exists():
        try:
            url = f"{const.MDI_BASE_URL}/{clean_name}"
            _LOGGER.debug(f"trying to download icon from {url}")
            response = await hass.async_add_executor_job(lambda: requests.get(url, timeout=10))
            if response.status_code == 200:
                _LOGGER.debug(f"Saving icon to {const.ICON_CACHE_DIR}/{clean_name}")
                try:
                    await asyncio.to_thread(lambda: svg_path.write_bytes(response.content))
                except Exception as e:
                    _LOGGER.error(f"error while saving the icon to {svg_path}: {e}")
            else:
                raise FileNotFoundError(f"could not find '{clean_name}' in '{const.MDI_BASE_URL}'. HTTP response code: {response.status_code})")
        except Exception as e:
            _LOGGER.error(f"error while downloading {url}: {e}")
            raise
    else:
        _LOGGER.debug(f"don't need to download anything, as {svg_path} already exists")

    _LOGGER.debug(f"icon is (now) locally available as SVG, doing some magic now")

    loop = asyncio.get_running_loop()
    def _read():
        return ET.parse(svg_path)
    tree = await loop.run_in_executor(None, _read)
    root = tree.getroot()

    # collect viewBox to scale correctly
    minx, miny, vbw, vbh = _parse_viewbox(root)

    # collect paths
    path_items = _collect_paths(root)
    if not path_items:
        return Image.new("RGBA", (i_size, i_size), (0, 0 ,0, 0))

    # compute scale to fit viewbox into size (preserve aspect)
    if vbw == 0 or vbh == 0:
        vbw, vbh = 100.0, 100.0
    scale = i_size / max(vbw, vbh)

    _LOGGER.debug(f"icon values: scale={scale}, viewbox-width={vbw}, viewbox-height={vbh}, min-x={minx}, min-y={miny}, path-items={len(path_items)}")

    # create canvas
#    img = Image.new("RGBA", (i_size, i_size), (*bg_color, 0))
    img = Image.new("RGBA", (i_size, i_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    sample_steps = 240  # mehr = glattere Kurven
    for d, fill in path_items:
        try:
            path = parse_path(d)
        except Exception as e:
            _LOGGER.error(f"exception in magic path: {e}")
            continue

        # sample points along path. We sample many points along param t ∈ [0,1]
        pts = []
        for i in range(sample_steps + 1):
            t = i / sample_steps
            try:
                p = path.point(t)
            except Exception as e:
                _LOGGER.error(f"exception in magic sample-steps: {e}")
                continue
            # convert to SVG canvas coords -> scale + translate
            x = (p.real - minx) * scale
            # SVG y direction is downwards; svgpathtools uses the same numeric coordinates,
            # so mapping directly should be okay. If icons appear vertically flipped,
            # invert: y = size - ((p.imag - miny) * scale)
            y = (p.imag - miny) * scale
            pts.append((x, y))

        # If path is closed, draw polygon, else draw polygon anyway as approximation.
        # Drop tiny segments
        if len(pts) >= 3:
            draw.polygon(pts, fill = i_color + (255,) if isinstance(i_color, tuple) else i_color)

    img = img.rotate(- rotation, resample = Image.BICUBIC, expand = False)

    return img


def _parse_viewbox(root: ET.Element) -> Tuple[float, float, float, float]:
    """
    Liefert minx, miny, width, height (viewBox) oder None-Werte, wenn nicht gesetzt.
    """
    vb = root.get("viewBox") or root.get("viewbox")
    if vb:
        parts = [float(x) for x in vb.strip().split()]
        if len(parts) == 4:
            return parts[0], parts[1], parts[2], parts[3]
    # Fallback: versuche width/height attributes
    w = root.get("width")
    h = root.get("height")
    try:
        return 0.0, 0.0, float(w) if w else 100.0, float(h) if h else 100.0
    except Exception:
        return 0.0, 0.0, 100.0, 100.0


def _collect_paths(root: ET.Element) -> List[Tuple[str, Optional[str]]]:
    """
    Liefert Liste von (d-string, fill-color) für alle <path> Elemente.
    Nur `d` und `fill` werden beachtet.
    """
    paths = []
    # Entferne Namespaces: arbeite mit lokalen Namen
    for elem in root.iter():
        # normalize tag (strip namespace)
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    for p in root.iter("path"):
        d = p.get("d")
        fill = p.get("fill")
        if d:
            paths.append((d, fill))
    return paths


def _color_from_svg_(fill: Optional[str], default=(255, 255, 255)) -> Tuple[int, int, int]:
    """
    einfache hex / rgb parser. Wenn fehlend, default zurückgeben.
    Unterstützt z.B. "#fff", "#ffffff", "rgb(255,0,0)" oder "none".
    """
    if not fill:
        return default
    s = fill.strip()
    if s.lower() == "none":
        return None
    if s.startswith("#"):
        s = s.lstrip("#")
        if len(s) == 3:
            r = int(s[0]*2, 16)
            g = int(s[1]*2, 16)
            b = int(s[2]*2, 16)
            return (r, g, b)
        elif len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    if s.startswith("rgb"):
        try:
            inside = s[s.find("(")+1:s.find(")")]
            parts = [int(x.strip()) for x in inside.split(",")]
            if len(parts) >= 3:
                return (parts[0], parts[1], parts[2])
        except Exception:
            pass
    # Fallback: versuche bekannte Farbnamen? (minimal)
    simple = {
        "white": (255,255,255),
        "black": (0,0,0)
    }
    return simple.get(s.lower(), default)


def render_svg_to_image_(svg_path: Path, size: int,
                        tint: Optional[Tuple[int,int,int]] = None,
                        rotation: int = 0) -> Image.Image:
    """
    Render a simple path-based SVG to a PIL RGBA Image of square size (size x size).
    - Only uses <path d="..."> with fill.
    - tint overrides fills (if provided).
    - rotation must be 0, 90, 180 or 270 (degrees).
    Returns: PIL.Image RGBA of dimension (size, size)
    """
    if rotation not in (0, 90, 180, 270):
        raise ValueError("rotation must be one of 0,90,180,270")

    tree = ET.parse(str(svg_path))
    root = tree.getroot()

    # collect viewBox to scale correctly
    minx, miny, vbw, vbh = _parse_viewbox(root)

    # collect paths
    path_items = _collect_paths(root)
    if not path_items:
        # fallback: return empty transparent
        return Image.new("RGBA", (size, size), (0,0,0,0))

    # compute scale to fit viewbox into size (preserve aspect)
    if vbw == 0 or vbh == 0:
        vbw, vbh = 100.0, 100.0
    scale = size / max(vbw, vbh)

    # create canvas
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)

    sample_steps = 240  # mehr = glattere Kurven

    for d, fill in path_items:
        try:
            path = parse_path(d)
        except Exception:
            # falls parse fehlschlägt, skip
            continue

        # determine fill color (None => transparent)
        if tint:
            color = tint
        else:
            color = _color_from_svg(fill, default=(255,255,255))
        if color is None:
            continue

        # sample points along path. We sample many points along param t ∈ [0,1]
        pts = []
        for i in range(sample_steps + 1):
            t = i / sample_steps
            try:
                p = path.point(t)
            except Exception:
                # fallback: skip
                continue
            # convert to SVG canvas coords -> scale + translate
            x = (p.real - minx) * scale
            # SVG y direction is downwards; svgpathtools uses the same numeric coordinates,
            # so mapping directly should be okay. If icons appear vertically flipped,
            # invert: y = size - ((p.imag - miny) * scale)
            y = (p.imag - miny) * scale
            pts.append((x, y))

        # If path is closed, draw polygon, else draw polygon anyway as approximation.
        # Drop tiny segments
        if len(pts) >= 3:
            draw.polygon(pts, fill=color+(255,) if isinstance(color, tuple) else color)

    # rotation: Pillow rotates counter-clockwise; we want rotation as visual clockwise
    if rotation and rotation != 0:
        # convert to negative angle for clockwise rotation
        angle = rotation % 360
        # rotate around center; expand=False to keep size
        img = img.rotate(-angle, resample=Image.BICUBIC, expand=False)

    return img


def load_icon_from_cache_or_raise_(name: str) -> Path:
    """
    Liefert den Pfad zum gecachten SVG (falls vorhanden), sonst raises FileNotFoundError.
    """
#    p = SVG_CACHE_DIR / f"{name}.svg"
    p = const.ICON_PATH / f"{name}.svg"
    if not p.exists():
        raise FileNotFoundError(f"SVG not found in cache: {p}")
    return p


def render_icon_(name: str,
                size: int,
                tint: Optional[Tuple[int,int,int]] = None,
                rotation: int = 0) -> Image.Image:
    """
    High-level: aus dem gecachten SVG (name.svg) ein PIL Image rendern.
    (Es cached *nur* das SVG, nicht das gerenderte Bitmap.)
    """
    svg_path = load_icon_from_cache_or_raise(name)
    return render_svg_to_image(svg_path, size=size, tint=tint, rotation=rotation)


def paste_icon_onto_shadow_(shadow_img: Image.Image,
                           icon_img: Image.Image,
                           x: int, y: int):
    """
    Paste icon_img (RGBA) onto shadow_img (RGB or RGBA) at (x,y) using alpha mask.
    """
    if shadow_img.mode != "RGBA":
        base = shadow_img.convert("RGBA")
    else:
        base = shadow_img

    base.paste(icon_img, (x, y), icon_img)
    return base.convert(shadow_img.mode)

