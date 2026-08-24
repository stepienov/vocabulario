document.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-href]");
  if (row && !event.target.closest("a, button, input")) {
    window.location = row.dataset.href;
  }
});
