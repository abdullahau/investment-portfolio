import os
import fitz  # PyMuPDF

input_folder = "path/to/file"                   # Enter source statement file
output_folder = "src/monthly-statements-pdf"
texts_to_remove = ["NAME", "A/C No"]            # Remove sensitive information

for filename in os.listdir(input_folder):
    if filename.lower().endswith(".pdf"):
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        doc = fitz.open(input_path)

        first_page = doc[0]
        for text in texts_to_remove:
            areas = first_page.search_for(text)
            for area in areas:
                first_page.add_redact_annot(area, fill=(1, 1, 1))  # white box

        first_page.apply_redactions()

        total_pages = len(doc)
        if total_pages > 2:
            for i in range(total_pages - 1, total_pages - 3, -1):
                doc.delete_page(i)

        doc.save(output_path)
        doc.close()

        print(f"Processed '{filename}': redacted + trimmed")

print("✅ All PDFs processed.")
