from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture
def sap_record():
    def factory(**overrides):
        record = {
            "id": "SAP-1",
            "sku": "0DD300040E",
            "material": "0DD300040E",
            "plant": "1400",
            "storagelocation": "FBM1",
            "maintenancestatus": "DL",
            "deletionflag": "",
            "fiscalyearofcurrentperiod": 2026,
            "currentperiod": "12",
            "freeavailablestock": 10,
            "stockintransfer": 0,
            "stockinqualityinspection": 0,
            "blockedstock": 0,
            "blockedstockreturns": 0,
            "dateoflastpostedcount": "20260601",
            "last_count": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "baseunit": "ST",
            "instance": "Kassel",
        }
        record.update(overrides)
        return record

    return factory
