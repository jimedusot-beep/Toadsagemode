/* Trusted App Studio flashcard template. No network, eval or markup injection. */
(() => {
  'use strict';
  const KEY = '{{STORAGE_KEY}}';
  const SCHEMA = 'toad-flashcards-v1';
  const MAX_CARDS = 120;
  const form = document.querySelector('#card-form');
  const front = document.querySelector('#front-input');
  const back = document.querySelector('#back-input');
  const save = document.querySelector('#save-card');
  const cancel = document.querySelector('#cancel-edit');
  const message = document.querySelector('#message');
  const list = document.querySelector('#card-list');
  const emptyList = document.querySelector('#empty-cards');
  const search = document.querySelector('#search-cards');
  const count = document.querySelector('#card-count');
  const progress = document.querySelector('#progress');
  const emptyStudy = document.querySelector('#empty-study');
  const controls = document.querySelector('#study-controls');
  const face = document.querySelector('#face-text');
  const faceLabel = document.querySelector('#face-label');
  const flip = document.querySelector('#flip-card');
  const position = document.querySelector('#position');
  const previous = document.querySelector('#previous-card');
  const next = document.querySelector('#next-card');
  const learned = document.querySelector('#learned-card');
  let cards = [];
  let current = 0;
  let showingBack = false;
  let editing = null;
  let storageWritable = true;
  let sequence = 0;

  function notice(value, error = false) {
    message.textContent = value;
    message.classList.toggle('error', error);
  }
  function validCard(item) {
    return item && typeof item === 'object' && !Array.isArray(item) &&
      typeof item.id === 'string' && /^[a-z0-9-]{1,70}$/.test(item.id) &&
      typeof item.front === 'string' && !!item.front.trim() && item.front.length <= 160 &&
      typeof item.back === 'string' && !!item.back.trim() && item.back.length <= 1200 &&
      typeof item.learned === 'boolean';
  }
  function restore() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw === null) return;
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.schema !== SCHEMA || !Array.isArray(parsed.cards) ||
          parsed.cards.length > MAX_CARDS || !parsed.cards.every(validCard)) {
        throw new Error('Unrecognized flashcard data');
      }
      const ids = new Set(parsed.cards.map(item => item.id));
      if (ids.size !== parsed.cards.length) throw new Error('Duplicate card IDs');
      cards = parsed.cards.map(({id, front, back, learned}) => ({id, front, back, learned}));
    } catch (_) {
      storageWritable = false;
      notice('Saved cards could not be read. They will not be overwritten; changes stay in this session.', true);
    }
  }
  function persist() {
    if (!storageWritable) return;
    try {
      localStorage.setItem(KEY, JSON.stringify({schema: SCHEMA, cards}));
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
    } while (cards.some(item => item.id === id));
    return id;
  }
  function resetEditor() {
    editing = null;
    form.reset();
    save.textContent = 'Add flashcard';
    cancel.hidden = true;
  }
  function showIndex(index) {
    if (!cards.length) return;
    current = (index + cards.length) % cards.length;
    showingBack = false;
    renderStudy();
  }
  function renderStudy() {
    const hasCards = cards.length > 0;
    controls.hidden = !hasCards;
    emptyStudy.hidden = hasCards;
    progress.textContent = cards.filter(card => card.learned).length + ' of ' + cards.length + ' learned';
    if (!hasCards) return;
    if (current >= cards.length) current = cards.length - 1;
    const card = cards[current];
    position.textContent = 'Card ' + (current + 1) + ' of ' + cards.length;
    face.textContent = showingBack ? card.back : card.front;
    faceLabel.textContent = showingBack ? 'ANSWER' : 'QUESTION';
    flip.setAttribute('aria-label', showingBack ? 'Flip card to see its question' : 'Flip card to see its answer');
    learned.setAttribute('aria-pressed', String(card.learned));
    learned.textContent = card.learned ? 'Mark not learned' : 'Mark learned';
  }
  function renderList() {
    list.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    const matches = cards.filter(card => (card.front + ' ' + card.back).toLocaleLowerCase().includes(query));
    for (const card of matches) {
      const item = document.createElement('li');
      item.className = 'card-row';
      const heading = document.createElement('h3');
      heading.textContent = card.front;
      const answer = document.createElement('p');
      answer.textContent = card.back;
      const status = document.createElement('p');
      status.className = 'card-status';
      status.textContent = card.learned ? 'Learned' : 'Still practicing';
      const actions = document.createElement('div');
      actions.className = 'card-actions';
      const study = document.createElement('button');
      study.type = 'button';
      study.textContent = 'Study';
      study.setAttribute('aria-label', 'Study: ' + card.front);
      study.addEventListener('click', () => {
        const index = cards.findIndex(candidate => candidate.id === card.id);
        if (index >= 0) {
          showIndex(index);
          flip.focus();
        }
      });
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.textContent = 'Edit';
      edit.setAttribute('aria-label', 'Edit: ' + card.front);
      edit.addEventListener('click', () => {
        editing = card.id;
        front.value = card.front;
        back.value = card.back;
        save.textContent = 'Update flashcard';
        cancel.hidden = false;
        front.focus();
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'Delete';
      remove.className = 'delete';
      remove.setAttribute('aria-label', 'Delete: ' + card.front);
      remove.addEventListener('click', () => {
        const index = cards.findIndex(candidate => candidate.id === card.id);
        if (index < 0) return;
        cards.splice(index, 1);
        if (editing === card.id) resetEditor();
        if (index < current) current -= 1;
        if (current >= cards.length) current = Math.max(0, cards.length - 1);
        showingBack = false;
        persist();
        render();
      });
      actions.append(study, edit, remove);
      item.append(heading, answer, status, actions);
      list.append(item);
    }
    count.textContent = cards.length + (cards.length === 1 ? ' card' : ' cards');
    emptyList.hidden = matches.length > 0;
    emptyList.textContent = cards.length ? 'No matching flashcards.' : 'No flashcards yet.';
  }
  function render() {
    renderStudy();
    renderList();
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const question = front.value.trim();
    const answer = back.value.trim();
    if (!question || question.length > 160 || !answer || answer.length > 1200) {
      notice('Enter a question (up to 160 characters) and an answer (up to 1200 characters).', true);
      return;
    }
    if (editing !== null) {
      const existing = cards.find(card => card.id === editing);
      if (!existing) {
        notice('This flashcard was removed; nothing was overwritten.', true);
        resetEditor();
        return;
      }
      existing.front = question;
      existing.back = answer;
    } else {
      if (cards.length >= MAX_CARDS) {
        notice('This deck holds 120 cards. Delete an old card first.', true);
        return;
      }
      cards.push({id: newId(), front: question, back: answer, learned: false});
    }
    resetEditor();
    persist();
    render();
    front.focus();
  });
  cancel.addEventListener('click', resetEditor);
  search.addEventListener('input', renderList);
  flip.addEventListener('click', () => {
    if (!cards.length) return;
    showingBack = !showingBack;
    renderStudy();
  });
  previous.addEventListener('click', () => showIndex(current - 1));
  next.addEventListener('click', () => showIndex(current + 1));
  learned.addEventListener('click', () => {
    if (!cards.length) return;
    cards[current].learned = !cards[current].learned;
    persist();
    render();
  });
  restore();
  render();
})();
