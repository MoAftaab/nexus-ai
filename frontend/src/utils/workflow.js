const REGULATED_TERMS = ['ppap', 'hazmat', 'vda', 'sds', 'compliance', 'document release']

export const workflowRoleLabels = {
  operator: 'Operations Operator',
  lead: 'Operations Lead',
  manager: 'Operations Manager',
  quality_compliance: 'Quality and Compliance Officer',
  director: 'Supply Chain Director',
}

export const workflowStatusLabels = {
  draft: 'Draft',
  planned: 'Planned; waiting for approval',
  submitted: 'Submitted',
  awaiting_lead: 'Waiting for Operations Lead',
  awaiting_manager: 'Waiting for Operations Manager',
  awaiting_quality_compliance: 'Waiting for Quality and Compliance',
  awaiting_director: 'Waiting for Supply Chain Director',
  approved: 'Approved, preparing execution',
  applying: 'Applying approved change',
  awaiting_verification: 'Waiting for verification',
  verified: 'Approved and verified',
  rolled_back: 'Rolled back to original source data',
  rejected: 'Rejected',
  returned: 'Returned for changes',
  cancelled: 'Cancelled',
  stale: 'Blocked because source data changed',
  failed_verification: 'Verification failed',
}

export function isRegulatedWorkflow({ title = '', is_regulated: regulated = false } = {}) {
  const text = String(title).toLowerCase()
  return regulated || REGULATED_TERMS.some((term) => text.includes(term))
}

export function getApprovalRoute({ severity = '', impact_euros: impact = 0, title = '', is_regulated: regulated = false } = {}) {
  const normalizedSeverity = String(severity).toLowerCase()
  const amount = Number(impact) || 0
  let roles
  if (normalizedSeverity === 'low' && amount < 25_000) roles = ['lead']
  else if (normalizedSeverity === 'critical' || amount >= 250_000) roles = ['manager', 'director']
  else if (normalizedSeverity === 'high' || amount >= 100_000) roles = ['manager', 'director']
  else roles = ['manager']

  if (isRegulatedWorkflow({ title, is_regulated: regulated })) {
    roles = roles.includes('quality_compliance') ? roles : roles.length === 1 && roles[0] === 'lead' ? [...roles, 'quality_compliance'] : [roles[0], 'quality_compliance', ...roles.slice(1)]
  }
  return roles.map((role, index) => ({ role, label: workflowRoleLabels[role], order: index + 1 }))
}

export function statusLabel(status) {
  return workflowStatusLabels[status] || String(status || '').replaceAll('_', ' ')
}
