/* Pension Helper – helpers shared by every page. Pages only ever talk to /api on this server. */

const $ = (s, el = document) => el.querySelector(s);
const inr = n => '₹' + Math.round(n || 0).toLocaleString('en-IN');
const initials = name => String(name || '?').split(/[\s@.]+/).filter(Boolean).map(w => w[0]).slice(0, 2).join('').toUpperCase();
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const shortMonth = ym => { const [y, m] = ym.split('-'); return MONTHS[+m - 1] + " '" + y.slice(2); };

/* Build elements safely: text is always added as text, never as HTML. */
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : String(kid));
  return el;
};

function toast(msg) {
  const t = $('#toast'); if (!t) return;
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 3600);
}

/* Talk to our own backend. A 401 means the login ran out: go back to the login page. */
async function api(path, { method = 'GET', body, form } = {}) {
  const res = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: body ? { 'content-type': 'application/json' } : {},
    body: form || (body ? JSON.stringify(body) : undefined)
  });
  if (res.status === 401 && path.startsWith('/status')) { location.href = '/#check'; throw new Error('Please enter the PPO number and date of birth again.'); }
  if (res.status === 401 && !/^\/(login|signup)$/.test(path)) { location.href = '/login'; throw new Error('Please log in again.'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const err = new Error(typeof d === 'string' ? d : 'Something went wrong (' + res.status + ').');
    err.status = res.status; err.code = data.code || null; err.data = data;
    throw err;
  }
  return data;
}

async function logout() {
  try { await api('/logout', { method: 'POST' }); } catch (e) {}
  location.href = '/';
}

/* Form helpers: show per-field messages under each input. */
function clearFieldErrors(form) {
  form.querySelectorAll('.field-error').forEach(e => e.remove());
  form.querySelectorAll('[aria-invalid]').forEach(e => e.removeAttribute('aria-invalid'));
}
function showFieldErrors(form, fields) {
  clearFieldErrors(form);
  let first = null;
  for (const [name, msg] of Object.entries(fields || {})) {
    const input = form.elements[name];
    if (!input || !input.closest) continue;
    input.setAttribute('aria-invalid', 'true');
    (input.closest('.field') || input.closest('label') || input.parentElement).append(h('div', { class: 'field-error' }, msg));
    first = first || input;
  }
  if (first) first.focus();
  return !!first;
}

/* Icons (inline SVG, drawn by us). */
const ICON = {
  logo: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 4l9 6.5"/><path d="M5 10v8m4.5-8v8m5-8v8M19 10v8"/><path d="M3 20h18"/></svg>',
  home: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/></svg>',
  upload: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4"/><path d="m6 10 6-6 6 6"/><path d="M4 20h16"/></svg>',
  settings: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  out: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>',
  file: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M12 18v-6"/><path d="m9 15 3-3 3 3"/></svg>',
  users: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/></svg>'
};
const icon = name => { const s = h('span', { 'aria-hidden': 'true', style: 'display:inline-flex' }); s.innerHTML = ICON[name] || ''; return s; };
document.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = ICON[el.dataset.icon] || ''; });

/* App shell: sidebar on desktop, a small top bar on phones. Fills #shell-side and #shell-top. */
async function mountShell(active) {
  const me = await api('/me');
  if (!me.workspace.onboarding_done) { location.href = '/onboarding'; throw new Error('Onboarding not finished.'); }
  const links = [['/dashboard', 'Dashboard', 'home', 'dashboard'], ['/uploads', 'Uploads', 'upload', 'uploads'], ['/settings', 'Settings', 'settings', 'settings']];
  const navLink = ([href, label, ic, key], withIcon) => h('a', { href, 'aria-current': key === active ? 'page' : null }, withIcon ? icon(ic) : null, label);
  const brand = h('a', { class: 'brand', href: '/dashboard' }, h('div', { class: 'logo' }, icon('logo')),
    h('div', {}, h('div', { class: 'brand-name' }, 'Pension Helper'), h('div', { class: 'brand-sub' }, me.role === 'office' ? 'Pension Office' : 'Family')));
  const side = $('#shell-side');
  if (side) side.replaceChildren(
    brand,
    h('nav', { class: 'nav', 'aria-label': 'Main' }, links.map(l => navLink(l, true))),
    h('div', { class: 'side-foot' },
      h('div', { class: 'side-user' }, h('div', { class: 'avatar', 'aria-hidden': 'true' }, initials(me.display_name)),
        h('div', { style: 'min-width:0' }, h('strong', {}, me.workspace.name || me.display_name), h('span', {}, me.email))),
      h('div', { class: 'side-actions' }, h('span', { 'data-theme-toggle': '' }), h('button', { class: 'btn small', type: 'button', onclick: logout }, icon('out'), 'Log out'))));
  const top = $('#shell-top');
  if (top) top.replaceChildren(
    h('a', { class: 'brand', href: '/dashboard', 'aria-label': 'Pension Helper' }, h('div', { class: 'logo', style: 'width:34px;height:34px' }, icon('logo'))),
    h('nav', {}, links.map(l => navLink(l, false))),
    h('div', { class: 'mobile-tools' }, h('span', { 'data-theme-toggle': '' }),
      h('button', { class: 'btn small', type: 'button', onclick: logout, title: 'Log out' }, icon('out'), h('span', { class: 'logout-text' }, 'Log out'))));
  if (window.PH) PH.mountToggles();
  return me;
}

/* Complaint tracker: Drafted -> Approved by office -> Sent to bank -> Resolved. */
const TRACK_STAGES = ['drafted', 'approved', 'sent', 'resolved'];
const TRACK_INDEX = { draft: 0, approved: 1, sent: 2, resolved: 3 };
function tracker(status, timeline, labels, fmt) {
  const tl = timeline || {};
  const rejected = status === 'rejected';
  const current = rejected ? 1 : (TRACK_INDEX[status] ?? 0);
  return h('ol', { class: 'tracker' + (rejected ? ' is-rejected' : '') }, TRACK_STAGES.map((key, i) => {
    const isRejectStep = rejected && i === 1;
    const done = rejected ? i === 0 : i <= current;
    const cls = isRejectStep ? 'rejected' : done ? (i === current ? 'done current' : 'done') : 'todo';
    const when = isRejectStep ? tl.rejected : tl[key];
    return h('li', { class: 'tstep ' + cls, 'aria-current': i === current ? 'step' : null },
      h('span', { class: 'tdot', 'aria-hidden': 'true' }, isRejectStep ? '✕' : done ? '✓' : String(i + 1)),
      h('span', { class: 'tlabel' }, isRejectStep ? labels.rejected : labels[key]),
      when && (done || isRejectStep) ? h('span', { class: 'twhen' }, fmt(when)) : null);
  }));
}
