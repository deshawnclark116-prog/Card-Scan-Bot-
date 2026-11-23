"""Pair filename-tagged Canon scans without guessing front/back ordering."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Iterable

SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
PATTERN = re.compile(r"^(?P<id>.+?)[ _.-](?P<side>front|back|f|b)$", re.I)


def pair_scans(paths: Iterable[str | Path]) -> tuple[dict[str, dict[str, Path]], list[str]]:
    grouped: dict[str, dict[str, Path]] = defaultdict(dict)
    skipped: list[str] = []
    for raw in sorted(map(Path, paths), key=lambda p: str(p)):
        if raw.suffix.casefold() not in SUFFIXES:
            continue
        match = PATTERN.fullmatch(raw.stem)
        if not match:
            skipped.append(f"{raw.name}: expected *_front / *_back")
            continue
        side = "front" if match["side"].casefold() in ("front", "f") else "back"
        key = match["id"].casefold()
        if side in grouped[key]:
            skipped.append(f"{raw.name}: duplicate {side} for {key}")
            continue
        grouped[key][side] = raw
    pairs = {key: group for key, group in grouped.items() if set(group) == {"front", "back"}}
    for key, group in grouped.items():
        if key not in pairs:
            skipped.append(f"{key}: missing {'back' if 'front' in group else 'front'}")
    return pairs, skipped
