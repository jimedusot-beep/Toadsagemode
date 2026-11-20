/* Project Explorer V1. Fixture-only and read-only.
 * No API calls except loading the same-origin reviewed fixture JSON.
 * Never use innerHTML, eval, iframes, localStorage or executable previews here.
 */
(() => {
  'use strict';

  function boot() {
    const api = window.SageExplorerAdapter;
    const $ = selector => document.querySelector(selector);
    const ui = {
      notice: $('#explorer-notice'), retry: $('#explorer-retry'),
      importFile: $('#explorer-import-file'), importButton: $('#explorer-import'),
      reset: $('#explorer-reset'),
      projects: $('#explorer-project-list'), count: $('#explorer-count'),
      state: $('#explorer-project-state'), stateDetail: $('#explorer-state-explanation'),
      title: $('#explorer-project-title'),
      summary: $('#explorer-project-summary'), files: $('#explorer-file-list'),
      searchForm: $('#explorer-search-form'), searchInput: $('#explorer-search-input'),
      searchButton: $('#explorer-search-button'), searchClear: $('#explorer-search-clear'),
      searchStatus: $('#explorer-search-status'), searchResults: $('#explorer-search-results'),
      empty: $('#explorer-empty'), path: $('#explorer-selected-path'),
      source: $('#explorer-source'), revisionState: $('#explorer-revision-state'),
      revisionSummary: $('#explorer-revision-summary'),
      diffStatus: $('#explorer-diff-status'),
      before: $('#explorer-before'), after: $('#explorer-after'),
      approve: $('#explorer-approve'), reject: $('#explorer-reject'),
      decision: $('#explorer-decision'), testState: $('#explorer-test-state'),
      testOutput: $('#explorer-test-output'),
      revisionOutput: $('#explorer-revision-output')
    };
    if (!api || !ui.projects || !ui.retry) return;
    let catalog = null;
    let selectedId = null;
    let selectedPath = null;
    let loading = false;
    let importing = false;
    let fixtureGeneration = 0; // Any reset/import invalidates older asynchronous fixture reads.
    const decisions = new Map(); // Session memory ONLY. Never a code write or backend approval.

    function node(tag, className, text) {
      const el = document.createElement(tag);
      if (className) el.className = className;
      if (text !== undefined) el.textContent = text;
      return el;
    }
    function clear(el) { el.replaceChildren(); }
    function announce(message, error = false) {
      ui.notice.textContent = message;
      ui.notice.classList.toggle('error', error);
    }
    function badge(el, state) {
      el.dataset.state = state;
      el.textContent = 'Fixture: ' + state + ' (sample only)';
    }
    function selectedProject() {
      return catalog?.projects.find(p => p.id === selectedId) || null;
    }
    function clearSearch() {
      ui.searchInput.value = '';
      ui.searchResults.replaceChildren();
      ui.searchClear.disabled = true;
      ui.searchStatus.textContent = selectedProject()
        ? 'No search active. Enter a term to search this local example.'
        : 'Select a fixture project before searching.';
    }
    function showSearchResults(result) {
      ui.searchResults.replaceChildren();
      ui.searchClear.disabled = false;
      if (!result.matches.length) {
        ui.searchStatus.textContent = 'No fixture matches found for the requested term. This is not a backend search.';
        return;
      }
      ui.searchStatus.textContent = result.limited
        ? 'Showing the first 50 fixture matches (limit reached). More matches may exist. No live service was searched.'
        : result.matches.length + ' fixture matches found. No live service was searched.';
      for (const match of result.matches) {
        const li = node('li');
        const button = node('button', 'explorer-search-result');
        button.type = 'button';
        const place = match.kind === 'filename' ? 'filename' : 'line ' + match.line;
        button.setAttribute('aria-label', 'Open sample source result: ' + match.path + ', ' + place);
        button.append(
          node('strong', '', match.path + ' · ' + place),
          node('span', 'explorer-search-snippet', match.snippet)
        );
        button.addEventListener('click', () => {
          if (selectedProject()?.id !== result.project_id) {
            clearSearch();
            announce('Search result is stale; select a fixture project and search again.', true);
            return;
          }
          selectedPath = match.path;
          render();
          if (match.line > 0) {
            const computed = getComputedStyle(ui.source);
            const lineHeight = Number.parseFloat(computed.lineHeight) || 21;
            ui.source.scrollTop = Math.max(0, (match.line - 1) * lineHeight - lineHeight * 2);
          }
          ui.source.focus({preventScroll:true});
          announce('Opened sample file ' + match.path +
            (match.line ? ', line ' + match.line : ', filename match') +
            '. Source remains read-only fixture text.');
        });
        li.append(button);
        ui.searchResults.append(li);
      }
    }
    function renderProjects() {
      clear(ui.projects);
      ui.count.textContent = catalog ? catalog.projects.length + ' examples' : '0 examples';
      if (!catalog) return;
      catalog.projects.forEach(project => {
        const li = node('li');
        const button = node('button', 'explorer-project-button');
        button.type = 'button';
        button.setAttribute('aria-pressed', String(project.id === selectedId));
        button.setAttribute('aria-label', 'Open fixture project: ' + project.title);
        button.append(node('strong', '', project.title), node('small', '', 'Fixture: ' + project.state));
        button.addEventListener('click', () => {
          selectedId = project.id;
          selectedPath = project.files[0]?.path || null;
          clearSearch();
          render();
          // render() replaces buttons. Restore a logical keyboard/VoiceOver position.
          ui.projects.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true});
          announce('Loaded fixture project ' + project.title + '. Source is read-only.');
        });
        li.append(button);
        ui.projects.append(li);
      });
    }
    function fileHierarchy(files) {
      const root = {folders: new Map(), files: []};
      files.forEach(file => {
        let current = root;
        const parts = file.path.split('/');
        for (let i = 0; i < parts.length - 1; i++) {
          const part = parts[i];
          if (!current.folders.has(part)) current.folders.set(part, {folders: new Map(), files: []});
          current = current.folders.get(part);
        }
        current.files.push({name: parts[parts.length - 1], path: file.path});
      });
      return root;
    }
    function renderFolder(tree, list) {
      [...tree.folders.keys()].sort().forEach(name => {
        const li = node('li');
        li.append(node('span', 'explorer-file-folder', '▸ ' + name + '/'));
        const nested = node('ul');
        renderFolder(tree.folders.get(name), nested);
        li.append(nested);
        list.append(li);
      });
      tree.files.sort((a, b) => a.name.localeCompare(b.name)).forEach(file => {
        const li = node('li');
        const button = node('button', 'explorer-file-button', file.name);
        button.type = 'button';
        button.setAttribute('aria-label', 'Read source: ' + file.path);
        if (file.path === selectedPath) button.setAttribute('aria-current', 'true');
        button.addEventListener('click', () => {
          selectedPath = file.path;
          renderSource(selectedProject());
          ui.files.querySelectorAll('button').forEach(btn => {
            const active = btn.getAttribute('aria-label') === 'Read source: ' + file.path;
            if (active) btn.setAttribute('aria-current', 'true');
            else btn.removeAttribute('aria-current');
          });
          announce('Showing ' + file.path + ' as inert source text.');
        });
        li.append(button);
        list.append(li);
      });
    }
    function renderSource(project) {
      const file = project?.files.find(item => item.path === selectedPath);
      ui.path.textContent = file ? file.path : 'No file selected';
      ui.source.textContent = file ? file.content : 'No source files are available for this example.';
      ui.source.scrollTop = 0;
    }
    const MAX_HIGHLIGHT_LINES = 600;
    function diffText(el, changes, side) {
      clear(el);
      let number = 0;
      changes.forEach(part => {
        if (side === 'before' && part.kind === 'added') return;
        if (side === 'after' && part.kind === 'removed') return;
        number++;
        const symbol = part.kind === 'added' ? '+' : (part.kind === 'removed' ? '−' : ' ');
        const label = String(number).padStart(4, ' ') + ' ' + symbol + ' ' + part.text;
        el.append(node('span', 'diff-line diff-' + part.kind, label));
      });
    }
    function renderRevision(project) {
      const proposal = project?.revision;
      badge(ui.revisionState, proposal?.status || 'blocked');
      if (!proposal) {
        ui.revisionSummary.textContent = 'No proposed revision exists for this fixture project.';
        ui.diffStatus.textContent = 'No source comparison available.';
        ui.before.textContent = 'No revision';
        ui.after.textContent = 'No revision';
      } else {
        const comparison = api.compareSource(proposal.before, proposal.after);
        const lines = comparison.lines;
        ui.revisionSummary.textContent = 'Example revision ' + proposal.id +
          ' · ' + proposal.path + ' · sample source comparison only.';
        if (lines.length > MAX_HIGHLIGHT_LINES) {
          // All source remains visible. Avoid thousands of mobile DOM spans.
          ui.before.textContent = proposal.before;
          ui.after.textContent = proposal.after;
          ui.diffStatus.textContent = 'Large comparison: showing the COMPLETE original and proposed source as plain text. Highlighting and line numbers are disabled to keep the page responsive. ' +
            (comparison.mode === 'coarse' ? 'Line-level diff was too large; change counts are approximate.' :
              'Exact line-change totals: ' + comparison.added + ' added, ' + comparison.removed + ' removed.');
        } else {
          diffText(ui.before, lines, 'before');
          diffText(ui.after, lines, 'after');
          ui.diffStatus.textContent = comparison.mode === 'exact'
            ? 'Exact line comparison: ' + comparison.added + ' added, ' +
              comparison.removed + ' removed, ' + comparison.hunks +
              ' change groups. This is sample text, not a test result.'
            : 'Coarse comparison (large change region): highlighted lines and change totals are APPROXIMATE. ' +
              'Some unchanged middle lines may appear changed. Read both full source panes before deciding.';
        }
      }
      const decision = project && decisions.get(project.id);
      ui.approve.disabled = !proposal || !!decision;
      ui.reject.disabled = !proposal || !!decision;
      ui.decision.textContent = decision
        ? 'Demo ' + decision + ' recorded for this page only. No source, test, or GitHub state changed.'
        : proposal ? 'No demo decision recorded. A confirmation is required.'
          : 'No revision available to approve or reject.';
    }
    function renderTests(project) {
      badge(ui.testState, project?.test.status || 'blocked');
      ui.testOutput.textContent = project?.test.output ||
        'No sample test output available. No test was executed.';
      ui.revisionOutput.textContent = project?.revision?.test.output ||
        'No revision test output available. No test was executed.';
    }
    function render() {
      const project = selectedProject();
      renderProjects();
      ui.title.textContent = project?.title || 'No project selected';
      ui.summary.textContent = project?.summary || 'No example project is available.';
      badge(ui.state, project?.state || 'blocked');
      const descriptions = {
        draft: 'Example draft only. No independent tests or release approval exist.',
        untested: 'Example only. No independent test receipt exists.',
        testing: 'Simulated testing label only. No test worker is running.',
        failed: 'Simulated failed test output only. No real test ran here.',
        verified: 'SIMULATED verified label only. NO independent verification evidence exists.',
        blocked: 'Example is blocked. This page cannot run or release source.'
      };
      ui.stateDetail.textContent = project ? descriptions[project.state] :
        'No sample project loaded. Nothing is verified or approved.';
      ui.searchInput.disabled = !project;
      ui.searchButton.disabled = !project;
      if (!project) ui.searchClear.disabled = true;
      clear(ui.files);
      ui.empty.hidden = Boolean(project?.files.length);
      if (project?.files.length) renderFolder(fileHierarchy(project.files), ui.files);
      else ui.empty.textContent = project
        ? 'Empty project: this fixture has no source files.'
        : 'No source files to display.';
      renderSource(project);
      renderRevision(project);
      renderTests(project);
    }
    function demoDecision(choice) {
      const project = selectedProject();
      if (!project?.revision || decisions.has(project.id)) return;
      const question = choice === 'approved' ? 'Approve' : 'Reject';
      if (!window.confirm(question + ' this FIXTURE revision? This is a page-memory example only. No source, tests or production code will change.')) {
        announce('Demo decision cancelled. Nothing changed.');
        return;
      }
      decisions.set(project.id, choice);
      renderRevision(project);
      announce('Demo revision ' + choice + '. This does not authorize a real change.');
    }
    async function load() {
      // Reset can supersede an in-flight import or an earlier fixture request.
      const requestId = ++fixtureGeneration;
      loading = true;
      ui.importFile.value = '';
      ui.importButton.disabled = true;
      catalog = null;
      selectedId = null;
      selectedPath = null;
      clearSearch();
      render();
      ui.retry.hidden = true;
      announce('Loading local sample projects…');
      try {
        const next = await api.loadFixtures(window.fetch.bind(window));
        if (requestId !== fixtureGeneration) return; // Superseded response.
        catalog = next;
        decisions.clear();
        selectedId = catalog.projects[0]?.id || null;
        selectedPath = catalog.projects[0]?.files[0]?.path || null;
        render();
        announce('Loaded ' + catalog.projects.length + ' fixture projects. No model, execution worker or live backend contacted.');
      } catch (error) {
        if (requestId !== fixtureGeneration) return;
        // Do not show untrusted raw fetch errors or accidentally preserve stale fixture UI.
        catalog = null;
        selectedId = null;
        selectedPath = null;
        render();
        ui.retry.hidden = false;
        announce('Cannot load safe fixture project data. No project or approval is available. ' +
          (error instanceof Error ? error.message : 'Check the local file and retry.'), true);
      } finally {
        if (requestId === fixtureGeneration) loading = false;
      }
    }
    async function importFixture() {
      if (importing || loading) return;
      const file = ui.importFile.files?.[0];
      if (!file) return;
      const requestId = fixtureGeneration;
      importing = true;
      ui.importButton.disabled = true;
      try {
      if (file.size > 100000) {
        announce('Fixture import refused: file exceeds 100 KB. Current projects are unchanged.', true);
        return;
      }
      let next;
      try {
        const bytes = await file.arrayBuffer();
        if (requestId !== fixtureGeneration) return; // Reset during local file read.
        const text = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
        if (text.length > 100000) throw Error('oversized');
        next = api.validateCatalog(JSON.parse(text));
      } catch (_) {
        if (requestId !== fixtureGeneration) return;
        announce('Fixture import refused: invalid UTF-8, JSON or project data. Current projects are unchanged.', true);
        return;
      }
      if (requestId !== fixtureGeneration) return;
      if (!window.confirm('Replace the displayed FIXTURE projects with examples from this JSON? No real source files, tests or GitHub content will change.')) {
        announce('Fixture import cancelled. Current projects are unchanged.');
        return;
      }
      if (requestId !== fixtureGeneration) return;
      ++fixtureGeneration; // Any other pending read must not replace imported fixtures.
      catalog = next;
      decisions.clear();
      selectedId = catalog.projects[0]?.id || null;
      selectedPath = catalog.projects[0]?.files[0]?.path || null;
      clearSearch();
      render();
      ui.importFile.value = '';
      ui.importButton.disabled = true;
      announce('Loaded ' + catalog.projects.length + ' local imported fixture projects. No production project imported.');
      } finally {
        importing = false;
        ui.importButton.disabled = !ui.importFile.files?.length;
      }
    }
    ui.searchForm.addEventListener('submit', event => {
      event.preventDefault();
      const project = selectedProject();
      if (!project) return;
      let result;
      try {
        result = api.searchFixtureProject(project, ui.searchInput.value, 50);
      } catch (_) {
        ui.searchResults.replaceChildren();
        ui.searchClear.disabled = false;
        ui.searchStatus.textContent = 'Search blocked: enter 1–100 UTF-8 bytes of plain text without control characters.';
        return;
      }
      showSearchResults(result);
    });
    ui.searchClear.addEventListener('click', () => {
      clearSearch();
      ui.searchInput.focus();
    });
    ui.searchInput.addEventListener('input', () => {
      if (ui.searchClear.disabled) return;
      ui.searchResults.replaceChildren();
      ui.searchClear.disabled = true;
      ui.searchStatus.textContent = 'Search term changed. Run Search again for current results.';
    });
    ui.importFile.addEventListener('change', () => {
      ui.importButton.disabled = !ui.importFile.files?.length;
    });
    ui.importButton.addEventListener('click', importFixture);
    ui.reset.addEventListener('click', load);
    ui.retry.addEventListener('click', load);
    ui.approve.addEventListener('click', () => demoDecision('approved'));
    ui.reject.addEventListener('click', () => demoDecision('rejected'));
    load();
  }
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
    else boot();
  }
})();
