"""Sold-comps-only valuation with exact matching, provenance and abstention."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from statistics import median
import re
from typing import Optional

from .identity import CardIdentity


COMP_COLUMNS = [
    "category", "subject", "year", "manufacturer", "set_name", "card_number",
    "parallel", "serial_number", "grade", "sale_type", "sold_date", "price",
    "shipping", "source_url",
]


@dataclass
class PriceEstimate:
    suggested: Optional[float]
    low: Optional[float]
    high: Optional[float]
    samples: int
    status: str
    sources: list[str]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _print_run(value: str) -> str:
    match = re.search(r"\b\d+\s*/\s*(\d+)\b", str(value or ""))
    return match.group(1) if match else _norm(value)


def load_comps(text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(text.lstrip("\ufeff")))
    missing = set(COMP_COLUMNS) - set(reader.fieldnames or [])
    if missing:
        raise ValueError("Sold comps CSV missing columns: " + ", ".join(sorted(missing)))
    return list(reader)


def estimate_price(identity: CardIdentity, comps: list[dict], *, today: Optional[date] = None,
                   min_samples: int = 3, max_age_days: int = 180) -> PriceEstimate:
    if not identity.complete_for_pricing:
        return PriceEstimate(None, None, None, 0,
                             "Exact card identity must be manually verified before pricing", [])
    today = today or date.today()
    prices: list[float] = []
    sources: list[str] = []
    for row in comps:
        if _norm(row.get("sale_type", "")) != "sold":
            continue
        source = (row.get("source_url") or "").strip()
        if not source.startswith(("https://", "http://")):
            continue
        try:
            sold_on = date.fromisoformat(str(row.get("sold_date", "")))
            value = float(row.get("price") or 0) + float(row.get("shipping") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if not 0 <= (today - sold_on).days <= max_age_days or value <= 0:
            continue
        matching = [
            "category", "subject", "year", "manufacturer", "set_name",
            "card_number", "parallel", "grade",
        ]
        if any(_norm(row.get(field, "")) != _norm(getattr(identity, field)) for field in matching):
            continue
        if _print_run(row.get("serial_number", "")) != _print_run(identity.serial_number):
            continue
        prices.append(value)
        sources.append(source)
    if len(prices) < min_samples:
        return PriceEstimate(None, None, None, len(prices),
                             f"Insufficient verified exact sold comps ({len(prices)}/{min_samples})", sources)
    ordered = sorted(prices)

    def percentile(p: float) -> float:
        pos = (len(ordered) - 1) * p
        lo = int(pos)
        hi = min(len(ordered) - 1, lo + 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

    return PriceEstimate(
        round(median(prices), 2), round(percentile(.25), 2),
        round(percentile(.75), 2), len(prices),
        f"Based on {len(prices)} exact sold comps from last {max_age_days} days (price + shipping)",
        sources,
    )
