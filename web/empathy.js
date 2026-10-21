/* Portable reference data only. Never interprets lesson text as instructions. */
(function(root,factory){if(typeof module==='object' && module.exports)module.exports=factory();else root.ToadEmpathy=factory();})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const SCHEMA='toad-empathy-library-v2',AUDIENCES=['adult','child','general'];
  const STATUSES=['needs_review','helpful','inappropriate','needs_revision'];
  const FIELDS=['title','situation','audience','source','material','technique','helpful_behavior','counterexample','practice_response','inappropriate_when'];
  const RUBRIC=['recognizes_without_assuming','useful_questions','accurate_practical_help','respectful_disagreement','avoids_condescension','audience_fit','boundaries_original_voice'];
  const clone=x=>JSON.parse(JSON.stringify(x)),bytes=x=>new TextEncoder().encode(x).length,now=()=>new Date().toISOString();
  const id=()=>globalThis.crypto?.randomUUID?.() || 'lesson-'+Date.now()+'-'+Math.random().toString(36).slice(2);
  function bound(data,max=2000000){if(bytes(JSON.stringify(data))>max)throw Error('Empathy data exceeds byte limit');}
  function empty(){return {schema:SCHEMA,schema_version:2,lessons:[],imports:[],assessments:[]};}
  function normalize(raw){
    if(!raw || typeof raw!=='object' || Array.isArray(raw))throw Error('Lesson must be an object');bound(raw);
    const item=clone(raw),defaults={title:raw.emotion || 'Conversation note',situation:raw.context || '',material:raw.context || '',audience:'general',technique:raw.principle || '',helpful_behavior:raw.principle || '',counterexample:raw.avoid || '',practice_response:raw.response || '',inappropriate_when:raw.avoid || '',source:{label:'Unspecified / user import',kind:'user_notes',rights:'not_recorded',url:'',retrieved_at:'',attribution:'',inspiration:''}};
    for(const [k,v] of Object.entries(defaults))if(item[k]===undefined)item[k]=v;
    for(const k of FIELDS)if(k!=='source' && (typeof item[k]!=='string' || bytes(item[k])>(k==='material'?250000:4000)))throw Error('Invalid or oversized lesson field: '+k);
    if(!item.material.trim() || !AUDIENCES.includes(item.audience))throw Error('Material and valid audience are required');
    if(!item.source || typeof item.source!=='object' || Array.isArray(item.source))throw Error('Invalid source');
    for(const k of ['label','kind','rights','url','retrieved_at','attribution','inspiration']){
      if(item.source[k]===undefined)item.source[k]='';
      if(typeof item.source[k]!=='string' || bytes(item.source[k])>4000)throw Error('Invalid source '+k);
    }
    if(!['user_notes','original_example','authorized_excerpt','authorized_transcript'].includes(item.source.kind))throw Error('Unsupported source kind');
    item.schema='toad-empathy-lesson-v2';return item;
  }
  function receive(raw){
    const item=normalize(raw),claims={};
    for(const k of ['id','version','review_status','evaluations','history','previous_versions','imported_claims'])if(item[k]!==undefined)claims[k]=clone(item[k]);
    return {...item,id:id(),version:1,review_status:'needs_review',evaluations:[],previous_versions:[],imported_claims:claims,history:[{event:'received_unreviewed',at:now()}]};
  }
  function note(material,audience='general',source){return receive({material,audience,situation:typeof material==='string'?material.slice(0,300):'',...(source?{source}:{})});}
  function validate(data){
    bound(data,1900000);
    if(!data || data.schema!==SCHEMA || !Array.isArray(data.lessons) || data.lessons.length>100 || !Array.isArray(data.imports) || !Array.isArray(data.assessments))throw Error('Unsupported stored empathy library; download recovery');
    const ids=new Set();
    for(const item of data.lessons){normalize(item);if(typeof item.id!=='string' || ids.has(item.id) || !Number.isInteger(item.version) || item.version<1 || !STATUSES.includes(item.review_status) || !Array.isArray(item.history) || !Array.isArray(item.previous_versions))throw Error('Invalid stored lesson');ids.add(item.id);}
    return clone(data);
  }
  function merge(current,incoming){
    validate(current);bound(incoming);
    if(!incoming || !['toad-empathy-v1',SCHEMA].includes(incoming.schema))throw Error('Unsupported empathy backup schema');
    const key=incoming.schema==='toad-empathy-v1'?'examples':'lessons',raw=incoming[key];
    if(!Array.isArray(raw) || raw.length>100)throw Error('Invalid lesson list');
    const records=raw.map(receive),result=clone(current);
    // Exact original payload equality only; differing unknown metadata is retained.
    for(let i=0;i<records.length;i++){
      const payload=JSON.stringify(raw[i]);
      const original=r=>Array.isArray(r.received_fields)?Object.fromEntries(r.received_fields.map(k=>[k,Object.hasOwn(r.imported_claims || {},k)?r.imported_claims[k]:r[k]])):null;
      if(!result.lessons.some(r=>JSON.stringify(original(r))===payload))result.lessons.push({...records[i],received_fields:Object.keys(raw[i])});
    }
    const metadata=Object.fromEntries(Object.entries(incoming).filter(([k])=>k!==key));
    if(!result.imports.some(x=>JSON.stringify(x)===JSON.stringify(metadata)))result.imports.push(metadata);
    return validate(result);
  }
  function edit(record,changes){
    if(!changes || Object.keys(changes).some(k=>!FIELDS.includes(k)))throw Error('Only lesson content fields can be corrected');
    if(changes.source!==undefined && (!changes.source || typeof changes.source!=='object' || Array.isArray(changes.source)))throw Error('Invalid source correction');
    const result=normalize({...record,...changes,...(changes.source?{source:{...record.source,...changes.source}}:{})});
    if(record.previous_versions.length>=20)throw Error('Revision limit reached; export first');
    const previous=clone(record);delete previous.previous_versions;
    result.previous_versions=[...clone(record.previous_versions),previous];result.version++;
    result.review_status='needs_review';result.history.push({event:'corrected_review_invalidated',at:now(),version:result.version});return result;
  }
  function review(record,status,note){
    if(!STATUSES.includes(status) || typeof note!=='string' || !note.trim() || note.length>4000)throw Error('Choose a review status and write a human review note');
    if(status==='helpful' && ['','not_recorded'].includes(record.source.rights) && record.source.kind!=='user_notes')throw Error('Record source rights before approval');
    record.review_status=status;record.history.push({event:'human_review',status,note,version:record.version,at:now()});return record;
  }
  const words=text=>new Set(text.toLowerCase().match(/[\p{L}\p{N}_]{3,}/gu) || []);
  function retrieve(data,query,audience='adult'){
    if(!AUDIENCES.includes(audience) || typeof query!=='string' || bytes(query)>4000)throw Error('Invalid retrieval query');
    const tokens=words(query);
    return data.lessons.filter(x=>x.review_status==='helpful' && [audience,'general'].includes(x.audience)).map(x=>({item:x,score:[...tokens].filter(w=>words(FIELDS.filter(k=>k!=='source').map(k=>x[k]).join(' ')).has(w)).length})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,3).map(x=>x.item);
  }
  function assessment(scenario,baseline,retrieved,scores,lessons){
    if(!scenario || typeof scenario.prompt!=='string' || !AUDIENCES.includes(scenario.audience) || typeof baseline!=='string' || typeof retrieved!=='string' || !baseline.trim() || !retrieved.trim() || bytes(baseline)>8000 || bytes(retrieved)>8000)throw Error('Provide both bounded responses before rating');
    for(const key of RUBRIC)for(const arm of ['baseline','retrieved'])if(!scores[key] || ![0,1,2,'na'].includes(scores[key][arm]))throw Error('Complete every rubric rating (or choose N/A)');
    return {id:id(),schema:'toad-empathy-comparison-v1',split:'practice',scenario_id:scenario.id,scenario:scenario.prompt,audience:scenario.audience,baseline:{response:baseline},retrieved:{response:retrieved,lesson_versions:lessons.map(x=>({id:x.id,version:x.version}))},human_ratings:[clone(scores)],model_ratings:[],improvement:null,origin:'human_self_report',response_origin:'user_supplied_unverified',at:now()};
  }
  return Object.freeze({SCHEMA,AUDIENCES,STATUSES,FIELDS,RUBRIC,empty,normalize,note,merge,edit,review,retrieve,validate,assessment,bytes});
});
