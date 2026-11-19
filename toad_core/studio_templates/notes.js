/* Trusted App Studio notes implementation; text-only rendering, no network. */
(() => {
  'use strict';
  const KEY = '{{STORAGE_KEY}}';
  const MAX_NOTES = 100;
  const form = document.querySelector('#note-form');
  const titleInput = document.querySelector('#note-title');
  const bodyInput = document.querySelector('#note-body');
  const saveButton = document.querySelector('#save-note');
  const cancelButton = document.querySelector('#cancel-edit');
  const search = document.querySelector('#note-search');
  const list = document.querySelector('#notes-list');
  const empty = document.querySelector('#empty');
  const count = document.querySelector('#count');
  const message = document.querySelector('#message');
  let notes = [];
  let editing = null;
  let storageWritable = true;
  let sequence = 0;

  function notice(text, error = false) {
    message.textContent = text;
    message.classList.toggle('error', error);
  }
  function validNote(note) {
    return note && typeof note === 'object' && !Array.isArray(note) &&
      typeof note.id === 'string' && /^[a-z0-9-]{1,70}$/.test(note.id) &&
      typeof note.title === 'string' && note.title.trim().length > 0 &&
      note.title.length <= 100 && typeof note.body === 'string' &&
      note.body.trim().length > 0 && note.body.length <= 3000;
  }
  function restore() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw === null) return;
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.schema !== 'toad-notes-v1' || !Array.isArray(parsed.notes) ||
          parsed.notes.length > MAX_NOTES || !parsed.notes.every(validNote)) {
        throw new Error('Unrecognized notes backup');
      }
      const ids = new Set(parsed.notes.map(item => item.id));
      if (ids.size !== parsed.notes.length) throw new Error('Duplicate note IDs');
      notes = parsed.notes.map(({id, title, body}) => ({id, title, body}));
    } catch (_) {
      storageWritable = false;
      notice('Saved notes could not be read. They will not be overwritten; edits stay in this session.', true);
    }
  }
  function persist() {
    if (!storageWritable) return;
    try {
      localStorage.setItem(KEY, JSON.stringify({schema: 'toad-notes-v1', notes}));
      notice('Saved locally on this device.');
    } catch (_) {
      storageWritable = false;
      notice('Browser storage is unavailable or full. Changes are visible but not saved.', true);
    }
  }
  function newId() {
    let id;
    do {
      sequence += 1;
      id = Date.now().toString(36) + '-' + sequence.toString(36);
    } while (notes.some(note => note.id === id));
    return id;
  }
  function resetEditor() {
    editing = null;
    form.reset();
    saveButton.textContent = 'Save note';
    cancelButton.hidden = true;
  }
  function render() {
    list.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    const matches = notes.filter(note => (note.title + ' ' + note.body).toLocaleLowerCase().includes(query));
    for (const note of matches) {
      const li = document.createElement('li');
      li.className = 'note';
      li.dataset.noteId = note.id;
      const heading = document.createElement('h3');
      heading.textContent = note.title;
      const body = document.createElement('p');
      body.textContent = note.body;
      const actions = document.createElement('div');
      actions.className = 'note-actions';
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.textContent = 'Edit';
      edit.setAttribute('aria-label', 'Edit: ' + note.title);
      edit.addEventListener('click', () => {
        editing = note.id;
        titleInput.value = note.title;
        bodyInput.value = note.body;
        saveButton.textContent = 'Update note';
        cancelButton.hidden = false;
        titleInput.focus();
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'Delete';
      remove.className = 'delete';
      remove.setAttribute('aria-label', 'Delete: ' + note.title);
      remove.addEventListener('click', () => {
        notes = notes.filter(item => item.id !== note.id);
        if (editing === note.id) resetEditor();
        persist();
        render();
      });
      actions.append(edit, remove);
      li.append(heading, body, actions);
      list.append(li);
    }
    count.textContent = notes.length + (notes.length === 1 ? ' note' : ' notes');
    empty.hidden = matches.length > 0;
    empty.textContent = notes.length ? 'No matching notes.' : 'No notes yet. Write one above.';
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const title = titleInput.value.trim();
    const body = bodyInput.value.trim();
    if (!title || title.length > 100 || !body || body.length > 3000) {
      notice('Enter a title (up to 100 characters) and content (up to 3000 characters).', true);
      return;
    }
    if (editing !== null) {
      const existing = notes.find(note => note.id === editing);
      if (!existing) {
        notice('The note being edited no longer exists.', true);
        resetEditor();
        return;
      }
      existing.title = title;
      existing.body = body;
    } else {
      if (notes.length >= MAX_NOTES) {
        notice('This app holds up to 100 notes. Delete an old note first.', true);
        return;
      }
      notes.push({id: newId(), title, body});
    }
    resetEditor();
    persist();
    render();
    titleInput.focus();
  });
  cancelButton.addEventListener('click', resetEditor);
  search.addEventListener('input', render);
  restore();
  render();
})();
