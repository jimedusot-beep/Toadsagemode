/* Toad Sage Free App Studio V2 — local project settings + safe design preview.
   No generative AI, code execution, third-party requests or app-data access.
*/
(() => {
  'use strict';
  const KEY = 'toad-sage-free-studio-projects-v1';
  const SCHEMA = 'toad-studio-projects-v1';
  const MAX_PROJECTS = 20;
  const MAX_BYTES = 12000;
  const KINDS = ['tasks', 'notes', 'flashcards'];
  const THEMES = ['forest', 'midnight'];
  const NAME = /^[a-z][a-z0-9-]{1,39}$/;

  function validProject(item) {
    return item !== null && typeof item === 'object' && !Array.isArray(item) &&
      Object.keys(item).sort().join(',') === 'kind,name,savedAt,theme,title' &&
      typeof item.name === 'string' && NAME.test(item.name) &&
      typeof item.title === 'string' && item.title.trim().length > 0 &&
      item.title.length <= 80 && !/[\u0000-\u001f\u007f]/.test(item.title) &&
      KINDS.includes(item.kind) && THEMES.includes(item.theme) &&
      typeof item.savedAt === 'string' &&
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(item.savedAt);
  }

  function parseProjects(raw) {
    if (raw === null) return [];
    if (typeof raw !== 'string' || raw.length > MAX_BYTES) {
      throw Error('The saved-project library is invalid or too large; it was not overwritten.');
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_) {
      throw Error('The saved-project library could not be read; it was not overwritten.');
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) ||
        Object.keys(parsed).sort().join(',') !== 'projects,schema' ||
        parsed.schema !== SCHEMA || !Array.isArray(parsed.projects) ||
        parsed.projects.length > MAX_PROJECTS ||
        !parsed.projects.every(validProject) ||
        new Set(parsed.projects.map(p => p.name)).size !== parsed.projects.length) {
      throw Error('The saved-project library is invalid; it was not overwritten.');
    }
    return parsed.projects.map(p => ({name:p.name,title:p.title,kind:p.kind,
      theme:p.theme,savedAt:p.savedAt}));
  }

  function makeRecord(input, savedAt = new Date().toISOString()) {
    const record = {
      name:input.name, title:input.title?.trim(), kind:input.kind,
      theme:input.theme, savedAt
    };
    if (!validProject(record)) {
      throw Error('Choose one supported app, a valid name, title and theme before saving.');
    }
    return record;
  }

  function upsertProject(projects, record) {
    if (!validProject(record)) throw Error('Invalid project settings.');
    const existing = projects.find(p=>p.name===record.name);
    if (existing && existing.kind!==record.kind) {
      throw Error('This name belongs to a different app type. Choose a new name or delete that project.');
    }
    if (!existing && projects.length>=MAX_PROJECTS) {
      throw Error('The free Studio holds at most 20 saved projects. Delete one before saving another.');
    }
    return [...projects.filter(p=>p.name!==record.name), record].sort(
      (a,b)=>a.name.localeCompare(b.name)
    );
  }

  function serializeProjects(projects) {
    if (!Array.isArray(projects) || projects.length>MAX_PROJECTS ||
        !projects.every(validProject) ||
        new Set(projects.map(p=>p.name)).size!==projects.length) {
      throw Error('Cannot save an invalid project library.');
    }
    const json=JSON.stringify({schema:SCHEMA,projects});
    if (json.length>MAX_BYTES) throw Error('Saved project data exceeds local size limit.');
    return json;
  }

  function mergeProjects(existing, incoming) {
    // Backup import is additive only. Never replace owner settings silently.
    serializeProjects(existing);
    serializeProjects(incoming);
    const records=new Map(existing.map(item=>[item.name,item]));
    for(const item of incoming) {
      const old=records.get(item.name);
      if(old && JSON.stringify(old)!==JSON.stringify(item)) {
        throw Error('Backup conflicts with saved project '+item.name+'; nothing was changed.');
      }
      if(!old) records.set(item.name,item);
    }
    const combined=[...records.values()].sort((a,b)=>a.name.localeCompare(b.name));
    serializeProjects(combined);
    return combined;
  }

  function describeKind(kind) {
    return ({tasks:'Task manager',notes:'Notes',flashcards:'Flashcards'})[kind]||'Flashcards';
  }

  function makeNode(tag, className, text) {
    const node=document.createElement(tag);
    if (className) node.className=className;
    if (text!==undefined) node.textContent=text;
    return node;
  }
  function renderPreview(fields) {
    const device=document.querySelector('#device-preview');
    const stage=document.querySelector('#preview-content');
    const title=document.querySelector('#preview-title');
    const size=document.querySelector('#preview-size').value;
    const kind=KINDS.includes(fields.kind)?fields.kind:'flashcards';
    device.dataset.theme=THEMES.includes(fields.theme)?fields.theme:'forest';
    device.dataset.size=size==='tablet'?'tablet':'phone';
    device.dataset.kind=kind;
    title.textContent=typeof fields.title==='string' && fields.title.trim() ?
      fields.title.trim().slice(0,80) : 'Untitled App';
    stage.replaceChildren();
    const h=makeNode('h4','',describeKind(kind));
    stage.append(h);
    if (kind==='flashcards') {
      stage.append(
        makeNode('p','mock-muted','1 of 3 learned'),
        makeNode('div','mock-flashcard','')
      );
      const card=stage.querySelector('.mock-flashcard');
      card.append(makeNode('small','','QUESTION'),
        makeNode('span','','What is an app prototype?'));
      stage.append(makeNode('div','mock-button','Flip card'));
    } else if (kind==='notes') {
      stage.append(makeNode('div','mock-input','Title of a note'),
        makeNode('div','mock-input','Write your ideas here…'),
        makeNode('div','mock-button','Save note'));
      const list=makeNode('ul','mock-list');
      list.append(makeNode('li','','Project ideas'),
        makeNode('li','','Research notes'));
      stage.append(list);
    } else {
      stage.append(makeNode('div','mock-input','What needs doing?'),
        makeNode('div','mock-button','Add task'));
      const list=makeNode('ul','mock-list');
      list.append(makeNode('li','','☐ Finish project outline'),
        makeNode('li','','☑ Review study notes'));
      stage.append(list);
    }
  }

  function boot() {
    const form=document.querySelector('#build-form');
    if (!form) return;
    const save=document.querySelector('#save-project');
    const status=document.querySelector('#projects-status');
    const list=document.querySelector('#project-list');
    const empty=document.querySelector('#projects-empty');
    const count=document.querySelector('#project-count');
    const screen=document.querySelector('#preview-size');
    const backup=document.querySelector('#backup-projects');
    const backupLink=document.querySelector('#backup-link');
    const restoreFile=document.querySelector('#backup-file');
    const restore=document.querySelector('#restore-projects');
    let backupUrl=null;
    let projects=[];
    let storageWritable=true;
    let pendingDelete=null;

    function notice(msg, style='') {
      status.textContent=msg;
      status.className=style;
    }
    function clearBackupDownload() {
      backupLink.hidden=true;
      backupLink.removeAttribute('download');
      backupLink.setAttribute('href','#');
      if(backupUrl){URL.revokeObjectURL(backupUrl);backupUrl=null;}
    }
    function selected() {
      return {
        kind:form.querySelector('input[name="kind"]:checked')?.value,
        title:document.querySelector('#title').value,
        name:document.querySelector('#slug').value,
        theme:document.querySelector('#theme').value
      };
    }
    function updatePreview() {
      renderPreview(selected());
    }
    function write(next) {
      if (!storageWritable) throw Error('Saved projects are disabled because existing storage cannot be read.');
      try {
        localStorage.setItem(KEY,serializeProjects(next));
        projects=next;
      } catch (_) {
        throw Error('Could not save locally. Browser storage may be unavailable or full; your old projects were preserved.');
      }
    }
    function renderLibrary() {
      backup.disabled=!storageWritable || projects.length===0;
      restore.disabled=!storageWritable || !restoreFile.files?.length;
      list.replaceChildren();
      count.textContent=projects.length+' of '+MAX_PROJECTS;
      empty.hidden=projects.length>0;
      for(const project of projects) {
        const li=makeNode('li','saved-project');
        const info=makeNode('div','saved-project-info');
        const heading=makeNode('strong','',project.title);
        const detail=makeNode('small','',describeKind(project.kind)+' · '+project.name+' · '+project.theme);
        const label=makeNode('div','');
        label.append(heading,detail);
        info.append(label);
        const buttons=makeNode('div','saved-project-actions');
        const load=makeNode('button','','Load');
        load.type='button';
        load.setAttribute('aria-label','Load: '+project.name);
        load.addEventListener('click',()=>{
          document.querySelector('#title').value=project.title;
          document.querySelector('#slug').value=project.name;
          document.querySelector('#theme').value=project.theme;
          const type=form.querySelector('input[name="kind"][value="'+project.kind+'"]');
          if(type)type.checked=true;
          form.dispatchEvent(new Event('input',{bubbles:true}));
          screen.value='phone';
          updatePreview();
          pendingDelete=null;
          renderLibrary();
          notice('Loaded project settings for '+project.title+'. No ZIP has been published.','success');
        });
        const del=makeNode('button','danger',pendingDelete===project.name?'Confirm delete':'Delete');
        del.type='button';
        del.setAttribute('aria-label',(pendingDelete===project.name?'Confirm delete: ':'Delete: ')+project.name);
        del.addEventListener('click',()=>{
          if(pendingDelete!==project.name) {
            pendingDelete=project.name;
            renderLibrary();
            notice('Tap Confirm delete to remove '+project.name+' from this device.','');
            return;
          }
          try {
            write(projects.filter(item=>item.name!==project.name));
            pendingDelete=null;
            renderLibrary();
            notice('Deleted saved settings for '+project.title+'. Generated apps are unaffected.','success');
          } catch(error) {
            notice(error.message,'error');
          }
        });
        buttons.append(load,del);
        li.append(info,buttons);
        list.append(li);
      }
    }
    function readStorage() {
      clearBackupDownload();
      try {
        projects=parseProjects(localStorage.getItem(KEY));
        storageWritable=true;
        save.disabled=false;
        notice(projects.length?'Saved projects are ready.':'Ready to save settings locally.');
      } catch (error) {
        projects=[];
        storageWritable=false;
        save.disabled=true;
        notice('Saved project storage could not be read; existing data was not overwritten. '+
          (error instanceof Error && error.message.includes('library') ? error.message : ''),'error');
      }
      pendingDelete=null;
      renderLibrary();
    }

    backup.addEventListener('click',()=>{
      try {
        if(!storageWritable || !projects.length) throw Error('No readable saved projects to export.');
        clearBackupDownload();
        const raw=serializeProjects(projects);
        backupUrl=URL.createObjectURL(new Blob([raw],{type:'application/json;charset=utf-8'}));
        backupLink.href=backupUrl;
        backupLink.download='toad-sage-studio-projects-backup.json';
        backupLink.hidden=false;
        notice('Backup ready: '+projects.length+' project settings. Tap Download project backup and save it in iPad Files.','success');
      } catch(error) {
        notice(error.message||'Could not export a project backup.','error');
      }
    });
    restoreFile.addEventListener('change',()=>{renderLibrary();});
    restore.addEventListener('click',async()=>{
      const file=restoreFile.files?.[0];
      if(!file || !storageWritable) {
        notice('Choose a JSON backup first. Existing unreadable storage cannot be overwritten.','error');
        return;
      }
      restore.disabled=true;
      try {
        if(file.size>48000) throw Error('Backup file exceeds the supported size limit.');
        const raw=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());
        const incoming=parseProjects(raw);
        const next=mergeProjects(projects,incoming);
        const added=next.length-projects.length;
        if(added) {
          write(next);
          clearBackupDownload();
          renderLibrary();
        }
        notice(added ? 'Restored '+added+' project settings without replacing existing projects.' :
          'Backup already matches saved projects; nothing changed.','success');
      } catch(error) {
        notice('Backup not restored. '+(error.message||'Invalid backup file.'),'error');
      } finally {
        restoreFile.value='';
        renderLibrary();
      }
    });
    window.addEventListener('pagehide',clearBackupDownload);
    form.addEventListener('input',updatePreview);
    form.addEventListener('change',updatePreview);
    screen.addEventListener('change',updatePreview);
    save.addEventListener('click',()=>{
      try {
        const record=makeRecord(selected());
        const next=upsertProject(projects,record);
        write(next);
        pendingDelete=null;
        renderLibrary();
        notice('Saved '+record.title+' locally on this device.','success');
      } catch(error) {
        notice(error.message||'Could not save project.','error');
      }
    });
    window.addEventListener('storage',event=>{
      if(event.key===KEY)readStorage();
    });
    readStorage();
    updatePreview();
  }

  if (typeof module!=='undefined'&&module.exports) {
    module.exports={KEY,SCHEMA,MAX_PROJECTS,validProject,parseProjects,makeRecord,
      upsertProject,serializeProjects,mergeProjects,describeKind};
  }
  if (typeof document!=='undefined') {
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
    else boot();
  }
})();
