/* Browser controller. Imported content is always rendered as text. */
(function () {
  'use strict';
  const $=id=>document.getElementById(id), C=window.ToadCatalog;
  const KEY='toad-ability-library-v2', LEGACY='toad-ability-library-v1';
  let library={schema:'toad-library-v2',schema_version:2,abilities:[],extensions:{}}, readable=false, rawStored=null;
  const selected=new Set();
  function notice(message,error){$('abilitymessage').textContent=message;$('abilitymessage').className=error?'error':'';}
  function element(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
  function download(data,name,type){const blob=new Blob([data],{type:type || 'application/json'}),url=URL.createObjectURL(blob),a=element('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
  function save(next){if(!readable)throw Error('Storage is unavailable or unreadable; recover it before saving.');const raw=JSON.stringify(next);if(C.bytes(raw)>C.LIMITS.backup)throw Error('Storage limit reached. Export a backup and remove old entries.');localStorage.setItem(KEY,raw);library=next;rawStored=raw;}
  function update(id,fn){const next=JSON.parse(JSON.stringify(library)),item=next.abilities.find(a=>a.id===id);if(!item)return;fn(item,next);save(next);render();}
  function render(){
    const root=$('abilityitems');root.textContent='';
    $('abilitycount').textContent=library.abilities.length+' candidates';
    const languages=[...new Set(library.abilities.map(a=>a.language))].sort(), chosen=$('languagefilter').value;
    $('languagefilter').textContent='';const all=element('option','All languages');all.value='';$('languagefilter').appendChild(all);
    languages.forEach(l=>{const o=element('option',l);o.value=l;$('languagefilter').appendChild(o);});$('languagefilter').value=languages.includes(chosen)?chosen:'';
    const query=$('searchabilities').value.toLowerCase(),status=$('statusfilter').value,lang=$('languagefilter').value;
    const items=library.abilities.filter(a=>(!query || [a.name,a.description,a.content,a.source].join(' ').toLowerCase().includes(query)) && (status==='all' || (status?a.status===status:a.status!=='archived')) && (!lang || a.language===lang));
    if(!items.length)root.appendChild(element('p',library.abilities.length?'No candidates match these filters.':'Your inbox is waiting. Paste something above and feed Toad.','small'));
    for(const item of items){
      const section=element('article',undefined,'ability');section.dataset.abilityId=item.id;
      const checklabel=element('label',undefined,'selectlabel'),check=element('input');check.type='checkbox';check.checked=selected.has(item.id);check.setAttribute('aria-label','Select '+item.name);check.onchange=()=>{if(check.checked)selected.add(item.id);else selected.delete(item.id);};checklabel.append(check,element('span',item.name));section.append(checklabel);
      section.appendChild(element('div',item.status.replaceAll('_',' ')+' · '+item.language+' · unverified','badge'));
      section.appendChild(element('p',item.description || 'No description yet.'));
      section.appendChild(element('p','Source: '+item.source+' · '+new Date(item.created_at).toLocaleString(),'small'));
      const actions=element('div',undefined,'actions');
      const archive=element('button',item.status==='archived'?'Restore':'Archive');archive.type='button';archive.onclick=()=>{try{update(item.id,a=>{a.status=a.status==='archived'?(a.validation_results.errors.length || a.validation_results.warnings.length?'needs_review':'inspected'):'archived';a.history.push({event:a.status==='archived'?'archived':'restored',at:new Date().toISOString()});});notice('Updated locally.');}catch(e){notice(e.message,true);}};
      const del=element('button','Delete','danger');del.type='button';del.onclick=()=>{if(!confirm('Delete '+item.name+' from this device? Export a backup first if you need it.'))return;try{const next={...library,abilities:library.abilities.filter(a=>a.id!==item.id)};save(next);selected.delete(item.id);render();notice('Deleted local candidate.');}catch(e){notice(e.message,true);}};
      actions.append(archive,del);section.appendChild(actions);
      const edit=element('details');edit.appendChild(element('summary','Edit name and description'));
      const name=element('input');name.value=item.name;name.maxLength=100;const desc=element('textarea');desc.value=item.description;desc.rows=2;desc.maxLength=4000;
      const nl=element('label','Name');nl.appendChild(name);const dl=element('label','Description');dl.appendChild(desc);const commit=element('button','Save changes');commit.type='button';commit.onclick=()=>{try{if(!name.value.trim())throw Error('A name is required.');update(item.id,a=>{const normalized=C.createCandidate(a.content,{name:name.value,description:desc.value,source:a.source});a.name=normalized.name;a.manifest.name=a.name;a.description=desc.value;a.manifest.description=desc.value;a.updated_at=new Date().toISOString();a.history.push({event:'metadata_edited',at:a.updated_at});});notice('Changes saved locally.');}catch(e){notice(e.message,true);}};edit.append(nl,dl,commit);section.appendChild(edit);
      const details=element('details');details.appendChild(element('summary','Inspection, files, and history'));
      details.appendChild(element('p','No code has been executed. Syntax checks in this browser cover JSON only. Python and other source need the local engine.','small'));
      const report=item.validation_results;
      details.appendChild(element('pre',JSON.stringify({observations:report.observations,assumptions:report.assumptions,errors:report.errors,warnings:report.warnings,dependencies:item.dependencies,permissions:item.permissions,compatibility:item.compatibility,history:item.history},null,2)));
      for(const f of item.manifest.files){details.append(element('h4',f.path),element('pre',f.content));}
      section.appendChild(details);root.appendChild(section);
    }
  }
  async function feed(){
    const button=$('captureability');button.disabled=true;
    try{
      let raw=$('feedinput').value;const files=[...$('sourcefiles').files];
      let manifest;
      if(files.length){
        if(files.length>C.LIMITS.files)throw Error('Choose at most 40 source files.');
        const entries=[];for(const f of files){if(f.size>C.LIMITS.file)throw Error(f.name+' is too large.');C.safePath(f.name);entries.push({path:f.name,content:await f.text()});}
        if(raw.trim())entries.unshift({path:'feed-notes.md',content:raw});
        const stub=C.createCandidate(raw.trim() || 'Source file package',{name:$('abilityname').value || files[0].name.replace(/\.[^.]+$/,'')});
        manifest=C.normalizeManifest({...stub.manifest,description:$('abilitydescription').value || stub.description,files:entries,entrypoint:entries.find(f=>f.path.endsWith('.py'))?.path || entries[0].path});
      }
      let candidate=C.createCandidate(manifest?'Uploaded source package':raw,{name:$('abilityname').value,description:$('abilitydescription').value,source:$('abilitysource').value || (files.length?'source upload':'manual paste')});
      if(manifest){candidate.manifest=manifest;candidate.name=manifest.name;candidate.version=manifest.version;candidate.content=raw || 'Uploaded source package';candidate.validation_results=C.inspect(manifest);candidate.language=[...new Set(manifest.files.map(f=>C.language(f.path)))].join(', ');candidate.status=candidate.validation_results.errors.length || candidate.validation_results.warnings.length?'needs_review':'inspected';}
      const duplicate=library.abilities.find(a=>C.identity(a)===C.identity(candidate));
      if(duplicate){notice('Already saved as '+duplicate.name+'. No duplicate added.');return;}
      if(library.abilities.length>=C.LIMITS.items)throw Error('Inbox full. Export a backup, then remove old entries.');
      save({...library,abilities:[candidate,...library.abilities]});render();notice('Saved '+candidate.name+' locally · '+candidate.language+' · '+candidate.status.replaceAll('_',' ')+'. Unverified; nothing executed.');
      $('feedinput').value='';$('sourcefiles').value='';$('abilitymessage').focus({preventScroll:true});
    }catch(e){notice('Could not save: '+e.message+' Your input is still here.',true);}finally{button.disabled=false;}
  }
  try{
    if(!C)throw Error('The catalog script did not load. Reload this page.');
    const raw=localStorage.getItem(KEY),legacy=raw===null?localStorage.getItem(LEGACY):null;rawStored=raw===null?legacy:raw;
    if(raw!==null)library=C.normalizeLibrary(C.parseJSON(raw),true);
    else if(legacy!==null){library=C.normalizeLibrary(C.parseJSON(legacy));localStorage.setItem(KEY,JSON.stringify(library));}
    readable=true;
    localStorage.setItem('toad-storage-probe','1');localStorage.removeItem('toad-storage-probe');
    readable=true;$('storagebanner').textContent='Local storage ready. Feeds stay in this browser; export backups.';
  }catch(e){$('storagebanner').textContent=(readable?'Saved inbox is readable, but storage is full or unavailable for new saves. Export a backup or remove old candidates. ':'Storage unavailable or unreadable. Recover/export stored data before resetting. ')+e.message;$('storagebanner').className='error';$('backupcontrols').open=true;}
  if(!C)return;
  for(const s of C.STATUSES){const o=element('option',s.replaceAll('_',' '));o.value=s;$('statusfilter').appendChild(o);}
  $('captureability').disabled=false;$('captureability').onclick=feed;
  $('clearfeed').onclick=()=>{$('feedinput').value='';$('sourcefiles').value='';notice('Input cleared. Saved candidates remain in your inbox.');};
  for(const id of ['searchabilities','statusfilter','languagefilter'])$(id).addEventListener(id==='searchabilities'?'input':'change',render);
  $('exportabilities').onclick=()=>{try{if(!readable)throw Error('Use raw recovery for unreadable storage.');download(JSON.stringify(library,null,2),'toad-library.json');notice('Backup download prepared. Keep the file somewhere you can find it.');}catch(e){notice(e.message,true);}};
  $('exportselected').onclick=()=>{const entries=library.abilities.filter(a=>selected.has(a.id));if(!entries.length){notice('Select at least one candidate first.',true);return;}download(JSON.stringify({...library,abilities:entries},null,2),'toad-library-selected.json');notice('Selected backup download prepared.');};
  $('importabilities').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>C.LIMITS.backup)throw Error('Backup exceeds 2 MB limit.');const merged=C.mergeLibraries(library,C.parseJSON(await f.text()));save(merged.library);render();notice('Imported '+merged.added+' candidates locally; '+merged.duplicates+' duplicates skipped. Imported claims remain unverified.');}catch(err){notice('Import refused: '+err.message,true);}finally{e.target.value='';}};
  $('recoverstorage').onclick=()=>{try{let raw=rawStored;if(raw===null)raw=localStorage.getItem(KEY) || localStorage.getItem(LEGACY);if(raw===null)throw Error('No stored data is available.');download(raw,'toad-storage-recovery.txt','text/plain');notice('Raw recovery download prepared.');}catch(e){notice('Recovery unavailable: '+e.message,true);}};
  $('resetstorage').onclick=()=>{if(readable){notice('Storage is readable. Use the individual delete controls.',true);return;}if(!confirm('Reset unreadable inbox data on this device? Download raw recovery first.'))return;try{localStorage.removeItem(KEY);localStorage.removeItem(LEGACY);location.reload();}catch(e){notice('Storage reset failed: '+e.message,true);}};
  const tasks=[];
  $('add').onclick=()=>{const id=$('taskid').value.trim(),file=$('filename').value.trim(),description=$('desc').value.trim();if(!/^TASK_[0-9]+$/.test(id) || !/^[A-Za-z][A-Za-z0-9_]*\.py$/.test(file) || !description){$('curriculummessage').textContent='Use a TASK_003-style ID, a safe .py filename and instructions.';return;}if(tasks.some(t=>t.id===id)){$('curriculummessage').textContent='Task ID already exists.';return;}tasks.push({id,script_name:file,description});$('curriculum').textContent=JSON.stringify(tasks,null,2);$('curriculummessage').textContent='Task added to this session.';};
  $('export').onclick=()=>download(JSON.stringify(tasks,null,2),'curriculum.json');
  render();
})();
