"use strict";
// The built-in browser (#/browser) and the device preview (#/preview), and their side panels (Settings › Features).
// Pages from dev servers on this Mac come through the hub's preview listener, on its own port and so its own origin:
// they can never reach the hub's API. External https pages are framed as they are, when they allow it.
// Everything sits inside one function, so no name here can collide with app.js; app.js reaches it through window.hubBrowser.
(() => {
  Object.assign(UI, {
    back: '<path d="m10 3-5 5 5 5"/>',
    forward: '<path d="m6 3 5 5-5 5"/>',
    reload: '<path d="M13 8a5 5 0 1 1-1.6-3.7"/><path d="M13 2.5v3h-3"/>',
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 3.5v-1a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1"/>',
    globe: '<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 1.7 2.6 3.7 2.6 6S9.8 12.3 8 14C6.2 12.3 5.4 10.3 5.4 8S6.2 3.7 8 2Z"/>',
    devices: '<rect x="1.5" y="3" width="9" height="7" rx="1"/><path d="M4 12.5h4"/><rect x="11" y="5.5" width="3.5" height="7.5" rx=".8"/>',
    rotate: '<rect x="1.5" y="5" width="6.5" height="9.5" rx="1"/><path d="M9 2.5h1a3.5 3.5 0 0 1 3.5 3.5v3"/><path d="m11.5 7.5 2 2 2-2"/>',
    fit: '<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>',
  });

  // ── the preview's origin: the first that answers, its pass set ──
  const B = { base: null, info: null, probing: null, port: null, frames: new Set() };
  const hello = (base, ticket) => new Promise((done) => {
    const probe = h("iframe", { class: "bro-hello", title: "", "aria-hidden": "true", tabIndex: -1, src: `${base}/__hub/hello?t=${encodeURIComponent(ticket)}` });
    const finish = (ok) => { clearTimeout(timer); removeEventListener("message", heard); probe.remove(); done(ok); };
    const heard = (e) => { if (e.origin === base && e.source === probe.contentWindow && e.data && e.data.hubHello === 1) finish(true); };
    const timer = setTimeout(() => finish(false), 4000);
    addEventListener("message", heard);
    document.body.append(probe);
  });
  const base = (fresh) => {
    if (B.base && !fresh) return Promise.resolve(B.base);
    if (B.probing) return B.probing;
    B.probing = (async () => {
      B.info = await api("/api/browser/info");
      for (const one of B.info.bases) if (await hello(one, B.info.ticket)) return (B.base = one);
      return (B.base = null);
    })().finally(() => { B.probing = null; });
    return B.probing;
  };
  addEventListener("message", (e) => {
    if (!B.base || e.origin !== B.base || !e.data || e.data.hubFrame !== "loc") return;
    for (const f of B.frames) if (f.iframe.contentWindow === e.source) f.heard(e.data);
  });
  // One port at a time per browser: the listener's port cookie is shared by every frame. Frames on another are told.
  const nowOn = (port, except) => { B.port = port; for (const f of B.frames) if (f !== except && f.port !== port && f.stale) f.stale(port); };

  // ── addresses ──
  const LOOP = /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|::1)$/i;
  const readAddress = (raw) => {
    let text = String(raw || "").trim();
    if (!text) return null;
    if (/^:?\d{2,5}(\/.*)?$/.test(text)) text = `http://localhost${text.startsWith(":") ? "" : ":"}${text}`;
    else if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) text = `${/^(localhost|127\.|0\.0\.0\.0|\[::1\])/i.test(text) ? "http" : "https"}://${text}`;
    let u;
    try { u = new URL(text); } catch (e) { return null; }
    if (!/^https?:$/.test(u.protocol)) return null;
    if (LOOP.test(u.hostname)) {
      const port = Number(u.port || (u.protocol === "https:" ? 443 : 80)), path = `${u.pathname}${u.search}${u.hash}` || "/";
      return { local: true, port, path, href: `http://localhost:${port}${path}`, shown: `localhost:${port}${path === "/" ? "" : path}` };
    }
    return { local: false, href: u.href, host: u.host, secure: u.protocol === "https:", shown: u.href.replace(/^https:\/\//, "") };
  };
  const goUrl = async (where, t) => {
    const { ticket } = await api(`/api/browser/ticket?port=${t.port}`);
    return `${where}/__hub/go?port=${t.port}&path=${encodeURIComponent(t.path)}&t=${encodeURIComponent(ticket)}`;
  };
  const LAST = "hub.browser.last";
  const lastUrl = (sid) => { try { return (JSON.parse(localStorage.getItem(LAST) || "{}"))[sid || "_"] || ""; } catch (e) { return ""; } };
  const keepUrl = (sid, href) => {
    try { const all = JSON.parse(localStorage.getItem(LAST) || "{}"); all[sid || "_"] = href; localStorage.setItem(LAST, JSON.stringify(all)); } catch (e) { /* private mode keeps nothing */ }
  };
  const routeFor = (kind, sid, href) => `#/${kind}/${sid || "-"}${href ? `/${encodeURIComponent(href)}` : ""}`;

  // ── suggestions: what the session printed, its own ports, and every web server of yours on this Mac ──
  const suggestions = async (sid) => {
    const got = await api(`/api/browser/suggest?sid=${encodeURIComponent(sid || "")}`).catch(() => ({ printed: [], listening: [] }));
    const s = sid ? session(sid) : null, rows = [], seen = new Set();
    const add = (row) => { if (seen.has(row.href)) return; seen.add(row.href); rows.push(row); };
    (got.printed || []).forEach((p) => add({ href: p.url, port: p.port, group: "session", label: `localhost:${p.port}${p.path === "/" ? "" : p.path}`, note: "printed in this session" }));
    ((s && s.ports) || []).forEach((port) => add({ href: `http://localhost:${port}/`, port, group: "session", label: `localhost:${port}`, note: "this session listens here" }));
    const known = new Set(rows.map((r) => r.port));
    (got.listening || []).forEach((l) => { if (!known.has(l.port)) add({ href: `http://localhost:${l.port}/`, port: l.port, group: "mac", label: `localhost:${l.port}`, note: [l.title, l.name].filter(Boolean).join(" · ") }); });
    return rows;
  };
  const suggestList = (rows, pick, sid) => {
    const mine = rows.filter((r) => r.group === "session"), mac = rows.filter((r) => r.group === "mac");
    const row = (r) => h("button", { type: "button", class: "bro-pick", "data-key": `pick:${r.href}`, onclick: () => pick(r.href) },
      h("span", { class: "bro-pick-url mono", textContent: r.label }), r.note ? h("span", { class: "bro-pick-note", textContent: r.note }) : null, uiIcon("chev"));
    return [
      sid ? h("h3", { class: "bro-sub", textContent: "From this session" }) : null,
      sid ? (mine.length ? h("div", { class: "bro-picks" }, mine.map(row)) : h("p", { class: "bro-none", textContent: "It hasn't printed a local address yet." })) : null,
      h("h3", { class: "bro-sub", textContent: "Running on this Mac" }),
      mac.length || (!sid && mine.length) ? h("div", { class: "bro-picks" }, (sid ? mac : rows).map(row)) : h("p", { class: "bro-none", textContent: "No web server of yours is listening right now." }),
    ];
  };

  // ── what fills the stage when there is no page to frame ──
  const card = (title, text, ...more) => h("div", { class: "bro-card", role: "status" }, h("div", { class: "bro-card-in" }, h("h2", { class: "bro-card-title", textContent: title }), text ? h("p", { textContent: text }) : null, more));
  const unreachable = () => {
    const cmd = (B.info && B.info.command) || "";
    return card("This device can't reach the preview yet", "Pages from your dev servers come through a port of their own, which Tailscale has to serve once. Run this on the Mac:",
      h("div", { class: "bro-cmd" }, h("code", { textContent: cmd }), copyButton(cmd)),
      h("div", { class: "bro-acts" }, h("button", { type: "button", class: "btn", "data-key": "bro-again", textContent: "Try again", onclick: () => { B.base = null; B.again && B.again(); } }),
        h("a", { class: "retry", href: "#/settings/health", textContent: "Settings › Health" })));
  };

  // ── one address bar, shared by the browser and the preview ──
  const addressBar = ({ sid, onOpen, buttons, compact }) => {
    const input = h("input", { type: "text", class: "bro-url", "aria-label": "Address", placeholder: "localhost:5173, or a web address", spellcheck: false, autocomplete: "off",
      autocapitalize: "off", enterkeyhint: "go", inputMode: "url", "data-key": "bro-url" });
    const lock = h("span", { class: "bro-where", "aria-hidden": "true" });
    const pop = h("div", { class: "bro-pop", hidden: true, role: "listbox", "aria-label": "Suggestions" });
    let rows = [], chosen = -1, fetched = 0;
    const paintPop = () => {
      fill(pop, rows.map((r, i) => h("div", { class: `bro-opt ${i === chosen ? "on" : ""}`, role: "option", id: `bro-opt-${i}`, "aria-selected": i === chosen ? "true" : "false",
        onpointerdown: (e) => e.preventDefault(), onclick: () => { hidePop(); onOpen(r.href); } },
        h("span", { class: "mono", textContent: r.label }), h("span", { class: "bro-pick-note", textContent: r.note }))));
      pop.hidden = !rows.length;
      input.setAttribute("aria-expanded", rows.length ? "true" : "false");
      if (chosen >= 0) input.setAttribute("aria-activedescendant", `bro-opt-${chosen}`); else input.removeAttribute("aria-activedescendant");
    };
    const hidePop = () => { pop.hidden = true; chosen = -1; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); };
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list"); input.setAttribute("aria-expanded", "false");
    input.addEventListener("focus", async () => {
      input.select();
      if (Date.now() - fetched > 4000) { fetched = Date.now(); rows = await suggestions(sid); }
      if (document.activeElement === input) { chosen = -1; paintPop(); }
    });
    input.addEventListener("blur", () => setTimeout(hidePop, 120));
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const n = rows.length;
        if (!n) return;
        e.preventDefault();
        chosen = e.key === "ArrowDown" ? (chosen + 1 >= n ? -1 : chosen + 1) : (chosen <= -1 ? n - 1 : chosen - 1);
        paintPop();
      }
      else if (e.key === "Escape") { e.stopPropagation(); if (!pop.hidden) hidePop(); else input.blur(); }
      else if (e.key === "Enter" && chosen >= 0) { e.preventDefault(); const r = rows[chosen]; hidePop(); onOpen(r.href); }
    });
    input.addEventListener("input", () => { if (chosen >= 0) { chosen = -1; paintPop(); } });
    const form = h("form", { class: `bro-bar ${compact ? "compact" : ""}`, role: "search", "aria-label": "Address", onsubmit: (e) => { e.preventDefault(); hidePop(); onOpen(input.value); input.blur(); } },
      buttons.before, h("div", { class: "bro-field" }, lock, input, pop), buttons.after);
    const show = (t) => {
      if (document.activeElement !== input) input.value = t ? t.shown : "";
      lock.className = `bro-where ${t ? (t.local ? "local" : t.secure ? "secure" : "plain") : ""}`;
      lock.title = t ? (t.local ? "A server on this Mac, through the hub" : t.secure ? "A web page" : "Not secure") : "";
    };
    return { form, input, show };
  };
  const iconButton = (icon, title, onclick, key) => h("button", { type: "button", class: "icon bro-btn", title, "aria-label": title, "data-key": key, onclick }, uiIcon(icon));
  const SANDBOX = "allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads";

  // A new tab is opened at once, inside the press (a browser blocks one opened later), and sent on when the ticket comes.
  const openTab = async (t) => {
    if (!t) return;
    if (!t.local) { window.open(t.href, "_blank", "noopener,noreferrer"); return; }
    const tab = window.open("about:blank", "_blank");
    if (tab) tab.opener = null;
    try {
      const where = await base();
      if (!where) { if (tab) tab.close(); toast("This device can't reach the preview yet. Settings › Health says how.", true); return; }
      const url = await goUrl(where, t);
      if (tab) tab.location.href = url; else window.open(url, "_blank", "noopener");
    } catch (error) { if (tab) tab.close(); explain(error); }
  };
  const copyLink = guard(async (t) => {
    if (!t) return;
    const where = t.local ? await base() : "";
    await navigator.clipboard.writeText(t.local ? (where ? `${where}/p/${t.port}${t.path}` : t.href) : t.href);
    toast(t.local ? "Link copied. It opens on any of your devices." : "Link copied");
  });

  // ── the browser ──
  const makeBrowser = ({ sid = "", url = "", compact = false, onUrl = null } = {}) => {
    const st = { t: null, frame: null, timer: null, alive: true, helper: false };
    const back = iconButton("back", "Back", () => tell("back"), "bro-back");
    const forward = iconButton("forward", "Forward", () => tell("forward"), "bro-forward");
    const reload = iconButton("reload", "Reload", () => (st.helper ? tell("reload") : open(st.t ? st.t.href : bar.input.value)), "bro-reload");
    const copy = iconButton("copy", "Copy link", () => copyLink(st.t), "bro-copy");
    const tab = iconButton("external", "Open in a new tab", () => openTab(st.t), "bro-tab");
    const devices = compact && feature("preview") ? h("a", { class: "icon bro-btn", title: "Device preview", "aria-label": "Device preview", "data-key": "bro-devices", href: routeFor("preview", sid, ""),
      onclick: (e) => { e.currentTarget.href = routeFor("preview", sid, st.t ? st.t.href : ""); } }, uiIcon("devices")) : null;
    const bar = addressBar({ sid, compact, onOpen: (text) => open(text), buttons: { before: [back, forward, reload], after: [copy, tab, devices] } });
    const loading = h("div", { class: "bro-loading", hidden: true });
    const note = h("div", { class: "bro-note", hidden: true });
    const stage = h("div", { class: "bro-stage" });
    const el = h("div", { class: `bro ${compact ? "compact" : ""}` }, bar.form, note, h("div", { class: "bro-view" }, loading, stage));
    const tell = (ask) => { if (st.frame && st.frame.iframe.contentWindow && B.base) st.frame.iframe.contentWindow.postMessage({ hubFrame: ask }, B.base); };
    const canNav = (on) => { [back, forward].forEach((b) => { b.disabled = !on; }); };
    const stop = () => { clearTimeout(st.timer); st.timer = null; if (st.frame) { B.frames.delete(st.frame); st.frame = null; } st.helper = false; loading.hidden = true; };
    const say = (node) => { stop(); note.hidden = true; canNav(false); fill(stage, node); };
    const remember = (t) => { keepUrl(sid, t.href); if (onUrl) onUrl(t.href); };
    const canShare = (on) => { copy.disabled = !on; tab.disabled = !on; };
    canShare(false);
    const showPicks = async () => {
      bar.show(null);
      say(card("Open a page", compact ? "" : "Pick a server, or type an address above.", h("div", { class: "bro-list", textContent: "Looking…" })));
      const rows = await suggestions(sid);
      if (!st.alive || st.t) return;
      const list = stage.querySelector(".bro-list");
      if (list) fill(list, suggestList(rows, (href) => open(href), sid));
    };
    const frameIt = (src, t) => {
      stop();
      const iframe = h("iframe", { class: "bro-frame", src, title: t.shown, sandbox: SANDBOX, allow: "clipboard-write; fullscreen", referrerPolicy: "no-referrer" });
      const f = { iframe, port: t.local ? t.port : null,
        heard: (d) => {
          st.helper = true; canNav(true);
          let u; try { u = new URL(d.href); } catch (e) { return; }
          if (u.origin !== B.base || u.pathname.startsWith("/__hub/")) return;
          const now = readAddress(`http://localhost:${f.port}${u.pathname}${u.search}${u.hash}`);
          if (!now) return;
          st.t = now; bar.show(now); remember(now);
          iframe.title = d.title ? String(d.title).slice(0, 200) : now.shown;
        },
        stale: (port) => {
          fill(note, h("span", { textContent: `The preview moved to :${port} for another page. Reload to come back to :${f.port}.` }),
            h("button", { type: "button", class: "retry", textContent: "Reload", onclick: () => open(st.t.href) }));
          note.hidden = false;
        } };
      if (t.local) { B.frames.add(f); nowOn(t.port, f); }
      st.frame = f;
      loading.hidden = false;
      iframe.addEventListener("load", () => { loading.hidden = true; });
      canNav(false);
      fill(stage, iframe);
    };
    const waitFor = (t) => {
      say(card(`Nothing is running on :${t.port}`, "Start the dev server, and the page opens here by itself.",
        h("div", { class: "bro-acts" }, h("button", { type: "button", class: "btn", "data-key": "bro-retry", textContent: "Try now", onclick: () => open(t.href) }), h("span", { class: "faint bro-wait", textContent: "Checking every few seconds" }))));
      st.timer = setTimeout(async function again() {
        if (!st.alive || st.t !== t) return;
        const up = await api(`/api/browser/probe?port=${t.port}`).catch(() => ({ up: false }));
        if (!st.alive || st.t !== t) return;
        if (up.up) open(t.href); else st.timer = setTimeout(again, 3000);
      }, 3000);
    };
    const open = guard(async (text) => {
      const t = readAddress(text);
      if (!t) { bar.show(st.t); toast("That isn't an address the browser can open.", true); return; }
      st.t = t; bar.show(t); remember(t); note.hidden = true; canShare(true);
      if (!t.local) {
        if (location.protocol === "https:" && !t.secure) return say(card("This page isn't secure", `${t.host} is plain http, which a secure page can't show inside it.`, h("div", { class: "bro-acts" }, h("button", { type: "button", class: "btn primary", "data-key": "bro-newtab", textContent: "Open in a new tab", onclick: () => openTab(t) }))));
        loading.hidden = false;
        const can = await api(`/api/browser/frameable?url=${encodeURIComponent(t.href)}`).catch(() => ({ frameable: null }));
        if (st.t !== t || !st.alive) return;
        if (can.frameable === false) return say(card(`${t.host} won't open inside the hub`, "It doesn't let other pages show it. A new tab works.", h("div", { class: "bro-acts" }, h("button", { type: "button", class: "btn primary", "data-key": "bro-newtab", textContent: "Open in a new tab", onclick: () => openTab(t) }))));
        frameIt(t.href, t);
        if (can.frameable === null) {
          fill(note, h("span", { textContent: "If this stays blank, the site won't show inside another page." }), h("button", { type: "button", class: "retry", textContent: "Open in a new tab", onclick: () => openTab(t) }));
          note.hidden = false;
        }
        return;
      }
      loading.hidden = false;
      const up = await api(`/api/browser/probe?port=${t.port}`);
      if (st.t !== t || !st.alive) return;
      if (!up.up) return waitFor(t);
      const where = await base();
      if (st.t !== t || !st.alive) return;
      if (!where) { B.again = () => open(t.href); return say(unreachable()); }
      frameIt(await goUrl(where, t), t);
    });
    const start = url || lastUrl(sid);
    if (start) open(start); else showPicks();
    return { el, open, focus: () => bar.input.focus(), reload: () => reload.click(), leave: () => { st.alive = false; stop(); } };
  };

  // ── the device preview ──
  const DEVICES = [
    { id: "iphone", name: "iPhone", w: 390, h: 844 },
    { id: "small", name: "Small phone", w: 375, h: 667 },
    { id: "ipad", name: "iPad", w: 820, h: 1180 },
    { id: "laptop", name: "Laptop", w: 1440, h: 900 },
    { id: "custom", name: "Custom", w: 1024, h: 768 },
  ];
  const PREFS = "hub.preview";
  const prefs = () => {
    let p = {};
    try { p = JSON.parse(localStorage.getItem(PREFS) || "{}") || {}; } catch (e) { p = {}; }
    const on = Array.isArray(p.on) ? p.on.filter((id) => DEVICES.some((d) => d.id === id)) : null;
    return { on: on && on.length ? on : ["iphone", "ipad", "laptop"], one: DEVICES.some((d) => d.id === p.one) ? p.one : "iphone", turned: p.turned && typeof p.turned === "object" ? p.turned : {},
      fit: p.fit !== false, custom: { w: Number(p.custom && p.custom.w) || 1024, h: Number(p.custom && p.custom.h) || 768 } };
  };
  const keepPrefs = (p) => { try { localStorage.setItem(PREFS, JSON.stringify(p)); } catch (e) { /* kept for this page only */ } };

  const makePreview = ({ sid = "", url = "", compact = false, onUrl = null } = {}) => {
    const p = prefs();
    const st = { t: null, src: "", path: "", frames: [], alive: true, timer: null };
    const single = () => compact || phone.matches;
    const sizeOf = (d) => { const w = d.id === "custom" ? p.custom.w : d.w, hgt = d.id === "custom" ? p.custom.h : d.h; return p.turned[d.id] ? { w: hgt, h: w } : { w, h: hgt }; };
    const shownDevices = () => single() ? DEVICES.filter((d) => d.id === p.one) : DEVICES.filter((d) => p.on.includes(d.id));
    const reloadAll = iconButton("reload", "Reload all", () => { st.frames.forEach((f) => f.reload()); }, "pv-reload");
    const browserLink = compact && feature("browser") ? h("a", { class: "icon bro-btn", title: "Open in the browser", "aria-label": "Open in the browser", "data-key": "pv-browser", href: routeFor("browser", sid, ""),
      onclick: (e) => { e.currentTarget.href = routeFor("browser", sid, st.t ? st.t.href : ""); } }, uiIcon("globe")) : null;
    const bar = addressBar({ sid, compact, onOpen: (text) => open(text), buttons: { before: [reloadAll], after: [iconButton("external", "Open in a new tab", () => openTab(st.t), "pv-tab"), browserLink] } });
    const tools = h("div", { class: "pv-tools" });
    const stage = h("div", { class: "pv-stage" });
    const el = h("div", { class: `pv ${compact ? "compact" : ""}` }, bar.form, tools, stage);
    const save = () => keepPrefs(p);
    const drawTools = () => {
      const fitBtn = h("button", { type: "button", class: `pv-chip ${p.fit ? "on" : ""}`, "aria-pressed": p.fit ? "true" : "false", "data-key": "pv-fit", title: "Scale the devices to fit", onclick: () => { p.fit = !p.fit; save(); drawTools(); layout(); } }, uiIcon("fit"), p.fit ? "Fit" : "100%");
      const custom = (p.on.includes("custom") && !single()) || (single() && p.one === "custom") ? h("span", { class: "pv-custom" },
        h("input", { type: "number", min: 240, max: 3840, value: p.custom.w, "aria-label": "Custom width", "data-key": "pv-w", onchange: (e) => { p.custom.w = Math.max(240, Math.min(3840, Number(e.target.value) || 1024)); save(); draw(); } }),
        h("span", { class: "faint", textContent: "×" }),
        h("input", { type: "number", min: 240, max: 3840, value: p.custom.h, "aria-label": "Custom height", "data-key": "pv-h", onchange: (e) => { p.custom.h = Math.max(240, Math.min(3840, Number(e.target.value) || 768)); save(); draw(); } })) : null;
      if (single()) {
        const pick = h("select", { class: "pv-pick", "aria-label": "Device", "data-key": "pv-device", onchange: (e) => { p.one = e.target.value; save(); drawTools(); draw(); } },
          DEVICES.map((d) => h("option", { value: d.id, selected: d.id === p.one, textContent: d.id === "custom" ? "Custom size" : `${d.name} · ${d.w} × ${d.h}` })));
        const d = DEVICES.find((x) => x.id === p.one);
        fill(tools, pick, custom, h("button", { type: "button", class: "pv-chip", "data-key": "pv-rotate", title: "Rotate", "aria-pressed": p.turned[d.id] ? "true" : "false", onclick: () => { p.turned[d.id] = !p.turned[d.id]; save(); draw(); drawTools(); } }, uiIcon("rotate"), "Rotate"));
        return;
      }
      fill(tools, h("div", { class: "pv-devs", role: "group", "aria-label": "Devices" }, DEVICES.map((d) => h("button", { type: "button", class: `pv-chip ${p.on.includes(d.id) ? "on" : ""}`, "aria-pressed": p.on.includes(d.id) ? "true" : "false", "data-key": `pv-dev:${d.id}`,
        onclick: () => { p.on = p.on.includes(d.id) ? p.on.filter((x) => x !== d.id) : DEVICES.filter((x) => x.id === d.id || p.on.includes(x.id)).map((x) => x.id); if (!p.on.length) p.on = [d.id]; save(); drawTools(); draw(); } },
        d.name))), custom, h("span", { class: "pv-gap" }), fitBtn);
    };
    const layout = () => {
      if (!st.frames.length) return;
      const pad = single() ? 12 : 24, gap = 24, label = 44;
      const W = stage.clientWidth - pad * 2 - gap * (st.frames.length - 1), H = stage.clientHeight - pad * 2 - label;
      const sizes = st.frames.map((f) => sizeOf(f.device));
      const fit = single() || p.fit;
      const scale = fit ? Math.max(0.1, Math.min(1, W / sizes.reduce((a, s) => a + s.w, 0), H / Math.max(...sizes.map((s) => s.h)))) : 1;
      stage.classList.toggle("scroll", !fit);
      st.frames.forEach((f, i) => f.size(sizes[i], scale));
    };
    const frameFor = (device) => {
      const iframe = h("iframe", { class: "pv-frame", title: `${device.name} preview`, sandbox: SANDBOX, referrerPolicy: "no-referrer", src: st.src });
      const screen = h("div", { class: "pv-screen" }, iframe);
      const label = h("span", { class: "pv-size mono" });
      const first = sizeOf(device);
      iframe.style.width = `${first.w}px`; iframe.style.height = `${first.h}px`;  // the page is laid out at the device's size from its first paint
      const rec = { device, iframe, port: st.t && st.t.local ? st.t.port : null, path: st.path,
        heard: (d) => {
          let u; try { u = new URL(d.href); } catch (e) { return; }
          if (u.origin !== B.base || u.pathname.startsWith("/__hub/")) return;
          rec.path = `${u.pathname}${u.search}${u.hash}`;
          if (rec.path === st.path) return;
          st.path = rec.path;  // one device went somewhere: the others follow, so they always show the same page
          const now = readAddress(`http://localhost:${rec.port}${st.path}`);
          if (now) { st.t = now; bar.show(now); keepUrl(sid, now.href); if (onUrl) onUrl(now.href); }
          st.frames.forEach((f) => { if (f !== rec && f.path !== st.path && f.iframe.contentWindow) f.iframe.contentWindow.postMessage({ hubFrame: "go", path: st.path }, B.base); });
        },
        stale: (port) => { rec.cover.hidden = false; rec.cover.firstChild.textContent = `The preview moved to :${port}.`; },
        reload: () => { rec.cover.hidden = true; if (rec.port && iframe.contentWindow && B.base) iframe.contentWindow.postMessage({ hubFrame: "reload" }, B.base); else iframe.src = st.src; },
        size: (s, scale) => {
          wrap.style.width = `${Math.round(s.w * scale)}px`;
          screen.style.width = `${Math.round(s.w * scale)}px`; screen.style.height = `${Math.round(s.h * scale)}px`;
          iframe.style.width = `${s.w}px`; iframe.style.height = `${s.h}px`; iframe.style.transform = scale === 1 ? "" : `scale(${scale})`;
          label.textContent = `${s.w} × ${s.h}${scale < 0.995 ? ` · ${Math.round(scale * 100)}%` : ""}`;
        } };
      rec.cover = h("div", { class: "pv-cover", hidden: true }, h("span"), h("button", { type: "button", class: "btn", textContent: "Reload", onclick: () => open(st.t.href) }));
      screen.append(rec.cover);
      const wrap = h("figure", { class: "pv-dev", "data-device": device.id },
        h("figcaption", { class: "pv-label" }, h("span", { class: "pv-name" }, h("b", { textContent: device.name }), label),
          single() ? null : iconButton("rotate", `Rotate the ${device.name}`, () => { p.turned[device.id] = !p.turned[device.id]; save(); layout(); }, `pv-turn:${device.id}`),
          iconButton("reload", `Reload the ${device.name}`, () => rec.reload(), `pv-one:${device.id}`)),
        screen);
      rec.wrap = wrap;
      if (rec.port) B.frames.add(rec);
      return rec;
    };
    const clear = () => { st.frames.forEach((f) => B.frames.delete(f)); st.frames = []; clearTimeout(st.timer); };
    const draw = () => {
      clear();
      if (!st.src) return;
      st.frames = shownDevices().map(frameFor);
      fill(stage, h("div", { class: "pv-row" }, st.frames.map((f) => f.wrap)));
      if (st.t && st.t.local) nowOn(st.t.port, null);
      requestAnimationFrame(layout);
    };
    const say = (node) => { clear(); st.src = ""; fill(stage, node); };
    const open = guard(async (text) => {
      const t = readAddress(text);
      if (!t) { toast("That isn't an address the preview can open.", true); return; }
      st.t = t; st.path = t.local ? t.path : ""; bar.show(t); keepUrl(sid, t.href); if (onUrl) onUrl(t.href);
      if (!t.local) {
        if (location.protocol === "https:" && !t.secure) return say(card("This page isn't secure", `${t.host} is plain http, which a secure page can't show inside it.`));
        const can = await api(`/api/browser/frameable?url=${encodeURIComponent(t.href)}`).catch(() => ({ frameable: null }));
        if (st.t !== t || !st.alive) return;
        if (can.frameable === false) return say(card(`${t.host} won't open inside the hub`, "It doesn't let other pages show it.", h("div", { class: "bro-acts" }, h("button", { type: "button", class: "btn primary", textContent: "Open in a new tab", onclick: () => openTab(t) }))));
        st.src = t.href; return draw();
      }
      const up = await api(`/api/browser/probe?port=${t.port}`);
      if (st.t !== t || !st.alive) return;
      if (!up.up) {
        say(card(`Nothing is running on :${t.port}`, "Start the dev server, and the devices show it by themselves.", h("div", { class: "bro-acts" }, h("button", { type: "button", class: "btn", "data-key": "bro-retry", textContent: "Try now", onclick: () => open(t.href) }))));
        st.timer = setTimeout(async function again() {
          if (!st.alive || st.t !== t) return;
          const now = await api(`/api/browser/probe?port=${t.port}`).catch(() => ({ up: false }));
          if (!st.alive || st.t !== t) return;
          if (now.up) open(t.href); else st.timer = setTimeout(again, 3000);
        }, 3000);
        return;
      }
      const where = await base();
      if (st.t !== t || !st.alive) return;
      if (!where) { B.again = () => open(t.href); return say(unreachable()); }
      st.src = await goUrl(where, t);
      draw();
    });
    const showPicks = async () => {
      say(card("Open a page", "Pick a server, or type an address above. It shows on every device at once.", h("div", { class: "bro-list", textContent: "Looking…" })));
      const rows = await suggestions(sid);
      if (!st.alive || st.t) return;
      const list = stage.querySelector(".bro-list");
      if (list) fill(list, suggestList(rows, (href) => open(href), sid));
    };
    const watch = new ResizeObserver(() => layout());
    watch.observe(stage);
    const onPhone = () => { drawTools(); if (st.src) draw(); };
    phone.addEventListener("change", onPhone);
    drawTools();
    const start = url || lastUrl(sid);
    if (start) open(start); else showPicks();
    return { el, open, focus: () => bar.input.focus(), reload: () => st.frames.forEach((f) => f.reload()),
      leave: () => { st.alive = false; clear(); watch.disconnect(); phone.removeEventListener("change", onPhone); } };
  };

  // ── the pages: #/browser[/<sid>[/<address>]] and #/preview[/<sid>[/<address>]] ──
  const page_ = (r) => {
    const s = r.sid ? session(r.sid) : null;
    const preview = r.name === "preview";
    const name = preview ? "Device preview" : "Browser";
    const made = (preview ? makePreview : makeBrowser)({ sid: s ? s.id : "", url: r.url });
    const crumbs = s ? [h("a", { href: `#/s/${s.id}`, class: "crumb", textContent: s.title || "Session" }), tail(name)] : [tail(name)];
    const other = preview ? (feature("browser") ? h("a", { class: "btn", href: routeFor("browser", s ? s.id : "", ""), "data-key": "to-browser" }, uiIcon("globe"), "Browser") : null)
      : (feature("preview") ? h("a", { class: "btn", href: routeFor("preview", s ? s.id : "", ""), "data-key": "to-preview" }, uiIcon("devices"), "Devices") : null);
    setTop(crumbs, [other]);
    view.append(h("div", { class: `bro-page ${preview ? "is-preview" : ""}` }, made.el));
    bind([["l", "address"], ["r", preview ? "reload all" : "reload"]], { l: () => made.focus(), r: () => made.reload() });
    page.leave = () => made.leave();
  };

  // ── side panels (the tabs agent's side panel shows them beside a session) ──
  const live = new Map();
  const panel = (id, title, icon, featureName, order, make) => addPanel({
    id, title, icon, feature: featureName, order,
    available: () => true,
    render: (s, box) => {
      const was = live.get(box);
      if (was && was.sid === s.id) return was.made.el;
      if (was) was.made.leave();
      const made = make({ sid: s.id, compact: true });
      live.set(box || made.el, { sid: s.id, made });
      return made.el;
    },
    leave: () => { live.forEach((v) => v.made.leave()); live.clear(); },
  });
  panel("browser", "Browser", "globe", "browser", 40, makeBrowser);
  panel("preview", "Devices", "devices", "preview", 41, makePreview);

  // Go to (⌘K): the two pages, for the session in hand when there is one.
  const palette = (held) => [
    feature("browser") ? { text: "Browser", icon: "globe", run: () => go(routeFor("browser", held ? held.id : "", "")) } : null,
    feature("preview") ? { text: "Device preview", icon: "devices", run: () => go(routeFor("preview", held ? held.id : "", "")) } : null,
  ].filter(Boolean);

  // Other features open an address here: hubBrowser.open({ url, sid? }) shows it in the browser (a no while it's off).
  const openIn = ({ url, sid } = {}) => { if (!feature("browser") || !url) return false; go(routeFor("browser", sid || "", String(url))); return true; };

  window.hubBrowser = { open: openIn, page: page_, palette, makeBrowser, makePreview, readAddress, base, routeFor, state: B };
})();
