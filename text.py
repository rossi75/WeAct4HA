from PIL import Image, ImageDraw, ImageFont
import io, struct, os, random

def text_to_bitmap_bytes(
    text,
    width=160,
    height=80,
    color=(255, 255, 255),
    bgcolor=(0, 0, 0),
    align="left",
    font_size=16,
    font=None
):
    """Erzeuge Bitmap aus Text für das Display (RGB565)."""
    img = Image.new("RGB", (width, height), bgcolor)
    draw = ImageDraw.Draw(img)

    # Schrift laden
    try:
        if font and os.path.exists(font):
            fnt = ImageFont.truetype(font, font_size)
        else:
            fnt = ImageFont.load_default()
    except Exception:
        fnt = ImageFont.load_default()

    # Textgröße berechnen
    lines = text.splitlines() or [text]
    line_heights = []
    max_width = 0
    for line in lines:
        w, h = draw.textsize(line, font=fnt)
        line_heights.append(h)
        max_width = max(max_width, w)

    total_height = sum(line_heights)
    y = (height - total_height) // 2 if align == "center" else 0

    for i, line in enumerate(lines):
        w, h = draw.textsize(line, font=fnt)
        if align == "right":
            x = width - w
        elif align == "center":
            x = (width - w) // 2
        else:
            x = 0
        draw.text((x, y), line, font=fnt, fill=color)
        y += h

    # RGB → RGB565
    pixels = img.getdata()
    buf = bytearray()
    for r, g, b in pixels:
        r >>= 3
        g >>= 2
        b >>= 3
        rgb565 = ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F)
        buf += struct.pack("<H", rgb565)
    return bytes(buf)
