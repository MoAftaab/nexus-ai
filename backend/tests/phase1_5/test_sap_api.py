from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_scan_exposes_sap_findings_and_inventory_fields():
    response = client.post("/api/scan")
    assert response.status_code == 200
    findings = client.get("/api/anomalies").json()["items"]
    assert any("SAP" in item["system"] or "Fiscal" in item["title"] or "Inventory" in item["title"] for item in findings)
    inventory = client.get("/api/data/inventory", params={"page_size": 1}).json()["items"]
    assert inventory and "storagelocation" in inventory[0]


def test_sap_finding_detail_keeps_evidence_and_cascade_contract():
    findings = client.get("/api/anomalies").json()["items"]
    sap = next(item for item in findings if "SAP" in item["system"] or "Fiscal" in item["title"])
    detail = client.get(f"/api/anomalies/{sap['id']}")
    assert detail.status_code == 200
    assert detail.json()["evidence"]
    assert detail.json()["cascade_nodes"]

