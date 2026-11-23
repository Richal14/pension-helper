/* Pension Helper – Settings: account, DA rates, password, activity. */

const when = iso => iso ? new Date(String(iso).replace(/([+-]\d{2})(\d{2})$/, '$1:$2')).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '–';
let S = null;

async function loadSettings() {
  try {
    S = await api('/settings');
    const d = S.details || {};
    const facts = S.role === 'office'
      ? [['Office', S.name], ['District', d.district], ['Contact person', d.contact_name], ['Phone', d.phone || '–'], ['Email', S.email]]
      : [['Account', S.email], ['Your name', d.your_name], ['Relation', d.relation], ['Pensioner', d.pensioner && d.pensioner.name]];
    $('#account').replaceChildren(
      h('div', { class: 'facts' }, facts.map(([k, v]) => h('div', { class: 'fact' }, h('div', { class: 'k' }, k), h('div', { class: 'v' }, v || '–')))),
      h('p', { class: 'cell-sub', style: 'margin-top:12px' }, S.consent_at ? 'Consent to store pensioner data given on ' + when(S.consent_at) + '.' : 'Consent not given yet.'));
    const f = $('#da'); f.da_old.value = S.da_old; f.da_new.value = S.da_new; f.da_new_from.value = S.da_new_from; daExample();
    $('#activity').replaceChildren(
      h('thead', {}, h('tr', {}, h('th', {}, 'When'), h('th', {}, 'Who'), h('th', {}, 'What'), h('th', {}, 'Details'))),
      h('tbody', {}, S.activity.map(a => h('tr', {}, h('td', {}, when(a.at)), h('td', {}, a.email || '–'), h('td', {}, a.action.replace(/_/g, ' ')), h('td', {}, a.detail || '')))));
  } catch (e) { $('#error-text').textContent = e.message; $('#error').classList.add('show'); }
}

function daExample() {
  const f = $('#da'), o = Number(f.da_old.value), n = Number(f.da_new.value);
  $('#da-example').textContent = 'Example: basic pension ₹30,000 → expected ' + inr(30000 * (1 + o / 100)) + ' before ' +
    (f.da_new_from.value ? shortMonth(f.da_new_from.value) : '…') + ', and ' + inr(30000 * (1 + n / 100)) + ' from then (before any commuted deduction).';
}
['input', 'change'].forEach(t => $('#da').addEventListener(t, daExample));
$('#da').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target, errs = {}, o = Number(f.da_old.value), n = Number(f.da_new.value);
  if (f.da_old.value === '' || o < 0 || o > 300) errs.da_old = 'Enter a rate between 0 and 300.';
  if (f.da_new.value === '' || n < 0 || n > 300) errs.da_new = 'Enter a rate between 0 and 300.';
  if (!/^20\d{2}-(0[1-9]|1[0-2])$/.test(f.da_new_from.value)) errs.da_new_from = 'Choose a month.';
  if (Object.keys(errs).length) { showFieldErrors(f, errs); return; }
  clearFieldErrors(f);
  const btn = $('#da-save'); btn.disabled = true;
  try { await api('/settings', { method: 'PUT', body: { da_old: o, da_new: n, da_new_from: f.da_new_from.value } }); toast('DA rates saved. Every check now uses them.'); await loadSettings(); }
  catch (ex) { if (!(ex.data && showFieldErrors(f, ex.data.fields))) toast('Not saved: ' + ex.message); }
  finally { btn.disabled = false; }
});
$('#pw').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target, errs = {}, err = $('#pw-err'); err.hidden = true;
  if (!f.current_password.value) errs.current_password = 'Please enter your current password.';
  if (f.new_password.value.length < 10) errs.new_password = 'At least 10 characters.';
  if (f.again.value !== f.new_password.value) errs.again = 'The two new passwords are different.';
  if (Object.keys(errs).length) { showFieldErrors(f, errs); return; }
  clearFieldErrors(f);
  try { await api('/me/password', { method: 'POST', body: { current_password: f.current_password.value, new_password: f.new_password.value } }); f.reset(); toast('Password changed. Other devices were logged out.'); await loadSettings(); }
  catch (ex) { err.textContent = ex.message; err.hidden = false; }
});

mountShell('settings').then(loadSettings).catch(e => { $('#error-text').textContent = e.message; $('#error').classList.add('show'); });
