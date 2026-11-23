/* Pension Helper – Pension Office dashboard. Built only from this office's uploaded data. */

const LC = {
  done: { cls: 'ok', text: 'Verified ✓' }, urgent: { cls: 'bad', text: 'Due soon' }, missed: { cls: 'bad', text: 'Missed' },
  open: { cls: 'warn', text: 'Due' }, not_open_yet: { cls: 'muted', text: 'Not open yet' }
};
const PAY = { ok: { cls: 'ok', text: 'Paid in full' }, problem: { cls: 'bad', text: 'Money pending' }, no_data: { cls: 'muted', text: 'No statement yet' } };
const LETTER = {
  draft: { cls: 'warn', text: 'Waiting for approval' }, approved: { cls: 'ok', text: 'Approved' }, rejected: { cls: 'muted', text: 'Rejected' },
  sent: { cls: 'info', text: 'Sent to bank' }, resolved: { cls: 'ok', text: 'Resolved' }
};
const TRACK_LABELS = { drafted: 'Drafted', approved: 'Approved by office', sent: 'Sent to bank', resolved: 'Resolved', rejected: 'Rejected by office' };
const LANGS = ['Hindi', 'English', 'Bengali', 'Marathi', 'Tamil', 'Telugu', 'Kannada', 'Gujarati', 'Malayalam', 'Punjabi', 'Odia', 'Urdu', 'Assamese'];
const chip = (map, key) => { const m = map[key] || { cls: 'muted', text: key }; return h('span', { class: 'chip ' + m.cls }, m.text); };
const issueText = t => ({ missing: 'pension not paid', short: 'pension paid short', missing_and_short: 'not paid and paid short' }[t] || t);
const asDate = iso => new Date(String(iso).length === 10 ? iso + 'T00:00:00' : iso);
const longDate = iso => asDate(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
const shortDate = iso => asDate(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

const state = { me: null, data: null, filter: 'all', lfilter: 'draft', search: '', openName: null, checks: {} };

/* ===== Data ===== */
async function load(quiet) {
  const btn = $('#refresh'); btn.disabled = true;
  try {
    const data = await api('/overview');
    if (!data || !data.totals || !Array.isArray(data.pensioners) || !Array.isArray(data.letters)) throw new Error('The server sent incomplete data. Please try again.');
    state.data = data;
    $('#error').classList.remove('show');
    render();
    if (quiet !== true) toast('Up to date');
  } catch (e) {
    $('#error-text').textContent = e.message; $('#error').classList.add('show');
  } finally { btn.disabled = false; }
}

function render() {
  const d = state.data, t = d.totals;
  $('#updated').textContent = 'Updated ' + new Date(d.generated_at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
  $('#title').textContent = state.me.workspace.name || 'Dashboard';
  if (!d.pensioners.length) {
    $('#content').replaceChildren(h('section', { class: 'empty-hero' },
      h('div', { class: 'eicon' }, icon('users')),
      h('h2', {}, 'No pensioners yet'),
      h('p', {}, 'Your dashboard is built only from your own data. Upload your pensioner list to see life certificates, payment checks and letters here.'),
      h('div', { style: 'display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:6px' },
        h('a', { class: 'btn primary large', href: '/uploads' }, 'Upload your pensioner list'),
        h('a', { class: 'btn large', href: '/api/templates/pensioner-list.csv', download: 'pensioner_list_template.csv' }, 'Download CSV template'),
        h('button', { class: 'btn large', type: 'button', onclick: () => openForm(null) }, 'Add one by hand'))));
    if (window.PH) PH.reveal($('#content'));
    return;
  }
  const total = Math.max(t.pensioners, 1);
  const seg = (n, color) => n ? h('span', { style: `width:${100 * n / total}%;background:${color}` }) : null;
  const notOpen = total - t.lc_submitted - t.lc_pending;
  $('#content').replaceChildren(
    h('section', { class: 'kpis' },
      h('div', { class: 'kpi ' + (t.lc_pending ? 'bad' : 'ok') }, h('div', { class: 'label' }, h('i'), 'Life certificates due'), h('div', { class: 'value', 'data-count': t.lc_pending, 'data-count-key': 'kpi-lc' }, t.lc_pending), h('div', { class: 'sub' }, d.days_left >= 0 ? d.days_left + ' days to the deadline' : 'Deadline passed')),
      h('div', { class: 'kpi ' + (t.amount_pending ? 'bad' : 'ok') }, h('div', { class: 'label' }, h('i'), 'Pension money pending'), h('div', { class: 'value', 'data-count': t.amount_pending, 'data-format': 'inr', 'data-count-key': 'kpi-amt' }, inr(t.amount_pending)), h('div', { class: 'sub' }, t.payment_problem_pensioners + ' pensioners · ' + t.payments_known + ' of ' + t.pensioners + ' with statements')),
      h('div', { class: 'kpi info' }, h('div', { class: 'label' }, h('i'), 'Letters to approve'), h('div', { class: 'value', 'data-count': t.letters_draft, 'data-count-key': 'kpi-letters' }, t.letters_draft), h('div', { class: 'sub' }, (t.letters_sent || 0) + ' sent · ' + (t.letters_resolved || 0) + ' resolved')),
      h('div', { class: 'kpi ok' }, h('div', { class: 'label' }, h('i'), 'Verified this year'), h('div', { class: 'value', 'data-count': t.lc_submitted, 'data-suffix': ' / ' + t.pensioners, 'data-count-key': 'kpi-verified' }, t.lc_submitted + ' / ' + t.pensioners), h('div', { class: 'sub' }, Math.round(100 * t.lc_submitted / total) + '% done'))),
    h('section', { class: 'deadline' },
      h('div', {}, h('strong', {}, 'Life certificate deadline: ' + d.deadline), h('span', { class: 'cell-sub', style: 'display:inline;margin-left:6px' }, '80+ from 1 October, others from 1 November')),
      h('div', { class: 'chip ' + (d.days_left <= 7 ? 'bad' : 'warn') }, d.days_left >= 0 ? d.days_left + ' days left' : 'Passed'),
      h('div', { class: 'bar', role: 'img', 'aria-label': t.lc_submitted + ' verified, ' + t.lc_pending + ' still due' },
        seg(t.lc_submitted, 'var(--ok)'), seg(t.lc_pending - t.lc_missed, 'var(--warn)'), seg(t.lc_missed, 'var(--bad)'), seg(notOpen, 'var(--track)')),
      h('div', { class: 'legend' },
        h('span', {}, h('i', { style: 'background:var(--ok)' }), t.lc_submitted + ' verified'),
        h('span', {}, h('i', { style: 'background:var(--warn)' }), (t.lc_pending - t.lc_missed) + ' still due'),
        t.lc_missed ? h('span', {}, h('i', { style: 'background:var(--bad)' }), t.lc_missed + ' missed') : null,
        h('span', {}, 'Families with an email get a reminder every morning at 9 AM'))),
    h('div', { class: 'grid' },
      h('section', { class: 'card', 'aria-labelledby': 'p-title' },
        h('div', { class: 'card-head' }, h('h2', { id: 'p-title' }, 'Pensioners'), h('span', { class: 'hint' }, 'Click a person to see details')),
        h('div', { class: 'toolbar' },
          h('input', { class: 'search', id: 'search', type: 'search', placeholder: 'Search by name or bank', 'aria-label': 'Search pensioners', value: state.search,
            oninput: e => { state.search = e.target.value; renderList(); } }),
          h('div', { class: 'seg', id: 'filters', role: 'group', 'aria-label': 'Filter pensioners' })),
        h('div', { class: 'list', id: 'list' })),
      h('section', { class: 'card', 'aria-labelledby': 'l-title' },
        h('div', { class: 'card-head' }, h('h2', { id: 'l-title' }, 'Letters to banks'),
          h('button', { class: 'btn small', id: 'draft-now', type: 'button', onclick: draftNow }, '✍ Draft letters now')),
        h('div', { class: 'toolbar' }, h('div', { class: 'seg', id: 'lfilters', role: 'group', 'aria-label': 'Filter letters' })),
        h('div', { id: 'letters' }))));
  renderList(); renderLetters();
  if (state.openName) openPensioner(state.openName, true);
  if (window.PH) {
    if (!state.revealed) { state.revealed = true; PH.reveal($('#content')); }  // fade up once; numbers count up
    else $('#content').querySelectorAll('[data-count]').forEach(PH.countUp);    // later refreshes: numbers move from the old value
  }
}

/* ===== Pensioner list ===== */
const FILTERS = [
  ['all', 'All', () => true],
  ['lc', 'Certificate due', p => ['open', 'urgent', 'missed'].includes(p.life_certificate.status)],
  ['pay', 'Money pending', p => p.payments.status === 'problem'],
  ['nodata', 'No statement', p => p.payments.status === 'no_data']
];
function renderList() {
  const ps = state.data.pensioners;
  $('#filters').replaceChildren(...FILTERS.map(([k, label, fn]) =>
    h('button', { type: 'button', 'aria-pressed': String(state.filter === k), onclick: () => { state.filter = k; renderList(); } }, label, h('span', { class: 'count' }, ps.filter(fn).length))));
  const fn = FILTERS.find(f => f[0] === state.filter)[2];
  const q = state.search.trim().toLowerCase();
  const urgent = p => ['urgent', 'missed'].includes(p.life_certificate.status) ? 1 : 0;
  const rows = ps.filter(fn).filter(p => !q || p.name.toLowerCase().includes(q) || (p.bank || '').toLowerCase().includes(q))
    .sort((a, b) => b.payments.amount_short - a.payments.amount_short || urgent(b) - urgent(a) || a.name.localeCompare(b.name));
  const list = $('#list');
  if (!rows.length) { list.replaceChildren(h('div', { class: 'empty' }, 'No pensioners match.')); return; }
  list.replaceChildren(...rows.map(p => {
    const lc = p.life_certificate, pay = p.payments;
    return h('button', { class: 'row', type: 'button', onclick: () => openPensioner(p.name) },
      h('div', { class: 'who' }, h('div', { class: 'avatar', 'aria-hidden': 'true' }, initials(p.name)),
        h('div', { style: 'min-width:0' }, h('div', { class: 'name' }, p.name), h('div', { class: 'meta' }, p.bank + ' · age ' + p.age))),
      h('div', {}, chip(LC, lc.status), lc.status === 'done' && lc.verified_until ? h('span', { class: 'cell-sub' }, 'until ' + shortDate(lc.verified_until)) : null),
      h('div', { class: 'col-pay' }, chip(PAY, pay.status), pay.status === 'problem' ? h('span', { class: 'cell-sub' }, inr(pay.amount_short) + ' · ' + pay.problem_months + ' month' + (pay.problem_months > 1 ? 's' : '')) : null),
      h('span', { class: 'chev', 'aria-hidden': 'true' }, '›'));
  }));
}

/* ===== Letters ===== */
function renderLetters() {
  const ls = state.data.letters;
  const L = [['draft', 'Waiting'], ['approved', 'Approved'], ['sent', 'Sent'], ['resolved', 'Resolved'], ['all', 'All']];
  $('#lfilters').replaceChildren(...L.map(([k, label]) =>
    h('button', { type: 'button', 'aria-pressed': String(state.lfilter === k), onclick: () => { state.lfilter = k; renderLetters(); } }, label, h('span', { class: 'count' }, k === 'all' ? ls.length : ls.filter(g => g.status === k).length))));
  const items = ls.filter(g => state.lfilter === 'all' || g.status === state.lfilter).sort((a, b) => (b.amount_short || 0) - (a.amount_short || 0));
  const box = $('#letters');
  if (!items.length) {
    const t = state.data.totals;
    box.replaceChildren(h('div', { class: 'empty' }, ls.length ? 'Nothing here.' : t.payment_problem_pensioners
      ? 'Money is missing for ' + t.payment_problem_pensioners + ' pensioner(s). Click “Draft letters now” and Claude will write the letters.'
      : 'No letters needed yet. Upload bank statements to check payments.'));
    return;
  }
  box.replaceChildren(...items.map(g => h('button', { class: 'letter', type: 'button', onclick: () => openLetter(g.id) },
    h('span', { class: 'name' }, g.name), h('span', { class: 'amt' }, inr(g.amount_short)),
    h('span', { class: 'desc' }, g.bank + ' · ' + issueText(g.issue_type)), h('span', {}, chip(LETTER, g.status)))));
}
async function draftNow() {
  const btn = $('#draft-now'); btn.disabled = true; btn.replaceChildren(h('span', { class: 'spin' }), ' Claude is writing…');
  try { const res = await api('/letters/draft-now', { method: 'POST' }); toast(res.message); state.lfilter = 'draft'; await load(true); }
  catch (e) { toast('Not drafted: ' + e.message); btn.disabled = false; btn.textContent = '✍ Draft letters now'; }
}

/* ===== Pensioner drawer ===== */
function openPensioner(name, refreshOnly) {
  const p = state.data.pensioners.find(x => x.name === name); if (!p) { closeAll(); return; }
  state.openName = name;
  $('#d-name').textContent = p.name;
  $('#d-meta').textContent = 'Age ' + p.age + ' · ' + p.bank + (p.bank_account_last4 ? ' a/c ••' + p.bank_account_last4 : '') + ' · PPO ending ' + p.ppo_last4 + ' · ' + p.language;
  const lc = p.life_certificate, pay = p.payments, s = state.data.settings;
  const lcLine = { urgent: 'Not submitted. Only ' + lc.days_left + ' days left.', open: 'Not submitted yet. ' + lc.days_left + ' days left.',
    missed: 'Deadline missed. Pension may pause from December until it is submitted.', not_open_yet: 'Submission window opens on ' + lc.window_opens + '.' }[lc.status] || '';
  const maxExp = Math.max(1, ...pay.months.map(m => m.expected));
  const letter = p.letter ? state.data.letters.find(g => g.id === p.letter.id) : null;
  const check = state.checks[p.name];
  $('#d-body').replaceChildren(
    h('div', { class: 'section', style: 'display:flex;gap:8px;flex-wrap:wrap' },
      h('button', { class: 'btn small', type: 'button', onclick: () => openForm(p) }, 'Edit details'),
      h('button', { class: 'btn small', type: 'button', onclick: () => openStatement(p) }, 'Upload bank statement'),
      h('button', { class: 'btn small bad', type: 'button', onclick: () => deletePensioner(p) }, 'Delete')),
    h('div', { class: 'section' }, h('h4', {}, 'Life certificate'),
      lc.status === 'done'
        ? h('div', {}, h('span', { class: 'verified' }, 'Verified until ' + longDate(lc.verified_until) + ' ✓'),
            h('p', { class: 'cell-sub', style: 'margin-top:8px' }, 'Jeevan Pramaan ID ' + (lc.pramaan_id || '–') + (lc.submitted_on ? ' · submitted ' + longDate(lc.submitted_on) : '') + '. Stored once: no reminders until the next cycle.'))
        : h('div', {}, h('div', { style: 'display:flex;gap:10px;align-items:center;flex-wrap:wrap' }, chip(LC, lc.status), h('span', {}, lcLine)),
            h('form', { class: 'inline-form', onsubmit: e => { e.preventDefault(); recordCertificate(p.id, e.target); } },
              h('input', { class: 'input', name: 'pid', placeholder: 'Jeevan Pramaan ID from the SMS', 'aria-label': 'Jeevan Pramaan ID', autocomplete: 'off', maxlength: '30' }),
              h('button', { class: 'btn primary', type: 'submit' }, 'Record certificate')))),
    h('div', { class: 'section' }, h('h4', {}, 'Pension payments'),
      h('div', { class: 'facts', style: 'margin-bottom:12px' },
        h('div', { class: 'fact' }, h('div', { class: 'k' }, 'Status'), h('div', { class: 'v' }, chip(PAY, pay.status))),
        h('div', { class: 'fact' }, h('div', { class: 'k' }, 'Money pending'), h('div', { class: 'v' }, inr(pay.amount_short)))),
      pay.months.length ? h('div', { class: 'months' }, pay.months.map(m => h('div', { class: 'month' },
        h('span', { class: 'm' }, shortMonth(m.month)),
        h('div', { class: 'mbar', title: 'Received ' + inr(m.received) + ' of ' + inr(m.expected) }, h('span', { class: m.status === 'ok' ? '' : m.status, style: `width:${Math.min(100, 100 * m.received / maxExp)}%` })),
        h('span', { class: 'amt' }, inr(m.received), m.status !== 'ok' ? h('small', {}, m.status === 'missing' ? 'not paid · ' + inr(m.expected) + ' due' : inr(m.difference) + ' short') : null))))
        : h('div', { class: 'empty', style: 'padding:14px' }, 'No bank statement yet. Use “Upload bank statement” above.'),
      h('p', { class: 'cell-sub', style: 'margin-top:10px' }, 'Expected = basic ' + inr(p.basic_pension) + ' + DA (' + s.da_old + '% before ' + shortMonth(s.da_new_from) + ', ' + s.da_new + '% from then) − commuted ' + inr(p.commuted_amount) + '. Change DA rates in Settings.')),
    h('div', { class: 'section' }, h('h4', {}, 'Letter to the bank'),
      letter ? h('div', { style: 'display:flex;gap:10px;align-items:center;flex-wrap:wrap' }, chip(LETTER, letter.status), h('button', { class: 'btn small', type: 'button', onclick: () => openLetter(letter.id) }, 'Open letter'))
        : h('span', { class: 'cell-sub' }, pay.status === 'problem' ? 'No letter yet. Use “Draft letters now” on the dashboard.' : 'Not needed.')),
    h('div', { class: 'section' }, h('h4', {}, 'Check again now'),
      h('p', { class: 'cell-sub', style: 'margin:0 0 10px' }, 'Runs the full check right now. If money is missing, Claude writes a fresh letter (one AI request).'),
      h('button', { class: 'btn', type: 'button', id: 'recheck', onclick: () => recheck(p.name) }, 'Run check'),
      check ? h('div', { class: 'check-result', style: 'margin-top:12px' },
        h('strong', {}, 'Checked ' + new Date(check.checked_at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })),
        h('ul', {}, ...(check.issues.length ? check.issues : ['No problems found.']).map(i => h('li', {}, i))),
        check.letter ? h('details', { style: 'margin-top:8px' }, h('summary', {}, 'Letter Claude just wrote'), h('div', { class: 'paper', style: 'margin:10px 0 0' }, check.letter)) : null) : null),
    h('div', { class: 'section' }, h('h4', {}, 'Family status check'),
      p.online_check ? h('span', { class: 'chip ok' }, 'On: the family can check with PPO + date of birth')
        : h('span', { class: 'cell-sub' }, 'Off. Use “Edit details” and add the date of birth (with the full PPO number) to turn it on.')),
    p.consent_given_at ? h('p', { class: 'cell-sub' }, 'Consent recorded ' + longDate(p.consent_given_at) + (p.consent_by ? ' by ' + p.consent_by : '') + '.') : null);
  if (!refreshOnly) { $('#drawer').classList.add('open'); $('#drawer').setAttribute('aria-hidden', 'false'); $('#scrim').classList.add('open'); }
}
async function recheck(name) {
  const btn = $('#recheck'); btn.disabled = true; btn.replaceChildren(h('span', { class: 'spin' }), ' Checking…');
  try { state.checks[name] = await api('/pensioners/check', { method: 'POST', body: { name } }); toast('Check finished for ' + name); }
  catch (e) { toast('Check failed: ' + e.message); }
  if (state.openName === name) openPensioner(name, true);
}
async function recordCertificate(id, form) {
  const pid = form.pid.value.trim(), btn = form.querySelector('button');
  if (!/^[A-Za-z0-9][A-Za-z0-9-]{5,29}$/.test(pid)) { toast('The Jeevan Pramaan ID should be 6 to 30 letters or numbers.'); form.pid.focus(); return; }
  btn.disabled = true; btn.replaceChildren(h('span', { class: 'spin' }), ' Saving…');
  try { const res = await api('/pensioners/record-certificate', { method: 'POST', body: { id, pramaan_id: pid } }); toast(res.message || 'Recorded'); await load(true); }
  catch (e) { toast('Not recorded: ' + e.message); btn.disabled = false; btn.textContent = 'Record certificate'; }
}

/* ===== Add / edit / delete ===== */
let editing = null;
function openModal(sel) { $(sel).classList.add('open'); $(sel).setAttribute('aria-hidden', 'false'); $('#scrim').classList.add('open'); }
function openForm(p) {
  editing = p;
  const f = $('#pf'); f.reset(); clearFieldErrors(f); $('#pf-err').hidden = true;
  $('#f-language').replaceChildren(h('option', { value: '' }, 'Choose…'), ...LANGS.map(l => h('option', { value: l }, l)));
  $('#pf-title').textContent = p ? 'Edit ' + p.name : 'Add pensioner';
  $('#pf-sub').textContent = p ? 'Changes apply everywhere, including payments and letters.' : 'All fields with * are required.';
  $('#ppo-star').hidden = !!p;
  $('#ppo-hint').textContent = p ? 'Stored: ending ' + (p.ppo_last4 || '–') + '. Leave empty to keep it.' : 'Only the last 4 digits are stored.';
  $('#acct-hint').textContent = p ? 'Stored: ' + (p.bank_account_last4 ? 'ending ' + p.bank_account_last4 : 'none') + '. Leave empty to keep it.' : 'Only the last 4 digits are stored.';
  $('#consent-row').hidden = !!p;
  $('#f-dob').max = new Date().toISOString().slice(0, 10);
  $('#dob-hint').textContent = p
    ? (p.online_check ? 'Online status check is on. To change it, type the date of birth and the full PPO number again.' : 'Type it with the full PPO number to let the family check the status online. Not stored.')
    : 'Lets the family check the status online with PPO + date of birth. Not stored.';
  if (p) { f.name.value = p.name; f.age.value = p.age; f.language.value = p.language; f.bank.value = p.bank; f.basic_pension.value = p.basic_pension || ''; f.commuted_amount.value = p.commuted_amount || 0; f.family_email.value = p.family_email || ''; }
  openModal('#pform'); setTimeout(() => f.name.focus(), 60);
}
function formErrors(f) {
  const e = {}, name = f.name.value.trim(), age = Number(f.age.value), basic = Number(f.basic_pension.value), comm = Number(f.commuted_amount.value || 0);
  if (name.length < 2 || /[0-9_@#$%^&*()+=<>{}[\]\\/|~`!?;:"]/.test(name)) e.name = 'Please enter the full name using letters only.';
  const dob = f.date_of_birth.value;
  if (dob) {
    const b = new Date(dob + 'T00:00:00'), now = new Date();
    const years = now.getFullYear() - b.getFullYear() - ((now.getMonth() < b.getMonth() || (now.getMonth() === b.getMonth() && now.getDate() < b.getDate())) ? 1 : 0);
    if (isNaN(b) || b >= now || years < 40 || years > 120) e.date_of_birth = 'The date of birth should give an age between 40 and 120.';
    else f.age.value = years;
    if (editing && !f.ppo_number.value.trim()) e.ppo_number = 'Type the full PPO number again, together with the date of birth.';
  } else if (editing && editing.online_check && f.ppo_number.value.trim()) e.date_of_birth = 'Type the date of birth again, so the family can keep checking online.';
  if (!f.age.value || Number(f.age.value) < 40 || Number(f.age.value) > 120) e.age = 'Age must be between 40 and 120.';
  if (!f.language.value) e.language = 'Please choose a language.';
  if (f.bank.value.trim().length < 2) e.bank = 'Please enter the bank name.';
  const ppo = f.ppo_number.value.replace(/[\s-]/g, ''); if ((!editing || ppo) && !/^\d{6,20}$/.test(ppo)) e.ppo_number = 'Enter 6 to 20 digits.';
  const acct = f.bank_account_number.value.replace(/[\s-]/g, ''); if (acct && !/^\d{6,20}$/.test(acct)) e.bank_account_number = 'Enter 6 to 20 digits, or leave empty.';
  if (!f.basic_pension.value || basic < 500 || basic > 1000000) e.basic_pension = 'Enter the monthly basic pension (₹500 to ₹10,00,000).';
  if (comm < 0 || (basic && comm >= basic)) e.commuted_amount = 'Must be 0 or more, and less than the basic pension.';
  const email = f.family_email.value.trim(); if (email && !/^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$/.test(email)) e.family_email = 'Please enter a valid email, or leave it empty.';
  if (!editing && !f.consent.checked) e.consent = 'Consent is required before adding a pensioner.';
  return e;
}
$('#pf').addEventListener('submit', async ev => {
  ev.preventDefault();
  const f = ev.target, err = $('#pf-err'); err.hidden = true;
  const local = formErrors(f); if (Object.keys(local).length) { showFieldErrors(f, local); return; }
  clearFieldErrors(f);
  const body = { name: f.name.value.trim(), age: Number(f.age.value), language: f.language.value, bank: f.bank.value.trim(), ppo_number: f.ppo_number.value.trim(),
    bank_account_number: f.bank_account_number.value.trim(), basic_pension: Number(f.basic_pension.value), commuted_amount: Number(f.commuted_amount.value || 0),
    family_email: f.family_email.value.trim(), date_of_birth: f.date_of_birth.value, consent: editing ? true : f.consent.checked };
  const btn = $('#pf-save'); btn.disabled = true; btn.replaceChildren(h('span', { class: 'spin' }), ' Saving…');
  try {
    const res = editing ? await api('/pensioners/' + editing.id, { method: 'PUT', body }) : await api('/pensioners', { method: 'POST', body });
    toast(res.message || 'Saved');
    const reopen = editing ? body.name : null;
    closeAll(); await load(true); if (reopen) openPensioner(reopen);
  } catch (e) { if (!(e.data && showFieldErrors(f, e.data.fields))) { err.textContent = e.message; err.hidden = false; } }
  finally { btn.disabled = false; btn.textContent = 'Save'; }
});
async function deletePensioner(p) {
  const typed = prompt('This permanently deletes ' + p.name + ' and ALL their payments and letters. It cannot be undone.\n\nType the name to confirm:');
  if (typed === null) return;
  if (typed.trim().toLowerCase() !== p.name.toLowerCase()) { toast('The name did not match. Nothing was deleted.'); return; }
  try { const res = await api('/pensioners/' + p.id, { method: 'DELETE' }); toast(res.message); closeAll(); await load(true); }
  catch (e) { toast('Not deleted: ' + e.message); }
}
function openStatement(p) {
  $('#st-sub').textContent = 'For ' + p.name + ' · CSV or PDF from ' + p.bank;
  mountUploads($('#st-body'), { statementsOnly: true, pensionerId: p.id, onChange: async () => { await load(true); } });
  openModal('#stmt');
}

/* ===== Letter modal ===== */
function openLetter(id) {
  const g = state.data.letters.find(x => x.id === id); if (!g) return;
  $('#m-title').textContent = 'Letter to ' + g.bank;
  $('#m-meta').textContent = 'For ' + g.name + ' · ' + inr(g.amount_short) + ' pending · letter #' + g.id;
  $('#m-paper').replaceChildren(h('div', { class: 'print-skip', style: 'font:14px/1.5 var(--font);margin:-4px 0 18px;padding-bottom:16px;border-bottom:1px solid var(--border)' },
    tracker(g.status, g.timeline, TRACK_LABELS, shortDate)), g.letter);
  $('#m-note').textContent = g.letter_source === 'ai' ? 'Drafted by Claude from the bank statements. Please read before approving.' : 'Drafted from the standard template.';
  const printBtn = h('button', { class: 'btn', type: 'button', onclick: () => { const pp = $('#m-paper'); pp.classList.add('print-me'); window.print(); setTimeout(() => pp.classList.remove('print-me'), 500); } }, 'Print');
  const copyBtn = h('button', { class: 'btn', type: 'button', onclick: async () => { try { await navigator.clipboard.writeText(g.letter); toast('Letter copied'); } catch (e) { toast('Copy not allowed here.'); } } }, 'Copy');
  const next = {
    draft: [h('button', { class: 'btn bad', type: 'button', onclick: () => decide(g, 'reject') }, 'Reject'), h('button', { class: 'btn ok', type: 'button', onclick: () => decide(g, 'approve') }, 'Approve letter')],
    approved: [h('button', { class: 'btn primary', type: 'button', onclick: () => decide(g, 'mark_sent') }, 'Mark as sent to bank')],
    sent: [h('button', { class: 'btn ok', type: 'button', onclick: () => decide(g, 'mark_resolved') }, 'Mark resolved')]
  }[g.status] || [];
  $('#m-actions').replaceChildren(...(g.status === 'draft' ? [] : [chip(LETTER, g.status)]), copyBtn, printBtn, ...next);
  openModal('#modal');
}
async function decide(g, decision) {
  const ask = { approve: 'Approve the letter for ' + g.name + '?', reject: 'Reject the letter for ' + g.name + '?',
    mark_sent: 'Mark the letter for ' + g.name + ' as sent to ' + g.bank + '?', mark_resolved: 'Mark the complaint for ' + g.name + ' as resolved?' }[decision];
  if (!confirm(ask + ' This cannot be undone.')) return;
  const btns = [...document.querySelectorAll('#m-actions button')]; btns.forEach(b => b.disabled = true);
  try { const body = await api('/letters/' + g.id + '/decision', { method: 'POST', body: { decision } }); toast(body.message || 'Saved'); closeAll(); await load(true); }
  catch (e) { toast('Not saved: ' + e.message); btns.forEach(b => b.disabled = false); }
}

/* ===== Closing ===== */
const MODALS = ['#modal', '#pform', '#stmt'];
function closeAll() {
  $('#drawer').classList.remove('open'); $('#drawer').setAttribute('aria-hidden', 'true');
  MODALS.forEach(s => { $(s).classList.remove('open'); $(s).setAttribute('aria-hidden', 'true'); });
  $('#scrim').classList.remove('open'); state.openName = null;
}
function closeTop() {
  const open = MODALS.find(s => $(s).classList.contains('open'));
  if (open) { $(open).classList.remove('open'); $(open).setAttribute('aria-hidden', 'true'); if (!$('#drawer').classList.contains('open')) $('#scrim').classList.remove('open'); }
  else closeAll();
}
document.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeTop(); });
$('#scrim').addEventListener('click', closeTop);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeTop(); });

/* ===== Start ===== */
$('#refresh').addEventListener('click', () => load());
$('#retry').addEventListener('click', () => load());
$('#add-p').addEventListener('click', () => state.data && openForm(null));
mountShell('dashboard').then(me => { state.me = me; return load(true); })
  .catch(e => { $('#error-text').textContent = e.message; $('#error').classList.add('show'); });
