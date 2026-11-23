/* Pension Helper – upload center (used in onboarding step 3 and on the Uploads page).
   Office: pensioner list (CSV) + bank statements. Family: bank statements. */

const FORMAT = [
  ['name', 'Full name', true], ['age', 'Age in years (40–120). Can be left empty if the date of birth is given', true],
  ['date_of_birth', 'DD/MM/YYYY. Lets the family check the status online with PPO + date of birth (never stored)', false],
  ['bank', 'Bank where the pension is paid', true],
  ['language', 'Hindi, English, Bengali, Marathi, Tamil, Telugu, Kannada, Gujarati, Malayalam, Punjabi, Odia, Urdu or Assamese', true],
  ['ppo_number', 'PPO number (only the last 4 digits are stored)', true],
  ['bank_account_number', 'Account number (only the last 4 digits are stored; used to match statements)', false],
  ['basic_pension', 'Basic pension per month in ₹', true], ['commuted_amount', 'Monthly commuted deduction in ₹ (0 if none)', false],
  ['family_email', 'Email for life-certificate reminders', false],
  ['jeevan_pramaan_id', 'If the life certificate is already submitted: its ID', false], ['certificate_date', '…and the date, DD/MM/YYYY', false]
];

function dropZone(id, title, sub, multiple, accept, onFiles) {
  const input = h('input', { type: 'file', id, accept, multiple: multiple || null });
  const zone = h('label', { class: 'drop', for: id },
    h('div', { class: 'dicon' }, icon('file')), h('strong', {}, title), h('span', { class: 'cell-sub', style: 'margin:0' }, sub), input);
  ['dragover', 'dragenter'].forEach(t => zone.addEventListener(t, e => { e.preventDefault(); zone.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach(t => zone.addEventListener(t, () => zone.classList.remove('drag')));
  zone.addEventListener('drop', e => { e.preventDefault(); if (e.dataTransfer.files.length) onFiles([...e.dataTransfer.files]); });
  input.addEventListener('change', () => { if (input.files.length) onFiles([...input.files]); input.value = ''; });
  return zone;
}

function mountUploads(root, { role, onChange, statementsOnly, pensionerId } = {}) {
  if (statementsOnly) role = 'statements';
  const changed = () => onChange && onChange();

  /* ----- Pensioner list (office) ----- */
  const listOut = h('div');
  const listCard = role === 'office' ? h('section', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', {}, '1. Pensioner list (CSV)'),
      h('a', { class: 'btn small', href: '/api/templates/pensioner-list.csv', download: 'pensioner_list_template.csv' }, 'Download CSV template')),
    h('div', { class: 'card-body' },
      dropZone('list-file', 'Choose your pensioner list (.csv)', 'One row per pensioner. Every row is checked before anything is saved.', false, '.csv,text/csv', files => uploadList(files[0])),
      listOut,
      h('details', { style: 'margin-top:12px' }, h('summary', { style: 'cursor:pointer;font-weight:600;font-size:14px' }, 'Which columns does the file need?'),
        h('table', { class: 'format-table' }, h('tbody', {}, FORMAT.map(([c, d, req]) =>
          h('tr', {}, h('td', {}, h('code', {}, c)), h('td', {}, d), h('td', {}, req ? h('span', { class: 'chip bad' }, 'required') : h('span', { class: 'chip muted' }, 'optional'))))))))) : null;

  async function uploadList(file) {
    listOut.replaceChildren(h('p', { class: 'cell-sub' }, h('span', { class: 'spin' }), ' Checking ' + file.name + '…'));
    const fd = new FormData(); fd.append('file', file);
    try {
      const res = await api('/upload/pensioner-list', { method: 'POST', form: fd });
      listOut.replaceChildren(h('div', { class: 'form-ok', style: 'margin:12px 0 0' }, '✓ ' + res.message + ' You can now upload their bank statements below.'));
      toast(res.message); changed();
    } catch (e) {
      const errors = (e.data && e.data.errors) || [];
      listOut.replaceChildren(h('div', { class: 'form-error', style: 'margin:12px 0 0' }, h('strong', {}, file.name + ': '), e.message),
        errors.length ? h('ul', { class: 'errlist' }, errors.map(x => h('li', {}, h('strong', {}, 'Row ' + x.row + ' · ' + x.field + ': '), x.message))) : null);
    }
  }

  /* ----- Bank statements ----- */
  const stOut = h('div', { style: 'display:grid;gap:12px;margin-top:12px' });
  const stCard = h('section', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', {}, (role === 'office' ? '2. ' : '') + 'Bank statements (CSV or PDF)'),
      h('span', { class: 'hint' }, 'Up to 20 files at once, 5 MB each')),
    h('div', { class: 'card-body' },
      dropZone('st-files', 'Choose bank statements', role === 'office'
        ? 'Each statement is matched to a pensioner by its account number (last 4 digits) or PPO number. The files are not saved.'
        : 'We read only the pension credits. The files are not saved.', true, '.csv,.pdf,text/csv,application/pdf', files => uploadStatements(files)),
      stOut));

  async function uploadStatements(files) {
    if (files.length > 20) { toast('Please choose at most 20 files.'); return; }
    stOut.replaceChildren(h('p', { class: 'cell-sub' }, h('span', { class: 'spin' }), ' Reading ' + files.length + ' file(s)…'));
    const fd = new FormData(); files.forEach(f => fd.append('files', f));
    if (pensionerId) fd.append('pensioner_id', String(pensionerId));
    let data;
    try { data = await api('/upload/statements', { method: 'POST', form: fd }); }
    catch (e) { stOut.replaceChildren(h('div', { class: 'form-error', style: 'margin:0' }, e.message)); return; }
    const items = [];
    const blocks = data.results.map(r => {
      if (!r.ok) return h('div', { class: 'file-result failed' },
        h('div', { class: 'fr-head' }, h('span', { class: 'fname' }, r.filename), h('span', { class: 'chip bad' }, 'Not read')),
        h('div', { style: 'font-size:13.5px;color:var(--bad)' }, r.error));
      const sel = h('select', { class: 'input', style: 'max-width:320px;padding:8px 10px', 'aria-label': 'Pensioner for ' + r.filename },
        h('option', { value: '' }, 'Choose the pensioner…'),
        data.pensioners.map(p => h('option', { value: p.id, selected: r.match && r.match.id === p.id ? true : null }, p.name + ' · PPO ending ' + p.ppo_last4)));
      const pills = r.months.map(m => h('label', { class: 'month-pill' + (m.amount_received ? '' : ' zero') },
        h('input', { type: 'checkbox', checked: true, value: m.month }), shortMonth(m.month) + ' · ',
        m.amount_received ? inr(m.amount_received) : 'no pension'));
      items.push({ token: r.token, sel, pills });
      return h('div', { class: 'file-result' },
        h('div', { class: 'fr-head' }, h('span', { class: 'fname' }, r.filename),
          r.match ? h('span', { class: 'chip ok' }, 'Matched by ' + r.match.how) : h('span', { class: 'chip warn' }, 'Please choose the pensioner')),
        h('div', { style: 'display:flex;gap:10px;flex-wrap:wrap;align-items:center' }, h('span', { class: 'label' }, 'Pensioner'), sel),
        h('div', { class: 'cell-sub', style: 'margin:0' }, r.transactions_read + ' transactions · ' + r.period.from + ' to ' + r.period.to + ' · untick any month you do not want to save'),
        h('div', { class: 'month-pills' }, pills));
    });
    const msg = h('div');
    const save = items.length ? h('button', { class: 'btn primary', type: 'button', onclick: async () => {
      const chosen = items.map(it => ({ token: it.token, pensioner_id: Number(it.sel.value), months: it.pills.map(p => p.querySelector('input')).filter(i => i.checked).map(i => i.value) }));
      const missing = chosen.findIndex(c => !c.pensioner_id);
      if (missing >= 0) { msg.replaceChildren(h('div', { class: 'form-error', style: 'margin:0' }, 'Please choose the pensioner for every statement.')); items[missing].sel.focus(); return; }
      const toSave = chosen.filter(c => c.months.length);
      if (!toSave.length) { msg.replaceChildren(h('div', { class: 'form-error', style: 'margin:0' }, 'Please tick at least one month.')); return; }
      save.disabled = true; save.replaceChildren(h('span', { class: 'spin' }), ' Saving…');
      try {
        const res = await api('/upload/statements/confirm', { method: 'POST', body: { items: toSave } });
        stOut.replaceChildren(h('div', { class: 'form-ok', style: 'margin:0' }, '✓ ' + res.message + ' ' + res.saved.map(s => s.name + ' (' + s.months + ' months)').join(', ')));
        toast(res.message); changed();
      } catch (e) {
        msg.replaceChildren(h('div', { class: 'form-error', style: 'margin:0' }, e.message));
        save.disabled = false; save.textContent = 'Save these payments';
      }
    } }, 'Save these payments') : null;
    stOut.replaceChildren(...blocks, msg, ...(save ? [h('div', {}, save)] : []));
  }

  root.replaceChildren(h('div', { class: 'up-grid' }, listCard, stCard));
}
