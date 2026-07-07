import json
import os
import re
import time
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

with open("structured_ddr_data.json") as f:
    data = json.load(f)

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
6. For "recommended_actions" specifically: if both a negative-side (symptom) and
   positive-side (suspected source) description are present, you should ALWAYS
   be able to generate a recommendation (repair the source, then remediate the
   symptom) — do not write "Not Available" for this field unless BOTH
   descriptions are literally missing. Base the recommendation on the same
   source-then-symptom repair logic you would use for a similar area.

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

def build_area_prompt(area):
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

results = []
for area in data["areas"]:
    prompt = build_area_prompt(area)

    # Retry loop — if we hit the free-tier rate limit, wait and try again
    max_retries = 5
    response = None
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                [SYSTEM_INSTRUCTIONS, prompt],
                generation_config={"temperature": 0.3}
            )
            break  # success, exit retry loop
        except ResourceExhausted:
            wait_time = 15
            print(f"  Rate limited on Area {area['area_num']}, "
                  f"waiting {wait_time}s (attempt {attempt+1}/{max_retries})...")
            time.sleep(wait_time)

    if response is None:
        print(f"  FAILED Area {area['area_num']} after {max_retries} retries.")
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
    print(f"Area {area['area_num']} done.")

    time.sleep(13)  # stay safely under 5 requests/minute (~1 every 12-13s)

with open("ddr_generated_content.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nAll areas processed. Saved to ddr_generated_content.json")