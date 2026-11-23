/* Pension Helper – 3-step onboarding: details -> consent -> upload documents. */

const OB = { me: null, state: null, step: 1 };
const RELATIONS = ['Son', 'Daughter', 'Spouse', 'Self', 'Other relative', 'Caregiver'];

function setProgress(step) {
  OB.step = step;
  document.querySelectorAll('.pstep').forEach(el => {
    const n = Number(el.dataset.step);
    el.classList.toggle('active', n === step);
    el.classList.toggle('done', n < step);
    el.querySelector('.n').textContent = n < step ? '✓' : String(n);
  });
  $('#pfill').style.width = (step === 1 ? 12 : step === 2 ? 50 : 88) + '%';
  $('#pbar').setAttribute('aria-valuenow', String(step));
}

function field(label, input, hint, full) {
  return h('div', { class: 'field' + (full ? ' full' : '') }, h('label', { for: input.id }, label), input, hint ? h('span', { class: 'hint' }, hint) : null);
}
const inp = (id, attrs = {}) => h('input', { class: 'input', id, name: id, autocomplete: 'off', ...attrs });

/* ===== Step 1: details ===== */
function step1() {
  setProgress(1);
  const d = OB.state.details || {};
  const office = OB.me.role === 'office';
  const err = h('div', { class: 'form-error', role: 'alert', hidden: true });
  let fields;
  if (office) {
    fields = [
      field('Office name *', inp('office_name', { maxlength: 120, value: d.office_name || '', placeholder: 'e.g. District Treasury & Pension Office, Ranchi' }), null, true),
      field('District / city *', inp('district', { maxlength: 80, value: d.district || '' })),
      field('Contact person *', inp('contact_name', { maxlength: 80, value: d.contact_name || OB.me.display_name || '' })),
      field('Office phone', inp('phone', { inputmode: 'tel', maxlength: 15, value: d.phone || '' }), '10 digits, optional.')
    ];
  } else {
    const p = d.pensioner || {};
    const lang = h('select', { class: 'input', id: 'language', name: 'language' }, h('option', { value: '' }, 'Choose…'),
      OB.state.languages.map(l => h('option', { value: l, selected: p.language === l ? true : null }, l)));
    const rel = h('select', { class: 'input', id: 'relation', name: 'relation' }, h('option', { value: '' }, 'Choose…'),
      RELATIONS.map(r => h('option', { value: r, selected: d.relation === r ? true : null }, r)));
    fields = [
      field('Your name *', inp('your_name', { maxlength: 80, value: d.your_name || OB.me.display_name || '' })),
      field('You are the pensioner\'s… *', rel),
      h('h3', { class: 'full', style: 'margin:8px 0 10px;font-size:15px' }, 'About the pensioner'),
      field('Pensioner\'s full name *', inp('name', { maxlength: 80, value: p.name || '' }), null, true),
      field('Age *', inp('age', { type: 'number', min: 40, max: 120, value: p.age || '' })),
      field('Language for messages *', lang),
      field('Bank where the pension is paid *', inp('bank', { maxlength: 80, value: p.bank || '', list: 'banks' }), null, true),
      field('PPO number *', inp('ppo_number', { inputmode: 'numeric', maxlength: 30 }), p.ppo_last4 ? 'Saved: ending ' + p.ppo_last4 + '. Type it again to continue.' : 'Printed on the Pension Payment Order. Only the last 4 digits are stored.'),
      field('Bank account number', inp('bank_account_number', { inputmode: 'numeric', maxlength: 30 }), 'Optional. Only the last 4 digits are stored.'),
      field('Basic pension (₹ per month) *', inp('basic_pension', { type: 'number', min: 500, max: 1000000, value: p.basic_pension || '' }), 'Written on the Pension Payment Order.'),
      field('Commuted amount (₹ per month)', inp('commuted_amount', { type: 'number', min: 0, value: p.commuted_amount ?? 0 }), '0 if nothing is deducted.')
    ];
  }
  const form = h('form', { novalidate: true },
    err, h('div', { class: 'form-grid' }, fields),
    h('datalist', { id: 'banks' }, ['State Bank of India', 'Punjab National Bank', 'Bank of Baroda', 'Canara Bank', 'Union Bank of India', 'Bank of Maharashtra', 'Indian Bank', 'Central Bank of India', 'UCO Bank', 'Indian Overseas Bank', 'India Post Payments Bank'].map(b => h('option', {}, b))),
    h('div', { class: 'onb-actions' }, h('span'), h('button', { class: 'btn primary large', type: 'submit' }, 'Continue')));
  form.addEventListener('submit', async e => {
    e.preventDefault();
    err.hidden = true;
    const body = Object.fromEntries(new FormData(form).entries());
    const errs = {};
    if (office) {
      if ((body.office_name || '').trim().length < 3) errs.office_name = 'Please enter the office name.';
      if ((body.district || '').trim().length < 2) errs.district = 'Please enter the district or city.';
      if ((body.contact_name || '').trim().length < 2) errs.contact_name = 'Please enter the contact person.';
      if (body.phone && !/^\+?[\d\s-]{10,15}$/.test(body.phone)) errs.phone = 'Please enter a 10-digit phone number, or leave it empty.';
    } else {
      if ((body.your_name || '').trim().length < 2) errs.your_name = 'Please enter your name.';
      if (!body.relation) errs.relation = 'Please choose one.';
      if ((body.name || '').trim().length < 2 || /\d/.test(body.name)) errs.name = 'Please enter the full name using letters only.';
      if (!body.age || body.age < 40 || body.age > 120) errs.age = 'Age must be between 40 and 120.';
      if (!body.language) errs.language = 'Please choose a language.';
      if ((body.bank || '').trim().length < 2) errs.bank = 'Please enter the bank name.';
      if (!/^\d{6,20}$/.test((body.ppo_number || '').replace(/[\s-]/g, ''))) errs.ppo_number = 'Enter the PPO number (6 to 20 digits).';
      if (body.bank_account_number && !/^\d{6,20}$/.test(body.bank_account_number.replace(/[\s-]/g, ''))) errs.bank_account_number = 'Enter 6 to 20 digits, or leave it empty.';
      if (!body.basic_pension || body.basic_pension < 500) errs.basic_pension = 'Enter the monthly basic pension (at least ₹500).';
      ['age', 'basic_pension', 'commuted_amount'].forEach(k => body[k] = Number(body[k] || 0));
    }
    if (Object.keys(errs).length) { showFieldErrors(form, errs); return; }
    clearFieldErrors(form);
    try {
      await api('/onboarding/details', { method: 'POST', body });
      OB.state = await api('/onboarding'); step2();
    } catch (ex) {
      if (!(ex.data && showFieldErrors(form, ex.data.fields))) { err.textContent = ex.message; err.hidden = false; }
    }
  });
  $('#step').replaceChildren(h('section', { class: 'card onb-card' },
    h('h2', {}, office ? 'Tell us about your pension office' : 'Tell us about you and the pensioner'),
    h('p', { class: 'lead' }, office ? 'This name appears on your dashboard and in the daily summary email.' : 'We use this to check the pension and send reminders in the right language.'),
    form));
  setTimeout(() => form.querySelector('input,select').focus(), 50);
}

/* ===== Step 2: consent ===== */
function step2() {
  setProgress(2);
  const office = OB.me.role === 'office';
  const err = h('div', { class: 'form-error', role: 'alert', hidden: true });
  const box = h('input', { type: 'checkbox', name: 'consent', id: 'consent', checked: OB.state.consent_at ? true : null });
  const form = h('form', { novalidate: true }, err,
    h('label', { class: 'consent', for: 'consent' }, box, h('span', {},
      h('strong', {}, 'I agree to the storage of pensioner data. '),
      office
        ? 'I confirm that the pensioners on the lists I upload (or their families) agreed that this pension office may store their details and bank statement totals, to send life-certificate reminders and to check their pension payments.'
        : 'I agree that Pension Helper may store the pensioner\'s details and the pension totals from the bank statements I upload, to send reminders and check the pension payments.')),
    h('ul', { class: 'cell-sub', style: 'margin:14px 0 0;padding-left:18px;font-size:13.5px;line-height:1.7' },
      h('li', {}, 'Only the last 4 digits of PPO and bank account numbers are stored.'),
      h('li', {}, 'Bank statement files are read once and never saved. Only monthly pension totals are kept.'),
      h('li', {}, 'Your data is visible only to your account.'),
      h('li', {}, 'You can delete a pensioner and all their records at any time.')),
    h('div', { class: 'onb-actions' },
      h('button', { class: 'btn', type: 'button', onclick: step1 }, 'Back'),
      h('button', { class: 'btn primary large', type: 'submit' }, 'I agree, continue')));
  form.addEventListener('submit', async e => {
    e.preventDefault();
    err.hidden = true;
    if (!box.checked) { showFieldErrors(form, { consent: 'Please tick this box to continue.' }); return; }
    clearFieldErrors(form);
    try {
      await api('/onboarding/consent', { method: 'POST', body: { consent: true } });
      OB.state = await api('/onboarding'); step3();
    } catch (ex) { err.textContent = ex.message; err.hidden = false; }
  });
  $('#step').replaceChildren(h('section', { class: 'card onb-card' },
    h('h2', {}, 'Consent to store pensioner data'), h('p', { class: 'lead' }, 'We need this before any pensioner data is saved.'), form));
}

/* ===== Step 3: uploads ===== */
function step3() {
  setProgress(3);
  const office = OB.me.role === 'office';
  const area = h('div');
  const finish = async () => {
    try { await api('/onboarding/finish', { method: 'POST' }); location.href = '/dashboard'; }
    catch (e) { toast(e.message); }
  };
  $('#step').replaceChildren(
    h('section', { class: 'card onb-card', style: 'margin-bottom:18px' },
      h('h2', {}, 'Upload your documents'),
      h('p', { class: 'lead', style: 'margin:0' }, office
        ? 'Start with your pensioner list (download the CSV template if you need it), then add bank statements. You can also do this later from the Uploads page.'
        : 'Upload the pensioner\'s bank statements (CSV or PDF) so we can check every month\'s pension. You can also do this later.')),
    area,
    h('div', { class: 'onb-actions' },
      h('button', { class: 'btn', type: 'button', onclick: step2 }, 'Back'),
      h('div', { style: 'display:flex;gap:8px;flex-wrap:wrap' },
        h('button', { class: 'btn', type: 'button', onclick: finish }, 'Skip for now'),
        h('button', { class: 'btn primary large', type: 'button', onclick: finish }, 'Go to my dashboard'))));
  mountUploads(area, { role: OB.me.role });
}

/* ===== Start ===== */
$('#logout').addEventListener('click', logout);
(async () => {
  try {
    OB.me = await api('/me');
    if (OB.me.workspace.onboarding_done) { location.href = '/dashboard'; return; }
    OB.state = await api('/onboarding');
    $('#who').textContent = OB.me.role === 'office' ? 'Pension Office set-up' : 'Family set-up';
    $('#s1-label').textContent = OB.me.role === 'office' ? 'Office details' : 'Family details';
    const s = OB.state.step;
    if (s >= 3) step3(); else if (s === 2) step2(); else step1();
  } catch (e) { $('#step').replaceChildren(h('div', { class: 'form-error' }, e.message)); }
})();
