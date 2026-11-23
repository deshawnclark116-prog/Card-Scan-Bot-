# Card Scan Bot — Canon scans → cropped card → price → sale flyer

**Personal-use prototype.** Take front and back scans with a Canon printer, save them to your Android phone or a synced desktop folder, then create clean shareable sale images. Supports sports cards, Pokémon/TCG cards and non-sports cards. No public marketplace or payment processing needed.

## What works in v0.1

- 📲 **Phone-friendly upload** of the front and back from your Files app using a Streamlit webpage.
- ✂️ **Background-aware auto-crop** on flatbed scans, with review flags and non-destructive fallback when edges are uncertain.
- 🔍 **Optional AI identification** using both sides via the OpenAI API; *all AI results are unverified drafts* until checked by a human.
- 💵 **Sold comps only:** imports CSV records with source URL, sale date, exact set/card/parallel/grade/print-run matching, and minimum 3 recent transactions. Does **not** claim live sold data access or fabricate prices.
- 🖼️ **1200×1500 PNG sale flyer**, plus cropped front/back and batch ZIP exports.
- 📁 **Desktop/synced-folder CLI watcher** using explicit filename pairing. Never guesses that adjacent scans belong together.
- ✅ Automated regression tests and GitHub Actions.

**Not yet built:** direct access to Canon's private Android folder from a remote server, true live sold-comps acquisition, automatic grade/condition guarantees, marketplace auto-posting, cloud inventory or seller payouts. If no validated comparable sales exist, the flyer says **Price on request** unless you manually set an asking price.

## Quick start on a computer

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed in the terminal. In **Single card → flyer**, upload front and back scans from your phone or computer. You can enter card details yourself and set an asking price without any API key. Download the generated PNG and share it to Facebook/Messenger.

### Using your Android phone

A website **cannot silently read or monitor a local phone folder** for privacy/security reasons. The initial workflow is: Canon printer → file saved in phone's Files folder → select front and back in the web app → flyer download. To browse a computer-hosted app from your phone, open the computer's LAN IP and port 8501 while both devices are on the same **trusted home Wi-Fi**; launch with `streamlit run app.py --server.address 0.0.0.0`. Streamlit by itself has **no login/auth**; do not expose it unprotected on the public internet. A native Android Storage Access Framework integration could add on-device folder watching later.

### Optional AI identifier

Set `OPENAI_API_KEY` in your environment (or a deployment secret) before starting the app; this uses a **paid developer API**, separate from a ChatGPT subscription. `CARD_SCAN_VISION_MODEL` defaults to `gpt-4.1-mini`. Images are sent to that API **only when you explicitly request identification**. Never commit an API key or personal scan files to GitHub.

```bash
# Mac/Linux example (run in the same terminal as streamlit):
export OPENAI_API_KEY='your-key-here'
```

The model reads **both sides** and proposes player/character, brand, set, card #, parallel, serial run and grade label. You must confirm the attributes yourself; AI confidence alone never unlocks valuation.

## Reliable sold-price inputs

Start by copying [`sample_data/sold_comps_template.csv`](sample_data/sold_comps_template.csv) and adding actual completed sales from a source you are authorized to use. Use **actual sold price and shipping charged**, not active listings or asking prices. Required columns:

`category,subject,year,manufacturer,set_name,card_number,parallel,serial_number,grade,sale_type,sold_date,price,shipping,source_url`

- `sale_type` must equal `sold`; `sold_date` must be `YYYY-MM-DD` and within the last **180 days**.
- `source_url` must link to the actual source transaction; CSV data is *user-provided*, not independently authenticated by this prototype.
- Match exact category, subject, year, brand, set, card #, parallel, raw/grade and **serial print run** (`23/99` is comparable to `44/99` only when every other attribute matches; `/99` never matches `/50`).
- Require at least **3 exact recent sold comps** to suggest a median price. The low/high range uses 25th–75th percentiles. With fewer than 3, it abstains.
- This estimate is a **comps summary, not a condition appraisal or a guarantee of what a buyer will pay**. Fees, taxes, condition differences and negotiation are not yet modeled.

## Bulk scan + ZIP workflow

Rename images into explicit front/back pairs:

```text
001_front.jpg
001_back.jpg
002_front.jpg
002_back.jpg
```

In the **Bulk scans → ZIP** tab, select multiple files and download a ZIP containing `/front.png`, `/back.png`, `/flyer.png`, `/result.json` for each pair, plus a manifest. Those batch flyers are **drafts** until the exact identification is reviewed. No misleading automatic price is shown.

## Run directly against a synced desktop folder

When your Canon scans arrive in a **computer folder** (or phone sync copies them there):

```bash
python -m cardbot.cli --in ./scans --out ./output
# Optional: process new file pairs every 8s while the process runs
python -m cardbot.cli --in ./scans --out ./output --watch
# Optional paid AI draft identification, requires OPENAI_API_KEY
python -m cardbot.cli --in ./scans --out ./output --watch --vision
```

The script only processes complete, stable front/back pairs, stores cropped PNGs plus a flyer and JSON, and skips unchanged input files. It **does not run on GitHub Actions continuously** and cannot monitor files only held on an Android phone.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Next build milestones

1. Validate crops on real Canon white/light-bordered cards, foil cards, multiple-card scans and rotated cards. Add interactive manual crop correction.
2. Integrate an authorized live sold-comps data source; collect real comp provenance, price, shipping, date, variant and grade; test false-match rate.
3. Add real local inventory with duplicate detection, card condition photos, cost basis and sale statuses.
4. Add Android folder access with explicit permissions; optional private hosted app and later eBay/listing integrations.