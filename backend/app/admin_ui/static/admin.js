document.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-href]");
  if (row && !event.target.closest("a, button, input")) {
    window.location = row.dataset.href;
  }
});

const menuBtn = document.querySelector(".menu-btn");
const overlay = document.querySelector(".nav-overlay");

function setNavOpen(open) {
  document.body.classList.toggle("nav-open", open);
  if (menuBtn) menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
}

menuBtn?.addEventListener("click", () => {
  setNavOpen(!document.body.classList.contains("nav-open"));
});
overlay?.addEventListener("click", () => setNavOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setNavOpen(false);
});
document.querySelectorAll(".sidebar .nav a").forEach((link) => {
  link.addEventListener("click", () => setNavOpen(false));
});
