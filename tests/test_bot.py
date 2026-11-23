import unittest
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from cardbot.crop import crop_card
from cardbot.batch import pair_scans
from cardbot.identity import CardIdentity
from cardbot.pricing import estimate_price, load_comps
from cardbot.flyer import make_flyer, png_bytes


class BotTests(unittest.TestCase):
    def test_crop_colored_card(self):
        im = Image.new("RGB", (900, 1200), "white")
        draw = ImageDraw.Draw(im)
        draw.rectangle((190, 210, 710, 940), fill=(45, 95, 150))
        result = crop_card(im)
        self.assertLess(result.image.width, result.image.height)
        self.assertGreater(result.confidence, .70)
        self.assertTrue(490 <= result.image.width <= 550)
        self.assertTrue(695 <= result.image.height <= 765)

    def test_uncertain_crop_does_not_throw_away_image(self):
        im = Image.new("RGB", (900, 1200), "white")
        result = crop_card(im)
        self.assertTrue(result.needs_review)
        self.assertEqual(result.image.size, im.size)

    def test_pairs_are_explicit_not_guessed(self):
        pairs, skipped = pair_scans([Path("001_front.jpg"), Path("001_back.png"), Path("orphan_front.jpg")])
        self.assertIn("001", pairs)
        self.assertEqual(len(pairs), 1)
        self.assertTrue(any("orphan" in s for s in skipped))

    def test_price_abstains_until_verified(self):
        ident = CardIdentity(category="sports", subject="Example", year="2025",
                             manufacturer="Topps", set_name="Chrome", card_number="1",
                             parallel="Refractor", grade="raw")
        self.assertIsNone(estimate_price(ident, []).suggested)

    def test_exact_matching_and_sold_only(self):
        ident = CardIdentity(category="sports", subject="Example", year="2025",
                             manufacturer="Topps", set_name="Chrome", card_number="1",
                             parallel="Gold", serial_number="23/50", grade="raw",
                             confidence="verified")
        rows = []
        for i, price in enumerate([20, 30, 40]):
            rows.append(dict(category="sports", subject="Example", year="2025",
                            manufacturer="Topps", set_name="Chrome", card_number="1",
                            parallel="Gold", serial_number=f"{i+1}/50", grade="raw",
                            sale_type="sold", sold_date="2026-11-01", price=price,
                            shipping=5, source_url=f"https://example.org/sale/{i}"))
        rows.extend([
            dict(rows[0], parallel="Base", price=10000),
            dict(rows[0], sale_type="active", price=10000),
            dict(rows[0], serial_number="3/99", price=10000),
        ])
        estimated = estimate_price(ident, rows, today=date(2026, 11, 23))
        self.assertEqual(estimated.suggested, 35)
        self.assertEqual(estimated.samples, 3)
        self.assertEqual(estimated.low, 30)
        self.assertEqual(estimated.high, 40)

    def test_flyer_without_price(self):
        front = Image.new("RGB", (500, 700), "blue")
        back = Image.new("RGB", (500, 700), "red")
        p = estimate_price(CardIdentity(), [])
        image = make_flyer(front, back, CardIdentity(), p)
        self.assertEqual(image.size, (1200, 1500))
        self.assertTrue(png_bytes(image).startswith(b"\x89PNG"))

    def test_csv_validation(self):
        with self.assertRaises(ValueError):
            load_comps("price,sold_date\n15,2026-11-01\n")


if __name__ == "__main__":
    unittest.main()
