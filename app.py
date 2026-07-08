import streamlit as st
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")  # only does anything locally, harmless if .env is missing

from pipeline.parse_thermal import run_thermal_extraction
from pipeline.parse_sample import run_sample_report_parsing
from pipeline.extract_photos import run_photo_extraction
from pipeline.generate_report import run_report_generation
from pipeline.build_ddr import build_document

st.set_page_config(page_title="DDR Report Generator", layout="centered")
st.title("AI-Powered DDR Report Generator")
st.write(
    "Upload a site Inspection Report and a Thermal Imaging Report (both PDF). "
    "This tool extracts observations, correlates thermal data, and generates "
    "a structured Detailed Diagnosis Report."
)

inspection_file = st.file_uploader("Inspection Report (PDF)", type="pdf")
thermal_file = st.file_uploader("Thermal Imaging Report (PDF)", type="pdf")

if inspection_file and thermal_file:
    if st.button("Generate DDR Report"):
        # Check Streamlit secrets first (cloud), fall back to .env (local)
        api_key = st.secrets.get("GEMINI_API_KEY") if hasattr(st, "secrets") else None
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            st.error("GEMINI_API_KEY not found. Set it in Streamlit Secrets (cloud) or your .env file (local).")
            st.stop()

        with tempfile.TemporaryDirectory() as tmpdir:
            inspection_path = os.path.join(tmpdir, "inspection.pdf")
            thermal_path = os.path.join(tmpdir, "thermal.pdf")
            with open(inspection_path, "wb") as f:
                f.write(inspection_file.read())
            with open(thermal_path, "wb") as f:
                f.write(thermal_file.read())

            photo_dir = os.path.join(tmpdir, "report_photos")

            with st.spinner("Extracting thermal readings..."):
                thermal_readings = run_thermal_extraction(thermal_path)

            with st.spinner("Parsing inspection report..."):
                areas, leftover = run_sample_report_parsing(inspection_path, thermal_readings)

            with st.spinner("Extracting photos..."):
                photo_manifest_int_keys = run_photo_extraction(inspection_path, photo_dir)
                photo_manifest = {str(k): v for k, v in photo_manifest_int_keys.items()}

            progress_text = st.empty()
            def show_progress(area_num):
                progress_text.write(f"Generated content for Area {area_num}...")

            with st.spinner("Generating report content with AI (~2 minutes)..."):
                report_areas = run_report_generation(areas, api_key, progress_callback=show_progress)

            with st.spinner("Assembling final document..."):
                output_path = os.path.join(tmpdir, "Final_DDR_Report.docx")
                build_document(report_areas, photo_manifest, output_path)

                with open(output_path, "rb") as f:
                    file_bytes = f.read()

        st.success("Done!")
        st.download_button(
            label="Download DDR Report (.docx)",
            data=file_bytes,
            file_name="DDR_Report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )