"""Extract plain text from the ERDC-CRREL AZCOT reports in docs/ into eda/reference/."""
from pathlib import Path

from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "eda" / "reference"
OUT.mkdir(exist_ok=True)

for pdf in sorted((REPO / "docs").glob("*.pdf")):
    reader = PdfReader(pdf)
    pages = [f"\n@@@ PAGE {i + 1} @@@\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages)]
    dest = OUT / (pdf.stem.replace(" ", "_") + ".txt")
    dest.write_text("".join(pages))
    print(f"{pdf.name}: {len(reader.pages)} pages -> {dest.relative_to(REPO)}")
