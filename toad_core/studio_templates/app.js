/* Trusted App Studio task-list template. No network, eval, or HTML injection. */
(() => {
  'use strict';
  const KEY = 'toad-sage-task-list-v1';
  const MAX_TASKS = 200;
  const form = document.querySelector('#task-form');
  const input = document.querySelector('#task-input');
  const list = document.querySelector('#task-list');
  const empty = document.querySelector('#empty');
  const count = document.querySelector('#count');
  const message = document.querySelector('#message');
  const clear = document.querySelector('#clear-done');
  const filters = Array.from(document.querySelectorAll('[data-filter]'));
  let tasks = [];
  let filter = 'all';
  let storageWritable = true;
  let counter = 0;

  function notice(text, error = false) {
    message.textContent = text;
    message.classList.toggle('error', error);
  }
  function validTask(item) {
    return item && typeof item === 'object' && !Array.isArray(item) &&
      typeof item.id === 'string' && /^[a-z0-9-]{1,70}$/.test(item.id) &&
      typeof item.title === 'string' && item.title.trim().length > 0 &&
      item.title.length <= 120 && typeof item.done === 'boolean';
  }
  function restore() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw === null) return;
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.schema !== 'toad-tasks-v1' || !Array.isArray(parsed.tasks) ||
          parsed.tasks.length > MAX_TASKS || !parsed.tasks.every(validTask)) {
        throw new Error('Unrecognized task backup');
      }
      const ids = new Set(parsed.tasks.map(item => item.id));
      if (ids.size !== parsed.tasks.length) throw new Error('Duplicate task IDs');
      tasks = parsed.tasks.map(({id, title, done}) => ({id, title, done}));
    } catch (_) {
      storageWritable = false;
      notice('Saved tasks could not be read. They will not be overwritten; new edits stay in this session.', true);
    }
  }
  function persist() {
    if (!storageWritable) return;
    try {
      localStorage.setItem(KEY, JSON.stringify({schema: 'toad-tasks-v1', tasks}));
      notice('Saved locally on this device.');
    } catch (_) {
      storageWritable = false;
      notice('Browser storage is unavailable or full. Changes are visible but not saved.', true);
    }
  }
  function newId() {
    let id;
    do {
      counter += 1;
      id = Date.now().toString(36) + '-' + counter.toString(36);
    } while (tasks.some(item => item.id === id));
    return id;
  }
  function render() {
    list.replaceChildren();
    const visible = tasks.filter(item => filter === 'all' ||
      (filter === 'active' && !item.done) || (filter === 'done' && item.done));
    for (const task of visible) {
      const li = document.createElement('li');
      li.className = 'task' + (task.done ? ' done' : '');
      li.dataset.taskId = task.id;
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = task.done;
      checkbox.setAttribute('aria-label', (task.done ? 'Mark active: ' : 'Mark completed: ') + task.title);
      checkbox.addEventListener('change', () => {
        task.done = checkbox.checked;
        persist();
        render();
      });
      const span = document.createElement('span');
      span.className = 'task-text';
      span.textContent = task.title;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'delete';
      button.textContent = 'Delete';
      button.setAttribute('aria-label', 'Delete: ' + task.title);
      button.addEventListener('click', () => {
        tasks = tasks.filter(item => item.id !== task.id);
        persist();
        render();
      });
      li.append(checkbox, span, button);
      list.append(li);
    }
    const remaining = tasks.filter(task => !task.done).length;
    count.textContent = remaining + (remaining === 1 ? ' remaining' : ' remaining');
    empty.hidden = visible.length > 0;
    if (!visible.length) empty.textContent = tasks.length ? 'Nothing in this filter.' : 'No tasks yet. Add one above.';
    clear.disabled = !tasks.some(item => item.done);
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const title = input.value.trim();
    if (!title || title.length > 120) {
      notice('Enter a task of up to 120 characters.', true);
      return;
    }
    if (tasks.length >= MAX_TASKS) {
      notice('This app holds up to 200 tasks. Complete or delete one first.', true);
      return;
    }
    tasks.push({id: newId(), title, done: false});
    input.value = '';
    persist();
    render();
    input.focus();
  });
  for (const button of filters) {
    button.addEventListener('click', () => {
      filter = button.dataset.filter;
      for (const other of filters) other.setAttribute('aria-pressed', String(other === button));
      render();
    });
  }
  clear.addEventListener('click', () => {
    tasks = tasks.filter(item => !item.done);
    persist();
    render();
  });
  restore();
  render();
})();
