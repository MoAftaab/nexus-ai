const AGENT_LABELS = Object.freeze({
  'Ingestion Agent': { name: 'Ingestion Agent', role: 'Loads & normalises 6 SAP sheets' },
  'Data-Quality Agent': { name: 'Data-Quality Agent', role: 'Detects bad master data (A1–A6)' },
  'Anomaly Agent': { name: 'Anomaly Agent', role: 'Detects inventory & process anomalies (B1–F2)' },
  'Correlation / Root-Cause Agent': { name: 'Correlation / Root-Cause Agent', role: 'Cross-system root cause & cascade tracing' },
  'Correlation Agent': { name: 'Correlation / Root-Cause Agent', role: 'Cross-system root cause & cascade tracing' },
  'Impact Agent': { name: 'Impact Agent', role: 'Scores € exposure & prioritises worklist' },
  'Action / Remediation Agent': { name: 'Action / Remediation Agent', role: 'Proposes fixes & routes for human approval' },
  'Action Agent': { name: 'Action / Remediation Agent', role: 'Proposes fixes & routes for human approval' },
  'Orchestrator (WALT)': { name: 'Orchestrator (WALT)', role: 'Plans flow & maintains audit trail' },
  'WALT Orchestrator': { name: 'Orchestrator (WALT)', role: 'Plans flow & maintains audit trail' },
  'Control Tower': { name: 'Orchestrator (WALT)', role: 'Plans flow & maintains audit trail' },
  Orchestrator: { name: 'Orchestrator (WALT)', role: 'Plans flow & maintains audit trail' },
  'Orchestrator Agent': { name: 'Orchestrator (WALT)', role: 'Plans flow & maintains audit trail' },
  Sentinel: { name: 'Anomaly Agent', role: 'Detects inventory & process anomalies' },
  Correlator: { name: 'Correlation / Root-Cause Agent', role: 'Cross-system root cause & linkage' },
  Cascade: { name: 'Data-Quality Agent', role: 'Master data quality & cascade tracing' },
  Impact: { name: 'Impact Agent', role: 'Scores € exposure & prioritises worklist' },
  Fix: { name: 'Action / Remediation Agent', role: 'Proposes human-approved fixes' },
  'Monitor Agent': { name: 'Anomaly Agent', role: 'Detects inventory & process anomalies' },
  'Investigator Agent': { name: 'Correlation / Root-Cause Agent', role: 'Cross-system linkage & root cause' },
  'Advisor Agent': { name: 'Impact Agent', role: 'Scores business impact & exposure' },
  'Approval Agent': { name: 'Action / Remediation Agent', role: 'Human approval routing & change control' },
  'Audit Agent': { name: 'Audit Agent', role: 'Records immutable audit trail' },
  'Copilot Agent': { name: 'WALT Copilot', role: 'Natural language operational twin' },
})

export function agentPresentation(name, fallbackRole = '') {
  const presentation = AGENT_LABELS[name]
  return presentation || { name: name || 'Specialist', role: fallbackRole || 'Operational specialist' }
}

export function agentDisplayName(name) {
  return agentPresentation(name).name
}

