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
    let projects=[];
    let storageWritable=true;
    let pendingDelete=null;

    function notice(msg, style='') {
      status.textContent=msg;
      status.className=style;
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
      upsertProject,serializeProjects,describeKind};
  }
  if (typeof document!=='undefined') {
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
    else boot();
  }
})();
