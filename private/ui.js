/* Same-origin private UI. There is no script execution or public endpoint. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
let csrf=null;
const say=(message,error=false)=>{$('message').textContent=message;$('message').className=error?'error':''};
const data=async path=>{const response=await fetch(path,{credentials:'same-origin',cache:'no-store'});if(response.status===401){location.replace('/login');throw Error('Session expired')}const json=await response.json();if(!response.ok)throw Error(json.error||'Request failed');return json};
function list(target,items,render){const root=$(target);root.replaceChildren();if(!items.length){root.textContent='No records yet.';return}const ul=document.createElement('ul');for(const item of items){const li=document.createElement('li');li.textContent=render(item);ul.append(li)}root.append(ul)}
async function refresh(){try{const [status,candidates,missions]=await Promise.all([data('/api/status'),data('/api/candidates'),data('/api/missions')]);csrf=status.bridge.csrf;$('send').disabled=false;$('status').textContent=JSON.stringify({candidates:status.candidates,statuses:status.statuses,queue:status.queue,remote_execution_enabled:status.bridge.execution_enabled},null,2);list('candidates',candidates,x=>x.name+' — '+x.status+' ('+x.language+')');list('missions',missions,x=>x.goal+' — '+x.status+' / '+x.phase);if($('message').textContent==='Connecting securely…')say('Connected to the local Acer engine.')}catch(e){say('Bridge unavailable: '+e.message,true)}}
$('send').onclick=async()=>{if(!csrf)return say('Not connected',true);$('send').disabled=true;try{const response=await fetch('/api/feed',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Toad-CSRF':csrf},body:JSON.stringify({content:$('feed').value,name:$('name').value.trim()||undefined})});const result=await response.json();if(!response.ok)throw Error(result.error||'Save failed');say('Saved to Acer: '+result.name+' · '+result.status+' · NOT EXECUTED');$('feed').value='';await refresh()}catch(e){say('Could not save: '+e.message+' (your input is still here)',true)}finally{$('send').disabled=!csrf}};
$('refresh').onclick=refresh;
refresh();setInterval(refresh,10000);
})();
