/* List/CRUD modules built on listModule(): Requirements, Reviews, Testing, Defects, CAPA */
const team = m => m.team.map(t => t.name);
const reqOpts = m => m.requirement_ids;
const H = html => ({ html });

/* ============ REQUIREMENTS ============ */
App.routes.requirements = listModule({
  api: 'requirements', title: 'Requirements', single: 'requirement', kicker: 'DEFINE · Requirements management', newLabel: 'New requirement',
  subtitle: 'Functional and non-functional requirements for the Hospital Management Software. Approval requires a recorded requirement review.',
  filters: [{ k: 'category', label: 'Category', options: m => m.requirement_categories }, { k: 'priority', label: 'Priority', options: m => m.levels },
    { k: 'risk', label: 'Risk', options: m => m.levels }, { k: 'status', label: 'Status', options: m => m.req_status }, { k: 'owner', label: 'Owner', options: team }],
  columns: [
    { label: 'ID', k: 'id', sort: 'id', render: r => `<span class="mono">${esc(r.id)}</span>` },
    { label: 'Requirement', sort: 'title', render: r => `<b>${esc(r.title)}</b><div class="sub">${esc(r.description)}</div>` },
    { label: 'Category', sort: 'category', render: r => esc(r.category) },
    { label: 'Priority', sort: 'priority', render: r => badge(r.priority) }, { label: 'Risk', sort: 'risk', render: r => badge(r.risk) },
    { label: 'Owner', sort: 'owner', render: r => esc(r.owner) }, { label: 'Status', sort: 'status', render: r => badge(r.status) },
    { label: 'Tests', render: r => chips(r.test_ids) }, { label: 'Defects', render: r => chips(r.defect_ids, 'bad') }],
  summary: rows => [['Shown', rows.length, ''], ['Approved+', rows.filter(r => ['Approved', 'Implemented', 'Verified'].includes(r.status)).length, 'green'],
    ['Awaiting review', rows.filter(r => ['Draft', 'Under Review'].includes(r.status)).length, 'amber'], ['No test case', rows.filter(r => !r.test_ids && r.status !== 'Rejected').length, 'red']]
    .map(([l, v, c]) => `<div class="kpi ${c}"><small>${l}</small><b>${v}</b></div>`).join(''),
  fields: [
    { k: 'title', label: 'Requirement title', type: 'text', req: true, wide: true }, { k: 'description', label: 'Detailed description', type: 'textarea', req: true },
    { k: 'category', label: 'Category', type: 'select', req: true, options: m => m.requirement_categories }, { k: 'req_type', label: 'Type', type: 'select', req: true, options: m => m.req_types },
    { k: 'priority', label: 'Priority', type: 'select', req: true, options: m => m.levels }, { k: 'risk', label: 'Risk level', type: 'select', req: true, options: m => m.levels },
    { k: 'owner', label: 'Assigned owner', type: 'select', req: true, options: team }, { k: 'quality_factor', label: 'Quality factor', type: 'select', options: m => m.quality_factors },
    { k: 'status', label: 'Status', type: 'select', req: true, options: m => m.req_status, hint: 'Approved/Implemented/Verified need an approved Requirement review.' },
    { k: 'need_id', label: 'Stakeholder need', type: 'select', options: m => m.needs.map(n => [n.id, `${n.id} ${n.title}`]) },
    { k: 'acceptance_criteria', label: 'Acceptance criteria', type: 'textarea', req: true }, { k: 'design_ref', label: 'Design reference', type: 'text' }, { k: 'impl_ref', label: 'Implementation reference', type: 'text' }],
  defaults: () => ({ status: 'Draft', req_type: 'Functional', priority: 'Medium', risk: 'Medium', owner: App.meta.settings.current_user }),
  fetchDetail: r => api(`/requirements/${r.id}/detail`),
  drawerExtra: r => `<div class="sect">Controlled documents</div><div class="chips">${docLinksHtml(['req_procedure', 'req_checklist', 'change_request', 'rtm'])}</div>`,
  drawerTitle: r => r.title, drawerBadges: r => `${badge(r.status)} ${badge(r.priority)} ${badge(r.risk + ' risk', BADGE[r.risk])}`,
  actions: (r, c) => [{ label: 'Change status', fn: () => statusDialog(r, 'requirements', App.meta.req_status, c) }, { label: 'Add test case', fn: () => { location.hash = `#/testing?new=${r.id}`; } }],
  detail: r => [
    { title: 'Requirement', rows: [['Description', r.description], ['Category', r.category], ['Type', r.req_type], ['Quality factor', r.quality_factor], ['Owner', r.owner], ['Acceptance criteria', r.acceptance_criteria]] },
    { title: 'Traceability', rows: [['Stakeholder need', r.need ? `${r.need.id} - ${r.need.title}` : ''], ['Design reference', r.design_ref], ['Implementation', r.impl_ref]] },
    { title: 'Review and approval', rows: [['Approved by', r.approved_by], ['Approved on', r.approved_on], ['Approval record', H(r.reviews.map(v => `<div><a class="chip" href="#/reviews?open=${v.id}">${esc(v.id)}</a> ${esc(v.review_type)} ${badge(v.decision || 'Pending')} <span class="when">${esc(v.reviewer || '')}</span></div>`).join('') || '<span class="when">No review record yet - approval is not possible</span>')]] },
    { title: 'Related test cases and defects', rows: [['Test cases', H(r.tests.map(t => `<div>${chips(t.id)} ${esc(t.scenario)} ${badge(t.status)}</div>`).join(''))], ['Defects', H(r.defects.map(d => `<div>${chips(d.id, 'bad')} ${esc(d.title)} ${badge(d.status)}</div>`).join(''))]] }]
});

function statusDialog(row, api_, statuses, c, extra = []) {
  openForm({ title: `Change status - ${row.id}`, fields: [{ k: 'status', label: 'New status', type: 'select', req: true, options: statuses }, ...extra], values: row, submitLabel: 'Update status',
    onSubmit: async d => { await api(`/${api_}/${row.id}`, { method: 'PUT', body: d }); toast(`${row.id} status updated`); await c.reload(); App.refreshBadges(); closeDrawer(); } });
}

/* ============ REVIEWS ============ */
App.routes.reviews = listModule({
  api: 'reviews', title: 'Quality Reviews and Approvals', single: 'review', kicker: 'VERIFY · Reviews and approvals', newLabel: 'New review', defaultSort: 'due_date',
  subtitle: 'Requirement, design, database, code, test plan, security, documentation and release reviews with mandatory checklists. No approval without a recorded reviewer and decision.',
  filters: [{ k: 'review_type', label: 'Type', options: m => m.review_types }, { k: 'approval_status', label: 'Status', options: m => ['Pending', ...m.review_decisions] }, { k: 'reviewer', label: 'Reviewer', options: team }],
  columns: [{ label: 'ID', k: 'id', sort: 'id', render: r => `<span class="mono">${esc(r.id)}</span>` },
    { label: 'Review', render: r => `<b>${esc(r.title)}</b><div class="sub">${esc(r.artifact)} ${esc(r.artifact_version || '')}</div>` },
    { label: 'Type', sort: 'review_type', render: r => esc(r.review_type) }, { label: 'Reviewer', sort: 'reviewer', render: r => esc(r.reviewer) },
    { label: 'Review date', sort: 'review_date', render: r => dt(r.review_date) }, { label: 'Due', sort: 'due_date', render: r => dt(r.due_date) },
    { label: 'Findings', render: r => r.finding_severity ? badge(r.finding_severity) : '<span class="when">-</span>' }, { label: 'Approval', sort: 'approval_status', render: r => badge(r.approval_status) }],
  fields: [{ k: 'review_type', label: 'Review type', type: 'select', req: true, options: m => m.review_types }, { k: 'title', label: 'Review title', type: 'text', req: true },
    { k: 'artifact', label: 'Artifact being reviewed', type: 'text', req: true }, { k: 'artifact_version', label: 'Artifact version', type: 'text' },
    { k: 'reviewer', label: 'Reviewer', type: 'select', options: team }, { k: 'review_date', label: 'Review date', type: 'date' }, { k: 'due_date', label: 'Due date', type: 'date' },
    { k: 'finding_severity', label: 'Severity of findings', type: 'select', options: m => m.finding_severities },
    { k: 'decision', label: 'Decision', type: 'select', options: m => m.review_decisions, hint: 'Leave blank while the review is pending.' },
    { k: 'requirement_ids', label: 'Requirements covered', type: 'multi', options: m => m.requirement_ids.map(i => [i, '']) },
    { k: 'checklist', label: 'Mandatory checklist (Approved requires all items)', type: 'checklist' },
    { k: 'findings', label: 'Review findings / actions', type: 'textarea' }, { k: 'comments', label: 'Reviewer comments', type: 'textarea' }],
  defaults: () => ({ reviewer: App.meta.settings.current_user, requirement_ids: [], checklist: {} }),
  drawerTitle: r => r.title, drawerBadges: r => `${badge(r.approval_status)} ${esc(r.review_type)}`,
  drawerExtra: r => `<div class="sect">Controlled documents</div><div class="chips">${docLinksHtml(r.review_type === 'Requirement review' ? ['peer_review', 'req_checklist'] : ['peer_review'])}</div>`,
  actions: (r, c) => [{ label: 'Record decision', fn: () => decisionDialog(r, c) }],
  detail: r => [{ title: 'Review', rows: [['Artifact', `${r.artifact} ${r.artifact_version || ''}`], ['Reviewer', r.reviewer], ['Review date', dt(r.review_date)], ['Due date', dt(r.due_date)], ['Decision', r.decision || 'Pending'], ['Severity of findings', r.finding_severity]] },
    { title: 'Findings and comments', rows: [['Findings', r.findings], ['Comments', r.comments]] },
    { title: 'Checklist', rows: Object.entries(r.checklist).map(([k, v]) => [v ? 'Checked' : 'Not checked', k]) },
    { title: 'Requirements covered', rows: [['Requirements', H(chips(r.requirement_ids.join(', ')))]] }]
});
function decisionDialog(r, c) {
  openForm({ title: `Record decision - ${r.id}`, sub: r.title, values: { ...r, reviewer: r.reviewer || App.meta.settings.current_user },
    fields: [{ k: 'reviewer', label: 'Reviewer', type: 'select', req: true, options: team }, { k: 'decision', label: 'Decision', type: 'select', req: true, options: m => m.review_decisions },
      { k: 'finding_severity', label: 'Severity of findings', type: 'select', options: m => m.finding_severities }, { k: 'checklist', label: 'Mandatory checklist', type: 'checklist' },
      { k: 'review_type', label: 'Review type', type: 'select', req: true, options: m => m.review_types, readonly: true, send: true },
      { k: 'findings', label: 'Findings / actions', type: 'textarea' }, { k: 'comments', label: 'Reviewer comments', type: 'textarea' }],
    submitLabel: 'Record decision', onSubmit: async d => { await api(`/reviews/${r.id}`, { method: 'PUT', body: { ...d, review_date: r.review_date || new Date().toISOString().slice(0, 10) } }); toast('Decision recorded'); await c.reload(); App.refreshBadges(); closeDrawer(); } });
}

/* ============ TESTING ============ */
App.routes.testing = listModule({
  api: 'tests', title: 'Test Management', single: 'test case', kicker: 'EXECUTE · Testing and verification', newLabel: 'New test case',
  subtitle: 'Hospital-specific test cases across unit, integration, system, regression, UAT, security, performance, data validation, database and recovery testing.',
  filters: [{ k: 'category', label: 'Category', options: m => m.test_categories }, { k: 'status', label: 'Status', options: m => m.test_status }, { k: 'requirement_id', label: 'Requirement', options: m => m.requirement_ids }, { k: 'tester', label: 'Tester', options: team }],
  columns: [{ label: 'ID', k: 'id', sort: 'id', render: r => `<span class="mono">${esc(r.id)}</span>` }, { label: 'Scenario', render: r => `<b>${esc(r.scenario)}</b><div class="sub">${esc(r.expected)}</div>` },
    { label: 'Requirement', sort: 'requirement_id', render: r => chips(r.requirement_id) }, { label: 'Category', sort: 'category', render: r => esc(r.category) },
    { label: 'Tester', sort: 'tester', render: r => esc(r.tester) }, { label: 'Executed', sort: 'exec_date', render: r => dt(r.exec_date) },
    { label: 'Status', sort: 'status', render: r => badge(r.status) }, { label: 'Defect', render: r => r.status === 'Failed' && !r.defect_ids ? '<span class="chip warn">none linked</span>' : chips(r.defect_ids, 'bad') }],
  summary: rows => { const c = s => rows.filter(r => r.status === s).length; return [['Shown', rows.length, ''], ['Passed', c('Passed'), 'green'], ['Failed', c('Failed'), 'red'], ['Not run / in progress', c('Not Run') + c('In Progress'), 'amber'], ['Blocked', c('Blocked'), 'amber']].map(([l, v, k]) => `<div class="kpi ${k}"><small>${l}</small><b>${v}</b></div>`).join(''); },
  fields: [{ k: 'scenario', label: 'Test scenario', type: 'text', req: true, wide: true }, { k: 'requirement_id', label: 'Related requirement', type: 'select', options: m => m.requirement_ids },
    { k: 'category', label: 'Test category', type: 'select', req: true, options: m => m.test_categories }, { k: 'preconditions', label: 'Preconditions', type: 'textarea' }, { k: 'steps', label: 'Test steps', type: 'textarea', req: true },
    { k: 'expected', label: 'Expected result', type: 'textarea', req: true }, { k: 'actual', label: 'Actual result', type: 'textarea' }, { k: 'tester', label: 'Tester', type: 'select', options: team },
    { k: 'exec_date', label: 'Execution date', type: 'date' }, { k: 'status', label: 'Status', type: 'select', req: true, options: m => m.test_status }, { k: 'evidence', label: 'Evidence / attachment reference', type: 'text' }],
  defaults: () => ({ status: 'Not Run', tester: App.meta.settings.current_user }),
  drawerTitle: r => r.scenario, drawerBadges: r => `${badge(r.status)} ${esc(r.category)}`,
  drawerExtra: r => `<div class="sect">Controlled documents</div><div class="chips">${docLinksHtml(['rtm', 'release_checklist'])}</div>`,
  actions: (r, c) => [{ label: 'Execute test', fn: () => executeDialog(r, c) }, ...(r.status === 'Failed' ? [{ label: 'Create linked defect', cls: 'teal', fn: () => defectFromTest(r, c) }] : [])],
  detail: r => [{ title: 'Test case', rows: [['Requirement', H(chips(r.requirement_id))], ['Category', r.category], ['Preconditions', r.preconditions], ['Steps', r.steps], ['Expected result', r.expected]] },
    { title: 'Execution', rows: [['Actual result', r.actual], ['Tester', r.tester], ['Execution date', dt(r.exec_date)], ['Status', r.status], ['Evidence', r.evidence], ['Linked defects', H(chips(r.defect_ids, 'bad'))]] }],
  afterRender: (view, c) => { const n = c.params.get('new'); if (n) { history.replaceState(null, '', '#/testing'); c.edit(null, { requirement_id: n }); } }
});
function executeDialog(r, c) {
  openForm({ title: `Execute ${r.id}`, sub: r.scenario, values: { ...r, tester: r.tester || App.meta.settings.current_user, exec_date: new Date().toISOString().slice(0, 10) },
    fields: [{ k: 'status', label: 'Result', type: 'select', req: true, options: m => m.test_status }, { k: 'actual', label: 'Actual result', type: 'textarea', req: true }, { k: 'tester', label: 'Tester', type: 'select', req: true, options: team },
      { k: 'exec_date', label: 'Execution date', type: 'date' }, { k: 'evidence', label: 'Evidence reference', type: 'text', wide: true }], submitLabel: 'Save result',
    onSubmit: async d => { const s = await api(`/tests/${r.id}`, { method: 'PUT', body: d }); toast(`${r.id} marked ${s.status}`); await c.reload(); App.refreshBadges(); closeDrawer();
      if (s.status === 'Failed' && !s.defect_ids && await confirmBox(`${r.id} failed. Create a linked defect now?`, 'Create defect')) defectFromTest(s, c); } });
}
function defectFromTest(r, c) {
  openForm({ title: `Create defect from ${r.id}`, sub: 'Steps, expected and actual results are copied from the failed test.',
    fields: [{ k: 'title', label: 'Defect title', type: 'text', req: true, wide: true }, { k: 'category', label: 'Category', type: 'select', req: true, options: m => m.defect_categories },
      { k: 'severity', label: 'Severity', type: 'select', req: true, options: m => m.severities }, { k: 'assigned_to', label: 'Assign developer', type: 'select', options: team }, { k: 'description', label: 'Description', type: 'textarea', req: true }],
    values: { title: `Failed test ${r.id}: ${r.scenario}`, severity: 'High', description: `Raised from failed test ${r.id}. Actual: ${r.actual || ''}` },
    submitLabel: 'Create defect', onSubmit: async d => { const x = await api(`/tests/${r.id}/create-defect`, { method: 'POST', body: d }); toast(`${x.id} created and linked to ${r.id}`); await c.reload(); App.refreshBadges(); closeDrawer(); } });
}

/* ============ DEFECTS ============ */
App.routes.defects = listModule({
  api: 'defects', title: 'Defect Management', single: 'defect', kicker: 'EXECUTE · Defect tracking', newLabel: 'Report defect', defaultSort: 'severity',
  subtitle: 'Hospital-specific defect tracking. Critical defects affecting patient data, prescriptions, laboratory results, billing or confidential access receive the highest priority.',
  filters: [{ k: 'category', label: 'Category', options: m => m.defect_categories }, { k: 'severity', label: 'Severity', options: m => m.severities }, { k: 'status', label: 'Status', options: m => m.defect_status },
    { k: 'module', label: 'Module', options: m => m.requirement_categories }, { k: 'assigned_to', label: 'Assigned', options: team }],
  columns: [{ label: 'ID', k: 'id', sort: 'id', render: r => `<span class="mono">${esc(r.id)}</span>` },
    { label: 'Defect', render: r => `<b>${esc(r.title)}</b><div class="sub">${esc(r.category)}${r.module ? ' · ' + esc(r.module) : ''}</div>` },
    { label: 'Severity', sort: 'severity', render: r => badge(r.severity) }, { label: 'Priority', sort: 'priority', render: r => badge(r.priority) + (r.patient_impact ? ' <span class="chip bad" title="Affects patient data, labs, prescriptions, billing or access">patient data</span>' : '') },
    { label: 'Status', sort: 'status', render: r => badge(r.status) }, { label: 'Assigned', render: r => esc(r.assigned_to) }, { label: 'Reported', sort: 'date_reported', render: r => dt(r.date_reported) },
    { label: 'Age', sort: 'age_days', render: r => r.age_days === null ? '-' : r.age_days + 'd' }, { label: 'Req / Test', render: r => chips([r.requirement_id, r.test_case_id].filter(Boolean).join(', ')) }],
  summary: rows => { const open = rows.filter(r => !['Resolved', 'Closed'].includes(r.status)); return [['Shown', rows.length, ''], ['Open', open.length, 'amber'], ['Critical open', open.filter(r => r.severity === 'Critical').length, 'red'], ['Patient-data impact (open)', open.filter(r => r.patient_impact).length, 'red'], ['Closed', rows.filter(r => r.status === 'Closed').length, 'green']].map(([l, v, k]) => `<div class="kpi ${k}"><small>${l}</small><b>${v}</b></div>`).join(''); },
  fields: [{ k: 'title', label: 'Defect title', type: 'text', req: true, wide: true }, { k: 'description', label: 'Description', type: 'textarea', req: true },
    { k: 'category', label: 'Category', type: 'select', req: true, options: m => m.defect_categories }, { k: 'severity', label: 'Severity', type: 'select', req: true, options: m => m.severities },
    { k: 'priority', label: 'Priority', type: 'select', options: m => m.defect_priorities, hint: 'Forced to Highest for critical/patient-data defects.' }, { k: 'status', label: 'Status', type: 'select', req: true, options: m => m.defect_status },
    { k: 'assigned_to', label: 'Assigned developer', type: 'select', options: team }, { k: 'date_reported', label: 'Date reported', type: 'date' },
    { k: 'requirement_id', label: 'Related requirement', type: 'select', options: m => m.requirement_ids }, { k: 'test_case_id', label: 'Related test case', type: 'select', options: m => m.test_ids },
    { k: 'steps', label: 'Steps to reproduce', type: 'textarea' }, { k: 'expected', label: 'Expected result', type: 'textarea' }, { k: 'actual', label: 'Actual result', type: 'textarea' },
    { k: 'resolution', label: 'Resolution details', type: 'textarea' }, { k: 'verification_result', label: 'Verification result', type: 'select', options: m => m.verification.filter(Boolean) }],
  defaults: () => ({ status: 'Open', severity: 'Medium', date_reported: new Date().toISOString().slice(0, 10) }),
  drawerTitle: r => r.title, drawerBadges: r => `${badge(r.status)} ${badge(r.severity)} ${badge(r.priority + ' priority', BADGE[r.priority])} ${r.patient_impact ? '<span class="badge b-red">Patient data impact</span>' : ''}`,
  drawerExtra: r => `<div class="sect">Controlled documents</div><div class="chips">${docLinksHtml(['capa_procedure', 'release_checklist'])}</div>`,
  actions: (r, c) => [{ label: 'Update status', fn: () => statusDialog(r, 'defects', App.meta.defect_status, c, [{ k: 'resolution', label: 'Resolution details', type: 'textarea' }, { k: 'verification_result', label: 'Verification result', type: 'select', options: m => m.verification.filter(Boolean) }, { k: 'assigned_to', label: 'Assigned developer', type: 'select', options: team }]) },
    { label: 'Open CAPA', cls: 'teal', fn: async () => { try { const x = await api(`/defects/${r.id}/create-capa`, { method: 'POST' }); toast(`${x.id} created`); location.hash = `#/capa?open=${x.id}`; } catch (e) { toast(e.message, true); } } }],
  detail: r => [{ title: 'Defect', rows: [['Description', r.description], ['Category', r.category], ['Hospital module', r.module], ['Assigned', r.assigned_to], ['Reported', `${dt(r.date_reported)} by ${r.reported_by || '-'}`], ['Age (days)', r.age_days === null ? 'Resolved' : r.age_days], ['Reopened', r.reopen_count + ' time(s)']] },
    { title: 'Reproduction', rows: [['Steps', r.steps], ['Expected', r.expected], ['Actual', r.actual]] }, { title: 'Traceability', rows: [['Requirement', H(chips(r.requirement_id))], ['Test case', H(chips(r.test_case_id))]] },
    { title: 'Resolution and verification', rows: [['Resolution', r.resolution], ['Verification', r.verification_result], ['Resolved on', r.resolved_on], ['Closed on', r.closed_on]] }]
});

/* ============ CAPA ============ */
App.routes.capa = listModule({
  api: 'capas', title: 'Corrective and Preventive Action', single: 'CAPA', kicker: 'IMPROVE · CAPA', newLabel: 'New CAPA', defaultSort: 'target_date',
  subtitle: 'Root-cause analysis with Five Whys, containment, corrective and preventive actions. A CAPA cannot close without documented effectiveness verification.',
  filters: [{ k: 'status', label: 'Status', options: m => m.capa_status }, { k: 'owner', label: 'Owner', options: team }, { k: 'defect_id', label: 'Defect', options: m => m.defect_ids }],
  columns: [{ label: 'ID', k: 'id', sort: 'id', render: r => `<span class="mono">${esc(r.id)}</span>` }, { label: 'Problem', render: r => `<b>${esc(r.problem)}</b><div class="sub">${esc(r.root_cause || 'Root cause not yet documented')}</div>` },
    { label: 'Defect', render: r => chips(r.defect_id, 'bad') + (r.defect_severity ? ' ' + badge(r.defect_severity) : '') }, { label: 'Owner', sort: 'owner', render: r => esc(r.owner) },
    { label: 'Target', sort: 'target_date', render: r => dt(r.target_date) }, { label: 'Status', sort: 'status', render: r => badge(r.status) },
    { label: 'Effectiveness', render: r => r.effectiveness_review ? badge('Verified', 'green') : '<span class="when">pending</span>' }],
  summary: rows => [['Shown', rows.length, ''], ['Closed', rows.filter(r => r.status === 'Closed').length, 'green'], ['In progress', rows.filter(r => !['Closed'].includes(r.status)).length, 'amber']].map(([l, v, k]) => `<div class="kpi ${k}"><small>${l}</small><b>${v}</b></div>`).join(''),
  fields: [{ k: 'defect_id', label: 'Related defect', type: 'select', options: m => m.defect_ids }, { k: 'owner', label: 'Responsible owner', type: 'select', req: true, options: team },
    { k: 'problem', label: 'Problem description', type: 'textarea', req: true }, { k: 'root_cause', label: 'Root cause analysis', type: 'textarea' },
    { k: 'why1', label: 'Why 1', type: 'text', wide: true }, { k: 'why2', label: 'Why 2', type: 'text', wide: true }, { k: 'why3', label: 'Why 3', type: 'text', wide: true }, { k: 'why4', label: 'Why 4', type: 'text', wide: true }, { k: 'why5', label: 'Why 5', type: 'text', wide: true },
    { k: 'containment', label: 'Immediate containment action', type: 'textarea' }, { k: 'corrective', label: 'Corrective action', type: 'textarea' }, { k: 'preventive', label: 'Preventive action', type: 'textarea' },
    { k: 'target_date', label: 'Target completion date', type: 'date' }, { k: 'status', label: 'Implementation status', type: 'select', req: true, options: m => m.capa_status },
    { k: 'verification_evidence', label: 'Verification evidence', type: 'textarea' }, { k: 'effectiveness_review', label: 'Effectiveness review', type: 'textarea' },
    { k: 'closure_approved_by', label: 'Closure approved by', type: 'select', options: team }],
  defaults: () => ({ status: 'Open', owner: App.meta.settings.current_user }),
  drawerTitle: r => r.problem.slice(0, 90), drawerBadges: r => `${badge(r.status)} ${r.defect_id ? chips(r.defect_id, 'bad') : ''}`,
  drawerExtra: r => `<div class="sect">Controlled documents</div><div class="chips">${docLinksHtml(['capa_procedure'])}</div>`,
  actions: (r, c) => [{ label: 'Advance / change status', fn: () => statusDialog(r, 'capas', App.meta.capa_status, c) }],
  detail: r => [{ title: 'Problem and cause', rows: [['Problem', r.problem], ['Defect', r.defect_id ? `${r.defect_id} - ${r.defect_title}` : ''], ['Root cause', r.root_cause], ['Owner', r.owner], ['Target date', dt(r.target_date)]] },
    { title: 'Five Whys', rows: [1, 2, 3, 4, 5].map(i => ['Why ' + i, r['why' + i]]) },
    { title: 'Actions', rows: [['Containment', r.containment], ['Corrective', r.corrective], ['Preventive', r.preventive]] },
    { title: 'Verification and closure', rows: [['Verification evidence', r.verification_evidence], ['Effectiveness review', r.effectiveness_review], ['Closure approved by', r.closure_approved_by], ['Closed on', r.closed_on]] }]
});
