document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll('.dismiss-notice').forEach((button) => {
  button.addEventListener('click', () => button.closest('.notice').remove());
});

// Select asli tetap menjadi nilai yang dikirim; input hanya untuk mencari nama.
function enhanceOfficerSelect(select) {
  const fieldId = select.id;
  const choices = Array.from(select.options, (option) => ({
    value: option.value, label: option.textContent.trim(),
  }));
  const picker = document.createElement('div');
  picker.className = 'officer-picker';
  const input = document.createElement('input');
  input.id = fieldId;
  input.type = 'text';
  input.autocomplete = 'off';
  input.spellcheck = false;
  input.placeholder = 'Ketik nama petugas...';
  input.value = select.value ? choices.find((choice) => choice.value === select.value).label : '';
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false');
  const list = document.createElement('div');
  list.id = `${fieldId}-options`;
  list.className = 'officer-options';
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', 'Pilihan penanggung jawab');
  list.hidden = true;
  input.setAttribute('aria-controls', list.id);
  select.id = `${fieldId}-select`;
  select.hidden = true;
  select.before(picker);
  picker.append(input, select, list);
  let options = [];
  let active = -1;

  const close = () => {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  };
  const choose = (choice) => {
    select.value = choice.value;
    input.value = choice.value ? choice.label : '';
    input.setCustomValidity('');
    close();
    input.focus({ preventScroll: true });
  };
  const markActive = () => {
    options.forEach((button, index) => button.classList.toggle('is-active', index === active));
    if (active >= 0) {
      input.setAttribute('aria-activedescendant', options[active].id);
      options[active].scrollIntoView({ block: 'nearest' });
    }
  };
  const render = (keyword = '') => {
    const matches = choices.filter((choice) => choice.label.toLocaleLowerCase('id').includes(keyword.trim().toLocaleLowerCase('id')));
    list.replaceChildren();
    active = -1;
    input.removeAttribute('aria-activedescendant');
    options = matches.map((choice, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.tabIndex = -1;
      button.id = `${list.id}-${index}`;
      button.textContent = choice.label;
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(select.value === choice.value));
      button.addEventListener('pointerdown', (event) => event.preventDefault());
      button.addEventListener('click', () => choose(choice));
      list.append(button);
      return button;
    });
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.className = 'combobox-empty';
      empty.textContent = 'Tidak ada petugas yang cocok.';
      empty.setAttribute('role', 'status');
      list.append(empty);
    }
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };
  input.addEventListener('focus', () => render());
  input.addEventListener('click', () => { if (list.hidden) render(); });
  input.addEventListener('input', () => {
    select.value = '';
    input.setCustomValidity(input.value.trim() ? 'Pilih petugas dari daftar, atau kosongkan untuk Belum ditugaskan.' : '');
    render(input.value);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (list.hidden) render(input.value);
      if (!options.length) return;
      active = event.key === 'ArrowDown' ? (active + 1) % options.length : (active <= 0 ? options.length - 1 : active - 1);
      markActive();
    } else if (event.key === 'Enter' && !list.hidden && (active >= 0 || options.length === 1)) {
      event.preventDefault();
      options[active >= 0 ? active : 0].click();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      close();
    }
  });
  picker.addEventListener('focusout', (event) => {
    if (!picker.contains(event.relatedTarget)) close();
  });
}

function initializeForm(root) {
  root.querySelectorAll('[data-counter-for]').forEach((counter) => {
    if (counter.dataset.initialized) return;
    counter.dataset.initialized = 'true';
    const input = root.querySelector(`[id="${counter.dataset.counterFor}"]`);
    const update = () => { counter.textContent = `${input.value.length}/${input.maxLength}`; };
    input.addEventListener('input', update);
    update();
  });
  root.querySelectorAll('select[data-searchable-officer]').forEach((select) => {
    if (select.dataset.initialized) return;
    select.dataset.initialized = 'true';
    enhanceOfficerSelect(select);
  });
}

initializeForm(document);

// Form dan validasi tetap ditangani Flask; dialog hanya menyajikan form sebagai popup.
const modal = document.getElementById('form-modal');
const modalBody = modal.querySelector('.modal-body');
const modalTitle = modal.querySelector('#form-modal-title');
const closeModal = modal.querySelector('.modal-close');
let modalTrigger = null;
let loadController = null;

function extractForm(doc) {
  return doc.querySelector('[data-modal-content]')
    || doc.querySelector('template[data-officer-template]')?.content.querySelector('[data-modal-content]');
}

function showModalError(message) {
  modalBody.querySelector('[data-modal-error]')?.remove();
  const error = document.createElement('div');
  error.className = 'notice error';
  error.dataset.modalError = 'true';
  error.setAttribute('role', 'alert');
  error.textContent = message;
  modalBody.prepend(error);
}

function displayForm(content) {
  modalTitle.textContent = content.dataset.modalTitle;
  modalBody.replaceChildren(content.cloneNode(true));
  initializeForm(modalBody);
  const errorField = modalBody.querySelector('.field-error')?.closest('.field')?.querySelector('input, textarea, select');
  const focus = errorField || modalBody.querySelector('[autofocus], input:not([type="hidden"])');
  focus?.focus({ preventScroll: true });
  modalBody.scrollTop = 0;
}

document.addEventListener('click', async (event) => {
  const trigger = event.target.closest('[data-modal-link], [data-modal-template]');
  if (!trigger || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  loadController?.abort();
  loadController = null;
  modalTrigger = trigger;
  modalBody.textContent = 'Memuat form...';
  modalTitle.textContent = 'Memuat form...';
  modal.showModal();
  document.body.classList.add('modal-open');
  if (trigger.dataset.modalTemplate) {
    displayForm(document.getElementById(trigger.dataset.modalTemplate).content.querySelector('[data-modal-content]'));
    return;
  }
  const controller = new AbortController();
  loadController = controller;
  try {
    const response = await fetch(trigger.href, { signal: controller.signal });
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (!modal.open || loadController !== controller) return;
    const content = extractForm(doc);
    if (!response.ok || !content) {
      modalBody.replaceChildren();
      modalTitle.textContent = 'Form belum dapat dibuka';
      showModalError(doc.querySelector('.error-page p')?.textContent || 'Gagal memuat form. Tutup lalu coba kembali.');
      return;
    }
    displayForm(content);
  } catch (error) {
    if (error.name !== 'AbortError' && modal.open && loadController === controller) {
      modalBody.replaceChildren();
      modalTitle.textContent = 'Koneksi terputus';
      showModalError('Form belum dapat dimuat. Periksa koneksi lalu coba kembali.');
    }
  }
});

closeModal.addEventListener('click', () => modal.close());
// Sesuai interaksi yang diminta: hanya tombol X, bukan Escape atau klik backdrop.
modal.addEventListener('cancel', (event) => event.preventDefault());
modal.addEventListener('close', () => {
  loadController?.abort();
  loadController = null;
  document.body.classList.remove('modal-open');
  modalBody.replaceChildren();
  modalTrigger?.focus({ preventScroll: true });
});

modal.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  if (form.dataset.submitting) return;
  const payload = new FormData(form);
  const submit = form.querySelector('button[type="submit"]');
  form.dataset.submitting = 'true';
  submit.disabled = true;
  closeModal.disabled = true;
  form.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(form.action, { method: 'POST', body: payload });
    if (response.redirected && response.ok) {
      window.location.assign(response.url);
      return;
    }
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const content = extractForm(doc);
    if (response.status === 422 && content) {
      displayForm(content);
    } else {
      showModalError(doc.querySelector('.error-page p')?.textContent || 'Perubahan belum dapat disimpan. Periksa input dan coba kembali.');
    }
  } catch {
    showModalError('Koneksi terputus. Periksa koneksi dan daftar tugas sebelum mengirim ulang.');
  } finally {
    delete form.dataset.submitting;
    submit.disabled = false;
    closeModal.disabled = false;
    form.removeAttribute('aria-busy');
  }
});

const clockFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});
const dateFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Jakarta', day: '2-digit', month: '2-digit', year: 'numeric',
});
function updateHeaderClock() {
  const now = new Date();
  document.querySelector('[data-header-clock]').textContent = clockFormat.format(now);
  document.querySelector('[data-header-date]').textContent = dateFormat.format(now);
}
updateHeaderClock();
setInterval(updateHeaderClock, 1000);
