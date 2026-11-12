'use strict';
// Uptime 24: one small server for the broadcast page, the admin interface and the channel poller.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const sources = require('./lib/sources');

const PORT = Number(process.env.PORT) || 8080;
const DATA = process.env.DATA_DIR || path.join(__dirname, 'data');
const USER = process.env.ADMIN_USER || 'admin';
let PASS = process.env.ADMIN_PASSWORD;
if (!PASS) {
  PASS = crypto.randomBytes(9).toString('base64url');
  console.log(`ADMIN_PASSWORD is not set. Generated one for this run: ${PASS}`);
}
const ELEVEN_KEY = process.env.ELEVENLABS_API_KEY || '';
const DEFAULT_VOICES = { max: 'pNInz6obpgDQGcFmaJgB', ada: '21m00Tcm4TlvDq8ikWAM', gus: 'ErXwobaYiN019PkySvjV' };

/* ---------- stored configuration ---------- */
fs.mkdirSync(path.join(DATA, 'tts'), { recursive: true });
const FILE = path.join(DATA, 'config.json');
let cfg = { channels: [], items: [], settings: { demo: true, voices: { max: '', ada: '', gus: '' }, ttsModel: 'eleven_multilingual_v2' } };
try {
  const j = JSON.parse(fs.readFileSync(FILE, 'utf8'));
  cfg = { channels: j.channels || [], items: j.items || [],
    settings: { ...cfg.settings, ...j.settings, voices: { ...cfg.settings.voices, ...(j.settings && j.settings.voices) } } };
} catch (e) { if (e.code !== 'ENOENT') console.error('Could not read config.json, starting empty:', e.message); }
function save() {
  cfg.items = cfg.items.filter(i => !i.expires || i.expires > Date.now());
  fs.writeFileSync(FILE + '.tmp', JSON.stringify(cfg, null, 2));
  fs.renameSync(FILE + '.tmp', FILE);
}

/* ---------- channel polling ---------- */
const runtime = new Map(); // channel id -> last pull result
const rt = id => { if (!runtime.has(id)) runtime.set(id, { services: [], items: [], lastFetch: 0, lastOk: 0, lastError: '', busy: false }); return runtime.get(id); };
async function pull(ch) {
  const r = rt(ch.id);
  if (r.busy) return;
  r.busy = true;
  try { const out = await sources.fetchChannel(ch); r.services = out.services; r.items = out.items; r.lastError = ''; r.lastOk = Date.now(); }
  catch (e) { r.lastError = String(e.message || e).slice(0, 200); }
  r.lastFetch = Date.now(); r.busy = false;
}
setInterval(() => {
  const now = Date.now();
  for (const ch of cfg.channels) if (ch.enabled && now - rt(ch.id).lastFetch >= ch.interval * 1000) pull(ch);
}, 3000);

/* ---------- what the broadcast reads ---------- */
const since = new Map(); // service id -> when its current status was first seen
const seen = new Map();  // item id -> when it was first seen (for feeds without dates)
function state() {
  const now = Date.now(), services = [], items = [];
  for (const i of cfg.items) {
    if (i.expires && i.expires <= now) continue;
    items.push({ id: i.id, title: i.title, text: i.text, severity: i.severity, breaking: i.breaking, source: 'Newsroom', created: i.created });
  }
  for (const ch of cfg.channels) {
    if (!ch.enabled) continue;
    const r = rt(ch.id);
    for (const s of r.services) {
      const id = ch.id + ':' + s.key, p = since.get(id);
      if (!p || p.status !== s.status) since.set(id, { status: s.status, at: now });
      services.push({ id, name: s.name, status: s.status, source: ch.name, incident: s.status === 'operational' ? null
        : { phase: s.phase || '', title: s.title || '', note: s.note || '', started: s.started || since.get(id).at } });
    }
    let n = 0;
    for (const i of r.items) {
      const id = ch.id + ':' + i.key;
      if (!seen.has(id)) seen.set(id, i.created || now);
      const created = seen.get(id);
      if (now - created > ch.maxAgeHours * 3600e3 || n >= 5) continue;
      n++;
      items.push({ id, title: i.title, text: i.text, severity: i.severity, breaking: false, source: ch.name, created });
    }
  }
  items.sort((a, b) => b.created - a.created);
  return { demo: !!cfg.settings.demo && !cfg.channels.some(c => c.enabled), services, items: items.slice(0, 12),
    voice: ELEVEN_KEY ? 'elevenlabs' : 'browser' };
}

/* ---------- ElevenLabs voice, cached on disk ---------- */
const ttsStarts = [];
async function tts(res, q) {
  if (!ELEVEN_KEY) return send(res, 404, { error: 'Voice is not configured' });
  const who = q.get('who'), text = sources.clean(q.get('text'), 300);
  if (!Object.hasOwn(DEFAULT_VOICES, who) || !text) return send(res, 400, { error: 'who and text are required' });
  const voice = cfg.settings.voices[who] || DEFAULT_VOICES[who], model = cfg.settings.ttsModel;
  const file = path.join(DATA, 'tts', crypto.createHash('sha1').update(voice + '|' + model + '|' + text).digest('hex') + '.mp3');
  if (!fs.existsSync(file)) {
    const now = Date.now();
    while (ttsStarts.length && now - ttsStarts[0] > 60000) ttsStarts.shift();
    if (ttsStarts.length >= 40) return send(res, 429, { error: 'Too many new voice lines, try again shortly' });
    ttsStarts.push(now);
    const r = await fetch('https://api.elevenlabs.io/v1/text-to-speech/' + encodeURIComponent(voice) + '?output_format=mp3_44100_128', {
      method: 'POST', signal: AbortSignal.timeout(20000),
      headers: { 'xi-api-key': ELEVEN_KEY, 'content-type': 'application/json', accept: 'audio/mpeg' },
      body: JSON.stringify({ text, model_id: model }),
    });
    if (!r.ok) { console.error('ElevenLabs answered', r.status, (await r.text()).slice(0, 200)); return send(res, 502, { error: 'The voice service failed' }); }
    fs.writeFileSync(file + '.tmp', Buffer.from(await r.arrayBuffer()));
    fs.renameSync(file + '.tmp', file);
  }
  res.writeHead(200, { 'content-type': 'audio/mpeg', 'cache-control': 'public, max-age=86400' });
  fs.createReadStream(file).pipe(res);
}
function pruneTts() { // spoken lines contain durations, so most are never reused: drop week-old clips
  const dir = path.join(DATA, 'tts'), cutoff = Date.now() - 7 * 86400e3;
  for (const f of fs.readdirSync(dir)) { try { if (fs.statSync(path.join(dir, f)).mtimeMs < cutoff) fs.unlinkSync(path.join(dir, f)); } catch (_) {} }
}
pruneTts(); setInterval(pruneTts, 3600e3);

/* ---------- http helpers ---------- */
function send(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(JSON.stringify(body));
}
function page(res, name) {
  res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache', 'x-content-type-options': 'nosniff' });
  fs.createReadStream(path.join(__dirname, 'public', name)).pipe(res);
}
const fail = (status, message) => Object.assign(new Error(message), { status });
const same = (a, b) => { const x = crypto.createHash('sha256').update(a).digest(), y = crypto.createHash('sha256').update(b).digest(); return crypto.timingSafeEqual(x, y); };
function authed(req) {
  const m = /^Basic (.+)$/.exec(req.headers.authorization || '');
  if (!m) return false;
  const s = Buffer.from(m[1], 'base64').toString(), i = s.indexOf(':');
  return i > 0 && same(s.slice(0, i), USER) & same(s.slice(i + 1), PASS);
}
function readJson(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const parts = [];
    req.on('data', c => { size += c.length; if (size > 65536) { reject(fail(413, 'Request is too large')); req.destroy(); } else parts.push(c); });
    req.on('end', () => { try { const j = JSON.parse(Buffer.concat(parts).toString() || '{}'); resolve(j && typeof j === 'object' ? j : {}); } catch (_) { reject(fail(400, 'Body is not valid JSON')); } });
    req.on('error', reject);
  });
}
const str = (v, max) => String(v ?? '').replace(/[\u0000-\u001f\u007f]+/g, ' ').trim().slice(0, max);

/* ---------- admin api ---------- */
function channelFrom(b, old) {
  const c = { id: old ? old.id : crypto.randomBytes(6).toString('hex'), ...old };
  const v = { ...old, ...b };
  c.name = str(v.name, 60); c.type = str(v.type, 20); c.url = str(v.url, 500);
  c.interval = Math.round(Number(v.interval) || 60); c.maxAgeHours = Math.round(Number(v.maxAgeHours) || 24); c.enabled = v.enabled !== false;
  if (!c.name) throw fail(400, 'Give the channel a name');
  if (!Object.hasOwn(sources.TYPES, c.type)) throw fail(400, 'Choose a channel type');
  let u; try { u = new URL(c.url); } catch (_) { throw fail(400, 'Enter a full address starting with http:// or https://'); }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') throw fail(400, 'Enter a full address starting with http:// or https://');
  if (c.interval < 15 || c.interval > 86400) throw fail(400, 'Check interval must be between 15 seconds and 24 hours');
  if (c.maxAgeHours < 1 || c.maxAgeHours > 720) throw fail(400, 'News age must be between 1 hour and 30 days');
  return c;
}
async function admin(req, res, p, m) {
  if (m === 'GET' && p === '/admin') return page(res, 'admin.html');
  if ((m === 'POST' || m === 'PUT') && !/^application\/json/i.test(req.headers['content-type'] || '')) throw fail(415, 'Send JSON');
  const body = m === 'POST' || m === 'PUT' ? await readJson(req) : {};
  const [, , , kind, id, action] = p.split('/'); // /api/admin/<kind>/<id>/<action>

  if (m === 'GET' && kind === 'config') {
    const now = Date.now();
    return send(res, 200, {
      types: sources.TYPES, settings: cfg.settings, voice: ELEVEN_KEY ? 'elevenlabs' : 'browser',
      items: cfg.items.filter(i => !i.expires || i.expires > now),
      channels: cfg.channels.map(c => { const r = rt(c.id); return { ...c, lastFetch: r.lastFetch, lastOk: r.lastOk, lastError: r.lastError, services: r.services.length, news: r.items.length }; }),
    });
  }
  if (kind === 'items') {
    if (m === 'POST' && !id) {
      const text = str(body.text, 600), ttl = Math.round(Number(body.ttlMinutes));
      if (!text) throw fail(400, 'Write the text the presenters should read');
      if (!(ttl >= 0 && ttl <= 43200)) throw fail(400, 'Choose how long the item stays on air');
      const item = { id: 'm' + crypto.randomBytes(6).toString('hex'), title: str(body.title, 80), text,
        severity: sources.SEVERITIES.includes(body.severity) ? body.severity : 'info', breaking: body.breaking === true,
        created: Date.now(), expires: ttl ? Date.now() + ttl * 60000 : 0 };
      cfg.items.unshift(item); save();
      return send(res, 201, item);
    }
    if (m === 'DELETE' && id) { cfg.items = cfg.items.filter(i => i.id !== id); save(); return send(res, 200, { ok: true }); }
  }
  if (kind === 'channels') {
    const ch = cfg.channels.find(c => c.id === id);
    if (m === 'POST' && !id) { const c = channelFrom(body); cfg.channels.push(c); save(); await pull(c); return send(res, 201, c); }
    if (id && !ch) throw fail(404, 'That channel no longer exists');
    if (m === 'PUT' && !action) { const c = channelFrom(body, ch); cfg.channels[cfg.channels.indexOf(ch)] = c; save(); if (c.enabled) await pull(c); return send(res, 200, c); }
    if (m === 'POST' && action === 'fetch') { await pull(ch); return send(res, 200, { ok: true, error: rt(ch.id).lastError }); }
    if (m === 'DELETE' && !action) { cfg.channels = cfg.channels.filter(c => c !== ch); runtime.delete(ch.id); save(); return send(res, 200, { ok: true }); }
  }
  if (m === 'PUT' && kind === 'settings') {
    if ('demo' in body) cfg.settings.demo = body.demo === true;
    for (const who of Object.keys(DEFAULT_VOICES)) {
      if (!body.voices || !(who in body.voices)) continue;
      const v = str(body.voices[who], 40);
      if (v && !/^[A-Za-z0-9]+$/.test(v)) throw fail(400, 'A voice ID contains only letters and digits');
      cfg.settings.voices[who] = v;
    }
    save();
    return send(res, 200, cfg.settings);
  }
  throw fail(404, 'Not found');
}

/* ---------- routes ---------- */
const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url, 'http://localhost'), p = u.pathname, m = req.method;
    if (m === 'GET' && p === '/') return page(res, 'index.html');
    if (m === 'GET' && p === '/api/state') return send(res, 200, state());
    if (m === 'GET' && p === '/api/tts') return await tts(res, u.searchParams);
    if (p === '/admin' || p.startsWith('/api/admin/')) {
      if (!authed(req)) { res.writeHead(401, { 'www-authenticate': 'Basic realm="Uptime 24 admin", charset="UTF-8"' }); return res.end('Sign in to manage Uptime 24.'); }
      return await admin(req, res, p, m);
    }
    send(res, 404, { error: 'Not found' });
  } catch (e) {
    if (!e.status) console.error(e);
    if (!res.headersSent) send(res, e.status || 500, { error: e.status ? e.message : 'Something went wrong on the server' });
    else res.end();
  }
});
server.listen(PORT, () => console.log(`Uptime 24 is on air at http://localhost:${PORT} (admin at /admin, user "${USER}")`));
for (const sig of ['SIGTERM', 'SIGINT']) process.on(sig, () => { server.close(() => process.exit(0)); setTimeout(() => process.exit(0), 1500).unref(); });
