import fitz
import os
import hashlib

def extract_appendix_photos(pdf_path, out_dir="report_photos", start_page=11, end_page=23):
    """
    Extracts only from the Appendix section (pages 11-23, 1-indexed),
    which contains the numbered Photo 1 - Photo 64 images in order.
    """
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    seen_hashes = set()
    photo_num = 0
    saved = {}

    for page_num in range(start_page - 1, end_page):  # convert to 0-indexed
        page = doc[page_num]
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]

            pix_w, pix_h = base_image.get("width", 0), base_image.get("height", 0)
            if pix_w < 100 or pix_h < 100:
                continue  # skip tiny icons

            content_hash = hashlib.md5(image_bytes).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            photo_num += 1
            fname = f"{out_dir}/photo_{photo_num:02d}.{ext}"
            with open(fname, "wb") as f:
                f.write(image_bytes)
            saved[photo_num] = fname
            print(f"  photo {photo_num}: page {page_num+1}, {pix_w}x{pix_h}, {fname}")

    doc.close()
    return saved

saved = extract_appendix_photos("Sample_Report.pdf")
print(f"\nTotal saved: {len(saved)} photos (expected: 64)")

# Build the final photo manifest — map what we have, flag what we don't
TOTAL_EXPECTED_PHOTOS = 64

photo_manifest = {}
for i in range(1, TOTAL_EXPECTED_PHOTOS + 1):
    if i in saved:
        photo_manifest[i] = {"path": saved[i], "available": True}
    else:
        photo_manifest[i] = {"path": None, "available": False}

import json
with open("photo_manifest.json", "w") as f:
    json.dump(photo_manifest, f, indent=2)

missing = [i for i in photo_manifest if not photo_manifest[i]["available"]]
print(f"\nPhoto manifest saved. {len(saved)}/{TOTAL_EXPECTED_PHOTOS} photos available.")
print(f"Missing/unresolved photo numbers: {missing}")