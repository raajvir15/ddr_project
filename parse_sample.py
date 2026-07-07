import fitz
import re
import json

def extract_full_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = "\n".join(doc[i].get_text() for i in range(len(doc)))
    doc.close()
    return text

def parse_impacted_areas(full_text):
    # Split the document into chunks, one per "Impacted Area N"
    area_splits = re.split(r'Impacted Area (\d+)', full_text)
    # area_splits looks like: [before, "1", chunk1, "2", chunk2, "3", chunk3, ...]

    areas = []
    for i in range(1, len(area_splits), 2):
        area_num = area_splits[i]
        chunk = area_splits[i + 1]

        # Cut this chunk off at the next major section if present
        # (SUMMARY TABLE or Appendix marks the end of impacted areas)
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
    # Remove stray section labels that leak in, collapse whitespace
    text = re.sub(r'Site Details|Impacted Area', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

full_text = extract_full_text("Sample_Report.pdf")
areas = parse_impacted_areas(full_text)

def fill_missing_photo_gaps(areas):
    """
    If an area's negative_photos list is empty, infer it from the gap
    between the previous area's last photo and this area's first
    positive photo. This happens when PDF text extraction loses
    content across a page break.
    """
    for i, area in enumerate(areas):
        if not area["negative_photos"]:
            prev_last = areas[i - 1]["positive_photos"][-1] if i > 0 else 0
            next_first = area["positive_photos"][0] if area["positive_photos"] else prev_last + 1
            inferred = list(range(prev_last + 1, next_first))
            area["negative_photos"] = inferred
            area["negative_photos_inferred"] = True  # flag it — don't hide that this was guessed
        else:
            area["negative_photos_inferred"] = False
    return areas

areas = fill_missing_photo_gaps(areas)

def flag_suspicious_text(areas):
    for area in areas:
        # descriptions ending mid-sentence (no punctuation, ends in a conjunction) are suspicious
        if re.search(r'\b(and|the|of|with|to)$', area["positive_description"].strip(), re.IGNORECASE):
            area["positive_description_suspicious"] = True
        else:
            area["positive_description_suspicious"] = False
    return areas

areas = flag_suspicious_text(areas)

for a in areas:
    print(a)

with open("sample_areas_parsed.json", "w") as f:
    json.dump(areas, f, indent=2)


# Load the sorted thermal readings from the earlier step
with open("thermal_parsed_sorted.json") as f:
    thermal_readings = json.load(f)

def assign_thermal_to_areas(areas, thermal_readings):
    idx = 0
    total_thermal = len(thermal_readings)
    total_negative_photos = sum(len(a["negative_photos"]) for a in areas)
    extra = total_thermal - total_negative_photos  # leftover shots to distribute

    for area in areas:
        count = len(area["negative_photos"])
        # give the area with the most negative photos any leftover extra shots
        take = count
        area["thermal_readings"] = thermal_readings[idx: idx + take]
        idx += take

    # any leftover thermal readings (due to extra=3) go unassigned — flag them
    leftover = thermal_readings[idx:]
    return areas, leftover

areas, leftover_thermal = assign_thermal_to_areas(areas, thermal_readings)

# Save the fully merged structure — this is the file generate_report.py will read
output = {
    "areas": areas,
    "unassigned_thermal_readings": leftover_thermal,
}
with open("structured_ddr_data.json", "w") as f:
    json.dump(output, f, indent=2)

print("Saved structured_ddr_data.json — ready for report generation")