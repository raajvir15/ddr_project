import json
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

load_dotenv(PROJECT_ROOT / ".env")

SYSTEM_INSTRUCTIONS = """
You are generating one section of a professional Detailed Diagnosis Report (DDR)
for a building waterproofing/structural inspection company. You will be given
structured data about ONE impacted area of a property inspection.

STRICT RULES — follow exactly:
1. Do NOT invent any fact not present in the data given to you.
2. If a field cannot be determined from the given data, write "Not Available" —
   never guess or fabricate a plausible-sounding answer.
3. If the data contains a flag indicating the information was inferred or is
   suspicious/uncertain, you MUST mention this uncertainty explicitly in your
   output (e.g. "Note: photo range for this area was reconstructed due to a
   data extraction gap and should be manually verified.")
4. Use simple, client-friendly language. No unnecessary technical jargon.
5. Base your Severity Assessment reasoning on the actual hotspot/coldspot
   temperature differential given (a larger gap between hotspot and coldspot
   in a damp area generally indicates more active moisture movement) — cite
   the actual numbers in your reasoning, don't just assert a severity level.
6. For "recommended_actions" specifically: if both a negative-side (symptom)
   and positive-side (suspected source) description are present, you should
   ALWAYS be able to generate a recommendation (repair the source, then
   remediate the symptom) — do not write "Not Available" for this field
   unless BOTH descriptions are literally missing.

Return ONLY valid JSON (no markdown fences, no preamble) matching this exact schema:
{
  "property_issue_summary": "...",
  "area_wise_observation": "...",
  "probable_root_cause": "...",
  "severity_assessment": "...",
  "recommended_actions": "...",
  "additional_notes": "...",
  "missing_or_unclear_information": "..."
}
"""


def _build_area_prompt(area):
    thermal_summary = "No thermal readings confidently correlated to this area."
    if area.get("thermal_readings"):
        temps = [f"hotspot {t['hotspot_c']}°C / coldspot {t['coldspot_c']}°C"
                 for t in area["thermal_readings"]]
        thermal_summary = "; ".join(temps)

    return f"""
AREA DATA:
- Area number: {area['area_num']}
- Negative-side (problem) description: {area['negative_description']}
- Negative-side photo count: {len(area['negative_photos'])} (photo numbers: {area['negative_photos']})
- Positive-side (suspected source) description: {area['positive_description']}
- Positive-side photo count: {len(area['positive_photos'])} (photo numbers: {area['positive_photos']})
- Negative-side photo range was inferred (not directly extracted): {area['negative_photos_inferred']}
- Positive-side description flagged as possibly garbled/incomplete: {area['positive_description_suspicious']}
- Thermal readings for this area: {thermal_summary}

Generate the DDR section fields for this area now.
"""


def run_report_generation(areas, api_key, progress_callback=None):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    results = []
    for area in areas:
        prompt = _build_area_prompt(area)

        response = None
        for attempt in range(5):
            try:
                response = model.generate_content(
                    [SYSTEM_INSTRUCTIONS, prompt],
                    generation_config={"temperature": 0.3}
                )
                break
            except ResourceExhausted:
                time.sleep(15)

        if response is None:
            results.append({
                "area_num": area["area_num"],
                "negative_description": area["negative_description"],
                "positive_description": area["positive_description"],
                "negative_photos": area["negative_photos"],
                "positive_photos": area["positive_photos"],
                "generated_content": {"error": "Failed after retries"}
            })
            continue

        raw_text = response.text.strip()
        raw_text = re.sub(r'^```json\s*|\s*```$', '', raw_text.strip())

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = {"error": "Failed to parse JSON", "raw_response": raw_text}

        results.append({
            "area_num": area["area_num"],
            "negative_description": area["negative_description"],
            "positive_description": area["positive_description"],
            "negative_photos": area["negative_photos"],
            "positive_photos": area["positive_photos"],
            "generated_content": parsed
        })

        if progress_callback:
            progress_callback(area["area_num"])

        time.sleep(13)

    return results


if __name__ == "__main__":
    with open(OUTPUTS_DIR / "structured_ddr_data.json") as f:
        data = json.load(f)

    api_key = os.environ["GEMINI_API_KEY"]
    results = run_report_generation(
        data["areas"], api_key,
        progress_callback=lambda n: print(f"Area {n} done.")
    )

    with open(OUTPUTS_DIR / "ddr_generated_content.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {OUTPUTS_DIR / 'ddr_generated_content.json'}")