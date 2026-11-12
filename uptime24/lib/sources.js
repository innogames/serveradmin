'use strict';
// Information channels: each type pulls one URL and returns
//   { services: [{ key, name, status, title?, phase?, note?, started? }],
//     items:    [{ key, title, text, severity, created }] }
// status is operational | degraded | outage | maintenance; severity is info | good | degraded | outage.

const crypto = require('node:crypto');

const TYPES = {
  statuspage: 'Status page (Atlassian Statuspage format)',
  rss: 'RSS or Atom feed',
  json: 'JSON endpoint (Uptime 24 format)',
  http: 'Website check (is this URL up?)',
};
const STATUSES = ['operational', 'degraded', 'outage', 'maintenance'];
const SEVERITIES = ['info', 'good', 'degraded', 'outage'];

const ENT = { lt: '<', gt: '>', amp: '&', quot: '"', apos: "'", nbsp: ' ' };
const decode = s => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
  if (e[0] !== '#') return ENT[e.toLowerCase()] ?? m;
  const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
  return n > 0 && n < 0x110000 ? String.fromCodePoint(n) : '';
});
/** Plain single-line text from markup of unknown quality. */
function clean(v, max) {
  let s = String(v ?? '').replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1');
  s = decode(decode(s).replace(/<[^>]*>/g, ' ')).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim();
  return s.length > max ? s.slice(0, max - 1).trimEnd() + '…' : s;
}
const hash = s => crypto.createHash('sha1').update(s).digest('hex').slice(0, 16);
const label = s => { const t = String(s || '').replace(/_/g, ' '); return t ? t[0].toUpperCase() + t.slice(1) : ''; };

const SP = { operational: 'operational', degraded_performance: 'degraded', partial_outage: 'degraded', major_outage: 'outage', under_maintenance: 'maintenance' };
function parseStatuspage(d) {
  const open = (d.incidents || []).filter(i => !['resolved', 'postmortem', 'completed'].includes(i.status));
  const maint = (d.scheduled_maintenances || []).filter(i => ['in_progress', 'verifying'].includes(i.status));
  const info = i => ({
    title: clean(i.name, 120), phase: label(i.status), started: Date.parse(i.started_at || i.created_at) || 0,
    note: clean(i.incident_updates && i.incident_updates[0] && i.incident_updates[0].body, 400),
  });
  const services = (d.components || []).filter(c => !c.group).map(c => {
    const s = { key: String(c.id), name: clean(c.name, 40), status: SP[c.status] || 'degraded' };
    if (s.status !== 'operational') {
      const inc = [...open, ...maint].find(i => (i.components || []).some(x => x.id === c.id));
      if (inc) Object.assign(s, info(inc));
    }
    return s;
  });
  const known = new Set(services.map(s => s.key));
  const items = open.filter(i => !(i.components || []).some(x => known.has(String(x.id)))).map(i => {
    const n = info(i);
    return { key: String(i.id), title: n.title, text: n.note || n.title, created: n.started,
      severity: i.impact === 'critical' || i.impact === 'major' ? 'outage' : i.impact === 'none' ? 'info' : 'degraded' };
  });
  return { services, items };
}

function parseFeed(xml) {
  const tag = (b, n) => { const m = b.match(new RegExp('<' + n + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + n + '>', 'i')); return m ? m[1] : ''; };
  const blocks = String(xml).match(/<(item|entry)[\s>][\s\S]*?<\/\1>/gi) || [];
  const items = blocks.slice(0, 30).map(b => {
    const title = clean(tag(b, 'title'), 120);
    const text = clean(tag(b, 'description') || tag(b, 'summary') || tag(b, 'content') || tag(b, 'content:encoded'), 400);
    const link = (b.match(/<link[^>]*href="([^"]+)"/i) || [])[1] || clean(tag(b, 'link'), 300);
    const id = clean(tag(b, 'guid') || tag(b, 'id'), 300) || link || title;
    const created = Date.parse(clean(tag(b, 'pubDate') || tag(b, 'updated') || tag(b, 'published') || tag(b, 'dc:date'), 60)) || 0;
    return { key: hash(id), title, text: text || title, severity: 'info', created };
  }).filter(i => i.title || i.text);
  return { services: [], items };
}

function parseJson(d) {
  const services = (Array.isArray(d.services) ? d.services : []).slice(0, 200).map(s => ({
    key: hash(String(s.id ?? s.name)), name: clean(s.name, 40), status: STATUSES.includes(s.status) ? s.status : 'degraded',
    title: clean(s.title, 120), phase: clean(s.phase, 30), note: clean(s.note, 400), started: Date.parse(s.since) || 0,
  })).filter(s => s.name);
  const items = (Array.isArray(d.items) ? d.items : []).slice(0, 30).map(i => ({
    key: hash(String(i.id ?? (i.title || '') + (i.text || ''))), title: clean(i.title, 120), text: clean(i.text, 400) || clean(i.title, 120),
    severity: SEVERITIES.includes(i.severity) ? i.severity : 'info', created: Date.parse(i.created) || 0,
  })).filter(i => i.text);
  return { services, items };
}

async function get(url) {
  const r = await fetch(url, { signal: AbortSignal.timeout(10000), redirect: 'follow', headers: { 'user-agent': 'uptime24/1.0', accept: '*/*' } });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const t = await r.text();
  if (t.length > 3e6) throw new Error('Response is too large');
  return t;
}
const asJson = t => { try { return JSON.parse(t); } catch (_) { throw new Error('Response is not JSON'); } };

async function fetchChannel(ch) {
  if (ch.type === 'statuspage') {
    const url = /\.json(\?|$)/.test(ch.url) ? ch.url : ch.url.replace(/\/+$/, '') + '/api/v2/summary.json';
    return parseStatuspage(asJson(await get(url)));
  }
  if (ch.type === 'rss') return parseFeed(await get(ch.url));
  if (ch.type === 'json') return parseJson(asJson(await get(ch.url)));
  if (ch.type === 'http') {
    let note = '';
    try {
      const r = await fetch(ch.url, { signal: AbortSignal.timeout(10000), redirect: 'follow', headers: { 'user-agent': 'uptime24/1.0' } });
      if (r.body) r.body.cancel().catch(() => {});
      if (r.status >= 400) note = 'The check received HTTP ' + r.status + '.';
    } catch (e) { note = e.name === 'TimeoutError' ? 'The check timed out after 10 seconds.' : 'The check could not connect.'; }
    return { services: [{ key: 'check', name: clean(ch.name, 40), status: note ? 'outage' : 'operational', note }], items: [] };
  }
  throw new Error('Unknown channel type');
}

module.exports = { TYPES, SEVERITIES, clean, parseStatuspage, parseFeed, parseJson, fetchChannel };
