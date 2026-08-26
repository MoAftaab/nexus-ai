import { useRef, useState } from 'react'
import { CheckCircle2, FileCheck2, FileText, FileWarning, FolderUp, Sparkles, Trash2, UploadCloud, X } from 'lucide-react'

export function Documents({ onInspect, onClearDocuments, onDeleteDocument, documentData }) {
  const inputRef = useRef(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const ingested = (documentData?.items || []).filter((item) => item.status !== 'source').slice(0, 6)

  const inspect = async (file) => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      setResult(await onInspect(file))
    } catch (cause) {
      setError(cause.message)
    } finally {
      setLoading(false)
    }
  }

  const handleClearKnowledgeBase = async (e) => {
    e?.preventDefault?.()
    e?.stopPropagation?.()
    setResult(null)
    if (onClearDocuments) {
      await onClearDocuments()
    }
  }

  const handleDeleteItem = async (e, id) => {
    e.stopPropagation()
    if (onDeleteDocument) {
      await onDeleteDocument(id)
      if (result?.document_id === id) {
        setResult(null)
      }
    }
  }

  const showRecord = (record) =>
    setResult({
      document_id: record.id,
      filename: record.filename,
      type: record.type,
      status: record.status,
      confidence: 100,
      fields: Object.entries(record.fields || {}).map(([label, value]) => ({
        label,
        value: String(value),
      })),
      mismatches: record.mismatches || [],
      preview_url: `/api/documents/${record.id}/preview`,
    })

  return (
    <div className="page documents-page">
      <div className="doc-viewport-grid">
        {/* Left Column: Upload Ingest Card + Cross-System Control Mismatches */}
        <div className="doc-left-col">
          {/* Upload Dropzone Card */}
          <article className="upload-card card-surface">
            <div className="doc-card-head">
              <span className="eyebrow"><UploadCloud size={13} /> Ingest a packet</span>
              <div className="supported-tags">
                <em>PPAP</em><em>ASN</em><em>VDA</em><em>Invoice</em><em>Cycle count</em>
              </div>
            </div>

            <button
              className="dropzone"
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                inspect(e.dataTransfer.files?.[0])
              }}
            >
              <span className="dropzone-icon">
                <FolderUp size={20} />
              </span>
              <strong>{loading ? 'Inspecting document...' : 'Drop operational packet here'}</strong>
              <p>or click to browse · CSV, TXT, MD, PDF, PNG, JPG, XLSX (up to 5 MB)</p>
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xlsm"
              hidden
              onChange={(e) => inspect(e.target.files?.[0])}
            />
          </article>

          {/* Cross-system Control & Mismatch Verification */}
          <section className="cross-check card-surface">
            <div className="section-title">
              <div>
                <span className="eyebrow"><FileWarning size={12} /> Cross-system control</span>
                <h3>Document vs. operational record</h3>
              </div>
              {result?.mismatches?.length ? (
                <span className="mismatch-count">{result.mismatches.length} attention items</span>
              ) : null}
            </div>

            {result ? (
              <div className="mismatch-table">
                <div className="mismatch-head">
                  <span>Required field</span>
                  <span>Document</span>
                  <span>System control</span>
                  <span>Status</span>
                </div>
                <div className="mismatch-rows-scroll">
                  {(result.mismatches.length
                    ? result.mismatches
                    : [{ field: 'Release controls', document: 'Matched', system: 'No blocking discrepancy', severity: 'clean' }]
                  ).map((item) => (
                    <div className="mismatch-row" key={item.field}>
                      <strong>{item.field}</strong>
                      <span>{item.document}</span>
                      <span>{item.system}</span>
                      <em className={item.severity}>{item.severity === 'clean' ? 'Matched' : 'Review'}</em>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="empty-document">
                <FileText size={18} />
                <strong>Awaiting document ingestion</strong>
                <p>Upload a packet to run automated cross-system verification against SAP, WMS & TMS records.</p>
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Extracted Document Inspection Result + History Knowledge Base */}
        <div className="doc-right-col">
          {/* Inspection Result Card */}
          <article className="document-preview card-surface">
            <div className="section-title">
              <div>
                <span className="eyebrow"><Sparkles size={12} /> Inspection result</span>
                <h3>{result?.filename || 'Awaiting an operational document'}</h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {result && (
                  <button
                    className="doc-header-action-btn"
                    type="button"
                    onClick={() => setResult(null)}
                    title="Close inspection"
                    aria-label="Close inspection"
                  >
                    <X size={13} />
                  </button>
                )}
                {result ? (
                  <span className={`inspection-status ${result.status}`}>
                    {result.status === 'clean' ? <CheckCircle2 size={13} /> : <FileWarning size={13} />}
                    {result.status}
                  </span>
                ) : (
                  <span className="inspection-status idle">Ready to inspect</span>
                )}
              </div>
            </div>

            {error && <div className="upload-error">{error}</div>}

            <div className="document-paper">
              <div className="paper-head">
                <FileText size={17} />
                <div>
                  <strong>{result?.type || 'NO DOCUMENT'}</strong>
                  <span>{result ? `${result.confidence}% extraction confidence` : 'Upload a packet to extract live fields'}</span>
                </div>
                {result?.preview_url && (
                  <a className="document-preview-link" href={result.preview_url} target="_blank" rel="noreferrer">
                    View raw source ↗
                  </a>
                )}
              </div>

              <div className="document-fields-scroll">
                {result?.fields?.length ? (
                  <div className="document-fields-grid">
                    {result.fields.map((field) => (
                      <div key={field.label} className="doc-field-item">
                        <span>{field.label}</span>
                        <strong>{field.value}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="doc-idle-fields">
                    <div className="doc-field-item">
                      <span>Monitoring scope</span>
                      <strong>{documentData?.summary?.source_documents || 200} source files</strong>
                    </div>
                    <div className="doc-field-item">
                      <span>Indexed memory</span>
                      <strong>{documentData?.summary?.ingested_records || 0} records</strong>
                    </div>
                    <div className="doc-field-item">
                      <span>Controls needing proof</span>
                      <strong>{documentData?.summary?.release_controls_needing_evidence || 0} items</strong>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </article>

          {/* History Knowledge Base */}
          {ingested.length > 0 && (
            <section className="document-history card-surface">
              <div className="section-title">
                <div>
                  <span className="eyebrow"><FileCheck2 size={12} /> Knowledge base</span>
                  <h3>Recently ingested evidence</h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    className="doc-header-action-btn delete-action"
                    type="button"
                    onClick={handleClearKnowledgeBase}
                    title="Clear all ingested evidence"
                    aria-label="Clear all ingested evidence"
                  >
                    <Trash2 size={13} />
                  </button>
                  <span className="history-badge">{documentData?.summary?.ingested_records || ingested.length} indexed</span>
                </div>
              </div>
              <div className="document-history-list">
                {ingested.map((record) => (
                  <button key={record.id} type="button" onClick={() => showRecord(record)}>
                    <FileText size={14} />
                    <div className="doc-hist-info">
                      <strong>{record.filename}</strong>
                      <small>{record.type} · {record.created_at ? new Date(record.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recently'}</small>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
