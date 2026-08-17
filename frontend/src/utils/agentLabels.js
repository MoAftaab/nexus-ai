const AGENT_LABELS = Object.freeze({
  Sentinel: { name: 'Issue Monitor', role: 'Finds anomalies' },
  Correlator: { name: 'System Linker', role: 'Connects records' },
  Cascade: { name: 'Impact Tracer', role: 'Follows downstream risk' },
  Impact: { name: 'Value Analyst', role: 'Measures business impact' },
  Fix: { name: 'Action Planner', role: 'Designs safe controls' },
  'Control Tower': { name: 'WALT Coordinator', role: 'Combines the evidence' },
  'Monitor Agent': { name: 'Issue Monitor', role: 'Finds data problems' },
  'Investigator Agent': { name: 'System Linker', role: 'Connects records across tools' },
  'Advisor Agent': { name: 'Impact Advisor', role: 'Explains cost and urgency' },
  'Approval Agent': { name: 'Approval Guide', role: 'Routes the decision' },
  'Audit Agent': { name: 'Audit Recorder', role: 'Records decisions and time' },
  'Copilot Agent': { name: 'WALT Assistant', role: 'Answers operational questions' },
  Orchestrator: { name: 'WALT Coordinator', role: 'Combines the evidence' },
})

export function agentPresentation(name, fallbackRole = '') {
  const presentation = AGENT_LABELS[name]
  return presentation || { name: name || 'Specialist', role: fallbackRole || 'Operational specialist' }
}

export function agentDisplayName(name) {
  return agentPresentation(name).name
}

