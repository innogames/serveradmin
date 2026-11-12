'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { parseStatuspage, parseFeed, parseJson, clean } = require('../lib/sources');

test('clean strips markup, entities and control characters', () => {
  // feeds often carry entity-encoded HTML, so encoded tags are removed like literal ones
  assert.equal(clean('<p>Fish &amp; chips&nbsp;&lt;br&gt;</p>\n<![CDATA[ <b>hot</b> ]]>', 100), 'Fish & chips hot');
  assert.equal(clean('abcdefghij', 5), 'abcd…');
  assert.equal(clean(undefined, 5), '');
});

test('statuspage: components become services and carry their incident', () => {
  const out = parseStatuspage({
    components: [
      { id: 'g', name: 'Group', status: 'operational', group: true },
      { id: 'a', name: 'API', status: 'major_outage' },
      { id: 'b', name: 'Web', status: 'operational' },
      { id: 'c', name: 'Mail', status: 'under_maintenance' },
    ],
    incidents: [
      { id: 'i1', name: 'API errors', status: 'identified', impact: 'major', created_at: '2026-01-01T10:00:00Z',
        components: [{ id: 'a' }], incident_updates: [{ body: '<p>Fix is <b>rolling</b> out.</p>' }, { body: 'older' }] },
      { id: 'i2', name: 'Billing emails delayed', status: 'investigating', impact: 'minor', created_at: '2026-01-01T11:00:00Z', incident_updates: [] },
      { id: 'i3', name: 'Old one', status: 'resolved', components: [{ id: 'b' }] },
    ],
  });
  assert.deepEqual(out.services.map(s => [s.name, s.status]), [['API', 'outage'], ['Web', 'operational'], ['Mail', 'maintenance']]);
  assert.equal(out.services[0].title, 'API errors');
  assert.equal(out.services[0].phase, 'Identified');
  assert.equal(out.services[0].note, 'Fix is rolling out.');
  assert.equal(out.services[0].started, Date.parse('2026-01-01T10:00:00Z'));
  assert.equal(out.services[2].title, undefined);
  assert.deepEqual(out.items.map(i => [i.title, i.severity]), [['Billing emails delayed', 'degraded']]);
});

test('feed: reads RSS items and Atom entries', () => {
  const rss = parseFeed(`<rss><channel><title>Feed</title>
    <item><title>One &amp; only</title><description><![CDATA[<p>Hello <i>there</i></p>]]></description>
      <guid>g1</guid><pubDate>Mon, 05 Jan 2026 10:00:00 GMT</pubDate></item>
    <item><title>Two</title><link>https://example.com/2</link></item></channel></rss>`);
  assert.equal(rss.items.length, 2);
  assert.equal(rss.items[0].title, 'One & only');
  assert.equal(rss.items[0].text, 'Hello there');
  assert.equal(rss.items[0].created, Date.parse('2026-01-05T10:00:00Z'));
  assert.equal(rss.items[1].text, 'Two');
  assert.notEqual(rss.items[0].key, rss.items[1].key);
  const atom = parseFeed(`<feed><entry><title type="html">Release</title><id>tag:1</id>
    <updated>2026-02-01T00:00:00Z</updated><summary>&lt;p&gt;Notes&lt;/p&gt;</summary><link href="https://example.com/r"/></entry></feed>`);
  assert.deepEqual([atom.items[0].title, atom.items[0].text, atom.items[0].created], ['Release', 'Notes', Date.parse('2026-02-01T00:00:00Z')]);
});

test('json: accepts the documented shape and ignores junk', () => {
  const out = parseJson({ services: [{ name: 'Shop', status: 'outage', note: 'Down' }, { name: 'Odd', status: 'weird' }, { status: 'outage' }],
    items: [{ title: 'Hi', text: 'There', severity: 'good' }, { severity: 'good' }] });
  assert.deepEqual(out.services.map(s => [s.name, s.status]), [['Shop', 'outage'], ['Odd', 'degraded']]);
  assert.deepEqual(out.items.map(i => [i.title, i.severity]), [['Hi', 'good']]);
  assert.deepEqual(parseJson({}), { services: [], items: [] });
});
