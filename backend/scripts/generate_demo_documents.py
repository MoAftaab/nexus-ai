"""Generate realistic demo documents wired to the live dataset's real identifiers.

Usage:  .nexus-env/Scripts/python.exe scripts/generate_demo_documents.py
Writes PDFs and a CSV into ../demo_documents/ ready for drag-and-drop in the
Document control page. One document is deliberately clean so the demo also
shows the system NOT crying wolf.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz

from app.config import get_settings
from app.services.operations import OperationsStore

OUT_DIR = Path(__file__).resolve().parents[2] / "demo_documents"


def write_pdf(path: Path, title: str, lines: list[str]) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), title, fontsize=16, fontname="helv")
    y = 110
    for line in lines:
        page.insert_text((72, y), line, fontsize=10, fontname="helv")
        y += 16
    document.save(path)
    document.close()


def main() -> None:
    store = OperationsStore(get_settings())
    data = store._dataset
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Delivery note missing PPAP (flags: PPAP + VDA gaps, links a real batch/SKU)
    packet = next((item for item in data.documents if not item["ppap_attached"]), data.documents[0])
    write_pdf(OUT_DIR / "delivery_note_missing_ppap.pdf", "DELIVERY NOTE — Nordwerk Components", [
        f"Batch: {packet['batch']}", f"Material: {packet['sku']}", "Quantity delivered: 480 EA",
        "Enclosures: commercial invoice, packing list.",
        "Note: quality approval paperwork to follow separately.",
    ])

    # 2. ASN referencing a real batch WITH its release evidence (clean — no findings)
    clean = next(item for item in data.documents if item["ppap_attached"])
    write_pdf(OUT_DIR / "asn_clean_with_ppap.pdf", "ADVANCED SHIPPING NOTICE", [
        f"Batch: {clean['batch']}", f"Material: {clean['sku']}", "Quantity: 320 EA",
        "PPAP approval: attached (rev C, signed).",
        "VDA label set: attached and verified at origin.",
    ])

    # 3. Supplier invoice, hazmat SKU, missing compliance wording (flags gaps)
    hazmat = next((sku for sku in data.skus if sku["storage_class"] == "hazmat"), data.skus[0])
    write_pdf(OUT_DIR / "invoice_hazmat_sku.pdf", "COMMERCIAL INVOICE — Helios Parts", [
        f"Item: {hazmat['id']} — {hazmat['description']}", "Quantity: 96 EA", "Unit price: EUR 42.10",
        "Incoterms: DAP Wolfsburg.", "Safety data sheet: not enclosed.",
    ])

    # 4. Cycle count sheet as CSV referencing real bins (parses as tabular text)
    rows = ["bin,sku,counted_qty,count_date"]
    for record in data.inventory[:6]:
        rows.append(f"{record['bin']},{record['sku']},{record['physical']},{data.generated_at.date().isoformat()}")
    (OUT_DIR / "cycle_count_sheet.csv").write_text("\n".join(rows), encoding="utf-8")

    print(f"Wrote 4 demo documents to {OUT_DIR}")
    print(" - delivery_note_missing_ppap.pdf  (flags PPAP + VDA gaps)")
    print(" - asn_clean_with_ppap.pdf         (clean — shows no false alarm)")
    print(" - invoice_hazmat_sku.pdf          (flags missing release evidence)")
    print(" - cycle_count_sheet.csv           (tabular ingestion)")


if __name__ == "__main__":
    main()
