const NA = reason => `not-applicable: ${reason}`;
const covered = evidence => `covered: ${evidence}`;
const dimensions = overrides => Object.freeze({
  modalClose: NA('no non-terminal modal'), navigation: NA('no local workflow state'), refresh: NA('route is read from Backend'),
  browserRestart: NA('no browser-owned draft'), backendRestart: NA('request is independently repeatable'), delayedAction: NA('single actor'),
  retry: covered('shared error/action contract'), cancellation: NA('read-only or atomic action'), upgradeCache: covered('Backend no-store assets'),
  ...overrides,
});

export const UI_READINESS_SUITES = Object.freeze([
  {
    id: 'foundation-contracts', task: 'UI-002/UI-003/UI-017',
    specification: 'UI Safety and Acceptance; Backend API Contract',
    backendEvidence: 'TestVersionedApiAuthorization',
    interruptions: dimensions({ retry:covered('interaction contract duplicate-action and error mapping') }),
    command: process.execPath,
    args: ['--test', 'apps/web/tests/api_contract_test.mjs', 'apps/web/tests/browser_fixture_test.mjs', 'apps/web/tests/ui_interaction_contract_test.mjs'],
    timeoutMs: 90_000,
  },
  {
    id: 'authenticated-smoke', task: 'UI-004C',
    specification: 'Authentication; API Contract',
    backendEvidence: 'TestAuthenticatedApiWorkflow',
    interruptions: dimensions({refresh:covered('credential reload'),browserRestart:covered('browser Token storage'),backendRestart:covered('reconnect smoke'),retry:covered('invalid replacement recovery')}),
    command: process.execPath, args: ['apps/web/tests/browser_workflow_acceptance.mjs'], timeoutMs: 90_000,
  },
  {
    id: 'admin-workflows', task: 'UI-004B/UI-010/UI-010A-D',
    specification: 'Authentication; Snapshot; protected database Restore',
    backendEvidence: 'BT-040/BT-041/BT-042 and Backend service/API regression',
    interruptions: dimensions({modalClose:covered('explicit Cancel in Admin reviews'),refresh:covered('authoritative Admin state reload'),backendRestart:covered('durable recovery catalog'),retry:covered('stale/replay contracts'),cancellation:covered('cleanup/Restore cancellation')}),
    command: process.execPath, args: ['apps/web/tests/admin_workflows_browser_acceptance.mjs'], timeoutMs: 180_000,
  },
  {
    id: 'device-enrollment', task: 'UI-019/UI-020/UI-021',
    specification: 'Authentication; UI Safety and Acceptance',
    backendEvidence: 'BT-060/BT-061 authentication and API regression',
    interruptions: dimensions({modalClose:covered('fixed top-bar resume entry'),navigation:covered('pending local state'),refresh:covered('legacy/current enrollment restore'),browserRestart:covered('persistent enrollment material'),backendRestart:covered('durable request plus local material'),delayedAction:covered('Admin approval status polling'),retry:covered('idempotent status'),cancellation:NA('request ends by rejection/expiry')}),
    command: process.execPath, args: ['apps/web/tests/device_enrollment_browser_acceptance.mjs'], timeoutMs: 120_000,
  },
  {
    id: 'permanent-entities', task: 'UI-005/UI-012/UI-018',
    specification: 'Permanent entity and Album relationship contracts',
    backendEvidence: 'Entity repository/service/API regression',
    interruptions: dimensions({navigation:covered('UI-024 saved draft and guarded leave'),refresh:covered('UI-024 draft restore'),browserRestart:covered('versioned local draft'),backendRestart:covered('local draft plus Backend version check'),retry:covered('failed save retains values'),cancellation:covered('leave and keep draft/discard lifecycle')}),
    command: process.execPath, args: ['apps/web/tests/entity_management_full_browser_acceptance.mjs'], timeoutMs: 120_000,
  },
  {
    id: 'import', task: 'UI-006/UI-013',
    specification: 'Import Workflow',
    backendEvidence: 'BT-019/BT-036; test_import_workflow_acceptance',
    interruptions: dimensions({navigation:covered('UI-025 saved workflow'),refresh:covered('UI-025 restore'),browserRestart:covered('versioned Import draft'),backendRestart:covered('re-preview/retry contract'),delayedAction:covered('Preview expiry is visible'),retry:covered('stale/replay re-preview'),cancellation:covered('explicit Abandon')}),
    command: process.execPath, args: ['apps/web/tests/import_full_browser_acceptance.mjs'], timeoutMs: 180_000,
  },
  {
    id: 'operation-history', task: 'UI-007',
    specification: 'Operation Logging',
    backendEvidence: 'BT-030; TestOperationHistoryDisclosure',
    interruptions: dimensions({navigation:covered('stable evidence routes'),refresh:covered('durable Operation reload')}),
    command: process.execPath, args: ['apps/web/tests/operation_history_browser_acceptance.mjs'], timeoutMs: 90_000,
  },
  {
    id: 'repair-quarantine', task: 'UI-008/UI-009/UI-014',
    specification: 'Issue Management; Repair Workflow',
    backendEvidence: 'BT-020/BT-022/BT-023/BT-038/BT-039 workflow acceptance',
    interruptions: dimensions({modalClose:covered('UI-026 non-dismissible reviewed action'),navigation:covered('stable Issue/Repair/Quarantine routes'),refresh:covered('interrupted-review guidance'),backendRestart:covered('durable workflow state'),retry:covered('stale/replay/collision'),cancellation:covered('explicit zero-write cancellation')}),
    command: process.execPath, args: ['apps/web/tests/repair_quarantine_full_browser_acceptance.mjs'], timeoutMs: 180_000,
  },
  {
    id: 'permission-disclosure', task: 'UI-015',
    specification: 'Authentication; role-sensitive Operation disclosure',
    backendEvidence: 'TestVersionedApiAuthorization; TestOperationHistoryDisclosure',
    interruptions: dimensions({retry:covered('UI-023 schema-aware negative disclosure assertions')}),
    command: process.execPath, args: ['apps/web/tests/permission_disclosure_full_browser_acceptance.mjs'], timeoutMs: 180_000,
  },
  {
    id: 'work-dispatch', task: 'UI-011E/UI-011F',
    specification: 'Work Dispatch Workflow',
    backendEvidence: 'BT-054 through BT-058; test_ai_workspace_workflow_acceptance',
    interruptions: dimensions({modalClose:covered('UI-026 non-dismissible Dispatch review'),navigation:covered('Active/History routes'),refresh:covered('selection restart and interrupted guidance'),backendRestart:covered('durable Groups'),delayedAction:covered('active Groups remain visible'),retry:covered('reservation conflict'),cancellation:covered('explicit preview and Group cancel')}),
    command: process.execPath, args: ['apps/web/tests/work_dispatch_browser_acceptance.mjs'], timeoutMs: 120_000,
  },
  {
    id: 'workspace-review', task: 'UI-011A-D',
    specification: 'AI Collection Workspace; Workspace Review state machine',
    backendEvidence: 'BT-043 through BT-053/BT-057; test_ai_workspace_workflow_acceptance',
    interruptions: dimensions({modalClose:covered('UI-026 Promotion review'),navigation:covered('UI-027 per-item draft'),refresh:covered('UI-027 draft restore'),browserRestart:covered('versioned review draft'),backendRestart:covered('durable version reconciliation'),delayedAction:covered('stale draft rebase'),retry:covered('validation/network/stale retention'),cancellation:covered('explicit draft discard')}),
    command: process.execPath, args: ['apps/web/tests/workspace_review_browser_acceptance.mjs'], timeoutMs: 180_000,
  },
  {
    id: 'simulated-ai-promotion', task: 'UI-029',
    specification: 'AI Collection Workspace; Work Dispatch; Review and Promotion',
    backendEvidence: 'BT-053; test_ai_workspace_workflow_acceptance',
    interruptions: dimensions({navigation:covered('durable Group and Review routes'),refresh:covered('authoritative Backend state reload'),browserRestart:covered('no model-process dependency'),backendRestart:covered('durable dispatch, results, review, and Promotion'),delayedAction:covered('reservation and Review remain durable'),retry:covered('versioned Review and Promotion contracts'),cancellation:covered('existing Group and Review lifecycle suites')}),
    command: process.execPath, args: ['apps/web/tests/simulated_ai_promotion_browser_acceptance.mjs'], timeoutMs: 120_000,
  },
  {
    id:'workflow-interruptions',task:'UI-024/UI-025/UI-026/UI-027/UI-028',
    specification:'Curator Web UI Specification interruption and recovery contract',
    backendEvidence:'Entity, Import, Preview/execute, and AI Workspace regression',
    interruptions:dimensions({modalClose:covered('reviewed action ignores Escape'),navigation:covered('entity/import local recovery'),refresh:covered('entity/import/review interruption scenarios'),browserRestart:covered('persistent versioned drafts'),backendRestart:covered('local versus durable state separation'),delayedAction:covered('stale/versioned recovery contracts'),retry:covered('fresh Preview guidance'),cancellation:covered('explicit Abandon and no execution')}),
    command:process.execPath,args:['apps/web/tests/workflow_interruption_browser_acceptance.mjs'],timeoutMs:120_000,
  },
]);
