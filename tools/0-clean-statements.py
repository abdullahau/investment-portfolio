# tools/0-clean-statements.py

import fitz  # PyMuPDF
from src import config

input_folder = config.RAW_DATA_DIR / "original-statements"
output_folder = config.RAW_DATA_DIR / "redacted-statements"

texts_to_remove = [config.ACCOUNT_NAME, config.ACCOUNT_NUM]

for input_path in input_folder.glob("*.pdf"):
    output_path = output_folder / input_path.name

    doc = fitz.open(input_path)

    first_page = doc[0]
    for text in texts_to_remove:
        areas = first_page.search_for(text)  # pyright: ignore
        for area in areas:
            first_page.add_redact_annot(area, fill=(1, 1, 1))  # white box

    first_page.apply_redactions()  # pyright: ignore

    total_pages = len(doc)
    if total_pages > 2:
        for i in range(total_pages - 1, total_pages - 3, -1):
            doc.delete_page(i)

    doc.save(output_path)
    doc.close()

    print(f"Processed '{input_path.name}': redacted + trimmed")

print("✅ All PDFs processed.")
