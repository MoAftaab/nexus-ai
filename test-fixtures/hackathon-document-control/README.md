# Hackathon Document Control Fixtures

These small evidence packets are test inputs for the Document Control page. They
use identifiers and values from the official six-sheet Hackathon workbook. The
Participant Guide and Dataset Report remain reference documents; they are not
operational evidence packets.

## Test cases

| File | Expected result | Official context |
| --- | --- | --- |
| `01_orphan_material_x1.txt` | Attention; links multiple SAP sheets and `HAC-X1-MAT-999001-0` | Material is present in Inventory_Stock, Warehouse_Bin, and Deliveries_Dispatch but absent from Material_Master |
| `02_atp_shortfall_x2.csv` | Attention; links delivery, inventory, and material records and `HAC-X2-MAT-100003-0` | Dispatch demand exceeds available stock |
| `03_blocked_vendor_f2.csv` | Attention; links PO and vendor records and the blocked-vendor finding | `VEND-5000` has an open PO while procurement is blocked |
| `04_negative_stock_b1.csv` | Attention; links Inventory_Stock and `HAC-B1-MAT-100003-0` | Inventory has negative on-hand quantity |
| `05_clean_material.txt` | Clean; links official material and inventory records with no active finding | `MAT-100001` is a control record without a seeded finding |
| `06_missing_identifier.txt` | Attention; asks for a supported identifier | No material, plant, batch, delivery, PO, vendor, or bin can be linked |

Upload one file at a time in **Document control**. A Hackathon result should show
the source dataset, matched sheet and record IDs, exact record fields, and related
finding buttons. It should not report synthetic PPAP/VDA controls for these files.
