# 🧠 NexusAI: The Complete System Bible & Metric Calculation Reference

---

## Executive Summary

**NexusAI** is an industrial-grade **Multi-Agent Supply-Chain Cascade Intelligence Platform** built to govern automotive manufacturing operations across enterprise boundaries (ERP, WMS, TMS, QMS, OMS, and Physical Sensor/Cycle Count streams). 

In modern just-in-sequence (JIS) and just-in-time (JIT) automotive assembly (e.g., Volkswagen Group plants such as Wolfsburg, Kassel, Bratislava, and Zwickau), operational records often drift silently between systems. A minor master-data discrepancy or a failed inventory movement journal propagates through bill-of-materials (BOM) trees, sequencing queues, and dispatch docks, culminating in production line stoppages costing up to **€4,200 per minute**.

NexusAI replaces slow, batch-oriented weekly reconciliation with real-time continuous drift detection, probabilistic graph cascade simulation, Monte-Carlo financial exposure quantification (€ loss modeling), role-based multi-tier change control governance with SHA-256 audit chaining, and closed-loop database remediation.

---

# Table of Contents
1. [Core Architectural Overview & Digital Twin Design](#1-core-architectural-overview--digital-twin-design)
2. [Executive & Operational Dashboard Metrics](#2-executive--operational-dashboard-metrics)
3. [Drift Detection Algorithms & Mathematical Formulas (All 20+ Detectors)](#3-drift-detection-algorithms--mathematical-formulas-all-20-detectors)
4. [Machine Learning Engine & Statistical Model Selection](#4-machine-learning-engine--statistical-model-selection)
5. [Graph Dependency Cascade & Monte Carlo Simulation Engine](#5-graph-dependency-cascade--monte-carlo-simulation-engine)
6. [Multi-Agent Specialist Reasoning Mesh](#6-multi-agent-specialist-reasoning-mesh)
7. [Document Parsing, Vision OCR & 3-Way Cross-System Verification](#7-document-parsing-vision-ocr--3-way-cross-system-verification)
8. [Role-Based Governance, Approval Matrix & Cryptographic Ledger](#8-role-based-governance-approval-matrix--cryptographic-ledger)
9. [Value Realization, Counterfactual Accounting & ROI Logic](#9-value-realization-counterfactual-accounting--roi-logic)
10. [End-to-End Real-World Industrial Use Cases](#10-end-to-end-real-world-industrial-use-cases)
11. [Metric Quick Reference Cheat Sheet](#11-metric-quick-reference-cheat-sheet)

---

# 1. Core Architectural Overview & Digital Twin Design

### 1.1 The Operational Twin (72,900 Active Records)
NexusAI maintains a synchronized digital twin representing real automotive manufacturing operations. The data topology consists of:

| Entity Category | Record Target Count | Canonical Source Systems | Description & Role |
| :--- | :--- | :--- | :--- |
| **Master SKUs** | $5,000$ records | SAP S/4HANA (MARA/MARC), WMS | Part numbers, family groups (Powertrain, Electronics, Interior, Chassis, Fluids), physical weights, fitment variants (LH/RH), hazmat classifications, storage bins. |
| **Inventory Positions** | $15,000$ positions | SAP S/4HANA (MARD), WMS, TMS, Cycle Count | Bin-level storage with 4-way truth tracking: WMS available, ERP book, TMS in-transit, and physical cycle count. |
| **SAP MARD Anchors** | $818$ real records | SAP S/4HANA Table `MARD` | Real-world automotive storage records covering 57 materials, 46 storage locations, fiscal periods, stock types (free, quality, blocked, transfer). |
| **Inbound Orders (POs)** | $2,000$ purchase orders | SAP MM / SRM, Supplier EDI | Purchase orders with expected quantities, receipt quantities, promised arrival dates, and QA inspection gates. |
| **Outbound Orders** | $10,000$ orders | OMS, SAP SD, Plant JIS Queue | Production plant demand orders with promised delivery timestamps, picking progress, priority tiers ($1$ to $10$). |
| **Dispatch Schedule** | $500$ shipments | TMS, Dock Scheduling | Outbound dock staging, vehicle capacities (kg), staged pallet weights, barcode label verification tallies. |
| **Workforce Logs** | $20,000$ shift logs | WMS Labor Management (LMS) | Hourly operator scan rates, picking/packing/replenishment tasks, exception counts, overtime hours. |
| **Documents** | $200$ compliance packets | QMS, Supplier Portal | Inbound shipping documents, PPAP declarations, VDA 4902 transport labels, SDS chemical sheets, invoices. |
| **KLT Containers** | $20,000$ pool units | Container Management (TMS) | Returnable Kleinladungsträger (KLT) transport boxes, tracking turnover and carrier return scan latency. |

---

# 2. Executive & Operational Dashboard Metrics

This section explains every key performance indicator (KPI) rendered across the NexusAI Command Center, Topbar, and Executive Deck.

---

### Metric 2.1: Open Exposure at Risk (`€`)

#### Meaning & Business Purpose
The total projected financial loss that the enterprise will incur if all currently open anomalies and supply chain disruptions propagate to their downstream consequences without intervention.

#### Mathematical Formula
$$\text{Exposure at Risk} = \sum_{i \in \mathcal{A}_{\text{open}}} \text{Impact}(i)$$

Where:
* $\mathcal{A}_{\text{open}} = \{ a \in \mathcal{A} \mid \text{Status}(a) \neq \text{"resolved"} \}$ is the set of all active, uncontained anomalies.
* $\text{Impact}(i)$ is the deterministic financial exposure calculated by the specific detector for anomaly $i$ in Euros (€).

#### Code Implementation (`operations.py`, `dashboardKpis.js`)
```python
open_items = [item for item in items if item.status != "resolved"]
exposure = sum(item.impact for item in open_items)
```

#### Industrial Use Case
Used by the **Supply Chain Director** and **Plant Operations Manager** during shift handover meetings to prioritize engineering and logistics interventions strictly by financial exposure.

---

### Metric 2.2: Line Readiness Index (`%`)

#### Meaning & Business Purpose
A normalized $0$ to $100\%$ operational score reflecting the overall health, stability, and unblocked capacity of factory assembly lines. A score of $100\%$ indicates zero high-risk blockers; deductions are applied proportionally to anomaly severity.

#### Mathematical Formula
$$\text{Readiness Index} = \max\left(0, \min\left(100, 100 - (9 \cdot N_{\text{critical}} + 4 \cdot N_{\text{high}} + 2 \cdot N_{\text{medium}})\right)\right)$$

Where:
* $N_{\text{critical}}$ is the number of active anomalies with severity `"critical"`.
* $N_{\text{high}}$ is the number of active anomalies with severity `"high"`.
* $N_{\text{medium}}$ is the number of active anomalies with severity `"medium"`.
* Low severity anomalies carry a weight of $0$ deductions.

#### Severity Weight Rationale
* **Critical ($-9\%$ per issue):** Represents immediate assembly line halt risks (e.g., JIS fitment mismatch staging for dispatch in $<2$ hours). 11 critical issues completely drop readiness to zero.
* **High ($-4\%$ per issue):** Significant operational risks (e.g., vehicle overload $>100\%$, supplier lead time drift $>3$ days, missing PPAP).
* **Medium ($-2\%$ per issue):** Contained non-conformances (e.g., hazmat flag discrepancies, delayed container return scans).

#### Code Implementation (`operations.py`)
```python
severity_counts = Counter(item.severity for item in open_items)
readiness = max(0, min(100, 
    100 
    - severity_counts.get("critical", 0) * 9 
    - severity_counts.get("high", 0) * 4 
    - severity_counts.get("medium", 0) * 2
))
```

---

### Metric 2.3: Cascades Contained (Count & Rate)

#### Meaning & Business Purpose
Tracks the exact number and percentage of identified supply chain faults that have been successfully resolved through verified source-system corrections and multi-tier approval sign-offs.

#### Mathematical Formulas
$$\text{Cascades Contained (Count)} = \sum_{i \in \mathcal{A}} \mathbb{I}(\text{Status}(i) = \text{"resolved"})$$

$$\text{Containment Rate (\%)} = \begin{cases} 
\text{round}\left( \frac{|\mathcal{A}_{\text{resolved}}|}{|\mathcal{A}|} \times 100 \right), & \text{if } |\mathcal{A}| > 0 \\
100\%, & \text{if } |\mathcal{A}| = 0
\end{cases}$$

Where $\mathbb{I}(\cdot)$ is the indicator function.

---

### Metric 2.4: Controls Available / Actionable Value (`€`)

#### Meaning & Business Purpose
The cumulative Euro value of financial exposure that can be immediately protected or has already been locked in by executing available corrective actions.

#### Mathematical Formula
$$\text{Controls Available} = \text{Value}_{\text{protected}} + \text{Value}_{\text{actionable}}$$

Where:
$$\text{Value}_{\text{protected}} = \sum_{a \in \mathcal{A}} \sum_{fx \in a.\text{actions}} \mathbb{I}(fx.\text{status} \in \{\text{"approved"}, \text{"applied"}\}) \cdot fx.\text{impact\_saved}$$
$$\text{Value}_{\text{actionable}} = \sum_{a \in \mathcal{A}_{\text{open}}} \sum_{fx \in a.\text{actions}} \mathbb{I}(fx.\text{status} = \text{"recommended"}) \cdot fx.\text{impact\_saved}$$

---

### Metric 2.5: Time to Impact Horizon & Urgent Window Counts

#### Meaning & Business Purpose
Categorizes anomalies by operational time remaining before physical disruption occurs on the shop floor or assembly dock.

#### Conversion & Bucketing Logic (`minutesToImpact`)
Text strings like `"1h 30m"`, `"2d 4h"`, `"1 shift"` are parsed into absolute minutes:
$$\text{Minutes}(d, h, m) = (d \times 1440) + (h \times 60) + m$$

| Horizon Bucket | Upper Bound | Urgency Category | Visual Color | Primary Action |
| :--- | :--- | :--- | :--- | :--- |
| **Within 2h** | $\le 120\text{ minutes}$ | Immediate Line-Side Blocker | Red (`#DA0C1F`) | Instant expedite / quarantine |
| **2h – 8h** | $\le 480\text{ minutes}$ | Same-Shift Critical | Coral (`#E67364`) | Rebalance shift assignments |
| **8h – 24h** | $\le 1440\text{ minutes}$ | Next-Day Horizon | Amber (`#FAAA3C`) | Reroute inbound transport |
| **Beyond 24h** | $> 1440\text{ minutes}$ | Strategic Planning Horizon | Teal (`#008C82`) | Standard change request cycle |

---

### Metric 2.6: System Risk Exposure Allocation (`% Share`)

#### Meaning & Business Purpose
When an anomaly crosses multiple systems (e.g. `ERP · WMS · TMS`), this metric decomposes and assigns fair financial exposure shares to each system to reveal where systemic data hygiene issues are concentrated.

#### Mathematical Formula
For an anomaly $i$ impacting systems $S_i = \{s_{i,1}, s_{i,2}, \dots, s_{i,k}\}$:
$$\text{Allocated Exposure}(s, i) = \frac{\text{Impact}(i)}{|S_i|}, \quad \forall s \in S_i$$
$$\text{Total System Exposure}(s) = \sum_{i \in \mathcal{A}_{\text{open}} \text{ s.t. } s \in S_i} \text{Allocated Exposure}(s, i)$$
$$\text{System Risk Share}(s) = \frac{\text{Total System Exposure}(s)}{\sum_{s'} \text{Total System Exposure}(s')} \times 100\%$$

---

# 3. Drift Detection Algorithms & Mathematical Formulas

NexusAI runs continuous background scanning across **20+ specialized detectors**. Every detector evaluates domain-specific physics and outputs explainable findings with exact financial exposure equations.

---

### 3.1 JIS Fitment Master Data Conflict Detector
* **Target System:** SAP ERP Master vs. High-Bay WMS.
* **Physics / Defect Mechanism:** High-velocity Just-In-Sequence (JIS) door panels and cockpit wiring harnesses require variant alignment (e.g. Left-Hand Drive `LH` vs. Right-Hand Drive `RH`). When WMS and ERP publish different revisions, incorrect parts are sequenced into dispatch racks.
* **Trigger Condition:**
  $$\text{sku}.\text{fitment\_wms} \neq \text{sku}.\text{fitment\_erp}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{JIS}} = (N_{\text{staged\_units}} \times 4,200) + 420,000$$
  * **Constants Explained:**
    * $€4,200$: The exact penalty per vehicle for delayed JIS station feed or manual off-line rectification.
    * $€420,000$: Fixed plant cost representing 100 minutes of main assembly line stoppage buffer (€4,200/min $\times$ 100 min).
* **Fix Action & Recovery:** Freeze JIS release, align WMS variant to ERP master, regenerate rack load sequence ($95\%$ value protected).

---

### 3.2 Master Weight Divergence Detector
* **Target System:** WMS Scales vs. SAP ERP vs. Carrier TMS.
* **Physics / Defect Mechanism:** Unit-of-measure conversion errors (e.g., lbs to kg, or individual piece vs. carton gross weight) result in misstated axle loads and carrier billing non-compliance.
* **Trigger Condition:**
  $$W_{\text{expected}} = \max(\text{ERP\_weight}, \text{TMS\_weight})$$
  $$\text{Variance Ratio } (\Delta_W) = \frac{|\text{WMS\_weight} - W_{\text{expected}}|}{W_{\text{expected}}} \ge 0.10 \quad (10\%)$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{weight}} = \lfloor 48,000 + (\Delta_W \times 85,000) \rfloor$$
  * **Constants Explained:**
    * $€48,000$: Base administrative and carrier re-weigh inspection penalty.
    * $€85,000$: Multiplier scaling potential road safety fines, axle overloading re-palletization, and demurrage.

---

### 3.3 Two-Factor Inventory Truth Divergence Detector
* **Target System:** WMS Available vs. SAP Book vs. Physical Cycle Count.
* **Physics / Defect Mechanism:** Failed receipt journals or unrecorded scrap create "ghost stock" where systems show inventory that does not physically exist in the bin.
* **Trigger Condition (Dual-Gated):**
  1. Spread Gate:
     $$\Delta_{\text{inv}} = \max(\text{wms}, \text{erp}, \text{physical}) - \min(\text{wms}, \text{erp}, \text{physical}) \ge 25\text{ units}$$
  2. Machine Learning Gate:
     $$\mathcal{P}_{\text{ML}}(\text{Fault} \mid \vec{x}) \ge 0.50 \quad (50\%)$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{inventory}} = \Delta_{\text{inv}} \times 4,400$$
  * **Constant Explained:** $€4,400$ represents the average value of 1 finished automotive module plus expediting freight to replace missing components.

---

### 3.4 Missing PPAP Compliance Detector
* **Target System:** Quality Management System (QMS) vs. Inbound ASN.
* **Physics / Defect Mechanism:** Production Part Approval Process (PPAP / VDA Level 3) sign-off is legally mandated before automotive safety components enter the assembly line.
* **Trigger Condition:**
  $$\text{document}.\text{ppap\_attached} = \text{False} \quad \land \quad \text{batch status} = \text{"Release Scheduled"}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{PPAP}} = \text{UniformRandom}(105,000, 158,000)$$
  * Reflects regulatory quarantine costs, third-party lab recertification, and batch holdback penalties.

---

### 3.5 Stale Supplier Lead-Time Drift Detector
* **Target System:** Purchasing Planning Master vs. Carrier Inbound Telemetry.
* **Physics / Defect Mechanism:** Supplier transit times degrade due to route constraints, but MRP planning parameters remain set to historical optimistic lead times.
* **Trigger Condition:**
  $$\text{Drift}_{\text{lead}} = \text{Actual\_Lead} - \text{Configured\_Lead} \ge 3.0\text{ days}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{lead}} = \lfloor \text{Drift}_{\text{lead}} \times 23,600 \rfloor$$
  * **Constant Explained:** $€23,600$ per day of buffer erosion, representing safety stock carrying costs and emergency air charter premiums.

---

### 3.6 VDA 4902 Barcode Verification Failure Detector
* **Target System:** Dispatch Staging Scanner vs. TMS Print Gateway.
* **Physics / Defect Mechanism:** Smudged thermal printheads or corrupted data matrices prevent automated high-speed gantries from scanning pallet labels.
* **Trigger Condition:**
  $$\text{Failed Labels} = \text{Total\_Labels} - \text{Verified\_Labels} > 0$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{VDA}} = \text{Failed Labels} \times 25,400$$
  * **Constant Explained:** OEM receiving gates reject non-scannable pallets with an immediate €25,400 rejection and administrative chargeback fee per unverified pallet.

---

### 3.7 Carrier Vehicle Overload Detector
* **Target System:** Outbound Load Planner vs. Transport Master.
* **Physics / Defect Mechanism:** Load consolidation schedules shipments that exceed gross vehicle weight ratings (GVWR).
* **Trigger Condition:**
  $$\text{Overload Ratio } (\mathcal{R}_{\text{load}}) = \frac{\text{Total Load (kg)}}{\text{Vehicle Capacity (kg)}} > 1.00$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{overload}} = \lfloor (\mathcal{R}_{\text{load}} - 1.00) \times 310,000 \rfloor$$
  * **Constant Explained:** $€310,000$ models highway safety enforcement impoundment, off-loading crane charges, and missed JIT delivery windows.

---

### 3.8 Workforce Productivity Shift Degradation Detector
* **Target System:** WMS Labor Management (LMS) Telemetry.
* **Physics / Defect Mechanism:** Operator scan exceptions, ergonomics bottlenecks, or mislabeled bins cause picking throughput to collapse while overtime spikes.
* **Trigger Condition:**
  $$\mu_{\text{recent\_rate}} < 0.70 \times \mu_{\text{historical\_rate}} \quad \land \quad \mu_{\text{recent\_overtime}} > \max(2.0, 2.5 \times \mu_{\text{historical\_overtime}})$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{workforce}} = \lfloor (\mu_{\text{historical\_rate}} - \mu_{\text{recent\_rate}}) \times 1,850 \rfloor$$
  * **Constant Explained:** $€1,850$ per lost unit/hour in unabsorbed warehouse overhead and overtime premiums.

---

### 3.9 Priority Outbound Order SLA Breach Detector
* **Target System:** Order Management (OMS) vs. WMS Fulfillment.
* **Physics / Defect Mechanism:** High-priority orders for downstream assembly lines remain unpicked inside their commitment window.
* **Trigger Condition:**
  $$T_{\text{now}} \le T_{\text{promised}} \le T_{\text{now}} + 12\text{h} \quad \land \quad \text{Picked\_Qty} < \text{Ordered\_Qty} \quad \land \quad \text{Priority} \le 2$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{SLA}} = (\text{Ordered\_Qty} - \text{Picked\_Qty}) \times 1,950$$
  * **Constant Explained:** OEM line shortage penalties of €1,950 per unfulfilled part unit.

---

### 3.10 Replenishment Coverage Gap Detector
* **Target System:** MRP Planning vs. Inbound PO Registry.
* **Physics / Defect Mechanism:** Available bin stock drops below reorder point, but no open Purchase Order exists.
* **Trigger Condition:**
  $$\sum \text{Stock}_{\text{on\_hand}} \le \text{Reorder\_Point} \quad \land \quad \text{SKU} \notin \{\text{SKUs on Open Inbound POs}\}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{replenish}} = (\text{Reorder\_Point} - \text{Total\_On\_Hand}) \times 2,150 + 38,000$$
  * **Constants Explained:**
    * $€2,150$: Unit production replacement cost.
    * $€38,000$: Expedited supplier tooling setup and rapid-freight mobilization fee.

---

### 3.11 Returnable Container (KLT) Overdue Scan Detector
* **Target System:** Returnable Packaging Ledger vs. Carrier EDI.
* **Trigger Condition:**
  $$\text{Container}.\text{overdue\_hours} > 24\text{ hours}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{KLT}} = N_{\text{overdue\_containers}} \times 720$$
  * **Constant Explained:** $€720$ demurrage fee and replacement cost per serialized automotive KLT tote.

---

### 3.12 SAP Fiscal Year Desynchronization Detector
* **Target System:** SAP Table `MARD-GJAHR` (Fiscal Year).
* **Physics / Defect Mechanism:** Storage records stuck in prior fiscal periods (e.g. 2022, 2023, 2024, 2025) reject automated goods receipts (MIGO) and goods issues (GI).
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{SAP\_FY}} = \min(85,000, 15,000 + N_{\text{locations}} \times 1,500)$$
  * **Severity Matrix:** FY2022 $\to$ Critical, FY2023 $\to$ High, FY2024 $\to$ Medium, FY2025 $\to$ Low.

---

### 3.13 SAP Unreconciled Physical Inventory Audit Detector
* **Target System:** SAP Table `MARD-DLINP` (Date of Last Posted Count).
* **Trigger Condition:**
  $$\text{DLINP} \in \{\text{null}, \text{"00000000"}\} \quad \lor \quad (T_{\text{now}} - \text{DLINP}) > 365\text{ days}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{SAP\_count}} = \min(120,000, 25,000 + N_{\text{unposted}} \times 100)$$

---

### 3.14 SAP Blocked & Restricted Stock Detector
* **Target System:** SAP Table `MARD-SPEME` (Blocked) & `MARD-INSME` (Quality Inspection).
* **Trigger Condition:**
  $$(\text{SPEME} > 0 \lor \text{INSME} > 0) \quad \land \quad \text{LABST (Free Available)} \le 0$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{SAP\_blocked}} = \min(95,000, 18,000 + Q_{\text{blocked\_units}} \times 2,000)$$

---

### 3.15 SAP Deletion & Maintenance Flag Detector
* **Target System:** SAP Table `MARD-LVORM` (Deletion Flag) & `MARD-PSTAT` (Maintenance Status).
* **Trigger Condition:**
  $$(\text{LVORM} = \text{"X"} \lor \text{PSTAT} = \text{"D"}) \quad \land \quad \text{LABST} > 0$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{SAP\_deletion}} = \min(50,000, 10,000 + N_{\text{records}} \times 3,000)$$

---

### 3.16 SAP Storage Location Fragmentation Detector
* **Target System:** SAP Table `MARD-LGORT` (Storage Location).
* **Trigger Condition:**
  $$\text{Material has } > 15 \text{ distinct zero-stock storage locations in } \text{MARD}$$
* **Mathematical Exposure Formula (€):**
  $$\text{Impact}_{\text{SAP\_frag}} = \min(45,000, 12,000 + N_{\text{zero\_locations}} \times 1,000)$$

---

# 4. Machine Learning Engine & Statistical Model Selection

To prevent false alarms in inventory reconciliation, NexusAI embeds an automated Machine Learning benchmarking and inference engine (`ml_detection.py`).

```
                              ┌────────────────────────────────────────┐
                              │     Inventory Records (WMS, ERP, Phys) │
                              └───────────────────┬────────────────────┘
                                                  │
                                                  ▼
                              ┌────────────────────────────────────────┐
                              │  7-Dimensional Feature Extractor       │
                              │  [w, e, p, spread, |w-e|, |e-p|, ratio]│
                              └───────────────────┬────────────────────┘
                                                  │
                      ┌───────────────────────────┼───────────────────────────┐
                      ▼                           ▼                           ▼
          ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
          │ Extra Trees Classifier│   │ Random Forest Class.  │   │ Hist Gradient Boost   │
          │ (180 Trees, Balanced) │   │ (180 Trees, Balanced) │   │ (180 Iter, MaxLeaf 18)│
          └───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
                      │                           │                           │
                      └───────────────────────────┼───────────────────────────┘
                                                  │
                                                  ▼
                              ┌────────────────────────────────────────┐
                              │  F1 Benchmark & Selection Gate         │
                              │  (Prioritizes F1 over raw Accuracy)    │
                              └───────────────────┬────────────────────┘
                                                  │
                                                  ▼
                              ┌────────────────────────────────────────┐
                              │  Winning Model Persisted & Scored      │
                              │  Predicts P(Anomaly | Record) >= 0.50  │
                              └────────────────────────────────────────┘
```

### 4.1 Feature Vector Construction
For each inventory record containing WMS count ($w$), ERP count ($e$), and Physical count ($p$), the engine constructs a 7-dimensional engineered feature vector $\vec{x}$:

$$\vec{x} = \begin{bmatrix}
x_1 \\ x_2 \\ x_3 \\ x_4 \\ x_5 \\ x_6 \\ x_7
\end{bmatrix} = \begin{bmatrix}
w \\
e \\
p \\
\max(w, e, p) - \min(w, e, p) \\
|w - e| \\
|e - p| \\
\frac{\max(w, e, p) - \min(w, e, p)}{\max\left(1, \frac{w + e + p}{3}\right)}
\end{bmatrix}$$

* **Feature $x_7$ (Relative Variance Ratio):** Ensures that a 20-unit spread on a 500-unit bin ($4\%$ variance) is treated differently than a 20-unit spread on a 25-unit bin ($80\%$ variance).

### 4.2 Candidate Model Roster & Hyperparameters
1. **ExtraTreesClassifier (Selected Top Performer):**
   * `n_estimators = 180`, `min_samples_leaf = 2`, `class_weight = "balanced"`, `n_jobs = -1`.
2. **RandomForestClassifier:**
   * `n_estimators = 180`, `min_samples_leaf = 2`, `class_weight = "balanced"`, `n_jobs = -1`.
3. **HistGradientBoostingClassifier:**
   * `max_iter = 180`, `learning_rate = 0.08`, `max_leaf_nodes = 18`.

### 4.3 Model Selection Criterion (Why F1-Score is Primary)
$$\text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}} = \frac{2 \cdot \text{TP}}{2 \cdot \text{TP} + \text{FP} + \text{FN}}$$

In industrial supply chains, genuine inventory corruption is rare ($\sim 18\%$ in calibration sets). Standard accuracy would reward a naive classifier that predicts "Normal" for 100% of records. The engine ranks candidates by:
$$\text{Rank Criteria} = (\text{F1}, \text{Accuracy}, \text{Model Name})$$

---

# 5. Graph Dependency Cascade & Monte Carlo Simulation Engine

NexusAI models downstream ripple effects using a **Directed Acyclic Graph (DAG)** $\mathcal{G} = (\mathcal{V}, \mathcal{E})$ powered by NetworkX and runs a **1,000-trial Monte-Carlo simulation** (`cascade_engine.py`) to determine propagation probabilities and tail financial risk.

```
       [Source Fault]
      (e.g., Master Fitment)
             │
             │ P(e1) = 93%
             ▼
    [Process Disruption]
    (JIS Sequence Builder)
             │
             │ P(e2) = 88%
             ▼
     [Logistics Node]
     (Dock 7 Staging)
             │
             │ P(e3) = 76%
             ▼
    [Outcome / Impact]
   (Assembly Line Feed)
 ───> €4,200/min Line Halt
```

### 5.1 Monte Carlo Simulation Algorithm
For an anomaly with graph $\mathcal{G}$, root nodes $\mathcal{R} = \{v \in \mathcal{V} \mid \text{in\_degree}(v) = 0\}$, and trials $M = 1,000$:

```python
for trial in 1 .. M:
    reached = set(R)
    queue = list(R)
    while queue is not empty:
        source = queue.pop(0)
        for (source, target, probability) in G.out_edges(source):
            if target not in reached and UniformRandom(0, 1) <= probability:
                reached.add(target)
                queue.append(target)
    
    trial_impact = sum(node.impact for node in reached if node.kind == "outcome")
    trial_impacts.append(trial_impact)
```

### 5.2 Output Statistical Metrics

#### 1. Propagation Probability ($P_{\text{prop}}$):
$$P_{\text{prop}} = \frac{1}{M} \sum_{m=1}^M \mathbb{I}(\text{trial\_impact}_m > 0)$$

#### 2. Expected Financial Impact ($\mathbb{E}[\text{Impact}]$):
$$\mathbb{E}[\text{Impact}] = \frac{1}{M} \sum_{m=1}^M \text{trial\_impact}_m$$

#### 3. P90 Financial Tail Risk ($\text{Impact}_{\text{P90}}$):
Let $\text{trial\_impacts}_{\text{sorted}}$ be the sorted array of trial impacts in ascending order.
$$\text{Impact}_{\text{P90}} = \text{trial\_impacts}_{\text{sorted}}[\lfloor 0.90 \times M \rfloor]$$
* **Business Meaning:** In $90\%$ of simulated real-world scenarios, the financial loss will not exceed this figure. This forms the Value-at-Risk (VaR) metric for executive capital reserve allocation.

### 5.3 Counterfactual "What-If" Analysis Formula
When evaluating a proposed remediation action with stated confidence $C \in [0, 100]\%$, the engine applies an edge damping factor:
$$\text{Residual Risk Factor} = 1 - \frac{C}{100}$$
$$\text{Probability}'(e) = \max\left(1\%, \text{round}\left(\text{Probability}(e) \times \text{Residual Risk Factor}\right)\right)$$

The **Expected Impact Avoided (ROI)** is calculated by re-simulating the damped graph:
$$\text{Impact Avoided} = \mathbb{E}[\text{Impact}]_{\text{baseline}} - \mathbb{E}[\text{Impact}]_{\text{mitigated}}$$

---

# 6. Multi-Agent Specialist Reasoning Mesh

NexusAI deploys a multi-agent AI mesh powered by calibrated GPT-5.4-mini instances (`agent_mesh.py`) running in parallel with structured handoff protocols.

```
                     ┌──────────────────────────────┐
                     │   User / Operator Inquiry    │
                     └──────────────┬───────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │ Sentinel Agent│       │Correlator Agt │       │ Cascade Agent │
    │  (Detection)  │       │   (Linkage)   │       │ (Simulation)  │
    └───────┬───────┘       └───────┬───────┘       └───────┬───────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    │ Handoff Notes
            ┌───────────────────────┴───────────────────────┐
            │                                               │
            ▼                                               ▼
    ┌───────────────┐                               ┌───────────────┐
    │  Impact Agent │                               │   Fix Agent   │
    │(Quantification│                               │(Control Design│
    └───────┬───────┘                               └───────┬───────┘
            │                                               │
            └───────────────────────┬───────────────────────┘
                                    │ Specialist Syntheses
                                    ▼
                    ┌──────────────────────────────┐
                    │  Control Tower Orchestrator  │
                    │ (Synthesized Decision Answer)│
                    └──────────────────────────────┘
```

| Agent Specialist | Domain & Responsibility | Prompt Strategy & Guardrails | Temperature |
| :--- | :--- | :--- | :--- |
| **1. Sentinel** | Statistical signal detection, threshold analysis, ML score verification. | Classifies signals into `CONFIRMED` vs. `NEEDS-VERIFICATION`. Zero tolerance for ungrounded citations. | $0.10$ |
| **2. Correlator** | Cross-system entity linkage (ERP SKU $\leftrightarrow$ WMS Bin $\leftrightarrow$ TMS Carrier). | Identifies common root-cause entities connecting seemingly independent anomalies across plants. | $0.15$ |
| **3. Cascade** | Graph topology traversal, propagation bottleneck identification. | Identifies specific pinch-point processes (e.g. JIS sequence builder) where risk escalates. | $0.15$ |
| **4. Impact / Economist** | Financial quantification, Monte Carlo P90 interpretation, SLA liability. | Explains cost components (€ line halt, labor overtime, expediting penalties) in business language. | $0.20$ |
| **5. Fix / Resolver** | Control design, step-by-step standard operating procedure (SOP). | Drafts actionable remediation steps with role ownership, ETA, and residual risk assessment. | $0.15$ |
| **6. Orchestrator** | Synthesis & executive communication. | Combines all 5 specialist handoffs into a unified, executive-ready response. | $0.20$ |

---

# 7. Document Parsing, Vision OCR & 3-Way Cross-System Verification

NexusAI features an intelligent document processing pipeline (`document_parser.py`, `operations.py`) that ingests physical paperwork and verifies it against live system truth.

```
 ┌───────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
 │ Inbound Logistics PDF │      │ Barcode / Label Image │      │ Excel Cycle Count CSV │
 └───────────┬───────────┘      └───────────┬───────────┘      └───────────┬───────────┘
             │                              │                              │
             ▼                              ▼                              ▼
 ┌───────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
 │ PyPDF / PyMuPDF OCR   │      │ LLM Vision Extractor  │      │ OpenPyXL Structured   │
 └───────────┬───────────┘      └───────────┬───────────┘      └───────────┬───────────┘
             │                              │                              │
             └──────────────────────────────┼──────────────────────────────┘
                                            │ Extracted Operational Fields
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │   Automated 3-Way Cross-System Verification   │
                    │   • PDF Data vs. SAP Purchase Order (PO)      │
                    │   • Barcode Matrix vs. WMS Master Weight      │
                    │   • Attached PPAP/VDA vs. QMS Release Gates   │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │ Generated Document Mismatch & Attention Flags │
                    └───────────────────────────────────────────────┘
```

### Document Inspection Rules
1. **PPAP Gate Verification:** Checks if the inbound ASN contains an approved PPAP Level 3 document reference. If absent for a safety-critical part, QMS quarantine gate is locked.
2. **VDA 4902 Label Compliance:** Verifies that transport labels contain standard VDA barcodes for automated high-bay warehouse scanning.
3. **Quantity & SKU Reconciliation:** Compares document item quantities against SAP PO line items; discrepancies $>0$ trigger receipt holds.

---

# 8. Role-Based Governance, Approval Matrix & Cryptographic Ledger

To ensure zero unauthorized database mutations in regulated environments, NexusAI implements a **4-Tier Role-Based Access Control (RBAC)** approval workflow (`change_control.py`).

```
  Level 1: Draft Creation          Level 2: Operational Review        Level 3: Management Sign-off       Level 4: Executive Authority
┌───────────────────────────┐    ┌───────────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
│    Operations Operator    │───>│      Operations Lead      │─────>│    Operations Manager     │─────>│   Supply Chain Director   │
│ • Detects anomaly drift   │    │ • Approves Low-Risk (<25k)│      │ • Approves Med-Risk (<100k│      │ • Approves High-Risk (100k│
│ • Generates Change Draft  │    │ • Review SLA: 12 Hours    │      │ • Review SLA: 24 Hours    │      │ • Approves Critical (250k+)
│ • CANNOT self-approve     │    └───────────────────────────┘      └─────────────┬─────────────┘      └───────────────────────────┘
└───────────────────────────┘                                                     │
                                                                                  │ (If Regulated / PPAP)
                                                                                  ▼
                                                                    ┌───────────────────────────┐
                                                                    │Quality & Compliance Offic.│
                                                                    │ • Mandatory PPAP/Hazmat   │
                                                                    │ • Review SLA: 8 Hours     │
                                                                    └───────────────────────────┘
```

### 8.1 Multi-Tier Approval Authority Matrix

| User Role | Hierarchy Tier | Approval Authority Threshold | Mandatory Involvement Triggers | Review SLA |
| :--- | :---: | :--- | :--- | :--- |
| **Operations Operator** | Level 1 | **Cannot Approve** (Draft Creator only) | Draft creator for all change requests. | — |
| **Operations Lead** | Level 2 | Low Risk ($< €25,000$) | Minor inventory adjustments, bin slotting updates. | 12 Hours |
| **Operations Manager** | Level 3 | Medium Risk ($€25,000 - €99,999$) | Lead-time updates, multi-bin reconciliations, Stage 1 for High/Critical. | 24 Hours |
| **Quality & Compliance Officer** | Level 3 (Special) | Regulatory Gatekeeper | Mandatory for any PPAP, Hazmat, SDS, or VDA compliance item. | 8 Hours |
| **Supply Chain Director** | Level 4 | High ($€100\text{k}+$) & Critical ($€250\text{k}+$) | Final executive sign-off for assembly line halt risks. | 48 Hours |

### 8.2 Separation of Duties Guardrail
$$\text{Requester}(CR) \cap \text{Approvers}(CR) = \emptyset$$
Requesters are strictly forbidden from approving their own change requests. Any self-approval attempt raises a `PermissionError`.

### 8.3 SHA-256 State Snapshots & Cryptographic Hash Chaining
Every change request captures three complete state snapshots:
1. `before_snapshot`: Canonical JSON state of affected database rows before changes.
2. `proposed_snapshot`: Exact fields and proposed replacement values.
3. `after_snapshot`: Post-execution verified database state.

#### Hash Chaining Formula (`_audit`):
$$\text{Payload Hash } (H_{\text{payload}}) = \text{SHA-256}\left(\text{JSON}_{\text{canonical}}(\text{event\_data})\right)$$
$$\text{Chain Hash } (H_{\text{current}}) = \text{SHA-256}\left(H_{\text{prior}} \mathbin{\Vert} H_{\text{payload}} \mathbin{\Vert} T_{\text{timestamp}}\right)$$
* Root Genesis Event: $H_{\text{prior}} = \text{"GENESIS"}$.
* Any modification of historical audit logs breaks the cryptographic chain verification (`verify_audit_chain` returns `False`).

---

# 9. Value Realization, Counterfactual Accounting & ROI Logic

NexusAI enforces mathematical counterfactual accounting (`operations.py`, `dashboardKpis.js`) to prove financial savings to auditors.

### 9.1 Verified Value Protected (`€`)
$$\text{Value Protected} = \sum_{a \in \mathcal{A}_{\text{resolved}}} \text{Impact}(a)$$
* **Rule:** A finding's full exposure value is credited to the value ledger **exactly once**, only after **all** required fix actions are approved and source database records are verified clean.

### 9.2 Annualized Operational ROI
Assuming a standard 3-shift per day automotive manufacturing operation ($1,095$ shifts per year):
$$\text{Annualized Value (€/year)} = \text{Value Protected (Current Shift)} \times 3 \times 365$$

### 9.3 Operational Speed Multiplier
$$\text{Manual Cadence} = 7 \text{ days} = 10,080 \text{ minutes}$$
$$\text{NexusAI Detection Cadence} = 4 \text{ minutes}$$
$$\text{Speed Multiplier} = \frac{10,080 \text{ min}}{4 \text{ min}} = 2,520\times \text{ faster}$$

---

# 10. End-to-End Real-World Industrial Use Cases

### Use Case 1: Preventing a Just-In-Sequence (JIS) Line Stoppage
* **Context:** Wolfsburg Plant, Golf 8 assembly line.
* **Incident:** Master data publish job misaligns door harness fitment (WMS has `LH`, SAP ERP has `RH`). 140 harnesses are staged for departure at Dock 7 in 1 hour 45 minutes.
* **NexusAI Action:**
  1. *Sentinel Detector* flags fitment mismatch; calculates **€1,008,000** exposure at risk.
  2. *Cascade Engine* simulates $93\% \to 88\% \to 76\%$ edge propagation to assembly feed.
  3. *Operator* creates Change Request `CR-JIS-001`.
  4. *Manager* and *Director* approve multi-tier request.
  5. *Closed-Loop Engine* republishes WMS master, regenerates rack sequence, and records €1,008,000 in protected value on the ledger.

### Use Case 2: Inbound Chemical Hazmat Compliance Gate
* **Context:** Kassel Component Facility.
* **Incident:** Coolant additive delivery arrives with storage class `hazmat`, but outbound transport safety flag is disabled (`False`).
* **NexusAI Action:**
  1. *Compliance Detector* flags hazmat mismatch (€42,000 exposure).
  2. *Quality & Compliance Officer* receives high-priority notification.
  3. Change request approved, SDS safety flags synchronized across ERP and WMS, preventing regulatory fine and transport carrier refusal.

---

# 11. Metric Quick Reference Cheat Sheet

| Metric / Parameter | Value / Formula | Target / Normal Range | Interpretation |
| :--- | :--- | :--- | :--- |
| **Readiness Index** | $100 - 9N_{\text{crit}} - 4N_{\text{high}} - 2N_{\text{med}}$ | $\ge 85\%$ | Operating posture of assembly facilities. |
| **JIS Halt Unit Cost** | $€4,200 / \text{unit}$ | — | Penalty per mis-sequenced vehicle. |
| **Line Stoppage Buffer**| $€420,000$ | — | Fixed 100-minute line-stop baseline cost. |
| **Weight Variance Gate**| $\ge 10\%$ spread | $< 2\%$ | Threshold for master weight divergence. |
| **Inventory Spread Gate**| $\ge 25$ units | $0$ units | Discrepancy between WMS, ERP, Physical. |
| **ML Anomaly Threshold**| $P(\text{fault}) \ge 0.50$ | $< 0.10$ | ExtraTrees classifier anomaly probability. |
| **Monte Carlo Trials** | $1,000$ iterations | $1,000$ | Standard statistical confidence sample. |
| **P90 Tail Risk** | 90th percentile impact | — | Value-at-Risk for capital protection. |
| **Audit Chaining** | SHA-256 hash linked | $100\%$ Valid | Tamper-evident governance proof. |

---
_Document Version: 2026.08.26 · NexusAI Multi-Agent Autonomous Supply Chain Core Architecture Reference Manual_
