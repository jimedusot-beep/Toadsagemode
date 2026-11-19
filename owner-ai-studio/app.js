/* Toad Sage private owner AI draft UI: model output is displayed only as text. */
(() => {
  'use strict';
  const form=document.getElementById('draft-form');
  const token=document.getElementById('token');
  const goal=document.getElementById('goal');
  const status=document.getElementById('result-status');
  const summary=document.getElementById('draft-summary');
  const generate=document.getElementById('generate');
  const statusCheck=document.getElementById('status-check');
  const showSource=document.getElementById('show-source');
  const sourceFile=document.getElementById('source-file');
  const sourceText=document.getElementById('source-text');
  let draftId=null;
  let sourceByPath=null;

  function notice(message,isError=false){
    status.textContent=message;
    status.className=isError?'error':'';
  }
  async function request(path,options={}){
    if(!token.value || token.value.length<32) throw Error('Enter the private token from your authorized server terminal.');
    const safeTransport=location.protocol==='https:' ||
      (location.protocol==='http:' && ['127.0.0.1','localhost'].includes(location.hostname));
    if(!safeTransport) throw Error('Private HTTPS is required; the model request was blocked.');
    const response=await fetch(path,{
      ...options,
      headers:{...(options.headers||{}),'X-Toad-Owner-Token':token.value},
      credentials:'same-origin',
      redirect:'error',
      cache:'no-store'
    });
    let payload;
    try {payload=await response.json();}
    catch(_){throw Error('Gateway returned invalid JSON.');}
    if(!response.ok) throw Error(payload.error||'Gateway refused the request.');
    return payload;
  }
  function reset(){
    draftId=null;sourceByPath=null;showSource.disabled=true;
    sourceFile.disabled=true;sourceText.textContent='';
    summary.textContent='No validated source to inspect.';
  }
  statusCheck.addEventListener('click',async()=>{
    try {
      const result=await request('/api/status');
      notice('Connection metadata: '+result.provider_selection+
        '; calls left '+result.calls_remaining+
        '. Provider connectivity is unverified; no execution or deployment.');
    } catch(error){notice(error.message,true);}
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    reset();
    generate.disabled=true;
    notice('Requesting one model draft; source remains inert JSON…');
    try {
      const result=await request('/api/drafts',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({goal:goal.value})
      });
      draftId=result.id;
      summary.textContent='Draft '+result.id+' · '+result.status+
        ' · Risk flags: '+(result.risk_flags?.join(', ')||'none observed')+
        ' · Source digest: '+result.draft_sha256+
        '. Unverified; no source execution, browser test or deployment.';
      showSource.disabled=false;
      notice('Quarantined source created. Inspect the code as text; nothing has been run.');
    }catch(error){notice(error.message,true);}
    finally{generate.disabled=false;}
  });
  function render(){
    if(!sourceByPath)return;
    sourceText.textContent=sourceByPath.get(sourceFile.value)||'File unavailable.';
  }
  sourceFile.addEventListener('change',render);
  showSource.addEventListener('click',async()=>{
    if(!draftId)return;
    showSource.disabled=true;
    try {
      const result=await request('/api/drafts/'+draftId);
      if(result.release_allowed!==false || result.executed!==false)
        throw Error('Draft safety status is invalid.');
      sourceByPath=new Map(result.draft.files.map(f=>[f.path,f.content]));
      if([...sourceByPath.keys()].sort().join(',')!=='app.js,index.html,styles.css')
        throw Error('Draft file manifest is invalid.');
      sourceFile.disabled=false;
      render(); // textContent only. Never innerHTML, iframe, eval or import().
      notice('Displaying raw proposal as text. Not runnable, verified, or deployed.');
    }catch(error){notice(error.message,true);sourceText.textContent='';}
    finally{showSource.disabled=false;}
  });
})();
