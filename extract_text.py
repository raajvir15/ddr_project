import fitz  # this is pymupdf

def extract_pages_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text()
        pages.append({"page_num": i + 1, "text": text})
    doc.close()
    return pages

sample_pages = extract_pages_text("Sample_Report.pdf")
thermal_pages = extract_pages_text("Thermal_Images.pdf")

print(f"Sample_Report.pdf: {len(sample_pages)} pages")
print(f"Thermal_Images.pdf: {len(thermal_pages)} pages")
print(thermal_pages[0]["text"])  # peek at what page 1 looks like