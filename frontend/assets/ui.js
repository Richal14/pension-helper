/* Pension Helper – theme (light / dark) and motion. Uses GSAP when it has loaded; every page still works without it.
   Respects "reduce motion": no movement, numbers appear straight away. */
(function () {
  const root = document.documentElement;
  const mqDark = window.matchMedia('(prefers-color-scheme: dark)');
  const mqReduceRaw = window.matchMedia('(prefers-reduced-motion: reduce)');
  // "reduce motion" is respected unless the presenter opened the page once with ?motion=on (html.force-motion)
  const mqReduce = { get matches() { return mqReduceRaw.matches && !root.classList.contains('force-motion'); } };
  const G = () => (window.gsap && !mqReduce.matches ? window.gsap : null);

  /* ---------------- Theme ---------------- */
  const stored = () => { try { return localStorage.getItem('ph-theme'); } catch (e) { return null; } };
  function apply(theme, animate) {
    if (animate && !mqReduce.matches) {
      root.classList.add('theme-anim');
      clearTimeout(apply._t); apply._t = setTimeout(() => root.classList.remove('theme-anim'), 500);
    }
    root.dataset.theme = theme;
    document.querySelectorAll('.theme-toggle').forEach(b => {
      b.setAttribute('aria-pressed', String(theme === 'dark'));
      b.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      b.title = b.getAttribute('aria-label');
    });
  }
  function toggleTheme() {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('ph-theme', next); } catch (e) {}
    apply(next, true);
  }
  // Follow the system setting until the person picks a theme themselves.
  mqDark.addEventListener && mqDark.addEventListener('change', e => { if (!stored()) apply(e.matches ? 'dark' : 'light', true); });

  const SUN = '<svg class="sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/></svg>';
  const MOON = '<svg class="moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7z"/></svg>';
  function themeButton() {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'icon-btn theme-toggle';
    b.innerHTML = SUN + MOON;
    b.addEventListener('click', toggleTheme);
    return b;
  }
  function mountToggles(scope) {
    (scope || document).querySelectorAll('[data-theme-toggle]').forEach(slot => slot.replaceWith(themeButton()));
    apply(root.dataset.theme || (mqDark.matches ? 'dark' : 'light'));
  }

  /* ---------------- Count-up numbers ---------------- */
  const lastValue = {};
  const fmt = (n, el) => {
    const f = el.dataset.format, v = Math.round(n);
    const body = f === 'inr' ? '₹' + v.toLocaleString('en-IN') : v.toLocaleString('en-IN');
    return (el.dataset.prefix || '') + body + (el.dataset.suffix || '');
  };
  function countUp(el) {
    if (el.dataset.counted) return;
    el.dataset.counted = '1';
    const to = Number(el.dataset.count) || 0, key = el.dataset.countKey;
    const from = key && key in lastValue ? lastValue[key] : 0;
    if (key) lastValue[key] = to;
    if (mqReduce.matches || from === to) { el.textContent = fmt(to, el); return; }
    const dur = Math.min(1400, 600 + Math.log10(Math.abs(to - from) + 1) * 220), t0 = performance.now();
    el.textContent = fmt(from, el);
    const step = now => {
      const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(from + (to - from) * e, el);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /* ---------------- Fade up on scroll ---------------- */
  const REVEAL = '.card, .kpi, .deadline, .feature, .status-card, .who-card, .empty-hero, .pipeline, .section-head, .file-result, [data-reveal]';
  let io = null;
  function animateIn(els) {
    const g = G();
    els.forEach((el, i) => {
      el.querySelectorAll('[data-count]').forEach(countUp);
      if (el.matches('[data-count]')) countUp(el);
      if (g) g.fromTo(el, { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: .7, delay: i * .09, ease: 'power3.out', clearProps: 'transform,opacity' });
      else if (!mqReduce.matches && el.animate) el.animate([{ opacity: 0, transform: 'translateY(22px)' }, { opacity: 1, transform: 'none' }], { duration: 600, delay: i * 90, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'backwards' });
    });
  }
  function reveal(scope) {
    const els = [...(scope || document).querySelectorAll(REVEAL)].filter(el => !el.dataset.revealed && !el.closest('.modal, .drawer'));
    els.forEach(el => { el.dataset.revealed = '1'; });
    // numbers outside cards still count up
    (scope || document).querySelectorAll('[data-count]').forEach(el => { if (!el.closest(REVEAL)) countUp(el); });
    if (!('IntersectionObserver' in window)) { els.forEach(el => el.querySelectorAll('[data-count]').forEach(countUp)); return; }
    if (!io) io = new IntersectionObserver(entries => {
      const shown = entries.filter(e => e.isIntersecting).map(e => e.target);
      shown.forEach(el => io.unobserve(el));
      if (shown.length) animateIn(shown);
    }, { rootMargin: '0px 0px -6% 0px', threshold: .08 });
    els.forEach(el => io.observe(el));
  }

  /* ---------------- Landing: hero words + pipeline ---------------- */
  function splitWords(el) {
    if (!el || el.dataset.split) return [];
    el.dataset.split = '1';
    const out = [];
    [...el.childNodes].forEach(node => {
      if (node.nodeType === 3) {
        const frag = document.createDocumentFragment();
        node.textContent.split(/(\s+)/).forEach(part => {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.append(document.createTextNode(part)); return; }
          const s = document.createElement('span'); s.className = 'w'; s.textContent = part; frag.append(s); out.push(s);
        });
        node.replaceWith(frag);
      } else if (node.nodeType === 1) { node.classList.add('w'); out.push(node); }
    });
    return out;
  }
  function hero() {
    const h1 = document.querySelector('.hero h1'), tag = document.querySelector('.hero .tagline');
    if (!h1) return;
    const words = [...splitWords(h1), ...splitWords(tag)];
    const box = document.querySelector('.hero .check-box');
    const rest = [...document.querySelectorAll('.hero [data-anim]')].filter(el => el !== h1 && el !== tag && el !== box);
    const g = G();
    const show = el => { if (el) { el.style.opacity = '1'; el.style.animation = 'none'; } };
    [h1, tag].forEach(show);
    if (!g) { rest.forEach(show); show(box); return; }
    g.set(words, { opacity: 0, y: 28, filter: 'blur(8px)' });
    const tl = g.timeline({ defaults: { ease: 'power3.out' } });
    if (box) tl.fromTo(box, { opacity: 0, y: 30, scale: .97 }, { opacity: 1, y: 0, scale: 1, duration: .9, clearProps: 'transform', onStart: () => { box.style.animation = 'none'; } }, .15);
    tl.to(words, { opacity: 1, y: 0, filter: 'blur(0px)', duration: .7, stagger: .045 }, 0)
      .fromTo(rest, { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: .6, stagger: .08, clearProps: 'transform', onStart: () => rest.forEach(el => { el.style.animation = 'none'; }) }, '-=.5');
  }
  function pipeline() {
    const box = document.querySelector('.pipeline');
    if (!box) return;
    const steps = [...box.querySelectorAll('.pipe-step')], dot = box.querySelector('.pipe-dot'), fill = box.querySelector('.pipe-fill');
    const g = G();
    if (!g) { steps.forEach(s => s.classList.add('lit')); if (fill) fill.removeAttribute('style'); return; }
    let tl = null;
    function build() {
      if (tl) tl.kill();
      steps.forEach(s => s.classList.remove('lit'));
      const vertical = window.matchMedia('(max-width: 760px)').matches;
      const base = box.querySelector('.pipe-wrap').getBoundingClientRect();
      const pts = steps.map(s => { const r = s.querySelector('.pipe-icon').getBoundingClientRect(); return { x: r.left + r.width / 2 - base.left, y: r.top + r.height / 2 - base.top }; });
      const half = 6.5, first = pts[0];
      g.set(dot, { x: first.x - half, y: first.y - half, left: 0, top: 0, opacity: 0 });
      if (vertical) g.set(fill, { height: 0, width: 3, top: first.y, left: first.x - 1.5, bottom: 'auto', right: 'auto' });
      else g.set(fill, { width: 0, height: 3, left: first.x, top: first.y - 1.5, right: 'auto', bottom: 'auto' });
      tl = g.timeline({ repeat: -1, repeatDelay: .6, paused: true });
      tl.to(dot, { opacity: 1, duration: .25 }).call(() => steps[0].classList.add('lit'));
      pts.forEach((p, i) => {
        if (!i) return;
        const size = vertical ? { height: p.y - first.y } : { width: p.x - first.x };
        tl.to(dot, { x: p.x - half, y: p.y - half, duration: .9, ease: 'power1.inOut' }, '+=.45')
          .to(fill, { ...size, duration: .9, ease: 'power1.inOut' }, '<')
          .call(() => steps[i].classList.add('lit'));
      });
      tl.to({}, { duration: 1.8 })
        .to(dot, { opacity: 0, duration: .3 })
        .call(() => steps.forEach(s => s.classList.remove('lit')))
        .to(fill, vertical ? { height: 0, duration: .4 } : { width: 0, duration: .4 });
      if (inView) tl.play();
    }
    let inView = false;
    new IntersectionObserver(([e]) => { inView = e.isIntersecting; if (tl) inView ? tl.play() : tl.pause(); }, { threshold: .25 }).observe(box);
    build();
    let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(build, 200); });
  }

  /* ---------------- Smooth page changes ---------------- */
  // Fade the page out before following a link to another page of this app (the next page fades in).
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target || a.hasAttribute('download')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.pathname.startsWith('/api/') || (url.pathname === location.pathname && url.hash)) return;
    if (mqReduce.matches) return;
    e.preventDefault();
    root.classList.add('leaving');
    setTimeout(() => { location.href = url.href; }, 170);
  });
  window.addEventListener('pageshow', () => root.classList.remove('leaving'));  // coming back with the Back button

  /* ---------------- Start ---------------- */
  window.PH = { toggleTheme, themeButton, mountToggles, reveal, countUp, reduced: () => mqReduce.matches, gsap: G };
  function start() {
    mountToggles();
    hero();
    pipeline();
    reveal();
    // containers filled in later by page scripts (onboarding steps, upload results)
    document.querySelectorAll('[data-auto-reveal]').forEach(box => new MutationObserver(() => reveal(box)).observe(box, { childList: true, subtree: true }));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
