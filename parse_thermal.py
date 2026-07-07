import fitz
import re
import json

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

thermal_pages = extract_pages_text("Thermal_Images.pdf")
parsed = [parse_thermal_page(p) for p in thermal_pages]

for row in parsed:
    print(row)

with open("thermal_parsed.json", "w") as f:
    json.dump(parsed, f, indent=2)

# Sort by the numeric part of the filename (RB02377X -> 2377)
def filename_number(row):
    return int(row["filename"][2:-1])  # strips "RB" prefix and "X" suffix

parsed_sorted = sorted(parsed, key=filename_number)

for row in parsed_sorted:
    print(row["filename"], row["hotspot_c"], row["coldspot_c"])

with open("thermal_parsed_sorted.json", "w") as f:
    json.dump(parsed_sorted, f, indent=2)