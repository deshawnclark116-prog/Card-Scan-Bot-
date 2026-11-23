"""Optional vision model card identification; never manufacture certainty."""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, fields
from io import BytesIO
import json
import os
from typing import Optional

from PIL import Image


@dataclass
class CardIdentity:
    category: str = ""
    subject: str = ""
    year: str = ""
    manufacturer: str = ""
    set_name: str = ""
    card_number: str = ""
    parallel: str = ""
    serial_number: str = ""
    grade: str = "raw"
    confidence: str = "unverified"
    notes: str = ""

    @property
    def title(self) -> str:
        pieces = [self.year, self.manufacturer, self.set_name, self.subject]
        title = " ".join(x.strip() for x in pieces if x.strip()) or "Unidentified trading card"
        if self.card_number:
            title += f" #{self.card_number}"
        if self.parallel:
            title += f" — {self.parallel}"
        if self.serial_number:
            title += f" ({self.serial_number})"
        if self.grade and self.grade.casefold() != "raw":
            title += f" | {self.grade}"
        return title

    @property
    def complete_for_pricing(self) -> bool:
        return all([
            self.category.strip(), self.subject.strip(), self.year.strip(),
            self.manufacturer.strip(), self.set_name.strip(), self.card_number.strip(),
        ]) and self.confidence == "verified"

    def to_dict(self) -> dict:
        return asdict(self)


def _image_data_url(image: Image.Image) -> str:
    fitted = image.copy()
    fitted.thumbnail((1600, 1600))
    buf = BytesIO()
    fitted.save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def identify_card(front: Image.Image, back: Image.Image, *, api_key: Optional[str] = None,
                  model: Optional[str] = None) -> CardIdentity:
    """Use front AND back; output unverified until user confirms exact attributes."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No OPENAI_API_KEY configured. Enter card details manually.")
    from openai import OpenAI
    client = OpenAI(api_key=key, timeout=45.0, max_retries=1)
    prompt = (
        "Analyze these TWO images of the SAME collectible card: first front, then back. "
        "Return one JSON object ONLY with these string fields: category (sports/tcg/non-sports), "
        "subject, year, manufacturer, set_name, card_number, parallel, serial_number, grade, "
        "confidence, notes. Use empty string for unknown. Do not guess unobservable details. "
        "Serial number must preserve X/Y exactly when visible. Distinguish print runs, "
        "base, refractors, autos and other parallels. Never infer grade from raw condition; "
        "set grade to raw unless a clearly visible legitimate grading slab label is readable. "
        "confidence must be one of high/medium/low, reflecting visual identification only, "
        "not price validation. Explain ambiguity in notes."
    )
    response = client.chat.completions.create(
        model=model or os.environ.get("CARD_SCAN_VISION_MODEL", "gpt-4.1-mini"),
        response_format={"type": "json_object"}, temperature=0,
        messages=[
            {"role": "system", "content": "You are an extremely careful trading card cataloging assistant. Return valid JSON only."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _image_data_url(front), "detail": "high"}},
                {"type": "image_url", "image_url": {"url": _image_data_url(back), "detail": "high"}},
            ]},
        ],
    )
    parsed = json.loads(response.choices[0].message.content or "{}")
    allowed = {f.name for f in fields(CardIdentity)}
    result = CardIdentity(**{k: str(v or "") for k, v in parsed.items() if k in allowed})
    original_confidence = result.confidence
    result.confidence = "unverified"
    result.notes = f"Vision confidence: {original_confidence}. {result.notes}".strip()
    return result
