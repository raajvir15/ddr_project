import fitz
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def extract_pages_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        pages.append({"page_num": i + 1, "text": doc[i].get_text()})
    doc.close()
    return pages


def parse_thermal_page(page):
    text = page["text"]
    filename = re.search(r'Thermal image\s*:\s*(RB\d+X)\.JPG', text)
    hotspot = re.search(r'Hotspot\s*:\s*\n([\d.]+)\s*°C', text)
    coldspot = re.search(r'Coldspot\s*:\s*\n([\d.]+)\s*°C', text)
    date = re.search(r'(\d{2}/\d{2}/\d{2})', text)
    return {
        "page_num": page["page_num"],
        "filename": filename.group(1) if filename else None,
        "hotspot_c": float(hotspot.group(1)) if hotspot else None,
        "coldspot_c": float(coldspot.group(1)) if coldspot else None,
        "date": date.group(1) if date else None,
    }


def run_thermal_extraction(pdf_path):
    pages = extract_pages_text(pdf_path)
    parsed = [parse_thermal_page(p) for p in pages]

    def filename_number(row):
        return int(row["filename"][2:-1]) if row["filename"] else 0

    return sorted(parsed, key=filename_number)


if __name__ == "__main__":
    result = run_thermal_extraction(str(INPUTS_DIR / "Thermal_Images.pdf"))
    for row in result:
        print(row["filename"], row["hotspot_c"], row["coldspot_c"])

    OUTPUTS_DIR.mkdir(exist_ok=True)
    with open(OUTPUTS_DIR / "thermal_parsed_sorted.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {OUTPUTS_DIR / 'thermal_parsed_sorted.json'}")