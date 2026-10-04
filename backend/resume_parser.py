from pathlib import Path
from pypdf import PdfReader
from docx import Document

def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if path.suffix.lower() == ".docx":
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    raise ValueError("Only PDF and DOCX files are supported.")
