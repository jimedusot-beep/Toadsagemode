/* Sage Studio Explorer V1 — strict fixture adapter, NO backend or execution API.
 * Agent A will define docs/SAGECODE_V1_CONTRACT.md separately.
 * Never reinterpret fixture statuses as actual tests, receipts or releases.
 */
(() => {
  'use strict';

  const SCHEMA = 'toad-sage-explorer-fixture-v1';
  const STATES = Object.freeze(['draft', 'untested', 'testing', 'failed', 'verified', 'blocked']);
  const MAX_CATALOG_CHARS = 100000;
  const MAX_SOURCE_CHARS = 12000;
  const ID = /^[a-z][a-z0-9-]{1,39}$/;
  const PATH = /^[A-Za-z0-9_./-]{1,120}$/;

  function fail(message) { throw new Error('Fixture invalid: ' + message); }
  function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function keys(value, expected, where) {
    if (!object(value) || Object.keys(value).sort().join('|') !== expected.slice().sort().join('|')) fail(where + ' fields');
  }
  function short(value, max, where, allowEmpty = false) {
    if (typeof value !== 'string' || value.length > max || (!allowEmpty && !value.trim()) ||
        value.includes('\u0000')) fail(where + ' must be bounded text');
    return value;
  }
  function pathName(value) {
    if (typeof value !== 'string' || !PATH.test(value) ||
        value.startsWith('/') || value.endsWith('/') || value.includes('//') ||
        value.split('/').some(part => part === '.' || part === '..')) fail('unsafe file path');
    return value;
  }
  function state(value, where) {
    if (!STATES.includes(value)) fail(where + ' is not a supported status');
    return value;
  }
  function testRecord(value, where) {
    keys(value, ['status', 'output'], where);
    return {status: state(value.status, where), output: short(value.output, 4000, where + ' output', true)};
  }
  function validateCatalog(raw) {
    if (!object(raw) || JSON.stringify(raw).length > MAX_CATALOG_CHARS) fail('catalog size or shape');
    keys(raw, ['schema', 'projects'], 'catalog');
    if (raw.schema !== SCHEMA || !Array.isArray(raw.projects) || raw.projects.length > 20) fail('schema or project limit');
    const ids = new Set();
    const projects = raw.projects.map(item => {
      keys(item, ['id', 'title', 'summary', 'state', 'files', 'revision', 'test'], 'project');
      if (typeof item.id !== 'string' || !ID.test(item.id) || ids.has(item.id)) fail('duplicate/invalid project ID');
      ids.add(item.id);
      if (!Array.isArray(item.files) || item.files.length > 24) fail('file limit');
      const paths = new Set();
      const files = item.files.map(file => {
        keys(file, ['path', 'content'], 'file');
        const path = pathName(file.path);
        if (paths.has(path)) fail('duplicate file');
        paths.add(path);
        return {path, content: short(file.content, MAX_SOURCE_CHARS, 'source', true)};
      });
      let revision = null;
      if (item.revision !== null) {
        keys(item.revision, ['id', 'path', 'before', 'after', 'status', 'test'], 'revision');
        const r = item.revision;
        if (typeof r.id !== 'string' || !ID.test(r.id)) fail('revision ID');
        const target = pathName(r.path);
        const actual = files.find(file => file.path === target);
        if (!actual) fail('revision targets a missing file');
        const before = short(r.before, MAX_SOURCE_CHARS, 'before source', true);
        if (before !== actual.content) fail('revision before-source differs from displayed file');
        revision = {
          id: r.id, path: target, before,
          after: short(r.after, MAX_SOURCE_CHARS, 'after source', true),
          status: state(r.status, 'revision state'),
          test: testRecord(r.test, 'revision test')
        };
      }
      return {
        id: item.id,
        title: short(item.title, 100, 'project title'),
        summary: short(item.summary, 240, 'project summary', true),
        state: state(item.state, 'project state'),
        files,
        revision,
        test: testRecord(item.test, 'project test')
      };
    });
    return {schema: SCHEMA, source: 'local-fixture-only', projects};
  }
  // Exact line-by-line longest-common-subsequence matching for a bounded
  // change region. For oversized inputs, explicitly label a COARSE comparison
  // rather than silently pretending every highlighted middle line changed.
  const MAX_DIFF_CELLS = 160000;
  function compareSource(before, after) {
    if (typeof before !== 'string' || typeof after !== 'string' ||
        before.length > MAX_SOURCE_CHARS || after.length > MAX_SOURCE_CHARS) {
      fail('comparison requires bounded source text');
    }
    const left = before.split('\n');
    const right = after.split('\n');
    let prefix = 0;
    while (prefix < left.length && prefix < right.length &&
           left[prefix] === right[prefix]) prefix++;
    let suffix = 0;
    while (suffix < left.length - prefix && suffix < right.length - prefix &&
           left[left.length - 1 - suffix] === right[right.length - 1 - suffix]) suffix++;
    const result = [];
    for (let i = 0; i < prefix; i++) result.push({kind: 'same', text: left[i]});
    const a = left.slice(prefix, left.length - suffix);
    const b = right.slice(prefix, right.length - suffix);
    let mode = 'exact';
    if (a.length && b.length && a.length * b.length <= MAX_DIFF_CELLS) {
      const width = b.length + 1;
      const scores = new Uint16Array((a.length + 1) * width);
      for (let i = a.length - 1; i >= 0; i--) {
        for (let j = b.length - 1; j >= 0; j--) {
          const offset = i * width + j;
          scores[offset] = a[i] === b[j] ?
            1 + scores[offset + width + 1] :
            Math.max(scores[offset + width], scores[offset + 1]);
        }
      }
      let i = 0, j = 0;
      while (i < a.length || j < b.length) {
        if (i < a.length && j < b.length && a[i] === b[j]) {
          result.push({kind: 'same', text: a[i++]}); j++;
        } else if (i < a.length && (j === b.length ||
                   scores[(i + 1) * width + j] >= scores[i * width + j + 1])) {
          result.push({kind: 'removed', text: a[i++]});
        } else {
          result.push({kind: 'added', text: b[j++]});
        }
      }
    } else {
      // Added-only and deleted-only blocks are exact without a score grid.
      if (a.length && b.length) mode = 'coarse';
      for (const text of a) result.push({kind: 'removed', text});
      for (const text of b) result.push({kind: 'added', text});
    }
    for (let i = left.length - suffix; i < left.length; i++) {
      result.push({kind: 'same', text: left[i]});
    }
    let added = 0, removed = 0, hunks = 0, active = false;
    for (const entry of result) {
      if (entry.kind === 'same') { active = false; continue; }
      if (!active) { hunks++; active = true; }
      if (entry.kind === 'added') added++;
      else removed++;
    }
    return {lines: result, mode, added, removed, hunks};
  }
  function diffLines(before, after) {
    return compareSource(before, after).lines;
  }
  async function loadFixtures(fetcher) {
    const response = await fetcher('./explorer-fixtures.json', {cache: 'no-store'});
    if (!response || !response.ok) throw new Error('Fixture catalog unavailable. Nothing was loaded.');
    if (Number(response.headers?.get('content-length')) > MAX_CATALOG_CHARS * 4)
      throw new Error('Fixture catalog is too large.');
    const text = await response.text();
    if (text.length > MAX_CATALOG_CHARS) throw new Error('Fixture catalog is too large.');
    let raw;
    try { raw = JSON.parse(text); }
    catch (_) { throw new Error('Fixture catalog is not valid JSON.'); }
    return validateCatalog(raw);
  }
  const api = Object.freeze({SCHEMA, STATES, validateCatalog, compareSource, diffLines, loadFixtures});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.SageExplorerAdapter = api;
})();
