(() => {
  "use strict";

  const main = document.querySelector("main[data-page]");
  const texts = JSON.parse(document.getElementById("texts").textContent);
  const page = main.dataset.page;
  const API = main.dataset.api;
  const form = document.getElementById("action-form");
  const credentials = document.getElementById("credentials");
  const statusBox = document.getElementById("status");
  const intro = document.getElementById("intro");
  const submit = document.getElementById("submit");
  const acknowledge = document.getElementById("acknowledge");
  const TIMEOUT_MS = 15000;
  const RECEIPT_KEY = "vocabulario.account-deletion";
  const dates = new Intl.DateTimeFormat(document.documentElement.lang, {
    dateStyle: "long",
    timeStyle: "short",
  });

  // Mail tokens travel in the fragment so they never reach server logs; drop them from history.
  const match = /^#token=([A-Za-z0-9_-]{43})$/.exec(window.location.hash);
  const fragmentToken = match ? match[1] : null;
  if (window.location.hash) {
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }

  let proofToken = null;
  let googleScript = null;
  let googleGeneration = 0;
  const cancelRequestId = newUuid();

  function newUuid() {
    return window.crypto.randomUUID();
  }

  function randomSecret() {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    return btoa(String.fromCharCode(...bytes))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  }

  // The receipt only reads the status; it never allows cancelling or deleting.
  function readReceipt() {
    try {
      return JSON.parse(window.sessionStorage.getItem(RECEIPT_KEY));
    } catch (_error) {
      throw new Error("storage_unavailable");
    }
  }

  function writeReceipt(receipt) {
    try {
      window.sessionStorage.setItem(RECEIPT_KEY, JSON.stringify(receipt));
      if (window.sessionStorage.getItem(RECEIPT_KEY) !== JSON.stringify(receipt)) {
        throw new Error("storage_unavailable");
      }
    } catch (_error) {
      throw new Error("storage_unavailable");
    }
  }

  function clearReceipt() {
    try {
      window.sessionStorage.removeItem(RECEIPT_KEY);
    } catch (_error) {
      /* nothing to clear */
    }
  }

  // Stored before the request leaves, so a lost answer can be retried with the same ids.
  function receiptForRequest() {
    const previous = readReceipt();
    if (previous && previous.pending) {
      writeReceipt(previous);
      return previous;
    }
    const receipt = { request_id: newUuid(), status_secret: randomSecret(), pending: true };
    writeReceipt(receipt);
    return receipt;
  }

  function showStatus(text, kind) {
    statusBox.textContent = text;
    statusBox.className = "status " + kind;
    statusBox.hidden = false;
    statusBox.focus();
  }

  function say(key, kind) {
    showStatus(texts[key], kind);
  }

  function finish(text, kind) {
    form.hidden = true;
    if (credentials) credentials.hidden = true;
    intro.hidden = kind === "success";
    showStatus(text, kind);
  }

  function busy(isBusy) {
    main.setAttribute("aria-busy", String(isBusy));
    main.querySelectorAll("button").forEach((button) => {
      if (isBusy) {
        button.dataset.wasDisabled = String(button.disabled);
        button.disabled = true;
      } else if (button.dataset.wasDisabled !== undefined) {
        button.disabled = button.dataset.wasDisabled === "true";
        delete button.dataset.wasDisabled;
      }
    });
  }

  function describe(view) {
    if (view.state === "grace") {
      return texts.del_status_grace
        .replace("%CANCEL%", dates.format(new Date(view.cancel_until)))
        .replace("%PURGE%", dates.format(new Date(view.purge_due_at)));
    }
    return texts["del_status_" + view.state] || texts.error;
  }

  function errorKey(status, body, signingIn) {
    const code = body && body.detail && typeof body.detail === "object" ? body.detail.code : null;
    if (code === "invalid_credentials") return "del_bad_credentials";
    if (code === "account_deletion_unavailable") return "del_unavailable";
    if (code === "deletion_irreversible") return "del_irreversible";
    if (code === "no_pending_deletion") return "del_no_pending";
    if (code === "deletion_not_found") return "del_status_none";
    if (status === 410) return "expired";
    if (status === 429) return "rate_limited";
    if (status === 422 && signingIn) return "del_bad_credentials";
    if (status === 400 || status === 403 || status === 422) return "invalid";
    return "error";
  }

  async function post(path, payload) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(API + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      return { status: response.status, body };
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function guarded(work) {
    busy(true);
    try {
      await work();
    } catch (error) {
      say(error.message === "storage_unavailable" ? "del_storage" : "network", "error");
    } finally {
      busy(false);
    }
  }

  async function requestDeletion(token) {
    const receipt = receiptForRequest();
    let response;
    try {
      response = await post("/request", {
        request_id: receipt.request_id,
        action_token: token,
        status_secret: receipt.status_secret,
        confirmation_version: "delete-account-v1",
      });
    } catch (_error) {
      say("del_unknown", "error");
      return;
    }
    const { status, body } = response;
    if (status === 202) {
      if (body.deletion_id !== receipt.request_id) {
        clearReceipt();
        finish(describe(body) + " " + texts.del_receipt_unavailable, "info");
        return;
      }
      writeReceipt({ ...receipt, pending: false });
      finish(describe(body), "success");
      return;
    }
    if (status >= 500 || status === 408) {
      say("del_unknown", "error");
      return;
    }
    proofToken = null;
    if (credentials) {
      form.hidden = true;
      credentials.hidden = false;
    }
    say(errorKey(status, body, false), "error");
  }

  async function cancelDeletion(token, knownDeletionId) {
    let deletionId = knownDeletionId;
    if (!deletionId) {
      const found = await post("/status", { action_token: token });
      if (found.status !== 200) {
        say(errorKey(found.status, found.body, false), "error");
        return;
      }
      deletionId = found.body.deletion_id;
    }
    let response;
    try {
      response = await post("/cancel", {
        deletion_id: deletionId,
        request_id: cancelRequestId,
        action_token: token,
      });
    } catch (_error) {
      say("del_unknown", "error");
      return;
    }
    const { status, body } = response;
    if (status === 200) {
      clearReceipt();
      finish(texts.del_cancelled, "success");
      return;
    }
    say(status >= 500 || status === 408 ? "del_unknown" : errorKey(status, body, false), "error");
  }

  async function refreshStatus() {
    const receipt = readReceipt();
    if (!receipt) {
      finish(texts.del_status_none, "error");
      return;
    }
    const { status, body } = await post("/status", {
      request_id: receipt.request_id,
      status_secret: receipt.status_secret,
    });
    if (status === 200) {
      showStatus(describe(body), body.state === "grace" ? "success" : "info");
      return;
    }
    say(status === 404 && receipt.pending ? "del_unknown" : errorKey(status, body, false), "error");
  }

  function credentialValues() {
    const email = document.getElementById("email");
    const password = document.getElementById("password");
    return { email: email.value.trim(), password: password.value, field: password };
  }

  async function withPassword(action) {
    googleGeneration += 1;
    const { email, password, field } = credentialValues();
    if (!email || !password) {
      say("del_bad_credentials", "error");
      return;
    }
    const { status, body } = await post("/proof/password", { email, password, action });
    field.value = "";
    if (status !== 200) {
      say(errorKey(status, body, true), "error");
      return;
    }
    await useProof(body, action);
  }

  async function useProof(body, action) {
    if (action === "cancel") {
      await cancelDeletion(body.action_token, body.deletion_id);
      return;
    }
    proofToken = body.action_token;
    credentials.hidden = true;
    statusBox.hidden = true;
    form.hidden = false;
    acknowledge.focus();
  }

  function loadGoogle() {
    if (!googleScript) {
      googleScript = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.onload = resolve;
        script.onerror = () => {
          googleScript = null;
          script.remove();
          reject(new Error("google_unavailable"));
        };
        document.head.appendChild(script);
      });
    }
    return googleScript;
  }

  async function startGoogle(action) {
    const generation = ++googleGeneration;
    const challenge = await post("/google/challenge", { action });
    if (challenge.status !== 200) {
      say(errorKey(challenge.status, challenge.body, false), "error");
      return;
    }
    await loadGoogle();
    const container = document.getElementById("google-button");
    container.replaceChildren();
    window.google.accounts.id.initialize({
      client_id: main.dataset.googleClientId,
      nonce: challenge.body.nonce,
      auto_select: false,
      callback: (result) => guarded(async () => {
        if (generation !== googleGeneration) return;
        const proof = await post("/proof/google", {
          action,
          challenge_id: challenge.body.challenge_id,
          id_token: result.credential,
        });
        if (proof.status !== 200) {
          say(errorKey(proof.status, proof.body, false), "error");
          return;
        }
        container.replaceChildren();
        await useProof(proof.body, action);
      }),
    });
    window.google.accounts.id.renderButton(container, { type: "standard", theme: "outline", size: "large" });
  }

  async function sendLink(action) {
    googleGeneration += 1;
    const { email } = credentialValues();
    if (!email) {
      say("del_bad_credentials", "error");
      return;
    }
    const { status, body } = await post("/email/request", { email, action });
    say(status === 202 ? "del_link_sent" : errorKey(status, body, true), status === 202 ? "info" : "error");
  }

  if (page === "delete_start") {
    credentials.addEventListener("submit", (event) => {
      event.preventDefault();
      guarded(() => withPassword("request"));
    });
    document
      .getElementById("proof-cancel")
      .addEventListener("click", () => guarded(() => withPassword("cancel")));
    document
      .getElementById("link-request")
      .addEventListener("click", () => guarded(() => sendLink("request")));
    document
      .getElementById("link-cancel")
      .addEventListener("click", () => guarded(() => sendLink("cancel")));
    if (main.dataset.googleClientId) {
      document.getElementById("google-request").addEventListener("click", () => guarded(() => startGoogle("request")));
      document.getElementById("google-cancel").addEventListener("click", () => guarded(() => startGoogle("cancel")));
    }
  }

  if (acknowledge) {
    acknowledge.addEventListener("change", () => {
      submit.disabled = !acknowledge.checked;
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    statusBox.hidden = true;
    if (page === "delete_status") {
      guarded(refreshStatus);
    } else if (page === "delete_cancel") {
      guarded(() => cancelDeletion(fragmentToken, null));
    } else {
      guarded(() => requestDeletion(proofToken || fragmentToken));
    }
  });

  if (page === "delete_start") {
    credentials.hidden = false;
    document.getElementById("email").focus();
  } else if (page === "delete_status") {
    form.hidden = false;
    guarded(refreshStatus);
  } else if (!fragmentToken) {
    finish(texts.missing_token, "error");
  } else {
    form.hidden = false;
    (acknowledge || submit).focus();
  }
})();
