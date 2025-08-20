import streamlit as st
import fitz  # PyMuPDF
import zipfile
import tempfile
import os
import io
import csv
import camelot
import pandas as pd
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# ---------------- AUTH SECTION ----------------
USERNAME = "Pushpal"
PASSWORD = "Pushpal2002"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🔐 Login Required")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state.authenticated = True
            st.success("✅ Login successful! Access granted.")
        else:
            st.error("❌ Invalid username or password")

# ---------------- PDF FUNCTIONS ----------------
def is_page_text_based(page):
    text = page.get_text().strip()
    return len(text) > 0

def extract_text_blocks(pdf_path):
    doc = fitz.open(pdf_path)
    results = []
    for page_num, page in enumerate(doc, start=1):
        if is_page_text_based(page):
            blocks = page.get_text("blocks")
            for b in blocks:
                results.append([page_num, "text", b[4].strip()])
        else:
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
            text = pytesseract.image_to_string(images[0])
            results.append([page_num, "ocr_text", text.strip()])
    return results

def extract_tables(pdf_path):
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        return [t.df.values.tolist() for t in tables]
    except:
        return []

# ---------------- SAVE FUNCTIONS ----------------
def save_to_csv(pdf_name, text_blocks, tables):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["page", "type", "content"])
    for tb in text_blocks:
        writer.writerow(tb)
    if tables:
        for i, table in enumerate(tables, start=1):
            writer.writerow([f"Table {i}"])
            for row in table:
                writer.writerow(row)  # ✅ each column separate
            writer.writerow([])  # blank line
    return output.getvalue()

def save_to_txt(pdf_name, text_blocks, tables):
    output = io.StringIO()
    output.write(f"### Extracted content from {pdf_name} ###\n\n")
    for tb in text_blocks:
        output.write(f"[Page {tb[0]} - {tb[1]}] {tb[2]}\n")
    if tables:
        for i, table in enumerate(tables, start=1):
            output.write(f"\nTable {i}:\n")
            for row in table:
                output.write(" | ".join(row) + "\n")
    return output.getvalue()

def save_to_excel(pdf_name, text_blocks, tables):
    text_df = pd.DataFrame(text_blocks, columns=["page", "type", "content"])
    with pd.ExcelWriter(io.BytesIO(), engine="xlsxwriter") as writer:
        text_df.to_excel(writer, index=False, sheet_name="Text")
        if tables:
            for i, table in enumerate(tables, start=1):
                table_df = pd.DataFrame(table)
                table_df.to_excel(writer, index=False, sheet_name=f"Table_{i}")
        writer.save()
        return writer.book.filename.getvalue()

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="PDF Extractor", layout="wide")

if not st.session_state.authenticated:
    login()
else:
    st.title("📄 PDF → CSV / Excel / TXT Extractor")
    st.write("Upload single/multiple PDFs, or ZIP with PDFs. Choose output format.")

    output_format = st.radio("Select output format:", ["CSV", "Excel", "TXT"])
    uploaded_files = st.file_uploader("Upload PDFs/ZIP", type=["pdf", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_output = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(zip_output.name, 'w') as zipf:
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(tmpdir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    def process_pdf(pdf_path, fname):
                        text_blocks = extract_text_blocks(pdf_path)
                        tables = extract_tables(pdf_path)

                        if output_format == "CSV":
                            data = save_to_csv(fname, text_blocks, tables)
                            zipf.writestr(fname.replace(".pdf", ".csv"), data)
                        elif output_format == "TXT":
                            data = save_to_txt(fname, text_blocks, tables)
                            zipf.writestr(fname.replace(".pdf", ".txt"), data)
                        elif output_format == "Excel":
                            data = save_to_excel(fname, text_blocks, tables)
                            zipf.writestr(fname.replace(".pdf", ".xlsx"), data)

                    if uploaded_file.name.endswith(".pdf"):
                        process_pdf(file_path, uploaded_file.name)
                    elif uploaded_file.name.endswith(".zip"):
                        with zipfile.ZipFile(file_path, 'r') as inner_zip:
                            inner_zip.extractall(tmpdir)
                            for item in os.listdir(tmpdir):
                                if item.endswith(".pdf"):
                                    process_pdf(os.path.join(tmpdir, item), item)

            st.success("✅ Extraction complete! Download your ZIP:")
            with open(zip_output.name, "rb") as f:
                st.download_button("Download Results", f, file_name="extracted_results.zip")

                
