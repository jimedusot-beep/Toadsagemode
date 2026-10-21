/* Phone-only review and practice. No remote model, uploads or execution. */
(function(){
  'use strict';
  const E=window.ToadEmpathy,C=window.ToadCatalog,$=id=>document.getElementById(id),KEY='toad-empathy-library-v2',TRANSFER='toad-empathy-transfer-v1';
  let data=E.empty(),expected=null,readable=false,editing=null,scenarios=[],practiceLessons=[],practiceScenario=null;
  const fields={title:'etitle',audience:'eaudience',material:'ematerial',situation:'esituation',technique:'etechnique',helpful_behavior:'ehelpful',counterexample:'ecounter',practice_response:'eresponse',inappropriate_when:'elimitations'};
  const sources={label:'esource',kind:'ekind',rights:'erights',url:'eurl',retrieved_at:'eretrieved',attribution:'eattribution',inspiration:'einspiration'};
  function message(text,error=false){$('emessage').textContent=text;$('emessage').className=error?'error':'';}
  function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
  function download(value,name){const url=URL.createObjectURL(new Blob([value],{type:'application/json'})),a=el('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
  async function persist(next){
    const base=expected;E.validate(next);
    const commit=()=>{
      if(!readable)throw Error('Stored empathy data is unreadable or unavailable. Download raw recovery first.');
      if(localStorage.getItem(KEY)!==base)throw Error('Library changed in another tab. Copy unsaved form text, then reload before saving.');
      const raw=JSON.stringify(next);localStorage.setItem(KEY,raw);data=next;expected=raw;
    };
    if(navigator.locks?.request)await navigator.locks.request('toad-empathy-write-v2',commit);else commit();
  }
  async function action(fn){try{await fn();}catch(e){message(e.message+' Your input has been kept.',true);}}
  function readForm(){const item={source:{}};for(const [key,id] of Object.entries(fields))item[key]=$(id).value;for(const [key,id] of Object.entries(sources))item.source[key]=$(id).value;item.title=item.title.trim() || 'Conversation note';return item;}
  function clear(){editing=null;$('lessonform').reset();$('elessonsave').textContent='Save unreviewed lesson';}
  function editForm(item){
    if((editing || $('ematerial').value) && !confirm('Replace the current unsaved form? Copy it first if needed.'))return;
    editing={id:item.id,version:item.version};for(const [key,id] of Object.entries(fields))$(id).value=item[key];for(const [key,id] of Object.entries(sources))$(id).value=item.source[key];
    $('lessonfields').open=true;$('elessonsave').textContent='Save correction · require review';$('etitle').focus();message('Editing version '+item.version+'. Previous versions are retained.');
  }
  function render(){
    const root=$('elessons');root.textContent='';const query=$('esearch').value.toLowerCase(),status=$('efilter').value;
    const shown=data.lessons.filter(x=>(!status || status===x.review_status) && JSON.stringify(x).toLowerCase().includes(query));
    $('ecount').textContent=data.lessons.length+' lessons · '+shown.length+' shown';
    for(const item of shown){
      const article=el('article');article.className='ability';article.dataset.lessonId=item.id;
      article.append(el('h3',item.title),el('p',item.audience+' · version '+item.version+' · '+item.review_status.replaceAll('_',' ')),el('p',item.technique || 'Interpretation not recorded yet.'));
      const preview=el('details');preview.append(el('summary','Material, interpretation and history'),el('pre',JSON.stringify(item,null,2)));article.append(preview);
      const correction=el('button','Correct this lesson');correction.type='button';correction.onclick=()=>editForm(item);article.append(correction);
      const review=el('details');review.append(el('summary','Review this version'));
      const label=el('label','Review status'),select=el('select');select.setAttribute('aria-label','Review status for '+item.title);
      for(const value of E.STATUSES){const option=el('option',value.replaceAll('_',' '));option.value=value;select.append(option);}select.value=item.review_status;label.append(select);
      const nl=el('label','Your review note'),note=el('textarea');note.maxLength=4000;note.rows=2;note.setAttribute('aria-label','Review note for '+item.title);nl.append(note);
      const button=el('button','Record human review');button.type='button';button.onclick=()=>action(async()=>{
        const next=structuredClone(data),record=next.lessons.find(x=>x.id===item.id);E.review(record,select.value,note.value);await persist(next);render();message('Human review saved for version '+record.version+'. This is not a model-quality certification.');
      });review.append(label,nl,button);article.append(review);
      const del=el('button','Delete lesson');del.type='button';del.className='danger';del.onclick=()=>{if(confirm('Delete this local lesson? Export a backup first.'))action(async()=>{const next={...data,lessons:data.lessons.filter(x=>x.id!==item.id)};await persist(next);render();message('Lesson deleted locally.');});};article.append(del);root.append(article);
    }
    if(!shown.length)root.append(el('p','No matching lessons. Save a note or add original starter examples.'));
    $('eassessmentcount').textContent=data.assessments.length+' locally recorded paired assessments. No improvement claim is calculated.';
  }
  async function publicData(path){const result=await fetch(path,{credentials:'omit',cache:'no-cache'});if(!result.ok)throw Error('Could not load original practice data');return C.parseJSON(await result.text());}
  function showScenario(){
    practiceScenario=scenarios.find(x=>x.id===$('escenario').value);if(!practiceScenario)return;
    practiceLessons=E.retrieve(data,practiceScenario.prompt,practiceScenario.audience).map(x=>({id:x.id,version:x.version,...Object.fromEntries(E.FIELDS.map(k=>[k,x[k]]))}));
    $('eprompt').textContent=practiceScenario.audience+': '+practiceScenario.prompt;$('efocus').textContent=practiceScenario.focus;
    $('ematches').textContent='';$('ematches').append(el('h3','Reviewed reference lessons for this trial'));
    if(!practiceLessons.length)$('ematches').append(el('p','No relevant reviewed lessons. Save and review an appropriate lesson, then reselect the scenario.'));
    for(const item of practiceLessons)$('ematches').append(el('pre',JSON.stringify(item,null,2)));
  }
  try{expected=localStorage.getItem(KEY);if(expected!==null)data=E.validate(C.parseJSON(expected));readable=true;message('Local empathy library ready. Lessons need review before retrieval.');}
  catch(e){message('Storage unavailable or unreadable. Download raw recovery; existing data was left untouched. '+e.message,true);}
  $('lessonform').onsubmit=event=>{event.preventDefault();action(async()=>{
    const submitted=readForm(),revision=JSON.stringify(submitted),target=editing,next=structuredClone(data);
    if(target){const index=next.lessons.findIndex(x=>x.id===target.id);if(index<0 || next.lessons[index].version!==target.version)throw Error('This lesson changed; reload after copying your correction');next.lessons[index]=E.edit(next.lessons[index],submitted);}
    else {next.lessons.push(E.note(submitted.material,submitted.audience,submitted.source));next.lessons[next.lessons.length-1]=E.normalize({...next.lessons.at(-1),...submitted});}
    await persist(next);if(JSON.stringify(readForm())===revision && editing===target)clear();else if(target && editing===target)editing={id:target.id,version:target.version+1};render();message('Lesson saved locally · needs review. Nothing trained or activated.');
  });};
  $('ecancel').onclick=()=>{if((editing || $('ematerial').value) && !confirm('Discard the unsaved form?'))return;clear();message('Form cleared. Saved lessons remain.');};
  $('eseed').onclick=()=>action(async()=>{const [legacy,examples]=await Promise.all([publicData('empathy/examples.json'),publicData('empathy/lessons.json')]);const next=E.merge(E.merge(data,legacy),examples);await persist(next);render();message('Original starter examples added as unreviewed lessons. No episodes were retrieved.');});
  $('eexport').onclick=()=>action(async()=>{if(!readable)throw Error('Use raw recovery for unreadable storage');download(JSON.stringify(data),'toad-empathy-backup.json');message('Empathy backup prepared. Private notes and assessments are included.');});
  $('erecovery').onclick=()=>action(async()=>{const raw=localStorage.getItem(KEY);if(raw===null)throw Error('No stored empathy data');download(raw,'toad-empathy-recovery.json');message('Raw recovery prepared. Keep it private.');});
  $('elessonfile').onchange=event=>action(async()=>{try{
    const file=event.target.files[0];if(!file)return;if(file.size>2000000)throw Error('File exceeds 2 MB');
    const text=await file.text();let next;
    if(/\.json$/i.test(file.name))next=E.merge(data,C.parseJSON(text));
    else {if(!/\.(txt|md)$/i.test(file.name))throw Error('Use a text, Markdown or JSON file');next=structuredClone(data);next.lessons.push(E.note(text,$('eaudience').value));}
    await persist(next);render();message('Imported locally. Imported approvals remain untrusted; review each lesson here.');
  }finally{event.target.value='';}});
  for(const id of ['esearch','efilter'])$(id).addEventListener(id==='esearch'?'input':'change',render);
  window.addEventListener('storage',event=>{if(event.key===KEY || event.key===null)message('Library changed in another tab. Copy unsaved input and reload; this tab will refuse stale saves.',true);});
  for(const key of E.RUBRIC){const box=el('div');box.className='filters';box.append(el('p',key.replaceAll('_',' ')));for(const arm of ['baseline','retrieved']){const label=el('label',arm),select=el('select');select.id='score-'+key+'-'+arm;select.setAttribute('aria-label',key+' '+arm);for(const value of ['','0','1','2','na']){const option=el('option',value===''?'Choose…':value==='na'?'N/A':value);option.value=value;select.append(option);}label.append(select);box.append(label);}$('erubric').append(box);}
  $('escenario').onchange=()=>{if(($('ebaseline').value || $('eretrievalresponse').value) && !confirm('Changing scenario clears unsaved responses and ratings. Continue?')){$('escenario').value=practiceScenario?.id || '';return;}$('ebaseline').value='';$('eretrievalresponse').value='';for(const select of $('erubric').querySelectorAll('select'))select.value='';showScenario();};
  $('eassessment').onclick=()=>action(async()=>{const scores={};for(const key of E.RUBRIC){scores[key]={};for(const arm of ['baseline','retrieved']){const value=$('score-'+key+'-'+arm).value;scores[key][arm]=value==='na'?'na':value===''?null:Number(value);}}
    const report=E.assessment(practiceScenario,$('ebaseline').value,$('eretrievalresponse').value,scores,practiceLessons),next=structuredClone(data);if(next.assessments.length>=100)throw Error('Assessment limit reached; export first');next.assessments.push(report);await persist(next);render();message('Paired human assessment saved. Responses are user-supplied and unverified; no improvement claim is made.');
  });
  action(async()=>{const sample=await publicData('empathy/practice.json');scenarios=sample.scenarios;$('escenario').textContent='';for(const item of scenarios){const option=el('option',item.id+' · '+item.domain+' · '+item.audience);option.value=item.id;$('escenario').append(option);}showScenario();});
  try{const raw=sessionStorage.getItem(TRANSFER);if(raw){const transfer=C.parseJSON(raw);if(typeof transfer.material!=='string' || E.bytes(transfer.material)>250000)throw Error('Transferred note is invalid');$('ematerial').value=transfer.material;$('esource').value=typeof transfer.source==='string'?transfer.source.slice(0,1000):'Feed Inbox';sessionStorage.removeItem(TRANSFER);message('Feed copied into this form. Review its source and press Save unreviewed lesson; original feed remains.');}}catch(e){message('Feed transfer unavailable: '+e.message,true);}
  window.addEventListener('beforeunload',event=>{if($('ematerial').value){event.preventDefault();event.returnValue='';}});
  render();
})();
