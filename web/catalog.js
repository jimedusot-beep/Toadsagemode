/* Pure, nonexecuting data operations shared by the inbox and its tests. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ToadCatalog = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const LIMITS = Object.freeze({file:250000, package:512000, backup:2000000, files:40, items:100});
  const STATUSES = ['received','inspected','needs_review','ready_for_testing','testing','failed','verified','installed','archived'];
  const EXTENSIONS = {py:'Python', js:'JavaScript', mjs:'JavaScript', html:'HTML', css:'CSS', json:'JSON', md:'Markdown', txt:'Text', toml:'TOML', yml:'YAML', yaml:'YAML', ini:'Text', cfg:'Text'};
  const encoder = new TextEncoder();
  const bytes = value => encoder.encode(value).length;
  const clone = value => JSON.parse(JSON.stringify(value));
  function parseJSON(text) {
    const data=JSON.parse(text), stack=[];
    for(const token of text.match(/"(?:\\.|[^"\\])*"|[{}\[\],:]/g) || []) {
      const top=stack[stack.length-1];
      if(token==='{' || token==='[')stack.push({object:token==='{',key:true,keys:new Set()});
      else if(token==='}' || token===']')stack.pop();
      else if(token===',' && top && top.object)top.key=true;
      else if(token[0]==='"' && top && top.object && top.key){const key=JSON.parse(token);if(top.keys.has(key))throw Error('Duplicate JSON key');top.keys.add(key);top.key=false;}
    }
    return data;
  }
  const now = () => new Date().toISOString();
  const uid = () => typeof crypto === 'object' && crypto.randomUUID ? crypto.randomUUID() : 'local-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
  const slug = value => String(value || 'new-ability').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,64) || 'new-ability';
  const language = path => EXTENSIONS[path.split('.').pop().toLowerCase()] || 'Text';
  function safePath(path) {
    if (typeof path !== 'string' || path.length > 180 || !path || /[\\:\x00-\x1f]/.test(path)) throw Error('Invalid file path');
    const parts = path.split('/');
    for (const p of parts) {
      if (!/^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(p) || p === '..' || p === '.' || /[. ]$/.test(p) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(p)) throw Error('File path is not portable');
    }
    if (['toad_core','core','policy','security'].includes(parts[0].toLowerCase())) throw Error('Protected core path');
    if (!EXTENSIONS[path.split('.').pop().toLowerCase()]) throw Error('Unsupported file path extension');
    return path;
  }
  function stringList(value, label) {
    if (!Array.isArray(value) || value.length > 40 || value.some(x=>typeof x !== 'string' || !x.trim() || x.length > 200 || /[\x00-\x1f]/.test(x))) throw Error('Invalid '+label+' list');
    return [...new Set(value)];
  }
  function normalizeManifest(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data) || !['toad-ability-v1','toad-ability-v2'].includes(data.schema)) throw Error('Unsupported package schema');
    if (bytes(JSON.stringify(data)) > LIMITS.package) throw Error('Package exceeds size limit');
    if (typeof data.name !== 'string' || !/^[a-z][a-z0-9_-]{1,63}$/.test(data.name)) throw Error('Invalid package name');
    if (typeof data.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(data.version)) throw Error('Invalid version');
    if (!Array.isArray(data.files) || !data.files.length || data.files.length > LIMITS.files) throw Error('Package needs 1–40 files');
    const seen = new Set();
    const files = data.files.map(f=>{
      if (!f || typeof f !== 'object') throw Error('Invalid file record');
      safePath(f.path);
      const key = f.path.toLowerCase();
      if (seen.has(key)) throw Error('Duplicate file path');
      for (const prev of seen) if (key.startsWith(prev+'/') || prev.startsWith(key+'/')) throw Error('Conflicting file paths');
      seen.add(key);
      if (typeof f.content !== 'string' || f.content.includes('\u0000') || bytes(f.content) > LIMITS.file) throw Error('Invalid or oversized file content');
      const extra = Object.fromEntries(Object.entries(f).filter(([k])=>!['path','content','extensions'].includes(k)));
      return {path:f.path,content:f.content,extensions:{...(f.extensions || {}),...extra}};
    });
    const entrypoint = data.entrypoint === undefined ? files[0].path : data.entrypoint;
    if (!files.some(f=>f.path===entrypoint)) throw Error('Entrypoint must be a listed file');
    const permissions = stringList(data.permissions || [], 'permissions');
    const dependencies = stringList(data.dependencies || [], 'dependencies');
    if(permissions.some(p=>!(/^[a-z][a-z0-9_.:-]{0,99}$/.test(p))))throw Error('Invalid permission name');
    if(dependencies.some(p=>!(/^[A-Za-z0-9][A-Za-z0-9_.-]*(?:[<>=!~]=?[A-Za-z0-9.*+_-]+(?:,[<>=!~]=?[A-Za-z0-9.*+_-]+)*)?$/.test(p))))throw Error('Invalid dependency specification');
    if(data.description!==undefined && (typeof data.description!=='string' || data.description.length>4000))throw Error('Invalid description');
    if(data.extensions!==undefined && (!data.extensions || typeof data.extensions!=='object' || Array.isArray(data.extensions)))throw Error('Invalid extensions object');
    if(data.compatibility!==undefined && (!data.compatibility || typeof data.compatibility!=='object' || Array.isArray(data.compatibility)))throw Error('Invalid compatibility object');
    if (!Array.isArray(data.tests || []) || (data.tests || []).length > 10) throw Error('Invalid tests');
    const legacy = [], tests = [];
    for (const t of data.tests || []) {
      if (typeof t === 'string' && data.schema === 'toad-ability-v1') { legacy.push(t); continue; }
      if (!t || typeof t !== 'object' || !['python','unittest'].includes(t.kind)) throw Error('Unsupported test specification');
      if (t.kind === 'python') {
        safePath(t.path);
        if (!files.some(f=>f.path===t.path) || !t.path.endsWith('.py') || typeof t.expected_stdout !== 'string' || bytes(t.expected_stdout)>16000) throw Error('Python tests require a file and expected_stdout');
      } else {
        if (typeof t.path !== 'string' || !/^[A-Za-z0-9_][A-Za-z0-9_/-]*$/.test(t.path) || t.path.split('/').some(p=>!p) || !files.some(f=>f.path.startsWith(t.path+'/') && /\/test[^/]*\.py$/.test(f.path))) throw Error('Unittest requires a directory with tests');
      }
      tests.push(clone(t));
    }
    const known=['schema','name','version','description','files','entrypoint','permissions','dependencies','tests','compatibility','extensions'];
    const extra = Object.fromEntries(Object.entries(data).filter(([k])=>!known.includes(k)));
    return {schema:'toad-ability-v2',name:data.name,version:data.version,description:typeof data.description==='string'?data.description.slice(0,4000):'',files,entrypoint,permissions,dependencies,tests,compatibility:clone(data.compatibility || {operating_systems:['unknown']}),extensions:{...(data.extensions||{}),...extra,...(legacy.length?{legacy_tests:legacy}:{})}};
  }
  function detect(text) {
    if (/^\s*(?:from\s+\w+\s+import|import\s+\w+|def\s+\w+\s*\(|class\s+\w+|print\s*\()/m.test(text)) return ['Python','py'];
    if (/^\s*(?:<!doctype html|<(?:html|div|body|img|h[1-6]|p|script)\b)/i.test(text)) return ['HTML','html'];
    if (/^\s*[\[{]/.test(text)) return ['JSON','json'];
    if (/\b(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=|console\.log\s*\()/.test(text)) return ['JavaScript','js'];
    if (/^[.#]?[\w-]+\s*\{[^}]*:[^}]*\}/m.test(text)) return ['CSS','css'];
    return [/^\s*#|```/.test(text)?'Markdown':'Text','md'];
  }
  function inspect(manifest) {
    const errors=[], warnings=[];
    const observations=[], assumptions=['Purpose and compatibility may need human review.','Pattern scanning cannot establish safety.'];
    for (const f of manifest.files) {
      if (f.path.endsWith('.json')) { try { parseJSON(f.content); } catch (_) { errors.push(f.path+': invalid JSON syntax'); } }
      for (const [rx,note] of [
        [/\b(?:exec\s*\(|eval\s*\(|subprocess\.|os\.system)/i,'Dynamic or host command execution indicator'],
        [/\b(?:rmtree|unlink\s*\(|os\.remove|rm\s+-rf)/i,'Deletion indicator'],
        [/\b(?:requests\.|urllib\.|fetch\s*\(|https?:\/\/)/i,'Network or reference URL'],
        [/\b(?:password|secret|api[_-]?key|token)\s*[:=]|BEGIN [A-Z ]*PRIVATE KEY/i,'Potential secret'],
        [/\b(?:sudo|chmod|chown|docker\s+run)/i,'Privilege indicator']
      ]) if (rx.test(f.content)) warnings.push(f.path+': '+note);
    }
    if (manifest.permissions.length) warnings.push('Requested permissions require policy review');
    if (manifest.extensions.legacy_tests) warnings.push('Legacy shell-style tests were preserved, not enabled');
    const langs=[...new Set(manifest.files.map(f=>language(f.path)))];
    observations.push(manifest.files.length+' text/source file(s)', 'Languages: '+langs.join(', '));
    return {valid_structure:true,errors,warnings,observations,assumptions,syntax_checked:manifest.files.filter(f=>f.path.endsWith('.json')).map(f=>f.path),syntax_unchecked:manifest.files.filter(f=>!f.path.endsWith('.json')).map(f=>f.path),executed:false,safe_to_run:'not_assessed'};
  }
  function createCandidate(text, options) {
    options=options || {};
    if (typeof text !== 'string' || !text.trim()) throw Error('Paste material or choose a source file first');
    if (bytes(text)>LIMITS.file) throw Error('Input exceeds the 250,000 byte limit');
    const original=text;
    let manifest;
    let parsed;
    try { parsed=parseJSON(text); } catch (_) { /* Invalid ordinary JSON is retained for inspection. */ }
    if(parsed && typeof parsed.schema==='string' && parsed.schema.startsWith('toad-ability-'))manifest=normalizeManifest(parsed);
    if (!manifest) {
      const files=[];
      const aliases={python:'py',py:'py',javascript:'js',js:'js',html:'html',css:'css',json:'json',markdown:'md',md:'md',text:'txt',txt:'txt'};
      const blocks=[...text.matchAll(/^```([^\n\r]*)\r?\n([\s\S]*?)^```\s*$/gm)];
      for (let i=0;i<blocks.length;i++) {
        const info=blocks[i][1].trim().split(/\s+/), ext=aliases[info[0].toLowerCase()] || 'txt';
        const path=info[1] || (blocks.length===1?'main.'+ext:'part-'+(i+1)+'.'+ext);
        files.push({path,content:blocks[i][2]});
      }
      const detected=detect(text);
      if (!files.length) files.push({path:options.filename || (detected[1]==='md'?'notes.md':'main.'+detected[1]),content:text});
      const title=options.name || (files.length>1?'project-package':detected[0]==='Text'?text.trim().split(/[\n.!?]/)[0].slice(0,55):detected[0]+'-ability');
      let name=slug(title); if (!/^[a-z]/.test(name)) name='toad-'+name; if (name.length<2) name+='-ability';
      manifest=normalizeManifest({schema:'toad-ability-v2',name:name.slice(0,64),version:'0.1.0',description:options.description || text.trim().split('\n')[0].slice(0,300),files,entrypoint:files[0].path,tests:[],permissions:[],dependencies:[]});
    }
    if (options.name) { manifest.name=slug(options.name); if (!/^[a-z][a-z0-9_-]{1,63}$/.test(manifest.name)) throw Error('Choose a name beginning with a letter'); }
    const report=inspect(manifest), timestamp=now();
    const langs=[...new Set(manifest.files.map(f=>language(f.path)))];
    return {id:uid(),name:manifest.name,description:options.description || manifest.description,version:manifest.version,source:options.source || 'manual paste',created_at:timestamp,updated_at:timestamp,language:langs.length===1?langs[0]:'Mixed',content:original,manifest,dependencies:manifest.dependencies,permissions:manifest.permissions,compatibility:manifest.compatibility,status:report.errors.length || report.warnings.length?'needs_review':'inspected',verification:'unverified',installed:false,validation_results:report,test_results:[],previous_versions:[],rollback:null,related_missions:[],history:[{event:'received',at:timestamp},{event:'inspected',at:timestamp}],extensions:{}};
  }
  function normalizeLibrary(data, trustedLocal) {
    if (!data || !['toad-library-v1','toad-library-v2'].includes(data.schema) || !Array.isArray(data.abilities) || data.abilities.length>LIMITS.items) throw Error('Unsupported library format or item limit');
    if (bytes(JSON.stringify(data))>LIMITS.backup) throw Error('Library exceeds backup size limit');
    const ids=new Set();
    const abilities=data.abilities.map(a=>{
      if (!a || typeof a.name!=='string' || typeof a.content!=='string') throw Error('Invalid ability record or content');
      if (!/^[a-z][a-z0-9_-]{1,63}$/.test(a.name)) throw Error('Invalid ability name');
      if(bytes(a.content)>(a.manifest?LIMITS.package:LIMITS.file))throw Error('Ability content exceeds size limit');
      const r=createCandidate(a.manifest?'Structured source package':a.content,{name:a.name,description:typeof a.description==='string'?a.description:'',source:typeof a.source==='string'?a.source:'backup import'});
      r.content=a.content;
      if (a.manifest) { r.manifest=normalizeManifest(a.manifest); r.name=r.manifest.name; r.version=r.manifest.version; r.validation_results=inspect(r.manifest); r.dependencies=r.manifest.dependencies; r.permissions=r.manifest.permissions; r.compatibility=r.manifest.compatibility; r.language=[...new Set(r.manifest.files.map(f=>language(f.path)))].join(', '); }
      r.id=typeof a.id==='string' && /^[A-Za-z0-9_-]{1,100}$/.test(a.id)?a.id:r.id;
      if (ids.has(r.id)) throw Error('Duplicate ability identifier'); ids.add(r.id);
      r.created_at=typeof a.created_at==='string'?a.created_at:r.created_at;
      r.extensions=trustedLocal?clone(a.extensions || {}):{original:clone(a)};
      // Only on-device states this browser can actually produce survive a local reload.
      if (trustedLocal && ['received','inspected','needs_review','archived'].includes(a.status)) {r.status=a.status; r.history=Array.isArray(a.history)?clone(a.history):r.history;}
      if (!trustedLocal) {r.history.push({event:'backup_imported_unverified',at:now()}); if(a.status==='archived')r.status='archived';}
      return r;
    });
    return {schema:'toad-library-v2',schema_version:2,abilities,extensions:trustedLocal?clone(data.extensions || {}):{original:Object.fromEntries(Object.entries(data).filter(([k])=>k!=='abilities'))}};
  }
  // Compare full execution-relevant data, not user-supplied IDs or hashes.
  function identity(r) { const m=r.manifest; return JSON.stringify([m.files.map(f=>[f.path,f.content]).sort((a,b)=>a[0].localeCompare(b[0])),m.entrypoint,m.tests,m.permissions,m.dependencies]); }
  function mergeLibraries(current,incoming) {
    const normalized=normalizeLibrary(incoming), library=clone(current), keys=new Set(library.abilities.map(identity));
    let added=0,duplicates=0;
    for (const r of normalized.abilities) {const key=identity(r); if(keys.has(key)){duplicates++;continue;} if(library.abilities.some(a=>a.id===r.id))r.id=uid();library.abilities.push(r);keys.add(key);added++;}
    if(library.abilities.length>LIMITS.items || bytes(JSON.stringify(library))>LIMITS.backup)throw Error('Merged library exceeds storage limit');
    return {library,added,duplicates};
  }
  function normalizeDraft(data) {
    const keys=['schema','content','name','description','source','has_files','saved_at'];
    if(!data || typeof data!=='object' || Array.isArray(data) || data.schema!=='toad-feed-draft-v1' || Object.keys(data).some(k=>!keys.includes(k)))throw Error('Unknown or invalid draft format; download it before clearing');
    for(const [key,limit] of [['content',LIMITS.file],['name',100],['description',4000],['source',200]]){
      if(typeof data[key]!=='string' || (key==='content'?bytes(data[key]):data[key].length)>limit)throw Error('Invalid or oversized draft field');
    }
    if(typeof data.has_files!=='boolean' || typeof data.saved_at!=='string' || data.saved_at.length>64 || !Number.isFinite(Date.parse(data.saved_at)))throw Error('Invalid draft metadata');
    return clone(data);
  }
  return Object.freeze({LIMITS,STATUSES,bytes,uid,safePath,language,normalizeManifest,createCandidate,normalizeLibrary,mergeLibraries,identity,inspect,parseJSON,normalizeDraft});
});
