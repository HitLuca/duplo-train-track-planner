/* Trenino Duplo — frontend.
   Solo visualizzazione: chiede i dati al backend (/api/...) e li disegna.
   Geometria, ricerca, ingombri e istruzioni sono calcolati dal server. */

const $ = id => document.getElementById(id);
let CAT = null;            // catalogo dei pezzi (etichette, colori, icone)
let inv = {};              // quantità per tipo, come le ha l'utente
let lastJob = null;        // id dell'ultima ricerca, per "Cerca ancora"
let results = [];          // miniature dei percorsi trovati
let saved = [];            // miniature dei percorsi salvati
let current = null;        // percorso aperto: {source:'search'|'saved', ref, data}

/* ---------- API ---------- */
async function api(path, opt = {}){
  const r = await fetch(path, {method: opt.method || 'GET', headers: {'Content-Type': 'application/json'}, body: opt.body ? JSON.stringify(opt.body) : undefined});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const setSync = t => { $('sync').textContent = t; };
const roomVal = () => ({w: +$('roomW').value || 0, h: +$('roomH').value || 0});

/* ---------- formattazione ---------- */
const fmtM = mm => (mm / 1000).toLocaleString('it-IT', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' m';
const fmtCm = mm => Math.round(mm / 10);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pts = a => a.map(p => p[0] + ',' + p[1]).join(' ');

/* ---------- disegno: forme già calcolate dal server → SVG ---------- */
let GID = 0;
function piecesSVG(pieces, labels){
  let defs = '', shadow = '', body = '', lbl = '';
  for (const p of pieces){
    let fill = CAT.colors[p.t];
    if (p.ramp){
      const id = 'g' + (++GID), [a, b] = p.ramp.up ? ['#FFE27A', '#B07A2A'] : ['#B07A2A', '#FFE27A'];
      defs += `<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${p.ramp.from[0]}" y1="${p.ramp.from[1]}" x2="${p.ramp.to[0]}" y2="${p.ramp.to[1]}"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`;
      fill = `url(#${id})`;
    }
    if (p.lift) shadow += `<polygon points="${pts(p.outline)}" transform="translate(${p.lift},${p.lift})" fill="rgba(60,40,0,.18)"/>`;
    body += `<g class="piece" data-i="${p.i}"><path class="base" d="M${pts(p.outline)} Z" fill="${fill}" stroke="rgba(0,0,0,.35)" stroke-width="1.5"/>`
      + p.rails.map(r => `<polyline points="${pts(r)}" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="5"/>`).join('')
      + p.ends.map(e => `<polyline points="${pts(e)}" stroke="rgba(0,0,0,.45)" stroke-width="2.5"/>`).join('') + '</g>';
  }
  for (const l of labels || []){
    const [x, y] = l.at;
    lbl += `<g class="lbl" pointer-events="none"><circle cx="${x}" cy="${y}" r="15" fill="#fff" stroke="rgba(0,0,0,.25)"/><text x="${x}" y="${y + 5}" text-anchor="middle" font-size="15" font-weight="800" fill="#2B2A33">${l.n}</text></g>`;
  }
  return `<defs>${defs}</defs>${shadow}${body}${lbl}`;
}
const vb = b => `${b.x} ${b.y} ${b.w} ${b.h}`;

/* ---------- inventario ---------- */
function iconSVG(icon){
  if (icon.kind === 'pillar') return `<svg viewBox="0 0 64 40"><rect x="10" y="6" width="44" height="28" rx="5" fill="${CAT.colors.PIL}"/>${[18,32,46].map(x => `<circle cx="${x}" cy="14" r="4" fill="#a8854f"/><circle cx="${x}" cy="26" r="4" fill="#a8854f"/>`).join('')}</svg>`;
  return `<svg viewBox="${icon.viewBox.join(' ')}">${piecesSVG(icon.pieces)}</svg>`;
}
function renderInv(){
  let h = '';
  for (const g of CAT.groups){
    h += `<h3>${esc(g.title)}</h3>`;
    for (const p of g.types){
      h += `<div class="inv-row" title="STL: ${esc(p.stl)}">${iconSVG(p.icon)}<div><div class="nm">${esc(p.label)}</div><div class="nf">${esc(p.info)}</div></div>
        <div class="step"><button data-t="${p.t}" data-d="-1" aria-label="meno">−</button><input data-t="${p.t}" type="number" min="0" value="${inv[p.t] || 0}"><button data-t="${p.t}" data-d="1" aria-label="più">+</button></div></div>`;
    }
  }
  $('inv').innerHTML = h;
  $('inv').querySelectorAll('button').forEach(b => b.onclick = () => { const t = b.dataset.t; inv[t] = Math.max(0, (inv[t] || 0) + +b.dataset.d); $('inv').querySelector(`input[data-t="${t}"]`).value = inv[t]; saveInv(); });
  $('inv').querySelectorAll('input').forEach(i => i.onchange = () => { inv[i.dataset.t] = Math.max(0, parseInt(i.value) || 0); i.value = inv[i.dataset.t]; saveInv(); });
}
let saveTimer = 0;
function saveInv(){
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      await api('/api/inventory', {method:'PUT', body:{inv, room: roomVal()}});
      setSync('💾 Pezzi salvati nel database');
      await loadSaved();   // il server ricalcola quali percorsi salvati non si possono più fare
    } catch(e){ setSync('⚠️ Errore nel salvataggio: ' + e.message); }
  }, 400);
}
$('roomW').onchange = $('roomH').onchange = saveInv;

/* ---------- ricerca ---------- */
async function runSearch(append){
  clearTimeout(saveTimer);
  $('go').disabled = $('more').disabled = true; $('bar').style.width = '0';
  $('status').textContent = 'Sto provando le combinazioni…';
  try {
    const {id} = await api('/api/search', {method:'POST', body:{inv, room: roomVal(), depth: $('time').value, previous: append ? lastJob : null}});
    let s;
    for (;;){
      s = await api('/api/search/' + id);
      $('bar').style.width = Math.round(s.progress * 100) + '%';
      if (s.done) break;
      $('status').textContent = `Sto provando le combinazioni… (${s.found} percorsi validi finora)`;
      await sleep(250);
    }
    if (s.error) throw new Error(s.error);
    lastJob = id; results = s.results;
    $('status').textContent = results.length ? `Trovati ${results.length} percorsi diversi.` : 'Nessun percorso chiuso con questi pezzi: servono almeno abbastanza curve per fare un giro completo (es. 12 curve da 30°).';
    renderGallery();
    if (results.length) openResult(0, $('gallery').querySelector('.res'));
  } catch(e){
    $('status').textContent = '⚠️ ' + e.message;
  } finally {
    $('go').disabled = false; $('more').disabled = !lastJob;
  }
}
$('go').onclick = () => runSearch(false);
$('more').onclick = () => runSearch(true);

/* ---------- gallerie ---------- */
function cardHTML(r, i, savedCard){
  const tag = savedCard ? `<span class="tag" style="background:var(--green)">${esc(r.name)}</span>` : `<span class="tag ${r.tag === 'Variante' ? 't2' : ''}">${esc(r.tag)}</span>`;
  const tools = savedCard ? `<div class="row" style="margin-top:6px"><button class="chip" data-act="ren">✏️ Rinomina</button><button class="chip" data-act="del">🗑 Elimina</button></div>` : '';
  return `<div class="res" data-i="${i}"><svg viewBox="${vb(r.thumb.bbox)}" preserveAspectRatio="xMidYMid meet">${piecesSVG(r.thumb.pieces)}</svg>
    ${tag}
    <div class="st"><b>${fmtM(r.len)}</b> · ${r.pieces} pezzi<br><span class="small">${fmtCm(r.width)} × ${fmtCm(r.depth)} cm${r.crossing ? ' · incrocio' : ''}${r.bridge ? ' · ponte' : ''}</span>
    ${savedCard && r.missing ? '<br><span class="small" style="color:var(--red)">⚠️ ora ti mancano dei pezzi</span>' : ''}</div>${tools}</div>`;
}
function renderGallery(){
  const g = $('gallery');
  if (!results.length){ g.innerHTML = '<div class="empty">Nessun percorso trovato.</div>'; return; }
  g.innerHTML = results.map((r, i) => cardHTML(r, i, false)).join('');
  g.querySelectorAll('.res').forEach(el => el.onclick = () => openResult(+el.dataset.i, el));
}
async function loadSaved(){
  try { saved = await api('/api/layouts'); } catch(e){ setSync('⚠️ ' + e.message); }
  renderSaved();
}
function renderSaved(){
  const el = $('saved');
  if (!saved.length){ el.innerHTML = '<div class="empty">Ancora nessun percorso salvato. Aprine uno e premi <b>⭐ Salva percorso</b>.</div>'; return; }
  el.innerHTML = saved.map((r, i) => cardHTML(r, i, true)).join('');
  el.querySelectorAll('.res').forEach(card => {
    const r = saved[+card.dataset.i];
    card.onclick = () => openSaved(r.id, card);
    card.querySelector('[data-act="del"]').onclick = async e => {
      e.stopPropagation();
      if (!confirm(`Eliminare "${r.name}"?`)) return;
      await api('/api/layouts/' + r.id, {method:'DELETE'}); await loadSaved();
    };
    card.querySelector('[data-act="ren"]').onclick = async e => {
      e.stopPropagation();
      const name = prompt('Nuovo nome:', r.name); if (!name) return;
      await api('/api/layouts/' + r.id, {method:'PATCH', body:{name}}); await loadSaved();
    };
  });
}
$('saveBtn').onclick = async () => {
  if (!current) return;
  if (current.source === 'saved'){ $('saveMsg').textContent = `Già salvato come "${current.data.name}"`; return; }
  const name = prompt('Come vuoi chiamare questo percorso?', `${current.data.tag} ${fmtM(current.data.len)}`);
  if (name === null) return;
  try {
    await api(`/api/search/${lastJob}/${current.ref}/save`, {method:'POST', body:{name: name || 'Percorso'}});
    $('saveMsg').textContent = 'Salvato ✓'; await loadSaved();
  } catch(e){ $('saveMsg').textContent = '⚠️ ' + e.message; }
};

/* ---------- vista grande ---------- */
function selectCard(cardEl){ document.querySelectorAll('.res').forEach(el => el.classList.toggle('sel', el === cardEl)); }
async function openResult(i, cardEl){
  selectCard(cardEl);
  try { showLayout({source:'search', ref:i, data: await api(`/api/search/${lastJob}/${i}`)}); }
  catch(e){ $('status').textContent = '⚠️ ' + e.message; }
}
async function openSaved(id, cardEl){
  selectCard(cardEl);
  try { showLayout({source:'saved', ref:id, data: await api('/api/layouts/' + id)}); }
  catch(e){ setSync('⚠️ ' + e.message); }
}

let view = null, train = {on:true, s:0, pts:null, last:0}, showNum = true, showGrid = false;
function showLayout(c){
  current = c; const r = c.data;
  $('detail').style.display = ''; $('saveMsg').textContent = c.source === 'saved' ? `Salvato come "${r.name}"` : '';
  view = {...r.bbox, base:{...r.bbox}};
  drawView();
  $('stats').innerHTML = `<div class="stat"><b>${fmtM(r.len)}</b><span>percorso</span></div><div class="stat"><b>${r.pieces}</b><span>pezzi</span></div><div class="stat"><b>${fmtCm(r.width)}×${fmtCm(r.depth)}</b><span>cm di ingombro</span></div>`;
  $('used').innerHTML = `<tr><td class="small">pezzo</td><td class="n small">usati / hai</td></tr>`
    + r.used.map(u => `<tr><td><span class="sw" style="background:${CAT.colors[u.t]}"></span>${esc(CAT.labels[u.t])}</td><td class="n">${u.used} / ${u.have}</td></tr>`).join('');
  $('steps').innerHTML = r.steps.map(s => `<li data-piece="${s.piece}"><span class="k">${s.n ?? s.icon}</span><span class="sw" style="background:${CAT.colors[s.t]}"></span>${esc(s.text)}${s.n ? ' ' + s.icon : ''}</li>`).join('');
  $('steps').querySelectorAll('li').forEach(el => {
    el.onmouseenter = () => hlPiece(el.dataset.piece, true);
    el.onmouseleave = () => hlPiece(el.dataset.piece, false);
  });
  train.pts = r.train.points; train.total = r.train.total; train.s = 0;
}
function hlPiece(i, on){ $('view').querySelectorAll(`.piece[data-i="${i}"]`).forEach(p => p.classList.toggle('hl', on)); }
function drawView(){
  const svg = $('view'), r = current.data;
  let grid = '';
  if (showGrid){
    const b = view.base, g0x = Math.floor((b.x - 2000) / 100) * 100, g0y = Math.floor((b.y - 2000) / 100) * 100;
    for (let x = g0x; x < b.x + b.w + 2000; x += 100) grid += `<line x1="${x}" y1="${b.y - 2000}" x2="${x}" y2="${b.y + b.h + 2000}" stroke="#E6DCC6" stroke-width="${x % 500 ? 1 : 2.5}"/>`;
    for (let y = g0y; y < b.y + b.h + 2000; y += 100) grid += `<line x1="${b.x - 2000}" y1="${y}" x2="${b.x + b.w + 2000}" y2="${y}" stroke="#E6DCC6" stroke-width="${y % 500 ? 1 : 2.5}"/>`;
  }
  svg.innerHTML = `<g>${grid}</g>${piecesSVG(r.pieces, showNum ? r.labels : null)}<g id="trainG"></g>`;
  setVB();
  svg.querySelectorAll('.piece').forEach(p => {
    const i = p.dataset.i;
    p.onmouseenter = () => { hlPiece(i, true); $('steps').querySelectorAll(`li[data-piece="${i}"]`).forEach(l => { l.classList.add('hl'); l.scrollIntoView({block:'nearest'}); }); };
    p.onmouseleave = () => { hlPiece(i, false); $('steps').querySelectorAll('li.hl').forEach(l => l.classList.remove('hl')); };
  });
}
function setVB(){ $('view').setAttribute('viewBox', vb(view)); }
function redrawKeepingZoom(){ if (!view) return; const v = {x:view.x, y:view.y, w:view.w, h:view.h}; drawView(); Object.assign(view, v); setVB(); }

/* pan & zoom */
(() => {
  const svg = $('view'); let drag = null;
  const toSvg = e => { const r = svg.getBoundingClientRect(); const s = Math.max(view.w / r.width, view.h / r.height);
    const ox = view.x + (view.w - r.width * s) / 2, oy = view.y + (view.h - r.height * s) / 2;
    return {x: ox + (e.clientX - r.left) * s, y: oy + (e.clientY - r.top) * s, s}; };
  svg.addEventListener('wheel', e => { if (!view) return; e.preventDefault();
    const p = toSvg(e), f = Math.exp(e.deltaY * 0.0015);
    view.x = p.x - (p.x - view.x) * f; view.y = p.y - (p.y - view.y) * f; view.w *= f; view.h *= f; setVB(); }, {passive:false});
  svg.addEventListener('pointerdown', e => { if (!view) return; drag = {x:e.clientX, y:e.clientY, vx:view.x, vy:view.y, s:toSvg(e).s}; svg.setPointerCapture(e.pointerId); svg.style.cursor = 'grabbing'; });
  svg.addEventListener('pointermove', e => { if (!drag) return; view.x = drag.vx - (e.clientX - drag.x) * drag.s; view.y = drag.vy - (e.clientY - drag.y) * drag.s; setVB(); });
  svg.addEventListener('pointerup', () => { drag = null; svg.style.cursor = ''; });
})();

/* treno animato: scorre lungo i punti del percorso forniti dal server */
function trainAt(s){
  const P = train.pts, L = train.total; s = ((s % L) + L) % L;
  let lo = 0, hi = P.length - 1;
  while (lo < hi){ const m = (lo + hi + 1) >> 1; if (P[m][2] <= s) lo = m; else hi = m - 1; }
  const a = P[lo], b = P[(lo + 1) % P.length];
  const sb = b[2] < a[2] ? L : b[2], t = (s - a[2]) / Math.max(1e-6, sb - a[2]);
  return {x: a[0] + (b[0] - a[0]) * t, y: a[1] + (b[1] - a[1]) * t};
}
function car(s, color, engine){
  const f = trainAt(s + 45), r = trainAt(s - 45);
  const x = (f.x + r.x) / 2, y = (f.y + r.y) / 2, ang = Math.atan2(f.y - r.y, f.x - r.x) * 180 / Math.PI;
  return `<g transform="translate(${x.toFixed(1)},${y.toFixed(1)}) rotate(${ang.toFixed(1)})">
    <rect x="-56" y="-30" width="112" height="60" rx="14" fill="${color}" stroke="rgba(0,0,0,.35)" stroke-width="2"/>
    ${engine ? '<rect x="-46" y="-20" width="44" height="40" rx="8" fill="#FFC928"/><circle cx="30" cy="0" r="11" fill="#333"/><circle cx="30" cy="0" r="5" fill="#777"/>'
             : [-24, 0, 24].map(cx => `<circle cx="${cx}" cy="-10" r="8" fill="rgba(255,255,255,.55)"/><circle cx="${cx}" cy="10" r="8" fill="rgba(255,255,255,.55)"/>`).join('')}</g>`;
}
function tick(ts){
  requestAnimationFrame(tick);
  const dt = Math.min(.05, (ts - (train.last || ts)) / 1000); train.last = ts;
  const gEl = document.getElementById('trainG');
  if (!gEl || !train.pts) return;
  if (!train.on){ gEl.innerHTML = ''; return; }
  train.s += 260 * dt;
  gEl.innerHTML = car(train.s - 250, '#2F6FDE') + car(train.s - 125, '#2E9E5B') + car(train.s, '#E3342F', true);
}
requestAnimationFrame(tick);

$('tTrain').onclick = e => { train.on = !train.on; e.target.classList.toggle('on', train.on); };
$('tNum').onclick = e => { showNum = !showNum; e.target.classList.toggle('on', showNum); redrawKeepingZoom(); };
$('tGrid').onclick = e => { showGrid = !showGrid; e.target.classList.toggle('on', showGrid); redrawKeepingZoom(); };
$('tFit').onclick = () => { if (view){ Object.assign(view, view.base); setVB(); } };
$('tSvg').onclick = () => {
  if (!view) return;
  const s = $('view').cloneNode(true); s.querySelector('#trainG').remove(); s.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  s.setAttribute('viewBox', vb(view.base));
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([s.outerHTML], {type:'image/svg+xml'}));
  a.download = 'percorso-duplo.svg'; a.click();
};

/* ---------- avvio ---------- */
(async function init(){
  try {
    const [cat, state] = await Promise.all([api('/api/catalog'), api('/api/inventory')]);
    CAT = cat; inv = state.inv;
    $('roomW').value = state.room.w || ''; $('roomH').value = state.room.h || '';
    renderInv();
    setSync('💾 Collegato al database: pezzi e percorsi vengono salvati.');
    await loadSaved();
  } catch(e){
    setSync('⚠️ Server non raggiungibile: avvia l\'app con Docker o con "python3 server.py". (' + e.message + ')');
    $('go').disabled = true;
  }
})();
