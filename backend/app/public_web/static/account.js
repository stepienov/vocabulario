(() => {
  "use strict";

  const main = document.querySelector("main[data-page]");
  const texts = JSON.parse(document.getElementById("texts").textContent);
  const form = document.getElementById("action-form");
  const statusBox = document.getElementById("status");
  const intro = document.getElementById("intro");
  const submit = document.getElementById("submit");
  const page = main.dataset.page;
  const minChars = Number(main.dataset.min);
  const maxChars = Number(main.dataset.max);
  const TIMEOUT_MS = 15000;
  const PASSWORD_CODES = {
    password_too_short: "too_short",
    password_too_long: "too_long",
    password_invalid_unicode: "invalid_unicode",
  };
  const BUTTONS = { reset: "reset_button", change: "change_button", verify: "verify_button" };
  const DONE = { reset: "reset_done", change: "change_done", verify: "verify_done" };
  const TERMINAL = { 400: "invalid", 409: "used", 410: "expired" };

  // The token travels in the fragment so it never reaches server logs; drop it from history.
  const match = /^#token=([A-Za-z0-9_-]{1,512})$/.exec(window.location.hash);
  const token = match ? match[1] : null;
  if (window.location.hash) {
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }

  function showStatus(key, kind) {
    statusBox.textContent = texts[key];
    statusBox.className = "status " + kind;
    statusBox.hidden = false;
    statusBox.focus();
  }

  function finish(key, kind) {
    form.hidden = true;
    intro.hidden = kind === "success";
    form.reset();
    showStatus(key, kind);
  }

  function busy(isBusy) {
    submit.disabled = isBusy;
    submit.textContent = isBusy ? texts.working : texts[BUTTONS[page]];
    main.setAttribute("aria-busy", String(isBusy));
  }

  if (!token) {
    finish("missing_token", "error");
    return;
  }

  let newPassword = null;
  let confirmPassword = null;
  let fieldError = null;
  if (page === "reset") {
    newPassword = document.getElementById("new-password");
    confirmPassword = document.getElementById("confirm-password");
    fieldError = document.getElementById("password-error");
    document.getElementById("show-password").addEventListener("change", (event) => {
      const type = event.target.checked ? "text" : "password";
      newPassword.type = type;
      confirmPassword.type = type;
    });
  }

  function showFieldError(key) {
    fieldError.textContent = texts[key];
    fieldError.hidden = false;
    newPassword.setAttribute("aria-invalid", "true");
    newPassword.focus();
  }

  function clearFieldError() {
    if (!fieldError) return;
    fieldError.hidden = true;
    fieldError.textContent = "";
    newPassword.removeAttribute("aria-invalid");
  }

  function localPasswordError() {
    // Count code points like the server does, not UTF-16 units.
    const length = Array.from(newPassword.value).length;
    if (length < minChars) return "too_short";
    if (length > maxChars) return "too_long";
    if (newPassword.value !== confirmPassword.value) return "mismatch";
    return null;
  }

  function handle(status, body) {
    if (status === 200) {
      finish(DONE[page], "success");
      return;
    }
    const code = body && body.detail && typeof body.detail === "object" ? body.detail.code : null;
    if (code === "email_unavailable") {
      finish("change_unavailable", "error");
      return;
    }
    if (TERMINAL[status]) {
      finish(TERMINAL[status], "error");
      return;
    }
    if (status === 422 && page === "reset" && PASSWORD_CODES[code]) {
      showFieldError(PASSWORD_CODES[code]);
      return;
    }
    if (status === 422) {
      finish("invalid", "error");
      return;
    }
    showStatus(status === 429 ? "rate_limited" : "error", "error");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    statusBox.hidden = true;
    const payload = { token };
    if (page === "reset") {
      clearFieldError();
      const problem = localPasswordError();
      if (problem) {
        showFieldError(problem);
        return;
      }
      payload.new_password = newPassword.value;
    }
    busy(true);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(main.dataset.api, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      handle(response.status, body);
    } catch (_error) {
      showStatus("network", "error");
    } finally {
      window.clearTimeout(timer);
      busy(false);
    }
  });

  form.hidden = false;
  (newPassword || submit).focus();
})();
