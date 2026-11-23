/* Pension Helper – family status page (no account; opened with PPO number + date of birth). Read only. Hindi / English. */

const T = {
  en: {
    brandSub: 'Pension status', leave: 'Check another pensioner', title: 'Pension status', subtitle: 'From the records of your pension office. Read only.',
    loadError: "Couldn't load the status.", age: 'Age', ppoEnding: 'PPO ending', updated: 'Updated', office: 'Pension office',
    lcTitle: 'Life certificate', payTitle: 'Pension payments',
    lc: { done: 'Verified ✓', urgent: 'Due very soon', open: 'Due', missed: 'Deadline missed', not_open_yet: 'Not open yet' },
    deadline: d => 'Deadline: ' + d, daysLeft: n => n === 1 ? '1 day left' : n + ' days left', opensOn: d => 'You can submit from ' + d,
    verifiedUntil: d => 'Verified until ' + d + ' ✓', pramaanId: id => 'Jeevan Pramaan ID ' + id, notAskedAgain: 'Recorded once. Nothing more is needed this year.',
    pay: { ok: 'Paid in full', problem: 'Money pending', no_data: 'Not checked yet' }, pending: 'pending',
    monthsAffected: n => n === 1 ? '1 month affected' : n + ' months affected', allPaid: 'Every month arrived in full.',
    noData: 'The pension office has not checked a bank statement yet.',
    letterTitle: 'Complaint to the bank', letterFor: (a, bank) => a + ' pending with ' + bank, openLetter: 'Read the letter',
    track: { drafted: 'Drafted', approved: 'Approved by office', sent: 'Sent to bank', resolved: 'Resolved', rejected: 'Not sent' },
    cstatus: { draft: 'A letter to the bank has been written. The pension office is checking it.',
      approved: 'The pension office approved the letter and will send it to the bank.',
      sent: 'The letter was sent to the bank. Waiting for the bank to pay.', resolved: 'Resolved. The bank has paid.',
      rejected: 'The pension office decided not to send this letter. Please contact them if money is still missing.' },
    noLetter: a => a + ' is pending. The pension office can see this and will prepare a letter to the bank.',
    print: 'Print', copy: 'Copy', copied: 'Copied',
    nextTitle: 'What to do next',
    s: {
      lcAppT: 'Submit the life certificate from home', lcAppX: 'On an Android phone, install the AadhaarFaceRD and Jeevan Pramaan Face apps, enter the pension details and do a face scan.',
      lcVisitT: 'Or go in person', lcVisitX: bank => 'Visit your ' + bank + ' branch, a post office or a Common Service Centre (CSC).',
      lcTellT: 'Tell the pension office', lcTellX: 'After submitting, share the Jeevan Pramaan ID from the SMS with your pension office. They record it once for the year.',
      lcMissedT: 'Submit the life certificate as soon as possible', lcMissedX: 'The pension may pause from December until it is submitted. It starts again after you submit.',
      lcDoneT: 'Life certificate: verified', lcDoneX: d => 'Verified until ' + d + '. Nothing more is needed this year.',
      lcWaitT: 'Life certificate: not yet', lcWaitX: d => 'You can submit it from ' + d + '.',
      stmtT: 'Payments not checked yet', stmtX: 'Give a recent bank statement (or passbook copy) to your pension office so they can check every month.',
      officeT: 'The pension office is on it', officeX: a => a + ' is pending. The office will write to the bank. You can check this page again any time.',
      checkT: 'The office is checking the letter', checkX: 'Once approved, the letter goes to the bank. Come back to follow it here.',
      sentT: 'Wait for the bank', sentX: 'Keep the passbook updated so you can see when the money arrives.',
      payOkT: 'Payments: nothing to do', payOkX: 'Every month arrived in full.',
      otpT: 'Never share an OTP', otpX: 'No one from the bank, the pension office or the government will ever ask for your OTP, PIN, Aadhaar or account number.'
    },
    monthTitle: 'Month by month', colMonth: 'Month', colExpected: 'Should get', colReceived: 'Received', colStatus: 'Status',
    m: { ok: 'OK', short: 'Paid short', missing: 'Not paid' },
    formula: 'Should get = basic pension + Dearness Relief − commuted amount.',
    privacy: 'For privacy this page closes by itself after 30 minutes. Account numbers and emails are never shown.'
  },
  hi: {
    brandSub: 'पेंशन की स्थिति', leave: 'दूसरे पेंशनभोगी की स्थिति देखें', title: 'पेंशन की स्थिति', subtitle: 'आपके पेंशन कार्यालय के रिकॉर्ड से। केवल देखने के लिए।',
    loadError: 'स्थिति नहीं खुल सकी।', age: 'आयु', ppoEnding: 'PPO के अंतिम अंक', updated: 'अपडेट', office: 'पेंशन कार्यालय',
    lcTitle: 'जीवन प्रमाण पत्र', payTitle: 'पेंशन भुगतान',
    lc: { done: 'सत्यापित ✓', urgent: 'जल्द जमा करें', open: 'जमा करना है', missed: 'अंतिम तिथि निकल गई', not_open_yet: 'अभी शुरू नहीं हुआ' },
    deadline: d => 'अंतिम तिथि: ' + d, daysLeft: n => n + ' दिन बचे हैं', opensOn: d => d + ' से जमा कर सकते हैं',
    verifiedUntil: d => d + ' तक सत्यापित ✓', pramaanId: id => 'जीवन प्रमाण ID ' + id, notAskedAgain: 'एक बार दर्ज हो गया। इस साल और कुछ नहीं करना है।',
    pay: { ok: 'पूरा भुगतान मिला', problem: 'राशि बाकी है', no_data: 'अभी जाँच नहीं हुई' }, pending: 'बाकी',
    monthsAffected: n => n + ' महीने प्रभावित', allPaid: 'हर महीने का पूरा भुगतान मिला है।',
    noData: 'पेंशन कार्यालय ने अभी बैंक स्टेटमेंट की जाँच नहीं की है।',
    letterTitle: 'बैंक को शिकायत', letterFor: (a, bank) => bank + ' में ' + a + ' बाकी', openLetter: 'पत्र पढ़ें',
    track: { drafted: 'पत्र तैयार', approved: 'कार्यालय ने मंज़ूर किया', sent: 'बैंक को भेजा', resolved: 'समाधान हो गया', rejected: 'नहीं भेजा' },
    cstatus: { draft: 'बैंक के लिए पत्र लिखा गया है। पेंशन कार्यालय इसकी जाँच कर रहा है।',
      approved: 'पेंशन कार्यालय ने पत्र मंज़ूर कर दिया है और इसे बैंक को भेजेगा।',
      sent: 'पत्र बैंक को भेज दिया गया है। बैंक के भुगतान का इंतज़ार है।', resolved: 'समाधान हो गया। बैंक ने भुगतान कर दिया है।',
      rejected: 'पेंशन कार्यालय ने यह पत्र नहीं भेजा। अगर राशि अब भी बाकी है तो कार्यालय से संपर्क करें।' },
    noLetter: a => a + ' बाकी है। पेंशन कार्यालय को यह दिख रहा है और वह बैंक के लिए पत्र तैयार करेगा।',
    print: 'प्रिंट', copy: 'कॉपी', copied: 'कॉपी हो गया',
    nextTitle: 'आगे क्या करें',
    s: {
      lcAppT: 'घर बैठे जीवन प्रमाण पत्र जमा करें', lcAppX: 'एंड्रॉइड फ़ोन पर AadhaarFaceRD और Jeevan Pramaan Face ऐप डाउनलोड करें, पेंशन की जानकारी भरें और चेहरे का स्कैन करें।',
      lcVisitT: 'या खुद जाकर जमा करें', lcVisitX: bank => 'अपनी ' + bank + ' शाखा, डाकघर या कॉमन सर्विस सेंटर (CSC) पर जाएँ।',
      lcTellT: 'पेंशन कार्यालय को बताएँ', lcTellX: 'जमा करने के बाद SMS में आई जीवन प्रमाण ID पेंशन कार्यालय को बताएँ। वे इसे साल में एक बार दर्ज करते हैं।',
      lcMissedT: 'जीवन प्रमाण पत्र जितनी जल्दी हो सके जमा करें', lcMissedX: 'जमा होने तक दिसंबर से पेंशन रुक सकती है। जमा करने के बाद फिर शुरू हो जाती है।',
      lcDoneT: 'जीवन प्रमाण पत्र: सत्यापित', lcDoneX: d => d + ' तक सत्यापित है। इस साल और कुछ नहीं करना है।',
      lcWaitT: 'जीवन प्रमाण पत्र: अभी नहीं', lcWaitX: d => d + ' से जमा कर सकते हैं।',
      stmtT: 'भुगतान की जाँच अभी नहीं हुई', stmtX: 'हाल का बैंक स्टेटमेंट (या पासबुक की कॉपी) पेंशन कार्यालय को दें ताकि वे हर महीना जाँच सकें।',
      officeT: 'पेंशन कार्यालय इस पर काम कर रहा है', officeX: a => a + ' बाकी है। कार्यालय बैंक को लिखेगा। आप यह पेज कभी भी फिर देख सकते हैं।',
      checkT: 'कार्यालय पत्र की जाँच कर रहा है', checkX: 'मंज़ूरी के बाद पत्र बैंक को जाएगा। इसकी प्रगति यहीं देखें।',
      sentT: 'बैंक का इंतज़ार करें', sentX: 'पासबुक अपडेट करवाते रहें ताकि पैसा आने पर पता चले।',
      payOkT: 'भुगतान: कुछ करने की ज़रूरत नहीं', payOkX: 'हर महीने का पूरा भुगतान मिला है।',
      otpT: 'कभी भी OTP न बताएँ', otpX: 'बैंक, पेंशन कार्यालय या सरकार की ओर से कोई भी आपका OTP, PIN, आधार या खाता नंबर कभी नहीं माँगेगा।'
    },
    monthTitle: 'महीने के हिसाब से', colMonth: 'महीना', colExpected: 'मिलना चाहिए', colReceived: 'मिला', colStatus: 'स्थिति',
    m: { ok: 'ठीक', short: 'कम मिला', missing: 'नहीं मिला' },
    formula: 'मिलना चाहिए = मूल पेंशन + महँगाई राहत − कम्यूटेड राशि।',
    privacy: 'गोपनीयता के लिए यह पेज 30 मिनट बाद अपने आप बंद हो जाता है। खाता नंबर और ईमेल कभी नहीं दिखाए जाते।'
  }
};
const LC_CLS = { done: 'ok', urgent: 'bad', missed: 'bad', open: 'warn', not_open_yet: 'muted' };
const PAY_CLS = { ok: 'ok', problem: 'bad', no_data: 'muted' };
const M_CLS = { ok: 'ok', short: 'warn', missing: 'bad' };

const state = { lang: 'en', data: null };
try { state.lang = localStorage.getItem('ph-lang') === 'hi' ? 'hi' : 'en'; } catch (e) {}
const t = () => T[state.lang];
const locale = () => state.lang === 'hi' ? 'hi-IN' : 'en-IN';
const toDate = v => new Date(String(v).length === 10 ? v + 'T00:00:00' : v);
const fmtDate = d => toDate(d).toLocaleDateString(locale(), { day: 'numeric', month: 'long', year: 'numeric' });
const fmtShort = d => toDate(d).toLocaleDateString(locale(), { day: 'numeric', month: 'short' });

function applyLang() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll('[data-t]').forEach(el => { const v = t()[el.dataset.t]; if (typeof v === 'string') el.textContent = v; });
  document.querySelectorAll('[data-lang]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lang === state.lang)));
  if (state.data) render();
}
document.querySelectorAll('[data-lang]').forEach(b => b.addEventListener('click', () => {
  state.lang = b.dataset.lang; try { localStorage.setItem('ph-lang', state.lang); } catch (e) {} applyLang();
}));

async function leave() {
  try { await api('/status/leave', { method: 'POST' }); } catch (e) {}
  location.href = '/#check';
}
$('#leave').addEventListener('click', leave);

async function load() {
  try {
    state.data = await api('/status');
    $('#error').classList.remove('show'); render();
    clearTimeout(load._t); load._t = setTimeout(leave, Math.max(5, state.data.expires_in) * 1000);  // close after 30 minutes
  } catch (e) { $('#error-text').textContent = e.message; $('#error').classList.add('show'); $('#result').replaceChildren(); }
}

/* ===== Letter view (read only) ===== */
function closeLetter() { $('#letter').classList.remove('open'); $('#letter').setAttribute('aria-hidden', 'true'); $('#scrim').classList.remove('open'); }
function openLetter(g) {
  const L = t();
  $('#lt-title').textContent = L.letterTitle + ' · ' + g.bank;
  $('#lt-sub').textContent = L.letterFor(inr(g.amount_short), g.bank);
  $('#lt-paper').replaceChildren(h('div', { class: 'print-skip', style: 'font:14px/1.5 var(--font);margin:-4px 0 18px;padding-bottom:16px;border-bottom:1px solid var(--border)' },
    tracker(g.status, g.timeline, L.track, fmtShort)), g.letter || '');
  $('#lt-note').textContent = L.cstatus[g.status] || '';
  $('#lt-actions').replaceChildren(
    h('button', { class: 'btn', type: 'button', onclick: async () => { try { await navigator.clipboard.writeText(g.letter || ''); toast(L.copied); } catch (e) {} } }, L.copy),
    h('button', { class: 'btn primary', type: 'button', onclick: () => { const pp = $('#lt-paper'); pp.classList.add('print-me'); window.print(); setTimeout(() => pp.classList.remove('print-me'), 500); } }, L.print));
  $('#letter').classList.add('open'); $('#letter').setAttribute('aria-hidden', 'false'); $('#scrim').classList.add('open');
}
document.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeLetter(); });
$('#scrim').addEventListener('click', closeLetter);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLetter(); });

/* ===== Render ===== */
function render() {
  const d = state.data, L = t(), p = d.pensioner;
  const lc = p.life_certificate, pay = p.payments;
  const year = new Date(d.generated_at).getFullYear();
  const deadline = new Date(year, 10, 30), opens = new Date(year, p.age >= 80 ? 9 : 10, 1);
  const owed = inr(pay.amount_short);
  const letter = d.letters[0] || null;

  const lcCard = lc.status === 'done'
    ? h('section', { class: 'card status-card' }, h('h3', {}, L.lcTitle), h('span', { class: 'chip ok' }, L.lc.done), h('div', { class: 'big' }, L.verifiedUntil(fmtDate(lc.verified_until))),
        h('div', { class: 'small' }, (lc.pramaan_id ? L.pramaanId(lc.pramaan_id) + ' · ' : '') + L.notAskedAgain))
    : h('section', { class: 'card status-card' }, h('h3', {}, L.lcTitle), h('span', { class: 'chip ' + LC_CLS[lc.status] }, L.lc[lc.status]),
        h('div', { class: 'big' }, lc.status === 'not_open_yet' ? L.opensOn(fmtDate(opens)) : lc.status === 'missed' ? L.deadline(fmtDate(deadline)) : L.daysLeft(lc.days_left)),
        h('div', { class: 'small' }, L.deadline(fmtDate(deadline))));
  const payCard = h('section', { class: 'card status-card' }, h('h3', {}, L.payTitle), h('span', { class: 'chip ' + PAY_CLS[pay.status] }, L.pay[pay.status]),
    pay.status === 'problem' ? [h('div', { class: 'big' }, h('span', { 'data-count': pay.amount_short, 'data-format': 'inr', 'data-count-key': 'status-owed' }, owed), ' ' + L.pending), h('div', { class: 'small' }, L.monthsAffected(pay.problem_months))]
      : pay.status === 'ok' ? h('div', { class: 'big', style: 'font-size:17px' }, L.allPaid)
      : h('div', { class: 'small', style: 'margin-top:10px' }, L.noData));

  const letterCard = letter ? h('section', { class: 'card', style: 'margin-bottom:18px' },
    h('div', { class: 'card-head' }, h('h2', {}, L.letterTitle), h('span', { class: 'hint' }, L.letterFor(inr(letter.amount_short), letter.bank))),
    h('div', { class: 'card-body' }, tracker(letter.status, letter.timeline, L.track, fmtShort),
      h('p', { style: 'margin:16px 0 12px;font-size:14.5px' }, L.cstatus[letter.status] || ''),
      letter.letter ? h('button', { class: 'btn primary', type: 'button', onclick: () => openLetter(letter) }, L.openLetter) : null))
    : pay.status === 'problem' ? h('section', { class: 'card', style: 'margin-bottom:18px' }, h('div', { class: 'card-head' }, h('h2', {}, L.letterTitle)),
        h('div', { class: 'card-body' }, h('p', { style: 'margin:0' }, L.noLetter(owed)))) : null;

  const S = L.s, steps = [];
  const step = (title, text, warning) => steps.push(h('li', { class: warning ? 'warning' : '' }, h('div', {}, h('strong', {}, title), h('span', {}, text))));
  if (lc.status === 'urgent' || lc.status === 'open') { step(S.lcAppT, S.lcAppX); step(S.lcVisitT, S.lcVisitX(p.bank)); step(S.lcTellT, S.lcTellX); }
  else if (lc.status === 'missed') { step(S.lcMissedT, S.lcMissedX); step(S.lcAppT, S.lcAppX); step(S.lcTellT, S.lcTellX); }
  else if (lc.status === 'not_open_yet') step(S.lcWaitT, S.lcWaitX(fmtDate(opens)));
  else step(S.lcDoneT, S.lcDoneX(fmtDate(lc.verified_until)));
  if (pay.status === 'no_data') step(S.stmtT, S.stmtX);
  else if (pay.status === 'ok') step(S.payOkT, S.payOkX);
  else if (!letter || letter.status === 'rejected') step(S.officeT, S.officeX(owed));
  else if (letter.status === 'draft') step(S.checkT, S.checkX);
  else if (letter.status === 'approved' || letter.status === 'sent') step(S.sentT, S.sentX);
  step(S.otpT, S.otpX, true);

  const monthName = ym => { const [y, m] = ym.split('-'); return new Date(+y, +m - 1, 1).toLocaleDateString(locale(), { month: 'long', year: 'numeric' }); };
  $('#result').replaceChildren(...[
    h('section', { class: 'card who-card' }, h('div', { class: 'avatar', 'aria-hidden': 'true' }, initials(p.name)),
      h('div', {}, h('h3', {}, p.name), h('p', {}, L.age + ' ' + p.age + ' · ' + p.bank + ' · ' + L.ppoEnding + ' ' + p.ppo_last4),
        h('p', { class: 'cell-sub' }, (d.office ? L.office + ': ' + d.office + ' · ' : '') + L.updated + ' ' + new Date(d.generated_at).toLocaleTimeString(locale(), { hour: 'numeric', minute: '2-digit' })))),
    h('div', { class: 'status-grid' }, lcCard, payCard),
    letterCard,
    h('section', { class: 'card', style: 'margin-bottom:18px' }, h('div', { class: 'card-head' }, h('h2', {}, L.nextTitle)), h('div', { class: 'card-body' }, h('ol', { class: 'steps' }, steps))),
    pay.months.length ? h('section', { class: 'card', style: 'overflow:hidden;margin-bottom:18px' }, h('div', { class: 'card-head' }, h('h2', {}, L.monthTitle)),
      h('table', { class: 'pay' },
        h('thead', {}, h('tr', {}, h('th', {}, L.colMonth), h('th', { class: 'num' }, L.colExpected), h('th', { class: 'num' }, L.colReceived), h('th', {}, L.colStatus))),
        h('tbody', {}, pay.months.map(m => h('tr', {}, h('td', {}, monthName(m.month)), h('td', { class: 'num' }, inr(m.expected)), h('td', { class: 'num' }, inr(m.received)),
          h('td', {}, h('span', { class: 'chip ' + M_CLS[m.status] }, L.m[m.status])))))),
      h('p', { class: 'cell-sub', style: 'padding:10px 20px 16px;margin:0' }, L.formula)) : null,
    h('p', { class: 'cell-sub', style: 'text-align:center' }, '🔒 ' + L.privacy)
  ].filter(Boolean));
  $('#result').removeAttribute('aria-busy');
  if (window.PH) PH.reveal($('#result'));  // cards fade up one by one, amounts count up
}

applyLang();
load();
