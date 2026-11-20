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
      state: $('#explorer-project-state'), title: $('#explorer-project-title'),
      summary: $('#explorer-project-summary'), files: $('#explorer-file-list'),
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
          render();
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
      if (loading) return;
      loading = true;
      catalog = null;
      selectedId = null;
      selectedPath = null;
      render();
      ui.retry.hidden = true;
      announce('Loading local sample projects…');
      try {
        catalog = await api.loadFixtures(window.fetch.bind(window));
        decisions.clear();
        selectedId = catalog.projects[0]?.id || null;
        selectedPath = catalog.projects[0]?.files[0]?.path || null;
        render();
        announce('Loaded ' + catalog.projects.length + ' fixture projects. No model, execution worker or live backend contacted.');
      } catch (error) {
        // Do not show untrusted raw fetch errors or accidentally preserve stale fixture UI.
        catalog = null;
        selectedId = null;
        selectedPath = null;
        render();
        ui.retry.hidden = false;
        announce('Cannot load safe fixture project data. No project or approval is available. ' +
          (error instanceof Error ? error.message : 'Check the local file and retry.'), true);
      } finally {
        loading = false;
      }
    }
    async function importFixture() {
      const file = ui.importFile.files?.[0];
      if (!file) return;
      if (file.size > 100000) {
        announce('Fixture import refused: file exceeds 100 KB. Current projects are unchanged.', true);
        return;
      }
      let next;
      try {
        const bytes = await file.arrayBuffer();
        const text = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
        if (text.length > 100000) throw Error('oversized');
        next = api.validateCatalog(JSON.parse(text));
      } catch (_) {
        announce('Fixture import refused: invalid UTF-8, JSON or project data. Current projects are unchanged.', true);
        return;
      }
      if (!window.confirm('Replace the displayed FIXTURE projects with examples from this JSON? No real source files, tests or GitHub content will change.')) {
        announce('Fixture import cancelled. Current projects are unchanged.');
        return;
      }
      catalog = next;
      decisions.clear();
      selectedId = catalog.projects[0]?.id || null;
      selectedPath = catalog.projects[0]?.files[0]?.path || null;
      render();
      ui.importFile.value = '';
      ui.importButton.disabled = true;
      announce('Loaded ' + catalog.projects.length + ' local imported fixture projects. No production project imported.');
    }
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
