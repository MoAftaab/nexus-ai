"""Export the generated operational twin into inspectable CSV datasets."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.services.seed import SyntheticDataset


DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"


def _write_csv(name: str, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    fields = list(records[0].keys())
    with (DATASETS_DIR / name).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def export_dataset(data: SyntheticDataset) -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv("master_skus.csv", data.skus)
    _write_csv("inventory_positions.csv", data.inventory)
    _write_csv("inbound_orders.csv", data.inbound_orders)
    _write_csv("outbound_orders.csv", data.outbound_orders)
    _write_csv("suppliers.csv", data.suppliers)
    _write_csv("dispatch_schedule.csv", data.dispatches)
    _write_csv("workforce_logs.csv", data.workforce)
    _write_csv("documents.csv", data.documents)
    _write_csv("containers.csv", data.containers)
    with (DATASETS_DIR / "manifest.json").open("w", encoding="utf-8") as output:
        json.dump({"seed": data.seed, "generated_at": data.generated_at.isoformat(), "tables": {"master_skus": len(data.skus), "inventory_positions": len(data.inventory), "inbound_orders": len(data.inbound_orders), "outbound_orders": len(data.outbound_orders), "suppliers": len(data.suppliers), "dispatch_schedule": len(data.dispatches), "workforce_logs": len(data.workforce), "documents": len(data.documents), "containers": len(data.containers)}}, output, indent=2)
