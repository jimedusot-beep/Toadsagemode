/* SageCode contract inspector: text-only, static fixture source, no API. */
(() => {
  'use strict';
  function boot() {
    const adapter=window.SageCodeContractAdapter;
    const $=selector=>document.querySelector(selector);
    const ui={
      notice:$('#sage-notice'),retry:$('#sage-retry'),
      state:$('#sage-state'),project:$('#sage-project-id'),
      revision:$('#sage-revision'),baseline:$('#sage-baseline'),
      evidence:$('#sage-evidence'),approval:$('#sage-approval'),
      tree:$('#sage-tree'),emptyTree:$('#sage-empty-tree'),
      sourceName:$('#sage-source-name'),navNote:$('#sage-navigation-note'),
      sourceState:$('#sage-source-state'),source:$('#sage-source'),
      limits:$('#sage-source-limits'),
      searchState:$('#sage-search-state'),searchResults:$('#sage-search-results'),
      proposalState:$('#sage-proposal-state'),proposalSummary:$('#sage-proposal-summary'),
      diff:$('#sage-diff'),proposalWarning:$('#sage-proposal-warning')
    };
    if(!adapter || !ui.retry) return;
    let sample=null;
    let selected=null;
    let loading=false;
    function elem(tag,cls,value) {
      const el=document.createElement(tag);
      if(cls) el.className=cls;
      if(value!==undefined) el.textContent=value;
      return el;
    }
    function clearScreen() {
      sample=null;selected=null;
      ui.state.textContent='Not loaded';
      ui.state.dataset.state='blocked';
      ui.project.textContent='No project selected.';
      ui.revision.textContent='Unavailable';
      ui.baseline.textContent='Unavailable';
      ui.evidence.textContent='Not available';
      ui.approval.textContent='Not authorized';
      ui.tree.replaceChildren();
      ui.emptyTree.hidden=true;
      ui.sourceName.textContent='No source selected';
      ui.navNote.textContent='No source line selected.';
      ui.sourceState.textContent='No source evidence loaded.';
      ui.source.textContent='No source to display.';
      ui.limits.textContent='A partial read cannot establish the entire source digest.';
      ui.searchState.textContent='No sample search loaded.';
      ui.searchResults.replaceChildren();
      ui.proposalState.textContent='Unreviewed';
      ui.proposalState.dataset.state='blocked';
      ui.proposalSummary.textContent='No sample proposal loaded.';
      ui.diff.textContent='No source diff available.';
      ui.proposalWarning.textContent='No test receipts or approval are available.';
    }
    function sourceFor(name,focus=false,line=0) {
      if(!sample) return;
      const source=sample.view.sources.find(item=>item.path===name);
      const check=sample.results.find(item=>item.path===name);
      if(!source || !check) return;
      selected=name;
      ui.sourceName.textContent=source.path;
      ui.source.textContent=source.content;
      // A later-page response may say truncated:false because no LATER pages
      // remain; this is still not the whole file if start_line > 1.
      const partial=source.truncated || source.start_line>1;
      const visibleLines=adapter.countLines(source.content);
      const visibleEnd=visibleLines ? source.start_line+visibleLines-1 : source.start_line;
      const part=partial ? 'Partial read' : 'Full sample read';
      const hash=check.check==='fixture_hash_matches'
        ? 'SHA-256 matches sample metadata; no authenticity or safety proof.'
        : 'Whole-file hash cannot be checked from a partial view.';
      ui.sourceState.textContent=part+
        (visibleLines ? ' · visible lines '+source.start_line+'–'+visibleEnd :
          ' · empty excerpt')+
        ' of '+source.total_lines+' · '+hash;
      ui.limits.textContent=source.truncated
        ? 'TRUNCATED SAMPLE: some source is omitted. The page has no additional read endpoint; displayed content is not complete.'
        : source.start_line>1
          ? 'PARTIAL SAMPLE: this later-page read omits earlier lines even though truncated=false. No whole-file SHA-256 check or previous-page endpoint exists.'
          : 'Read-only example source. A hash match is not a test, trusted server attestation or approval.';
      ui.tree.querySelectorAll('button').forEach(btn=>{
        if(btn.dataset.path===name)btn.setAttribute('aria-current','true');
        else btn.removeAttribute('aria-current');
      });
      ui.source.scrollTop=0;
      if(line>0 && (line<source.start_line || line>visibleEnd || visibleLines===0)) {
        ui.navNote.textContent='Sample search hit at line '+line+
          ' is OUTSIDE the loaded excerpt (visible '+source.start_line+'–'+visibleEnd+
          '). No additional source can be fetched here; the matching line is not displayed.';
      } else if(line>0) {
        const css=getComputedStyle(ui.source);
        const height=Number.parseFloat(css.lineHeight)||20;
        ui.source.scrollTop=Math.max(0,(line-source.start_line-2)*height);
        ui.navNote.textContent='Sample source navigated to visible line '+line+'.';
      } else {
        ui.navNote.textContent='Read-only fixture file selected. No source line was requested.';
      }
      if(focus)ui.source.focus({preventScroll:true});
    }
    function render() {
      const {view,results}=sample;
      const status=view.status;
      ui.state.textContent='Source-only · UNVERIFIED example';
      ui.state.dataset.state='untested';
      ui.project.textContent='Fixture project: '+status.project_id;
      ui.revision.textContent=status.revision;
      ui.baseline.textContent=status.baseline_revision;
      ui.evidence.textContent='Null: no execution, test run or receipt';
      ui.approval.textContent='False: no owner approval or release permission';
      ui.tree.replaceChildren();
      ui.emptyTree.hidden=view.tree.entries.some(item=>item.kind==='file');
      for(const item of view.tree.entries){
        const li=elem('li');
        if(item.kind==='directory') {
          li.append(elem('span','sage-directory','▸ '+item.path+'/'));
        } else {
          const button=elem('button','explorer-file-button',item.path);
          button.type='button';
          button.dataset.path=item.path;
          button.setAttribute('aria-label','Read SageCode fixture source: '+item.path);
          button.addEventListener('click',()=>sourceFor(item.path,true));
          li.append(button);
        }
        ui.tree.append(li);
      }
      ui.searchResults.replaceChildren();
      ui.searchState.textContent='Example term: "'+view.search.term+'" · '+
        view.search.matches.length+' fixture hit(s).'+
        (view.search.limited?' Sample result limit reached; more hits may exist.' :
          view.search.matches.length===0 ? ' No sample matches; no live search occurred.' :
          ' Not a live search.');
      for(const hit of view.search.matches){
        const li=elem('li');
        const button=elem('button','explorer-search-result');
        button.type='button';
        const line=hit.kind==='filename'?'filename match':'line '+hit.line;
        button.setAttribute('aria-label','Open contract example hit: '+hit.path+', '+line);
        button.append(elem('strong','',hit.path+' · '+line),
          elem('span','explorer-search-snippet',hit.snippet));
        button.addEventListener('click',()=>sourceFor(hit.path,true,hit.line));
        li.append(button);
        ui.searchResults.append(li);
      }
      if(view.proposal){
        ui.proposalState.textContent='Unverified · pending owner review';
        ui.proposalState.dataset.state='untested';
        ui.proposalSummary.textContent='Proposed revision '+view.proposal.revision+
          ' · parent '+view.proposal.parent_revision+
          '. Example only, never installed.';
        ui.diff.textContent=view.proposal.diff;
        ui.proposalWarning.textContent=view.proposal.truncated
          ? 'TRUNCATED DIFF: review is incomplete. No tests or approvals exist; this UI cannot apply source.'
          : 'Complete example diff text (not executed). No independent tests, approvals or release permissions.';
      }else{
        ui.proposalState.textContent='No proposal';
        ui.proposalState.dataset.state='blocked';
        ui.proposalSummary.textContent='No sample revision proposal exists.';
        ui.diff.textContent='No diff.';
      }
      const first=selected || view.sources[0]?.path;
      if(first)sourceFor(first);
    }
    async function load(){
      if(loading)return;
      loading=true;
      clearScreen();
      ui.retry.hidden=true;
      ui.notice.classList.remove('error');
      ui.notice.textContent='Loading local sample and checking complete source hashes…';
      try{
        sample=await adapter.loadFixture(window.fetch.bind(window),window.crypto?.subtle);
        render();
        ui.notice.textContent='Loaded SageCode contract fixture: '+sample.results.length+
          ' sample source records checked for metadata consistency. No real model, API, tests or approvals.';
      }catch(_){
        clearScreen();
        ui.retry.hidden=false;
        ui.notice.classList.add('error');
        ui.notice.textContent='Blocked: SageCode contract sample is missing, invalid or failed its source integrity check. No source or revision is available.';
      }finally{loading=false;}
    }
    ui.retry.addEventListener('click',load);
    load();
  }
  if(typeof document!=='undefined'){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
    else boot();
  }
})();
