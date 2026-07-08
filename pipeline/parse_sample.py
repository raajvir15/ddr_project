import fitz
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def extract_full_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = "\n".join(doc[i].get_text() for i in range(len(doc)))
    doc.close()
    return text


def extract_between(text, start_marker, end_marker):
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return ""
    start_idx += len(start_marker)
    if end_marker:
        end_idx = text.find(end_marker, start_idx)
        if end_idx == -1:
            end_idx = len(text)
    else:
        end_idx = len(text)
    return text[start_idx:end_idx]


def extract_photo_numbers(text):
    return [int(n) for n in re.findall(r'Photo\s+(\d+)', text)]


def clean(text):
    text = re.sub(r'Site Details|Impacted Area', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_impacted_areas(full_text):
    area_splits = re.split(r'Impacted Area (\d+)', full_text)
    areas = []
    for i in range(1, len(area_splits), 2):
        area_num = area_splits[i]
        chunk = area_splits[i + 1]
        chunk = re.split(r'SUMMARY TABLE|Appendix', chunk)[0]

        neg_desc = extract_between(chunk, "Negative side Description", "Negative side photographs")
        pos_desc = extract_between(chunk, "Positive side Description", "Positive side photographs")

        neg_photos = extract_photo_numbers(
            extract_between(chunk, "Negative side photographs", "Positive side Description")
        )
        pos_photos = extract_photo_numbers(
            extract_between(chunk, "Positive side photographs", None)
        )

        areas.append({
            "area_num": int(area_num),
            "negative_description": clean(neg_desc),
            "negative_photos": neg_photos,
            "positive_description": clean(pos_desc),
            "positive_photos": pos_photos,
        })
    return areas


def fill_missing_photo_gaps(areas):
    for i, area in enumerate(areas):
        if not area["negative_photos"]:
            prev_last = areas[i - 1]["positive_photos"][-1] if i > 0 else 0
            next_first = area["positive_photos"][0] if area["positive_photos"] else prev_last + 1
            inferred = list(range(prev_last + 1, next_first))
            area["negative_photos"] = inferred
            area["negative_photos_inferred"] = True
        else:
            area["negative_photos_inferred"] = False
    return areas


def flag_suspicious_text(areas):
    for area in areas:
        if re.search(r'\b(and|the|of|with|to)$', area["positive_description"].strip(), re.IGNORECASE):
            area["positive_description_suspicious"] = True
        else:
            area["positive_description_suspicious"] = False
    return areas


def assign_thermal_to_areas(areas, thermal_readings):
    idx = 0
    for area in areas:
        count = len(area["negative_photos"])
        area["thermal_readings"] = thermal_readings[idx: idx + count]
        idx += count
    leftover = thermal_readings[idx:]
    return areas, leftover


def run_sample_report_parsing(pdf_path, thermal_readings):
    full_text = extract_full_text(pdf_path)
    areas = parse_impacted_areas(full_text)
    areas = fill_missing_photo_gaps(areas)
    areas = flag_suspicious_text(areas)
    areas, leftover = assign_thermal_to_areas(areas, thermal_readings)
    return areas, leftover


if __name__ == "__main__":
    from parse_thermal import run_thermal_extraction

    thermal_readings = run_thermal_extraction(str(INPUTS_DIR / "Thermal_Images.pdf"))
    areas, leftover = run_sample_report_parsing(str(INPUTS_DIR / "Sample_Report.pdf"), thermal_readings)

    OUTPUTS_DIR.mkdir(exist_ok=True)
    output = {"areas": areas, "unassigned_thermal_readings": leftover}
    with open(OUTPUTS_DIR / "structured_ddr_data.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {OUTPUTS_DIR / 'structured_ddr_data.json'}")