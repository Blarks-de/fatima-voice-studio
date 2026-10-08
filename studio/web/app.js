'use strict';
// Fatima Voice Studio: the whole UI. Plain JS, no build step.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const plural = (n, word, many) => `${n} ${n === 1 ? word : (many || word + 's')}`;
const S = { state: null, voices: [], settings: null, batches: [], detail: null, view: null, scripts: [], smode: 'list', cmode: 'single' };

// ---------- icons (inline SVG, follow the text colour) ----------
const ICONS = {
  mark: '<path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6 6 0 0 1 3.5 5.5"/>',
  box: '<path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8ZM12 17v5"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  drive: '<rect x="2" y="13" width="20" height="8" rx="2"/><path d="M5 13 7.5 4h9L19 13M6 17h.01M10 17h.01"/>',
  upload: '<path d="M12 15V3M7 8l5-5 5 5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  play: '<path d="M7 4.5v15l12-7.5-12-7.5Z"/>',
  wave: '<path d="M2 12h2M6 8v8M10 5v14M14 9v6M18 7v10M22 12h0"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  folder: '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z"/>',
  pencil: '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5Z"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4M21 4v5h-5"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  up: '<path d="m6 15 6-6 6 6"/>', down: '<path d="m6 9 6 6 6-6"/>',
  pause: '<path d="M8 5v14M16 5v14"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3"/>',
  check: '<path d="m5 12 5 5 9-10"/>', alert: '<path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
  star: '<path d="m12 3 2.8 5.8 6.2.9-4.5 4.4 1 6.2L12 17.4 6.5 20.3l1-6.2L3 9.7l6.2-.9L12 3Z"/>',
  dice: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 8h.01M16 8h.01M12 12h.01M8 16h.01M16 16h.01"/>',
  speaker: '<path d="M11 5 6 9H3v6h3l5 4V5ZM16 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/>',
};
const icon = (name, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;
function paintIcons(root = document) { root.querySelectorAll('[data-icon]').forEach((el) => { el.outerHTML = icon(el.dataset.icon); }); }

// ---------- server ----------
async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: { 'X-Studio': '1' } };
  if (opts.json !== undefined) { init.body = JSON.stringify(opts.json); init.headers['Content-Type'] = 'application/json'; }
  if (opts.form) init.body = opts.form;
  const r = await fetch(path, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : (j.detail?.[0]?.msg || msg); } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return opts.raw ? r : r.json();
}

let toastTimer;
function toast(msg, ok = false) {
  const t = $('toast');
  const host = [...document.querySelectorAll('dialog[open]')].pop() || document.body;
  if (t.parentElement !== host) host.append(t);
  t.textContent = msg; t.className = 'toast' + (ok ? ' ok' : ''); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, ok ? 2600 : 7000);
}
const run = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message); } };

// Polling redraws constantly: only touch the DOM when the markup changed, and not while a button is held.
let pointerHeld = false;
window.addEventListener('pointerdown', () => { pointerHeld = true; }, true);
window.addEventListener('pointerup', () => { pointerHeld = false; }, true);
function setHtml(el, html) {
  if (!el || el._html === html || pointerHeld) return;
  // Keep audio that's playing: redraws would stop it.
  if ([...el.querySelectorAll('audio')].some((a) => !a.paused)) return;
  el._html = html;
  el.innerHTML = html;
}

function fmtDur(sec) {
  if (sec == null) return '—';
  sec = Math.round(sec);
  if (sec < 60) return `${sec} s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m < 60) return `${m} min${s ? ` ${s} s` : ''}`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
function fmtClock(sec) { sec = Math.round(sec || 0); return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`; }
function fmtWhen(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === now.toDateString()) return `today ${time}`;
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${time}`;
}
const fmtSize = (b) => (b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.round(b / 1e6)} MB`);
const langName = (code) => S.state?.languages?.[code] || code || '—';
const voiceName = (id) => S.voices.find((v) => v.id === id)?.name || (id ? id : 'no voice');
const fileUrl = (b, rel, v, dl) => `/api/batches/${b}/files/${rel.split('/').map(encodeURIComponent).join('/')}?v=${encodeURIComponent(v || '')}${dl ? '&download=1' : ''}`;
const isBusy = (st) => ['running', 'queued', 'finishing'].includes(st);

const STATUS = {
  running: ['accent live', 'Speaking'], queued: ['', 'Queued'], paused: ['warn', 'Paused'], finishing: ['accent live', 'Finishing'],
  done: ['ok', 'Done'], failed: ['red', 'Needs attention'], cancelled: ['', 'Cancelled'], pending: ['', 'Waiting'],
};
const chip = (st) => { const [c, t] = STATUS[st] || ['', st]; return `<span class="chip ${c}">${t}</span>`; };

function confirmDialog(title, body, okLabel = 'Delete') {
  return new Promise((resolve) => {
    const dlg = $('confirm');
    $('confirm-title').textContent = title;
    $('confirm-body').textContent = body;
    $('confirm-ok').textContent = okLabel;
    dlg.returnValue = '';
    dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true });
    dlg.showModal();
  });
}

// A general editor dialog: title + big text + optional extra fields. Resolves with the values or null.
function editDialog({ title, help = '', name = null, nameLabel = 'Title', text = null, rows = 14, extra = '', ok = 'Save', onOpen }) {
  return new Promise((resolve) => {
    const dlg = $('editor');
    $('editor-title').textContent = title;
    $('editor-help').textContent = help; $('editor-help').hidden = !help;
    $('editor-name-field').hidden = name === null;
    $('editor-name-field').querySelector('label').textContent = nameLabel;
    $('editor-name').value = name ?? '';
    $('editor-text').hidden = text === null;
    $('editor-text').value = text ?? '';
    $('editor-text').rows = rows;
    $('editor-extra').innerHTML = extra;
    paintIcons($('editor-extra'));
    $('editor-ok').textContent = ok;
    dlg.returnValue = '';
    dlg.addEventListener('close', () => {
      if (dlg.returnValue !== 'ok') return resolve(null);
      const extraVals = {};
      $('editor-extra').querySelectorAll('[name]').forEach((el) => { extraVals[el.name] = el.type === 'checkbox' ? el.checked : el.value; });
      resolve({ name: $('editor-name').value, text: $('editor-text').value, ...extraVals });
    }, { once: true });
    dlg.showModal();
    onOpen?.(dlg);
  });
}

function voiceOptions(selected, { blank } = {}) {
  const opts = S.voices.map((v) => `<option value="${esc(v.id)}"${v.id === selected ? ' selected' : ''}>${esc(v.name)}${v.language ? ` · ${esc(langName(v.language))}` : ''}</option>`);
  if (blank) opts.unshift(`<option value=""${!selected ? ' selected' : ''}>${esc(blank)}</option>`);
  if (!S.voices.length && !blank) opts.unshift('<option value="">No voices yet — add one on the Voices page</option>');
  return opts.join('');
}
function languageOptions(selected) {
  return Object.entries(S.state?.languages || {}).map(([k, v]) => `<option value="${k}"${k === selected ? ' selected' : ''}>${esc(v)}</option>`).join('');
}

// ---------- routing ----------
const VIEWS = ['create', 'batches', 'batch', 'voices', 'models', 'setup', 'connect', 'settings'];
function route() {
  const [view, arg] = (location.hash.slice(1) || 'create').split('/');
  let v = VIEWS.includes(view) ? view : 'create';
  if (document.body.classList.contains('locked') && v !== 'setup') { v = 'setup'; history.replaceState(null, '', '#setup'); }
  S.view = v; S.arg = arg ? decodeURIComponent(arg) : null;
  VIEWS.forEach((x) => { $(`view-${x}`).hidden = x !== v; });
  document.querySelectorAll('.nav a').forEach((a) => {
    const on = a.dataset.view === v || (v === 'batch' && a.dataset.view === 'batches') || (v === 'setup' && a.dataset.view === 'settings' && !document.body.classList.contains('locked'));
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('settings-menu').hidden = true;
  ({ create: showCreate, batches: loadBatches, batch: loadDetail, voices: loadVoices, models: loadModels, setup: loadSetup,
     connect: loadConnect, settings: loadSettings })[v]?.();
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);

// The Settings tab opens a small menu: General or Setup.
document.querySelector('.nav a[data-view="settings"]').addEventListener('click', (e) => {
  if (document.body.classList.contains('locked')) return;
  e.preventDefault();
  const m = $('settings-menu'), r = e.currentTarget.getBoundingClientRect();
  m.style.left = `${Math.min(r.left, innerWidth - 250)}px`; m.style.top = `${r.bottom + 6}px`;
  m.hidden = !m.hidden;
});
document.addEventListener('click', (e) => { if (!e.target.closest('.nav a[data-view="settings"], #settings-menu')) $('settings-menu').hidden = true; });

document.addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-open-folder]');
  if (b) await api('/api/open-folder', { method: 'POST', json: { which: b.dataset.openFolder } });
}));

// ---------- status poll ----------
async function pollState() {
  try {
    S.state = await api('/api/state');
  } catch {
    $('engine-text').textContent = 'Not running'; $('engine-dot').className = 'state-dot error';
    return;
  }
  const st = S.state;
  const wasLocked = document.body.classList.contains('locked');
  document.body.classList.toggle('locked', !st.setup_ready);
  if (!st.setup_ready && S.view !== 'setup') location.hash = '#setup';
  if (wasLocked && st.setup_ready) route();
  const eng = st.engine;
  let text, sub = '', dot = '';
  if (eng.state === 'error') { text = 'Engine problem'; sub = eng.error || ''; dot = 'error'; }
  else if (st.current || st.api_busy) {
    dot = 'busy';
    const pct = eng.frames_expected ? Math.min(99, Math.round(100 * eng.frames / eng.frames_expected)) : null;
    text = st.api_busy && !st.current ? 'Speaking · API / preview' : `Speaking${pct != null ? ` · ${pct}%` : ''}`;
    sub = st.current ? `“${st.current.text}”` : '';
  } else if (st.finishing) { dot = 'busy'; text = 'Writing files · subtitles'; }
  else { text = st.setup_ready ? `Ready · ${eng.engine.toUpperCase()}` : 'Setup needed'; dot = st.setup_ready ? '' : 'off'; }
  $('engine-text').textContent = text; $('engine-sub').textContent = sub; $('engine-dot').className = `state-dot ${dot}`;
  $('foot-right').textContent = `v${st.version} · ${st.api_base}`;
  if (st.update?.status === 'available') $('foot-left').innerHTML = `Fatima Voice Studio · <a href="#settings">update ${esc(st.update.latest)} available</a>`;
}

// ---------- CREATE ----------
const DRAFT = 'fvs-draft-v1';
function saveDraft() {
  try { localStorage.setItem(DRAFT, JSON.stringify({ single: $('single-text').value, scripts: S.scripts, name: $('batch-name').value, cmode: S.cmode })); } catch { /* storage off */ }
}
function loadDraft() {
  try {
    const d = JSON.parse(localStorage.getItem(DRAFT) || '{}');
    $('single-text').value = d.single || '';
    S.scripts = Array.isArray(d.scripts) && d.scripts.length ? d.scripts : [{ title: '', text: '' }];
    $('batch-name').value = d.name || '';
    if (d.cmode) setCmode(d.cmode, false);
  } catch { S.scripts = [{ title: '', text: '' }]; }
}

function setCmode(mode, save = true) {
  S.cmode = mode;
  $('composer').dataset.cmode = mode; document.body.dataset.cmode = mode;
  $('create-mode').querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b.dataset.cmode === mode));
  $('go-label').textContent = mode === 'single' ? 'Make it' : 'Start batch';
  if (save) saveDraft();
  updateSummary();
}
$('create-mode').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) setCmode(b.dataset.cmode); });

function setSmode(mode) {
  S.smode = mode;
  document.querySelectorAll('[data-smode]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.smode === mode));
  $('script-list').hidden = mode !== 'list'; $('list-tools').hidden = mode !== 'list';
  $('paste-box').hidden = mode !== 'paste';
}
document.querySelectorAll('[data-smode]').forEach((b) => b.addEventListener('click', () => setSmode(b.dataset.smode)));

function renderScripts() {
  $('script-list').innerHTML = S.scripts.map((s, i) => `
    <li class="script-row" data-i="${i}">
      <div class="head"><span class="num">${String(i + 1).padStart(2, '0')}</span>
        <input class="title" data-f="title" value="${esc(s.title)}" placeholder="Title (optional — taken from the first words)">
        <button type="button" class="icon-btn" data-act="del" aria-label="Remove script">${icon('x')}</button></div>
      <textarea data-f="text" rows="${Math.min(12, Math.max(3, Math.ceil((s.text || '').length / 70)))}" placeholder="Script text. Blank lines start a new paragraph.">${esc(s.text)}</textarea>
      <div class="row between" style="gap:8px">
        <span class="meta">${s.text ? `${s.text.length.toLocaleString()} characters · about ${fmtDur(s.text.length / 14)}` : ''}</span>
        <span class="row" style="gap:6px">
          <select class="mini" data-f="voice" aria-label="Voice for this script">${voiceOptions(s.voice || '', { blank: 'Batch voice' })}</select>
          <select class="mini" data-f="language" aria-label="Language for this script"><option value="">Batch language</option>${languageOptions(s.language || '')}</select>
        </span></div>
    </li>`).join('');
  $('script-count').textContent = plural(S.scripts.filter((s) => s.text.trim()).length, 'script');
}
$('script-list').addEventListener('input', (e) => {
  const row = e.target.closest('.script-row'); if (!row) return;
  const f = e.target.dataset.f;
  S.scripts[row.dataset.i][f] = e.target.value;
  if (f === 'voice' && e.target.value) {  // a voice brings its own language
    const v = S.voices.find((x) => x.id === e.target.value);
    if (v?.language) { S.scripts[row.dataset.i].language = v.language; row.querySelector('[data-f="language"]').value = v.language; }
  }
  if (f === 'text') row.querySelector('.meta').textContent = e.target.value ? `${e.target.value.length.toLocaleString()} characters · about ${fmtDur(e.target.value.length / 14)}` : '';
  $('script-count').textContent = plural(S.scripts.filter((s) => s.text.trim()).length, 'script');
  saveDraft(); updateSummary();
});
$('script-list').addEventListener('click', (e) => {
  const b = e.target.closest('[data-act="del"]'); if (!b) return;
  S.scripts.splice(Number(b.closest('.script-row').dataset.i), 1);
  if (!S.scripts.length) S.scripts.push({ title: '', text: '' });
  renderScripts(); saveDraft(); updateSummary();
});
$('add-script').addEventListener('click', () => {
  S.scripts.push({ title: '', text: '' }); renderScripts(); saveDraft();
  $('script-list').lastElementChild?.querySelector('textarea')?.focus();
});

// "Paste and split": ### headings or --- lines separate scripts.
function splitPasted(text) {
  const out = [];
  let cur = null;
  for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
    const h = line.match(/^\s*#{1,3}\s+(.+?)\s*$/);
    if (h || /^\s*-{3,}\s*$/.test(line)) {
      if (cur && cur.text.trim()) out.push(cur);
      cur = { title: h ? h[1] : '', text: '' };
    } else {
      cur = cur || { title: '', text: '' };
      cur.text += line + '\n';
    }
  }
  if (cur && cur.text.trim()) out.push(cur);
  return out.map((s) => ({ title: s.title, text: s.text.trim() }));
}
$('paste-text').addEventListener('input', () => {
  const found = splitPasted($('paste-text').value);
  $('paste-found').textContent = found.length ? `${plural(found.length, 'script')} found: ${found.slice(0, 4).map((s) => s.title || s.text.slice(0, 24) + '…').join(' · ')}${found.length > 4 ? ' …' : ''}` : 'No scripts found yet.';
  $('paste-apply').disabled = !found.length;
});
$('paste-apply').addEventListener('click', () => {
  const found = splitPasted($('paste-text').value);
  const keep = S.scripts.filter((s) => s.text.trim());
  S.scripts = [...keep, ...found];
  $('paste-text').value = ''; $('paste-apply').disabled = true; $('paste-found').textContent = 'No scripts found yet.';
  setSmode('list'); renderScripts(); saveDraft(); updateSummary();
  toast(`Added ${plural(found.length, 'script')}.`, true);
});

// Import: each .txt/.md file is a script (title = file name); a .csv has columns text,title,voice,language.
function parseCSV(text) {
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cell); rows.push(row); row = []; cell = ''; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const head = (rows.shift() || []).map((h) => h.trim().toLowerCase());
  const col = (name) => head.indexOf(name);
  if (col('text') < 0 && col('script') < 0) throw new Error('The CSV needs a "text" column (and optionally title, voice, language).');
  const ti = col('text') >= 0 ? col('text') : col('script');
  return rows.filter((r) => (r[ti] || '').trim()).map((r) => {
    const s = { title: (r[col('title')] || '').trim(), text: r[ti].trim() };
    const v = (r[col('voice')] || '').trim(); if (v) s.voice = v;
    const l = (r[col('language')] || '').trim().toLowerCase(); if (l) s.language = l;
    return s;
  });
}
$('import-btn').addEventListener('click', () => $('import-file').click());
$('import-file').addEventListener('change', run(async (e) => {
  const added = [];
  for (const f of e.target.files) {
    const text = await f.text();
    if (/\.csv$/i.test(f.name)) added.push(...parseCSV(text));
    else added.push({ title: f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '), text: text.trim() });
  }
  e.target.value = '';
  S.scripts = [...S.scripts.filter((s) => s.text.trim()), ...added.filter((s) => s.text)];
  setSmode('list'); renderScripts(); saveDraft(); updateSummary();
  toast(`Imported ${plural(added.length, 'script')}.`, true);
}));

function fillCreateSelects() {
  const st = S.state; if (!st) return;
  const s = S.settings || {};
  const keepVoice = $('voice').value || s.default_voice || st.default_voice;
  $('voice').innerHTML = voiceOptions(keepVoice);
  const v = S.voices.find((x) => x.id === $('voice').value);
  const keepLang = $('language').dataset.touched ? $('language').value : (v?.language || st.default_language);
  $('language').innerHTML = languageOptions(keepLang);
  const keepModel = $('model').value || st.default_model;
  $('model').innerHTML = st.models.filter((m) => m.kind === 'voice').map((m) => `<option value="${m.key}"${m.key === keepModel ? ' selected' : ''}${m.installed ? '' : ' disabled'}>${esc(m.label)}${m.installed ? '' : ' (not downloaded)'}</option>`).join('');
  const m = st.models.find((x) => x.key === $('model').value);
  $('model-license').innerHTML = m ? licenseBadge(m) : '';
  $('voice-help').innerHTML = !S.voices.length ? 'Add a voice first: <a href="#voices">Voices → Add a voice</a> (a 6–15 second clip), or find a new one there.'
    : (v?.advice?.length ? `${icon('alert')} ${esc(v.advice[0])}` : '');
  if (!$('pause-paragraph').value) $('pause-paragraph').value = s.pause_paragraph ?? 0.7;
  if (!$('loudness').dataset.touched && s.loudness != null) {
    const val = String(Math.round(s.loudness));
    if ([...$('loudness').options].some((o) => o.value === val)) $('loudness').value = val;
  }
  if (!$('fmt-wav').dataset.touched && s.formats) { $('fmt-wav').checked = s.formats.includes('wav'); $('fmt-mp3').checked = s.formats.includes('mp3'); }
  if (!$('opt-srt').dataset.touched && s.subtitles != null) $('opt-srt').checked = s.subtitles;
}
$('voice').addEventListener('change', () => {
  const v = S.voices.find((x) => x.id === $('voice').value);
  if (v?.language && !$('language').dataset.touched) $('language').value = v.language;
  fillCreateSelects(); updateSummary();
});
$('language').addEventListener('change', () => { $('language').dataset.touched = '1'; });
['loudness', 'fmt-wav', 'fmt-mp3', 'opt-srt'].forEach((id) => $(id).addEventListener('change', () => { $(id).dataset.touched = '1'; }));
$('model').addEventListener('change', fillCreateSelects);

function licenseBadge(m) {
  return m.noncommercial ? `<span class="license nc">${icon('alert')} ${esc(m.license)}</span>` : `<span class="license ok">${icon('check')} ${esc(m.license)}</span>`;
}

function createSettings() {
  const formats = [$('fmt-wav').checked && 'wav', $('fmt-mp3').checked && 'mp3'].filter(Boolean);
  const out = { voice: $('voice').value, language: $('language').value, model: $('model').value,
                formats: formats.length ? formats : ['mp3'], subtitles: $('opt-srt').checked,
                loudness: Number($('loudness').value), pause_paragraph: Number($('pause-paragraph').value || 0.7) };
  if ($('seed').value !== '') out.seed = Number($('seed').value);
  return out;
}

let summaryTimer;
function updateSummary() {
  clearTimeout(summaryTimer);
  summaryTimer = setTimeout(async () => {
    const texts = S.cmode === 'single' ? [$('single-text').value] : S.scripts.map((s) => s.text);
    const filled = texts.filter((t) => t.trim());
    if (!filled.length) { $('summary').innerHTML = S.cmode === 'single' ? 'Type something to hear it.' : 'Add a script, paste several, or import files.'; return; }
    try {
      let segs = 0, est = 0;
      for (const t of filled) {
        const r = await api('/api/split-preview', { method: 'POST', json: { text: t, pause_paragraph: Number($('pause-paragraph').value || 0.7) } });
        segs += r.segments; est += r.estimate_s + r.pauses_s;
      }
      const speed = S.setupBench?.x_realtime || 2;
      const make = est / speed + filled.length * 3;
      $('summary').innerHTML = `${S.cmode === 'batch' ? `<b>${plural(filled.length, 'script')}</b> · ` : ''}<b>${plural(segs, 'part')}</b> · about <b>${fmtDur(est)}</b> of audio · ready in about <b>${fmtDur(make)}</b>${S.setupBench ? '' : ' (estimate; run the speed test in Setup for yours)'}`;
    } catch { /* server busy */ }
  }, 350);
}
$('single-text').addEventListener('input', () => { saveDraft(); updateSummary(); });
$('pause-paragraph').addEventListener('input', updateSummary);
$('batch-name').addEventListener('input', saveDraft);
$('single-text').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('go').click(); } });

$('go').addEventListener('click', run(async () => {
  if (!S.voices.length) { location.hash = '#voices'; throw new Error('Add a voice first (Voices page).'); }
  const settings = createSettings();
  $('go').disabled = true;
  try {
    if (S.cmode === 'single') {
      const text = $('single-text').value.trim();
      if (!text) throw new Error('Type the text to speak.');
      const r = await api('/api/singles', { method: 'POST', json: { text, settings } });
      S.single = { batch: r.batch.id, n: r.script.n };
      renderSingle();
    } else {
      const scripts = S.scripts.filter((s) => s.text.trim()).map((s) => ({ title: s.title || null, text: s.text, voice: s.voice || null, language: s.language || null }));
      if (!scripts.length) throw new Error('Add at least one script.');
      const b = await api('/api/batches', { method: 'POST', json: { name: $('batch-name').value.trim() || null, scripts, settings } });
      S.scripts = [{ title: '', text: '' }]; $('batch-name').value = ''; renderScripts(); saveDraft();
      toast(`Batch “${b.name}” started.`, true);
      location.hash = `#batch/${b.id}`;
    }
  } finally { $('go').disabled = false; }
}));

// The quick take's result card follows that single until it's done.
async function renderSingle() {
  if (!S.single) return;
  let d;
  try { d = await api(`/api/batches/${S.single.batch}`); } catch { return; }
  const s = d.scripts.find((x) => x.n === S.single.n);
  if (!s) return;
  $('single-empty').hidden = true; $('single-out').hidden = false;
  const out = s.output, v = out.finished || '';
  let html = `<div class="row between"><span class="micro">Quick take · ${esc(s.voice_name || '')} · ${esc(langName(s.language))}</span>${chip(s.status)}</div>
    <div class="take"><div class="text">${esc(s.text)}</div>`;
  if (s.status === 'done') {
    const main = out.files.mp3 || out.files.wav;
    html += `<audio controls autoplay src="${fileUrl(d.id, main, v)}"></audio>
      <div class="files">${Object.entries(out.files).map(([k, f]) => `<a class="btn sm" href="${fileUrl(d.id, f, v, 1)}" download>${icon('download')} ${k.toUpperCase()}</a>`).join('')}
      <button class="btn sm" data-single="again">${icon('dice')} Another take</button>
      <a class="btn sm" href="#batch/${d.id}">Open in Batches</a></div>
      <span class="micro">${fmtDur(out.seconds)} · ${out.match != null ? `Whisper heard ${Math.round(out.match * 100)}% of the words` : ''}</span>`;
  } else if (s.status === 'failed') {
    const it = d.items.find((x) => x.script === s.n && x.error);
    html += `<p class="err-note">${esc(it?.error || out.error || 'Something went wrong.')}</p><a class="btn sm" href="#batch/${d.id}">Open to retry</a>`;
  } else {
    const done = s.done, total = s.segments;
    html += `<div class="progress live"><div style="width:${Math.max(6, 100 * done / Math.max(1, total))}%"></div></div><span class="micro">${s.status === 'finishing' ? 'Writing the files…' : `Part ${Math.min(done + 1, total)} of ${total}…`}</span>`;
  }
  setHtml($('single-out'), html + '</div>');
  if (isBusy(s.status) || s.status === 'queued') setTimeout(renderSingle, 1200);
}
$('single-out').addEventListener('click', run(async (e) => {
  if (!e.target.closest('[data-single="again"]')) return;
  $('seed').value = '';
  $('go').click();
}));

async function renderQueue() {
  if (S.view !== 'create') return;
  try { S.batches = await api('/api/batches'); } catch { return; }
  const order = S.state?.queue || [];
  const active = S.batches.filter((b) => order.includes(b.id)).sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  const recent = S.batches.filter((b) => !order.includes(b.id)).slice(0, 4);
  const row = (b, i) => `<div class="qitem">
      ${chip(b.status)}
      <a class="name" href="#batch/${b.id}">${esc(b.name)}</a>
      <span class="sub">${b.kind === 'singles' ? '' : `${b.scripts_done}/${b.scripts_total} scripts · `}${b.done}/${b.total} parts${b.eta_seconds ? ` · ~${fmtDur(b.eta_seconds)} left` : ''}</span>
      ${order.includes(b.id) ? `<button class="icon-btn" data-q="up" data-id="${b.id}" ${i === 0 ? 'disabled' : ''} aria-label="Move up">${icon('up')}</button>
      <button class="icon-btn" data-q="${b.paused ? 'resume' : 'pause'}" data-id="${b.id}" aria-label="${b.paused ? 'Resume' : 'Pause'}">${icon(b.paused ? 'play' : 'pause')}</button>` : ''}
    </div>`;
  setHtml($('queue-list'), (active.length ? active.map(row).join('') : '<p class="help">Nothing waiting. New batches start right away.</p>')
    + (recent.length ? `<div class="micro" style="margin-top:12px">Recent</div>${recent.map(row).join('')}` : ''));
}
$('queue-list').addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-q]'); if (!b) return;
  const id = b.dataset.id;
  if (b.dataset.q === 'up') {
    const order = [...(S.state?.queue || [])];
    const i = order.indexOf(id); if (i > 0) { [order[i - 1], order[i]] = [order[i], order[i - 1]]; await api('/api/queue/order', { method: 'POST', json: { ids: order } }); }
  } else await api(`/api/batches/${id}/${b.dataset.q}`, { method: 'POST' });
  await pollState(); renderQueue();
}));

async function showCreate() {
  await loadVoicesList();
  fillCreateSelects(); renderScripts(); updateSummary(); renderQueue();
  if (S.single) renderSingle();
}

// ---------- BATCHES ----------
S.selecting = false;
S.selected = new Set();
async function loadBatches() {
  try { S.batches = await api('/api/batches'); } catch (e) { toast(e.message); return; }
  renderBatches();
}
function renderBatches() {
  const q = $('batch-search').value.trim().toLowerCase();
  const shown = S.batches.filter((b) => !q || b.name.toLowerCase().includes(q) || b.first_text.toLowerCase().includes(q));
  S.shown = shown;
  const html = shown.length ? shown.map((b) => `
    <div class="card bcard${S.selecting ? ' selectable' : ''}${S.selected.has(b.id) ? ' picked' : ''}" data-id="${b.id}">
      ${S.selecting ? `<input type="checkbox" ${S.selected.has(b.id) ? 'checked' : ''} ${isBusy(b.status) ? 'disabled' : ''} aria-label="Select">` : ''}
      <div class="main">
        <div class="row" style="gap:10px;min-width:0">${chip(b.status)}<a class="name" href="#batch/${b.id}">${esc(b.name)}</a></div>
        <div class="first">${esc(b.first_text)}</div>
        <div class="meta"><span>${fmtWhen(b.created)}</span>
          <span>${b.kind === 'singles' ? plural(b.scripts_total, 'quick take') : plural(b.scripts_total, 'script')}</span>
          ${b.audio_seconds ? `<span>${fmtDur(b.audio_seconds)} of audio</span>` : ''}
          ${isBusy(b.status) ? `<span>${b.done}/${b.total} parts${b.eta_seconds ? ` · ~${fmtDur(b.eta_seconds)} left` : ''}</span>` : ''}
          ${b.checks ? `<span style="color:var(--warn)">${plural(b.checks, 'part')} to check</span>` : ''}
          ${b.failed ? `<span style="color:var(--red-hi)">${b.failed} failed</span>` : ''}</div>
      </div>
      ${S.selecting ? '' : `<div class="acts">
        <a class="btn sm" href="#batch/${b.id}">View</a>
        <button class="btn sm" data-b="open" data-id="${b.id}">${icon('folder')} Folder</button>
        ${b.scripts_done ? `<a class="btn sm" href="/api/batches/${b.id}/export.zip?content=final">${icon('download')} ZIP</a>` : ''}
        <button class="btn sm" data-b="rerun" data-id="${b.id}">${icon('refresh')} Re-run</button>
        <button class="icon-btn" data-b="delete" data-id="${b.id}" aria-label="Delete">${icon('trash')}</button></div>`}
    </div>`).join('') : `<div class="card empty">${q ? 'No batch matches that search.' : 'No batches yet. Make one on the Create page.'}</div>`;
  setHtml($('batch-list'), html);
  $('bulkbar').hidden = !S.selecting;
  $('bulk-count').textContent = `${S.selected.size} selected`;
  $('bulk-delete').disabled = !S.selected.size;
}
$('batch-search').addEventListener('input', renderBatches);
$('select-toggle').addEventListener('click', () => {
  S.selecting = !S.selecting; S.selected.clear();
  $('select-toggle').textContent = S.selecting ? 'Cancel' : 'Select';
  $('select-toggle').setAttribute('aria-pressed', S.selecting);
  $('batch-list')._html = ''; renderBatches();
});
$('select-all').addEventListener('click', () => { S.shown.filter((b) => !isBusy(b.status)).forEach((b) => S.selected.add(b.id)); $('batch-list')._html = ''; renderBatches(); });
$('bulk-delete').addEventListener('click', run(async () => {
  const n = S.selected.size;
  if (!await confirmDialog(`Delete ${plural(n, 'batch', 'batches')}?`, 'Their folders go to the Recycle Bin, so you can restore them from there.')) return;
  const r = await api('/api/batches-delete', { method: 'POST', json: { ids: [...S.selected] } });
  toast(`Deleted ${plural(r.deleted.length, 'batch', 'batches')}${r.skipped.length ? `; ${r.skipped.length} skipped (still working or in use)` : ''}.`, !r.skipped.length);
  S.selecting = false; S.selected.clear(); $('select-toggle').textContent = 'Select';
  loadBatches();
}));
$('batch-list').addEventListener('click', run(async (e) => {
  const card = e.target.closest('.bcard');
  if (S.selecting && card) {
    e.preventDefault();
    const b = S.batches.find((x) => x.id === card.dataset.id);
    if (!b || isBusy(b.status)) return;
    S.selected.has(b.id) ? S.selected.delete(b.id) : S.selected.add(b.id);
    $('batch-list')._html = ''; renderBatches(); return;
  }
  const btn = e.target.closest('[data-b]'); if (!btn) return;
  await batchAction(btn.dataset.id, btn.dataset.b);
  loadBatches();
}));

async function batchAction(id, act) {
  const b = S.batches.find((x) => x.id === id) || S.detail;
  if (act === 'delete') {
    if (!await confirmDialog(`Delete “${b?.name}”?`, 'The folder goes to the Recycle Bin, so you can restore it from there.')) return;
    await api(`/api/batches/${id}`, { method: 'DELETE' });
    toast('Moved to the Recycle Bin.', true);
    if (S.view === 'batch') location.hash = '#batches';
    return;
  }
  if (act === 'cancel' && !await confirmDialog('Stop this batch?', 'Parts not spoken yet are cancelled. Finished scripts are kept; you can Retry later.', 'Stop')) return;
  const r = await api(`/api/batches/${id}/${act}`, { method: 'POST' });
  if (act === 'rerun') { toast(`Re-running as “${r.name}”.`, true); location.hash = `#batch/${r.id}`; }
}

// ---------- ONE BATCH ----------
S.open = new Set();    // scripts whose parts the user opened
S.closed = new Set();  // ... or closed
async function loadDetail() {
  if (!S.arg) return;
  try { S.detail = await api(`/api/batches/${encodeURIComponent(S.arg)}`); } catch (e) { toast(e.message); location.hash = '#batches'; return; }
  if (!S.voices.length) await loadVoicesList();
  renderDetail();
}
function segRow(d, it) {
  const cur = S.state?.current;
  const running = cur && cur.batch === d.id && cur.item === it.id;
  return `<div class="seg-row${it.check ? ' flag' : ''}${running ? ' running' : ''}" data-item="${it.id}">
    <span class="k">${it.k}</span>
    <div><div class="txt">${esc(it.text)}</div>
      <div class="sub">${chip(running ? 'running' : it.status)}${it.audio_s ? `<span>${it.audio_s.toFixed(1)} s</span>` : ''}${it.duration ? `<span>made in ${it.duration.toFixed(1)} s</span>` : ''}<span>seed ${it.seed}</span>${it.pause_after ? `<span>then ${it.pause_after} s pause</span>` : ''}</div>
      ${it.check ? `<div class="flag-note">${icon('alert')} ${esc(it.check)}</div>` : ''}
      ${it.error ? `<div class="err-note">${esc(it.error)}</div>` : ''}</div>
    <div class="tools">${it.status === 'done' ? `<audio controls preload="metadata" src="${fileUrl(d.id, it.file, it.finished)}"></audio>` : ''}
      <div class="row" style="gap:6px">
        <button class="btn xs" data-seg="regen" ${running ? 'disabled' : ''} title="Speak this part again with a new seed">${icon('dice')} New take</button>
        <button class="btn xs" data-seg="edit" ${running ? 'disabled' : ''}>${icon('pencil')} Edit</button>
        ${['failed', 'cancelled'].includes(it.status) ? '<button class="btn xs accent" data-seg="retry">Retry</button>' : ''}</div></div>
  </div>`;
}
function renderDetail() {
  const d = S.detail; if (!d) return;
  $('b-name').textContent = d.name;
  const st = d.settings;
  $('b-meta').innerHTML = `${chip(d.status)} &nbsp;${fmtWhen(d.created)} · ${d.kind === 'singles' ? plural(d.scripts_total, 'quick take') : plural(d.scripts_total, 'script')} · ${d.done}/${d.total} parts`
    + `${d.audio_seconds ? ` · ${fmtDur(d.audio_seconds)} of audio` : ''}${d.eta_seconds ? ` · about ${fmtDur(d.eta_seconds)} left` : ''}`
    + (d.kind === 'singles' ? '' : ` · ${esc(voiceName(st.voice))} · ${esc(langName(st.language))} · seed ${st.seed}`);
  const busy = isBusy(d.status);
  setHtml($('b-actions'), [
    busy && !d.paused ? `<button class="btn sm" data-d="pause">${icon('pause')} Pause</button>` : '',
    d.paused ? `<button class="btn sm accent" data-d="resume">${icon('play')} Resume</button>` : '',
    busy || d.paused ? `<button class="btn sm" data-d="cancel">${icon('stop')} Stop</button>` : '',
    d.failed || d.cancelled ? `<button class="btn sm accent" data-d="retry">${icon('refresh')} Retry</button>` : '',
    d.scripts_done ? `<a class="btn sm" href="/api/batches/${d.id}/export.zip?content=final">${icon('download')} ZIP</a><a class="btn sm" href="/api/batches/${d.id}/export.zip?content=both" title="Finished files plus every part">${icon('download')} ZIP + parts</a>` : '',
    `<button class="btn sm" data-d="open">${icon('folder')} Folder</button>`,
    `<button class="btn sm" data-d="rerun">${icon('refresh')} Re-run</button>`,
    busy ? '' : `<button class="icon-btn" data-d="delete" aria-label="Delete batch">${icon('trash')}</button>`,
  ].join(''));
  const prog = $('b-progress');
  prog.className = `progress${busy ? ' live' : ''}`;
  prog.firstElementChild.style.width = `${100 * d.done / Math.max(1, d.total)}%`;
  const html = d.scripts.map((s) => {
    const items = d.items.filter((it) => it.script === s.n);
    const out = s.output, v = out.finished || '';
    const main = out.files?.mp3 || out.files?.wav;
    const open = S.open.has(s.n) || (!S.closed.has(s.n) && (d.scripts.length === 1 || s.checks || s.failed));
    return `<section class="card scard" data-n="${s.n}">
      <div class="top">${chip(s.status)}<span class="title">${esc(s.title)}</span><span class="stem">${esc(s.stem)}</span>
        <button class="btn xs" data-s="edit">${icon('pencil')} Edit script</button>
        ${s.status === 'done' ? `<button class="btn xs" data-s="refinish" title="Rebuild the WAV/MP3/SRT from the parts (after changing loudness or formats in Settings)">${icon('refresh')} Rebuild files</button>` : ''}
        ${d.scripts.length > 1 ? `<button class="icon-btn" data-s="delete" aria-label="Delete script">${icon('trash')}</button>` : ''}</div>
      <div class="info"><span>${esc(s.voice_name || voiceName(s.voice))}</span><span>${esc(langName(s.language))}</span>
        <span>${plural(s.segments, 'part')}</span><span>${s.chars.toLocaleString()} characters</span>
        ${out.seconds ? `<span>${fmtClock(out.seconds)} long</span>` : `<span>about ${fmtDur(s.estimate_s)}</span>`}
        ${out.lufs_before != null ? `<span>levelled to ${st.loudness ?? -16} LUFS</span>` : ''}
        ${out.match != null ? `<span title="Share of the script's words Whisper recognised in the audio">Whisper heard ${Math.round(out.match * 100)}%</span>` : ''}
        ${s.checks ? `<span style="color:var(--warn)">${plural(s.checks, 'part')} to check</span>` : ''}</div>
      ${s.status === 'done' && main ? `<div class="player"><audio controls preload="metadata" src="${fileUrl(d.id, main, v)}"></audio>
        <div class="files">${Object.entries(out.files).map(([k, f]) => `<a class="btn sm" href="${fileUrl(d.id, f, v, 1)}" download>${icon('download')} ${k.toUpperCase()}</a>`).join('')}</div></div>` : ''}
      ${out.status === 'failed' ? `<p class="err-note">Writing the files failed: ${esc(out.error)}</p>` : ''}
      <details class="segs" ${open ? 'open' : ''} data-n="${s.n}"><summary>Parts (${s.done}/${s.segments})</summary>
        ${items.map((it) => segRow(d, it)).join('')}
      </details></section>`;
  }).join('');
  setHtml($('b-scripts'), html);
}
$('b-scripts').addEventListener('toggle', (e) => {
  const det = e.target.closest?.('details.segs'); if (!det) return;
  const n = Number(det.dataset.n);
  if (det.open) { S.open.add(n); S.closed.delete(n); } else { S.open.delete(n); S.closed.add(n); }
}, true);
$('b-actions').addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-d]'); if (!b) return;
  await batchAction(S.detail.id, b.dataset.d);
  if (S.view === 'batch') loadDetail();
}));
$('b-rename').addEventListener('click', run(async () => {
  const r = await editDialog({ title: 'Rename batch', help: 'The folder on disk is renamed too.', name: S.detail.name, nameLabel: 'Name', ok: 'Rename' });
  if (!r || !r.name.trim() || r.name.trim() === S.detail.name) return;
  await api(`/api/batches/${S.detail.id}`, { method: 'PATCH', json: { name: r.name.trim() } });
  toast('Renamed.', true); loadDetail();
}));
$('b-scripts').addEventListener('click', run(async (e) => {
  const d = S.detail;
  const sb = e.target.closest('[data-s]');
  if (sb) {
    const n = Number(sb.closest('.scard').dataset.n);
    const s = d.scripts.find((x) => x.n === n);
    if (sb.dataset.s === 'edit') {
      const r = await editDialog({
        title: `Edit script ${n}`, help: 'Only the parts whose text changed are spoken again; the rest keep their audio.',
        name: s.title, text: s.text,
        extra: `<div class="pair"><div class="field"><label class="label">Voice</label><div class="select-wrap"><select class="select" name="voice">${voiceOptions(s.voice)}</select>${icon('chevron')}</div></div>
          <div class="field" style="flex:0 0 160px"><label class="label">Language</label><div class="select-wrap"><select class="select" name="language">${languageOptions(s.language)}</select>${icon('chevron')}</div></div></div>
          <p class="help">Changing the voice or language speaks the whole script again.</p>`,
      });
      if (!r) return;
      const body = {};
      if (r.text !== s.text) body.text = r.text;
      if (r.name !== s.title) body.title = r.name;
      if (r.voice !== s.voice) body.voice = r.voice;
      if (r.language !== s.language) body.language = r.language;
      if (!Object.keys(body).length) return;
      S.detail = await api(`/api/batches/${d.id}/scripts/${n}`, { method: 'PATCH', json: body });
      toast('Saved. Changed parts are queued.', true);
    } else if (sb.dataset.s === 'refinish') {
      S.detail = await api(`/api/batches/${d.id}/scripts/${n}/refinish`, { method: 'POST' });
      toast('Rebuilding the files…', true);
    } else if (sb.dataset.s === 'delete') {
      if (!await confirmDialog(`Delete script ${n}?`, 'Its finished files go to the Recycle Bin.')) return;
      S.detail = await api(`/api/batches/${d.id}/scripts/${n}`, { method: 'DELETE' });
    }
    $('b-scripts')._html = ''; renderDetail(); return;
  }
  const gb = e.target.closest('[data-seg]'); if (!gb) return;
  const id = gb.closest('.seg-row').dataset.item;
  const it = d.items.find((x) => x.id === id);
  if (gb.dataset.seg === 'regen') S.detail = await api(`/api/batches/${d.id}/segments/${id}/regenerate`, { method: 'POST', json: { new_seed: true } });
  else if (gb.dataset.seg === 'retry') S.detail = await api(`/api/batches/${d.id}/segments/${id}/retry`, { method: 'POST' });
  else if (gb.dataset.seg === 'edit') {
    const r = await editDialog({ title: `Edit part ${it.k}`, help: 'Fix a word, spell a name the way it sounds, or add punctuation for a pause. This part is spoken again.', text: it.text, rows: 6, ok: 'Save and speak again' });
    if (!r || r.text.trim() === it.text) return;
    S.detail = await api(`/api/batches/${d.id}/segments/${id}`, { method: 'PATCH', json: { text: r.text } });
  }
  $('b-scripts')._html = ''; renderDetail();
}));

// ---------- VOICES ----------
async function loadVoicesList() {
  try { S.voices = await api('/api/voices'); } catch { /* keep the old list */ }
}
async function loadVoices() {
  await loadVoicesList();
  if (!S.settings) S.settings = await api('/api/settings');
  const lang = $('voice-lang').value || S.state?.default_language || 'en';
  $('voice-lang').innerHTML = languageOptions(lang);
  $('find-lang').innerHTML = languageOptions($('find-lang').value || lang);
  renderVoiceCards();
}
function renderVoiceCards() {
  const def = S.settings?.default_voice;
  const html = S.voices.length ? S.voices.map((v) => `
    <section class="card vcard${v.id === def ? ' default' : ''}" data-id="${esc(v.id)}">
      <div class="top"><span class="name">${esc(v.name)}</span>${v.id === def ? '<span class="chip accent">Default</span>' : ''}${v.source === 'found' ? '<span class="chip">Found</span>' : ''}</div>
      <div class="meta"><span>${esc(langName(v.language))}</span><span>${v.seconds} s clip</span>${v.denoised ? '<span>noise reduced</span>' : ''}<span>${fmtWhen(v.created)}</span></div>
      ${v.notes ? `<div class="notes">${esc(v.notes)}</div>` : ''}
      <audio controls preload="metadata" src="/api/voices/${encodeURIComponent(v.id)}/clip?v=${encodeURIComponent(v.seconds + '-' + v.denoised)}"></audio>
      ${v.advice?.length ? `<ul class="tips">${v.advice.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>` : ''}
      <div class="preview-slot"></div>
      <div class="acts">
        <button class="btn sm accent" data-v="preview">${icon('speaker')} Hear it speak</button>
        <button class="btn sm" data-v="edit">${icon('pencil')} Edit</button>
        ${v.id === def ? '' : `<button class="btn sm" data-v="default">${icon('star')} Make default</button>`}
        <button class="icon-btn" data-v="delete" aria-label="Delete voice">${icon('trash')}</button>
      </div>
    </section>`).join('') : '<div class="card empty" style="grid-column:1/-1">No voices yet. Add a clip above, or find a new voice.</div>';
  setHtml($('voice-cards'), html);
}

// Adding a voice from a file
S.voiceFile = null;
function setVoiceFile(f) {
  S.voiceFile = f;
  $('voice-drop-text').innerHTML = f ? `<b>${esc(f.name)}</b><br><small>${fmtSize(f.size)} · click to choose another</small>` : 'Drop an audio file here, or click to choose';
  const p = $('voice-file-preview');
  if (f) { p.src = URL.createObjectURL(f); p.hidden = false; } else p.hidden = true;
  if (f && !$('voice-name').value) $('voice-name').value = f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').slice(0, 60);
  checkVoiceForm();
}
function checkVoiceForm() { $('voice-add').disabled = !(S.voiceFile && $('voice-name').value.trim() && $('voice-consent').checked); }
$('voice-file').addEventListener('change', (e) => setVoiceFile(e.target.files[0] || null));
['voice-name', 'voice-consent'].forEach((id) => $(id).addEventListener('input', checkVoiceForm));
$('voice-consent').addEventListener('change', checkVoiceForm);
const drop = $('voice-drop');
['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('over')));
drop.addEventListener('drop', (e) => { e.preventDefault(); if (e.dataTransfer.files[0]) setVoiceFile(e.dataTransfer.files[0]); });
$('voice-add').addEventListener('click', run(async () => {
  const form = new FormData();
  form.append('file', S.voiceFile); form.append('name', $('voice-name').value.trim());
  form.append('language', $('voice-lang').value); form.append('notes', $('voice-notes').value);
  form.append('denoise', $('voice-denoise').checked ? '1' : '0');
  $('voice-add').disabled = true; $('voice-add').textContent = 'Preparing the clip…';
  try {
    const v = await api('/api/voices', { method: 'POST', form });
    toast(`Added “${v.name}” (${v.seconds} s clip).${v.advice?.length ? ' ' + v.advice[0] : ''}`, !v.advice?.length);
    setVoiceFile(null); $('voice-file').value = ''; $('voice-name').value = ''; $('voice-notes').value = ''; $('voice-consent').checked = false;
    S.settings = await api('/api/settings');
    await loadVoices();
  } finally { $('voice-add').textContent = 'Add voice'; checkVoiceForm(); }
}));

$('voice-cards').addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-v]'); if (!b) return;
  const card = b.closest('.vcard'), id = card.dataset.id;
  const v = S.voices.find((x) => x.id === id);
  if (b.dataset.v === 'preview') {
    b.disabled = true; b.innerHTML = `${icon('speaker')} Speaking…`;
    try {
      const r = await api(`/api/voices/${encodeURIComponent(id)}/preview`, { method: 'POST', json: {}, raw: true });
      const url = URL.createObjectURL(await r.blob());
      card.querySelector('.preview-slot').innerHTML = `<div class="micro">Sample · ${esc(langName(v.language))}</div><audio controls autoplay src="${url}"></audio>`;
    } finally { b.disabled = false; b.innerHTML = `${icon('speaker')} Hear it speak`; }
  } else if (b.dataset.v === 'default') {
    S.settings = await api('/api/settings', { method: 'PUT', json: { default_voice: id } });
    $('voice-cards')._html = ''; renderVoiceCards(); toast(`“${v.name}” is now the default voice.`, true);
  } else if (b.dataset.v === 'delete') {
    if (!await confirmDialog(`Delete “${v.name}”?`, 'Its folder (clip and original file) goes to the Recycle Bin. Finished audio made with it is kept.')) return;
    await api(`/api/voices/${encodeURIComponent(id)}`, { method: 'DELETE' });
    S.settings = await api('/api/settings'); await loadVoices();
  } else if (b.dataset.v === 'edit') {
    const r = await editDialog({
      title: `Edit “${v.name}”`, name: v.name, nameLabel: 'Name', text: null, ok: 'Save',
      extra: `<div class="pair"><div class="field"><label class="label">Language</label><div class="select-wrap"><select class="select" name="language">${languageOptions(v.language)}</select>${icon('chevron')}</div></div></div>
        <div class="field"><label class="label">Notes</label><input class="input" name="notes" value="${esc(v.notes || '')}"></div>
        <hr style="border:0;border-top:1px solid var(--line);width:100%">
        <p class="help">Prepare the clip again from the original file (${v.trimmed_from ?? v.seconds} s):</p>
        <label class="check"><input type="checkbox" name="denoise" ${v.denoised ? 'checked' : ''}> Reduce background noise</label>
        <div class="pair"><div class="field"><label class="label">Use from (seconds)</label><input class="input mono" name="start" type="number" min="0" step="0.1" value="${v.range?.[0] ?? ''}" placeholder="start"></div>
          <div class="field"><label class="label">to (seconds)</label><input class="input mono" name="end" type="number" min="0" step="0.1" value="${v.range?.[1] ?? ''}" placeholder="end"></div></div>
        <p class="help">Pick the cleanest 6–15 seconds of one person talking. Longer clips are cut at a pause after 20 seconds.</p>`,
    });
    if (!r) return;
    await api(`/api/voices/${encodeURIComponent(id)}`, { method: 'PATCH', json: { name: r.name, language: r.language, notes: r.notes } });
    const range = [r.start === '' ? null : Number(r.start), r.end === '' ? null : Number(r.end)];
    if (r.denoise !== !!v.denoised || String(range) !== String(v.range || [null, null])) {
      await api(`/api/voices/${encodeURIComponent(id)}/prepare`, { method: 'POST', json: { denoise: r.denoise, start: range[0], end: range[1] } });
    }
    await loadVoices(); toast('Saved.', true);
  }
}));

// Find a voice: random new voices to keep
$('find-go').addEventListener('click', run(async () => {
  const n = Number($('find-count').value);
  $('find-go').disabled = true; $('find-go').innerHTML = `${icon('sparkle')} Finding ${n} voices… (about ${n * 8} s)`;
  try {
    const found = await api('/api/voices/find', { method: 'POST', json: { language: $('find-lang').value, count: n } });
    $('found-list').innerHTML = found.map((f, i) => `
      <div class="found-item" data-token="${f.token}" data-lang="${f.language}">
        <div class="row between"><span class="micro">Voice ${i + 1} · ${esc(langName(f.language))}</span></div>
        <audio controls src="/api/found/${f.token}"></audio>
        <div class="row" style="gap:8px"><input class="input" placeholder="Name it to keep it" maxlength="60" style="height:34px"><button class="btn sm accent" data-keep>Keep</button></div>
      </div>`).join('');
  } finally { $('find-go').disabled = false; $('find-go').innerHTML = `${icon('sparkle')} Find voices`; }
}));
$('found-list').addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-keep]'); if (!b) return;
  const item = b.closest('.found-item'), name = item.querySelector('input').value.trim();
  if (!name) { item.querySelector('input').focus(); throw new Error('Give the voice a name first.'); }
  const v = await api('/api/voices/keep', { method: 'POST', json: { token: item.dataset.token, name, language: item.dataset.lang } });
  item.innerHTML = `<span class="chip ok">${icon('check')} Kept as “${esc(v.name)}”</span>`;
  S.settings = await api('/api/settings'); await loadVoices();
}));

// ---------- MODELS ----------
async function loadModels() {
  let models;
  try { models = await api('/api/models'); } catch (e) { toast(e.message); return; }
  const group = (kind, title, help) => `<div class="group-title">${title}</div><p class="help" style="margin:-6px 0 12px">${help}</p>`
    + models.filter((m) => m.kind === kind).map(modelCard).join('');
  setHtml($('models-list'), group('voice', 'Voice models', 'Speak your scripts. Each runs on the engine chosen on the Setup page.')
    + group('subtitles', 'Subtitles and transcripts', 'Time the SRT subtitles of every finished script, and power the transcription API. Run on the CPU; the small one is plenty for subtitles.'));
  if (models.some((m) => m.job && ['downloading', 'checking', 'installing'].includes(m.job.status))) setTimeout(() => S.view === 'models' && loadModels(), 1000);
}
function dlBox(job, total, partial, kind, key) {
  if (job && ['downloading', 'checking', 'installing'].includes(job.status)) {
    const pct = job.total ? Math.min(100, 100 * job.done / job.total) : 0;
    const label = job.status === 'checking' ? 'Checking the download…' : job.status === 'installing' ? 'Installing…' : `${fmtSize(job.done)} of ${fmtSize(job.total)}`;
    return `<div class="dl"><div class="progress live"><div style="width:${pct}%"></div></div><div class="row between"><span class="micro">${label}</span><button class="text-btn red" data-${kind}="cancel" data-key="${key}">Pause</button></div></div>`;
  }
  return '';
}
function modelCard(m) {
  const busy = m.job && ['downloading', 'checking', 'installing'].includes(m.job.status);
  let acts;
  if (busy) acts = dlBox(m.job, m.to_download, m.partial, 'm', m.key);
  else if (m.installed && m.kind === 'subtitles') acts = (m.in_use ? `<span class="chip ok">${icon('check')} In use</span>`
    : `<span class="chip">Downloaded</span><button class="btn sm accent" data-m="use" data-key="${m.key}">Use this one</button>`)
    + `<button class="btn sm" data-m="remove" data-key="${m.key}">Remove</button>`;
  else if (m.installed) acts = `<span class="chip ok">${icon('check')} Downloaded</span><button class="btn sm" data-m="remove" data-key="${m.key}">Remove</button>`;
  else if (m.partial) acts = `<button class="btn sm accent" data-m="download" data-key="${m.key}">${icon('download')} Resume (${fmtSize(m.partial)} done)</button><button class="text-btn red" data-m="discard" data-key="${m.key}">Discard</button>`;
  else acts = `<button class="btn sm accent" data-m="download" data-key="${m.key}">${icon('download')} Download ${fmtSize(m.to_download)}</button>`;
  return `<div class="card mcard"><div class="main">
      <div class="name">${esc(m.label)} ${licenseBadge(m)}${m.default ? '<span class="chip accent">Default</span>' : ''}${m.recommended && !m.installed ? '<span class="chip dark">Recommended</span>' : ''}</div>
      <div class="about">${esc(m.about)}</div>
      <div class="meta"><span>${fmtSize(m.size)}</span>${m.shared?.length ? `<span>shares ${plural(m.shared.length, 'file')} with other models (downloaded once)</span>` : ''}<a href="${esc(m.page)}" target="_blank" rel="noopener">Model page ↗</a>${m.fit && m.fit !== 'fits' && m.fit !== 'cpu' ? `<span style="color:var(--warn)">${m.fit === 'tight' ? 'tight fit for your GPU' : 'too big for your GPU'}</span>` : ''}</div>
      ${m.job?.status === 'failed' ? `<div class="err-note">${esc(m.job.error)}</div>` : ''}
    </div><div class="acts">${acts}</div></div>`;
}
document.addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-m]'); if (!b) return;
  const key = b.dataset.key, act = b.dataset.m;
  if (act === 'download') await api(`/api/models/${key}/download`, { method: 'POST' });
  else if (act === 'cancel') await api(`/api/models/${key}/cancel`, { method: 'POST' });
  else if (act === 'discard') { if (!await confirmDialog('Discard the paused download?', 'The part already downloaded is deleted.', 'Discard')) return; await api(`/api/models/${key}/partial`, { method: 'DELETE' }); }
  else if (act === 'use') { S.settings = await api('/api/settings', { method: 'PUT', json: { subtitles_model: key } }); toast('Subtitles and transcripts now use this model.', true); }
  else if (act === 'remove') { if (!await confirmDialog('Remove this model?', 'Its files are deleted from this PC. You can download it again any time.', 'Remove')) return; await api(`/api/models/${key}`, { method: 'DELETE' }); }
  setTimeout(() => (S.view === 'setup' ? loadSetup() : loadModels()), 300);
}));

// ---------- SETUP ----------
async function loadSetup(refresh = false) {
  let s;
  try { s = await api(`/api/setup${refresh ? '?refresh=1' : ''}`); } catch (e) { toast(e.message); return; }
  S.setupBench = s.benchmark;
  const hw = s.hardware, g = s.gpu;
  const locked = document.body.classList.contains('locked');
  $('setup-lede').textContent = locked ? 'Welcome! Two downloads and you\'re ready: the engine that runs the voices, and a voice model. The ones that suit this PC are marked Recommended.'
    : 'What this PC has, and the engine and models that suit it.';
  const stepHead = (n, done, title, text) => `<div class="step${done ? ' done' : ''}"><span class="n">${done ? '✓' : n}</span><div><h2>${title}</h2><p>${text}</p></div></div>`;
  const engines = s.engines.map((e) => {
    const busy = e.job && ['downloading', 'checking', 'installing'].includes(e.job.status);
    let acts;
    if (busy) acts = dlBox(e.job, e.size, e.partial, 'e', e.key);
    else if (e.active) acts = `<span class="chip ok">${icon('check')} In use</span>`;
    else if (e.installed) acts = `<button class="btn sm accent" data-e="use" data-key="${e.key}">Use this one</button><button class="btn sm" data-e="remove" data-key="${e.key}">Remove</button>`;
    else if (e.partial) acts = `<button class="btn sm accent" data-e="download" data-key="${e.key}">Resume (${fmtSize(e.partial)} done)</button><button class="text-btn red" data-e="discard" data-key="${e.key}">Discard</button>`;
    else acts = `<button class="btn sm ${e.recommended ? 'accent' : ''}" data-e="download" data-key="${e.key}">${icon('download')} Download ${fmtSize(e.size)}</button>`;
    return `<div class="card mcard"><div class="main"><div class="name">${esc(e.label)}${e.recommended ? '<span class="chip dark">Recommended</span>' : ''}</div>
      <div class="about">${esc(e.about)}</div>${e.job?.status === 'failed' ? `<div class="err-note">${esc(e.job.error)}</div>` : ''}</div><div class="acts">${acts}</div></div>`;
  }).join('');
  const voiceModels = s.models.filter((m) => m.kind === 'voice').map(modelCard).join('');
  const subModels = s.models.filter((m) => m.kind === 'subtitles').map(modelCard).join('');
  const b = s.benchmark;
  const html = `
    <div class="card hw">
      <div><div class="k">Graphics card</div><div class="v">${esc(g ? g.name : 'None found')}</div><small>${g ? `${g.vram_gb} GB${g.driver ? ` · driver ${esc(g.driver)}` : ''}` : 'Speech runs on the CPU'}</small></div>
      <div><div class="k">Memory</div><div class="v">${hw.ram_gb} GB RAM</div></div>
      <div><div class="k">Processor</div><div class="v">${esc(hw.cpu)}</div><small>${hw.cores} threads</small></div>
      <div><div class="k">Free disk (models)</div><div class="v">${s.disk_free != null ? fmtSize(s.disk_free) : '—'}</div></div>
    </div>
    ${s.warnings.map((w) => `<div class="warn-box ${w.level}">${icon('alert')}<span>${esc(w.message)}</span></div>`).join('')}
    ${stepHead(1, s.steps.engine, 'Engine', `llama.cpp ${esc(s.engine_release)}, the official build. Pick the one for your graphics card.`)}
    ${engines}
    ${stepHead(2, s.steps.model, 'Voice model', 'Speaks your scripts. Both versions are free for commercial use.')}
    ${voiceModels}
    ${stepHead(3, s.steps.subtitles, 'Subtitles <span class="opt" style="font-weight:400;font-size:14px;color:var(--muted)">— recommended</span>', 'Times the SRT subtitles for your videos, on the CPU. Small is plenty for subtitles; the bigger ones are more accurate for transcribing other audio.')}
    ${subModels}
    ${stepHead(4, s.steps.voice, 'A voice', s.steps.voice ? 'You have voices in your library.' : 'Add a 6–15 second clip of a voice, or find a new one.')}
    ${s.ready ? `<a class="btn ${s.steps.voice ? '' : 'accent'}" href="#voices">${icon('users')} Open Voices</a>` : '<p class="help">Available once the engine and a voice model are downloaded.</p>'}
    ${stepHead(5, s.steps.benchmark, 'Speed test', 'Speaks a short paragraph to measure how fast this PC is.')}
    <div class="card bench">${b ? `<div><div class="big">${b.x_realtime}×</div><small>faster than real time</small></div>
      <div class="kv"><span class="k">Paragraph</span><span>${b.audio_s} s of speech in ${b.took_s} s</span><span class="k">Engine</span><span>${esc(b.engine)} · ${esc(b.model)}</span>
      <span class="k">10-min script</span><span>about ${fmtDur(600 / b.x_realtime + 30)}</span></div>` : '<p class="help" style="flex:1">Not tested yet.</p>'}
      <button class="btn ${b ? '' : 'accent'}" id="bench-go" ${s.ready ? '' : 'disabled'}>${icon('play')} ${b ? 'Test again' : 'Run speed test'}</button></div>`;
  setHtml($('setup-body'), html);
  const busy = s.engines.some((e) => e.job && ['downloading', 'checking', 'installing'].includes(e.job.status))
    || s.models.some((m) => m.job && ['downloading', 'checking', 'installing'].includes(m.job.status));
  if (busy) setTimeout(() => S.view === 'setup' && loadSetup(), 1000);
}
$('setup-refresh').addEventListener('click', () => loadSetup(true));
document.addEventListener('click', run(async (e) => {
  const b = e.target.closest('[data-e]'); if (!b) return;
  const act = b.dataset.e;
  if (act === 'remove' && !await confirmDialog('Remove this engine?', 'Its files are deleted. You can download it again any time.', 'Remove')) return;
  if (act === 'discard' && !await confirmDialog('Discard the paused download?', 'The part already downloaded is deleted.', 'Discard')) return;
  await api(`/api/setup/engines/${b.dataset.key}/${act}`, { method: 'POST' });
  setTimeout(() => { loadSetup(); pollState(); }, 300);
}));
$('setup-body').addEventListener('click', run(async (e) => {
  if (!e.target.closest('#bench-go')) return;
  const btn = e.target.closest('#bench-go');
  btn.disabled = true; btn.textContent = 'Testing… (about 20 seconds)';
  try { await api('/api/setup/benchmark', { method: 'POST' }); } finally { $('setup-body')._html = ''; loadSetup(); }
}));

// ---------- CONNECT ----------
async function loadConnect() {
  S.settings = await api('/api/settings');
  const s = S.settings, base = S.state.api_base, key = s.api_key, port = s.port;
  const voice = S.voices[0]?.name || 'Narrator';
  const code = (text) => `<div class="code"><button class="icon-btn copy" data-copy="${esc(text)}" aria-label="Copy">${icon('copy')}</button>${esc(text)}</div>`;
  const tabs = {
    claude: `claude mcp add --scope user --transport http fatima-voice-studio http://127.0.0.1:${port}/mcp --header "Authorization: Bearer ${key}"`,
    codex: `# ~/.codex/config.toml\n[mcp_servers.fatima-voice-studio]\nurl = "http://127.0.0.1:${port}/mcp"\nhttp_headers = { "Authorization" = "Bearer ${key}" }`,
    antigravity: `// ~/.gemini/config/mcp_config.json\n{ "mcpServers": { "fatima-voice-studio": { "serverUrl": "http://127.0.0.1:${port}/mcp",\n    "headers": { "Authorization": "Bearer ${key}" } } } }`,
    hermes: `# ~/.hermes/config.yaml\nmcp_servers:\n  fatima-voice-studio:\n    url: "http://127.0.0.1:${port}/mcp"\n    headers:\n      Authorization: "Bearer ${key}"\n    timeout: 1800`,
    stdio: `command: ${s.python_exe}\nargs: ["${s.mcp_script.replace(/\\/g, '\\\\')}"]`,
  };
  const tab = S.connectTab || 'claude';
  const html = `<div class="settings-grid">
    <section class="card panel"><h2>OpenAI-compatible API</h2>
      <p class="help">Any app that can use OpenAI's text-to-speech can use this PC instead: point it at the address below with the key. <span class="mono">voice</span> is a name from your voice library.</p>
      <div class="kv"><span class="k">Base URL</span><span class="mono">${esc(base)}</span><span class="k">API key</span><span class="row" style="gap:6px"><span class="mono" id="key-text">${esc(key.slice(0, 12))}…</span><button class="icon-btn" data-copy="${esc(key)}" aria-label="Copy key">${icon('copy')}</button></span></div>
      ${code(`curl ${base}/audio/speech \\\n  -H "Authorization: Bearer ${key}" -H "Content-Type: application/json" \\\n  -d '{"input": "Hello from my own PC.", "voice": "${voice}", "response_format": "mp3"}' \\\n  -o hello.mp3`)}
      ${code(`from openai import OpenAI\nclient = OpenAI(base_url="${base}", api_key="${key}")\nclient.audio.speech.create(model="qwen3-tts", voice="${voice}", input="Hello!").write_to_file("hello.mp3")`)}
      <table class="plain"><tr><th>Endpoint</th><th>What it does</th></tr>
        <tr><td class="mono">POST /v1/audio/speech</td><td>Text to speech (mp3, wav, flac, pcm). Extras: <span class="mono">language</span>, <span class="mono">seed</span>. Any length; long text is split and joined.</td></tr>
        <tr><td class="mono">POST /v1/audio/transcriptions</td><td>Speech to text with Whisper (json, text, srt, vtt, verbose_json).</td></tr>
        <tr><td class="mono">GET /v1/audio/voices</td><td>Your voice library.</td></tr>
        <tr><td class="mono">GET /v1/models</td><td>Installed models.</td></tr></table>
      <p class="help">Interactive docs: <a href="/docs" target="_blank">/docs</a>. Requests go ahead of batches. The API only listens on this PC (127.0.0.1).</p>
    </section>
    <section class="card panel"><h2>AI agents (MCP)</h2>
      <p class="help">Let Claude Code, Codex, Antigravity, Hermes or any MCP agent make voiceovers: list voices, start batches, wait, fix parts, export. The studio must be running.</p>
      <div class="tabs">${Object.keys(tabs).map((t) => `<button type="button" data-tab="${t}" aria-pressed="${t === tab}">${{ claude: 'Claude Code', codex: 'Codex', antigravity: 'Antigravity', hermes: 'Hermes', stdio: 'Other (stdio)' }[t]}</button>`).join('')}</div>
      ${code(tabs[tab])}
      <h2 style="margin-top:8px">Guard rails</h2>
      <p class="help">Agents can't download models or delete anything. They only write to the Exports folder (<span class="mono">${esc(s.exports_dir)}</span>), and only read voice clips and script files from these folders (plus Batches and Exports):</p>
      <textarea class="paste mono" id="agent-dirs" rows="4" style="font-size:12px">${esc(s.agent_read_dirs.join('\n'))}</textarea>
      <label class="check"><input type="checkbox" id="agent-nc" ${s.agents_noncommercial ? 'checked' : ''}> Let agents use non-commercial models (none installed by default)</label>
      <button class="btn sm" id="agent-save">Save guard rails</button>
    </section></div>`;
  setHtml($('connect-body'), html);
}
document.addEventListener('click', run(async (e) => {
  const c = e.target.closest('[data-copy]');
  if (c) { await navigator.clipboard.writeText(c.dataset.copy); toast('Copied.', true); return; }
  const t = e.target.closest('[data-tab]');
  if (t) { S.connectTab = t.dataset.tab; $('connect-body')._html = ''; loadConnect(); return; }
  if (e.target.closest('#agent-save')) {
    const dirs = $('agent-dirs').value.split('\n').map((x) => x.trim()).filter(Boolean);
    S.settings = await api('/api/settings', { method: 'PUT', json: { agent_read_dirs: dirs, agents_noncommercial: $('agent-nc').checked } });
    toast('Saved.', true);
  }
}));

// ---------- SETTINGS ----------
async function loadSettings() {
  S.settings = await api('/api/settings');
  await loadVoicesList();
  const s = S.settings, st = S.state;
  const upd = await api('/api/update').catch(() => null);
  const pathRow = (key, label, help) => `<div class="field"><label class="label">${label}</label><div class="path-row"><input class="input" data-set="${key}" value="${esc(s[key])}"><button class="btn sm" data-browse="${key}">Browse</button></div>${help ? `<p class="help">${help}</p>` : ''}</div>`;
  const html = `<div class="settings-grid">
    <section class="card panel"><h2>Defaults for new scripts</h2>
      <div class="field"><label class="label">Voice</label><div class="select-wrap"><select class="select" data-set="default_voice">${voiceOptions(s.default_voice, { blank: 'None' })}</select>${icon('chevron')}</div></div>
      <div class="pair"><div class="field"><label class="label">Language</label><div class="select-wrap"><select class="select" data-set="default_language">${languageOptions(s.default_language)}</select>${icon('chevron')}</div></div>
        <div class="field"><label class="label">Voice model</label><div class="select-wrap"><select class="select" data-set="default_model">${st.models.filter((m) => m.kind === 'voice').map((m) => `<option value="${m.key}"${m.key === s.default_model ? ' selected' : ''}>${esc(m.label)}${m.installed ? '' : ' (not downloaded)'}</option>`).join('')}</select>${icon('chevron')}</div></div></div>
    </section>
    <section class="card panel"><h2>Output</h2>
      <div class="field"><span class="label">Files for each finished script</span><div class="checks">
        <label><input type="checkbox" data-fmt="wav" ${s.formats.includes('wav') ? 'checked' : ''}> WAV</label>
        <label><input type="checkbox" data-fmt="mp3" ${s.formats.includes('mp3') ? 'checked' : ''}> MP3</label>
        <label><input type="checkbox" data-set="subtitles" ${s.subtitles ? 'checked' : ''}> Subtitles (SRT)</label></div></div>
      <div class="field"><label class="label">Whisper model (subtitles and transcripts)</label><div class="select-wrap"><select class="select" data-set="subtitles_model"><option value=""${s.subtitles_model ? '' : ' selected'}>Best one downloaded</option>${st.models.filter((m) => m.kind === 'subtitles').map((m) => `<option value="${m.key}"${m.key === s.subtitles_model ? ' selected' : ''}${m.installed ? '' : ' disabled'}>${esc(m.label)}${m.installed ? '' : ' (not downloaded)'}</option>`).join('')}</select>${icon('chevron')}</div></div>
      <div class="pair"><div class="field"><label class="label">Loudness (LUFS)</label><input class="input mono" type="number" step="0.5" min="-30" max="-9" data-set="loudness" value="${s.loudness}"><p class="help">−16 suits voiceovers; YouTube plays at about −14.</p></div>
        <div class="field"><label class="label">MP3 quality (kbps)</label><div class="select-wrap"><select class="select" data-set="mp3_bitrate">${[96, 128, 160].map((k) => `<option${k === s.mp3_bitrate ? ' selected' : ''}>${k}</option>`).join('')}</select>${icon('chevron')}</div></div></div>
      <div class="pair"><div class="field"><label class="label">Pause between paragraphs (s)</label><input class="input mono" type="number" step="0.1" min="0" max="10" data-set="pause_paragraph" value="${s.pause_paragraph}"></div>
        <div class="field"><label class="label">Pause inside a paragraph (s)</label><input class="input mono" type="number" step="0.05" min="0" max="5" data-set="pause_segment" value="${s.pause_segment}"></div></div>
      <div class="field"><label class="label">Longest part (characters)</label><input class="input mono" type="number" step="50" min="150" max="1200" data-set="max_chars" value="${s.max_chars}"><p class="help">Text is spoken in parts of up to this length (about ${Math.round(s.max_chars / 14)} s). Shorter parts are quicker to redo; longer ones flow more.</p></div>
    </section>
    <section class="card panel"><h2>Folders</h2>
      ${pathRow('batches_dir', 'Batches', 'Every batch is a folder in here.')}
      ${pathRow('exports_dir', 'Exports', 'Where AI agents save exports.')}
      <div class="row wrap"><button class="btn sm" data-open-folder="voices">${icon('folder')} Voices</button><button class="btn sm" data-open-folder="models">${icon('folder')} Models</button><button class="btn sm" data-open-folder="logs">${icon('folder')} Logs</button></div>
    </section>
    <section class="card panel"><h2>App</h2>
      <label class="switch"><input type="checkbox" data-set="start_with_windows" ${s.start_with_windows ? 'checked' : ''}> Start with Windows (in the tray)</label>
      <label class="switch"><input type="checkbox" data-set="notify" ${s.notify ? 'checked' : ''}> Windows notification when a batch finishes</label>
      <div class="pair"><div class="field"><label class="label">Port</label><input class="input mono" type="number" data-set="port" value="${s.port}"><p class="help">Applies after a restart.</p></div>
        <div class="field"><label class="label">API key</label><input class="input mono" data-set="api_key" value="${esc(s.api_key)}"></div></div>
      <div class="field"><label class="label">Hugging Face token <span class="opt">— optional</span></label><input class="input mono" type="password" data-set="hf_token" placeholder="${s.hf_token_set ? 'Set (type to replace, clear to remove)' : 'Not needed for the models here'}"></div>
    </section>
    <section class="card panel"><h2>Updates</h2>
      <div class="kv"><span class="k">This version</span><span>${esc(s.version)}</span><span class="k">Latest</span><span>${esc(upd?.latest || '—')}</span></div>
      ${upd?.status === 'available' ? `<p class="help">${esc(upd.notes || '')}</p><div class="row wrap">${upd.quick_ok ? '<button class="btn accent sm" data-update="quick">Quick update</button>' : ''}<button class="btn sm ${upd.quick_ok ? '' : 'accent'}" data-update="full">Full update</button></div>` : ''}
      ${upd?.error ? `<p class="err-note">${esc(upd.error)}</p>` : upd?.status === 'up_to_date' ? '<p class="help">You have the latest version.</p>' : upd?.status === 'manual' && upd.url ? `<p class="help">Version ${esc(upd.latest)} is out: <a href="${esc(upd.url)}" target="_blank">download it from GitHub</a>.</p>` : ''}
      <div class="row wrap"><button class="btn sm" data-update="check">${icon('refresh')} Check now</button>
        <label class="switch"><input type="checkbox" data-set="check_updates" ${s.check_updates ? 'checked' : ''}> Check automatically</label></div>
      ${s.installed ? '' : '<p class="help">Running from source: updates come from git, not from here.</p>'}
    </section></div>`;
  setHtml($('settings-body'), html);
}
$('settings-body').addEventListener('change', run(async (e) => {
  const el = e.target;
  let body = null;
  if (el.dataset.set) body = { [el.dataset.set]: el.type === 'checkbox' ? el.checked : (el.type === 'number' ? Number(el.value) : el.value) };
  if (el.dataset.fmt) body = { formats: [...document.querySelectorAll('[data-fmt]')].filter((x) => x.checked).map((x) => x.dataset.fmt) };
  if (!body) return;
  const r = await api('/api/settings', { method: 'PUT', json: body });
  S.settings = r;
  toast(r.restart_needed ? 'Saved. Restart the app to use the new port.' : 'Saved.', true);
}));
$('settings-body').addEventListener('click', run(async (e) => {
  const br = e.target.closest('[data-browse]');
  if (br) {
    const key = br.dataset.browse;
    const r = await api('/api/browse-folder', { method: 'POST', json: { start: S.settings[key] } });
    if (r.path) { S.settings = await api('/api/settings', { method: 'PUT', json: { [key]: r.path } }); $('settings-body')._html = ''; loadSettings(); toast('Saved.', true); }
    return;
  }
  const up = e.target.closest('[data-update]');
  if (up) {
    if (up.dataset.update === 'check') await api('/api/update/check', { method: 'POST' });
    else {
      if (!await confirmDialog('Install the update now?', 'The app closes, updates and starts again by itself. Your voices, models, settings and audio are kept.', 'Update')) return;
      await api(`/api/update/${up.dataset.update}`, { method: 'POST' });
      toast('Updating… the app restarts by itself.', true);
    }
    $('settings-body')._html = ''; loadSettings();
  }
}));

// ---------- start ----------
paintIcons();
loadDraft();
setSmode('list');
(async () => {
  await pollState();
  try { S.settings = await api('/api/settings'); } catch { /* not ready */ }
  try { const s = await api('/api/setup'); S.setupBench = s.benchmark; } catch { /* not ready */ }
  route();
  setInterval(async () => {
    await pollState();
    if (document.hidden) return;
    if (S.view === 'batch' && S.arg) {
      try { S.detail = await api(`/api/batches/${encodeURIComponent(S.arg)}`); renderDetail(); } catch { /* deleted */ }
    } else if (S.view === 'batches') loadBatches();
    else if (S.view === 'create') renderQueue();
  }, 1500);
})();
