/* Only reviewed, prebuilt static preview URLs are ever loaded. */
(() => {
  'use strict';
  const KINDS = Object.freeze(['tasks','notes','flashcards']);
  const THEMES = Object.freeze(['forest','midnight']);
  const TITLES = Object.freeze({
    tasks:'Task manager',notes:'Notes',flashcards:'Flashcards'
  });

  function previewRoute(kind,theme) {
    if (!KINDS.includes(kind) || !THEMES.includes(theme)) {
      throw Error('Only reviewed app previews may be loaded.');
    }
    return './previews/'+kind+'-'+theme+'/index.html';
  }
  function previewTitle(text) {
    if (typeof text!=='string' || !text.trim() || text.length>80 ||
        /[\u0000-\u001f\u007f]/.test(text)) return null;
    return text.trim();
  }

  function boot() {
    const form=document.querySelector('#build-form');
    const frame=document.querySelector('#interactive-frame');
    const label=document.querySelector('#interactive-label');
    const message=document.querySelector('#interactive-status');
    const reset=document.querySelector('#reset-interactive');
    if (!form || !frame || !label || !message || !reset) return;
    let currentRoute='';

    function settings() {
      return {
        kind:form.querySelector('input[name="kind"]:checked')?.value,
        theme:document.querySelector('#theme').value,
        title:document.querySelector('#title').value
      };
    }
    function sendTitle() {
      const title=previewTitle(settings().title);
      // The sandboxed frame has an opaque origin (null). targetOrigin '*'
      // is required, and only public visible title text is ever sent.
      // The recipient is an exact allowlisted local static URL.
      if (title && frame.contentWindow) {
        frame.contentWindow.postMessage({
          type:'toad-reviewed-preview-title-v1',title
        },'*');
      }
    }
    function show() {
      const {kind,theme}=settings();
      let route;
      try {route=previewRoute(kind,theme);}
      catch (_) {
        message.textContent='Only reviewed tasks, notes, and flashcards may be previewed.';
        return;
      }
      label.textContent=TITLES[kind]+' · '+(theme==='midnight'?'Midnight blue':'Forest green');
      frame.title='Isolated interactive '+TITLES[kind]+' preview';
      if (route!==currentRoute) {
        currentRoute=route;
        message.textContent='Loading a fresh temporary preview. Previous demo edits are discarded.';
        frame.src=route;
      } else {
        sendTitle();
      }
    }
    frame.addEventListener('load',()=>{
      sendTitle();
      message.textContent='Interactive preview ready. Demo data will reset when the frame is reloaded.';
    });
    frame.addEventListener('error',()=>{
      message.textContent='The reviewed preview could not load. No code has been executed.';
    });
    form.addEventListener('input',show);
    form.addEventListener('change',show);
    reset.addEventListener('click',()=>{
      if (!currentRoute) return;
      frame.src=currentRoute;
      message.textContent='Resetting temporary preview data…';
    });
    show();
  }
  if (typeof module!=='undefined' && module.exports) {
    module.exports={previewRoute,previewTitle};
  }
  if (typeof document!=='undefined') {
    if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
    else boot();
  }
})();
