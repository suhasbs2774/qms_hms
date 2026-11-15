/* Custom pages: Dashboard, Quality Analytics, Traceability (RTM), Release Management, Documents, Settings */

/* ============ DASHBOARD ============ */
App.routes.dashboard = async view => {
  const d = await api('/dashboard');
  const k = d.kpis, s = d.score;
  const circ = 2 * Math.PI * 56, off = circ * (1 - Math.min(100, s.score) / 100);
  const recCls = k.release_recommendation === 'NO-GO' ? 'go-NO-GO' : k.release_recommendation === 'GO' ? 'go-GO' : 'go-CONDITIONAL';
  const card = (l, v, sub, c, link) => `<a href="${link || '#'}" class="kpi ${c || ''}" style="color:inherit"><small>${l}</small><b>${v}</b><span>${sub || '&nbsp;'}</span></a>`;
  view.innerHTML = `
  <div class="page-h"><div><div class="kicker">Executive overview</div><h1>Quality dashboard</h1><p>Live metrics calculated from the database records of the Hospital Management Software QMS.</p></div>
    <div style="display:flex;gap:8px"><a class="btn" href="#/analytics">Quality analytics</a><a class="btn primary" href="#/release">Release gate</a></div></div>
  <section class="hero">
    <div class="ring"><svg width="132" height="132"><circle cx="66" cy="66" r="56" stroke="rgba(255,255,255,.15)" stroke-width="11" fill="none"/><circle cx="66" cy="66" r="56" stroke="#5eead4" stroke-width="11" fill="none" stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${off}"/></svg><div class="v"><b>${s.score}</b><small>QUALITY SCORE</small></div></div>
    <div><h2>${esc(s.rating)} · ${k.open_defects} open defects, ${k.critical_defects} critical</h2>
      <p>${k.passed_tests} of ${k.total_tests} tests passed (${pctTxt(k.pass_rate)} pass rate), ${k.approved_requirements} of ${k.total_requirements} requirements approved, traceability ${pctTxt(k.traceability)}. Priority is given to defects that affect patient data, laboratory results, prescriptions, billing and confidential access.</p>
      <p style="margin-top:8px;font-size:12px;opacity:.75">Score: ${esc(s.formula)}</p></div>
    <div class="rel"><small>RELEASE GATE</small><b class="${recCls}">${esc(k.release_recommendation)}</b><small>${pctTxt(k.release_readiness)} ready</small><div class="bar" style="background:rgba(255,255,255,.2)"><i style="width:${k.release_readiness || 0}%"></i></div></div>
  </section>
  <div class="kpis">
    ${card('Total requirements', k.total_requirements, 'all categories', '', '#/requirements')}${card('Approved requirements', k.approved_requirements, 'review-backed', 'green', '#/requirements?status=Approved')}
    ${card('Pending review', k.pending_review_requirements, 'draft / under review', 'amber', '#/requirements?status=Under Review')}${card('Total test cases', k.total_tests, 'across 10 categories', '', '#/testing')}
    ${card('Passed tests', k.passed_tests, pctTxt(k.pass_rate) + ' pass rate', 'green', '#/testing?status=Passed')}${card('Failed tests', k.failed_tests, 'need defects / retest', 'red', '#/testing?status=Failed')}
    ${card('Open defects', k.open_defects, 'not resolved or closed', 'amber', '#/defects')}${card('Critical defects', k.critical_defects, 'blocks release', 'red', '#/defects?severity=Critical')}
    ${card('Completed reviews', k.completed_reviews, 'decision recorded', 'teal', '#/reviews')}${card('Pending approvals', k.pending_approvals, 'no decision yet', 'amber', '#/reviews?approval_status=Pending')}
    ${card('Test pass rate', pctTxt(k.pass_rate), 'baseline ≥ ' + (App.meta.settings.min_pass_rate) + '%', k.pass_rate >= +App.meta.settings.min_pass_rate ? 'green' : 'red', '#/analytics')}${card('Traceability coverage', pctTxt(k.traceability), 'need→design→test', 'teal', '#/traceability')}
    ${card('Quality score', k.quality_score, k.quality_rating, '', '#/analytics')}${card('CAPA completion', pctTxt(k.capa_rate), k.total_capas + ' CAPAs', 'teal', '#/capa')}${card('Release readiness', pctTxt(k.release_readiness), k.release_recommendation, k.release_recommendation === 'GO' ? 'green' : 'red', '#/release')}
  </div>
  <div class="card mt"><h3>PLAN → DEFINE → EXECUTE → VERIFY → MEASURE → REPORT → IMPROVE <small>Quality lifecycle · progress from live records</small></h3>
    <div class="life">${d.lifecycle.map(l => `<div class="stage" onclick="location.hash='#/${l.route}'"><b>${l.stage}</b><p>${esc(l.description)}</p><div class="bar ${l.progress < 40 ? 'red' : l.progress < 75 ? 'amber' : ''}"><i style="width:${l.progress}%"></i></div><em>${l.progress}% · ${esc(l.modules)}</em></div>`).join('')}</div></div>
  <div class="grid g3 mt">
    <div class="card"><h3>Defect severity distribution</h3><div class="chartbox"><canvas id="c-sev"></canvas></div></div>
    <div class="card"><h3>Test execution results</h3><div class="chartbox"><canvas id="c-test"></canvas></div></div>
    <div class="card"><h3>Requirements status</h3><div class="chartbox"><canvas id="c-req"></canvas></div></div>
  </div>
  <div class="grid g2 mt">
    <div class="card"><h3>Quality performance <small>% of target areas</small></h3><div class="chartbox"><canvas id="c-perf"></canvas></div></div>
    <div class="card"><h3>Defects by hospital module</h3><div class="chartbox"><canvas id="c-mod"></canvas></div></div>
  </div>
  <div class="grid g-main mt">
    <div class="grid" style="gap:16px">
      <div class="card"><h3>Critical quality alerts <small>${d.alerts.length} shown</small></h3><ul class="list">${d.alerts.map(a => `<li style="cursor:pointer" onclick="location.hash='#/${a.route}${a.id ? '?open=' + a.id : ''}'"><span class="pip ${a.level}"></span><span>${esc(a.text)}</span></li>`).join('') || '<li class="when">No active alerts.</li>'}</ul></div>
      <div class="card"><h3>Upcoming review and CAPA deadlines</h3><ul class="list">${d.deadlines.map(x => `<li style="cursor:pointer" onclick="location.hash='#/${x.route}?open=${x.id}'"><span class="pip ${x.overdue ? 'critical' : 'ok'}"></span><span><b class="mono">${esc(x.id)}</b> ${esc(x.title).slice(0, 80)}<br><span class="when">${esc(x.kind)} · ${esc(x.owner || '')} · due ${dt(x.due)} ${x.overdue ? '<b style="color:var(--red)">(overdue ' + (-x.days_left) + 'd)</b>' : x.days_left !== null ? '(in ' + x.days_left + 'd)' : ''}</span></span></li>`).join('') || '<li class="when">No open deadlines.</li>'}</ul></div>
    </div>
    <div class="grid" style="gap:16px;align-content:start">
      <div class="card"><h3>Risk summary</h3><div class="riskgrid">${Object.entries(d.risk.by_risk).map(([l, v]) => `<div><b style="color:${PAL[l]}">${v}</b><span>${l} risk reqs</span></div>`).join('')}</div>
        <ul class="list"><li><span class="pip critical"></span><span>${d.risk.high_risk_unverified} of ${d.risk.high_risk_total} high/critical-risk requirements not yet verified</span></li>
        <li><span class="pip ${d.risk.patient_data_defects_open ? 'critical' : 'ok'}"></span><span>${d.risk.patient_data_defects_open} open defects affect patient data, labs, prescriptions, billing or access</span></li>
        <li><span class="pip ${d.risk.failed_tests_without_defect.length ? 'warning' : 'ok'}"></span><span>${d.risk.failed_tests_without_defect.length} failed tests without a linked defect</span></li></ul></div>
      <div class="card"><h3>Recent activity</h3><ul class="list timeline">${d.activity.map(a => `<li><span class="pip"></span><span><b>${esc(a.actor)}</b> ${esc(a.action)} <span class="mono">${esc(a.entity_id)}</span><br><span class="when">${esc(a.detail || '')} · ${esc(a.ts.slice(0, 16))}</span></span></li>`).join('')}</ul></div>
    </div>
  </div>`;
  const c = d.charts;
  chart('c-sev', 'doughnut', c.severity.labels, c.severity.values);
  chart('c-test', 'bar', c.tests.labels, c.tests.values);
  chart('c-req', 'doughnut', c.requirements.labels, c.requirements.values, { colors: ['#94A3B8', '#F59E0B', '#2563EB', '#0F9D91', '#059669', '#DC2626'] });
  chart('c-perf', 'bar', d.quality_performance.labels, d.quality_performance.values, { horizontal: true, max: 100, colors: d.quality_performance.values.map(v => v >= 80 ? '#0F9D91' : v >= 60 ? '#F59E0B' : '#DC2626') });
  c.modules.labels.length ? chart('c-mod', 'bar', c.modules.labels, c.modules.values, { horizontal: true, colors: ['#2563EB'] }) : emptyChart('c-mod', 'No defects recorded.');
};

/* ============ QUALITY ANALYTICS ============ */
App.routes.analytics = async view => {
  const d = await api('/metrics'); const c = d.charts, s = d.score;
  view.innerHTML = `
  <div class="page-h"><div><div class="kicker">MEASURE · REPORT · Quality analytics</div><h1>Quality analytics and reporting</h1><p>Twelve metrics calculated from stored records. Each shows its formula, records used and an interpretation. Metrics without data are reported as not measurable.</p></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn primary" href="/api/report/pdf">${ico('down')} PDF report</a><a class="btn" href="/api/report/xlsx">${ico('down')} Excel report</a><a class="btn" href="/api/report/csv">${ico('down')} CSV data</a><a class="btn" href="/api/report/print" target="_blank">Print report</a></div></div>
  <div class="card" style="margin-bottom:16px;display:flex;gap:24px;align-items:center;flex-wrap:wrap"><div><div class="kicker">Overall quality score</div><div style="font-size:42px;font-weight:700">${s.score}<span style="font-size:16px;color:var(--mute)"> / 100</span></div>${badge(s.rating, s.score >= 70 ? 'green' : s.score >= 50 ? 'amber' : 'red')}</div><div style="flex:1;min-width:260px;color:var(--mute);font-size:12.5px"><b style="color:var(--navy)">How it is calculated.</b> ${esc(s.formula)}<br>Base ${s.base}, penalty −${s.penalty}. The minimum ${d.min_pass_rate}% pass rate is the proposed project baseline, not a regulatory standard.</div></div>
  <div class="grid g3">${d.metrics.map(m => `<div class="metric ${m.status}"><h4>${esc(m.name)} ${badge(m.status === 'n/a' ? 'n/a' : m.status.toUpperCase(), BADGE[m.status])}</h4><div class="val">${esc(m.display)}</div>
    <dl><dt>Formula</dt><dd>${esc(m.formula)}</dd><dt>Records used</dt><dd>${esc(m.used)}</dd><dt>Interpretation</dt><dd>${esc(m.interpretation)}</dd></dl></div>`).join('')}</div>
  <div class="grid g3 mt"><div class="card"><h3>Defect severity distribution</h3><div class="chartbox"><canvas id="a-sev"></canvas></div></div>
    <div class="card"><h3>Defects by hospital module</h3><div class="chartbox"><canvas id="a-mod"></canvas></div></div>
    <div class="card"><h3>Test execution results</h3><div class="chartbox"><canvas id="a-test"></canvas></div></div>
    <div class="card"><h3>Monthly defect trend</h3><div class="chartbox"><canvas id="a-trend"></canvas></div></div>
    <div class="card"><h3>Requirements approval status</h3><div class="chartbox"><canvas id="a-req"></canvas></div></div>
    <div class="card"><h3>Quality performance (%)</h3><div class="chartbox"><canvas id="a-perf"></canvas></div></div></div>`;
  chart('a-sev', 'bar', c.severity.labels, c.severity.values);
  c.modules.labels.length ? chart('a-mod', 'bar', c.modules.labels, c.modules.values, { horizontal: true, colors: ['#0F9D91'] }) : emptyChart('a-mod', 'No defects recorded.');
  chart('a-test', 'doughnut', c.tests.labels, c.tests.values);
  c.trend.available ? chart('a-trend', 'line', c.trend.labels, null, { legend: true, datasets: [{ label: 'Reported', data: c.trend.reported, borderColor: '#DC2626', backgroundColor: '#DC2626', tension: .3 }, { label: 'Closed', data: c.trend.closed, borderColor: '#0F9D91', backgroundColor: '#0F9D91', tension: .3 }] }) : emptyChart('a-trend', 'Monthly trend needs defects dated in at least two different months. Not enough dated history is stored, so no trend is shown.');
  chart('a-req', 'doughnut', c.requirements.labels, c.requirements.values, { colors: ['#94A3B8', '#F59E0B', '#2563EB', '#0F9D91', '#059669', '#DC2626'] });
  const pm = d.metrics.filter(m => m.unit === '%' && m.value !== null && m.key !== 'release_readiness');
  chart('a-perf', 'bar', pm.map(m => m.name), pm.map(m => m.value), { horizontal: true, max: 100, colors: pm.map(m => m.value >= 80 ? '#0F9D91' : m.value >= 60 ? '#F59E0B' : '#DC2626') });
};

/* ============ TRACEABILITY ============ */
App.routes.traceability = async view => {
  const d = await api('/rtm'); const s = d.summary;
  const st = { q: '', gap: '' };
  view.innerHTML = `
  <div class="page-h"><div><div class="kicker">VERIFY · Requirements traceability matrix</div><h1>Traceability matrix</h1><p>Stakeholder need → Requirement → Design → Implementation → Test case → Test result → Defect → CAPA. Gaps are detected automatically.</p></div>
    <div style="display:flex;gap:8px"><a class="btn primary" href="/api/rtm/export.xlsx">${ico('down')} RTM Excel</a><a class="btn" href="/api/rtm/export.csv">${ico('down')} RTM CSV</a></div></div>
  <div class="kpis" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin-bottom:14px">
    ${[['Without test cases', s.without_tests, 'No test case', 'red'], ['Without approval', s.without_approval, 'No approval', 'amber'], ['Failed tests', s.with_failed_tests, 'Failed test', 'red'], ['Open defects', s.with_open_defects, 'Open defect', 'amber'], ['Missing links', s.missing_links, 'Missing', 'amber'], ['Unverified', s.unverified, 'Unverified', 'amber']].map(([l, v, g, c]) => `<div class="kpi ${c}" style="cursor:pointer" data-gap="${g}"><small>${l}</small><b>${v}</b><span>of ${s.total} requirements</span></div>`).join('')}</div>
  <div class="toolbar"><input class="grow" id="q" placeholder="Search requirement, design, test or defect ID..."><select id="gap"><option value="">All requirements</option><option>No test case</option><option>No approval</option><option>Failed test</option><option>Open defect</option><option>Missing</option><option>Unverified</option><option>Verified</option></select><button class="btn sm" id="clr">Clear</button><span class="when" id="cnt"></span></div>
  <div id="tbl"></div>
  <div class="card mt"><h3>Orphan records <small>no requirement link</small></h3>${s.orphan_tests + s.orphan_defects ? `<div>Tests: ${chips(d.orphan_tests.map(x => x.id).join(', '))}<br>Defects: ${chips(d.orphan_defects.map(x => x.id).join(', '), 'bad')}</div>` : '<span class="when">Every test case and defect is linked to a requirement (backward traceability complete).</span>'}</div>`;
  const tc = t => `<span class="chip ${t.status === 'Passed' ? 'ok' : t.status === 'Failed' ? 'bad' : 'warn'}" title="${esc(t.status)}">${esc(t.id)}</span>`;
  function draw() {
    const q = st.q.toLowerCase();
    const rows = d.rows.filter(r => {
      if (q && !JSON.stringify([r.id, r.title, r.design_ref, r.impl_ref, r.tests, r.defects, r.need_id]).toLowerCase().includes(q)) return false;
      if (st.gap === 'Verified') return r.verified;
      if (st.gap === 'Unverified') return !r.verified && r.status !== 'Rejected';
      if (st.gap === 'Missing') return r.gaps.some(g => g.startsWith('Missing'));
      return !st.gap || r.gaps.includes(st.gap);
    });
    $('#cnt').textContent = rows.length + ' requirements';
    $('#tbl').innerHTML = rows.length ? `<div class="tablewrap"><table><thead><tr><th>Req ID</th><th>Requirement</th><th>Category</th><th>Priority</th><th>Risk</th><th>Need</th><th>Design</th><th>Implementation</th><th>Test case(s)</th><th>Result</th><th>Defects</th><th>CAPA</th><th>Approval</th><th>Gaps</th></tr></thead><tbody>${rows.map(r => `<tr class="clickable" onclick="location.hash='#/requirements?open=${r.id}'"><td class="mono">${r.id}</td><td><b>${esc(r.title)}</b></td><td>${esc(r.category)}</td><td>${badge(r.priority)}</td><td>${badge(r.risk)}</td><td>${chips(r.need_id)}</td><td>${r.design_ref ? `<span class="sub">${esc(r.design_ref)}</span>` : '<span class="chip bad">missing</span>'}</td><td>${r.impl_ref ? `<span class="sub">${esc(r.impl_ref)}</span>` : '<span class="when">-</span>'}</td><td><div class="chips">${r.tests.map(tc).join('') || '<span class="chip bad">none</span>'}</div></td><td>${badge(r.test_result)}</td><td><div class="chips">${r.defects.map(x => `<span class="chip ${['Resolved', 'Closed'].includes(x.status) ? 'ok' : 'bad'}" title="${esc(x.status)}">${esc(x.id)}</span>`).join('') || '<span class="when">-</span>'}</div></td><td>${chips(r.capas.map(c => c.id).join(', '))}</td><td>${badge(r.approval)}</td><td>${r.gaps.map(g => `<span class="badge b-amber" style="margin:1px">${esc(g)}</span>`).join('') || badge('Complete', 'green')}</td></tr>`).join('')}</tbody></table></div>` : '<div class="tablewrap"><div class="empty">No requirements match.</div></div>';
  }
  $('#q').oninput = e => { st.q = e.target.value; draw(); };
  $('#gap').onchange = e => { st.gap = e.target.value; draw(); };
  $('#clr').onclick = () => { st.q = st.gap = ''; $('#q').value = ''; $('#gap').value = ''; draw(); };
  $$('[data-gap]').forEach(el => el.onclick = () => { st.gap = el.dataset.gap; $('#gap').value = st.gap === 'Missing' ? 'Missing' : st.gap; draw(); });
  draw();
};

/* ============ RELEASE MANAGEMENT ============ */
App.routes.release = async view => {
  const d = await api('/release');
  const cls = d.recommendation === 'GO' ? 'GO' : d.recommendation === 'NO-GO' ? 'NO-GO' : 'CONDITIONAL';
  view.innerHTML = `
  <div class="page-h"><div><div class="kicker">REPORT · Release readiness gate</div><h1>Release management</h1><p>${esc(d.release_version)} — mandatory checks are evaluated from live data. GO cannot be recorded while any mandatory check is failed or pending.</p></div>
    <div style="display:flex;gap:8px"><a class="btn" href="/api/report/pdf">${ico('down')} Quality report (PDF)</a><button class="btn primary" id="decide">Record release decision</button></div></div>
  <div class="grid g-main">
    <div class="card" style="padding:0"><h3 style="padding:16px 18px 0">Mandatory checks <small>${d.passed} passed · ${d.failed} failed · ${d.pending} pending</small></h3>
      ${d.checks.map(c => `<div class="check"><div class="ic ${c.status}">${c.status === 'Passed' ? '✓' : c.status === 'Failed' ? '✕' : '…'}</div><div><b>${esc(c.name)}</b>${c.manual ? ' <span class="badge b-blue">manual confirmation</span>' : ''}<small>${esc(c.detail)}</small>${c.manual && c.note ? `<small>Evidence: ${esc(c.note)} (${esc(c.updated_by)}, ${esc(c.updated_on)})</small>` : ''}</div><div style="text-align:right">${badge(c.status)}${c.manual ? `<br><button class="btn sm" style="margin-top:6px" data-m="${c.key}">${c.confirmed ? 'Update' : 'Confirm'}</button>` : ''}</div></div>`).join('')}</div>
    <div class="grid" style="gap:16px;align-content:start">
      <div class="decision ${cls}"><small>RECOMMENDED DECISION</small><b>${esc(d.recommendation)}</b><small>${pctTxt(d.readiness_pct)} READINESS</small><div class="bar" style="background:rgba(255,255,255,.3);margin-top:12px"><i style="width:${d.readiness_pct}%;background:#fff"></i></div></div>
      <div class="card"><h3>Decision rules</h3><ul class="list"><li><span class="pip ok"></span><span><b>GO</b> only if all ${d.total} checks pass.</span></li><li><span class="pip warning"></span><span><b>CONDITIONAL GO</b> only if no critical defects, pass-rate baseline met, security tests passed and security/release reviews approved; conditions must be documented.</span></li><li><span class="pip critical"></span><span><b>NO-GO</b> can always be recorded.</span></li></ul></div>
      <div class="card"><h3>Decision history</h3><ul class="list">${d.decisions.map(x => `<li><span class="pip ${x.decision === 'GO' ? 'ok' : x.decision === 'NO-GO' ? 'critical' : 'warning'}"></span><span><b>${esc(x.decision)}</b> · ${esc(x.release_version)}<br><span class="when">${esc(x.decided_by)} · ${esc(x.decided_on)}</span><br>${esc(x.rationale)}${x.conditions ? `<br><i>Conditions: ${esc(x.conditions)}</i>` : ''}</span></li>`).join('') || '<li class="when">No release decision recorded yet.</li>'}</ul></div>
    </div></div>`;
  $$('[data-m]').forEach(b => b.onclick = () => {
    const c = d.checks.find(x => x.key === b.dataset.m);
    openForm({ title: c.name, sub: 'Record the evidence reference (e.g. backup log ID, rollback plan document).', values: { confirmed: c.confirmed ? 'yes' : 'no', note: c.note },
      fields: [{ k: 'confirmed', label: 'Confirmed?', type: 'select', req: true, options: [['yes', 'Yes - confirmed'], ['no', 'No - not confirmed']] }, { k: 'note', label: 'Evidence / reference', type: 'textarea', req: false }], submitLabel: 'Save',
      onSubmit: async v => { await api('/release/manual/' + c.key, { method: 'POST', body: { confirmed: v.confirmed === 'yes', note: v.note } }); toast('Check updated'); App.routes.release(view); App.refreshBadges(); } });
  });
  $('#decide').onclick = () => openForm({ title: 'Record release decision', sub: `System recommendation: ${d.recommendation}`, values: { decision: d.recommendation },
    fields: [{ k: 'decision', label: 'Decision', type: 'select', req: true, options: m => m.release_decisions }, { k: 'rationale', label: 'Rationale', type: 'textarea', req: true }, { k: 'conditions', label: 'Conditions (required for CONDITIONAL GO)', type: 'textarea' }],
    submitLabel: 'Record decision', onSubmit: async v => { await api('/release/decision', { method: 'POST', body: v }); toast('Release decision recorded'); App.routes.release(view); } });
};

/* ============ DOCUMENTS (QMS library) ============ */
const DOC_FIELDS = [{ k: 'title', label: 'Document title', type: 'text', req: true, wide: true }, { k: 'doc_type', label: 'Document category', type: 'select', req: true, options: m => m.doc_types },
  { k: 'version', label: 'Version', type: 'text', req: true, hint: 'Changing the version records a new revision and re-opens approval.' }, { k: 'owner', label: 'Document owner', type: 'select', req: true, options: team },
  { k: 'approval_status', label: 'Approval status', type: 'select', req: true, options: m => m.doc_status }, { k: 'review_date', label: 'Next review date', type: 'date' },
  { k: 'description', label: 'Description', type: 'textarea' }, { k: 'change_summary', label: 'Change summary (recorded in version history)', type: 'textarea' }];
const dlBtn = (id, f, label) => `<a class="dlbtn" href="/api/documents/${id}/download/${f}" download>${label} ${ico('down')}</a>`;

async function viewDoc(id, reload) {
  const d = await api(`/documents/${id}/content`);
  const o = drawer(`<div style="display:flex;justify-content:space-between;gap:10px"><div><div class="mono">${esc(d.id)} · v${esc(d.version)}</div><h2>${esc(d.title)}</h2></div><button class="btn sm" id="dclose">Close</button></div>
    <div class="meta">${badge(d.approval_status)} <span class="badge b-navy">${esc(d.doc_type)}</span></div>
    <div class="actions" style="justify-content:flex-start;margin:0 0 8px">${dlBtn(d.id, 'word', 'Download Word (.docx)')}${dlBtn(d.id, 'excel', 'Download Excel (.xlsx)')}</div>
    <div class="actions" style="justify-content:flex-start;margin:0">${d.approval_status !== 'Approved' ? '<button class="btn sm teal" id="d-appr">Approve this version</button>' : ''}<button class="btn sm" id="d-rev">New revision</button><button class="btn sm" id="d-edit">Edit details</button></div>
    <div class="sect">Document control</div><dl class="kv"><dt>Document ID</dt><dd>${esc(d.id)}</dd><dt>Version</dt><dd>${esc(d.version)}</dd><dt>Owner</dt><dd>${esc(d.owner)}</dd><dt>Creation date</dt><dd>${dt(d.created_on)}</dd><dt>Review date</dt><dd>${dt(d.review_date)}</dd><dt>Last updated</dt><dd>${dt(d.updated_on)}</dd><dt>Approval status</dt><dd>${esc(d.approval_status)}</dd><dt>Approved by</dt><dd>${esc(d.approved_by || 'Not yet approved')}${d.approved_on ? ' on ' + dt(d.approved_on) : ''}</dd></dl>
    <div class="sect">Purpose</div><p style="margin:0">${esc(d.outline.purpose)}</p>
    <div class="sect">Contents (${d.outline.sections.length} sections)</div>${d.outline.sections.map((s, n) => `<details ${n < 2 ? 'open' : ''} style="margin:4px 0"><summary><b>${n + 1}. ${esc(s.heading)}</b></summary><ul style="margin:6px 0 6px 18px;padding:0;color:var(--mute);font-size:13px">${s.items.slice(0, 6).map(i => `<li>${esc(i)}</li>`).join('')}</ul></details>`).join('')}
    <div class="sect">Version history and approval records</div><div class="tablewrap"><table><thead><tr><th>Version</th><th>Date</th><th>By</th><th>Change</th><th>Status</th><th>Approved by</th></tr></thead><tbody>${d.versions.map(v => `<tr><td><b>${esc(v.version)}</b></td><td class="nw">${dt(v.changed_on)}</td><td>${esc(v.changed_by)}</td><td>${esc(v.summary)}</td><td>${badge(v.approval_status)}</td><td>${esc(v.approved_by || '-')}</td></tr>`).join('')}</tbody></table></div>
    <div class="sect">Used by QMS modules</div><div class="chips">${d.modules.map(m => `<a class="chip" href="#/${m}">${esc(TITLES[m] || m)}</a>`).join('') || '-'}</div>`);
  $('#dclose', o).onclick = closeDrawer;
  const after = async () => { App.docs = await api('/documents'); closeDrawer(); if (reload) await reload(); };
  const ap = $('#d-appr', o);
  if (ap) ap.onclick = async () => { if (!await confirmBox(`Approve ${d.id} version ${d.version} as ${App.meta.settings.current_user}? The approval is recorded in the version history.`, 'Approve')) return; try { await api('/documents/' + d.id, { method: 'PUT', body: { approval_status: 'Approved', change_summary: `Version ${d.version} approved` } }); toast(`${d.id} approved`); await after(); viewDoc(d.id, reload); } catch (e) { toast(e.message, true); } };
  $('#d-edit', o).onclick = () => openForm({ title: 'Edit ' + d.id, fields: DOC_FIELDS, values: d, submitLabel: 'Save', onSubmit: async v => { await api('/documents/' + d.id, { method: 'PUT', body: v }); toast(d.id + ' updated'); await after(); viewDoc(d.id, reload); } });
  $('#d-rev', o).onclick = () => openForm({ title: `New revision of ${d.id}`, sub: `Current version ${d.version}. A new revision returns the document to review and needs re-approval.`,
    fields: [{ k: 'version', label: 'New version number', type: 'text', req: true }, { k: 'summary', label: 'What changed?', type: 'textarea', req: true }, { k: 'review_date', label: 'Next review date', type: 'date' }], values: { review_date: d.review_date },
    submitLabel: 'Create revision', onSubmit: async v => { await api(`/documents/${d.id}/revise`, { method: 'POST', body: v }); toast(`${d.id} revised to v${v.version}`); await after(); viewDoc(d.id, reload); } });
}

App.routes.documents = async (view, params) => {
  const s = App.meta.settings;
  const st = App.docState = App.docState || { q: '', type: '', status: '' };
  const today = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: '2-digit', year: 'numeric' }).replace(',', '').toUpperCase();
  const all = await api('/documents'); App.docs = all;
  const approved = all.filter(d => d.approval_status === 'Approved').length;
  view.innerHTML = `
  <div class="lib-top"><span>PROJECTS &nbsp;/&nbsp; ${esc(s.project_name.toUpperCase())} &nbsp;/&nbsp; <b style="color:var(--navy)">DOCUMENTS</b></span>
    <span style="display:flex;gap:10px;align-items:center">${esc(today)} <button class="btn sm" id="refresh" title="Refresh">↻</button><a class="btn sm" href="/api/handbook.docx" style="border-radius:0">Quality handbook ↗</a></span></div>
  <div class="lib-title"><div><div class="kick">REFERENCE / CONTROLLED DOCUMENTS</div><h1>QMS Library<i>.</i></h1><p>Project-ready plans, procedures, templates, and checklists.</p></div><div class="lib-rev">CONTROLLED SET · REV ${esc(s.library_revision || '1.0')}<br><span style="opacity:.7">${approved}/${all.length} APPROVED</span></div></div>
  <div class="banner"><div class="q">Q<span style="position:absolute;bottom:3px;font-size:14px;color:#60a5fa">/</span></div><div><h3>Hospital Management Software Quality Baseline</h3><p>The Project Quality Plan is the control document. Procedures define how quality evidence is produced, templates capture approved records, and checklists ensure consistent verification.</p></div></div>
  <div class="toolbar"><input class="grow" id="dq" placeholder="Search documents by ID, title, owner or content (e.g. five whys, rollback)..." value="${esc(st.q)}">
    <select id="dtype"><option value="">Type: All</option>${App.meta.doc_types.map(t => `<option ${st.type === t ? 'selected' : ''}>${t}</option>`).join('')}</select>
    <select id="dstat"><option value="">Approval: All</option>${App.meta.doc_status.map(t => `<option ${st.status === t ? 'selected' : ''}>${t}</option>`).join('')}</select>
    <button class="btn sm" id="dclr">Clear</button><span class="when" id="dcount"></span></div>
  <div id="cards"></div>
  <div class="lib-foot">Approvals: <b>QA Lead</b> owns quality direction · <b>Project Manager</b> authorizes business release · <b>CCB</b> controls baseline changes · <b>Hospital stakeholder</b> accepts requirements</div>
  <div class="page-h mt"><div><div class="kicker">Document control register</div><h2 style="margin:0">Controlled document register</h2></div></div><div id="register"></div>`;
  const load = async () => {
    const qs = new URLSearchParams({ q: st.q, doc_type: st.type, approval_status: st.status });
    const docs = await api('/documents?' + qs);
    $('#dcount').textContent = `${docs.length} of ${all.length} documents`;
    $('#cards').innerHTML = docs.length ? `<div class="libgrid">${docs.map(d => { const n = all.findIndex(x => x.id === d.id) + 1; return `<div class="doccard ${n === 1 ? 'first' : ''}"><div class="tp"><span>${esc(d.doc_type)}</span><span>${String(n).padStart(2, '0')}</span></div><div class="st">${badge(d.approval_status)}</div>
      <h4>${esc(d.title)}</h4><p>${esc(d.description)}</p><div class="when" style="margin-bottom:8px;font-family:var(--mono);font-size:10.5px">${esc(d.id)} · v${esc(d.version)} · ${esc(d.owner)}<br>Review ${dt(d.review_date)} · ${d.version_count} version${d.version_count === 1 ? '' : 's'}</div>
      <div class="dl">Download as</div><div class="dls">${dlBtn(d.id, 'word', 'Word')}${dlBtn(d.id, 'excel', 'Excel')}<button class="dlbtn" data-v="${d.id}">View</button></div></div>`; }).join('')}</div>` : '<div class="tablewrap"><div class="empty">No documents match the search and filters.</div></div>';
    $('#register').innerHTML = docs.length ? `<div class="tablewrap"><table><thead><tr><th>ID</th><th>Title</th><th>Version</th><th>Owner</th><th>Created</th><th>Review date</th><th>Last updated</th><th>Approval status</th><th>Actions</th></tr></thead><tbody>
      ${docs.map(d => `<tr><td class="mono">${d.id}</td><td><b>${esc(d.title)}</b></td><td>v${esc(d.version)}</td><td>${esc(d.owner)}</td><td class="nw">${dt(d.created_on)}</td><td class="nw">${dt(d.review_date)}</td><td class="nw">${dt(d.updated_on)}</td><td>${badge(d.approval_status)}</td><td style="white-space:nowrap"><button class="btn sm" data-v="${d.id}">View</button> <a class="btn sm" href="/api/documents/${d.id}/download/word" download>Word</a> <a class="btn sm" href="/api/documents/${d.id}/download/excel" download>Excel</a></td></tr>`).join('')}</tbody></table></div>` : '';
    $$('[data-v]').forEach(b => b.onclick = () => viewDoc(b.dataset.v, async () => { Object.assign(all, await api('/documents')); App.routes.documents(view, new URLSearchParams()); }));
  };
  let tm; $('#dq').oninput = e => { clearTimeout(tm); tm = setTimeout(() => { st.q = e.target.value; load(); }, 250); };
  $('#dtype').onchange = e => { st.type = e.target.value; load(); };
  $('#dstat').onchange = e => { st.status = e.target.value; load(); };
  $('#dclr').onclick = () => { st.q = st.type = st.status = ''; $('#dq').value = ''; $('#dtype').value = ''; $('#dstat').value = ''; load(); };
  $('#refresh').onclick = () => App.routes.documents(view, new URLSearchParams());
  await load();
  const open = params && params.get('open');
  if (open) viewDoc(open, () => App.routes.documents(view, new URLSearchParams()));
};

/* ============ SETTINGS ============ */
App.routes.settings = async view => {
  const [set, tm] = await Promise.all([api('/settings'), api('/team')]);
  view.innerHTML = `
  <div class="page-h"><div><div class="kicker">Configuration</div><h1>Settings</h1><p>Project information, team members and roles (editable), and the project baseline for the test pass rate.</p></div></div>
  <div class="grid g2"><div class="card"><h3>Project information</h3><div class="form" id="pf">
    ${[['project_name', 'Project name'], ['team_name', 'Team'], ['project_version', 'Release label'], ['release_version', 'Release version'], ['organisation', 'Organisation'], ['library_revision', 'QMS library controlled-set revision'], ['min_pass_rate', 'Minimum test pass rate (%) - proposed baseline']].map(([k, l]) => `<div class="f ${k === 'organisation' ? 'wide' : ''}"><label>${l}</label><input data-k="${k}" value="${esc(set[k] || '')}"></div>`).join('')}</div><div id="perr"></div>
    <div class="actions"><button class="btn primary" id="savep">Save project settings</button></div></div>
  <div class="card"><h3>Team members and roles <button class="btn sm primary" id="addm">${ico('plus')} Add</button></h3><table><thead><tr><th>Name</th><th>Role</th><th>Email</th><th></th></tr></thead><tbody>
    ${tm.map(t => `<tr><td><b>${esc(t.name)}</b></td><td>${esc(t.role)}</td><td>${esc(t.email || '-')}</td><td style="white-space:nowrap"><button class="btn sm" data-te="${t.id}">Edit</button> <button class="btn sm danger" data-td="${t.id}">Remove</button></td></tr>`).join('')}</tbody></table>
    <p class="when" style="margin-top:10px">Renaming a member updates their name across requirements, reviews, tests, defects, CAPA and documents.</p></div></div>
  <div class="card mt"><h3>Demonstration data</h3><p style="color:var(--mute)">Reset the database to the original fictional demonstration records (no real patient data). All changes are lost.</p><button class="btn danger" id="reset">Reset demo data</button></div>`;
  $('#savep').onclick = async () => {
    const body = Object.fromEntries($$('#pf input').map(i => [i.dataset.k, i.value]));
    try { await api('/settings', { method: 'PUT', body }); App.meta = await api('/meta'); chrome(); toast('Settings saved'); } catch (e) { $('#perr').innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  };
  const mf = [{ k: 'name', label: 'Name', type: 'text', req: true }, { k: 'role', label: 'Role', type: 'select', req: true, options: m => m.team_roles }, { k: 'email', label: 'Email', type: 'text' }];
  const again = async () => { App.meta = await api('/meta'); chrome(); App.routes.settings(view); };
  $('#addm').onclick = () => openForm({ title: 'Add team member', fields: mf, onSubmit: async v => { await api('/team', { method: 'POST', body: v }); toast('Member added'); again(); } });
  $$('[data-te]').forEach(b => b.onclick = () => { const t = tm.find(x => x.id == b.dataset.te); openForm({ title: 'Edit team member', fields: mf, values: t, onSubmit: async v => { await api('/team/' + t.id, { method: 'PUT', body: v }); toast('Member updated'); again(); } }); });
  $$('[data-td]').forEach(b => b.onclick = async () => { if (await confirmBox('Remove this team member? Existing records keep their name.', 'Remove')) { try { await api('/team/' + b.dataset.td, { method: 'DELETE' }); again(); } catch (e) { toast(e.message, true); } } });
  $('#reset').onclick = async () => { if (await confirmBox('Reset ALL data to the demonstration dataset?', 'Reset')) { await api('/reset-demo-data', { method: 'POST' }); App.meta = await api('/meta'); chrome(); toast('Demo data restored'); location.hash = '#/dashboard'; render(); } };
};
