# NexusAI generated operational datasets

This folder deliberately contains the live, inspectable synthetic data used by the
dashboard. It is not a hard-coded UI fixture.

Current generated volume: 72,900 records across the following context-relevant
automotive supply-chain sources:

| File | Records |
| --- | ---: |
| `master_skus.csv` | 5,000 |
| `inventory_positions.csv` | 15,000 |
| `inbound_orders.csv` | 2,000 |
| `outbound_orders.csv` | 10,000 |
| `suppliers.csv` | 200 |
| `dispatch_schedule.csv` | 500 |
| `workforce_logs.csv` | 20,000 |
| `documents.csv` | 200 |
| `containers.csv` | 20,000 |

`manifest.json` records the exact seed and generation time. Regenerate the whole
operation with:

```powershell
cd backend
python scripts/generate_dataset.py --seed 20260720
```

The generator first creates valid source records and then injects realistic dirty-data
conditions. Detection, graph simulation, dashboard metrics, data APIs, and Markdown
knowledge preparation all derive from these files and persisted records.
