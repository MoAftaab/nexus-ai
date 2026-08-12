
  # NexusAI: Role-based approval workflow, synchronized dashboards, and evidence control

  ## Summary

  Build NexusAI as a multi-site governed operations platform for Wolfsburg, Bratislava, and Pune.

  Every fix becomes a single canonical change request. The request moves through visible approval stages, updates every relevant dashboard in real time,
  applies only after final approval, re-scans the data, and records immutable before/after evidence.

  Finding
  → Request created
  → Approval stages
  → Approved
  → Source patch applied
  → Scan verifies outcome
  → Completed / verified

  ## Roles and dashboards

  Use seven roles with distinct dashboards. They share the NexusAI shell and the same underlying request data, but each dashboard answers a different
  question.

   Role                            Dashboard                     Main purpose
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Operations Operator             Request Workspace             Create requests; track own requests through every stage
  ──────────────────────────────  ────────────────────────────  ───────────────────────────────────────────────────────────────────────────
   Operations Lead                 Lead Approval Queue           Approve low-risk site requests; monitor team workload
  ──────────────────────────────  ────────────────────────────  ───────────────────────────────────────────────────────────────────────────
   Operations Manager              Operations Approval Center    Approve medium/high requests; manage site risk and bottlenecks
  ──────────────────────────────  ────────────────────────────  ───────────────────────────────────────────────────────────────────────────
   Quality & Compliance Manager    Evidence Gate                 Review PPAP, hazmat, VDA, SDS, document-release evidence
  ──────────────────────────────  ────────────────────────────  ───────────────────────────────────────────────────────────────────────────
   Supply Chain Director           Executive Control Tower       Approve critical/high-value and cross-site changes; compare site exposure
  ──────────────────────────────  ────────────────────────────  ───────────────────────────────────────────────────────────────────────────
   Auditor                         Audit Archive                 Read-only timeline, evidence, snapshots, reports, and decisions
  ──────────────────────────────  ────────────────────────────  ───────────────────────────────────────────────────────────────────────────
   System Administrator            Access & Policy Console       Manage seeded users, site scopes, roles, and approval-policy versions

  Seed 15 demo users:

  - 3 Operators, 3 Leads, 3 Operations Managers, 3 Quality & Compliance Managers
  - 1 global Director, 1 global Auditor, 1 global Administrator

  V1 uses seeded account sign-in. Users switch by signing out and selecting another account; the backend validates role and site scope. A future OIDC/
  Entra/Okta provider will replace seeded sessions without changing workflow logic.

  ## Canonical workflow and synchronized stage tracking

  Every dashboard reads the same change_request record and its approval_steps. No dashboard has its own copy of workflow state.

  ### Request stages

  Draft
  → Submitted
  → Awaiting Operations Lead          (low risk)
  → Awaiting Operations Manager       (medium+ risk)
  → Awaiting Quality & Compliance    (regulated only)
  → Awaiting Director                (high/critical risk)
  → Approved
  → Applying
  → Awaiting verification evidence   (when required)
  → Verified / completed

  Alternative outcomes:

  Rejected · Returned for changes · Cancelled · Stale · Failed verification

  ### What users see

  Every request displays a live stage rail:

  ● Request submitted
  ● Lead approved
  ◐ Manager review
  ○ Quality review
  ○ Director review
  ○ Apply and verify

  Each stage shows:

  - Current status: completed, active, waiting, skipped, rejected, stale
  - Required approver role and assigned person
  - Site
  - Decision timestamp and comment
  - SLA/deadline
  - Exact next action
  - Before/proposed/after snapshot availability

  ### Real-time synchronization

  When any decision occurs:

  1. The backend writes the approval decision, request state, audit event, and workflow version in one transaction.
  2. After commit, it publishes a scoped WebSocket event.
  3. All authorized dashboards refresh the same request summary and update counters immediately.
  4. The Operator sees “Manager review started.”
  5. The Manager sees their pending queue decrease after decision.
  6. The Director sees the request appear only when their approval stage becomes active.
  7. The Command Center updates exposure, pending approvals, and completed controls after execution/verification.

  Use events such as:

  - change_requested
  - approval_stage_activated
  - approval_decided
  - change_returned
  - change_rejected
  - change_stale
  - change_applied
  - verification_required
  - change_verified

  Events are filtered by site scope and user permissions.

  ## Approval policy

   Condition                                     Required approvers
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Low severity and under €25k                   Operations Lead
  ────────────────────────────────────────────  ───────────────────────────────────────────────────────────────────
   Medium severity or €25k–€99,999               Operations Manager
  ────────────────────────────────────────────  ───────────────────────────────────────────────────────────────────
   High severity or €100k–€249,999               Operations Manager → Director
  ────────────────────────────────────────────  ───────────────────────────────────────────────────────────────────
   Critical severity or €250k+                   Operations Manager → Quality & Compliance if regulated → Director
  ────────────────────────────────────────────  ───────────────────────────────────────────────────────────────────
   PPAP, hazmat, compliance, document release    Quality & Compliance is always required

  Rules:

  - Requesters cannot approve their own request.
  - Approvers must have access to the request site; Director/Auditor/Admin have global site scope.
  - Reject requires a reason.
  - Return-for-changes invalidates the old proposal and requires a revised snapshot.
  - Administrator policy changes are versioned and audited.
  - In-flight requests retain the policy version used at creation.
  - Final approval automatically applies the change only after source data revalidation.

  ## Change request, snapshots, and audit

  A request contains three immutable comparison states:

   State                    Meaning
  ━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Before snapshot          Source-record state when the request was submitted
  ───────────────────────  ─────────────────────────────────────────────────────
   Proposed snapshot        Exact dataset fields NexusAI intends to modify
  ───────────────────────  ─────────────────────────────────────────────────────
   Actual after snapshot    Values persisted after final approval and execution

  The approval screen must show:

  - Anomaly, evidence, site, source system, dataset run, and target record IDs
  - Field-level before → proposed after diff
  - Expected cascade probability, expected impact, P90 exposure, readiness effect, and value protected
  - Attached documents and document hashes
  - Approval path, active stage, prior decisions, comments, and policy version
  - Actual changed values and post-scan verification after execution

  Audit events are append-only and hash-linked:

  - Actor, role, site, timestamp, event type, request ID, anomaly ID
  - Prior/current hash
  - Snapshot hash, document hash, policy version
  - Approval/rejection comments
  - Before/proposed/after snapshot references
  - Scan result and verified outcome

  Demo reset creates a new audited dataset run; it must never erase historical audit records.

  ## Data model and backend changes

  Add persistent entities for:

  - Sites
  - Users, roles, and user-site scopes
  - Approval policies and version history
  - Change requests
  - Approval steps/decisions
  - Change snapshots and field-level diffs
  - Document-to-request relationships
  - Immutable audit events

  Add site_id to synthetic records, findings, documents, actions, change requests, and dataset runs.

  Separate planning from execution:

  1. build_change_preview creates a non-mutating patch plan.
  2. create_change_request freezes before/proposed snapshots and approval policy.
  3. decide_approval validates the current user and advances the workflow.
  4. execute_approved_change checks source hashes and applies the patch transactionally.
  5. verify_change runs the existing detector scan and captures actual outcome.

  The execution transaction must include source updates, action/request status, after snapshot, audit event, and outcome/value-ledger entry. Refresh the
  in-memory operational twin only after commit.

  ## UI changes

  Add these pages:

  - Sign in
  - Change Control
  - Audit Archive
  - Access & Policy Console

  Adapt existing pages:

  - Replace direct Apply fix with Preview and request approval.
  - Add stage badges and live approval status to Risk Intelligence, Command Center, Anomaly Drawer, Outcomes, and Alert Timeline.
  - Replace the static Wolfsburg selector with a real scoped site selector.
  - Add dashboard metrics:
      - Requests awaiting my decision
      - Requests by workflow stage
      - Approval SLA risk
      - Value awaiting approval
      - Verified value protected
      - Stale/failed requests

  - Use the Change Ledger timeline as the key workflow visual rather than generic status cards.

  ## Document ingestion and cross-site evidence pack

  Keep the existing four smoke-test files. Add a structured pack under:

  demo_documents/approval_pack/<site>/<scenario>/

   Site          Problem evidence                  Verification evidence
  ━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Wolfsburg     Missing-PPAP delivery note PDF    Signed PPAP release certificate PDF
  ────────────  ────────────────────────────────  ─────────────────────────────────────────
   Wolfsburg     Cycle-count variance CSV          Reconciliation journal XLSX
  ────────────  ────────────────────────────────  ─────────────────────────────────────────
   Bratislava    Failed VDA label scan PNG         Reprint verification PDF
  ────────────  ────────────────────────────────  ─────────────────────────────────────────
   Bratislava    Hazmat packet without SDS PDF     Signed SDS/declaration PDF
  ────────────  ────────────────────────────────  ─────────────────────────────────────────
   Pune          ASN / lead-time variance XLSX     Expedite PO + supplier confirmation PDF
  ────────────  ────────────────────────────────  ─────────────────────────────────────────
   Pune          Overdue container ledger CSV      Carrier return-scan receipt PNG

  Document extraction must capture site, SKU, batch, supplier, quantity, date, reference number, and PPAP/VDA/SDS status. It cross-checks those values
  against the site-scoped twin and attaches the document to the right anomaly/change request.

  Each document stores file hash, extracted fields, mismatches, preview, upload time, site, and audit relationship.

  Generate PDFs, spreadsheets, CSVs, and images using live seeded identifiers. Visually verify final PDFs and XLSX sheets before using them in the demo.

  ## APIs

  Add APIs for:

  - Seeded sign-in, sign-out, current principal, permitted sites
  - Change-preview generation
  - Change-request create/list/detail/cancel
  - Approval inbox, approve, reject, return-for-changes
  - Workflow-stage summaries by site/role

  The current direct apply endpoint becomes an internal execution mechanism and is removed from normal UI usage.

  - Correct role/site dashboard and navigation after sign-in
  - Site-bound users cannot view or approve other-site requests
  - Requester cannot self-approve
  - Correct policy routing for severity, value thresholds, and regulated categories
  - Every dashboard receives the same live stage transition after an approval event
  - Preview includes every field that execution modifies
  - Stale source data blocks execution safely
  - All document pairs ingest correctly and link to their intended site/request
  - Existing detection, cascade, scan, chat, document, ledger, and WebSocket behaviour remains working

  ## Delivery order

  1. Multi-site seeded data, users, sign-in, and server-side role/site checks
  2. Change-request, approval, snapshot, and immutable audit persistence
  3. Preview/revalidation/execution services and workflow APIs
  4. Synchronized role dashboards, Change Control, stage rail, and real-time events
  5. Audit Archive and Access & Policy Console
  6. Structured document extraction and cross-site demo evidence pack
  7. Regression tests, visual document verification, and end-to-end demo walkthrough

  ## Next product phase

  After this release, add a Resilience Planner that simulates cross-site supplier delay, stockout, transport, and workforce scenarios. It will compare
  mitigation options, cost, P90 risk, expected outcome, and required approval path before any change is requested.
