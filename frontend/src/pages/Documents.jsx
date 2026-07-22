import { useRef, useState } from 'react'
import { CheckCircle2, FileCheck2, FileText, FileWarning, FolderUp, ScanSearch, Sparkles, UploadCloud } from 'lucide-react'

export function Documents({ onInspect, documentData }) {
  const inputRef = useRef(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const ingested = (documentData?.items || []).filter((item) => item.status !== 'source').slice(0, 5)

  const inspect = async (file) => {
    if (!file) return
    setLoading(true); setError('')
    try { setResult(await onInspect(file)) }
    catch (cause) { setError(cause.message) }
    finally { setLoading(false) }
  }
  const showRecord = (record) => setResult({
    document_id: record.id,
    filename: record.filename,
    type: record.type,
    status: record.status,
    confidence: 100,
    fields: Object.entries(record.fields || {}).map(([label, value]) => ({ label, value: String(value) })),
    mismatches: record.mismatches || [],
    preview_url: `/api/documents/${record.id}/preview`,
  })

  return <div className="page documents-page">
    <section className="page-lead">
      <div><span className="eyebrow"><ScanSearch size={14} /> Document intelligence</span><h2>Release the right freight with the right proof.</h2><p>Drop a supplier packet, VDA label, ASN, invoice or count sheet. Nexus extracts evidence and compares it against operational controls.</p></div>
      <div className="document-stat"><FileCheck2 size={20} /><div><strong>{documentData?.summary?.source_documents || 0} source documents monitored</strong><span>{documentData?.summary?.release_controls_needing_evidence || 0} controls need evidence · {documentData?.summary?.ingested_records || 0} ingested</span></div></div>
    </section>
    <section className="document-grid">
      <article className="upload-card card-surface">
        <span className="eyebrow"><UploadCloud size={14} /> Ingest a packet</span>
        <button className="dropzone" onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); inspect(event.dataTransfer.files?.[0]) }}>
          <span className="dropzone-icon"><FolderUp size={25} /></span><strong>{loading ? 'Inspecting document...' : 'Drop a document here'}</strong><p>or click to browse · CSV, TXT, Markdown, PDF, image, XLSX up to 5 MB</p>
        </button>
        <input ref={inputRef} type="file" accept=".csv,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xlsm" hidden onChange={(event) => inspect(event.target.files?.[0])} />
        <div className="supported-docs"><span>Control-aware extraction</span><div><em>PPAP</em><em>ASN</em><em>VDA</em><em>Invoice</em><em>Cycle count</em></div></div>
      </article>
      <article className="document-preview card-surface">
        <div className="section-title"><div><span className="eyebrow"><Sparkles size={14} /> Inspection result</span><h3>{result?.filename || 'Awaiting an operational document'}</h3></div>{result ? <span className={`inspection-status ${result.status}`}>{result.status === 'clean' ? <CheckCircle2 size={15} /> : <FileWarning size={15} />}{result.status}</span> : <span className="inspection-status idle">Ready to inspect</span>}</div>
        {error && <div className="upload-error">{error}</div>}
        <div className="document-paper"><div className="paper-head"><FileText size={21} /><div><strong>{result?.type || 'NO DOCUMENT'}</strong><span>{result ? `${result.confidence}% extraction confidence` : 'Upload a packet to extract its live fields'}</span></div></div><div className="document-fields">{result?.fields?.length ? result.fields.map((field) => <div key={field.label}><span>{field.label}</span><strong>{field.value}</strong></div>) : <div><span>Retrieval status</span><strong>{documentData?.summary?.ingested_records || 0} Markdown records available</strong></div>}</div></div>
        {result?.preview_url && <a className="document-preview-link" href={result.preview_url} target="_blank" rel="noreferrer">Open extracted page preview</a>}
      </article>
    </section>
    <section className="cross-check card-surface">
      <div className="section-title"><div><span className="eyebrow"><FileWarning size={14} /> Cross-system control</span><h3>Document vs. operational record</h3></div>{result?.mismatches?.length ? <span className="mismatch-count">{result.mismatches.length} attention items</span> : null}</div>
      {result ? <div className="mismatch-table"><div><span>Required field</span><span>Document</span><span>System control</span><span>Status</span></div>{(result.mismatches.length ? result.mismatches : [{ field: 'Release controls', document: 'Matched', system: 'No blocking discrepancy', severity: 'clean' }]).map((item) => <div key={item.field}><strong>{item.field}</strong><span>{item.document}</span><span>{item.system}</span><em className={item.severity}>{item.severity === 'clean' ? 'Matched' : 'Review'}</em></div>)}</div> : <div className="empty-document"><FileText size={26} /><h3>Start with a document</h3><p>We will show each field against the relevant dispatch and quality controls.</p></div>}
    </section>
    {ingested.length > 0 && <section className="document-history card-surface"><div className="section-title"><div><span className="eyebrow"><FileCheck2 size={14} /> Knowledge base</span><h3>Recently ingested evidence</h3></div><span>{documentData.summary.ingested_records} indexed</span></div><div className="document-history-list">{ingested.map((record) => <button key={record.id} onClick={() => showRecord(record)}><FileText size={16} /><div><strong>{record.filename}</strong><small>{record.type} · {record.created_at ? new Date(record.created_at).toLocaleString() : 'Recently'}</small></div><span className={`inspection-status ${record.status}`}>{record.status}</span></button>)}</div></section>}
  </div>
}
