from __future__ import annotations

from collections import Counter

from app.services.seed import TARGET_COUNTS, _load_sap_records, generate_dataset


def test_all_818_real_records_present_in_inventory():
    data = generate_dataset(42)
    assert sum(1 for row in data.inventory if row.get("sap_anchor")) == 818
    assert len({row["sap_source_id"] for row in data.inventory if row.get("sap_anchor")}) == 818


def test_total_inventory_positions_reach_15000():
    assert len(generate_dataset(42).inventory) == 15_000


def test_all_57_real_material_ids_present_in_skus():
    sap = _load_sap_records()
    data = generate_dataset(42)
    materials = {row["material"].strip() for row in sap}
    assert len(materials) == 57
    assert materials <= {sku["id"] for sku in data.skus}


def test_all_46_storage_locations_present_in_inventory():
    sap = _load_sap_records()
    data = generate_dataset(42)
    locations = {row["storagelocation"].strip() for row in sap}
    assert len(locations) == 46
    assert locations <= {row["storagelocation"] for row in data.inventory if row.get("sap_source_id")}


def test_fiscal_year_distribution_matches_real_ratios():
    years = Counter(row["fiscalyearofcurrentperiod"] for row in _load_sap_records())
    assert years == Counter({2022: 97, 2023: 214, 2024: 202, 2025: 146, 2026: 159})


def test_99_percent_records_have_unposted_count():
    rows = _load_sap_records()
    assert sum(row["dateoflastpostedcount"] == "00000000" for row in rows) >= 813


def test_deletion_flag_records_present():
    assert sum(row["deletionflag"] == "X" for row in _load_sap_records()) >= 4


def test_blocked_stock_records_present():
    rows = generate_dataset(42).inventory[:TARGET_COUNTS["sap_anchor_records"]]
    assert sum(float(row["blockedstock"]) > 0 for row in rows) >= 8


def test_no_material_id_has_trailing_whitespace():
    data = generate_dataset(42)
    assert all(row["material"] == row["material"].strip() for row in data.inventory if row.get("sap_source_id"))
    assert all(sku["id"] == sku["id"].strip() for sku in data.skus)


def test_plant_is_always_1400():
    assert all(row["plant"] == "1400" for row in generate_dataset(42).inventory if row.get("sap_source_id"))


def test_synthetic_supply_chain_entities_link_to_real_material_ids():
    data = generate_dataset(42)
    real_materials = {row["material"] for row in _load_sap_records()}
    assert {order["sku"] for order in data.inbound_orders} <= {sku["id"] for sku in data.skus}
    assert any(order["sku"] in real_materials for order in data.inbound_orders)


def test_existing_supply_chain_entity_counts_unchanged():
    data = generate_dataset(42)
    assert len(data.suppliers) == 200
    assert len(data.dispatches) == TARGET_COUNTS["dispatch_schedule"]
    assert len(data.workforce) == TARGET_COUNTS["workforce_logs"]
    assert len(data.documents) == TARGET_COUNTS["documents"]
    assert len(data.containers) == TARGET_COUNTS["containers"]


def test_dataset_is_reproducible_with_same_seed():
    first = generate_dataset(42)
    second = generate_dataset(42)
    assert first.inventory == second.inventory
    assert first.skus == second.skus
    assert first.inbound_orders == second.inbound_orders


def test_none_seed_generates_fresh_dataset():
    data = generate_dataset(None)
    assert data.seed is not None
    assert len(data.inventory) == 15_000


def test_non_sap_inventory_records_have_safe_default_sap_fields():
    rows = [row for row in generate_dataset(42).inventory if not row.get("sap_source_id")]
    assert rows
    assert all(row.get("sap_anchor") is False for row in rows)
    assert all(row.get("plant") is None or row.get("plant") == "1400" for row in rows)


def test_free_available_stock_is_not_always_zero_after_scaling():
    rows = generate_dataset(42).inventory
    assert any(float(row.get("freeavailablestock", 0)) > 0 for row in rows)
