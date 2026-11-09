document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll('.dismiss-notice').forEach((button) => {
  button.addEventListener('click', () => button.closest('.notice').remove());
});

document.querySelectorAll('[data-counter-for]').forEach((counter) => {
  const input = document.getElementById(counter.dataset.counterFor);
  const update = () => { counter.textContent = `${input.value.length}/${input.maxLength}`; };
  input.addEventListener('input', update);
  update();
});
