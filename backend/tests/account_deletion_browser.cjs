const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "public_web", "static", "account_deletion.js"), "utf8");

async function setup(page, options = {}) {
  const elements = {};
  function element(id) {
    if (!elements[id]) {
      elements[id] = {
        dataset: {}, hidden: false, disabled: false, checked: false, value: "",
        handlers: {}, textContent: "", addEventListener(type, fn) { this.handlers[type] = fn; },
        focus() {}, setAttribute() {}, querySelectorAll() { return []; }, replaceChildren() {},
      };
    }
    return elements[id];
  }
  element("texts").textContent = JSON.stringify(Object.fromEntries([
    "network", "del_storage", "del_unknown", "del_status_none", "del_cancelled", "error",
    "del_status_grace", "del_status_completed", "del_bad_credentials", "del_receipt_unavailable",
  ].map(key => [key, key])));
  const main = element("main");
  main.dataset = { page, api: "/api", googleClientId: options.google ? "client" : "" };
  let stored = options.receipt ? JSON.stringify(options.receipt) : null;
  const requests = [];
  let googleOptions;
  const window = {
    location: { hash: ["delete_confirm", "delete_cancel"].includes(page) ? "#token=" + "a".repeat(43) : "", pathname: "/", search: "" },
    crypto: { randomUUID: () => "uuid", getRandomValues: bytes => bytes.fill(1) },
    sessionStorage: {
      getItem() { if (options.storageBlocked) throw Error("blocked"); return stored; },
      setItem(_key, value) { if (options.storageBlocked) throw Error("blocked"); stored = value; },
      removeItem() { stored = null; },
    },
    setTimeout, clearTimeout,
    google: { accounts: { id: { initialize(value) { googleOptions = value; }, renderButton() {} } } },
  };
  const document = {
    documentElement: { lang: "en" },
    querySelector: () => main,
    getElementById: element,
    createElement() { return { remove() {} }; },
    head: { appendChild(script) { script.onload(); } },
  };
  const fetch = async (url, init) => {
    requests.push({ url, body: JSON.parse(init.body) });
    const result = await options.fetch(url, JSON.parse(init.body));
    if (result instanceof Error) throw result;
    return { status: result.status, json: async () => result.body };
  };
  vm.runInNewContext(source, {
    window, document, fetch, history: { replaceState() {} }, Intl, Uint8Array,
    AbortController, btoa: value => Buffer.from(value, "binary").toString("base64"),
  });
  async function flush() { for (let i = 0; i < 12; i++) await new Promise(resolve => setImmediate(resolve)); }
  async function trigger(id, type) {
    element(id).handlers[type]({ preventDefault() {} });
    await flush();
  }
  await flush();
  return { element, trigger, requests, receipt: () => JSON.parse(stored), google: () => googleOptions, flush };
}

(async () => {
  const blocked = await setup("delete_confirm", { storageBlocked: true, fetch: async () => { throw Error("unexpected"); } });
  await blocked.trigger("action-form", "submit");
  assert.equal(blocked.requests.length, 0);
  assert.equal(blocked.element("status").textContent, "del_storage");

  const retry = await setup("delete_confirm", { fetch: async () => new Error("timeout") });
  await retry.trigger("action-form", "submit");
  const receipt = retry.receipt();
  assert.equal(receipt.pending, true);
  assert.equal(retry.element("status").textContent, "del_unknown");
  await retry.trigger("action-form", "submit");
  assert.equal(retry.requests[0].body.request_id, retry.requests[1].body.request_id);
  assert.equal(retry.requests[0].body.status_secret, retry.requests[1].body.status_secret);
  assert.deepEqual(Object.keys(receipt).sort(), ["pending", "request_id", "status_secret"]);

  const status = await setup("delete_status", { receipt, fetch: async () => ({ status: 404, body: {} }) });
  assert.equal(status.requests[0].url, "/api/status");
  assert.equal(status.element("status").textContent, "del_unknown");
  const failure = await setup("delete_confirm", { fetch: async () => ({ status: 500, body: {} }) });
  await failure.trigger("action-form", "submit");
  assert.equal(failure.receipt().pending, true);
  assert.equal(failure.element("status").textContent, "del_unknown");

  const cancelled = await setup("delete_cancel", {
    fetch: async url => url.endsWith("/status")
      ? { status: 200, body: { deletion_id: "deletion-id" } }
      : new Error("timeout"),
  });
  await cancelled.trigger("action-form", "submit");
  assert.equal(cancelled.element("status").textContent, "del_unknown");
  await cancelled.trigger("action-form", "submit");
  assert.equal(cancelled.requests[1].body.request_id, cancelled.requests[3].body.request_id);

  const existing = await setup("delete_confirm", {
    fetch: async () => ({ status: 202, body: { deletion_id: "another-id", state: "completed" } }),
  });
  await existing.trigger("action-form", "submit");
  assert.equal(existing.receipt(), null);
  assert.match(existing.element("status").textContent, /del_receipt_unavailable/);

  const google = await setup("delete_start", {
    google: true,
    fetch: async url => url.endsWith("/google/challenge")
      ? { status: 200, body: { challenge_id: "challenge", nonce: "nonce" } }
      : { status: 200, body: { action_token: "proof" } },
  });
  await google.trigger("google-request", "click");
  assert.equal(google.google().nonce, "nonce");
  google.google().callback({ credential: "google-token" });
  await google.flush();
  assert.equal(google.requests[1].url, "/api/proof/google");
  assert.equal(google.requests[1].body.action, "request");
  assert.equal(google.element("credentials").hidden, true);
  assert.equal(google.element("action-form").hidden, false);

  const switched = await setup("delete_start", {
    google: true,
    fetch: async () => ({ status: 200, body: { challenge_id: "challenge", nonce: "nonce" } }),
  });
  await switched.trigger("google-request", "click");
  const oldCallback = switched.google().callback;
  await switched.trigger("google-cancel", "click");
  oldCallback({ credential: "old-token" });
  await switched.flush();
  assert.equal(switched.requests.length, 2);
  console.log("account deletion browser tests passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
