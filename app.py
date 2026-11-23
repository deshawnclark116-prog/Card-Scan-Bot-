"""Phone-friendly personal card scanning and flyer application."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import streamlit as st

from cardbot.batch import pair_scans
from cardbot.crop import crop_card, open_scan
from cardbot.flyer import make_flyer, png_bytes
from cardbot.identity import CardIdentity, identify_card
from cardbot.pricing import estimate_price, load_comps


st.set_page_config(page_title="Card Scan Bot", page_icon="🃏", layout="wide")
st.title("🃏 Card Scan Bot")
st.caption("Canon scan → safe crop → exact card verification → sold-comps price → shareable flyer")

with st.sidebar:
    st.header("Valuation inputs")
    comps_upload = st.file_uploader("Sold-comps CSV (optional)", type=["csv"], key="comps")
    comps: list[dict] = []
    if comps_upload is not None:
        try:
            comps = load_comps(comps_upload.getvalue().decode("utf-8-sig"))
            st.success(f"Loaded {len(comps)} comp rows. Only exact sold matches count.")
        except (ValueError, UnicodeError) as error:
            st.error(str(error))
    st.caption("No price is fabricated. This version imports documented sold transactions; live marketplaces are not yet connected.")
    st.link_button("See CSV template", "https://github.com/deshawnclark116-prog/Card-Scan-Bot-/blob/main/sample_data/sold_comps_template.csv")


def get_crops(front_data: bytes, back_data: bytes):
    return crop_card(open_scan(front_data)), crop_card(open_scan(back_data))


def render_crops(front, back):
    left, right = st.columns(2)
    with left:
        st.image(front.image, caption=f"Front crop — {front.reason}", use_container_width=True)
        if front.needs_review:
            st.warning("Check front edges; original scan was kept or crop needs review")
    with right:
        st.image(back.image, caption=f"Back crop — {back.reason}", use_container_width=True)
        if back.needs_review:
            st.warning("Check back edges and serial numbering")


single, bulk = st.tabs(["Single card → flyer", "Bulk scans → ZIP"])
with single:
    st.markdown("**Choose both Canon scans from your phone's Files app.**")
    f = st.file_uploader("Front scan", type=["jpg", "jpeg", "png", "webp", "tif", "tiff"], key="front")
    b = st.file_uploader("Back scan", type=["jpg", "jpeg", "png", "webp", "tif", "tiff"], key="back")
    if f is not None and b is not None:
        try:
            front_data, back_data = f.getvalue(), b.getvalue()
            front, back = get_crops(front_data, back_data)
            render_crops(front, back)
            image_key = hashlib.sha256(front_data + back_data).hexdigest()[:16]
            if st.session_state.get("image_key") != image_key:
                st.session_state["image_key"] = image_key
                st.session_state["ai_card"] = CardIdentity()
                st.session_state.pop("last_flyer", None)
            if st.button("Identify using AI (requires OPENAI_API_KEY)"):
                with st.spinner("Reading both sides..."):
                    try:
                        st.session_state["ai_card"] = identify_card(front.image, back.image)
                        st.session_state.pop("last_flyer", None)
                        st.success("AI draft ready. Verify the exact variant before pricing.")
                    except Exception as exc:
                        st.error(f"Identification unavailable: {exc}")
            ai = st.session_state.get("ai_card", CardIdentity())
            st.subheader("Confirm card identification")
            st.caption("AI output is a draft. Check printed set/card number, parallel, serial run and grade.")
            # Different form identity after an AI update prevents stale input defaults.
            form_id = hashlib.sha256((image_key + json.dumps(ai.to_dict(), sort_keys=True)).encode()).hexdigest()[:12]
            with st.form("card_review_" + form_id):
                choices = ["sports", "tcg", "non-sports"]
                category = st.selectbox("Category", choices, index=choices.index(ai.category) if ai.category in choices else 0)
                subject = st.text_input("Player / character / subject", value=ai.subject)
                c1, c2 = st.columns(2)
                with c1:
                    year = st.text_input("Year", value=ai.year)
                    manufacturer = st.text_input("Brand / manufacturer", value=ai.manufacturer)
                    number = st.text_input("Card number", value=ai.card_number)
                    serial = st.text_input("Serial numbering (example: 23/99)", value=ai.serial_number)
                with c2:
                    set_name = st.text_input("Set", value=ai.set_name)
                    parallel = st.text_input("Parallel (blank if base)", value=ai.parallel)
                    grade = st.text_input("Raw or graded label", value=ai.grade or "raw")
                    ask = st.number_input("Asking price USD (0 = use comps / price on request)",
                                          min_value=0., step=1., value=0.)
                contact = st.text_input("Flyer contact line", value="Message me if interested")
                verified = st.checkbox("I checked the exact card identity and variant against both scans")
                submit = st.form_submit_button("Generate sale flyer", type="primary")
            if submit:
                identity = CardIdentity(
                    category=category, subject=subject, year=year, manufacturer=manufacturer,
                    set_name=set_name, card_number=number, parallel=parallel, serial_number=serial,
                    grade=grade or "raw", confidence="verified" if verified else "unverified",
                    notes=ai.notes,
                )
                estimate = estimate_price(identity, comps)
                flyer = make_flyer(front.image, back.image, identity, estimate,
                                   asking_price=ask if ask > 0 else None, seller_line=contact)
                st.session_state["last_flyer"] = (png_bytes(flyer), estimate.status, identity.title)
            if "last_flyer" in st.session_state:
                flyer_bytes, price_status, title = st.session_state["last_flyer"]
                st.info(price_status)
                st.image(flyer_bytes, caption=title, width=450)
                st.download_button("Download 1200×1500 PNG flyer", flyer_bytes,
                                   file_name="card-sale-flyer.png", mime="image/png")
        except Exception as exc:
            st.error(f"Couldn't process images: {exc}")
    else:
        st.info("Upload a front scan and a back scan to begin.")

with bulk:
    st.write("Upload scans named 001_front.jpg, 001_back.jpg, 002_front.jpg, 002_back.jpg, etc. Both sides required.")
    uploads = st.file_uploader("Select multiple scans from phone or computer", accept_multiple_files=True,
                               type=["jpg", "jpeg", "png", "webp", "tif", "tiff"], key="bulk")
    use_vision = st.checkbox("Attempt AI identification for each pair (paid API, optional)", value=False)
    st.caption("Bulk drafts are unverified; ZIP contains cropped images, flyer drafts and metadata, not asserted prices.")
    if uploads and st.button("Process pairs and build ZIP", type="primary"):
        pairs, skipped = pair_scans([Path(x.name) for x in uploads])
        by_name = {x.name: x for x in uploads}
        if len(by_name) != len(uploads):
            st.error("Duplicate upload filenames detected. Please rename the scans before processing.")
        elif not pairs:
            st.warning("No complete front/back filename pairs found.")
        else:
            mem = BytesIO()
            manifest = []
            with st.spinner(f"Processing {len(pairs)} card pairs..."):
                with ZipFile(mem, "w", ZIP_DEFLATED) as zip_out:
                    for key, sides in pairs.items():
                        try:
                            front, back = get_crops(
                                by_name[sides["front"].name].getvalue(),
                                by_name[sides["back"].name].getvalue(),
                            )
                            identity = CardIdentity()
                            if use_vision:
                                identity = identify_card(front.image, back.image)
                            estimate = estimate_price(identity, comps)
                            folder = "cards/" + "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:90]
                            zip_out.writestr(folder + "/front.png", png_bytes(front.image))
                            zip_out.writestr(folder + "/back.png", png_bytes(back.image))
                            zip_out.writestr(folder + "/flyer.png",
                                             png_bytes(make_flyer(front.image, back.image, identity, estimate)))
                            info = {
                                "key": key, "identity": identity.to_dict(), "price": estimate.__dict__,
                                "front_crop_needs_review": front.needs_review,
                                "back_crop_needs_review": back.needs_review,
                            }
                            zip_out.writestr(folder + "/result.json", json.dumps(info, indent=2))
                            manifest.append(info)
                        except Exception as exc:
                            skipped.append(f"{key}: {exc}")
                    zip_out.writestr("manifest.json", json.dumps(manifest, indent=2))
                    zip_out.writestr("skipped.txt", "\n".join(skipped))
            st.success(f"Prepared {len(manifest)} card pairs")
            if skipped:
                st.warning(f"{len(skipped)} files/groups need review: " + "; ".join(skipped[:5]))
            st.download_button("Download processed cards ZIP", mem.getvalue(),
                               file_name="card-scan-bot-results.zip", mime="application/zip")
