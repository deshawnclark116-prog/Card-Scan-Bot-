"""Create shareable 1200x1500 card sales images with no invented grades/prices."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .identity import CardIdentity
from .pricing import PriceEstimate


NAVY = (20, 31, 52)
BLUE = (49, 112, 205)
GRAY = (99, 111, 131)


def _font(size: int, bold: bool = False):
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _contain(canvas: Image.Image, image: Image.Image, rect: tuple[int, int, int, int]):
    x, y, w, h = rect
    thumb = ImageOps.contain(image.convert("RGB"), (w, h), Image.Resampling.LANCZOS)
    canvas.paste(thumb, (x + (w - thumb.width) // 2, y + (h - thumb.height) // 2))


def make_flyer(front: Image.Image, back: Image.Image, identity: CardIdentity,
               estimate: PriceEstimate, *, asking_price: Optional[float] = None,
               seller_line: str = "Message me if interested") -> Image.Image:
    if asking_price is not None and asking_price <= 0:
        raise ValueError("Asking price must be positive")
    image = Image.new("RGB", (1200, 1500), (247, 249, 252))
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 1200, 158), fill=NAVY)
    d.text((65, 37), "AVAILABLE CARD", font=_font(54, True), fill="white")
    d.text((65, 105), "Front + back scans  |  Personal collection", font=_font(26), fill=(192, 204, 223))
    d.rounded_rectangle((56, 188, 1144, 1025), radius=26, fill="white")
    d.rectangle((91, 225, 814, 978), outline=(225, 230, 239), width=3)
    d.rectangle((848, 510, 1109, 874), outline=(225, 230, 239), width=3)
    _contain(image, front, (100, 234, 704, 735))
    _contain(image, back, (856, 520, 245, 346))
    d.text((878, 895), "CARD BACK", fill=GRAY, font=_font(19, True))

    words = identity.title.split()
    lines = []
    line = ""
    font = _font(34, True)
    for word in words:
        next_line = (line + " " + word).strip()
        if d.textlength(next_line, font=font) > 1055 and line:
            lines.append(line)
            line = word
        else:
            line = next_line
    if line:
        lines.append(line)
    for idx, line in enumerate(lines[:2]):
        d.text((66, 1049 + idx * 46), line, font=font, fill=NAVY)
    if len(lines) > 2:
        d.text((66, 1145), "Title shortened — verify exact card in listing",
               font=_font(18), fill=GRAY)
    if asking_price is not None:
        price_text = f"ASKING  ${asking_price:,.2f}"
    elif estimate.suggested is not None:
        price_text = f"SUGGESTED  ${estimate.suggested:,.2f}"
    else:
        price_text = "PRICE ON REQUEST"
    d.text((66, 1182), price_text, font=_font(53, True), fill=BLUE)
    if estimate.suggested is not None:
        d.text((68, 1256), f"Sold comps: ${estimate.low:,.2f}–${estimate.high:,.2f}   |   n={estimate.samples}",
               font=_font(24), fill=GRAY)
    else:
        d.text((68, 1256), "No verified comparable-sales price available", font=_font(22), fill=GRAY)
    d.line((66, 1335, 1130, 1335), fill=(223, 229, 238), width=3)
    seller_line = seller_line.strip()[:75] or "Message me if interested"
    d.text((68, 1361), seller_line, font=_font(30, True), fill=NAVY)
    d.text((68, 1428), "Raw cards are not professionally graded. Confirm condition before purchasing.",
           font=_font(17), fill=GRAY)
    return image


def png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
