from __future__ import annotations
import io, asyncio
import os
import requests
from pathlib import Path
import math
import logging
from svgpathtools import parse_path
import custom_components.weact_display.const as const
from typing import Tuple, Optional, List, Dict
import xml.etree.ElementTree as ET
from picosvg.svg import SVG
from PIL import Image, ImageDraw, ImageChops

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
async def load_icon(hass, i_name: str, i_size = 32, i_color = (255, 255, 255), rotation = 0) -> bytes:
    from .commands import normalize_color, send_screen

    clean_name = f"{i_name.replace("mdi:", "").strip()}.svg"
    svg_path = const.ICON_CACHE_DIR / f"{clean_name}"

    if i_color is None:
        i_color = (255, 255, 255)
        _LOGGER.debug(f"set icon-color to {i_color} as no parameter is given")
    else:
        i_color = normalize_color(i_color)
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

    # logrotate
    max_files = const.MAX_SVG_FILES
    try:
        files = await hass.async_add_executor_job(
            lambda: [
                os.path.join(const.ICON_CACHE_DIR, f)
                for f in os.listdir(const.ICON_CACHE_DIR)
                if f.lower().endswith(".svg")
                and os.path.isfile(os.path.join(const.ICON_CACHE_DIR, f))
            ]
        )

        _LOGGER.debug(f"found {len(files)} files in {const.ICON_CACHE_DIR}/")

        files.sort(key=os.path.getmtime)        # nach Änderungszeit sortieren (älteste zuerst)
        files_to_delete = files[:-max_files]        # alles außer den letzten x löschen

        _LOGGER.debug(f"deleting {len(files_to_delete)} files in {const.ICON_CACHE_DIR}/")

        for f in files_to_delete:
            try:
                os.remove(f)
            except Exception as e:
                _LOGGER.warning(f"Could not delete old debug file {f}: {e}")
    except Exception as e:
        _LOGGER.error(f"Cleanup error in debug dir: {e}")

    _LOGGER.debug("icon is (now) locally available as SVG, doing some magic now")

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
        return Image.new("RGBA", (i_size, i_size), (0, 0, 0, 0))

    # compute scale to fit viewbox into size (preserve aspect)
    if vbw == 0 or vbh == 0:
        vbw, vbh = 100.0, 100.0
    scale = i_size / max(vbw, vbh)
    dx = (i_size - vbw * scale) / 2
    dy = (i_size - vbh * scale) / 2
    sample_steps = i_size * 2  # mehr = glattere Kurven

    _LOGGER.debug(f"icon values: scale={scale}, viewbox-width={vbw}, viewbox-height={vbh}, min-x={minx}, min-y={miny}, path-items={len(path_items)}, dx={dx}, dy={dy}, sample-steps={sample_steps}")

    # final alpha mask
    final_mask = Image.new("L", (i_size, i_size), 0)

    # create canvas
    img = Image.new("RGBA", (i_size, i_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for d, fill, fillrule in path_items:
        try:
            path = parse_path(d)
        except Exception as e:
            _LOGGER.error(f"exception in magic path: {e}")
            continue

    subpaths = path.continuous_subpaths()

    if fillrule == "evenodd":
        # XOR-combine subpaths
        path_mask = Image.new("L", (i_size, i_size), 0)

        for sub in subpaths:
            pts = []

            for i in range(sample_steps + 1):
                t = i / sample_steps
                try:
                    p = path.point(t)
                except Exception as e:
                    _LOGGER.error(f"exception in magic sample-steps: {e}")
                    continue
                x = (p.real - minx) * scale + dx
                y = (p.imag - miny) * scale + dy
                pts.append((x, y))

            if len(pts) >= 3:
                tmp = Image.new("L", (i_size, i_size), 0)
                ImageDraw.Draw(tmp).polygon(pts, fill=255)
                path_mask = ImageChops.logical_xor(path_mask, tmp)

        final_mask = ImageChops.logical_or(final_mask, path_mask)

    else:
        # nonzero → simple OR (sufficient for MDI icons)
        path_mask = Image.new("L", (i_size, i_size), 0)
        draw = ImageDraw.Draw(path_mask)

        for sub in subpaths:
            pts = []
            for i in range(sample_steps + 1):
                t = i / sample_steps
                p = sub.point(t)
                x = (p.real - minx) * scale + dx
                y = (p.imag - miny) * scale + dy
                pts.append((x, y))

            if len(pts) >= 3:
                draw.polygon(pts, fill=255)

        final_mask = ImageChops.lighter(final_mask, path_mask)

    # colorize
    img = Image.new("RGBA", (i_size, i_size), i_color + (255,))
    img.putalpha(final_mask)
    img = img.rotate(- rotation, resample = Image.BICUBIC, expand = False)
    data = img.tobytes()
    pil = Image.frombytes("RGBA", (i_size, i_size), data)

    return pil


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


def _collect_paths(root):
    items = []
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    for p in root.iter("path"):
        d = p.get("d")
        if not d:
            continue
        fill = p.get("fill")
        fillrule = p.get("fill-rule", "nonzero").lower()
        items.append((d, fill, fillrule))

    return items
