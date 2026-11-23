"""Local desktop/synced-folder processor. A cloud server cannot watch Android folders."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import time

from .batch import pair_scans
from .crop import crop_card, open_scan
from .identity import CardIdentity, identify_card
from .pricing import estimate_price, load_comps
from .flyer import make_flyer


def safe_name(value: str) -> str:
    return (re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "card")[:100]


def process_folder(scan_dir: Path, out_dir: Path, comps: list[dict], *, vision: bool = False) -> tuple[int, list[str]]:
    pairs, skipped = pair_scans(scan_dir.iterdir())
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for key, group in pairs.items():
        card_dir = out_dir / safe_name(key)
        marker = card_dir / "result.json"
        fingerprint = {side: {"mtime_ns": path.stat().st_mtime_ns, "size": path.stat().st_size}
                       for side, path in group.items()}
        if any(time.time() - path.stat().st_mtime < 4 for path in group.values()):
            skipped.append(f"{key}: waiting for scans to finish writing")
            continue
        if marker.exists():
            try:
                if json.loads(marker.read_text()).get("input_fingerprint") == fingerprint:
                    continue
            except (ValueError, OSError):
                pass
        try:
            front = crop_card(open_scan(group["front"].read_bytes()))
            back = crop_card(open_scan(group["back"].read_bytes()))
            identity = CardIdentity()
            if vision:
                identity = identify_card(front.image, back.image)
            estimate = estimate_price(identity, comps)
            card_dir.mkdir(parents=True, exist_ok=True)
            front.image.save(card_dir / "front.png")
            back.image.save(card_dir / "back.png")
            make_flyer(front.image, back.image, identity, estimate).save(card_dir / "flyer.png")
            marker.write_text(json.dumps({
                "input_fingerprint": fingerprint,
                "processed_at": datetime.now().isoformat(),
                "identity": identity.to_dict(),
                "price": estimate.__dict__,
                "front_crop": {"needs_review": front.needs_review, "reason": front.reason},
                "back_crop": {"needs_review": back.needs_review, "reason": back.reason},
                "note": "Unverified identity requires user confirmation before price is available",
            }, indent=2))
            count += 1
        except Exception as exc:
            skipped.append(f"{key}: {type(exc).__name__}: {exc}")
    return count, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Canon flatbed card scans")
    parser.add_argument("--in", dest="scan_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, default=Path("output"))
    parser.add_argument("--comps", type=Path)
    parser.add_argument("--vision", action="store_true", help="Use paid vision API (needs OPENAI_API_KEY)")
    parser.add_argument("--watch", action="store_true", help="Poll local/synced folder every 8 seconds")
    args = parser.parse_args()
    if not args.scan_dir.is_dir():
        parser.error("--in must be an existing folder")
    comps = load_comps(args.comps.read_text(encoding="utf-8-sig")) if args.comps else []
    while True:
        count, skipped = process_folder(args.scan_dir, args.out_dir, comps, vision=args.vision)
        print(f"Processed {count} new/changed card pairs")
        for note in skipped:
            print(" -", note)
        if not args.watch:
            break
        time.sleep(8)


if __name__ == "__main__":
    main()
