import fitz
import os
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def extract_appendix_photos(pdf_path, out_dir, start_page=11, end_page=23):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    seen_hashes = set()
    photo_num = 0
    saved = {}

    for page_num in range(start_page - 1, end_page):
        page = doc[page_num]
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]

            pix_w, pix_h = base_image.get("width", 0), base_image.get("height", 0)
            if pix_w < 100 or pix_h < 100:
                continue

            content_hash = hashlib.md5(image_bytes).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            photo_num += 1
            fname = os.path.join(out_dir, f"photo_{photo_num:02d}.{ext}")
            with open(fname, "wb") as f:
                f.write(image_bytes)
            saved[photo_num] = fname

    doc.close()
    return saved

##  goes into a specific range of PDF pages, finds every real photo, throws out 
# icons and duplicates, and saves each unique one as its own file


def run_photo_extraction(pdf_path, out_dir, total_expected=64):
    saved = extract_appendix_photos(pdf_path, out_dir)

    photo_manifest = {}
    for i in range(1, total_expected + 1):
        if i in saved:
            photo_manifest[i] = {"path": saved[i], "available": True}
        else:
            photo_manifest[i] = {"path": None, "available": False}

    return photo_manifest

# # takes whatever photos were actually successfully extracted, and builds a 
# complete accounting of all 64 expected photo numbers — including the ones that couldn't be found


if __name__ == "__main__":
    OUTPUTS_DIR.mkdir(exist_ok=True)
    photo_dir = OUTPUTS_DIR / "report_photos"

    manifest = run_photo_extraction(str(INPUTS_DIR / "Sample_Report.pdf"), str(photo_dir))

    with open(OUTPUTS_DIR / "photo_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    missing = [k for k, v in manifest.items() if not v["available"]]
    print(f"{len(manifest) - len(missing)}/{len(manifest)} photos available.")
    print("Missing:", missing)