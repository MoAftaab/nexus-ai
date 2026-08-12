import { useMemo, useState } from 'react'
import { BookOpen, Boxes, Database, Factory, Network, Search, Cpu } from 'lucide-react'

const GROUPS = [
  {
    id: 'systems',
    icon: Boxes,
    title: 'The systems we watch',
    intro: 'A warehouse never runs on one system. Each keeps its own copy of the truth — and NexusAI exists because those copies drift apart.',
    terms: [
      { term: 'ERP', full: 'Enterprise Resource Planning', simple: 'The company’s central business system — purchasing, finance, planning. Thinks in orders and money.', here: 'One of the three "truths" we cross-check. When ERP and WMS disagree on stock or weight, that’s a finding.' },
      { term: 'WMS', full: 'Warehouse Management System', simple: 'Runs the physical warehouse: which bin holds what, who picks what, in what order. Thinks in bins and scans.', here: 'Usually the system closest to physical reality — but not immune to bad master data.' },
      { term: 'TMS', full: 'Transport Management System', simple: 'Plans trucks, routes and freight costs. Thinks in kilograms, pallets and departure slots.', here: 'A wrong weight in TMS means miscalculated loads and freight bills — one of our seeded defects.' },
      { term: 'OMS', full: 'Order Management System', simple: 'Tracks customer orders from placement to delivery, including the promised delivery deadline.', here: 'Source of the promised departure time behind our SLA-risk findings.' },
      { term: 'QMS', full: 'Quality Management System', simple: 'Holds quality approvals and certificates. Nothing ships to an automotive plant without its paperwork.', here: 'Where the release gate blocks a batch when its PPAP evidence is missing.' },
    ],
  },
  {
    id: 'automotive',
    icon: Factory,
    title: 'Automotive logistics language',
    intro: 'Our demo warehouse supplies a car plant. Automotive supply chains are the most demanding in logistics — these are their rules.',
    terms: [
      { term: 'JIT', full: 'Just-In-Time', simple: 'Parts arrive right when they’re needed — no warehouse full of buffer stock.', here: 'Why small data errors are dangerous: there’s no slack to absorb them.' },
      { term: 'JIS', full: 'Just-In-Sequence', simple: 'Stricter than JIT: parts must arrive in the exact order cars come down the line. Car 4711 is red with left-hand drive? Rack position 1 must hold exactly that harness.', here: 'Our highest-impact finding: ERP and WMS disagree on a part variant, so the sequence builder loads the wrong one — discovered only at line-side.' },
      { term: 'SKU', full: 'Stock Keeping Unit', simple: 'One unique product variant. A left-hand harness and its right-hand twin are two different SKUs.', here: 'The basic unit all our master data and inventory positions hang off.' },
      { term: 'SLA', full: 'Service Level Agreement', simple: 'The contractual promise — usually a delivery deadline. Missing one costs penalties and trust.', here: 'The escalation agent predicts breaches before they happen, while there’s still time to expedite.' },
      { term: 'PPAP', full: 'Production Part Approval Process', simple: 'The evidence pack proving a supplier’s part meets spec. No approval, no release — full stop.', here: 'The document agent flags batches sitting in quarantine without it.' },
      { term: 'VDA', full: 'Verband der Automobilindustrie', simple: 'The German automotive industry association. Its standardized transport labels make racks machine-readable across companies.', here: 'Failed VDA label verification is our dispatch-readiness finding.' },
      { term: 'ASN', full: 'Advanced Shipping Notice', simple: 'The digital "your delivery is coming" message with contents, quantities and batches.', here: 'One of the document types the ingestion pipeline parses and cross-checks.' },
      { term: 'KLT', full: 'Kleinladungsträger (small load carrier)', simple: 'The standardized stackable plastic boxes automotive parts travel in. Expensive, reusable, and constantly lost.', here: 'The container-tracking agent notices when return scans go missing.' },
      { term: 'Hazmat', full: 'Hazardous Materials', simple: 'Substances with legal handling rules — chemicals, fluids, batteries. Wrong storage or transport is a safety and compliance violation.', here: 'A compliance finding: a SKU stored as hazmat whose handling flag was silently switched off.' },
    ],
  },
  {
    id: 'data',
    icon: Cpu,
    title: 'Data quality & detection',
    intro: 'The core problem: the same fact recorded three times, three ways. Detection is how we find the drift without anyone labeling it.',
    terms: [
      { term: 'Master data', full: null, simple: 'The reference facts everything relies on: a part’s weight, dimensions, variant, storage class. Boring — until it’s wrong, and every process trusting it inherits the error.', here: 'Weight and fitment conflicts across ERP/WMS/TMS are master-data findings.' },
      { term: 'Reconciliation', full: null, simple: 'Comparing copies of the same fact across systems and working out which one is right.', here: 'The Reconciliation page shows WMS vs ERP vs physical count side by side, with the drift timeline.' },
      { term: 'Cycle count', full: null, simple: 'Physically counting a bin’s contents to check the system numbers. The ground truth of a warehouse.', here: 'The "physical" column — when it disagrees with both WMS and ERP, the journals are broken.' },
      { term: 'Lead time', full: null, simple: 'How long a supplier takes from order to delivery. Planning trusts this number to time everything.', here: 'A supplier configured at 3 days but actually delivering in 8 makes every plan silently wrong.' },
      { term: 'Anomaly score', full: null, simple: 'A 0–100% rating from our ML model of how abnormal an inventory position looks, based on the spread between its recorded quantities.', here: 'A finding needs BOTH a big absolute spread AND a high model score — so statistical noise never pages an operator.' },
      { term: 'F1 score', full: null, simple: 'An accuracy measure for rare-event detection that balances "did we find the real faults?" against "did we cry wolf?". Plain accuracy would score 99% by ignoring every fault.', here: 'Why F1 — not accuracy — picks which of the three trained models goes live (see System health).' },
    ],
  },
  {
    id: 'cascade',
    icon: Network,
    title: 'Cascade & impact modeling',
    intro: 'A data error is never just a data error — it travels. This is the vocabulary of how we predict where it lands and what it costs.',
    terms: [
      { term: 'Cascade', full: null, simple: 'The chain reaction from one root cause: wrong weight → wrong load plan → failed compliance check → delayed truck. Each arrow is one hop.', here: 'The Cascade map draws this chain as a graph you can drag, inspect and simulate.' },
      { term: 'Propagation probability', full: null, simple: 'The percentage on each edge: how likely the problem jumps to the next step, given it reached the current one. Multiplying along the chain is why far-away consequences are less certain.', here: 'Edges above 70% render gold and animated — the dangerous route at a glance.' },
      { term: 'Monte-Carlo simulation', full: null, simple: 'Instead of one guess, roll the dice 1,000 times: each trial randomly decides which hops happen based on their probabilities. The spread of results tells you what to expect.', here: 'Powers the ribbon above the graph and the what-if scenarios.' },
      { term: 'Expected impact', full: null, simple: 'The average damage across all 1,000 trials — including the lucky runs where the cascade fizzles out.', here: 'The honest number for prioritization, next to the worst-case headline.' },
      { term: 'P90 impact', full: null, simple: 'The damage level only exceeded in the worst 10% of trials. "Plan for this, hope for less."', here: 'Shown in the ribbon so operators see tail risk, not just averages.' },
      { term: 'What-if simulation', full: null, simple: 'Re-running the same 1,000 trials with a proposed fix applied virtually, to price the fix before committing to it.', here: 'Scenario controls on the Cascade map: exposure with vs without each control.' },
      { term: 'Blast radius', full: null, simple: 'Everything downstream that one root cause can touch — orders, dispatches, docks, the line.', here: 'The node count and euro total attached to every cascade.' },
    ],
  },
  {
    id: 'sap',
    icon: Database,
    title: 'SAP inventory controls',
    intro: 'The MARD view anchors material stock to the storage location, period, and physical-count evidence that the ERP uses to plan movement.',
    terms: [
      { term: 'SAP MARD', full: 'Material Stock at Storage Location', simple: 'The SAP stock view that records how much of a material sits at each storage location.', here: 'The SAP ERP tab in Reconciliation shows the live MARD fields alongside WMS, ERP, TMS, and count values.' },
      { term: 'Plant 1400', full: 'VW Kassel Distribution Center', simple: 'The Kassel DC plant code used by the seeded SAP dataset.', here: 'Every real SAP anchor record is tied to plant 1400 and instance Kassel.' },
      { term: 'Fiscal period desynchronization', full: null, simple: 'An ERP material record is still in a prior fiscal year, so period close and goods movements can be blocked.', here: 'Nexus groups FY2022–FY2025 records by severity and exposes the affected storage locations.' },
      { term: 'Storage location fragmentation', full: null, simple: 'One material is spread across many zero-stock locations, bloating MRP and increasing picking error risk.', here: 'The fragmentation detector flags more than 15 zero-stock storage locations for one material.' },
      { term: 'Physical inventory blocking', full: null, simple: 'A SAP flag that prevents goods movement while a count is unposted or under review.', here: 'Unposted count records are grouped into a physical-inventory audit finding.' },
      { term: 'Deletion flag (LVORM)', full: null, simple: 'The master-data marker that retires a material/storage location from normal use.', here: 'A deleted location with active stock is escalated and routed through governed change control.' },
    ],
  },
]

export function KeyTerms() {
  const [query, setQuery] = useState('')
  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return GROUPS
    return GROUPS.map((group) => ({
      ...group,
      terms: group.terms.filter((item) => `${item.term} ${item.full || ''} ${item.simple} ${item.here}`.toLowerCase().includes(needle)),
    })).filter((group) => group.terms.length)
  }, [query])
  return <div className="page terms-page">
    <section className="page-lead"><div><span className="eyebrow"><BookOpen size={14} /> Domain glossary</span><h2>The language of what we’re dealing with.</h2><p>Automotive warehousing has its own vocabulary. Every term below is used somewhere in this product — explained the way you’d explain it to a colleague, not a textbook.</p></div>
      <label className="table-search terms-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search terms…" /></label></section>
    {groups.length === 0 && <section className="card-surface empty-state"><BookOpen size={22} /><h3>No matching term</h3><p>Try an abbreviation like JIS, PPAP or WMS.</p></section>}
    {groups.map(({ id, icon: Icon, title, intro, terms }) => <section key={id} className="terms-group">
      <div className="terms-group-head"><span className="terms-group-icon"><Icon size={16} /></span><div><h3>{title}</h3><p>{intro}</p></div></div>
      <div className="terms-grid">
        {terms.map((item) => <article key={item.term} className="term-card card-surface">
          <div className="term-head"><strong>{item.term}</strong>{item.full && <small>{item.full}</small>}</div>
          <p className="term-simple">{item.simple}</p>
          <p className="term-here"><b>In NexusAI:</b> {item.here}</p>
        </article>)}
      </div>
    </section>)}
  </div>
}
