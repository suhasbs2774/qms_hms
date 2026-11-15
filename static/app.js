/* HOSPITAL QUALITY OS - core frontend (helpers, form engine, generic list module, router) */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const App = { meta: null, charts: {}, routes: {}, alerts: [] };

async function api(path, opts = {}) {
  const o = { headers: { 'Content-Type': 'application/json' }, ...opts };
  if (o.body && typeof o.body !== 'string') o.body = JSON.stringify(o.body);
  const r = await fetch('/api' + path, o);
  let data = null;
  try { data = await r.json(); } catch (e) { /* non-json */ }
  if (!r.ok) throw new Error((data && data.error) || `Request failed (${r.status})`);
  return data;
}

function toast(msg, err) {
  const t = document.createElement('div');
  t.className = 'toast' + (err ? ' err' : '');
  t.textContent = msg;
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), err ? 6500 : 3200);
}

const ICON = {
  dashboard: '<path d="M3 13h8V3H3zM13 21h8V11h-8zM13 3v6h8V3zM3 21h8v-6H3z"/>',
  requirements: '<path d="M9 5h10M9 12h10M9 19h10M4 5l1 1 2-2M4 12l1 1 2-2M4 19l1 1 2-2"/>',
  reviews: '<path d="M9 12l2 2 4-4"/><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  testing: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/>',
  defects: '<path d="M12 8v5M12 17h.01"/><path d="M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  traceability: '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10M6 8l5 8M18 8l-5 8"/>',
  analytics: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
  capa: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  release: '<path d="M5 15c-1 3-1 5-1 5s2 0 5-1M14 4c3-1 6-1 6-1s0 3-1 6l-7 7-5-5zM9 12l-4-1 3-3 4 1"/>',
  documents: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  down: '<path d="M12 4v12M6 12l6 6 6-6M5 21h14"/>',
  plus: '<path d="M12 5v14M5 12h14"/>'
};
const ico = (n, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON[n] || ''}</svg>`;

const NAV = [
  ['dashboard', 'Dashboard'], ['requirements', 'Requirements'], ['reviews', 'Reviews'], ['testing', 'Testing'], ['defects', 'Defects'],
  ['traceability', 'Traceability'], ['analytics', 'Quality Analytics'], ['capa', 'CAPA'], ['release', 'Release Management'],
  ['documents', 'Documents'], ['settings', 'Settings']
];
const TITLES = Object.fromEntries(NAV);

const BADGE = {
  'Approved': 'green', 'Verified': 'green', 'Passed': 'green', 'Closed': 'green', 'Implemented': 'teal', 'GO': 'green', 'Resolved': 'teal', 'good': 'green',
  'Approved with actions': 'teal', 'Under Review': 'amber', 'Pending': 'amber', 'Retesting': 'amber', 'In Progress': 'blue', 'Assigned': 'blue', 'Verification': 'amber',
  'Action Planned': 'blue', 'Investigation': 'blue', 'Draft': 'gray', 'Open': 'red', 'Not Run': 'gray', 'Failed': 'red', 'Blocked': 'amber', 'Rejected': 'red',
  'Rework required': 'red', 'Reopened': 'red', 'Critical': 'red', 'Highest': 'red', 'High': 'amber', 'Medium': 'blue', 'Low': 'gray', 'NO-GO': 'red',
  'CONDITIONAL GO': 'amber', 'warning': 'amber', 'critical': 'red', 'No test': 'gray', 'Not approved': 'amber', 'Obsolete': 'gray', 'n/a': 'gray'
};
const badge = (t, c) => t === null || t === undefined || t === '' ? '' : `<span class="badge b-${c || BADGE[t] || 'gray'}">${esc(t)}</span>`;
const chips = (ids, status) => (ids || '').toString().split(/,\s*/).filter(Boolean).map(i => `<span class="chip ${status || ''}">${esc(i)}</span>`).join('') || '<span class="when">-</span>';
const fmtNum = v => v === null || v === undefined ? 'n/a' : v;
const pctTxt = v => v === null || v === undefined ? 'n/a' : v + '%';
const dt = s => s ? String(s).slice(0, 10) : '-';

/* ---------------- modal / drawer */
function modal(html, cls = '') {
  const w = document.createElement('div');
  w.className = 'modal-wrap';
  w.innerHTML = `<div class="modal ${cls}">${html}</div>`;
  w.addEventListener('mousedown', e => { if (e.target === w) w.remove(); });
  document.body.appendChild(w);
  return w;
}
function confirmBox(msg, okLabel = 'Delete') {
  return new Promise(res => {
    const w = modal(`<h2>Please confirm</h2><p style="color:var(--mute)">${esc(msg)}</p><div class="actions"><button class="btn" id="c-no">Cancel</button><button class="btn danger" id="c-yes">${esc(okLabel)}</button></div>`, 'sm');
    $('#c-no', w).onclick = () => { w.remove(); res(false); };
    $('#c-yes', w).onclick = () => { w.remove(); res(true); };
  });
}
function drawer(html) {
  closeDrawer();
  const o = document.createElement('div');
  o.className = 'overlay';
  o.id = 'drawer-overlay';
  o.innerHTML = `<div class="drawer">${html}</div>`;
  o.addEventListener('mousedown', e => { if (e.target === o) o.remove(); });
  document.body.appendChild(o);
  return o;
}
const closeDrawer = () => { const d = $('#drawer-overlay'); if (d) d.remove(); };

/* ---------------- form engine */
function optsOf(f) { return typeof f.options === 'function' ? f.options(App.meta) : (f.options || []); }
function fieldHtml(f, v) {
  const id = 'f_' + f.k;
  const lab = `<label for="${id}">${esc(f.label)}${f.req ? ' <i>*</i>' : ''}</label>`;
  const hint = f.hint ? `<small>${esc(f.hint)}</small>` : '';
  const ro = f.readonly ? 'disabled' : '';
  let ctl = '';
  if (f.type === 'textarea') ctl = `<textarea id="${id}" ${ro} placeholder="${esc(f.placeholder || '')}">${esc(v ?? '')}</textarea>`;
  else if (f.type === 'select') {
    const o = optsOf(f).map(x => Array.isArray(x) ? x : [x, x]);
    ctl = `<select id="${id}" ${ro}>${f.req ? '' : '<option value=""></option>'}${o.map(([val, l]) => `<option value="${esc(val)}" ${String(v ?? '') === String(val) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  } else if (f.type === 'multi') {
    const sel = new Set(v || []);
    ctl = `<div class="checks" id="${id}">${optsOf(f).map(([val, l]) => `<label><input type="checkbox" value="${esc(val)}" ${sel.has(val) ? 'checked' : ''}> <span><b class="mono">${esc(val)}</b> ${esc(l)}</span></label>`).join('') || '<span class="when">No items</span>'}</div>`;
  } else if (f.type === 'checklist') ctl = `<div class="checks" id="${id}"></div>`;
  else ctl = `<input id="${id}" type="${f.type === 'date' ? 'date' : f.type === 'number' ? 'number' : 'text'}" value="${esc(v ?? '')}" ${ro} placeholder="${esc(f.placeholder || '')}">`;
  return `<div class="f ${f.wide || f.type === 'textarea' || f.type === 'multi' || f.type === 'checklist' ? 'wide' : ''}">${lab}${ctl}${hint}</div>`;
}
function renderChecklist(w, values) {
  const t = $('#f_review_type', w);
  const box = $('#f_checklist', w);
  if (!t || !box) return;
  const items = App.meta.checklists[t.value] || [];
  const cur = values.checklist || {};
  box.innerHTML = items.map(i => `<label><input type="checkbox" data-item="${esc(i)}" ${cur[i] ? 'checked' : ''}> ${esc(i)}</label>`).join('');
}
function collect(w, fields) {
  const out = {};
  for (const f of fields) {
    if (f.readonly && !f.send) continue;
    const el = $('#f_' + f.k, w);
    if (!el) continue;
    if (f.type === 'multi') out[f.k] = $$('input:checked', el).map(i => i.value);
    else if (f.type === 'checklist') out[f.k] = Object.fromEntries($$('input', el).map(i => [i.dataset.item, i.checked]));
    else out[f.k] = el.value;
  }
  return out;
}
function openForm({ title, sub, fields, values = {}, submitLabel = 'Save', onSubmit }) {
  const w = modal(`<h2>${esc(title)}</h2>${sub ? `<div class="meta">${esc(sub)}</div>` : ''}<div class="form">${fields.map(f => fieldHtml(f, values[f.k])).join('')}</div><div id="ferr"></div><div class="actions"><button class="btn" id="f-cancel">Cancel</button><button class="btn primary" id="f-ok">${esc(submitLabel)}</button></div>`);
  if (fields.some(f => f.type === 'checklist')) {
    renderChecklist(w, values);
    $('#f_review_type', w).addEventListener('change', () => renderChecklist(w, {}));
  }
  $('#f-cancel', w).onclick = () => w.remove();
  $('#f-ok', w).onclick = async () => {
    const btn = $('#f-ok', w);
    btn.disabled = true;
    $('#ferr', w).innerHTML = '';
    try {
      await onSubmit(collect(w, fields));
      w.remove();
    } catch (e) {
      $('#ferr', w).innerHTML = `<div class="err">${esc(e.message)}</div>`;
      btn.disabled = false;
    }
  };
  return w;
}

/* ---------------- charts */
const PAL = { Critical: '#DC2626', High: '#F59E0B', Medium: '#2563EB', Low: '#0F9D91', Passed: '#0F9D91', Failed: '#DC2626', Blocked: '#F59E0B', 'Not Run': '#94A3B8', 'In Progress': '#2563EB' };
const SERIES = ['#2563EB', '#0F9D91', '#F59E0B', '#DC2626', '#14243A', '#7C3AED', '#64748B', '#0EA5E9', '#16A34A', '#DB2777', '#EA580C', '#475569'];
function chart(id, type, labels, values, opts = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  if (App.charts[id]) App.charts[id].destroy();
  const colors = opts.colors || labels.map((l, i) => PAL[l] || SERIES[i % SERIES.length]);
  const circ = type === 'doughnut' || type === 'pie';
  App.charts[id] = new Chart(el, {
    type,
    data: { labels, datasets: opts.datasets || [{ data: values, backgroundColor: colors, borderRadius: circ ? 0 : 6, borderWidth: circ ? 2 : 0, borderColor: '#fff', barThickness: opts.thickness }] },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: opts.horizontal ? 'y' : 'x',
      cutout: type === 'doughnut' ? '62%' : undefined,
      plugins: { legend: { display: circ || !!opts.legend, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } },
      scales: circ ? {} : { x: { grid: { display: false }, ticks: { font: { size: 11 } }, max: opts.horizontal ? opts.max : undefined }, y: { beginAtZero: true, grid: { color: '#EEF2F7' }, ticks: { precision: 0, font: { size: 11 } }, max: opts.horizontal ? undefined : opts.max } },
      animation: { duration: 700 }
    }
  });
}
const emptyChart = (id, msg) => { const el = document.getElementById(id); if (el) el.parentElement.innerHTML = `<div class="empty">${esc(msg)}</div>`; };

/* ---------------- generic list module */
function listModule(cfg) {
  return async function (view, params) {
    const st = cfg.state = cfg.state || { q: '', sort: cfg.defaultSort || 'id', dir: cfg.defaultDir || 'asc', f: {} };
    for (const [k, v] of params) { if (k === 'q') st.q = v; else if (cfg.filters.some(f => f.k === k)) st.f[k] = v; }
    view.innerHTML = `
      <div class="page-h"><div><div class="kicker">${esc(cfg.kicker)}</div><h1>${esc(cfg.title)}</h1><p>${esc(cfg.subtitle)}</p></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">${cfg.headerExtra ? cfg.headerExtra() : ''}<a class="btn" id="x-csv">${ico('down')} CSV</a><a class="btn" id="x-xlsx">${ico('down')} Excel</a>
        <button class="btn primary" id="new">${ico('plus')} ${esc(cfg.newLabel)}</button></div></div>
      ${cfg.summary ? '<div id="summary" class="kpis" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:14px"></div>' : ''}
      <div class="toolbar"><input class="grow" id="q" placeholder="Search ${esc(cfg.title.toLowerCase())}..." value="${esc(st.q)}">
        ${cfg.filters.map(f => `<select data-f="${f.k}"><option value="">${esc(f.label)}: All</option>${f.options(App.meta).map(o => `<option ${st.f[f.k] == o ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`).join('')}
        <button class="btn sm" id="clear">Clear</button><span class="when" id="count"></span></div>
      <div id="tbl"></div>`;
    let rows = [];
    const qs = () => new URLSearchParams({ q: st.q, sort: st.sort, dir: st.dir, ...Object.fromEntries(Object.entries(st.f).filter(([, v]) => v)) }).toString();
    const setLinks = () => { $('#x-csv').href = `/api/export/${cfg.api}.csv?${qs()}`; $('#x-xlsx').href = `/api/export/${cfg.api}.xlsx?${qs()}`; };
    async function load() {
      setLinks();
      try { rows = await api(`/${cfg.api}?${qs()}`); } catch (e) { $('#tbl').innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
      $('#count').textContent = `${rows.length} record${rows.length === 1 ? '' : 's'}`;
      if (cfg.summary) $('#summary').innerHTML = cfg.summary(rows);
      draw();
    }
    function draw() {
      if (!rows.length) { $('#tbl').innerHTML = '<div class="tablewrap"><div class="empty">No records match the current search and filters.</div></div>'; return; }
      $('#tbl').innerHTML = `<div class="tablewrap"><table><thead><tr>${cfg.columns.map(c => `<th class="${c.sort ? 'sortable' : ''}" data-s="${c.sort || ''}">${esc(c.label)}${st.sort === c.sort ? (st.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr class="clickable" data-id="${esc(r.id)}">${cfg.columns.map(c => `<td>${c.render ? c.render(r) : esc(r[c.k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
      $$('th.sortable').forEach(th => th.onclick = () => { const s = th.dataset.s; st.dir = st.sort === s && st.dir === 'asc' ? 'desc' : 'asc'; st.sort = s; load(); });
      $$('tbody tr').forEach(tr => tr.onclick = () => openDetail(rows.find(r => r.id === tr.dataset.id)));
    }
    async function openDetail(row) {
      if (cfg.fetchDetail) row = await cfg.fetchDetail(row);
      const acts = [...(cfg.actions ? cfg.actions(row, { reload: load, open: openDetail, edit, view }) : []),
        { label: 'Edit', fn: () => edit(row) }, { label: 'Delete', cls: 'danger', fn: () => remove(row) }];
      const o = drawer(`<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px"><div><div class="mono">${esc(row.id)}</div><h2>${esc(cfg.drawerTitle(row))}</h2></div><button class="btn sm" id="dclose">Close</button></div>
        <div class="meta">${cfg.drawerBadges ? cfg.drawerBadges(row) : ''}</div>
        <div class="actions" style="justify-content:flex-start;margin:0 0 6px">${acts.map((a, i) => `<button class="btn sm ${a.cls || ''}" data-a="${i}">${esc(a.label)}</button>`).join('')}</div>
        ${cfg.detail(row).map(s => `<div class="sect">${esc(s.title)}</div><dl class="kv">${s.rows.map(([l, v]) => `<dt>${esc(l)}</dt><dd>${v === undefined || v === null || v === '' ? '<span class="when">-</span>' : (typeof v === 'object' && v.html !== undefined ? v.html : esc(v))}</dd>`).join('')}</dl>`).join('')}
        ${cfg.drawerExtra ? cfg.drawerExtra(row) : ''}`);
      $('#dclose', o).onclick = closeDrawer;
      $$('[data-a]', o).forEach(b => b.onclick = () => acts[b.dataset.a].fn());
      if (cfg.afterDrawer) cfg.afterDrawer(o, row, { reload: load, open: openDetail });
    }
    function edit(row, over) {
      openForm({
        title: row ? `Edit ${row.id}` : `New ${cfg.single}`, sub: cfg.formSub, fields: cfg.fields, values: row || { ...(cfg.defaults ? cfg.defaults() : {}), ...(over || {}) },
        submitLabel: row ? 'Save changes' : `Create ${cfg.single}`,
        onSubmit: async data => {
          const saved = await api(row ? `/${cfg.api}/${row.id}` : `/${cfg.api}`, { method: row ? 'PUT' : 'POST', body: data });
          toast(`${saved.id} ${row ? 'updated' : 'created'}`);
          await load(); App.refreshBadges();
          if (row) openDetail(saved); else closeDrawer();
        }
      });
    }
    async function remove(row) {
      if (!await confirmBox(`Delete ${row.id}? This permanently removes the record${cfg.deleteNote ? '. ' + cfg.deleteNote : ''}.`)) return;
      try { await api(`/${cfg.api}/${row.id}`, { method: 'DELETE' }); toast(`${row.id} deleted`); closeDrawer(); load(); App.refreshBadges(); } catch (e) { toast(e.message, true); }
    }
    $('#new').onclick = () => edit(null);
    let tm; $('#q').oninput = e => { clearTimeout(tm); tm = setTimeout(() => { st.q = e.target.value; load(); }, 250); };
    $$('select[data-f]').forEach(s => s.onchange = () => { st.f[s.dataset.f] = s.value; load(); });
    $('#clear').onclick = () => { st.q = ''; st.f = {}; $('#q').value = ''; $$('select[data-f]').forEach(s => s.value = ''); load(); };
    if (cfg.afterRender) cfg.afterRender(view, { reload: load, edit, params });
    await load();
    const open = params.get('open');
    if (open) { try { openDetail(await api(`/${cfg.api}/${open}`)); } catch (e) { toast(e.message, true); } }
  };
}

/* ---------------- related controlled documents (integration of the QMS library) */
function docLinksHtml(keys) {
  const ds = (App.docs || []).filter(d => keys.includes(d.doc_key));
  return ds.map(d => `<a class="chip" href="#/documents?open=${d.id}" title="${esc(d.title)}">${esc(d.id)} ${esc(d.title)} v${esc(d.version)} · ${esc(d.approval_status)}</a>`).join(' ');
}
function docStrip(path, view) {
  const ds = (App.docs || []).filter(d => (d.modules || []).includes(path));
  if (!ds.length || path === 'documents' || path === 'dashboard') return;
  const el = document.createElement('div');
  el.className = 'docstrip';
  el.innerHTML = `<b>Controlled documents</b> ${ds.map(d => `<a href="#/documents?open=${d.id}"><span class="mono">${esc(d.id)}</span> ${esc(d.title)} <i>v${esc(d.version)}</i> ${badge(d.approval_status)}</a>`).join('')}<a href="#/documents">QMS Library →</a>`;
  const h = $('.page-h', view);
  if (h) h.after(el); else view.prepend(el);
}

/* ---------------- router + chrome */
function parseHash() {
  const h = location.hash.replace(/^#\/?/, '') || 'dashboard';
  const [path, qs] = h.split('?');
  return { path, params: new URLSearchParams(qs || '') };
}
async function render() {
  const { path, params } = parseHash();
  const route = App.routes[path] || App.routes.dashboard;
  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.r === path));
  $('#crumbs').innerHTML = `HOSPITAL QUALITY OS &nbsp;/&nbsp; <b>${esc(TITLES[path] || 'Dashboard')}</b>`;
  $('#sidebar').classList.remove('open');
  const view = $('#view');
  view.innerHTML = '<div class="loading">Loading...</div>';
  closeDrawer();
  $$('.modal-wrap').forEach(m => m.remove());
  Object.values(App.charts).forEach(c => c.destroy());
  App.charts = {};
  try { App.docs = await api('/documents'); } catch (e) { /* ignore */ }
  try { await route(view, params); docStrip(path, view); } catch (e) { console.error(e); view.innerHTML = `<div class="err">Could not load this page: ${esc(e.message)}</div>`; }
  window.scrollTo(0, 0);
}
App.refreshBadges = async function () {
  try {
    App.alerts = await api('/alerts');
    const n = App.alerts.length;
    const b = $('#bellcount'); b.textContent = n; b.hidden = !n;
    const d = await api('/defects?status=Open'); const dc = $('[data-r=defects] .count'); if (dc) { dc.textContent = d.length; dc.classList.toggle('red', d.length > 0); }
  } catch (e) { /* ignore */ }
};
function chrome() {
  const s = App.meta.settings;
  $('#nav').innerHTML = NAV.map(([r, t]) => `<a href="#/${r}" data-r="${r}">${ico(r)}<span>${t}</span>${r === 'defects' ? '<span class="count">0</span>' : ''}</a>`).join('');
  $('#sf-team').textContent = s.team_name; $('#sf-proj').textContent = s.project_name;
  $('#projchip').innerHTML = `<b>${esc(s.project_name)}</b>${esc(s.team_name)} · ${esc(s.project_version)}`;
  const me = App.meta.team.find(t => t.name === s.current_user) || App.meta.team[0];
  $('#uname').textContent = me.name; $('#urole').textContent = me.role; $('#avatar').textContent = me.name.split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase();
}
function wireChrome() {
  $('#menu').onclick = () => $('#sidebar').classList.toggle('open');
  const hideAll = () => { ['gresults', 'bellmenu', 'usermenu'].forEach(i => $('#' + i).hidden = true); };
  document.addEventListener('click', e => { if (!e.target.closest('.search,#bell,#bellmenu,.user,#usermenu')) hideAll(); });
  let tm;
  $('#gsearch').oninput = e => {
    clearTimeout(tm);
    tm = setTimeout(async () => {
      const q = e.target.value.trim(); const box = $('#gresults');
      if (q.length < 2) { box.hidden = true; return; }
      const res = await api('/search?q=' + encodeURIComponent(q));
      box.innerHTML = res.length ? res.map(r => `<div class="it" data-r="${r.route}" data-id="${esc(r.id)}"><small>${esc(r.id)}</small><span>${esc(r.title)}</span></div>`).join('') : '<div class="empty">No matches</div>';
      box.hidden = false;
      $$('.it', box).forEach(it => it.onclick = () => { box.hidden = true; $('#gsearch').value = ''; location.hash = `#/${it.dataset.r}?open=${encodeURIComponent(it.dataset.id)}`; });
    }, 220);
  };
  $('#bell').onclick = async () => {
    await App.refreshBadges();
    const m = $('#bellmenu');
    m.innerHTML = `<div style="padding:12px 14px;font-weight:700">Quality alerts <span class="when">(${App.alerts.length})</span></div>` + (App.alerts.length ? App.alerts.map(a => `<div class="it" data-r="${a.route}" data-id="${esc(a.id)}"><span class="pip ${a.level}"></span><span>${esc(a.text)}</span></div>`).join('') : '<div class="empty">No active alerts</div>');
    m.hidden = !m.hidden; $('#usermenu').hidden = true;
    $$('.it', m).forEach(it => it.onclick = () => { m.hidden = true; location.hash = `#/${it.dataset.r}` + (it.dataset.id ? `?open=${encodeURIComponent(it.dataset.id)}` : ''); });
  };
  $('#user').onclick = () => {
    const m = $('#usermenu');
    m.innerHTML = '<div style="padding:12px 14px;font-weight:700">Act as team member</div>' + App.meta.team.map(t => `<div class="it" data-n="${esc(t.name)}"><span><b>${esc(t.name)}</b><br><span class="when">${esc(t.role)}</span></span></div>`).join('');
    m.hidden = !m.hidden; $('#bellmenu').hidden = true;
    $$('.it', m).forEach(it => it.onclick = async () => { await api('/settings', { method: 'PUT', body: { current_user: it.dataset.n } }); App.meta = await api('/meta'); chrome(); m.hidden = true; toast('Acting as ' + it.dataset.n); render(); });
  };
}
async function boot() {
  App.meta = await api('/meta');
  chrome(); wireChrome();
  window.addEventListener('hashchange', render);
  await render();
  App.refreshBadges();
}
