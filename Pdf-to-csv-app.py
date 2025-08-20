import streamlit as st
import fitz  # PyMuPDF
import zipfile
import tempfile
import os
import io
import csv
import camelot
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# ---------------- AUTH SECTION ----------------
# Simple static credentials (change for client)
USERNAME = "clientuser"
PASSWORD = "clientpass"

# Initialize session state
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

def save_to_csv(pdf_name, text_blocks, tables):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["page", "type", "content"])
    for tb in text_blocks:
        writer.writerow(tb)
    if tables:
        for i, table in enumerate(tables, start=1):
            writer.writerow(["table", f"table_{i}", "---TABLE START---"])
            for row in table:
                writer.writerow(["", "row", ", ".join(row)])
            writer.writerow(["", "", "---TABLE END---"])
    return output.getvalue()

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="PDF to CSV Extractor", layout="wide")

if not st.session_state.authenticated:
    login()
else:
    st.title("📄 PDF → CSV All-Rounder Extractor")
    st.write("Upload single/multiple PDFs, folder (as ZIP), or ZIP with PDFs. Get structured CSV with text + tables.")

    uploaded_files = st.file_uploader("Upload PDFs/ZIP", type=["pdf", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_output = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(zip_output.name, 'w') as zipf:
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(tmpdir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    if uploaded_file.name.endswith(".pdf"):
                        text_blocks = extract_text_blocks(file_path)
                        tables = extract_tables(file_path)
                        csv_data = save_to_csv(uploaded_file.name, text_blocks, tables)
                        csv_filename = uploaded_file.name.replace(".pdf", ".csv")
                        zipf.writestr(csv_filename, csv_data)
                    elif uploaded_file.name.endswith(".zip"):
                        with zipfile.ZipFile(file_path, 'r') as inner_zip:
                            inner_zip.extractall(tmpdir)
                            for item in os.listdir(tmpdir):
                                if item.endswith(".pdf"):
                                    pdf_path = os.path.join(tmpdir, item)
                                    text_blocks = extract_text_blocks(pdf_path)
                                    tables = extract_tables(pdf_path)
                                    csv_data = save_to_csv(item, text_blocks, tables)
                                    csv_filename = item.replace(".pdf", ".csv")
                                    zipf.writestr(csv_filename, csv_data)
            st.success("✅ Extraction complete! Download your ZIP:")
            with open(zip_output.name, "rb") as f:
                st.download_button("Download CSV ZIP", f, file_name="extracted_csvs.zip")
