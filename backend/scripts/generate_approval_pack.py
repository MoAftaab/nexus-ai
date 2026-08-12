"""Generate the cross-site approval evidence pack from live seeded identifiers."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from app.services.seed import generate_dataset


ROOT = Path(__file__).resolve().parents[2] / "demo_documents" / "approval_pack"
XLSX_MANIFEST: list[dict[str, object]] = []


def pdf(path: Path, title: str, fields: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((52, 70), "NEXUSAI / EVIDENCE CONTROL", fontsize=10, color=(.55, .45, .23))
    page.insert_text((52, 112), title, fontsize=24, color=(.12, .09, .2))
    y = 158
    for label, value in fields.items():
        page.insert_text((52, y), f"{label}: {value}", fontsize=12, color=(.2, .17, .25))
        y += 28
    page.insert_text((52, 730), "Generated from live NexusAI seeded identifiers · demo evidence only", fontsize=9, color=(.45, .42, .48))
    document.save(path)
    document.close()


def xlsx(path: Path, title: str, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    XLSX_MANIFEST.append({"path": str(path), "title": title, "rows": rows})


def png(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 700), "#211b3b")
    draw = ImageDraw.Draw(image)
    draw.text((60, 60), "NEXUSAI / VISUAL EVIDENCE", fill="#eed593")
    draw.text((60, 125), title, fill="#f5f1e6")
    for index, line in enumerate(lines):
        draw.text((60, 210 + index * 52), line, fill="#d9d0c4")
    image.save(path)


def csv_file(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = [",".join(headers), *(" ,".join(str(value) for value in row) for row in rows)]
    path.write_text("\n".join(content).replace(" ,", ","), encoding="utf-8")


def main() -> None:
    data = generate_dataset(1234)
    sku = data.skus[0]["id"]
    second_sku = data.skus[1]["id"]
    po = data.inbound_orders[0]["id"]
    container = data.containers[0]["id"]
    supplier = next(item["name"] for item in data.suppliers if item["id"] == data.inbound_orders[0]["supplier"])
    batch = data.documents[0]["batch"]
    quantity = str(data.inbound_orders[0]["expected_qty"])
    today = date.today().isoformat()

    pdf(ROOT / "wolfsburg/ppap_gap/missing_ppap_delivery_note.pdf", "Delivery note / PPAP gap", {"Site": "wolfsburg", "SKU": sku, "Batch": batch, "Supplier": supplier, "Quantity": quantity, "Date": today, "Reference": po, "PPAP status": "MISSING"})
    pdf(ROOT / "wolfsburg/ppap_gap/signed_ppap_release_certificate.pdf", "Signed PPAP release certificate", {"Site": "wolfsburg", "SKU": sku, "Batch": batch, "Supplier": supplier, "Quantity": quantity, "Date": today, "Reference": f"PPAP-{po}", "PPAP status": "APPROVED / SIGNED"})
    csv_file(ROOT / "wolfsburg/cycle_count/cycle_count_variance.csv", ["site", "sku", "batch", "quantity_system", "quantity_counted", "date", "reference"], [["wolfsburg", sku, batch, quantity, str(max(0, int(quantity) - 4)), today, f"CC-{po}"]])
    xlsx(ROOT / "wolfsburg/cycle_count/reconciliation_journal.xlsx", "Cycle-count reconciliation journal", [["Site", "wolfsburg"], ["SKU", sku], ["Batch", batch], ["Supplier", supplier], ["Quantity", quantity], ["Date", today], ["Reference", f"JRN-{po}"], ["PPAP/VDA/SDS status", "PPAP approved; VDA verified; SDS not applicable"]])

    png(ROOT / "bratislava/vda_label/failed_vda_label_scan.png", "Failed VDA label scan", [f"Site: bratislava", f"SKU: {second_sku}", f"Batch: {batch}", f"Reference: VDA-{po}", "VDA status: FAILED / REPRINT REQUIRED"])
    pdf(ROOT / "bratislava/vda_label/reprint_verification.pdf", "VDA label reprint verification", {"Site": "bratislava", "SKU": second_sku, "Batch": batch, "Supplier": supplier, "Quantity": quantity, "Date": today, "Reference": f"VDA-REPRINT-{po}", "VDA status": "VERIFIED"})
    pdf(ROOT / "bratislava/hazmat/hazmat_without_sds.pdf", "Hazmat packet without SDS", {"Site": "bratislava", "SKU": sku, "Batch": batch, "Supplier": supplier, "Quantity": quantity, "Date": today, "Reference": f"HZ-{po}", "SDS status": "MISSING"})
    pdf(ROOT / "bratislava/hazmat/signed_sds_declaration.pdf", "Signed SDS declaration", {"Site": "bratislava", "SKU": sku, "Batch": batch, "Supplier": supplier, "Quantity": quantity, "Date": today, "Reference": f"SDS-{po}", "SDS status": "APPROVED / SIGNED"})

    xlsx(ROOT / "pune/lead_time/asn_lead_time_variance.xlsx", "ASN / lead-time variance", [["Site", "pune"], ["SKU", sku], ["Batch", batch], ["Supplier", supplier], ["Quantity", quantity], ["Date", today], ["Reference", f"ASN-{po}"], ["PPAP/VDA/SDS status", "PPAP verified; VDA verified; SDS not applicable"], ["Configured lead", "5 days"], ["Observed lead", "9 days"]])
    pdf(ROOT / "pune/lead_time/expedite_po_supplier_confirmation.pdf", "Expedite PO / supplier confirmation", {"Site": "pune", "SKU": sku, "Batch": batch, "Supplier": supplier, "Quantity": quantity, "Date": today, "Reference": f"EXP-{po}", "PPAP/VDA/SDS status": "PPAP verified; supplier confirmed expedite"})
    csv_file(ROOT / "pune/containers/overdue_container_ledger.csv", ["site", "container", "supplier", "sku", "batch", "overdue_hours", "date", "reference"], [["pune", container, supplier, sku, batch, "42", today, f"KLT-{container}"]])
    png(ROOT / "pune/containers/carrier_return_scan_receipt.png", "Carrier return-scan receipt", ["Site: pune", f"Container: {container}", f"SKU: {sku}", f"Batch: {batch}", f"Reference: RETURN-{container}", "Return scan: VERIFIED"])
    (ROOT / ".workbook_manifest.json").write_text(json.dumps(XLSX_MANIFEST, indent=2), encoding="utf-8")
    print(f"Generated approval pack at {ROOT}")


if __name__ == "__main__":
    main()
