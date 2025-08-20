import streamlit as st
import fitz  # PyMuPDF
import zipfile
import tempfile
import os
import io
import camelot
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
                results.append(f"[Page {page_num} - TEXT] {b[4].strip()}")
        else:
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
            text = pytesseract.image_to_string(images[0])
            results.append(f"[Page {page_num} - OCR] {text.strip()}")
    return results

def extract_tables(pdf_path):
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        table_texts = []
        for i, t in enumerate(tables, start=1):
            table_texts.append(f"\n--- TABLE {i} START ---\n")
            for row in t.df.values.tolist():
                table_texts.append(" | ".join(row))
            table_texts.append(f"--- TABLE {i} END ---\n")
        return table_texts
    except:
        return []

def save_to_txt(pdf_name, text_blocks, tables):
    output = io.StringIO()
    output.write(f"### Extracted content from {pdf_name} ###\n\n")
    for tb in text_blocks:
        output.write(tb + "\n")
    if tables:
        for t in tables:
            output.write(t + "\n")
    return output.getvalue()

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="PDF to TXT Extractor", layout="wide")

if not st.session_state.authenticated:
    login()
else:
    st.title("📄 PDF → TXT All-Rounder Extractor")
    st.write("Upload single/multiple PDFs, folder (as ZIP), or ZIP with PDFs. Get structured text with original file names.")

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
                        txt_data = save_to_txt(uploaded_file.name, text_blocks, tables)
                        txt_filename = uploaded_file.name.replace(".pdf", ".txt")
                        zipf.writestr(txt_filename, txt_data)
                    elif uploaded_file.name.endswith(".zip"):
                        with zipfile.ZipFile(file_path, 'r') as inner_zip:
                            inner_zip.extractall(tmpdir)
                            for item in os.listdir(tmpdir):
                                if item.endswith(".pdf"):
                                    pdf_path = os.path.join(tmpdir, item)
                                    text_blocks = extract_text_blocks(pdf_path)
                                    tables = extract_tables(pdf_path)
                                    txt_data = save_to_txt(item, text_blocks, tables)
                                    txt_filename = item.replace(".pdf", ".txt")
                                    zipf.writestr(txt_filename, txt_data)
            st.success("✅ Extraction complete! Download your ZIP:")
            with open(zip_output.name, "rb") as f:
                st.download_button("Download TXT ZIP", f, file_name="extracted_txts.zip")
                
