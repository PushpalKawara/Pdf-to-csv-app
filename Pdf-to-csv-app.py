# pdf-to-structured-excel-app.py

import streamlit as st
import fitz  # PyMuPDF
import zipfile
import tempfile
import os
import io
import re
import pandas as pd
import camelot
from pdf2image import convert_from_path
import pytesseract

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

# ---------------- HELPERS ----------------
def is_page_text_based(page):
    text = page.get_text().strip()
    return len(text) > 0

def clean_and_split(text):
    """
    Split text into columns based on 2+ spaces, | or ') '
    Example: "Q1 2023   120.5   80.3" → ["Q1 2023", "120.5", "80.3"]
    """
    parts = re.split(r'\s{2,}|\||\)\s', text.strip())
    return [p.strip() for p in parts if p.strip()]

# ---------------- EXTRACTORS ----------------
def extract_text_blocks(pdf_path):
    """Extracts text & OCR from PDF pages"""
    doc = fitz.open(pdf_path)
    results = []
    for page_num, page in enumerate(doc, start=1):
        if is_page_text_based(page):
            blocks = page.get_text("blocks")
            for b in blocks:
                row = clean_and_split(b[4])
                if row:
                    results.append(row)
        else:
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
            text = pytesseract.image_to_string(images[0])
            row = clean_and_split(text)
            if row:
                results.append(row)
    return results

def extract_tables(pdf_path):
    """Extract structured tables using Camelot"""
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        cleaned = []
        for t in tables:
            for row in t.df.values.tolist():
                row_clean = clean_and_split(" ".join(row))
                if row_clean:
                    cleaned.append(row_clean)
        return cleaned
    except:
        return []

# ---------------- SAVE FUNCTIONS ----------------
def remove_duplicates(rows):
    """Remove duplicate rows"""
    df = pd.DataFrame(rows)
    df = df.drop_duplicates().reset_index(drop=True)
    return df.values.tolist()

def save_to_excel(rows, fname):
    """Save cleaned rows to Excel"""
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=False, sheet_name="ExtractedData")
    output.seek(0)
    return output.getvalue()

# ---------------- STREAMLIT APP ----------------
st.set_page_config(page_title="PDF → Structured Excel Extractor", layout="wide")

if not st.session_state.authenticated:
    login()
else:
    st.title("📄 PDF → Structured Excel Extractor")
    st.write("Upload multiple PDFs or ZIP and download clean Excel (structured tables, no duplicates).")

    uploaded_files = st.file_uploader("Upload PDFs/ZIP", type=["pdf", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_output = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(zip_output.name, 'w') as zipf:

                def process_pdf(pdf_path, fname):
                    text_rows = extract_text_blocks(pdf_path)
                    table_rows = extract_tables(pdf_path)

                    # Merge + clean
                    all_rows = text_rows + table_rows
                    clean_rows = remove_duplicates(all_rows)

                    if clean_rows:
                        data = save_to_excel(clean_rows, fname)
                        zipf.writestr(fname.replace(".pdf", ".xlsx"), data)

                for uploaded_file in uploaded_files:
                    file_path = os.path.join(tmpdir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

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
                st.download_button("📥 Download Results", f, file_name="extracted_excel_results.zip")
                
    
