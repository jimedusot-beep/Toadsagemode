/* SageCode Contract Inspector: strict, LOCAL-FIXTURE-only adapter.
 * Matches the shapes in Agent A's draft docs/SAGECODE_V1_CONTRACT.md.
 * Nothing here authenticates a server, grants approval, or runs source.
 */
(() => {
  'use strict';
  const SCHEMA = 'sagecode-ui-fixture-v1';
  const MAX_FIXTURE_CHARS = 100000;
  const SHA = /^[0-9a-f]{64}$/;
  const PROJECT = /^[a-z][a-z0-9_-]{1,63}$/;
  const PATH = /^[A-Za-z0-9_./-]{1,120}$/;
  const encoder = new TextEncoder();
  function fail(reason) { throw new Error('SageCode sample rejected: ' + reason); }
  function obj(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }
  function fields(x, keys, what) {
    if (!obj(x) || Object.keys(x).sort().join('|') !== keys.slice().sort().join('|')) {
      fail(what + ' fields');
    }
  }
  function str(s, max, what, empty = false) {
    if (typeof s !== 'string' || s.length > max || (!empty && !s) ||
        /[\u0000]/.test(s)) fail(what + ' text');
    return s;
  }
  function hex(s, what) { if (typeof s !== 'string' || !SHA.test(s)) fail(what + ' digest'); return s; }
  function projectId(s) { if (typeof s !== 'string' || !PROJECT.test(s)) fail('project ID'); return s; }
  function path(s) {
    if (typeof s !== 'string' || !PATH.test(s) || s[0] === '/' ||
        s.endsWith('/') || s.includes('//') ||
        s.split('/').some(p => p === '.' || p === '..')) fail('unsafe source path');
    return s;
  }
  function integer(n, min, max, what) {
    if (!Number.isSafeInteger(n) || n < min || n > max) fail(what + ' bounds');
    return n;
  }
  function isBool(x, what) { if (typeof x !== 'boolean') fail(what + ' boolean'); return x; }
  function rejectAuthority(x, what) {
    if (x.verification !== 'unverified' || x.release_allowed !== false ||
        ('review_status' in x && x.review_status !== 'pending_review') ||
        ('approved' in x && x.approved !== false) ||
        ('executed' in x && x.executed !== false)) fail(what + ' falsely claims authority');
  }
  function utf8(s) { return encoder.encode(s).length; }
  function countLines(s) {
    if (!s) return 0;
    return s.split(/\r\n|\n|\r/).length - (/\r\n$|\n$|\r$/.test(s) ? 1 : 0);
  }
  function validateFixture(input) {
    if (!obj(input) || JSON.stringify(input).length > MAX_FIXTURE_CHARS) fail('size/structure');
    fields(input, ['fixture_schema','status','tree','sources','search','proposal'], 'fixture');
    if (input.fixture_schema !== SCHEMA) fail('unsupported fixture schema');
    const status = input.status;
    fields(status, ['schema','project_id','revision','baseline_revision','verification',
      'review_status','executed','approved','release_allowed','test_evidence'], 'status');
    if (status.schema !== 'sagecode-project-status-v1') fail('SageCode status schema');
    const id = projectId(status.project_id);
    hex(status.revision, 'current revision');
    hex(status.baseline_revision, 'baseline revision');
    isBool(status.executed, 'executed');
    isBool(status.approved, 'approved');
    isBool(status.release_allowed, 'release');
    if (status.test_evidence !== null) fail('V1 may not claim test receipts');
    rejectAuthority(status, 'status');
    const revision = status.revision;
    const tree = input.tree;
    fields(tree, ['project_id','revision','entries'], 'tree');
    if (tree.project_id !== id || tree.revision !== revision ||
        !Array.isArray(tree.entries) || tree.entries.length > 80) fail('tree revision or limits');
    const files = new Map(), directories = new Set(), treePaths = new Set();
    for (const entry of tree.entries) {
      if (!obj(entry) || typeof entry.kind !== 'string') fail('file tree entry');
      const name = path(entry.path);
      if (treePaths.has(name)) fail('duplicate tree entry');
      treePaths.add(name);
      if (entry.kind === 'directory') {
        fields(entry, ['path','kind'], 'directory');
        directories.add(name);
      } else if (entry.kind === 'file') {
        fields(entry, ['path','kind','bytes','sha256'], 'file');
        integer(entry.bytes,0,250000,'file byte length');
        hex(entry.sha256,'file');
        files.set(name,entry);
      } else fail('unknown entry kind');
    }
    if (files.size > 40) fail('file count');
    for (const name of files.keys()) {
      const parts = name.split('/');
      for (let k=1;k<parts.length;k++) {
        if (!directories.has(parts.slice(0,k).join('/'))) fail('missing derived directory');
      }
    }
    for (const name of directories) {
      if (![...files.keys()].some(file=>file.startsWith(name+'/'))) fail('orphan directory');
    }
    if (!Array.isArray(input.sources) || input.sources.length !== files.size) fail('source view count');
    const sources = new Map();
    for (const source of input.sources) {
      fields(source, ['project_id','revision','path','start_line','total_lines',
        'content','truncated','sha256'], 'source');
      const name = path(source.path), entry = files.get(name);
      if (!entry || sources.has(name) || source.project_id !== id ||
          source.revision !== revision || source.sha256 !== entry.sha256) {
        fail('source differs from project/revision/tree');
      }
      integer(source.start_line,1,100000,'starting line');
      integer(source.total_lines,0,100000,'total lines');
      isBool(source.truncated,'source truncation');
      str(source.content,16000,'source',true);
      if (utf8(source.content) > 16000) fail('source read exceeds 16 kB');
      if (!source.truncated) {
        if (source.start_line !== 1 || utf8(source.content) !== entry.bytes ||
            countLines(source.content) !== source.total_lines) fail('full source metadata mismatch');
      } else if (source.start_line > Math.max(1,source.total_lines)) {
        fail('partial source start beyond total lines');
      }
      sources.set(name,source);
    }
    const search = input.search;
    fields(search,['project_id','revision','term','matches','limited'],'search');
    if (search.project_id !== id || search.revision !== revision) fail('search wrong project/revision');
    str(search.term,100,'search term');
    if (utf8(search.term)>100 || /[\u0000-\u001f\u007f]/.test(search.term)) fail('invalid search term');
    isBool(search.limited,'search limit');
    if (!Array.isArray(search.matches) || search.matches.length>100) fail('search hits');
    for (const hit of search.matches) {
      fields(hit,['path','line','snippet','kind'],'search hit');
      const name = path(hit.path);
      const source = sources.get(name);
      if (!source) fail('search hit outside declared files');
      integer(hit.line,0,100000,'search hit line');
      str(hit.snippet,200,'search snippet',true);
      if (hit.kind === 'filename') {
        if (hit.line !== 0) fail('filename matches must use line zero');
      } else if (hit.kind === 'content') {
        if (hit.line < 1 || hit.line > source.total_lines) fail('content line out of range');
      } else fail('search hit kind');
    }
    let proposal = null;
    if (input.proposal !== null) {
      proposal=input.proposal;
      fields(proposal,['project_id','revision','parent_revision','unchanged','diff',
        'truncated','verification','review_status','release_allowed'],'proposal');
      if (proposal.project_id !== id || proposal.parent_revision !== revision ||
          hex(proposal.revision,'proposed revision') === revision) fail('proposal ancestry');
      isBool(proposal.unchanged,'unchanged');
      isBool(proposal.truncated,'proposal truncation');
      if (proposal.unchanged) fail('fixture proposal must represent a change');
      str(proposal.diff,30000,'proposal diff',true);
      if (utf8(proposal.diff)>30000) fail('proposal diff bytes');
      rejectAuthority(proposal,'proposal');
    }
    return {schema:SCHEMA,origin:'local-fixture-only',status,tree,sources:[...sources.values()],search,proposal};
  }
  async function validateHashes(view, subtle) {
    if (!subtle || typeof subtle.digest !== 'function') fail('SHA-256 unavailable; source cannot be checked');
    const results = [];
    for (const source of view.sources) {
      if (source.truncated) {
        results.push({path:source.path,check:'partial_view_not_hash_verified'});
        continue;
      }
      const bytes=encoder.encode(source.content);
      let digest;
      try { digest=await subtle.digest('SHA-256',bytes); }
      catch (_) { fail('source hash check unavailable'); }
      const actual=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
      if (actual!==source.sha256) fail('source content SHA-256 mismatch');
      results.push({path:source.path,check:'fixture_hash_matches'});
    }
    return {view,results,fixture_consistency_only:true};
  }
  async function loadFixture(fetcher,subtle) {
    const response=await fetcher('./sagecode-contract-fixture.json',{cache:'no-store'});
    if (!response || !response.ok) throw Error('SageCode fixture unavailable.');
    if (Number(response.headers?.get('content-length'))>MAX_FIXTURE_CHARS*4)
      fail('fixture response too large');
    const raw=await response.text();
    if (raw.length>MAX_FIXTURE_CHARS) fail('fixture text too large');
    let parsed;
    try {parsed=JSON.parse(raw);}
    catch (_) {fail('fixture JSON not valid');}
    return validateHashes(validateFixture(parsed),subtle);
  }
  const api=Object.freeze({SCHEMA,validateFixture,validateHashes,loadFixture,countLines});
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  if (typeof window!=='undefined') window.SageCodeContractAdapter=api;
})();
