/* Browser controller. Imported content is always rendered as text. */
(function () {
  'use strict';
  const $=id=>document.getElementById(id), C=window.ToadCatalog;
  const KEY='toad-ability-library-v2', LEGACY='toad-ability-library-v1';
  let library={schema:'toad-library-v2',schema_version:2,abilities:[],extensions:{}}, readable=false, rawStored=null;
  let expectedRaw=null, expectedLegacy=null;
  const DRAFT='toad-feed-draft-v1';
  let draftReadable=true, draftRaw=null, missingDraftFiles=false, draftTimer=null, draftRevision=0;
  const selected=new Set();
  function notice(message,error){$('abilitymessage').textContent=message;$('abilitymessage').className=error?'error':'';}
  function element(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
  function download(data,name,type){const blob=new Blob([data],{type:type || 'application/json'}),url=URL.createObjectURL(blob),a=element('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
  function readInbox(){
    const raw=localStorage.getItem(KEY),legacy=raw===null?localStorage.getItem(LEGACY):null;
    rawStored=raw===null?legacy:raw;
    try{
      const next=raw!==null?C.normalizeLibrary(C.parseJSON(raw),true):legacy!==null?C.normalizeLibrary(C.parseJSON(legacy)):{schema:'toad-library-v2',schema_version:2,abilities:[],extensions:{}};
      library=next;expectedRaw=raw;expectedLegacy=legacy;readable=true;
    }catch(e){readable=false;throw e;}
  }
  function synchronize(){
    const raw=localStorage.getItem(KEY),legacy=raw===null?localStorage.getItem(LEGACY):null;
    if(raw===expectedRaw && legacy===expectedLegacy)return false;
    if([...document.querySelectorAll('[data-metadata-field]')].some(e=>e.value!==e.defaultValue))throw Error('Inbox changed in another tab. Copy your unsaved name or description edits before reloading.');
    try{readInbox();render();$('storagebanner').textContent='Inbox updated on this device. Export backups regularly.';$('storagebanner').className='';return true;}
    catch(e){$('storagebanner').textContent='Changed inbox data is unreadable. Download raw recovery before resetting. '+e.message;$('storagebanner').className='error';$('backupcontrols').open=true;throw e;}
  }
  async function save(next){
    // Capture the base before waiting: storage events may change the displayed view.
    const base=expectedRaw,legacyBase=expectedLegacy;
    const commit=()=>{
      if(!readable)throw Error('Storage is unavailable or unreadable; recover it before saving.');
      const current=localStorage.getItem(KEY);
      if(current!==base || (current===null && localStorage.getItem(LEGACY)!==legacyBase)){
        synchronize();throw Error('Inbox changed in another tab. Review the updated items, then try again.');
      }
      const raw=JSON.stringify(next);if(C.bytes(raw)>C.LIMITS.backup)throw Error('Storage limit reached. Export a backup and remove old entries.');
      localStorage.setItem(KEY,raw);library=next;rawStored=raw;expectedRaw=raw;expectedLegacy=null;
    };
    // Web Locks coordinate participating tabs. Older browsers retain a stale-read guard.
    if(navigator.locks && typeof navigator.locks.request==='function')return navigator.locks.request('toad-inbox-write-v2',commit);
    return commit();
  }
  async function update(id,fn){const next=JSON.parse(JSON.stringify(library)),item=next.abilities.find(a=>a.id===id);if(!item)return;fn(item,next);await save(next);render();}
  function draftNotice(message,error){$('draftstatus').textContent=message;$('draftstatus').className=error?'small error':'small';}
  function draftFields(){return {schema:DRAFT,content:$('feedinput').value,name:$('abilityname').value,description:$('abilitydescription').value,source:$('abilitysource').value,has_files:missingDraftFiles || $('sourcefiles').files.length>0,saved_at:new Date().toISOString()};}
  function clearDraft(){
    clearTimeout(draftTimer);draftTimer=null;
    try{sessionStorage.removeItem(DRAFT);draftRaw=null;draftReadable=true;draftNotice('No unsent draft. Feed Toad saves to your inbox.');}
    catch(e){draftNotice('Draft cleanup unavailable. An earlier draft may reappear on reload. '+e.message,true);}
  }
  function persistDraft(){
    clearTimeout(draftTimer);draftTimer=null;
    if(!draftReadable){draftNotice('Saved draft is unreadable. Download it before Clear input. New text is not being kept as a draft.',true);return;}
    const fields=draftFields();
    if(!fields.content && !fields.name && !fields.description && !fields.source && !fields.has_files){clearDraft();return;}
    try{const raw=JSON.stringify(C.normalizeDraft(fields));sessionStorage.setItem(DRAFT,raw);draftRaw=raw;draftNotice('Draft saved in this tab · not in your inbox yet.'+(fields.has_files?' Attachments must be selected again after reload.':''));}
    catch(e){draftNotice('Could not update this tab’s draft. Keep this page open or download the draft before leaving. '+e.message,true);}
  }
  function clearForm(discardUnreadable=false){
    draftRevision++;for(const id of ['feedinput','abilityname','abilitydescription','abilitysource','sourcefiles'])$(id).value='';
    missingDraftFiles=false;$('draftfilewarning').hidden=true;
    if(draftReadable || discardUnreadable)clearDraft();
    else {clearTimeout(draftTimer);draftTimer=null;draftNotice('Feed saved. Unreadable draft storage has been left untouched; download recovery before Clear input.',true);}
  }
  function applyDraft(fields){
    for(const [id,key] of [['feedinput','content'],['abilityname','name'],['abilitydescription','description'],['abilitysource','source']])$(id).value=fields[key];
    $('sourcefiles').value='';missingDraftFiles=fields.has_files;$('draftfilewarning').hidden=!missingDraftFiles;
  }
  function restoreDraft(){
    try{
      draftRaw=sessionStorage.getItem(DRAFT);if(draftRaw===null)return;
      const fields=C.normalizeDraft(C.parseJSON(draftRaw));
      applyDraft(fields);
      draftNotice('Draft restored in this tab · not in your inbox yet.'+(missingDraftFiles?' Select the files again or continue without attachments.':''));
    }catch(e){draftReadable=false;draftNotice('Saved draft unavailable or unreadable. Download draft to recover it before Clear input. '+e.message,true);}
  }
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
      const archive=element('button',item.status==='archived'?'Restore':'Archive');archive.type='button';archive.onclick=async()=>{try{await update(item.id,a=>{a.status=a.status==='archived'?(a.validation_results.errors.length || a.validation_results.warnings.length?'needs_review':'inspected'):'archived';a.history.push({event:a.status==='archived'?'archived':'restored',at:new Date().toISOString()});});notice('Updated locally.');}catch(e){notice(e.message,true);}};
      const del=element('button','Delete','danger');del.type='button';del.onclick=async()=>{if(!confirm('Delete '+item.name+' from this device? Export a backup first if you need it.'))return;try{const next={...library,abilities:library.abilities.filter(a=>a.id!==item.id)};await save(next);selected.delete(item.id);render();notice('Deleted local candidate.');}catch(e){notice(e.message,true);}};
      actions.append(archive,del);section.appendChild(actions);
      const edit=element('details');edit.appendChild(element('summary','Edit name and description'));
      const name=element('input');name.defaultValue=item.name;name.value=item.name;name.dataset.metadataField='name';name.maxLength=100;const desc=element('textarea');desc.defaultValue=item.description;desc.value=item.description;desc.dataset.metadataField='description';desc.rows=2;desc.maxLength=4000;
      const nl=element('label','Name');nl.appendChild(name);const dl=element('label','Description');dl.appendChild(desc);const commit=element('button','Save changes');commit.type='button';commit.onclick=async()=>{try{if(!name.value.trim())throw Error('A name is required.');await update(item.id,a=>{const normalized=C.createCandidate(a.content,{name:name.value,description:desc.value,source:a.source});a.name=normalized.name;a.manifest.name=a.name;a.description=desc.value;a.manifest.description=desc.value;a.updated_at=new Date().toISOString();a.history.push({event:'metadata_edited',at:a.updated_at});});notice('Changes saved locally.');}catch(e){notice(e.message,true);}};edit.append(nl,dl,commit);section.appendChild(edit);
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
      if(missingDraftFiles && !$('sourcefiles').files.length)throw Error('Select the files again, or choose Continue without attachments.');
      const revision=draftRevision,options={name:$('abilityname').value,description:$('abilitydescription').value,source:$('abilitysource').value};
      const raw=$('feedinput').value,files=[...$('sourcefiles').files];
      let manifest;
      if(files.length){
        if(files.length>C.LIMITS.files)throw Error('Choose at most 40 source files.');
        const entries=[];for(const f of files){if(f.size>C.LIMITS.file)throw Error(f.name+' is too large.');C.safePath(f.name);entries.push({path:f.name,content:await f.text()});}
        if(raw.trim())entries.unshift({path:'feed-notes.md',content:raw});
        const stub=C.createCandidate(raw.trim() || 'Source file package',{name:options.name || files[0].name.replace(/\.[^.]+$/,'')});
        manifest=C.normalizeManifest({...stub.manifest,description:options.description || stub.description,files:entries,entrypoint:entries.find(f=>f.path.endsWith('.py'))?.path || entries[0].path});
      }
      let candidate=C.createCandidate(manifest?'Uploaded source package':raw,{...options,source:options.source || (files.length?'source upload':'manual paste')});
      if(manifest){candidate.manifest=manifest;candidate.name=manifest.name;candidate.version=manifest.version;candidate.content=raw || 'Uploaded source package';candidate.validation_results=C.inspect(manifest);candidate.language=[...new Set(manifest.files.map(f=>C.language(f.path)))].join(', ');candidate.status=candidate.validation_results.errors.length || candidate.validation_results.warnings.length?'needs_review':'inspected';}
      const duplicate=library.abilities.find(a=>C.identity(a)===C.identity(candidate));
      if(duplicate){notice('Already saved as '+duplicate.name+'. No duplicate added.');return;}
      if(library.abilities.length>=C.LIMITS.items)throw Error('Inbox full. Export a backup, then remove old entries.');
      await save({...library,abilities:[candidate,...library.abilities]});render();notice('Saved '+candidate.name+' locally · '+candidate.language+' · '+candidate.status.replaceAll('_',' ')+'. Unverified; nothing executed.');
      if(revision===draftRevision)clearForm();else {persistDraft();notice('Saved '+candidate.name+' locally. Newer edits remain in your draft.');}
      $('abilitymessage').focus({preventScroll:true});
    }catch(e){notice('Could not save: '+e.message+' Your input is still here.',true);}finally{button.disabled=false;}
  }
  try{
    if(!C)throw Error('The catalog script did not load. Reload this page.');
    readInbox();
    localStorage.setItem('toad-storage-probe','1');localStorage.removeItem('toad-storage-probe');
    readable=true;$('storagebanner').textContent='Local storage ready. Feeds stay in this browser; export backups.'+(!navigator.locks?' Use one tab at a time in this browser.':'');
  }catch(e){$('storagebanner').textContent=(readable?'Saved inbox is readable, but storage is full or unavailable for new saves. Export a backup or remove old candidates. ':'Storage unavailable or unreadable. Recover/export stored data before resetting. ')+e.message;$('storagebanner').className='error';$('backupcontrols').open=true;}
  if(!C)return;
  for(const s of C.STATUSES){const o=element('option',s.replaceAll('_',' '));o.value=s;$('statusfilter').appendChild(o);}
  $('captureability').disabled=false;$('captureability').onclick=feed;
  restoreDraft();
  for(const id of ['feedinput','abilityname','abilitydescription','abilitysource'])$(id).addEventListener('input',()=>{draftRevision++;if(draftReadable)draftNotice('Keeping draft in this tab…');clearTimeout(draftTimer);draftTimer=setTimeout(persistDraft,200);});
  $('sourcefiles').addEventListener('change',()=>{draftRevision++;if($('sourcefiles').files.length){missingDraftFiles=false;$('draftfilewarning').hidden=true;}persistDraft();});
  $('discarddraftfiles').onclick=()=>{missingDraftFiles=false;$('draftfilewarning').hidden=true;draftRevision++;persistDraft();};
  $('clearfeed').onclick=()=>{clearForm(true);notice('Input and this tab’s draft cleared. Saved candidates remain in your inbox.');};
  $('downloaddraft').onclick=()=>{try{
    if(!draftReadable && draftRaw!==null){download(draftRaw,'toad-draft-recovery.txt','text/plain');notice('Raw draft recovery download prepared.');return;}
    const fields=draftFields();if(!fields.content && !fields.name && !fields.description && !fields.source && !fields.has_files)throw Error('There is no unsent draft to download.');
    download(JSON.stringify(fields,null,2),'toad-feed-draft.json');notice('Draft download prepared. Attached file contents are not included.');
  }catch(e){notice(e.message,true);}};
  $('importdraft').onchange=async e=>{try{
    const file=e.target.files[0];if(!file)return;if(file.size>C.LIMITS.package)throw Error('Draft exceeds 512 KB.');
    const revision=draftRevision,fields=C.normalizeDraft(C.parseJSON(await file.text()));
    if(revision!==draftRevision)throw Error('The draft changed while reading this file. Review your input and try again.');
    const current=draftFields();
    if((current.content || current.name || current.description || current.source || current.has_files || (!draftReadable && draftRaw!==null)) && !confirm('Replace the current unsent draft? Download it first if you need to keep it.'))return;
    applyDraft(fields);draftRevision++;draftReadable=true;persistDraft();notice('Draft restored into the editor. Press Feed Toad when ready; nothing has been added to the inbox.');
  }catch(e){notice('Draft import refused: '+e.message,true);}finally{e.target.value='';}};
  window.addEventListener('pagehide',()=>{if(draftTimer!==null)persistDraft();});
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden' && draftTimer!==null)persistDraft();});
  window.addEventListener('storage',e=>{try{if(e.storageArea===localStorage && (e.key===KEY || e.key===LEGACY || e.key===null))if(synchronize())notice('Inbox updated from another tab. Your draft has not changed.');}catch(e){notice('Inbox changed in another tab: '+e.message,true);}});
  for(const id of ['searchabilities','statusfilter','languagefilter'])$(id).addEventListener(id==='searchabilities'?'input':'change',render);
  $('exportabilities').onclick=()=>{try{synchronize();if(!readable)throw Error('Use raw recovery for unreadable storage.');download(JSON.stringify(library,null,2),'toad-library.json');notice('Backup download prepared. Keep the file somewhere you can find it.');}catch(e){notice(e.message,true);}};
  $('exportselected').onclick=()=>{try{synchronize();if(!readable)throw Error('Use raw recovery for unreadable storage.');const entries=library.abilities.filter(a=>selected.has(a.id));if(!entries.length){notice('Select at least one candidate first.',true);return;}download(JSON.stringify({...library,abilities:entries},null,2),'toad-library-selected.json');notice('Selected backup download prepared.');}catch(e){notice(e.message,true);}};
  $('importabilities').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>C.LIMITS.backup)throw Error('Backup exceeds 2 MB limit.');const incoming=C.parseJSON(await f.text());const merged=C.mergeLibraries(library,incoming);await save(merged.library);render();notice('Imported '+merged.added+' candidates locally; '+merged.duplicates+' duplicates skipped. Imported claims remain unverified.');}catch(err){notice('Import refused: '+err.message,true);}finally{e.target.value='';}};
  $('recoverstorage').onclick=()=>{try{let raw=rawStored;if(raw===null)raw=localStorage.getItem(KEY) || localStorage.getItem(LEGACY);if(raw===null)throw Error('No stored data is available.');download(raw,'toad-storage-recovery.txt','text/plain');notice('Raw recovery download prepared.');}catch(e){notice('Recovery unavailable: '+e.message,true);}};
  $('resetstorage').onclick=()=>{if(readable){notice('Storage is readable. Use the individual delete controls.',true);return;}if(!confirm('Reset unreadable inbox data on this device? Download raw recovery first.'))return;try{localStorage.removeItem(KEY);localStorage.removeItem(LEGACY);location.reload();}catch(e){notice('Storage reset failed: '+e.message,true);}};
  const tasks=[];
  $('add').onclick=()=>{const id=$('taskid').value.trim(),file=$('filename').value.trim(),description=$('desc').value.trim();if(!/^TASK_[0-9]+$/.test(id) || !/^[A-Za-z][A-Za-z0-9_]*\.py$/.test(file) || !description){$('curriculummessage').textContent='Use a TASK_003-style ID, a safe .py filename and instructions.';return;}if(tasks.some(t=>t.id===id)){$('curriculummessage').textContent='Task ID already exists.';return;}tasks.push({id,script_name:file,description});$('curriculum').textContent=JSON.stringify(tasks,null,2);$('curriculummessage').textContent='Task added to this session.';};
  $('export').onclick=()=>download(JSON.stringify(tasks,null,2),'curriculum.json');
  render();
})();
