# pdf_to_structured_excel_app.py
# Streamlit app: PDF(s) -> Structured Excel (one XLSX per PDF)
# - Handles text PDFs + scanned PDFs (OCR fallback)
# - Extracts tables (Camelot) + text blocks, cleans, de-duplicates
# - Auto-fit Excel columns
# - Single PDF => direct XLSX download
# - Multiple PDFs / uploaded ZIP => ZIP of XLSX files

import streamlit as st
import fitz  # PyMuPDF
import zipfile
import tempfile
import os
import io
import re
import pandas as pd

# Optional / external deps
import camelot
from pdf2image import convert_from_path
import pytesseract

# ---------------- AUTH (simple demo gate) ----------------
USERNAME = "Pushpal"
PASSWORD = "Pushpal2002"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🔐 Login Required")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == USERNAME and p == PASSWORD:
            st.session_state.authenticated = True
            st.success("✅ Login successful")
        else:
            st.error("❌ Invalid credentials")

# ---------------- Helpers ----------------
def is_page_text_based(page) -> bool:
    """Detect if a page has a text layer (vs image-only)."""
    try:
        text = page.get_text().strip()
        return len(text) > 0
    except Exception:
        return False

def clean_and_split(text: str):
    """
    Split a line into columns:
    - 2+ spaces OR '|' OR ') ' as delimiters
    """
    if not text:
        return []
    parts = re.split(r"\s{2,}|\||\)\s", text.strip())
    return [p.strip() for p in parts if p and p.strip()]

def remove_duplicates(rows):
    """Drop exact duplicate rows."""
    if not rows:
        return rows
    df = pd.DataFrame(rows)
    df = df.drop_duplicates().reset_index(drop=True)
    return df.values.tolist()

# ---------------- Extractors ----------------
def extract_text_blocks(pdf_path: str):
    """
    Extract text blocks from each page.
    If a page has no text -> OCR that page.
    Returns list[List[str]] where each inner list is a row.
    """
    results = []
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return results

    for page_num, page in enumerate(doc, start=1):
        try:
            if is_page_text_based(page):
                # text blocks structure: (x0, y0, x1, y1, text, block_no, ...)
                for b in page.get_text("blocks"):
                    txt = b[4] if len(b) >= 5 else ""
                    for line in txt.splitlines():
                        row = clean_and_split(line)
                        if row:
                            results.append(row)
            else:
                # OCR fallback for scanned page
                images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
                if images:
                    txt = pytesseract.image_to_string(images[0])
                    for line in txt.splitlines():
                        row = clean_and_split(line)
                        if row:
                            results.append(row)
        except Exception:
            # skip bad page silently
            continue
    return results

def extract_tables(pdf_path: str):
    """
    Extract tables using Camelot.
    Try 'lattice' first (for ruled tables), then 'stream' (for whitespace tables).
    Returns list[List[str]] without any 'Table 1/2' headings.
    """
    all_rows = []

    def _process_tables(tables):
        rows = []
        for t in tables:
            df = t.df  # already a DataFrame-like
            for r in df.values.tolist():
                # Join cells, then re-split using our common delimiters to normalize
                row_clean = clean_and_split(" ".join([str(x) for x in r]))
                if row_clean:
                    rows.append(row_clean)
        return rows

    try:
        # lattice first
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
        all_rows.extend(_process_tables(tables))
    except Exception:
        pass

    try:
        # stream fallback
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
        all_rows.extend(_process_tables(tables))
    except Exception:
        pass

    return all_rows

# ---------------- Excel Output ----------------
def save_to_excel_autofit(rows: list) -> bytes:
    """
    Save rows to Excel with autofit columns, no header row.
    Returns XLSX bytes.
    """
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        sheet_name = "Sheet1"
        df.to_excel(writer, index=False, header=False, sheet_name=sheet_name)

        ws = writer.sheets[sheet_name]
        # Autofit each column based on content length
        for idx, col in enumerate(df.columns):
            # convert column to string for length calc
            try:
                max_len = int(df[col].astype(str).map(len).max())
            except Exception:
                max_len = 10
            # little padding and cap width
            ws.set_column(idx, idx, min(max_len + 2, 80))
    output.seek(0)
    return output.getvalue()

def process_pdf_to_xlsx_bytes(pdf_path: str) -> bytes:
    """
    Run both extractors, merge, deduplicate, export to Excel bytes.
    """
    text_rows = extract_text_blocks(pdf_path)
    table_rows = extract_tables(pdf_path)
    all_rows = text_rows + table_rows
    clean_rows = remove_duplicates(all_rows)
    if not clean_rows:
        # still produce a minimal file so client gets something
        clean_rows = [["No data extracted"]]
    return save_to_excel_autofit(clean_rows)

# ---------------- Streamlit App ----------------
st.set_page_config(page_title="PDF → Structured Excel", layout="wide")

if not st.session_state.authenticated:
    login()
else:
    st.title("📄 PDF → Structured Excel (Auto-fit, No Duplicates)")
    st.caption("Upload single/multiple PDFs or a ZIP. Single PDF → direct XLSX. Multiple/ZIP → ZIP of XLSX files.")

    uploaded_files = st.file_uploader(
        "Upload PDFs or a ZIP containing PDFs",
        type=["pdf", "zip"],
        accept_multiple_files=True
    )

    if uploaded_files:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Case 1: Single PDF => return XLSX directly
            if len(uploaded_files) == 1 and uploaded_files[0].name.lower().endswith(".pdf"):
                one = uploaded_files[0]
                pdf_path = os.path.join(tmpdir, one.name)
                with open(pdf_path, "wb") as f:
                    f.write(one.getbuffer())
                xlsx_bytes = process_pdf_to_xlsx_bytes(pdf_path)
                st.success("✅ Processed")
                st.download_button(
                    "📥 Download Excel",
                    data=xlsx_bytes,
                    file_name=os.path.splitext(one.name)[0] + ".xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            else:
                # Case 2: Multiple PDFs and/or a ZIP => Build a ZIP of XLSX files
                zip_output = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                added = 0
                with zipfile.ZipFile(zip_output.name, "w", zipfile.ZIP_DEFLATED) as zf:

                    def handle_pdf(path_on_disk: str, display_name: str):
                        nonlocal added
                        xbytes = process_pdf_to_xlsx_bytes(path_on_disk)
                        xlsx_name = os.path.splitext(display_name)[0] + ".xlsx"
                        zf.writestr(xlsx_name, xbytes)
                        added += 1

                    for uf in uploaded_files:
                        local_path = os.path.join(tmpdir, uf.name)
                        with open(local_path, "wb") as f:
                            f.write(uf.getbuffer())

                        if uf.name.lower().endswith(".pdf"):
                            handle_pdf(local_path, uf.name)

                        elif uf.name.lower().endswith(".zip"):
                            # Unpack ZIP and process any PDFs inside
                            with zipfile.ZipFile(local_path, "r") as inner:
                                safe_dir = os.path.join(tmpdir, "unzipped")
                                os.makedirs(safe_dir, exist_ok=True)
                                inner.extractall(safe_dir)
                                for root, _, files in os.walk(safe_dir):
                                    for name in files:
                                        if name.lower().endswith(".pdf"):
                                            pdf_path = os.path.join(root, name)
                                            # display name inside zip: flatten to basename
                                            handle_pdf(pdf_path, name)

                if added == 0:
                    st.warning("No PDFs found to process.")
                else:
                    st.success(f"✅ Processed {added} file(s). Download ZIP:")
                    with open(zip_output.name, "rb") as f:
                        st.download_button(
                            "📥 Download All (ZIP)",
                            data=f,
                            file_name="extracted_excels.zip",
                            mime="application/zip"
                        )

    with st.expander("ℹ️ Setup Notes"):
        st.markdown(
            "- Requires system packages: **poppler**, **tesseract-ocr**, **ghostscript** (for Camelot).\n"
            "- Python packages: `streamlit, pymupdf, pandas, camelot-py[cv], pdf2image, pytesseract, Pillow, xlsxwriter`.\n"
            "- This app avoids adding any 'Table 1/2' headings; only clean rows are exported.\n"
            "- Columns are auto-fitted to avoid cutoff."
    )
