/* Trusted $0 App Studio browser package generator.
   Exactly three reviewed app kinds. No LLM, remote APIs, eval or uploads.
*/
(() => {
  'use strict';
  const KINDS = Object.freeze(['tasks', 'notes', 'flashcards']);
  const THEMES = Object.freeze(['forest', 'midnight']);
  const NAMES = /^[a-z][a-z0-9-]{1,39}$/;
  const encoder = new TextEncoder();

  function validateCatalog(bundle) {
    if (!bundle || bundle.schema !== 'toad-free-studio-templates-v1' ||
        !bundle.templates || typeof bundle.templates !== 'object' ||
        Object.keys(bundle.templates).sort().join(',') !== KINDS.slice().sort().join(',')) {
      throw Error('Reviewed app template catalog is unavailable or invalid.');
    }
    for (const kind of KINDS) {
      const entry = bundle.templates[kind];
      if (!entry || Object.keys(entry).sort().join(',') !== 'css,html,js') {
        throw Error('Incomplete reviewed template: ' + kind);
      }
      for (const part of ['html','css','js']) {
        if (typeof entry[part] !== 'string' || !entry[part].trim() || entry[part].length > 80000) {
          throw Error('Invalid reviewed app template.');
        }
      }
    }
    return bundle;
  }

  function validateInput({kind,name,title,theme}) {
    if (!KINDS.includes(kind) || !THEMES.includes(theme)) {
      throw Error('Choose a supported app and theme.');
    }
    if (typeof name !== 'string' || !NAMES.test(name)) {
      throw Error('App name must use 2–40 lowercase letters, numbers or hyphens, starting with a letter.');
    }
    if (typeof title !== 'string' || !title.trim() || title.length > 80 ||
        [...title].some(ch => ch.charCodeAt(0) < 32 || ch.charCodeAt(0) === 127)) {
      throw Error('Enter a title of 1–80 characters without line breaks.');
    }
    return {kind,name,title:title.trim(),theme};
  }

  function escapeHtml(text) {
    return text.replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function makeSources(bundle, options) {
    validateCatalog(bundle);
    const {kind,name,title,theme} = validateInput(options);
    const selected = bundle.templates[kind];
    const storageKey = 'toad-sage-' + kind + '-v1:' + name;
    let script = selected.js;
    if (kind === 'tasks') {
      const old = "const KEY = 'toad-sage-task-list-v1';";
      if (!script.includes(old)) throw Error('Trusted task key is missing.');
      script = script.replace(old, "const KEY = '" + storageKey + "';");
    } else {
      if (!script.includes('{{STORAGE_KEY}}')) throw Error('Trusted app key is missing.');
      script = script.replace('{{STORAGE_KEY}}', storageKey);
    }
    if (!selected.html.includes('{{TITLE}}') || !selected.html.includes('{{THEME}}')) {
      throw Error('Trusted app HTML template is invalid.');
    }
    const html = selected.html.replaceAll('{{TITLE}}',escapeHtml(title))
      .replaceAll('{{THEME}}',theme);
    const readme = [
      '# ' + title,
      '',
      'A standalone Toad Sage ' + kind + ' app from an owner-reviewed offline template.',
      'Run on a trusted static HTTPS host, e.g. Netlify Drop.',
      'All data stays only in this browser when local storage is available.',
      'No accounts, AI calls, sync, tracking, or external dependencies.',
      'Never store credentials, client health records, or sensitive data in this demo.',
      'The generated ZIP has not itself passed browser tests or been deployed.',
      'Source review and owner approval are required before publishing.',
      ''
    ].join('\n');
    return {
      'index.html': html,
      'styles.css': selected.css,
      'app.js': script,
      'README.md': readme,
    };
  }

  function write16(view,offset,value){view.setUint16(offset,value,true);}
  function write32(view,offset,value){view.setUint32(offset,value>>>0,true);}

  const CRC = new Uint32Array(256);
  for (let i=0;i<256;i++) {
    let crc=i;
    for (let j=0;j<8;j++) crc=(crc&1)?(0xedb88320^(crc>>>1)):(crc>>>1);
    CRC[i]=crc>>>0;
  }
  function crc32(bytes) {
    let crc=0xffffffff;
    for (const value of bytes) crc=CRC[(crc^value)&0xff]^(crc>>>8);
    return (crc^0xffffffff)>>>0;
  }

  /* ZIP STORE only. Non-executable bytes, no third-party compressor. */
  function makeZip(source) {
    const names = Object.keys(source);
    const allowed = new Set(['index.html','styles.css','app.js','README.md','build_report.json']);
    if (names.length !== allowed.size || new Set(names).size !== allowed.size ||
        names.some(n => !allowed.has(n))) {
      throw Error('Invalid ZIP file manifest.');
    }
    const entries=names.map(name=>{
      const data=encoder.encode(source[name]);
      const filename=encoder.encode(name);
      if (data.length > 150000 || filename.length > 100) throw Error('App file too large.');
      return {name, data, filename, crc:crc32(data), offset:0};
    });
    const pieces=[];
    let size=0;
    for (const entry of entries) {
      entry.offset=size;
      const header=new Uint8Array(30+entry.filename.length);
      const v=new DataView(header.buffer);
      write32(v,0,0x04034b50);write16(v,4,20);
      write32(v,14,entry.crc);
      write32(v,18,entry.data.length);write32(v,22,entry.data.length);
      write16(v,26,entry.filename.length);
      header.set(entry.filename,30);
      pieces.push(header,entry.data);
      size+=header.length+entry.data.length;
    }
    const centralOffset=size;
    for (const entry of entries) {
      const header=new Uint8Array(46+entry.filename.length);
      const v=new DataView(header.buffer);
      write32(v,0,0x02014b50);write16(v,4,20);write16(v,6,20);
      write32(v,16,entry.crc);
      write32(v,20,entry.data.length);write32(v,24,entry.data.length);
      write16(v,28,entry.filename.length);
      write32(v,42,entry.offset);
      header.set(entry.filename,46);
      pieces.push(header);
      size+=header.length;
    }
    const end=new Uint8Array(22);
    const v=new DataView(end.buffer);
    write32(v,0,0x06054b50);write16(v,8,entries.length);
    write16(v,10,entries.length);
    write32(v,12,size-centralOffset);
    write32(v,16,centralOffset);
    pieces.push(end);
    const total=size+end.length;
    if (total>400000) throw Error('App ZIP exceeds safe browser size.');
    const output=new Uint8Array(total);
    let pos=0;
    for (const part of pieces){output.set(part,pos);pos+=part.length;}
    return output;
  }

  async function sha256Hex(text) {
    if (!globalThis.crypto?.subtle) throw Error('HTTPS or localhost is required for integrity hashing.');
    const bytes=await crypto.subtle.digest('SHA-256',encoder.encode(text));
    return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
  }

  async function makePackage(bundle,options) {
    const fields=validateInput(options);
    const sources=makeSources(bundle,fields);
    const fileHashes={};
    for (const [path,content] of Object.entries(sources)) {
      fileHashes[path]=await sha256Hex(content);
    }
    const report={
      schema:'toad-app-build-v1',name:fields.name,title:fields.title,theme:fields.theme,
      template:'trusted-offline-'+fields.kind+'-v1',kind:fields.kind,
      status:'generated_unverified',files_sha256:fileHashes,
      test_evidence:'none_for_this_build',requires_owner_review:true,
      browser_tested_this_build:false,deployed:false,model_generated:false,
      paid_requests:0,server_requests:0,sandbox_executed:false,
    };
    sources['build_report.json']=JSON.stringify(report,null,2)+'\n';
    return {files:sources,zip:makeZip(sources),report};
  }

  // Inspect only STORE-mode ZIPs made by our reviewed browser template builder.
  // Never unpack to disk, execute uploaded code, or grant an uploaded file authority.
  function readBuildOptions(bytes) {
    const paths=['index.html','styles.css','app.js','README.md','build_report.json'];
    if (!(bytes instanceof Uint8Array) || bytes.length<100 || bytes.length>400000) {
      throw Error('Choose a supported small Toad Sage app ZIP.');
    }
    const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
    const decoder=new TextDecoder('utf-8',{fatal:true});
    let offset=0;
    let report=null;
    for(const expectedPath of paths) {
      if(offset+30>bytes.length || view.getUint32(offset,true)!==0x04034b50 ||
          view.getUint16(offset+6,true)!==0 || view.getUint16(offset+8,true)!==0) {
        throw Error('Unsupported ZIP format or file layout.');
      }
      const expectedCrc=view.getUint32(offset+14,true);
      const compressed=view.getUint32(offset+18,true);
      const uncompressed=view.getUint32(offset+22,true);
      const nameLength=view.getUint16(offset+26,true);
      const extraLength=view.getUint16(offset+28,true);
      if(compressed!==uncompressed || compressed>150000 ||
          nameLength===0 || nameLength>100 || extraLength!==0 ||
          offset+30+nameLength+compressed>bytes.length) {
        throw Error('Unexpected ZIP entries or file sizes.');
      }
      const pathStart=offset+30;
      const name=decoder.decode(bytes.subarray(pathStart,pathStart+nameLength));
      if(name!==expectedPath) throw Error('The ZIP contains unsupported file paths.');
      const start=pathStart+nameLength;
      const data=bytes.subarray(start,start+compressed);
      if(crc32(data)!==expectedCrc) throw Error('ZIP file checksum mismatch.');
      if(expectedPath==='build_report.json') {
        try { report=JSON.parse(decoder.decode(data)); }
        catch(_) { throw Error('The ZIP build report is not readable JSON.'); }
      }
      offset=start+compressed;
    }
    if(offset+4>bytes.length || view.getUint32(offset,true)!==0x02014b50 ||
        !report || typeof report!=='object' || Array.isArray(report)) {
      throw Error('The ZIP is incomplete or missing its build report.');
    }
    return validateInput({
      kind:report.kind,name:report.name,title:report.title,theme:report.theme
    });
  }

  async function verifyDownloadedZip(bundle,bytes) {
    validateCatalog(bundle);
    const options=readBuildOptions(bytes);
    // Rebuild from the currently loaded reviewed catalog, not from uploaded
    // source/report claims. A self-consistent but modified ZIP must still fail.
    const expected=await makePackage(bundle,options);
    if(expected.zip.length!==bytes.length ||
        expected.zip.some((value,index)=>value!==bytes[index])) {
      throw Error('ZIP source does not match the current reviewed templates.');
    }
    if(!globalThis.crypto?.subtle) throw Error('HTTPS is needed for ZIP hashing.');
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    return {
      status:'source_matches_current_reviewed_catalog',
      ...options,
      zip_sha256:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join(''),
      source_executed:false,
      individual_app_browser_tested:false,
      deployed:false,
      owner_review_required:true
    };
  }

  function suggestedSlug(title) {
    return (title||'my-app').toLowerCase().normalize('NFKD')
      .replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-')
      .replace(/^-+|-+$/g,'').replace(/^[^a-z]+/,'').slice(0,40).replace(/-+$/,'')||'my-app';
  }

  async function boot() {
    const form=document.querySelector('#build-form');
    const title=document.querySelector('#title');
    const slug=document.querySelector('#slug');
    const theme=document.querySelector('#theme');
    const status=document.querySelector('#status');
    const download=document.querySelector('#download');
    const verifyFile=document.querySelector('#verify-zip-file');
    const verifyButton=document.querySelector('#verify-zip');
    const verifyStatus=document.querySelector('#verify-status');
    let editedSlug=false;
    slug.addEventListener('input',()=>{editedSlug=true;});
    title.addEventListener('input',()=>{
      if (!editedSlug) slug.value=suggestedSlug(title.value);
    });
    function notice(value,state='') {
      status.textContent=value;
      status.className=state;
    }
    let catalog;
    try {
      const response=await fetch('./templates.json',{cache:'no-store'});
      if (!response.ok) throw Error('Missing reviewed template catalog');
      catalog=validateCatalog(await response.json());
      download.disabled=false;
      notice('Ready. No API calls or charges. This builds a ZIP on your device.');
    } catch (_) {
      notice('Templates could not load. Open this site through a secure HTTPS static host.', 'error');
      return;
    }
    const link=document.querySelector('#download-link');
    verifyFile.addEventListener('change',()=>{
      verifyButton.disabled=!verifyFile.files?.length;
      verifyStatus.textContent=verifyFile.files?.length ?
        'Selected ZIP has not been checked.' : 'Choose an app ZIP to inspect.';
      verifyStatus.className='';
    });
    verifyButton.addEventListener('click',async()=>{
      const file=verifyFile.files?.[0];
      if(!file) return;
      verifyButton.disabled=true;
      verifyStatus.textContent='Checking selected ZIP without executing it…';
      verifyStatus.className='';
      try {
        if(file.size>400000) throw Error('The selected ZIP exceeds the size limit.');
        const result=await verifyDownloadedZip(catalog,new Uint8Array(await file.arrayBuffer()));
        verifyStatus.textContent='Source match: '+result.title+' ('+result.kind+
          '). SHA-256 '+result.zip_sha256+'. No app code was run; owner review is still required.';
        verifyStatus.className='success';
      } catch(error) {
        verifyStatus.textContent='ZIP not verified: '+
          (error instanceof Error?error.message:'Unknown file error.');
        verifyStatus.className='error';
      } finally {
        verifyButton.disabled=!verifyFile.files?.length;
      }
    });
    let readyUrl=null;
    function invalidateReadyDownload() {
      link.hidden=true;
      link.removeAttribute('download');
      link.setAttribute('href','#');
      if(readyUrl){URL.revokeObjectURL(readyUrl);readyUrl=null;}
    }
    form.addEventListener('input',invalidateReadyDownload);
    form.addEventListener('change',invalidateReadyDownload);
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      invalidateReadyDownload();
      download.disabled=true;
      notice('Preparing your app locally…');
      try {
        const kind=form.querySelector('input[name="kind"]:checked')?.value;
        const result=await makePackage(catalog,{
          kind,name:slug.value,title:title.value,theme:theme.value
        });
        const blob=new Blob([result.zip],{type:'application/zip'});
        readyUrl=URL.createObjectURL(blob);
        link.href=readyUrl;
        link.download=result.report.name+'-toad-sage-app.zip';
        link.hidden=false;
        notice('ZIP prepared: '+result.report.title+' ('+result.zip.length+
          ' bytes). Tap Download prepared ZIP to save it, then upload to Netlify Drop.', 'success');
      } catch (error) {
        notice(error instanceof Error?error.message:'Could not create your app ZIP.', 'error');
      } finally {
        download.disabled=false;
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports={validateCatalog,validateInput,makeSources,makePackage,makeZip,
      readBuildOptions,verifyDownloadedZip,suggestedSlug,crc32};
  }
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
    else boot();
  }
})();
