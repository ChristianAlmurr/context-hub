"use strict";
// Dream Hub. Everything from the server is placed with textContent: memory and chat hold text from transcripts and the web.

const clean = (kids) => kids.flat(Infinity).filter((kid) => kid !== null && kid !== undefined && kid !== false);
// A redraw replaces nodes. Focus, the place in a scrolled list and a press that spans a poll all survive it.
const SPOTS = "a[href], button, input, textarea, select, summary";
const tagKind = (el) => `${el.tagName}|${el.getAttribute("role") || ""}`;
const spotIn = (root) => {
  const at = document.activeElement;
  if (!at || at === document.body || at === root || !root.contains(at) || !at.matches(SPOTS)) return null;
  const same = [...root.querySelectorAll(SPOTS)].filter((el) => tagKind(el) === tagKind(at));
  return { key: at.dataset.key || at.dataset.nav, kind: tagKind(at), index: same.indexOf(at) };
};
const returnTo = (root, spot) => {
  if (!spot) return;
  const keyed = spot.key && root.querySelector(`[data-key="${CSS.escape(spot.key)}"], [data-nav="${CSS.escape(spot.key)}"]`);
  const same = [...root.querySelectorAll(SPOTS)].filter((el) => tagKind(el) === spot.kind);
  const next = keyed || same[spot.index] || same[same.length - 1];
  if (next && next !== document.activeElement) next.focus({ preventScroll: true });
};
const fill = (el, ...kids) => {
  const spot = spotIn(el), scroll = el.scrollTop;
  el.replaceChildren(...clean(kids));
  if (scroll) el.scrollTop = scroll;
  returnTo(el, spot);
};
// Unchanged data leaves the DOM alone.
const drawn = new WeakMap();
const differs = (el, ...parts) => { const sig = JSON.stringify(parts); if (drawn.get(el) === sig) return false; drawn.set(el, sig); return true; };
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || (value === false && key !== "spellcheck")) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key === "style") el.style.cssText = value;
    else if (key in el && key !== "list") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...clean(kids));
  if ((tag === "button" || tag === "a") && attrs.title && !attrs["aria-label"] && !el.textContent.trim()) el.setAttribute("aria-label", attrs.title);
  return el;
};
const svg = (paths) => {
  const span = document.createElement("span");
  span.innerHTML = `<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
  return span.firstChild;
};
const UI = {
  dots: '<g fill="currentColor" stroke="none"><circle cx="3.5" cy="8" r="1.25"/><circle cx="8" cy="8" r="1.25"/><circle cx="12.5" cy="8" r="1.25"/></g>',
  bell: '<path d="M4 11.5V7a4 4 0 0 1 8 0v4.5"/><path d="M2.5 11.5h11"/><path d="M6.8 13.8a1.3 1.3 0 0 0 2.4 0"/>',
  phone: '<path d="M5 1.5h6a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1Z"/><path d="M7 12.5h2"/>',
  stop: '<rect x="4" y="4" width="8" height="8"/>',
  close: '<path d="m4 4 8 8M12 4l-8 8"/>', plus: '<path d="M8 3v10M3 8h10"/>', chev: '<path d="m6 3 5 5-5 5"/>',
  menu: '<path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11"/>', split: '<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M8 2.5v11"/>',
  splitDown: '<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 8h12"/>',
  move: '<path d="M8 2.5v11M2.5 8h11M6.3 4.2 8 2.5l1.7 1.7M6.3 11.8 8 13.5l1.7-1.7M4.2 6.3 2.5 8l1.7 1.7M11.8 6.3 13.5 8l-1.7 1.7"/>',
  shared: '<path d="M6.5 9.5 9.5 6.5"/><path d="M7.5 4.5 9 3a2.8 2.8 0 0 1 4 4l-1.5 1.5"/><path d="M8.5 11.5 7 13a2.8 2.8 0 0 1-4-4l1.5-1.5"/>',
  gear: '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v1.7M8 12.5v1.7M1.8 8h1.7M12.5 8h1.7M3.6 3.6l1.2 1.2M11.2 11.2l1.2 1.2M12.4 3.6l-1.2 1.2M4.8 11.2l-1.2 1.2"/>',
  external: '<path d="M9.5 2.5h4v4M13.5 2.5 7.5 8.5M12 9.5v3a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3"/>',
  branch: '<circle cx="4.5" cy="3.5" r="1.5"/><circle cx="4.5" cy="12.5" r="1.5"/><circle cx="11.5" cy="5.5" r="1.5"/><path d="M4.5 5v6M11.5 7c0 2.5-3 2.5-7 3.5"/>',
  check: '<path d="m3.5 8.5 3 3 6-7"/>', updown: '<path d="m5.5 6.5 2.5-2.5 2.5 2.5M5.5 9.5 8 12l2.5-2.5"/>', corner: '<path d="M4 3.5v4.5a2 2 0 0 0 2 2h6.5M10 7.5l2.5 2.5-2.5 2.5"/>',
  panel: '<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M10 2.5v11"/>',
  sidebar: '<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M6 2.5v11"/>',
  home: '<path d="M2.5 7 8 2.5 13.5 7"/><path d="M4 6v7.5h8V6"/>',
  pin: '<path d="M6 2.5h4M6.8 2.5v4L4.5 9.5h7L9.2 6.5v-4M8 9.5v4"/>',
  clip: '<path d="m13 7.5-5.3 5.3a3.2 3.2 0 0 1-4.5-4.5l5.5-5.5a2.1 2.1 0 0 1 3 3L6.2 11.3a1 1 0 0 1-1.5-1.5L9.5 5"/>',
  folder: '<path d="M2 4.5a1 1 0 0 1 1-1h3l1.5 1.5H13a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1Z"/>',
  folderPlus: '<path d="M2 4.5a1 1 0 0 1 1-1h3l1.5 1.5H13a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1Z"/><path d="M8 7.5v4M6 9.5h4"/>',
  hub: '<circle cx="8" cy="8" r="2"/><circle cx="3" cy="3.5" r="1.3"/><circle cx="13" cy="3.5" r="1.3"/><circle cx="3" cy="12.5" r="1.3"/><circle cx="13" cy="12.5" r="1.3"/><path d="m4 4.5 2.5 2M12 4.5l-2.5 2M4 11.5l2.5-2M12 11.5l-2.5-2"/>',
  send: '<path d="M8 13V3.5M4 7.5l4-4 4 4"/>',
  term: '<rect x="1.5" y="2.5" width="13" height="11" rx="1.5"/><path d="m4.5 6 2 2-2 2M8.5 10.5h3"/>',
  chat: '<path d="M2.5 3.5h11v7.5H7l-3 2.5V11H2.5Z"/>',
  keyboard: '<rect x="1.5" y="4" width="13" height="8" rx="1"/><path d="M4 6.5h1M7.5 6.5h1M11 6.5h1M4 9.5h8"/>',
  catcher: '<circle cx="8" cy="6" r="4.5"/><path d="M8 3.6 10.4 6 8 8.4 5.6 6Z"/><path d="M5 10.4v4M8 10.5v4.5M11 10.4v4"/>',
};
const pinMark = () => h("span", { class: "pin-mark", role: "img", "aria-label": "Pinned", title: "Pinned" }, svg(UI.pin));
const uiIcon = (name) => svg(UI[name]);
const known = (message) => Object.assign(new Error(message), { known: true });
const NO_ANSWER = "The hub didn't answer. Check the connection and try again.";
const api = async (path, body) => {
  const options = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options).catch(() => { throw known(NO_ANSWER); });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(known(data.error || NO_ANSWER), { status: response.status, held: !!data.held });
  return data;
};
const upload = async (path, file) => {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file }).catch(() => { throw known(NO_ANSWER); });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw known(data.error || "That file didn't upload. Try again.");
  return data;
};
const toastEl = document.getElementById("toast");
// A passing note floats. An error stays, so it takes a line of its own under the top bar and never sits over a terminal's prompt.
const placeToast = () => {
  const open = [...document.querySelectorAll("dialog[open]")].pop();
  if (open) { if (toastEl.parentNode !== open) open.append(toastEl); }
  else if (toastEl.classList.contains("sticky")) { if (toastEl.nextElementSibling !== view) view.before(toastEl); }
  else if (toastEl.parentNode !== document.body) document.body.append(toastEl);
};
const hideToast = () => {
  clearTimeout(toast.timer);
  const wasSticky = toastEl.classList.contains("sticky"), hadFocus = toastEl.contains(document.activeElement);
  toastEl.classList.remove("show", "sticky");
  if (!wasSticky) return;
  fill(toastEl);
  placeToast();
  if (hadFocus) { if (route().name === "session" && pageKeys.Enter) pageKeys.Enter(); else view.focus({ preventScroll: true }); }
};
function toast(text, sticky) {
  toastEl.classList.toggle("sticky", !!sticky);
  placeToast();
  fill(toastEl, h("span", { textContent: text }), sticky ? h("button", { class: "icon", type: "button", title: "Dismiss", onclick: hideToast }, uiIcon("close")) : null);
  toastEl.classList.add("show");
  clearTimeout(toast.timer);
  if (!sticky) toast.timer = setTimeout(hideToast, 5000);
}
const explain = (error) => toast(error.known ? error.message : "That didn't work. Reload the page and try again.", true);
const guard = (fn) => async (...args) => { try { return await fn(...args); } catch (error) { explain(error); } };
// One press, one action: the button says what it's doing and can't fire twice.
const once = (word, fn, button) => {
  let running = false;
  return async (...args) => {
    if (running) return;
    running = true;
    const el = button || (args[0] && args[0].currentTarget);
    const had = el ? [...el.childNodes] : [];
    if (el) { el.setAttribute("aria-busy", "true"); el.setAttribute("aria-disabled", "true"); el.textContent = word; }
    try { return await fn(...args); } catch (error) { explain(error); } finally {
      running = false;
      if (el) { el.removeAttribute("aria-busy"); el.removeAttribute("aria-disabled"); el.replaceChildren(...had); }
    }
  };
};
const say = (text) => { document.getElementById("say").textContent = text; };
// Two steps for what a stray key shouldn't start. Focus lands on the way out, so a repeated key or Enter can't confirm it.
let confirmOpen = false;
const confirmStep = ({ title, body, yes, no }) => new Promise((resolve) => {
  if (confirmOpen) { resolve(false); return; }
  confirmOpen = true;
  let answer = false;
  const dialog = h("dialog", { class: "confirm", "aria-label": title });
  const stay = h("button", { type: "button", class: "btn", textContent: no, onclick: () => dialog.close() });
  const agree = h("button", { type: "button", class: "btn primary", textContent: yes, onclick: () => { answer = true; dialog.close(); } });
  fill(dialog, h("h1", { textContent: title }), body ? h("p", { class: "sheet-lead", textContent: body }) : null, h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  dialog.addEventListener("close", () => { confirmOpen = false; resolve(answer); });
  sheet(dialog);
  stay.focus();
});
// A name asked for in a small sheet: a folder's, say. Resolves to the trimmed name, or null when cancelled.
const askName = ({ title, value = "", yes, placeholder = "" }) => new Promise((resolve) => {
  if (confirmOpen) { resolve(null); return; }
  confirmOpen = true;
  let answer = null;
  const dialog = h("dialog", { class: "confirm", "aria-label": title });
  const input = h("input", { type: "text", class: "name-input", value, placeholder, maxLength: 40, "aria-label": title, enterkeyhint: "done", autocapitalize: "words" });
  const agree = h("button", { type: "submit", class: "btn primary", textContent: yes });
  const form = h("form", { onsubmit: (e) => { e.preventDefault(); const v = input.value.trim().replace(/\s+/g, " "); if (!v) { input.focus(); return; } answer = v; dialog.close(); } },
    h("h1", { textContent: title }), input, h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, h("button", { type: "button", class: "btn", textContent: "Cancel", onclick: () => dialog.close() }), agree)));
  dialog.append(form);
  dialog.addEventListener("close", () => { confirmOpen = false; resolve(answer); });
  sheet(dialog);
  input.focus();
  input.select();
});
// What a failed load leaves where its content would have been.
// A slow load says so; a fast one doesn't flash.
const loadingIn = (box, text, stillMine = () => true) => { const timer = setTimeout(() => { if (stillMine()) fill(box, h("div", { class: "empty-line", role: "status", textContent: text })); }, 200); return () => clearTimeout(timer); };
// A retry that fails again in a blink still has to look like it ran.
const retryLine = (text, retry) => h("div", { class: "empty-line retry-line", role: "alert" }, h("span", { textContent: text }), h("button", { class: "retry", textContent: "Retry", onclick: once("Retrying…", async (e) => { await Promise.all([retry(e), new Promise((done) => setTimeout(done, 400))]); }) }));
// Shape first, colour second: every state reads without hue and without motion.
const DOT_WORDS = { working: "Working", needs: "Needs you", finished: "Finished", shell: "Terminal", ended: "Ended", closing: "Closing", closed: "Closed", offline: "Not connected", "no-claude": "Claude isn't running", error: "Stopped with an error",
  dreaming: "Dreaming", reasoning: "Thinking", searching: "Searching", using: "Using a tool", compacting: "Compacting", retrying: "Retrying", background: "Working in the background", waiting: "Waiting", idle: "Idle" };
// The terminal is still open but Claude has left it: that isn't Ended.
const shownState = (s) => s.state === "ended" && s.alive ? "no-claude" : s.state;
// A name stays on one line when it fits, so "web-shop" doesn't break at its hyphen.
const nb = (text) => h("span", { class: "nb", dir: "auto", textContent: text });
const dot = (state, title) => state ? h("span", { class: `dot ${state}`, role: "img", "aria-label": DOT_WORDS[state] || state, title }) : h("span", { class: "dot", "aria-hidden": "true" });
// Motion as the person chose it (theme.js resolves "system" from the media query), else as the system asks.
const reduced = () => document.documentElement.dataset.motion ? document.documentElement.dataset.motion === "reduce" : matchMedia("(prefers-reduced-motion: reduce)").matches;
const P = (name) => encodeURIComponent(name);
const ago = (seconds) => {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 90) return "now";
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
};
const agoWords = (seconds) => ago(seconds) === "now" ? "just now" : `${ago(seconds)} ago`;
// ── Dream timing: the kit checks once a day and dreams only when one is due ──
const WEEKDAYS = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"];
const clockHour = (hour) => `${String(hour).padStart(2, "0")}:00`;
// A job made before the daily check runs on one weekday, and reads that way until the project is switched off and on again.
const weekly = (schedule) => !!schedule && schedule.weekday !== null && schedule.weekday !== undefined;
const dreamTiming = (schedule, lead = "") => !schedule ? "Automatic dreams"
  : weekly(schedule) ? `${lead}${WEEKDAYS[schedule.weekday % 7]} ${clockHour(schedule.hour)}` : `Automatic dreams, checked daily at ${clockHour(schedule.hour)}`;
// What the kit last decided, in its own words after "due:" or "not due:" (counts, or why it is holding back after a
// try that wrote nothing), with when. The reason of the last dream is the same line without "due:", or "started by hand".
const dreamCheck = (check) => {
  if (!check) return [];
  if (check.problem) return [check.problem];
  const lines = [], reason = check.reason.replace(/^due: /, "");
  if (reason && check.dreamed) lines.push(reason === "started by hand" ? `Last dream ${agoWords(check.dreamed)}, started by hand` : `Last dream ${agoWords(check.dreamed)}: ${reason}`);
  if (check.verdict && check.checked && check.verdict.replace(/^due: /, "") !== reason) {
    const [, not, counts] = check.verdict.match(/^(not )?due: (.*)$/) || [];
    lines.push(counts === undefined ? `Checked ${agoWords(check.checked)}: ${check.verdict}` : `${not ? "Not due" : "Due"} when checked ${agoWords(check.checked)}: ${counts}`);
    // While an open proposal holds a due dream back, the daily check reminds its person every few days.
    if (check.reminded && check.verdict.startsWith("not due: the proposal")) lines.push(`You were reminded of this proposal on ${dayOf(check.reminded.at)}`);
  }
  if (check.waiting_said) lines.push(`You were reminded on ${dayOf(check.waiting_said)} that approved changes are waiting`);
  return lines;
};
const dayOf = (at) => new Date(at * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const dreamWhy = (check) => dreamCheck(check).map((line) => h("div", { class: "dream-why", textContent: line }));
const saved = {
  get(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* the view just resets */ } },
};
// Inline marks, and what Claude names: a link opens in a new tab, and inside a session a file path in `code` opens in
// the viewer (or says why it can't).
const FILE_LIKE = /^(?:~\/|\/|\.{1,2}\/)?[\w.@%+-]+(?:\/[\w.@%+ -]+)*\.(png|jpe?g|gif|webp|avif|svg|mp3|m4a|wav|ogg|flac|aac|mp4|mov|webm|pdf|md|txt|json|csv|log|py|js|ts|tsx|swift|sh|html|css|ya?ml|toml)$/i;
const webLink = (url, label, sid) => {
  const a = h("a", { class: "in-link", href: url, target: "_blank", rel: "noopener noreferrer", dir: "auto", textContent: label || url.replace(/^https?:\/\/(www\.)?/, "") });
  if (matchMedia("(hover: hover)").matches) { a.onmouseenter = (e) => showHover(e, url, sid); a.onmouseleave = hideHover; a.onclick = hideHover; }
  return a;
};
const inline = (text, ctx = {}) => {
  const out = [];
  const pattern = /`([^`]+)`|\*\*([^*]+)\*\*|!?\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>"'`)\]}]+)|!?\[([^\]]*)\]\(<?([^)<>\n]+?)>?\)/g;
  let last = 0, match;
  while ((match = pattern.exec(text))) {
    if (match.index > last) out.push(text.slice(last, match.index));
    if (match[1] !== undefined) {
      const code = match[1];
      if (/^https?:\/\/\S+$/.test(code)) out.push(webLink(code, null, ctx.sid));
      else if (ctx.sid && FILE_LIKE.test(code)) out.push(h("button", { type: "button", class: "in-file", title: "Open", onclick: () => openPreview({ sid: ctx.sid, path: code }) }, h("code", { textContent: code })));
      else out.push(h("code", { textContent: code }));
    } else if (match[2] !== undefined) out.push(h("strong", { textContent: match[2] }));
    else if (match[3] !== undefined) out.push(webLink(match[4], match[3] || null, ctx.sid));
    else if (match[6] !== undefined) {  // [label](path) or ![label](path) naming a file of the session: the label opens it
      const path = (() => { try { return decodeURI(tidyPath(match[7].trim())); } catch { return tidyPath(match[7].trim()); } })();
      if (ctx.sid && FILE_LIKE.test(path)) out.push(h("button", { type: "button", class: "in-file", title: path, onclick: () => openPreview({ sid: ctx.sid, path }) }, h("code", { textContent: match[6] || path.split("/").pop() })));
      else out.push(match[0]);
    } else {
      const url = match[5].replace(/[.,;:!?*_]+$/, "");
      out.push(webLink(url, null, ctx.sid));
      if (url.length < match[5].length) out.push(match[5].slice(url.length));
    }
    last = pattern.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
};
const markdown = (text, ctx = {}) => {
  const root = h("div", { class: "doc" });
  let list = null, fence = null, table = null;
  const closeFence = () => { root.append(h("pre", {}, h("code", { textContent: fence.join("\n") }))); fence = null; };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*```/.test(line)) { if (fence) closeFence(); else { fence = []; list = table = null; } continue; }
    if (fence) { fence.push(raw); continue; }
    if (/^\s*<!--.*-->\s*$/.test(line)) continue;
    if (/^\s*\|/.test(line)) {
      list = null;
      if (/^\s*\|[\s:|-]+$/.test(line)) continue;
      const tag = table ? "td" : "th";
      if (!table) { table = h("table"); root.append(table); }
      table.append(h("tr", {}, line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => h(tag, {}, inline(cell.trim(), ctx)))));
      continue;
    }
    table = null;
    const bullet = line.match(/^\s*[-*] (.*)$/), numbered = !bullet && line.match(/^\s*(\d+)[.)] (.*)$/);
    if (bullet || numbered) {
      const tag = bullet ? "UL" : "OL";
      if (!list || list.tagName !== tag) { list = bullet ? h("ul") : h("ol", { start: numbered[1] }); root.append(list); }
      list.append(h("li", {}, inline(bullet ? bullet[1] : numbered[2], ctx)));
      continue;
    }
    list = null;
    const heading = line.match(/^#{1,4} (.*)$/);
    if (heading) root.append(h("h3", {}, inline(heading[1], ctx)));
    else if (line.trim()) root.append(h("p", { dir: "auto" }, inline(line, ctx)));
  }
  if (fence) closeFence();
  return root;
};

// ── project identity: a pixel glyph drawn from the name, unless you uploaded an image ──
const nameHash = (name) => {
  let hash = 2166136261;
  for (const c of name) { hash ^= c.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  return hash >>> 0;
};
const IDENTITY = [0, 1, 2, 3, 4, 5].map((i) => `var(--id-${i})`);  // a project keeps its colour everywhere, in each theme's tone of it (app.css)
const glyphCells = (name) => {
  const hash = nameHash(name);
  const cells = [];
  for (let y = 0; y < 5; y++) for (let x = 0; x < 3; x++) if ((hash >>> (x + y * 3)) & 1) { cells.push([x, y]); if (x < 2) cells.push([4 - x, y]); }
  return cells.length >= 7 ? cells : [[2, 0], [1, 1], [3, 1], [2, 2], [0, 2], [4, 2], [1, 3], [3, 3], [2, 4]];
};
let iconStamp = Date.now();
const mark = (p, size = 20, icon = p.icon) => {
  const edge = Math.max(15, Math.round(size / 5) * 5);  // whole pixels, so the glyph stays crisp
  const tile = h("span", { class: "mark", style: `width:${edge}px;height:${edge}px;--c:${IDENTITY[nameHash(p.name) % IDENTITY.length]}` });
  if (icon && icon.kind === "image") tile.append(h("img", { src: `/api/p/${P(p.name)}/icon?v=${iconStamp}`, alt: "" }));
  else {
    const holder = document.createElement("span");
    holder.innerHTML = `<svg viewBox="0 0 5 5" fill="currentColor" shape-rendering="crispEdges" aria-hidden="true">${glyphCells(p.name).map(([x, y]) => `<rect x="${x}" y="${y}" width="1" height="1"/>`).join("")}</svg>`;
    tile.append(holder.firstChild);
  }
  return tile;
};

// ── state and routing ──
let S = { projects: [], sessions: [] };
// Hub-wide settings, as GET /api/settings gives them (the Settings page owns them, and they live in config.json under
// "settings"). Every feature reads its own through pref(), with the default it had before there were settings, so it
// behaves the same until the person changes it.
let SETTINGS = {};
const pref = (name, fallback) => { const v = SETTINGS[name]; return v === undefined || v === null ? fallback : v; };
const view = document.getElementById("view");
const top_ = document.getElementById("top");
const side = document.getElementById("side");
let page = { key: "", update: null, leave: null };
const hub = { ready: false, down: false };
const banner = h("div", { class: "banner", hidden: true }, h("span", { textContent: "Dream Hub isn't answering. Retrying every 3 seconds." }), h("button", { class: "retry", textContent: "Retry now", onclick: once("Retrying…", () => tick()) }));
top_.after(banner);
const staleBanner = h("div", { class: "banner stale", hidden: true }, h("span", { textContent: "Dream Hub was updated. This page is from the version before: reload to use the new one." }), h("button", { class: "retry", textContent: "Reload", onclick: () => location.reload() }));
banner.after(staleBanner);
// ── a newer Dream Hub: said quietly, installed only when the person presses Update ──
let hubVersion = null;
const updateText = h("span");
const updateList = h("ul", { class: "update-list" });
const updateLink = h("a", { class: "retry", target: "_blank", rel: "noopener noreferrer", textContent: "See changes" });
const updateGo = h("button", { class: "retry", textContent: "Update" });
const updateLater = h("button", { class: "retry", textContent: "Later" });
const updateBanner = h("div", { class: "banner update", hidden: true }, updateText, updateLink, updateGo, updateLater, h("details", { class: "update-more" }, h("summary", { textContent: "What changed" }), updateList));
staleBanner.after(updateBanner);
const laterKey = () => { try { return localStorage.getItem("hub.updateLater") || ""; } catch (e) { return ""; } };
const paintUpdate = (u) => {
  hubVersion = u.version || null;
  const newest = u.commits && u.commits[0] ? u.commits[0].commit : (u.state || "");
  const show = u.state === "available" || u.state === "by hand";
  if (!show || laterKey() === newest) { updateBanner.hidden = true; return; }
  updateBanner.dataset.newest = newest;
  const n = u.behind || 0;
  updateText.textContent = u.state === "by hand" ? `Dream Hub has an update. ${u.why}`
    : `Update available: ${n} ${n === 1 ? "change" : "changes"}, newest ${u.newest || ""}.${u.why ? ` ${u.why}` : ""}`;
  fill(updateList, (u.commits || []).map((c) => h("li", {}, h("code", { textContent: c.commit }), ` ${c.subject} `, h("span", { class: "faint", textContent: c.date }))));
  updateList.parentNode.hidden = !(u.commits || []).length;
  updateLink.hidden = !u.link; if (u.link) updateLink.href = u.link;
  updateGo.hidden = u.state !== "available" || !!u.why;
  updateBanner.hidden = false;
};
updateGo.onclick = once("Updating…", async () => {
  const started = await api("/api/update/apply", {});
  updateGo.hidden = true;
  updateText.textContent = `Updating. The hub restarts when it's done, and this page offers to reload. What it did is in ${started.log}.`;
});
updateLater.onclick = () => { try { localStorage.setItem("hub.updateLater", updateBanner.dataset.newest || ""); } catch (e) {} updateBanner.hidden = true; };
const pollUpdate = async () => { try { paintUpdate(await api("/api/update")); } catch (e) { /* a check that can't be read says nothing */ } };
pollUpdate();
setInterval(pollUpdate, 30 * 60 * 1000);
const checkUpdates = async (button) => {
  button.disabled = true; button.textContent = "Checking…";
  try {
    await api("/api/update/check", {});
    for (let i = 0; i < 40; i++) {
      await new Promise((done) => setTimeout(done, 1000));
      const u = await api("/api/update");
      if (u.checking) continue;
      paintUpdate(u);
      button.textContent = { current: "Up to date", available: `${u.behind} new ${u.behind === 1 ? "change" : "changes"}`, offline: "Couldn't reach the repository", "by hand": "Update by hand", "no origin": "No repository to check", "not a clone": "Not a git clone" }[u.state] || "Checked";
      return;
    }
    button.textContent = "Still checking";
  } catch (error) { button.textContent = error.message || "Couldn't check"; }
};

// ── keyboard: every page says what its keys do on the status line ──
let pageKeys = {}, pageHints = [], navKey = "";
const status_ = document.getElementById("status");
const bind = (hints, actions = {}) => { pageHints = hints; pageKeys = actions; drawStatus(); };
const inTerminal = () => !!(document.activeElement && document.activeElement.closest && document.activeElement.closest(".xterm"));
function drawStatus() {
  const working = S.sessions.filter((s) => s.state === "working").length, waiting = attention();
  const hints = chording() ? [["g", "then"], ["h", "home"], ["d", "dreams"], ["m", "memory"], ["n", "new session"], ["s", "sidebar"]] : typeof pageHints === "function" ? pageHints() : pageHints;
  fill(status_, hints.map(([keys, word]) => h("span", {}, h("kbd", { textContent: keys }), word)), inTerminal() ? null : [hints.some(([keys]) => keys === "/") ? null : h("span", {}, h("kbd", { textContent: "/" }), "find"), h("span", {}, h("kbd", { textContent: "?" }), "keys")],
    h("span", { class: "tally" }, working ? h("b", { class: "work", textContent: `${working} working` }) : null, waiting ? h("b", { class: "need", textContent: `${waiting} waiting` }) : null));
}
const navItems = () => [...view.querySelectorAll("[data-nav]")].filter((el) => el.offsetParent);
const markNav = () => view.querySelectorAll("[data-nav]").forEach((el) => el.classList.toggle("sel", el.dataset.nav === navKey && !!el.offsetParent));
const moveNav = (step) => {
  const items = navItems();
  if (!items.length) return;
  const at = items.findIndex((el) => el.dataset.nav === navKey);
  const next = items[at < 0 ? (step > 0 ? 0 : items.length - 1) : Math.max(0, Math.min(items.length - 1, at + step))];
  navKey = next.dataset.nav;
  markNav();
  next.scrollIntoView({ block: "nearest" });
};
const goUp = () => {
  const r = route();
  if (r.name === "session") { const s = session(r.ids[0]); go(s ? `#/p/${P(s.project)}` : "#/"); }
  else if (r.name === "project") go(r.tab === "home" ? "#/" : r.tab === "new" && r.rest ? `#/s/${r.rest}` : `#/p/${P(r.project)}`);
  else if (r.name === "new") go("#/");
};
const MAX_PANES = 4;
// ── Split layouts: a tree of panes. A split lays its parts side by side ("h") or stacked ("v"); a leaf is a session id.
// The hash says the shape: #/s/a,b is side by side, as it always was (and a,b,c and a,b,c,d the old grid);
// anything else is written out, h(a,v(b,c)) for a beside b over c. Sizes stay in this browser, per layout.
const isSplit = (n) => typeof n !== "string";
const leavesOf = (n) => isSplit(n) ? n.k.flatMap(leavesOf) : [n];
const treeText = (n) => isSplit(n) ? `${n.d}(${n.k.map(treeText).join(",")})` : n;
const even = (count) => Array.from({ length: count }, () => 1 / count);
const legacyLayout = (ids) => ids.length < 2 ? ids[0] : ids.length === 2 ? { d: "h", k: ids, z: even(2) }
  : { d: "v", k: [{ d: "h", k: ids.slice(0, 2), z: even(2) }, ids.length === 3 ? ids[2] : { d: "h", k: ids.slice(2, 4), z: even(2) }], z: even(2) };
const layoutText = (n) => { const ids = leavesOf(n); return ids.length > 1 && treeText(n) === treeText(legacyLayout(ids)) ? ids.join(",") : treeText(n); };
// After any change: a split of one part is that part, a split inside one the same way is folded into it, sizes add up to one.
const tidyLayout = (n) => {
  if (!n || !isSplit(n)) return n || null;
  const k = [], z = [];
  n.k.forEach((kid, i) => {
    kid = tidyLayout(kid);
    if (!kid) return;
    const share = n.z[i] > 0 ? n.z[i] : 1 / n.k.length;
    if (isSplit(kid) && kid.d === n.d) kid.k.forEach((part, j) => { k.push(part); z.push(share * kid.z[j]); });
    else { k.push(kid); z.push(share); }
  });
  if (!k.length) return null;
  if (k.length === 1) return k[0];
  const total = z.reduce((a, b) => a + b, 0) || 1;
  return { d: n.d, k, z: z.map((v) => v / total) };
};
const mapLeaves = (n, swap) => isSplit(n) ? { ...n, k: n.k.map((kid) => mapLeaves(kid, swap)) } : swap(n);
const layoutWithout = (n, id) => tidyLayout(mapLeaves(n, (leaf) => leaf === id ? null : leaf));
const sideDir = (side) => side === "left" || side === "right" ? "h" : "v";
const sideFirst = (side) => side === "left" || side === "top";
// A session dropped beside a pane takes half of that pane's room.
const layoutBeside = (n, target, id, side) => tidyLayout(mapLeaves(layoutWithout(n, id), (leaf) => leaf === target ? { d: sideDir(side), k: sideFirst(side) ? [id, leaf] : [leaf, id], z: even(2) } : leaf));
// Dropped on the edge of the whole split, it runs the full height or width and takes an even share.
const layoutEdge = (n, id, side) => {
  const rest = layoutWithout(n, id);
  if (!rest) return id;
  const d = sideDir(side), parts = isSplit(rest) && rest.d === d ? rest.k.length : 1, share = 1 / (parts + 1);
  return tidyLayout({ d, k: sideFirst(side) ? [id, rest] : [rest, id], z: sideFirst(side) ? [share, 1 - share] : [1 - share, share] });
};
const layoutSwap = (n, a, b) => mapLeaves(n, (leaf) => leaf === a ? b : leaf === b ? a : leaf);
// Added without a place (Split, ⌘-click, Open beside): beside the last pane, or under the row it ends, as the old grid grew.
const layoutAdd = (n, id) => {
  if (!n) return id;
  if (leavesOf(n).includes(id)) return n;
  if (!isSplit(n)) return { d: "h", k: [n, id], z: even(2) };
  const last = leavesOf(n).pop();
  const holderOf = (node) => !isSplit(node) ? null : node.k.includes(last) ? node : node.k.map(holderOf).find(Boolean);
  const holder = holderOf(n);
  if (holder.d === "v") return layoutBeside(n, last, id, "right");
  const wrap = (node) => node === holder ? { d: "v", k: [node, id], z: even(2) } : isSplit(node) ? { ...node, k: node.k.map(wrap) } : node;
  return tidyLayout(wrap(n));
};
const parseTree = (text) => {
  let at = 0;
  const node = () => {
    const open = /^([hv])\(/.exec(text.slice(at));
    if (!open) { const id = /^[^(),]+/.exec(text.slice(at)); if (!id) throw new Error("layout"); at += id[0].length; return id[0]; }
    at += 2;
    const k = [node()];
    while (text[at] === ",") { at++; k.push(node()); }
    if (text[at++] !== ")" || k.length < 2) throw new Error("layout");
    return { d: open[1], k, z: even(k.length) };
  };
  const tree = node();
  if (at !== text.length) throw new Error("layout");
  return tree;
};
// Sizes are kept per layout: the shares of each split, in the order the splits are written.
const sizeLists = (n) => isSplit(n) ? [n.z, ...n.k.flatMap(sizeLists)] : [];
const keepSizes = (n) => {
  if (!isSplit(n)) return;
  const all = saved.get("layoutSizes", {}), key = layoutText(n);
  delete all[key];
  all[key] = sizeLists(n).map((z) => z.map((v) => Math.round(v * 1e4) / 1e4));
  const keys = Object.keys(all);
  keys.slice(0, Math.max(0, keys.length - 40)).forEach((old) => delete all[old]);
  saved.set("layoutSizes", all);
};
const withSizes = (n) => {
  const lists = saved.get("layoutSizes", {})[layoutText(n)];
  if (!lists) return n;
  let at = 0;
  const put = (node) => {
    if (!isSplit(node)) return node;
    const z = lists[at++];
    return { ...node, z: Array.isArray(z) && z.length === node.k.length && z.every((v) => v > 0) ? z : node.z, k: node.k.map(put) };
  };
  return put(n);
};
const readLayout = (text) => {
  let tree;
  try { tree = text.includes("(") ? parseTree(text) : legacyLayout([...new Set(text.split(",").filter(Boolean))].slice(0, MAX_PANES)); }
  catch { tree = legacyLayout([...new Set(text.split(/[(),]/).filter((part) => part && !/^[hv]$/.test(part)))].slice(0, MAX_PANES)); }
  const seen = new Set();
  tree = tidyLayout(mapLeaves(tree, (leaf) => seen.has(leaf) || seen.size >= MAX_PANES ? null : (seen.add(leaf), leaf)));
  return tree ? withSizes(tree) : null;
};
const layoutHash = (n) => { keepSizes(n); return `#/s/${layoutText(n)}`; };
const goLayout = (n) => n ? go(layoutHash(n)) : go("#/");
const route = () => {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "s" && parts[1]) { const layout = readLayout(parts[1]); if (layout) return { name: "session", ids: leavesOf(layout), layout }; }
  if (parts[0] === "p" && parts[1]) return { name: "project", project: parts[1], tab: parts[2] || "home", rest: parts.slice(3).join("/") };
  if (parts[0] === "new") return { name: "new" };
  if (parts[0] === "catcher") return { name: "catcher" };
  return { name: "now" };
};
// Hub-wide sessions belong to no project. They sit under one row of their own, which answers to project() like a project does.
const HUB = "@hub";
const hubProject = () => ({ name: HUB, display: "Hub sessions", hub: true, repos: [(S.hubwide || {}).folder || "~/agent-memory"], icon: null, setup: [], lessons: 0 });
const project = (name) => name === HUB ? hubProject() : S.projects.find((p) => p.name === name);
// Folders of projects: a way to sort them, kept on the server so every browser sees the same ones.
const groups = () => (S.groups && S.groups.folders) || [];
const groupOf = (name) => ((S.groups && S.groups.of) || {})[name] || null;
const changeGroups = guard(async (body, said) => { await api("/api/groups", body); await tick(); if (said) toast(said); });
const newFolder = guard(async (projects = []) => {
  const name = await askName({ title: "New folder", yes: "Create", placeholder: "Clients, Personal, Experiments…" });
  if (name) await changeGroups({ op: "create", name, projects }, projects.length ? `Moved to ${name}` : null);
});
const projectMenu = (anchor, p) => {
  const now = groupOf(p.name);
  popover(anchor, [
    { name: "New session", icon: "plus", run: () => newSession(p.name) },
    { group: "Folder" },
    ...groups().map((f) => ({ name: f.name, icon: "folder", on: now === f.id, run: () => { if (now !== f.id) changeGroups({ op: "move", project: p.name, id: f.id }, `Moved to ${f.name}`); } })),
    now ? { name: "Out of its folder", icon: "close", run: () => changeGroups({ op: "move", project: p.name, id: null }, "Out of its folder") } : null,
    { name: "New folder…", icon: "folderPlus", run: () => newFolder([p.name]) },
  ].filter(Boolean));
};
const folderMenu = (anchor, f) => {
  const at = groups().findIndex((x) => x.id === f.id), last = groups().length - 1;
  popover(anchor, [
    { name: "Rename…", icon: "gear", run: guard(async () => { const name = await askName({ title: "Rename folder", value: f.name, yes: "Rename" }); if (name && name !== f.name) await changeGroups({ op: "rename", id: f.id, name }); }) },
    at > 0 ? { name: "Move up", icon: "updown", run: () => changeGroups({ op: "shift", id: f.id, by: -1 }) } : null,
    at < last ? { name: "Move down", icon: "updown", run: () => changeGroups({ op: "shift", id: f.id, by: 1 }) } : null,
    { name: "Delete folder…", icon: "close", run: guard(async () => {
      const n = S.projects.filter((p) => groupOf(p.name) === f.id).length;
      const ok = await confirmStep({ title: `Delete the folder ${f.name}?`, body: n ? `Its ${n === 1 ? "project goes" : `${n} projects go`} back to the top of the list. No project, session or memory is touched.` : "It's empty. Nothing else changes.", yes: "Delete folder", no: "Keep it" });
      if (ok) await changeGroups({ op: "delete", id: f.id }, "Folder deleted");
    }) },
  ].filter(Boolean));
};
const session = (id) => S.sessions.find((s) => s.id === id);
// A proposal waits for its person from the moment a dream writes it until it is applied or dismissed: the kit's record says which.
const openReview = (p) => p.latest && p.latest.state === "open" && p.latest.total > 0;
const attention = (name) => S.sessions.filter((s) => s.state === "needs" && (!name || s.project === name)).length
  + S.projects.filter((p) => (!name || p.name === name) && openReview(p)).length;
const liveClaude = (name) => S.sessions.filter((s) => s.project === name && s.alive && s.kind === "claude");
const go = (hash) => { location.hash = hash; };

const crumbTo = (p) => h("a", { href: `#/p/${P(p.name)}` }, mark(p, 15), h("span", { class: "t", dir: "auto", textContent: p.display }));
const phone = matchMedia("(max-width: 760px)");
// The phone's keyboard covers the page from below: the app takes the height that's left, so a message box stays above it.
if (window.visualViewport) {
  const vv = window.visualViewport;
  const fitView = () => { document.documentElement.style.setProperty("--vvh", `${Math.round(vv.height)}px`); if (phone.matches && (window.scrollY || document.documentElement.scrollTop)) window.scrollTo(0, 0); };
  vv.addEventListener("resize", fitView);
  vv.addEventListener("scroll", fitView);
  fitView();
}
const sideOpen = () => document.body.classList.contains("side-open");
const syncSide = () => {
  side.inert = phone.matches && !sideOpen();
  const button = top_.querySelector(".menu-btn");
  if (button) button.setAttribute("aria-expanded", sideOpen() ? "true" : "false");
};
function setSide(open) {
  const was = sideOpen(), inside = side.contains(document.activeElement);
  document.body.classList.toggle("side-open", open);
  syncSide();
  if (open && !was) { const first = side.querySelector("a, button"); if (first) first.focus({ preventScroll: true }); }
  if (!open && was && inside) { const button = top_.querySelector(".menu-btn"); if (button) button.focus({ preventScroll: true }); }
}
function closeSide() { setSide(false); }
window.addEventListener("hashchange", () => { if (phone.matches && sideOpen()) closeSide(); });  // going back with the drawer open must not leave it over the next page

// ── Shell: the sidebar's width and its icon rail, kept per browser ──
const SIDE = { min: 180, max: 420, start: 240, rail: 48 };
const shell = { w: SIDE.start, rail: false, ...saved.get("shell", {}) };
const clampSide = (w) => Math.round(Math.min(SIDE.max, Math.max(SIDE.min, w)));
// A phone has its drawer instead, so the rail is a desktop thing only.
const railed = () => !phone.matches && !!shell.rail;
const sideEdge = h("div", { class: "side-edge", role: "separator", tabindex: 0, "aria-orientation": "vertical", "aria-label": "Resize the sidebar", "aria-controls": "side", "aria-valuemin": SIDE.min, "aria-valuemax": SIDE.max, title: "Drag to resize, double-click to reset" });
side.after(sideEdge);
const applyShell = () => {
  document.documentElement.style.setProperty("--side-w", `${railed() ? SIDE.rail : shell.w}px`);
  document.body.classList.toggle("rail", railed());
  sideEdge.setAttribute("aria-valuenow", railed() ? SIDE.rail : shell.w);
  sideEdge.setAttribute("aria-valuetext", railed() ? "Icons only" : `${shell.w} pixels`);
};
const keepShell = () => saved.set("shell", { w: shell.w, rail: !!shell.rail });
function setRail(on) {
  if (!!shell.rail === on) return;
  const inside = side.contains(document.activeElement);
  shell.rail = on;
  keepShell();
  applyShell();
  sideKey = "";
  drawSide();
  drawAlerts();
  if (inside) { const back = side.querySelector(".side-toggle"); if (back) back.focus({ preventScroll: true }); }
}
// One drag for every edge in the shell: a pointer capture, the edge's own size while it moves, and a save when it ends.
// Terminals refit by themselves once the size stops changing, so nothing here floods them.
const dragEdge = (handle, { start, move, end, reset, step }) => {
  handle.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    if (start) start();
    handle.setPointerCapture(e.pointerId);
    document.body.classList.add("dragging");
    const moved = (m) => move(m.clientX, m.clientY);
    handle.addEventListener("pointermove", moved);
    handle.addEventListener("lostpointercapture", () => { handle.removeEventListener("pointermove", moved); document.body.classList.remove("dragging"); end(); }, { once: true });
  });
  handle.addEventListener("dblclick", reset);
  handle.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); reset(); return; }
    const by = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -1, ArrowDown: 1 }[e.key];
    if (!by) return;
    e.preventDefault();
    step(by * 16);
  });
};
// Drag past the narrowest width and the sidebar folds to its rail; drag out of the rail and it opens again.
let widthBefore = SIDE.start;
dragEdge(sideEdge, {
  start: () => { widthBefore = shell.w; },
  move: (x) => {
    const w = x - side.getBoundingClientRect().left;
    if (w < SIDE.min - 48) { if (!shell.rail) { shell.w = widthBefore; setRail(true); } return; }
    shell.w = clampSide(w);
    if (shell.rail) setRail(false); else applyShell();
  },
  end: keepShell,
  reset: () => { shell.w = SIDE.start; keepShell(); if (shell.rail) setRail(false); else applyShell(); },
  step: (by) => { if (shell.rail) { if (by > 0) setRail(false); return; } if (shell.w + by < SIDE.min) { setRail(true); return; } shell.w = clampSide(shell.w + by); keepShell(); applyShell(); },
});
phone.addEventListener("change", () => { applyShell(); sideKey = ""; drawSide(); });
applyShell();

// ── The orb: the hub's status mark, a pixel cube (ui/orbs.js) ──
// An orb is kept while its state is, so a poll's redraw moves the same one into the new row instead of restarting it.
const orbsKept = new Map();
const orbOf = (key, state, size = 14) => {
  if (!window.hubOrb) return dot(state);  // the module loads after this script; hub-orbs-ready redraws with orbs
  const kept = orbsKept.get(key);
  if (kept && kept.state === state && kept.size === size && kept.el.isConnected) return kept.el;
  const el = window.hubOrb(state, { size, label: DOT_WORDS[state] || state });
  orbsKept.set(key, { state, size, el });
  return el;
};
const pruneOrbs = () => orbsKept.forEach((kept, key) => { if (!kept.el.isConnected) orbsKept.delete(key); });
// What a session's orb shows: the finer word for what a working Claude is doing, when the server has it.
const orbState = (s) => s.state === "working" ? (s.orb || "working") : s.state === "error" ? "error" : shownState(s);
// Line two of a session row: what it is doing or asking, in the state's colour. The orb already says which state.
const rowLine = (s) => {
  const state = shownState(s);
  if (state === "working") return s.activity ? [s.activity.tool, s.activity.target].filter(Boolean).join(" ") : oneLine(s.now);
  if (state === "needs") return oneLine(s.asking) || "Needs your input";
  if (state === "error") return oneLine(s.error) || "Stopped with an error";
  if (state === "finished") return oneLine(s.said) || "Done";
  if (state === "closing") return "Writing a handoff";
  if (state === "no-claude") return "Claude isn't running";
  return "";
};
// When the current turn began; only a working session has one, and only once the server says so.
const turnSince = (s) => s.state !== "working" ? null : (s.turn && s.turn.since) || (s.activity && s.activity.since) || null;
const elapsed = (from) => {
  const t = Math.max(0, Math.floor(Date.now() / 1000 - from));
  if (t < 60) return `${t}s`;
  if (t < 3600) return `${Math.floor(t / 60)}m ${String(t % 60).padStart(2, "0")}s`;
  return `${Math.floor(t / 3600)}h ${String(Math.floor(t / 60) % 60).padStart(2, "0")}m`;
};
const ticking = (from) => h("time", { class: "elapsed", "data-since": from, textContent: elapsed(from) });
// Every elapsed time ticks on its own, without a redraw.
setInterval(() => document.querySelectorAll("time[data-since]").forEach((el) => { const now = elapsed(Number(el.dataset.since)); if (el.textContent !== now) el.textContent = now; }), 1000);
const setTop = (crumbs, actions = [], noSeparators) => {
  const trail = [];
  crumbs.forEach((crumb, index) => { if (index && !noSeparators) trail.push(h("span", { class: "sep", textContent: "/" })); trail.push(crumb); });
  fill(top_,
    h("button", { class: "icon menu-btn", title: "Menu", "aria-expanded": sideOpen() ? "true" : "false", onclick: () => setSide(!sideOpen()) }, uiIcon("menu")),
    h("div", { class: "crumbs" }, trail),
    h("div", { class: "actions-top" }, actions));
};
const tail = (text) => h("h1", { class: "tail", dir: "auto", textContent: text });
// The page still has a name for the tab and for screen readers when something on screen already shows it.
const quietTail = (text) => h("h1", { class: "tail sr-only", dir: "auto", textContent: text });

let sideKey = "", sideEdit = {}, sideHash = "";
// The list scrolls; what waits for you, notifications and New project stay put beneath it.
const sideList = h("div", { class: "side-list" });
const sideWrap = h("div", { class: "side-wrap" }, sideList);
const alertsSay = h("div", { class: "sr-only", role: "status" });
const alertsList = h("div", { class: "alert-list" });
const alertsBox = h("div", { id: "alerts" }, alertsSay, alertsList);
const sideEnd = h("div", { class: "side-end" });
const sideFoot = h("div", { class: "side-foot" }, alertsBox, sideEnd);
side.append(sideWrap, sideFoot);
const markSideEdge = () => sideWrap.classList.toggle("more", sideList.scrollTop + sideList.clientHeight < sideList.scrollHeight - 1);
sideList.addEventListener("scroll", markSideEdge, { passive: true });
new ResizeObserver(markSideEdge).observe(sideList);
const expanded = () => saved.get("expanded", {});
const isOpen = (p, r) => { const v = expanded()[p.name]; return v === undefined ? r.project === p.name || S.sessions.some((s) => s.project === p.name && s.alive) || (r.name === "session" && r.ids.some((id) => (session(id) || {}).project === p.name)) : v; };
// Every row of the sidebar has the same two edges: its mark in a 15px slot at the row's inset, and its words after it.
const slot = (...kids) => h("span", { class: "slot", "aria-hidden": kids.some((k) => k && k.getAttribute && k.getAttribute("role") === "img") ? undefined : "true" }, kids);
const gone = (s) => (s.state === "closed" || s.state === "ended") && !s.alive;
// The Dream Catcher: pinned under Home, with its own mark. Its count is what its last run left for you; while it runs, its orb works.
const catcherShown = () => { const c = S.catcher || {}; return [c.phase, c.waiting, c.run]; };
const catcherLabel = () => { const c = S.catcher || {}; return c.phase === "running" ? "Dream Catcher, catching dreams now" : c.waiting ? `Dream Catcher, ${c.waiting} waiting on you` : "Dream Catcher"; };
const catcherRow = (r) => {
  const c = S.catcher || {}, on = r.name === "catcher";
  return h("a", { class: `nav catcher-nav ${on ? "on" : ""}`, href: "#/catcher", onclick: closeSide, "aria-current": on ? "page" : undefined, "data-key": "catcher", "aria-label": catcherLabel() },
    slot(uiIcon("catcher")), h("span", { class: "label", textContent: "Dream Catcher" }),
    c.phase === "running" ? h("span", { class: "state" }, orbOf("catcher", "working")) : c.waiting ? h("span", { class: "count", textContent: c.waiting }) : null);
};
// When a run is carried out, a notification says how much it left for you (if notifications are on and the app isn't in front).
let catcherSeen;
const noticeCatcher = () => {
  const c = S.catcher || {}, mark = c.phase === "settled" ? `${c.run}:${c.settled}` : "";
  if (catcherSeen !== undefined && mark && mark !== catcherSeen && notifyState() === "on" && (document.visibilityState !== "visible" || !document.hasFocus())) {
    const note = postNotification("Dream Catcher", { body: c.waiting ? `${c.waiting} ${c.waiting === 1 ? "thing waits" : "things wait"} for you` : "It decided everything. Nothing waits for you.", tag: "hub-catcher" });
    if (note) note.onclick = () => { note.close(); window.focus(); go("#/catcher"); };
  }
  if (mark || catcherSeen === undefined) catcherSeen = mark;
};
const projectOrb = (p, sessions) => attention(p.name) ? orbOf(`p:${p.name}`, "needs") : sessions.some((s) => s.state === "working") ? orbOf(`p:${p.name}`, "working") : p.dreaming ? orbOf(`p:${p.name}`, "dreaming") : null;
const drawSide = () => {
  if (sideEdit.kind === "rename" && side.querySelector(".side-input")) return;
  const r = route();
  const key = JSON.stringify([location.hash, hub.ready, hub.down, sideEdit, notifyState(), railed(), !!window.hubOrb, S.projects.map((p) => [p.name, p.display, p.icon, openReview(p), p.dreaming, p.needs]),
    S.sessions.map((s) => [s.id, s.title, s.state, s.alive, orbState(s), rowLine(s), turnSince(s)]), expanded(), iconStamp, S.groups, saved.get("foldersShut", {}), catcherShown()]);
  if (key === sideKey) return;
  sideKey = key;
  if (railed()) drawRail(r); else drawTree(r);
  pruneOrbs();
  markSideEdge();
  const input = sideList.querySelector(".side-input");
  if (input) { input.focus(); input.select(); }
};
const sideToggle = () => h("button", { class: "icon side-toggle", type: "button", title: railed() ? "Expand the sidebar (⌘B)" : "Collapse the sidebar (⌘B)", "aria-label": railed() ? "Expand the sidebar" : "Collapse the sidebar", "aria-expanded": railed() ? "false" : "true", "aria-controls": "side", "data-key": "side-toggle", onclick: () => setRail(!railed()) }, uiIcon("sidebar"));
function drawTree(r) {
  const count = attention();
  const projectNode = (p) => {
    const open = isOpen(p, r);
    const sessions = S.sessions.filter((s) => s.project === p.name);
    const activeHome = r.name === "project" && r.project === p.name && r.tab === "home";
    const heldInside = !open && r.name === "session" && r.ids.some((id) => (session(id) || {}).project === p.name);
    // Closed and ended sessions fold away under the running ones, and open by themselves when one of them is on screen.
    const live = sessions.filter((s) => !gone(s));
    const past = sessions.filter(gone).sort((a, b) => (b.closedAt || b.created) - (a.closedAt || a.created));
    const pastOpen = !!saved.get("closedOpen", {})[p.name] || (r.name === "session" && past.some((s) => r.ids.includes(s.id))) || past.some((s) => sideEdit.id === s.id);
    const pastWord = past.every((s) => s.state === "closed") ? "Closed" : past.some((s) => s.state === "closed") ? "Closed or ended" : "Ended";
    const sessionRow = (s) => {
      if (sideEdit.id === s.id) return renameRow(s);
      const shown = r.name === "session" && r.ids.includes(s.id);
      const addable = r.name === "session" && s.alive && !shown;
      const beside = () => { closeSide(); if (r.ids.length < MAX_PANES) goLayout(layoutAdd(r.layout, s.id)); else toast("Close a pane first"); };
      // A finished row keeps one line: what it said is on Home and in its pane. Live rows say what they're doing now.
      const line = gone(s) ? "" : rowLine(s), from = turnSince(s);
      return h("div", { class: `side-row ${shown ? "on" : ""} ${line || from ? "two" : ""}`, title: rowTip(s), "data-sid": s.id },
        h("a", { class: "nav session", href: `#/s/${s.id}`, "aria-current": shown ? "page" : undefined, "data-key": `s:${s.id}`, "data-drag-sid": s.id,
          oncontextmenu: (e) => { e.preventDefault(); sessionMenu(e.currentTarget, s); },
          onclick: (e) => { if ((e.metaKey || e.ctrlKey || e.shiftKey) && addable) { e.preventDefault(); beside(); } else if (shown && r.ids.length > 1 && !e.metaKey && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); closeSide(); pageKeys.jump(r.ids.indexOf(s.id)); } else closeSide(); } },
          slot(orbOf(`s:${s.id}`, orbState(s))),
          h("span", { class: "lines" }, h("span", { class: "label", dir: "auto", textContent: bareTitle(s) }),
            line || from ? h("span", { class: `sub st-${shownState(s)}` }, h("span", { class: "what", dir: "auto", textContent: line }), from ? ticking(from) : null) : null)),
        addable && r.ids.length < MAX_PANES ? h("button", { class: "hover-add", title: `Open ${s.title} beside`, "data-key": `beside:${s.id}`, onclick: beside }, uiIcon("split")) : null,
        h("button", { class: "hover-add more", title: `Actions for ${s.title}`, "aria-haspopup": "menu", "data-key": `more:${s.id}`, onclick: (e) => sessionMenu(e.currentTarget, s) }, uiIcon("dots")));
    };
    const toggle = () => { saved.set("expanded", { ...expanded(), [p.name]: !open }); sideKey = ""; drawSide(); };
    const menu = (anchor) => projectMenu(anchor, p);
    return h("div", { class: `side-group ${open && sessions.length ? "open" : ""} ${p.hub ? "hub-group" : ""}`, "data-project": p.name },
      h("div", { class: `side-row project ${activeHome || heldInside ? "on" : ""} ${!open && sessions.length ? "folded" : ""}`, draggable: !p.hub && !phone.matches ? "true" : undefined,
        ondragstart: p.hub ? undefined : (e) => { e.dataTransfer.setData("text/x-hub-project", p.name); e.dataTransfer.effectAllowed = "move"; } },
        h("a", { class: "nav", href: `#/p/${P(p.name)}`, onclick: closeSide, "aria-current": activeHome ? "page" : undefined, "data-key": `p:${p.name}`, oncontextmenu: p.hub ? undefined : (e) => { e.preventDefault(); menu(e.currentTarget); } },
          slot(p.hub ? uiIcon("hub") : mark(p, 15)), h("span", { class: "label", dir: "auto", textContent: p.display }), h("span", { class: "state" }, projectOrb(p, sessions))),
        p.hub ? null : h("button", { class: "hover-add more", title: `Actions for ${p.display}`, "aria-haspopup": "menu", "data-key": `pmore:${p.name}`, onclick: (e) => menu(e.currentTarget) }, uiIcon("dots")),
        h("button", { class: "hover-add", title: p.hub ? "New hub session: every project's memory, no permission prompts" : `New session in ${p.display}`, "data-key": `new:${p.name}`, onclick: () => newSession(p.name) }, uiIcon("plus")),
        sessions.length ? h("button", { class: `chev ${open ? "open" : ""}`, title: `${open ? "Collapse" : "Expand"} ${p.display}`, "aria-expanded": open ? "true" : "false", "data-key": `chev:${p.name}`, onclick: toggle }, svg(UI.chev)) : null),
      open && sessions.length ? h("div", { class: "side-sessions" }, live.map(sessionRow),
        past.length ? h("button", { class: "side-fold", type: "button", "aria-expanded": pastOpen ? "true" : "false", "data-key": `fold:${p.name}`,
          onclick: () => { saved.set("closedOpen", { ...saved.get("closedOpen", {}), [p.name]: !pastOpen }); sideKey = ""; drawSide(); const again = sideList.querySelector(`[data-key="fold:${CSS.escape(p.name)}"]`); if (again) again.focus({ preventScroll: true }); } },
          h("span", { class: `slot chev ${pastOpen ? "open" : ""}`, "aria-hidden": "true" }, svg(UI.chev)), h("span", { textContent: pastWord }), h("span", { class: "fold-n", textContent: past.length })) : null,
        past.length && pastOpen ? h("div", { class: "side-past" }, past.map(sessionRow)) : null) : null,
    );
  };
  // Folders first, in the order you put them, each with its projects; then the projects in no folder.
  const shut = saved.get("foldersShut", {});
  const folderNode = (f) => {
    const inside = S.projects.filter((p) => groupOf(p.name) === f.id);
    const holds = inside.some((p) => (r.project === p.name) || (r.name === "session" && r.ids.some((id) => (session(id) || {}).project === p.name)));
    const open = !shut[f.id] || holds;
    const waiting = inside.reduce((n, p) => n + attention(p.name), 0), working = S.sessions.some((s) => inside.some((p) => p.name === s.project) && s.state === "working");
    const toggle = () => { saved.set("foldersShut", { ...saved.get("foldersShut", {}), [f.id]: open }); sideKey = ""; drawSide(); };
    const drop = (e) => { const name = e.dataTransfer.getData("text/x-hub-project"); e.currentTarget.classList.remove("drop-on"); if (name) { e.preventDefault(); changeGroups({ op: "move", project: name, id: f.id }, `Moved to ${f.name}`); } };
    return h("div", { class: `side-folder ${open ? "open" : ""}`, "data-folder": f.id },
      h("div", { class: "side-row folder-row", ondragover: (e) => { if ([...e.dataTransfer.types].includes("text/x-hub-project")) { e.preventDefault(); e.currentTarget.classList.add("drop-on"); } }, ondragleave: (e) => e.currentTarget.classList.remove("drop-on"), ondrop: drop },
        h("button", { class: "nav folder-nav", type: "button", "aria-expanded": open ? "true" : "false", "data-key": `folder:${f.id}`, onclick: toggle, oncontextmenu: (e) => { e.preventDefault(); folderMenu(e.currentTarget, f); } },
          h("span", { class: `slot chev ${open ? "open" : ""}`, "aria-hidden": "true" }, svg(UI.chev)), h("span", { class: "label", dir: "auto", textContent: f.name }),
          !open && (waiting || working) ? h("span", { class: "state" }, rowOrb(waiting ? "needs" : "working")) : h("span", { class: "fold-n", textContent: inside.length })),
        h("button", { class: "hover-add more", title: `Actions for the folder ${f.name}`, "aria-haspopup": "menu", "data-key": `fmore:${f.id}`, onclick: (e) => folderMenu(e.currentTarget, f) }, uiIcon("dots"))),
      open ? h("div", { class: "folder-items" }, inside.length ? inside.map(projectNode) : h("div", { class: "side-none", textContent: phone.matches ? "Empty. Use a project's ⋯ to move it here." : "Empty. Drag a project here, or use its ⋯ menu." })) : null);
  };
  const loose = S.projects.filter((p) => !groupOf(p.name));
  const looseDrop = (e) => { const name = e.dataTransfer.getData("text/x-hub-project"); e.currentTarget.classList.remove("drop-on"); if (name && groupOf(name)) { e.preventDefault(); changeGroups({ op: "move", project: name, id: null }, "Out of its folder"); } };
  fill(sideList,
    h("div", { class: "brand" }, slot(h("i")), "Dream Hub"),
    h("a", { class: `nav ${r.name === "now" ? "on" : ""}`, href: "#/", onclick: closeSide, "aria-current": r.name === "now" ? "page" : undefined, "data-key": "home" }, slot(uiIcon("home")), h("span", { class: "label", textContent: "Home" }), count ? h("span", { class: "count", textContent: count }) : null),
    catcherRow(r),
    projectNode(hubProject()),
    h("div", { class: "side-title with-act", ondragover: (e) => { if ([...e.dataTransfer.types].includes("text/x-hub-project")) { e.preventDefault(); e.currentTarget.classList.add("drop-on"); } }, ondragleave: (e) => e.currentTarget.classList.remove("drop-on"), ondrop: looseDrop },
      h("span", { textContent: "Projects" }), h("button", { class: "side-title-act", type: "button", title: "New folder", "aria-label": "New folder", "data-key": "new-folder", onclick: () => newFolder() }, uiIcon("folderPlus"))),
    groups().map(folderNode),
    loose.map(projectNode),
    hub.ready && !S.projects.length ? h("div", { class: "side-none", textContent: "No projects yet" }) : null);
  fill(sideEnd, notifyRow(), h("div", { class: "side-row foot-row" },
    h("a", { class: `nav ${r.name === "new" ? "on" : ""}`, href: "#/new", onclick: closeSide, "aria-current": r.name === "new" ? "page" : undefined, "data-key": "new-project" }, slot(uiIcon("plus")), h("span", { class: "label", textContent: "New project" })),
    phone.matches ? null : sideToggle()));
}
// The rail keeps what you supervise: each project's mark and an orb for every session still running under it.
function drawRail(r) {
  const count = attention();
  const item = (attrs, label, ...kids) => h("a", { ...attrs, class: `nav rail-item ${attrs.class || ""}`, title: label, "aria-label": label, onclick: closeSide }, slot(...kids));
  fill(sideList,
    h("div", { class: "brand" }, slot(h("i")), h("span", { class: "sr-only", textContent: "Dream Hub" })),
    item({ href: "#/", class: r.name === "now" ? "on" : "", "aria-current": r.name === "now" ? "page" : undefined, "data-key": "home" }, count ? `Home, ${count} waiting on you` : "Home", uiIcon("home"), count ? h("span", { class: "rail-count", "aria-hidden": "true" }) : null),
    item({ href: "#/catcher", class: r.name === "catcher" ? "on" : "", "aria-current": r.name === "catcher" ? "page" : undefined, "data-key": "catcher" }, catcherLabel(), uiIcon("catcher"), (S.catcher || {}).waiting ? h("span", { class: "rail-count", "aria-hidden": "true" }) : null),
    [hubProject(), ...groups().flatMap((f) => S.projects.filter((p) => groupOf(p.name) === f.id)), ...S.projects.filter((p) => !groupOf(p.name))].map((p) => {
      const live = S.sessions.filter((s) => s.project === p.name && !gone(s));
      if (p.hub && !live.length && !(r.name === "project" && r.project === HUB)) return null;
      const activeHome = r.name === "project" && r.project === p.name;
      return h("div", { class: "side-group rail-group" },
        item({ href: `#/p/${P(p.name)}`, class: activeHome ? "on" : "", "aria-current": activeHome && r.tab === "home" ? "page" : undefined, "data-key": `p:${p.name}` }, p.display, p.hub ? uiIcon("hub") : mark(p, 15), attention(p.name) ? h("span", { class: "rail-count", "aria-hidden": "true" }) : null),
        live.map((s) => {
          const shown = r.name === "session" && r.ids.includes(s.id);
          const line = rowLine(s);
          return h("div", { class: `side-row ${shown ? "on" : ""}`, "data-sid": s.id },
            item({ href: `#/s/${s.id}`, class: "session", "aria-current": shown ? "page" : undefined, "data-key": `s:${s.id}` }, `${s.title}, ${DOT_WORDS[shownState(s)] || s.state}${line ? `: ${line}` : ""}`, orbOf(`s:${s.id}`, orbState(s))));
        }));
    }));
  fill(sideEnd, notifyRow(), h("a", { class: `nav rail-item ${r.name === "new" ? "on" : ""}`, href: "#/new", title: "New project", "aria-label": "New project", "aria-current": r.name === "new" ? "page" : undefined, "data-key": "new-project" }, slot(uiIcon("plus"))), sideToggle());
}

const carryNames = () => { // names used to live in this browser; each moves to the server once
  const names = Object.entries(saved.get("sessionNames", {}));
  if (!names.length) return;
  names.forEach(([id, title]) => {
    const s = session(id);
    const done = () => { const left = saved.get("sessionNames", {}); delete left[id]; saved.set("sessionNames", left); };
    if (!s) return done();
    s.title = title;
    api(`/api/sessions/${id}/rename`, { title }).then(done, () => {});
  });
};
const statusLine = (s) => s.state === "error" ? (s.error || "Something went wrong") : s.state === "working" ? `Working${s.now ? `: ${s.now}` : ""}` : s.state === "needs" ? (s.asking || "Needs your input") : s.state === "finished" ? `Done${s.said ? `: ${s.said}` : ""}` : s.state === "shell" ? "Terminal"
  : s.state === "closing" ? "Closing: tidying up and writing a handoff" : s.state === "closed" ? `Closed${s.note ? `: ${noteLine(s.note)}` : ""}` : s.alive ? "Claude isn't running. The terminal is still open." : "Ended";
// The first line of a handoff is what it finished: the line a row has room for.
const noteLine = (note) => oneLine((note || "").split("\n").find((line) => line.trim()) || "").replace(/^\**done:?\**\s*/i, "");
const canClose = (s) => s.kind === "claude" && s.state !== "closing" && s.state !== "closed";
const canResume = (s) => s.kind === "claude" && !s.alive && s.resumable;
const resumeSession = (s) => api(`/api/sessions/${s.id}/resume`, {}).then(() => { toast(`Resuming ${s.title}`); return tick(); });
// Closing keeps the conversation and ends the process. A handoff note, asked for first, is what you read when you come back.
// With uncommitted changes in a git folder it may also ask Claude to commit its own work first; the hub says what came of it when the close ends.
let closeOpen = false;
const closeSession = guard(async (s) => {
  if (closeOpen) return;
  closeOpen = true;
  let check;
  try { check = await api(`/api/sessions/${s.id}/closing`); } catch (error) { closeOpen = false; throw error; }
  const busy = check.working ? "Claude is working, so there's no time for a handoff. Close it when it stops to get one." : check.typed ? "Something is typed in this session. Send or clear it to get a handoff." : "";
  const live = check.alive && !busy;
  const box = h("input", { type: "checkbox", checked: live, disabled: !live });
  const canCommit = live && check.commit;
  const commitBox = h("input", { type: "checkbox", checked: canCommit, disabled: !canCommit });
  const hint = h("input", { type: "text", class: "name-input commit-hint", maxlength: 200, placeholder: "Message hint (optional)", "aria-label": "A hint for the commit message", disabled: !canCommit });
  const syncCommit = () => {
    commitBox.disabled = !canCommit || !box.checked;
    const on = !commitBox.disabled && commitBox.checked;
    hint.disabled = !on;
    hint.hidden = !canCommit;
    stayNote.textContent = on ? "Claude commits only the files it changed in this session, in the repo's own style. It never pushes, and anything it isn't sure of stays uncommitted." : check.changes === 1 ? "Closing doesn't commit it, and it stays where it is." : "Closing doesn't commit them, and they stay where they are.";
  };
  const stayNote = h("span");
  box.addEventListener("change", syncCommit);
  commitBox.addEventListener("change", syncCommit);
  const dialog = h("dialog", { class: "confirm close-sheet", "aria-label": `Close ${s.title}` });
  const stay = h("button", { type: "button", class: "btn", textContent: "Keep running", onclick: () => dialog.close() });
  const agree = h("button", { type: "button", class: "btn primary", textContent: "Close session" });
  agree.onclick = once("Closing…", async () => {
    const commit = !commitBox.disabled && commitBox.checked;
    watchClose(s.id);
    const done = await api(`/api/sessions/${s.id}/close`, { note: box.checked, commit, hint: commit ? hint.value.trim() : "" });
    dialog.close();
    if (done.closing) toast(done.commit ? "Committing, tidying up, then closing. You'll hear when it's done." : "Tidying up, then closing. You'll hear when it's done.");
    await tick();
  }, agree);
  hint.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); agree.click(); } });
  const files = check.files || [];
  const why = check.changes && !canCommit && live ? (check.noVcs ? "This folder is in the hub's no_vcs list, so Claude isn't asked to commit here." : check.commitWhy) : "";
  fill(dialog,
    h("h1", {}, "Close “", h("span", { dir: "auto", textContent: s.title }), "”?"),
    h("p", { class: "sheet-lead", textContent: "Claude stops and the conversation is kept. Read it here any time, or resume it where it left off." }),
    check.changes ? h("div", { class: "close-warn", role: "note" }, dot("needs"), h("div", { class: "close-warn-body" },
      h("p", {}, h("b", { textContent: `${check.changes} uncommitted ${check.changes === 1 ? "change" : "changes"}` }), ` in ${check.folder}. `, stayNote),
      files.length ? h("ul", { class: "close-files", "aria-label": "Uncommitted files" }, files.map((f) => h("li", { dir: "auto", title: f, textContent: f })),
        check.changes > files.length ? h("li", { class: "more", textContent: `and ${check.changes - files.length} more` }) : null) : null)) : null,
    check.alive ? h("label", { class: "check" }, box, h("span", { textContent: "Tidy up and write a handoff first" })) : null,
    check.alive && !busy ? h("p", { class: "close-hint", textContent: "Claude stops any servers it started and removes its test leftovers, then notes what's done, open and next." }) : null,
    canCommit ? h("label", { class: "check" }, commitBox, h("span", { textContent: "Commit them first" })) : null,
    canCommit ? h("div", { class: "close-hint" }, hint) : null,
    why ? h("p", { class: "close-hint", textContent: why }) : null,
    busy ? h("p", { class: "close-hint", textContent: busy }) : null,
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  syncCommit();
  dialog.addEventListener("close", () => { closeOpen = false; });
  sheet(dialog);
  stay.focus();
});
// A close that ends later (the handoff came, or the wait ran out) is told wherever you are: a toast, and a browser
// notification when the app isn't in front. Watched ids are kept in this browser, so a reload mid-close still hears it.
const closeWatch = () => saved.get("closeWatch", {});
const watchClose = (id) => saved.set("closeWatch", { ...closeWatch(), [id]: Date.now() });
const closedWords = (s) => {
  const r = s.closeResult || {}, folder = (s.repo || "").replace(/\/$/, "").split("/").pop();
  const commits = r.commits || [];
  const committed = commits.length ? `Committed ${commits[0].hash} “${commits[0].subject}”${commits.length > 1 ? ` and ${commits.length - 1} more` : ""}.` : r.commit ? "Nothing was committed." : "";
  const left = r.left ? `${r.left} uncommitted ${r.left === 1 ? "change" : "changes"} left${folder ? ` in ${folder}` : ""}.` : "";
  const handoff = r.commit && !r.handoff ? "No handoff came back." : "";
  return [committed, left, handoff].filter(Boolean).join(" ");
};
const noticeClosed = () => {
  const watch = closeWatch();
  let changed = false;
  S.sessions.forEach((s) => {
    if (s.state === "closing" && !(s.id in watch)) { watch[s.id] = Date.now(); changed = true; }
    if (s.state !== "closed" || !(s.id in watch)) return;
    delete watch[s.id]; changed = true;
    const words = closedWords(s);
    toast(`Closed “${bareTitle(s)}”. ${words || "The conversation is kept."}`, true);
    say(`${bareTitle(s)} has closed. ${words}`);
    if (notifyState() === "on" && (document.visibilityState !== "visible" || !document.hasFocus())) {
      const note = postNotification(`Closed: ${s.title}`, { body: words || "The conversation is kept.", tag: `hub-closed-${s.id}` });
      if (note) note.onclick = () => { note.close(); window.focus(); go(`#/s/${s.id}`); };
    }
  });
  // A session that went away, or a watch older than a day, is forgotten.
  Object.keys(watch).forEach((id) => { if (!session(id) || Date.now() - watch[id] > 864e5) { delete watch[id]; changed = true; } });
  if (changed) saved.set("closeWatch", watch);
};
// The name comes first: on a row, this is how a truncated one is read in full.
// A session's title starts with its project ("my-app · …"). Where the project is already said just before it (its
// heading in the sidebar, the crumb before it) the title leaves it out.
const bareTitle = (s) => {
  const p = project(s.project) || {};
  const lead = [p.display, s.project, s.project === HUB ? "Hub" : ""].filter(Boolean).find((n) => s.title.toLowerCase().startsWith(`${n.toLowerCase()} · `));
  return lead ? s.title.slice(lead.length + 3) : s.title;
};
const rowTip = (s) => statusLine(s) === s.title ? s.title : `${s.title}\n${statusLine(s)}`;
const backToRow = (id) => {
  const row = sideList.querySelector(`[data-sid="${id}"]`);
  if (row) { row.querySelector("a").focus({ preventScroll: true }); row.querySelector(".more").focus({ preventScroll: true }); }  // hidden until the row holds focus
};
const closeEdit = () => {
  const id = sideEdit.id;
  sideEdit = {}; sideKey = ""; drawSide();
  backToRow(id);
};
const startEdit = (s, kind) => {
  sideEdit = { id: s.id, kind }; sideKey = ""; drawSide();
};
const sessionMenu = (anchor, s) => popover(anchor, [
  { name: "Rename", run: () => startEdit(s, "rename") },
  canClose(s) && s.alive ? { name: "Close session", run: () => closeSession(s) } : null,
  canResume(s) ? { name: "Resume", run: guard(() => resumeSession(s)) } : null,
  { name: "Delete…", run: () => deleteSession(s) },
].filter(Boolean));
function renameRow(s) {
  const commit = (byKey) => {
    if (sideEdit.id !== s.id) return;
    const name = input.value.trim().replace(/\s+/g, " ").slice(0, 80);
    const live = session(s.id) || s;  // polls replaced S while this row was being edited
    if (name && name !== live.title) { live.title = name; api(`/api/sessions/${s.id}/rename`, { title: name }).catch((error) => { toast(error.known ? error.message : NO_ANSWER, true); tick(); }); }
    sideEdit = {}; sideKey = "";
    render();
    if (byKey) backToRow(s.id);
  };
  const input = h("input", { class: "side-input", dir: "auto", value: s.title, maxLength: 80, "aria-label": "Session name", onblur: () => commit(false), onkeydown: (e) => { if (e.key === "Enter") { e.preventDefault(); commit(true); } } });
  return h("div", { class: "side-row" }, h("div", { class: "nav session" }, slot(orbOf(`s:${s.id}`, orbState(s))), input));
}
// Deleting can't be resumed from, so the dialog says first what goes where, what stops, and what memory has of it.
let deleteOpen = false;
const deleteSession = guard(async (s) => {
  if (deleteOpen) return;
  deleteOpen = true;
  let check;
  try { check = await api(`/api/sessions/${s.id}/deleting`); } catch (error) { deleteOpen = false; throw error; }
  const claude = check.kind === "claude", kit = check.kit;
  const dialog = h("dialog", { class: "confirm delete-sheet", "aria-label": `Delete ${check.title}` });
  const stay = h("button", { type: "button", class: "btn", textContent: "Keep session", onclick: () => dialog.close() });
  const agree = h("button", { type: "button", class: "btn danger", textContent: "Delete session" });
  agree.onclick = once("Deleting…", async () => {
    const done = await api(`/api/sessions/${s.id}/delete`, {});
    dialog.close();
    const r = route();
    if (r.name === "session" && r.ids.includes(s.id)) {
      const rest = layoutWithout(r.layout, s.id);
      if (rest) goLayout(rest); else go(`#/p/${P(check.project)}`);
    }
    toast(`Deleted “${check.title}”${done.stopped ? " after stopping it" : ""}. ${done.moved.length ? `It's in the Trash, in ${done.trash.split("/").pop()}.` : "There was nothing to move to the Trash."}`);
    await tick();
  }, agree);
  const facts = [(project(check.project) || {}).display || check.project, check.last ? `last ran ${whenShort(check.last)}` : null,
    check.created ? `started ${whenShort(check.created)}` : null, check.size || null].filter(Boolean);
  const trashed = [claude ? (check.transcripts ? "its conversation" : check.record ? "the hub's copy of its conversation" : null) : null,
    check.uploads ? `${check.uploads} ${check.uploads === 1 ? "file" : "files"} you shared with it` : null].filter(Boolean);
  const note = (text, warn) => warn ? h("p", { class: "close-warn", role: "note" }, dot("needs"), h("span", { textContent: text })) : h("p", { class: "close-hint", textContent: text });
  const kitLine = !kit ? null : kit.read === "all" ? note(`The memory kit has read all of it: its last dream, on ${dayOf(kit.dreamed)}, covered this conversation.`)
    : kit.read === "part" ? note(`The memory kit's last dream, on ${dayOf(kit.dreamed)}, read it only up to then. What happened after that hasn't reached memory and will be lost to it.`, true)
    : kit.dreamed ? note(`No dream has read it yet (the last was on ${dayOf(kit.dreamed)}), so what it taught is lost to memory.`, true)
    : note("The memory kit has no record of a dream on this project, so nothing from this conversation is in memory. What it taught is lost to memory.", true);
  fill(dialog,
    h("h1", {}, "Delete “", h("span", { dir: "auto", textContent: check.title }), "”?"),
    h("div", { class: "sheet-facts" }, facts.map((f) => h("span", { textContent: f }))),
    check.closing ? note("It is closing now. Delete it once it has closed.", true) : null,
    check.alive ? note(claude ? `It is running now${check.working ? " and Claude is in the middle of a turn" : ""}. Deleting stops it first.` : "This terminal is running now. Deleting stops it first.", true) : null,
    h("p", { class: "sheet-lead", textContent: claude ? "You can't resume or read this conversation in the hub afterwards, and it leaves every list." : "It leaves every list in the hub." }),
    h("p", { class: "sheet-lead", textContent: trashed.length ? `To the Trash, in one folder: ${trashed.join(" and ")}. Finder can put it back until you empty the Trash.` : "Nothing of it needs to go to the Trash." }),
    kitLine,
    kit ? note(kit.archive ? `The kit's searchable copy in ${kit.archive} is kept. The kit removes it ${kit.keep_days} days after the session ended.` : "The kit has no searchable copy of it, so a search won't find it afterwards either.") : null,
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  agree.disabled = check.closing;
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => { deleteOpen = false; });
  sheet(dialog);
  stay.focus();
});

// ── Sessions waiting for you: a card in the app, and a browser notification when you are elsewhere ──
const notifyState = () => !("Notification" in window) ? "none" : Notification.permission === "granted" ? (saved.get("notify", true) ? "on" : "off") : Notification.permission;
const postNotification = (title, options) => { try { return new Notification(title, options); } catch { return null; } };
const toggleNotify = guard(async () => {
  if (Notification.permission === "denied") { toast("Allow notifications for this site in your browser settings"); return; }
  if (Notification.permission === "default") {
    const answer = await Notification.requestPermission();
    saved.set("notify", answer === "granted");
    if (answer === "granted") postNotification("Dream Hub", { body: "You'll hear from me when a session needs you." });
  } else saved.set("notify", !saved.get("notify", true));
  sideKey = "";
  drawSide();
});
const notifyRow = () => {
  const now = notifyState();
  const word = now === "on" ? "Notifications on" : "Turn on notifications";
  return now === "none" ? null : h("button", { type: "button", class: `nav notify ${railed() ? "rail-item" : ""}`, onclick: toggleNotify, title: railed() ? word : undefined, "aria-label": railed() ? word : undefined }, slot(uiIcon("bell")), railed() ? null : h("span", { class: "label", textContent: word }));
};
const alerts = { seen: null, dismissed: new Set(), native: new Map(), key: "" };
// You're watching a session when you're in its pane, or, on a phone, when it's the page in front of you.
const watching = (id) => (document.hasFocus() && !!(document.activeElement && document.activeElement.closest(`.pane[data-sid="${id}"]`)))
  || (phone.matches && document.visibilityState === "visible" && route().name === "session" && route().ids.includes(id));
const openWaiting = (id) => {
  window.focus();
  const r = route();
  if (r.name === "session" && r.ids.includes(id)) { pageKeys.jump(r.ids.indexOf(id)); return; }
  if (r.name === "session" && r.ids.length > 1 && r.ids.length < MAX_PANES) goLayout(layoutAdd(r.layout, id)); else go(`#/s/${id}`);
};
// The sidebar holds what's waiting; on a phone, or with the sidebar hidden, one bar under the top row does. Home has its own list.
const barred = () => phone.matches || railed();
const placeAlerts = () => {
  alertsBox.classList.toggle("alert-bar", barred());
  if (barred()) { if (alertsBox.previousElementSibling !== banner) banner.after(alertsBox); }
  else if (alertsBox.parentNode !== sideFoot) sideFoot.prepend(alertsBox);
};
const oneLine = (text) => (text || "").replace(/\s+/g, " ").trim();
// The dock takes what the window can spare: the list keeps a working height and the foot's two rows stay in reach.
const cardRoom = () => Math.max(0, Math.min(3, Math.floor((side.clientHeight - 8 - sideEnd.offsetHeight - 36 - 160) / 86)));
const drawAlerts = () => {
  placeAlerts();
  const waiting = S.sessions.filter((s) => s.state === "needs" && !alerts.dismissed.has(s.id) && !watching(s.id));
  const count = waiting.length;
  const line = count ? `${count} ${count === 1 ? "session needs" : "sessions need"} you` : "";
  if (alertsSay.textContent !== line) alertsSay.textContent = line;
  const onHome = route().name === "now";
  const cards = onHome ? [] : waiting.slice(0, barred() ? 1 : cardRoom());
  const more = onHome ? 0 : count - cards.length;
  const key = JSON.stringify([cards.map((s) => [s.id, s.title, s.asking]), more]);
  if (key === alerts.key) return;
  alerts.key = key;
  fill(alertsList, cards.map((s) => h("div", { class: "alert" },
    h("button", { class: "alert-open", "data-key": `alert:${s.id}`, title: s.asking || undefined, onclick: () => openWaiting(s.id) }, slot(orbOf(`a:${s.id}`, "needs")),
      h("span", { class: "alert-text" }, h("b", { dir: "auto", textContent: s.title || (project(s.project) || {}).display || s.project }), oneLine(s.asking) ? h("small", { dir: "auto", textContent: oneLine(s.asking) }) : h("small", {}, "Needs your input in ", nb((project(s.project) || {}).display || s.project)))),
    h("button", { class: "icon", title: "Dismiss", "data-key": `dismiss:${s.id}`, onclick: () => { alerts.dismissed.add(s.id); drawAlerts(); } }, uiIcon("close")))),
    more ? h("a", { class: "alert-more", href: "#/", textContent: `${more} more` }) : null);
};
const noticeNeeds = () => {
  const waiting = S.sessions.filter((s) => s.state === "needs");
  const now = new Set(waiting.map((s) => s.id));
  alerts.dismissed.forEach((id) => { if (!now.has(id)) alerts.dismissed.delete(id); });
  alerts.native.forEach((note, id) => { if (!now.has(id)) { note.close(); alerts.native.delete(id); } });
  if (alerts.seen && notifyState() === "on" && (document.visibilityState !== "visible" || !document.hasFocus())) {
    waiting.filter((s) => !alerts.seen.has(s.id)).forEach((s) => {
      const note = postNotification(s.title, { body: s.asking || `${(project(s.project) || {}).display || s.project} needs your input`, tag: `hub-${s.id}` });
      if (note) { note.onclick = () => { note.close(); openWaiting(s.id); }; alerts.native.set(s.id, note); }
    });
  }
  alerts.seen = now;
};
const titleNow = () => {
  const r = route(), p = r.project && project(r.project);
  const name = r.name === "session" ? (r.ids.length > 1 ? "Split" : (session(r.ids[0]) || {}).title || "Not found")
    : r.name === "new" ? "New project"
    : r.name === "catcher" ? "Dream Catcher"
    : r.name === "project" && p ? (r.tab === "home" ? p.display : `${{ memory: "Memory", dreams: "Dreams", new: "New session" }[r.tab]} · ${p.display}`)
    : "";
  const waiting = S.sessions.filter((s) => s.state === "needs").length, working = S.sessions.filter((s) => s.state === "working").length;
  // A tab is narrow and cut from the end, so the counts lead: what waits on you first, then what's at work.
  const counts = [waiting ? `${waiting} waiting` : "", working ? `${working} working` : ""].filter(Boolean).join(", ");
  document.title = `${counts ? `(${counts}) ` : ""}${name ? `${name} · ` : ""}Dream Hub`;
  drawFavicon(waiting ? "needs" : working ? "working" : "");
};
// The tab's icon carries the same news: a rose diamond when something waits on you, a jade square while any work runs.
const FAVICON = { "": "", needs: "%3Cpath d='M24 15l7 7-7 7-7-7z' fill='%23ff5c8a'/%3E", working: "%3Crect x='19' y='17' width='10' height='10' fill='%232dd4a0'/%3E" };
const faviconEl = document.querySelector("link[rel=icon]");
let faviconShown = null;
const drawFavicon = (state) => {
  if (!faviconEl || faviconShown === state) return;
  faviconShown = state;
  faviconEl.href = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%230b1020'/%3E%3Crect x='${state ? 7 : 12}' y='7' width='8' height='18' fill='%232f62f5'/%3E${FAVICON[state]}%3C/svg%3E`;
};
const refreshTips = () => side.querySelectorAll("[data-sid]").forEach((row) => { const s = session(row.dataset.sid); if (s) row.title = rowTip(s); });
document.getElementById("scrim").addEventListener("click", closeSide);
document.querySelector(".skip-link").addEventListener("click", (e) => { e.preventDefault(); view.focus(); });
phone.addEventListener("change", () => { syncSide(); drawAlerts(); });
window.addEventListener("resize", drawAlerts);
// The shown row is revealed once the dock has its final height, and only when there is data to find it in.
const revealRow = () => {
  if (!hub.ready || location.hash === sideHash) return;
  sideHash = location.hash;
  const row = sideList.querySelector(".side-row.on");
  if (row && !phone.matches) row.scrollIntoView({ block: "nearest" });
};

const show = (key, build) => {
  if (page.key === key) { page.update && page.update(); return; }
  page.leave && page.leave();
  page = { key, update: null, leave: null };
  pageKeys = {}; pageHints = []; navKey = "";
  drawn.delete(top_);
  fill(view);
  view.scrollTop = 0;
  build();
  if (!document.querySelector("dialog[open]") && !view.contains(document.activeElement) && !top_.contains(document.activeElement)) view.focus({ preventScroll: true });
};
const render = () => {
  drawSide();
  drawStatus();
  drawAlerts();
  titleNow();
  revealRow();
  if (!hub.ready) return;
  const r = route();
  if (r.name === "new") return show("new", pageNew);
  if (r.name === "catcher") return show("catcher", pageCatcher);
  if (r.name === "session") {
    const key = `s:${layoutText(r.layout)}`;
    if (page.key !== key && r.ids.every((id) => !session(id))) return show(`missing:${key}`, () => {
      setTop([tail("Not found")]);
      view.append(h("div", { class: "page narrow" }, h("div", { class: "empty-line retry-line" }, h("span", { textContent: "That session no longer exists." }), h("a", { class: "retry", href: "#/", textContent: "Go home" }))));
    });
    if (page.key !== key && page.key.startsWith("s:") && page.retarget) { page.key = key; page.retarget(r.layout); return; }
    return show(key, () => pageSession(r.layout));
  }
  if (r.name === "project" && r.project === HUB) return show(`newsession:${HUB}:${r.tab === "new" ? r.rest : ""}`, () => pageNewSession(HUB, r.tab === "new" ? r.rest : ""));
  if (r.name === "project" && project(r.project)) {
    if (r.tab === "new") return show(`newsession:${r.project}:${r.rest}`, () => pageNewSession(r.project, r.rest));
    if (r.tab === "memory") {
      const key = `memory:${r.project}:${r.rest}`;
      if (page.key !== key && page.retarget && page.key.startsWith(`memory:${r.project}:`)) { page.key = key; page.retarget(r.rest); return; }
      return show(key, () => pageMemory(r.project, r.rest));
    }
    if (r.tab === "dreams") return show(`dreams:${r.project}:${r.rest}`, () => pageDreams(r.project, r.rest));
    return show(`home:${r.project}`, () => pageHome(r.project));
  }
  if (r.name === "project") return show(`missing:${r.project}`, () => {
    setTop([tail("Not found")]);
    view.append(h("div", { class: "page narrow" }, h("div", { class: "empty-line retry-line" }, h("span", { textContent: `No project called ${r.project}.` }), h("a", { class: "retry", href: "#/", textContent: "Go home" }))));
  });
  show("now", pageNow);
};
// A click spanning a poll must land on the button it started on, so nothing is redrawn mid-press.
let pressing = false, pressedAt = 0, owed = false;
const held = () => pressing && Date.now() - pressedAt < 5000;
const settle = guard(async () => { carryNames(); noticeNeeds(); noticeClosed(); noticeCatcher(); render(); refreshTips(); });
const letGo = () => { pressing = false; if (owed) { owed = false; setTimeout(settle, 60); } };
window.addEventListener("pointerdown", () => { pressing = true; pressedAt = Date.now(); }, true);
["pointerup", "pointercancel"].forEach((name) => window.addEventListener(name, letGo, true));
window.addEventListener("blur", letGo);  // not capture: a press that moves focus out of a terminal or a field blurs that element, and only the window leaving ends the press
window.addEventListener("keydown", (e) => { if (e.key === " " && e.target.closest && e.target.closest("button")) { pressing = true; pressedAt = Date.now(); } }, true);
window.addEventListener("keyup", (e) => { if (e.key === " ") letGo(); }, true);
const setDown = (down) => {
  if (hub.down === down) return;
  hub.down = down;
  banner.hidden = !down;
  say(down ? "Dream Hub isn't answering. Retrying every 3 seconds." : "Connected");
  if (!hub.ready) fill(view);
  drawSide();
};
const tick = async () => {
  let state;
  try { state = await api("/api/state"); } catch { setDown(true); return; }
  S = state;
  hub.ready = true;
  setDown(false);
  // A page loaded from an earlier build of the hub shows things the new one no longer accepts: say so, once, and offer to reload.
  if (!hub.version) hub.version = state.version;
  else if (state.version && state.version !== hub.version && !hub.stale) { hub.stale = true; staleBanner.hidden = false; say("Dream Hub was updated. Reload to use the new version."); }
  if (peekOpen) peekOpen.draw();
  if (held()) { owed = true; return; }
  await settle();
};
// A draft never goes quietly: leaving a page that holds unsaved text asks first.
let shownHash = location.hash;
const askToLeave = async (target) => {
  const leave = await confirmStep({ title: "Discard your edits?", body: "What you changed in this file hasn't been saved.", yes: "Discard edits", no: "Keep editing" });
  if (!leave) { const box = view.querySelector("textarea.edit"); if (box) box.focus(); return; }
  page.dirty = null;
  go(target);
};
window.addEventListener("hashchange", () => {
  if (location.hash !== shownHash && page.dirty && page.dirty()) {
    const target = location.hash;
    history.replaceState(null, "", `${location.pathname}${location.search}${shownHash}`);
    askToLeave(target);
    return;
  }
  shownHash = location.hash;
  render();
});
window.addEventListener("beforeunload", (e) => { if (page.dirty && page.dirty()) { e.preventDefault(); e.returnValue = ""; } });

const openClaude = guard(async (name) => {
  const live = liveClaude(name);
  if (live.length) return go(`#/s/${live[0].id}`);
  const result = await api("/api/sessions", { project: name, tasks: [], isolate: false });
  await tick();
  go(`#/s/${result.ids[0]}`);
});

// ── Sessions as strips: state, what it's doing now, and a trace of every tool call ──
const MODES = [
  { id: "plan", name: "Plan", say: "Reads and proposes. Changes nothing until you approve." },
  { id: "manual", name: "Ask first", say: "Checks with you before edits and commands." },
  { id: "acceptEdits", name: "Accept edits", say: "Edits files freely and asks before commands." },
  { id: "auto", name: "Auto", say: "Works on its own. Risky actions are checked first." },
  { id: "bypassPermissions", name: "Skip permissions", say: "Never asks. Every edit and command just runs." },
];
// The model picker. Each id is a Claude Code --model alias and must be a key of MODELS in hub_data.py; change the
// names and lines here when the models change.
const MODELS = [
  { id: "opus", name: "Opus 5.5", say: "For complex work and everyday tasks" },
  { id: "fable", name: "Fable 5.2", say: "For your toughest challenges" },
  { id: "sonnet", name: "Sonnet 5.5", say: "Most efficient for simpler tasks" },
  { id: "haiku", name: "Haiku 5.5", say: "Fastest for quick answers" },
];
const EFFORTS = ["low", "medium", "high", "xhigh", "max"];
const modeName = (id) => (MODES.find((m) => m.id === id) || {}).name || "";
const modelName = (id) => (MODELS.find((m) => m.id === id) || {}).name || "";
const TRACE_WORDS = { r: "Read", "!": "Error", err: "Error", a: "Agent", x: "Run", e: "Edit", m: "Other" };
const traceTally = (list) => {
  const n = {};
  list.forEach((k) => { const word = TRACE_WORDS[k] || "Other"; n[word] = (n[word] || 0) + 1; });
  return `${list.length} tool ${list.length === 1 ? "call" : "calls"}: ${Object.entries(n).map(([word, c]) => `${c} ${word}`).join(", ")}`;
};
const traceBar = (list) => list && list.length ? h("span", { class: "trace", role: "img", "aria-label": traceTally(list), title: traceTally(list) }, list.map((kind) => h("i", { class: `k-${kind === "!" ? "err" : kind}` }))) : h("span", { class: "trace" });
const pips = (a) => a && a.total ? h("span", { class: "pips", title: `${a.total} ${a.total === 1 ? "subagent" : "subagents"}, ${a.running} running` }, Array.from({ length: Math.min(a.total, 8) }, (_, i) => h("i", { class: i < a.running ? "on" : "" }))) : null;
const pip = (kind) => h("span", { class: `pip ${kind}`, role: "img", "aria-label": kind === "memory" ? "Memory write" : "Commit" });
const strip = (s, showProject) => {
  const p = project(s.project);
  const said = s.state === "needs" ? oneLine(s.asking) || "Needs your input" : s.state === "ended" && s.alive ? "Claude isn't running" : s.state === "working" ? s.now || s.said || s.task
    : s.state === "closing" ? "Tidying up and writing a handoff" : s.state === "closed" ? noteLine(s.note) || s.said || s.task : s.said || s.task;
  const line = said && !said.startsWith((s.title || "").replace(/…$/, "")) ? said : "";
  return h("div", { class: "strip-wrap" },
    h("a", { class: "strip", href: `#/s/${s.id}`, "data-nav": s.id, "data-drag-sid": s.id },
      dot(shownState(s)),
      h("span", { class: "strip-main" }, h("span", { class: "t", dir: "auto", textContent: s.title }), line ? h("span", { class: "line", dir: "auto", title: line, textContent: line }) : null),
      s.kind === "claude" ? traceBar(s.trace) : h("span", { class: "trace" }),
      h("span", { class: "strip-facts" },
        pips(s.agents),
        showProject && p ? mark(p, 15) : null,
        s.kind === "claude" ? [h("span", { textContent: modeName(s.mode) }), h("span", { textContent: modelName(s.model) }), s.code ? h("span", { textContent: "Code Mode" }) : null] : s.title === "Terminal" ? null : h("span", { textContent: "Terminal" }),
        s.isolate ? h("span", { title: "Has its own worktree", class: "tree" }, svg(UI.branch)) : null,
        h("time", { textContent: ago(s.created) })),
      h("span"),
      s.agents && s.agents.doing && s.agents.doing.length ? h("span", { class: "strip-crew" }, s.agents.doing.map((what) => h("div", {}, h("i"), what))) : null),
    s.phone ? h("button", { class: "icon strip-phone", title: "Open on phone", "data-key": `phone:${s.id}`, onclick: () => openExternal(s.phone) }, uiIcon("phone")) : null);
};
const legend = () => h("span", { class: "legend" }, [["r", "Read"], ["err", "Error"], ["a", "Agent"], ["x", "Run"], ["e", "Edit"], ["m", "Other"]].map(([kind, word]) => h("span", {}, h("i", { class: `k-${kind}` }), word)));

// A memory write that changed or removed a line says which, as the kit logged it: the line before, and the line after if there is one.
const logLine = (text) => (text || "").replace(/^- /, "");
const changeLine = (row) => row.was && row.now ? h("span", { class: "log-change", dir: "auto" }, h("del", { textContent: logLine(row.was) }), " → ", h("ins", { textContent: logLine(row.now) }))
  : row.was ? h("span", { class: "log-change", dir: "auto" }, "removed: ", h("del", { textContent: logLine(row.was) })) : null;

// ── Dashboard parts ──
const panel = (title, side, ...body) => h("section", { class: "panel" }, title || side ? h("header", {}, title ? h("h2", { textContent: title }) : h("span"), side) : null, body);
// Fixed order, checked for colour-blind separation: the marks' order never changes with the data.
const KINDS = [["r", "Read"], ["err", "Error"], ["a", "Agent"], ["x", "Run"], ["e", "Edit"], ["m", "Other tools"]];
const short = (day) => new Date(`${day}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
function barsChart(days) {
  const top = Math.max(1, ...days.map((d) => d.n));
  const total = days.reduce((sum, d) => sum + d.n, 0);
  return h("div", { class: "chart" },
    h("div", { class: "bars", role: "img", "aria-label": `${total} commits and memory writes in the last 14 days. ${days.filter((d) => d.n).map((d) => `${short(d.day)}: ${d.n}`).join(", ")}` },
      days.map((d, i) => h("div", { class: "bar-col", "data-tip": `${short(d.day)}: ${d.n}` }, h("i", { class: i === days.length - 1 ? "today" : "", style: `height:${d.n ? Math.max(4, 100 * d.n / top) : 0}%` })))),
    h("div", { class: "axis" }, h("span", { textContent: short(days[0].day) }), h("span", { textContent: `Peak ${top}` }), h("span", { textContent: "Today" })));
}
function toolMix(sessions) {
  const totals = {};
  sessions.forEach((s) => Object.entries(s.tally || {}).forEach(([k, n]) => { const key = k === "!" ? "err" : k; totals[key] = (totals[key] || 0) + n; }));
  const all = Object.values(totals).reduce((a, b) => a + b, 0);
  if (!all) return null;
  const present = KINDS.filter(([k]) => totals[k]);
  return h("div", { class: "chart" },
    h("div", { class: "mix", role: "img", "aria-label": present.map(([k, word]) => `${word} ${totals[k]}`).join(", ") }, present.map(([k, word]) => h("i", { class: `k-${k}`, style: `flex:${totals[k]} 0 2px`, "data-tip": `${word}: ${totals[k]}` }))),
    h("div", { class: "mix-rows" }, present.map(([k, word]) => h("div", {}, h("i", { class: `k-${k}` }), h("span", { textContent: word }), h("b", { textContent: totals[k] }), h("small", { textContent: `${Math.round(100 * totals[k] / all)}%` })))));
}
const dashTop = (crumbs, actions) => setTop(crumbs, actions, true);

// ── D: pages ──
// The cube where it is ready, the old dot until the module has loaded; pages redraw once it has.
let orbsReady = !!window.hubOrb;
window.addEventListener("hub-orbs-ready", () => { orbsReady = true; if (page.update) page.update(); });
const rowOrb = (state, size = 14) => h("span", { class: `row-orb s-${state}`, role: "img", "aria-label": DOT_WORDS[state] || state },
  window.hubOrb ? window.hubOrb(state, { size, label: false }) : dot(state));
const ROW_ORB = 16;  // the queue's two-line rows
// A finished turn or a closed session is read once you open it, in this browser. What it said is part of the mark,
// so the next turn that finishes is unread again.
const READ_KEY = "hub.read";
const DONE_FOR = 86400;  // a closed session stays in Done for a day
const isDone = (s) => s.state === "finished" || (s.state === "closed" && !!s.closedAt && Date.now() / 1000 - s.closedAt < DONE_FOR);
const readMark = (s) => `${s.state}:${s.said || s.note || ""}`.slice(0, 200);
const isRead = (s) => saved.get(READ_KEY, {})[s.id] === readMark(s);
const setRead = (ids, on) => {
  const marks = saved.get(READ_KEY, {});
  ids.forEach((id) => { const s = session(id); if (s && on) marks[id] = readMark(s); else delete marks[id]; });
  if (hub.ready) Object.keys(marks).forEach((id) => { if (!session(id)) delete marks[id]; });
  saved.set(READ_KEY, marks);
};
const sessionIds = (url) => { const m = (url || "").match(/#\/s\/([^/?]+)/); return m ? decodeURIComponent(m[1]).split(",") : []; };
// Opening a session reads it; so does leaving it, for a turn that finished while you watched.
window.addEventListener("hashchange", (e) => {
  const ids = [...sessionIds(e.oldURL), ...sessionIds(e.newURL)].filter((id) => { const s = session(id); return s && isDone(s); });
  if (ids.length) setRead(ids, true);
});
// Activity: a dream writes one log row per item. Consecutive rows of one dream fold into one line you can open.
const DREAM_ROW = /^dream (\S+) item (\d+): ([\s\S]*)$/;
const feedOpen = new Set();
const feedTail = (a, showProject) => { const p = showProject && project(a.project); return [showProject ? (p ? mark(p, 15) : h("span")) : h("span", { class: "s", textContent: a.who }), h("time", { textContent: ago(a.at) })]; };
const feed = (rows, showProject) => {
  const out = [];
  for (let i = 0; i < rows.length;) {
    const first = rows[i], m = first.kind === "memory" && first.text.match(DREAM_ROW);
    let j = i + 1;
    if (m) while (j < rows.length && rows[j].kind === "memory" && rows[j].who === first.who && rows[j].project === first.project && (rows[j].text.match(DREAM_ROW) || [])[1] === m[1]) j++;
    if (m && j - i > 1) {
      const group = rows.slice(i, j), key = `${first.project || ""}:${m[1]}:${first.who}`;
      out.push(h("details", { class: "feed-group", open: feedOpen.has(key), ontoggle: (e) => { if (e.currentTarget.open) feedOpen.add(key); else feedOpen.delete(key); } },
        h("summary", { class: "item" }, pip("memory"), h("span", { class: "t" }, h("span", { textContent: `Dream ${m[1]}` }), h("span", { class: "n", textContent: `${group.length} items` }), h("span", { class: "chev-s" }, svg(UI.chev))), feedTail(first, showProject)),
        h("div", { class: "feed-items" }, group.map((a) => { const [, , n, rest] = a.text.match(DREAM_ROW); return h("div", { class: "item" }, h("span", { class: "n", textContent: n }), h("span", { class: "t" }, rest, changeLine(a))); }))));
    } else out.push(h("div", { class: "item" }, pip(first.kind), h("span", { class: "t" }, first.text, changeLine(first)), feedTail(first, showProject)));
    i = j;
  }
  return h("div", { class: "feed" }, out);
};
const feedLegend = () => h("span", { class: "legend" }, h("span", {}, h("i", { class: "pip commit" }), "Commit"), h("span", {}, h("i", { class: "pip memory" }), "Memory write"));
// A project's three places, as tabs in the top bar. Each says its one fact: how many sessions are open, how many
// lessons memory holds, and how many things in Dreams wait for you.
const projectTabs = (p, at) => {
  const open = S.sessions.filter((s) => s.project === p.name && s.alive).length;
  const asking = S.sessions.some((s) => s.project === p.name && s.state === "needs");
  const dreamsWait = (p.needs || 0) + (openReview(p) ? 1 : 0) + ((p.waits && p.waits.you) || 0);
  const tab = (key, word, href, count, hot) => h("a", { class: `ptab ${key === at ? "on" : ""}`, href, "aria-current": key === at ? "page" : undefined, "data-key": `tab:${key}` },
    h("span", { textContent: word }), count ? h("b", { class: hot ? "hot" : "", textContent: String(count) }) : null);
  return h("nav", { class: "ptabs", "aria-label": p.display },
    tab("home", "Sessions", `#/p/${P(p.name)}`, open, asking),
    tab("memory", "Memory", `#/p/${P(p.name)}/memory`, p.lessons),
    tab("dreams", "Dreams", `#/p/${P(p.name)}/dreams`, dreamsWait, true));
};
const tabsKey = (p) => [p.display, p.icon, iconStamp, p.lessons, p.needs, openReview(p), p.waits, S.sessions.filter((s) => s.project === p.name).map((s) => [s.alive, s.state])];
// The top bar of a project's pages: its mark and name, then the tabs. On a phone the name gives way to the tabs.
const projectTop = (p, at, actions) => setTop([
  at === "home" ? h("h1", { class: "tail marked" }, mark(p, 20), h("span", { class: "t", dir: "auto", textContent: p.display }))
    : [h("a", { class: "crumb-home", href: `#/p/${P(p.name)}`, title: p.display }, mark(p, 20), h("span", { class: "t", dir: "auto", textContent: p.display })), quietTail(at === "memory" ? "Memory" : "Dreams")],
  projectTabs(p, at)], actions, true);

function pageNow() {
  const TABS = [["needs", "Needs you"], ["working", "Working"], ["done", "Done"]];
  let chosen = null, shown = "needs", rows = { needs: [], working: [], done: [] }, everything = false;
  const pick = (key) => { chosen = key; everything = false; navKey = ""; last = ""; draw(); const b = root.querySelector(`[data-key="tab:${key}"]`); if (b && root.contains(document.activeElement)) b.focus(); };
  const selected = () => { const el = navItems().find((e) => e.classList.contains("sel")); return el && rows[shown].find((r) => r.nav === el.dataset.nav); };
  const toggleRead = (row) => { if (!row || !row.sid) return; setRead([row.sid], !row.read); toast(row.read ? "Marked unread" : "Marked read"); last = ""; draw(); };
  bind(() => [["1 2 3", "queue"], ["j k", "move"], ["↵", "open"], ...(shown === "done" ? [["e", "read"]] : []), ["n", "new session"]], {
    n: () => newSession(), N: () => go("#/new"), 1: () => pick("needs"), 2: () => pick("working"), 3: () => pick("done"),
    e: () => { if (shown === "done") toggleRead(selected()); },
    " ": () => { const row = selected(); if (row && row.sid && window.hubPeek) window.hubPeek(row.sid); },
  });
  const root = h("div", { class: "dash home" });
  view.append(root);
  let last = "", data = null, failed = false;
  const card = (p) => {
    const open = liveClaude(p.name).length;
    const repos = p.repos.map((r) => r.split("/").pop()).filter((r) => r !== p.name);
    const fact = open ? `${open} open` : p.setup.length ? "Finish setting up" : !p.schedule ? null
      : weekly(p.schedule) ? `Dreams ${WEEKDAYS[p.schedule.weekday % 7].slice(0, 3)} ${clockHour(p.schedule.hour)}` : `Dreams daily ${clockHour(p.schedule.hour)}`;
    const state = attention(p.name) ? "needs" : S.sessions.some((s) => s.project === p.name && s.state === "working") ? "working" : p.dreaming ? "dreaming" : null;
    return h("a", { class: "card", href: `#/p/${P(p.name)}`, "data-nav": `p:${p.name}` },
      h("div", { class: "card-top" }, mark(p, 30), h("div", { class: "card-name" }, h("b", { dir: "auto", textContent: p.display }), repos.length ? h("span", { textContent: repos.join("  ") }) : null), state ? rowOrb(state) : null),
      h("div", { class: "card-line" }, h("span", { class: p.setup.length && !open ? "todo" : "", textContent: fact || "" }), h("span", { textContent: `${p.lessons} lessons` })));
  };
  // One row: what it is and the line under it, then whose and how long ago. Rows are links; Done rows also toggle read.
  const qRow = (row) => h("div", { class: `qrow ${row.read ? "read" : ""}`, "data-nav": row.nav, "data-drag-sid": row.sid && session(row.sid) ? row.sid : undefined, onclick: (e) => { if (!e.target.closest("a, button")) go(row.href); } },
    rowOrb(row.state, ROW_ORB),
    h("span", { class: "q-main" }, h("a", { class: "q-t", href: row.href, dir: "auto", textContent: row.title }), row.line ? h("span", { class: "q-line", dir: "auto", title: row.line, textContent: row.line }) : null),
    h("span", { class: "q-meta" }, row.p ? [mark(row.p, 15), h("span", { class: "q-p", dir: "auto", textContent: row.p.display })] : null, row.at ? h("time", { textContent: ago(row.at) }) : null),
    row.sid && shown === "done" ? h("button", { class: "q-act", type: "button", "data-key": `read:${row.sid}`, textContent: row.read ? "Mark unread" : "Mark read", onclick: () => toggleRead(row) }) : null);
  const queue = () => {
    const p = (name) => project(name);
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    rows.needs = [
      ...S.sessions.filter((s) => s.state === "needs" || s.state === "error").map((s) => ({ nav: s.id, sid: s.id, href: `#/s/${s.id}`, state: s.state, title: s.title, line: s.state === "error" ? s.error || "Stopped with an error" : oneLine(s.asking) || "Needs your input", p: p(s.project), at: s.activity && s.activity.since })),
      ...S.projects.filter(openReview).map((x) => ({ nav: `r:${x.name}`, href: `#/p/${P(x.name)}/dreams`, state: "needs", title: `Review ${plural(x.latest.changes, "memory change", "memory changes")}`, p: x, at: x.latest.written })),
      ...S.projects.filter((x) => x.needs).map((x) => ({ nav: `n:${x.name}`, href: `#/p/${P(x.name)}/dreams`, state: "needs", title: x.needs === 1 ? "1 thing a dream found" : `${x.needs} things dreams found`, line: "Approve a fix, reject it, or mark it done", p: x })),
      ...S.projects.filter((x) => x.waits && x.waits.you).map((x) => ({ nav: `w:${x.name}`, href: `#/p/${P(x.name)}/dreams`, state: "needs", title: `${plural(x.waits.you, "approved change waits", "approved changes wait")} for you`, line: "ORG.md or Steering, which only you apply", p: x })),
    ];
    rows.working = [
      ...S.sessions.filter((s) => s.state === "working" || s.state === "closing").sort((a, b) => b.created - a.created).map((s) => ({ nav: s.id, sid: s.id, href: `#/s/${s.id}`, state: s.state, title: s.title,
        line: s.state === "closing" ? "Tidying up and writing a handoff" : s.activity ? `${s.activity.tool} ${s.activity.target || ""}`.trim() : s.now || "Working", p: p(s.project), at: (s.turn && s.turn.since) || s.created })),
      ...S.projects.filter((x) => x.dreaming).map((x) => ({ nav: `d:${x.name}`, href: `#/p/${P(x.name)}/dreams`, state: "working", title: "Dreaming", line: x.batch ? `Reading ${plural(x.batch, "session", "sessions")}` : null, p: x })),
    ];
    rows.done = S.sessions.filter(isDone).map((s) => ({ nav: s.id, sid: s.id, href: `#/s/${s.id}`, state: s.state, title: s.title, line: s.state === "closed" ? noteLine(s.note) || "Closed" : s.said || "Done", p: p(s.project), at: s.closedAt, read: isRead(s) }))
      .sort((a, b) => (a.read ? 1 : 0) - (b.read ? 1 : 0) || (b.at || 0) - (a.at || 0));
    const counts = { needs: rows.needs.length, working: rows.working.length, done: rows.done.filter((r) => !r.read).length };
    // Whatever has something in it leads; a zero never does.
    shown = chosen || TABS.map(([k]) => k).find((k) => counts[k]) || "needs";
    const tabKeys = (e) => {
      const at = TABS.findIndex(([k]) => k === shown);
      const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (step) { e.preventDefault(); pick(TABS[(at + step + TABS.length) % TABS.length][0]); }
    };
    const empty = { needs: "Nothing needs you.", working: "Nothing is running.", done: "Nothing has finished today." };
    // On a phone a list stops at five, and says how many more there are.
    const cap = phone.matches && !everything && rows[shown].length > 6 ? 5 : Infinity;
    return h("section", { class: "panel triage" },
      h("div", { class: "qtabs", role: "tablist", "aria-label": "Queue", onkeydown: tabKeys }, TABS.map(([k, word]) => h("button", { type: "button", role: "tab", id: `qt-${k}`, "data-key": `tab:${k}`, class: `qtab ${k === shown ? "on" : ""}`,
        "aria-selected": k === shown ? "true" : "false", "aria-controls": "qpanel", tabIndex: k === shown ? 0 : -1, onclick: () => pick(k) },
        h("span", { textContent: word }), h("b", { class: counts[k] ? `n-${k}` : "zero", textContent: String(counts[k]) })))),
      h("div", { class: "qlist", id: "qpanel", role: "tabpanel", "aria-labelledby": `qt-${shown}` },
        rows[shown].length ? rows[shown].slice(0, cap).map(qRow) : h("div", { class: "empty-line", textContent: empty[shown] }),
        rows[shown].length > cap ? h("button", { type: "button", class: "disclose q-more", "aria-expanded": "false", onclick: () => { everything = true; last = ""; draw(); } }, h("span", { class: "chev" }, svg(UI.chev)), `${rows[shown].length - cap} more`) : null));
  };
  const draw = () => {
    if (differs(top_, "home")) dashTop([tail("Home")], [h("button", { class: "btn primary", textContent: "New session", onclick: () => newSession() })]);
    const key = JSON.stringify([S.projects, S.groups, S.sessions.map((s) => [s.id, s.title, s.state, s.asking, s.error, s.now, s.said, s.note, s.closedAt, s.activity, s.turn, s.tally, s.alive, isDone(s) && isRead(s)]), Math.floor(Date.now() / 60000), data, failed, iconStamp, orbsReady, chosen, everything, phone.matches]);
    if (key === last) return;
    last = key;
    const metrics = data ? Object.values(data.metrics) : [];
    const calls = metrics.reduce((n, m) => n + m.tool_calls, 0), errors = metrics.reduce((n, m) => n + m.tool_errors, 0);
    const health = [`${S.projects.reduce((n, p) => n + p.lessons, 0)} lessons`, calls ? `${(100 * errors / calls).toFixed(1)} errors per 100 tool calls` : null].filter(Boolean).join(" · ");
    fill(root,
      S.projects.length ? queue() : null,
      S.projects.length ? panel("Projects", h("span", { class: "head-fact", textContent: health }),
        groups().map((f) => { const inside = S.projects.filter((p) => groupOf(p.name) === f.id); return inside.length ? h("section", { class: "card-folder" }, h("h3", {}, uiIcon("folder"), h("span", { dir: "auto", textContent: f.name })), h("div", { class: "cards" }, inside.map(card))) : null; }),
        groups().some((f) => S.projects.some((p) => groupOf(p.name) === f.id)) && S.projects.some((p) => !groupOf(p.name)) ? h("h3", { class: "card-folder-loose" }, "Not in a folder") : null,
        h("div", { class: "cards" }, S.projects.filter((p) => !groupOf(p.name)).map(card)))
        : panel(null, null, h("div", { class: "empty-line first-run" }, h("span", { textContent: "No projects yet. A project keeps its memory and sessions together." }), h("a", { class: "btn primary", href: "#/new", textContent: "Create a project" }))),
      failed && !data ? retryLine("Charts and activity didn't load. Retrying in 20 seconds.", load) : null,
      h("div", { class: "panel-row" },
        data && data.pulse.length ? panel("Commits and memory writes, 14 days", null, barsChart(data.pulse)) : null,
        toolMix(S.sessions) ? panel("Tool calls", null, toolMix(S.sessions)) : null),
      data && data.activity.length ? panel("Activity", feedLegend(), feed(data.activity, true)) : null);
    markNav();
  };
  const load = async () => {
    try { data = await api("/api/home"); failed = false; } catch { failed = true; }
    if (!root.isConnected) return;  // the answer came after you left Home: its draw would retitle the next page
    if (held()) { owed = true; return; }
    draw();
  };
  draw();
  load();
  const timer = setInterval(load, 20000);
  page.update = draw;
  page.leave = () => clearInterval(timer);
}

// ── Project dashboard: agents lead, the prompt docks beneath ──
function pageHome(name) {
  const dash = h("div", { class: "dash" });
  const compose = composer({ name });
  const ideasBox = h("div", { class: "ideas" });
  view.append(h("div", { class: "workspace" }, dash, h("div", { class: "dock" }, ideasBox, compose.el)));
  const boardBox = h("section", { class: "panel board" });
  const setupBox = h("div", { class: "setup-box" });
  const rail = h("div", { class: "panel-row rail" });
  const mainRest = h("div", { class: "col-rest" });
  dash.append(setupBox, boardBox, rail, mainRest);
  let data = null, last = "", endedOpen = false, failed = false;
  bind([["j k", "move"], ["↵", "open"], ["i", "prompt"], ["n", "new session"], ["m", "memory"], ["d", "dreams"], [",", "settings"]], {
    i: () => compose.focus(), n: () => newSession(name), m: () => go(`#/p/${P(name)}/memory`), d: () => go(`#/p/${P(name)}/dreams`), ",": () => projectSettings(name),
  });

  const showAgent = (agent) => {
    const dialog = h("dialog", { class: "agent-sheet" });
    dialog.setAttribute("aria-label", agent.name);
    fill(dialog, h("h1", { textContent: agent.name }),
      agent.description ? h("p", { class: "sheet-lead", textContent: agent.description }) : null,
      h("div", { class: "sheet-facts" }, agent.model ? h("span", { textContent: agent.model }) : null, h("span", { textContent: agent.source === "personal" ? "Personal" : "This project" }), agent.tools ? h("span", { textContent: agent.tools }) : null),
      h("pre", { textContent: agent.body }),
      h("div", { class: "actions" }, h("span"), h("div", { class: "right" },
        h("button", { class: "btn", textContent: "Close", onclick: () => dialog.close() }),
        h("button", { class: "btn primary", textContent: "Start with this agent", onclick: () => { dialog.close(); compose.useAgent(agent.name); } }))));
    sheet(dialog);
  };

  const suggestions = () => {
    if (!data) return [];
    const ideas = [];
    for (const r of data.repos) {
      if (r.dirty) ideas.push({ text: `Review ${r.dirty} uncommitted in ${r.name}`, prompt: `Review the uncommitted changes in ${r.name}. Group them into sensible commits and tell me anything that looks wrong. Don't commit yet.`, mode: "plan" });
      else if (!["main", "master", "detached"].includes(r.branch)) ideas.push({ text: `Summarise ${r.branch}`, prompt: `Summarise what's on the ${r.branch} branch in ${r.name} compared with the main branch, and what's left before it can merge.`, mode: "plan" });
    }
    return ideas.slice(0, 2);
  };

  const newAgent = () => compose.fill("Create a new subagent in .claude/agents for this project. It should: ", "acceptEdits");
  const buildAgent = () => h("button", { class: "icon", title: "Build a new agent", "aria-label": "Build a new agent", onclick: newAgent }, uiIcon("plus"));
  const draw = () => {
    const p = project(name);
    if (!p) return;
    const sessions = S.sessions.filter((s) => s.project === name);
    const count = (state) => sessions.filter((s) => s.state === state).length;
    const working = count("working"), waiting = count("needs");
    if (differs(top_, "project", tabsKey(p))) projectTop(p, "home", [h("button", { class: "icon", title: "Project settings", "aria-label": "Project settings", onclick: () => projectSettings(name) }, uiIcon("gear"))]);
    const ages = sessions.map((s) => ({ ...s, age: Math.round((Date.now() / 1000 - s.created) / 60) }));
    const key = JSON.stringify([p, ages, data, iconStamp, endedOpen, failed]);
    if (key === last) return;
    last = key;
    const order = { needs: 0, working: 1, finished: 2, shell: 3 };
    const gone = (s) => (s.state === "ended" || s.state === "closed") && !s.alive;
    const active = sessions.filter((s) => !gone(s)).sort((a, b) => (order[a.state] ?? 3) - (order[b.state] ?? 3) || b.created - a.created);
    const ended = sessions.filter(gone).sort((a, b) => (b.closedAt || b.created) - (a.closedAt || a.created));
    const endedWord = ended.every((s) => s.state === "closed") ? "closed" : ended.some((s) => s.state === "closed") ? "closed or ended" : "ended";
    const metric = data && data.metrics[data.metrics.length - 1];
    if (differs(setupBox, p.setup)) fill(setupBox, p.setup.length ? panel("Finish setting up", null, p.setup.map((item, i) => h("a", { class: "notice", href: item.go === "sessions" || item.go === "commit" ? `#/p/${P(name)}` : `#/p/${P(name)}/${item.go}`, "data-nav": `setup:${i}`,
        onclick: item.go === "sessions" ? (e) => { e.preventDefault(); openClaude(name); } : item.go === "commit" ? guard(async (e) => { e.preventDefault(); await api(`/api/p/${P(name)}/commit-kit`, { repo: item.repo }); toast("Committed"); await tick(); }) : undefined }, dot(), h("span", { class: "t", textContent: item.text }), item.go === "commit" ? h("span", { class: "go", textContent: "Commit" }) : null))) : null);
    if (differs(boardBox, ages, endedOpen)) fill(boardBox,
      h("header", {}, h("h2", {}, "Sessions", working ? h("span", { class: "h-n", textContent: `${working} working` }) : null, waiting ? h("span", { class: "h-n need", textContent: `${waiting} ${waiting === 1 ? "needs" : "need"} you` }) : null), active.some((s) => s.trace && s.trace.length) ? legend() : null),
      active.map((s) => strip(s)),
      active.length ? null : h("div", { class: "empty-line", textContent: ended.length ? "Nothing is running." : "Nothing has run here yet. Describe a task below." }),
      ended.length ? h("button", { class: "disclose", "aria-expanded": endedOpen ? "true" : "false", onclick: () => { endedOpen = !endedOpen; last = ""; draw(); } }, h("span", { class: `chev ${endedOpen ? "open" : ""}` }, svg(UI.chev)), `${ended.length} ${endedWord}`) : null,
      endedOpen ? ended.map((s) => strip(s)) : null);
    if (differs(mainRest, data && data.activity, failed)) fill(mainRest,
      failed && !data ? retryLine("This project's details didn't load. Retrying in 20 seconds.", load) : null,
      data && data.activity.length ? panel("Activity", feedLegend(), feed(data.activity, false)) : null);
    if (differs(ideasBox, suggestions())) fill(ideasBox, suggestions().map((idea) => h("button", { class: "idea", onclick: () => compose.fill(idea.prompt, idea.mode) }, uiIcon("corner"), h("span", { textContent: idea.text }))));
    const schedule = p.schedule;
    const hour = schedule ? schedule.hour : null;  // none: the kit picks an hour free of the other stores' dreams and fixers
    const mix = toolMix(sessions);
    const errorRate = metric && metric.tool_calls ? h("span", { class: "head-fact", textContent: `${metric.errors_per_100_tool_calls} errors per 100 calls, last dream` }) : null;
    if (differs(rail, data, mix, schedule, dreamCheck(p.check))) fill(rail,
      data && data.pulse.length ? panel("Commits and memory writes, 14 days", null, barsChart(data.pulse)) : null,
      mix ? panel("Tool calls", errorRate, mix) : null,
      data ? panel("Agents you can run", data.agents.length ? buildAgent() : null,
        data.agents.length ? data.agents.map((a) => h("button", { class: "agent-row", onclick: () => showAgent(a) }, h("b", { textContent: a.name }), a.description ? h("span", { textContent: a.description }) : null))
          : h("div", { class: "empty-line retry-line" }, h("button", { class: "retry", textContent: "Build a new agent", onclick: newAgent }))) : null,
      panel(data ? "Repositories" : null, null, data ? data.repos.map((r) => h("div", { class: "p" }, h("span", { class: "k", textContent: r.name }), h("span", { class: "v" }, h("span", { class: "mono", textContent: r.branch }), r.dirty ? h("small", { textContent: `${r.dirty} changed` }) : null))) : null,
        h("div", { class: "p dream-row" }, h("span", { class: "k", textContent: dreamTiming(schedule, "Dreams ") }), h("button", { class: `switch ${schedule ? "on" : ""}`, title: "Automatic dreams", "aria-pressed": schedule ? "true" : "false", onclick: guard(async () => { await api(`/api/p/${P(name)}/schedule`, { on: !schedule, hour }); await tick(); }) })),
        dreamWhy(p.check)));
    markNav();
  };
  const load = async () => {
    try { data = await api(`/api/p/${P(name)}/home`); if (!held()) compose.agents(data.agents); failed = false; } catch { failed = true; }
    if (held()) { owed = true; return; }
    draw();
  };
  draw();
  load();
  const timer = setInterval(load, 20000);
  page.update = draw;
  page.leave = () => clearInterval(timer);
}

// ── Project settings ──
function projectSettings(name) {
  const p = project(name);
  const dialog = h("dialog");
  let icon = p.icon && p.icon.kind === "image" ? { ...p.icon } : { kind: "letter", value: "", color: "#8fb0ff" };
  const preview = h("span");
  const display = h("input", { type: "text", value: p.display, maxLength: 40, spellcheck: false });
  const paint = () => fill(preview, mark(p, 45, icon));
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", style: "display:none", onchange: guard(async () => {
    if (!file.files[0]) return;
    await upload(`/api/p/${P(name)}/icon`, file.files[0]);
    iconStamp = Date.now();
    icon = { kind: "image", value: "", color: "#8fb0ff" };
    paint();
  }) });
  const saveBtn = h("button", { type: "button", class: "btn primary", textContent: "Save", onclick: () => save() });
  const save = once("Saving…", async () => { await api(`/api/p/${P(name)}/profile`, { display: display.value, icon }); dialog.close(); await tick(); }, saveBtn);
  display.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } });
  fill(dialog, h("h1", { textContent: "Project settings" }),
    h("div", { class: "identity" }, preview, h("label", { class: "field" }, h("span", { textContent: "Name" }), display)),
    h("div", { class: "icon-extra" }, h("button", { type: "button", class: "btn", textContent: "Upload image", onclick: () => file.click() }), h("button", { type: "button", class: "btn", textContent: "Use generated glyph", onclick: () => { icon = { kind: "letter", value: "", color: "#8fb0ff" }; paint(); } }), file),
    h("div", { class: "actions" }, h("span", { class: "mono quiet", textContent: name }), h("div", { class: "right" },
      h("button", { type: "button", class: "btn", textContent: "Cancel", onclick: () => dialog.close() }),
      saveBtn)));
  dialog.setAttribute("aria-label", "Project settings");
  paint();
  sheet(dialog);
}

// Every modal: opens, names itself, and hands a visible error back to the page as it closes.
function sheet(dialog) {
  dialog.addEventListener("close", () => { const hadToast = dialog.contains(toastEl); if (hadToast) document.body.append(toastEl); dialog.remove(); if (hadToast) placeToast(); });
  document.body.append(dialog);
  dialog.showModal();
}

// ── Small menus: mode, model, agent ──
function popover(anchor, items) {
  const rect = anchor.getBoundingClientRect();
  const above = window.innerHeight - rect.bottom < 280;
  const home = anchor.closest("[data-sid], #top, #side, #view") || document.body;
  const anchorSpot = spotIn(home) || { key: anchor.dataset.key, kind: tagKind(anchor), index: [...home.querySelectorAll(SPOTS)].filter((el) => tagKind(el) === tagKind(anchor)).indexOf(anchor) };
  const row = anchor.closest(".side-row");
  if (row) row.classList.add("menu-open");
  const close = () => { popup.remove(); document.removeEventListener("mousedown", away, true); if (anchor.isConnected) anchor.focus(); else returnTo(home, anchorSpot); if (row) row.classList.remove("menu-open"); };
  const away = (e) => { if (!popup.contains(e.target)) close(); };
  const popup = h("div", { class: "popup menu", role: "menu", "aria-label": anchor.title || anchor.textContent, style: `${above ? `bottom:${window.innerHeight - rect.top + 6}px` : `top:${rect.bottom + 6}px`};left:${Math.max(8, Math.min(rect.left, window.innerWidth - 320))}px`,
    onkeydown: (e) => {
      const rows = [...popup.querySelectorAll("button")];
      const at = rows.indexOf(document.activeElement);
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
      if (e.key === "Tab") close();
      if (e.key === "ArrowDown") { e.preventDefault(); rows[(at + 1) % rows.length].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); rows[(at - 1 + rows.length) % rows.length].focus(); }
    } },
    items.map((item) => item.group ? h("div", { class: "menu-group", textContent: item.group }) : h("button", { role: "on" in item ? "menuitemradio" : "menuitem", "aria-checked": "on" in item ? (item.on ? "true" : "false") : undefined, class: item.on ? "on" : "", onclick: () => { close(); item.run(); } },
      item.dot ? dot(item.dot) : item.icon ? uiIcon(item.icon) : null,
      h("span", { class: "menu-text" }, h("b", { dir: "auto", textContent: item.name }), item.say ? h("small", { textContent: item.say }) : null), item.on ? svg(UI.check) : null)));
  (anchor.closest("dialog") || document.body).append(popup);
  document.addEventListener("mousedown", away, true);
  const firstRow = popup.querySelector("button.on") || popup.querySelector("button");
  if (firstRow) firstRow.focus(); else popup.tabIndex = -1, popup.focus();
}
const pill = (text, title, run) => h("button", { type: "button", class: "pill", title, "aria-haspopup": "menu", onclick: (e) => run(e.currentTarget) }, h("span", { textContent: text }), svg(UI.updown));

// ── Composer: the same object on a project's page and on New session ──
let carried = null;
const READS_LIKE_A_QUESTION = /^(plan|how|why|what|review|audit|investigate|explain|compare|should|research|look into)\b/i;
function composer({ name, full, splitWith }) {
  const key = `prefs:${name}`;
  const prefs = { mode: "auto", model: "opus", effort: "", code: false, ...saved.get(key, {}), agent: "" };
  const keep = () => saved.set(key, { mode: prefs.mode, model: prefs.model, effort: prefs.effort, code: prefs.code });
  const p = project(name);
  let agents = [], shell = false, touched = false, isolate = false, skipHint = false, repo = p.repos[0], startError = "";
  // What you've typed stays with the project until it's started. The dock shows the first task and holds on to the rest.
  const draftKey = `draft:${name}`, later = [];
  let offered = "";  // the last idea placed in the box: replacing it loses nothing you typed
  const keepDraft = () => { const texts = [...boxes.map((b) => b.value), ...later]; saved.set(draftKey, texts.some((t) => t.trim()) ? texts : null); };

  const area = () => {
    const el = h("textarea", { rows: full ? 3 : 1, spellcheck: true, "aria-label": "Task for Claude", placeholder: full ? "Describe the task. Leave it empty to start and type in the session." : "What should Claude do?",
      oninput: () => { size(el); startError = ""; keepDraft(); paint(); } });
    return el;
  };
  const size = (el) => { el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 260)}px`; };
  const boxes = [area()];
  const prompts = h("div", { class: "prompts" });
  const toolbar = h("div", { class: "bar" });
  const choose = h("div", { class: "choose" });
  const note = h("div", { class: "note", "aria-live": "polite" });
  const preview = h("code", { class: "command" });
  const startBtn = h("button", { class: "btn primary start", onclick: () => start() }, h("span", { textContent: "Start" }), h("kbd", { textContent: "⌘↩" }));
  const el = h("div", { class: `composer ${full ? "full" : ""}`, onkeydown: (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); start(); } } }, h("div", { class: "field-box" }, prompts, full ? null : toolbar), note, full ? choose : null, full ? h("div", { class: "launch" }, preview, startBtn) : null);

  const tasks = () => boxes.map((b) => b.value.trim()).filter(Boolean);
  const busy = () => p.hub ? 0 : S.sessions.filter((s) => s.alive && s.kind === "claude" && s.repo === repo && !s.isolate && s.state === "working").length;
  const wantsTree = () => !shell && !p.hub && (touched ? isolate : tasks().length > 1);
  const codeMode = () => !shell && !p.hub && !!prefs.code;
  const repoName = () => repo.split("/").pop();
  const paintPrompts = () => fill(prompts, boxes.map((box, i) => { box.setAttribute("aria-label", boxes.length > 1 ? `Task for agent ${i + 1}` : "Task for Claude"); return boxes.length > 1 ? h("div", { class: "prompt-row" }, h("span", { class: "n", textContent: i + 1 }), box, h("button", { type: "button", class: "icon", title: "Remove this agent", onclick: () => { boxes.splice(i, 1); keepDraft(); paintPrompts(); paint(); boxes[Math.max(0, i - 1)].focus(); } }, uiIcon("close"))) : box; }));

  const modeMenu = (anchor) => popover(anchor, MODES.map((m) => ({ ...m, on: prefs.mode === m.id, run: () => { prefs.mode = m.id; keep(); paint(); } })));
  const modelMenu = (anchor) => popover(anchor, MODELS.map((m) => ({ ...m, on: prefs.model === m.id, run: () => { prefs.model = m.id; keep(); paint(); } })));
  const agentMenu = (anchor) => popover(anchor, [{ name: "Claude", say: "The main agent, with no special role", on: !prefs.agent, run: () => { prefs.agent = ""; paint(); } }, ...agents.map((a) => ({ name: a.name, say: a.description, on: prefs.agent === a.name, run: () => { prefs.agent = a.name; paint(); } }))]);
  const folderPill = () => p.repos.length > 1 ? pill(repoName(), "Folder", (anchor) => popover(anchor, p.repos.map((r) => ({ name: r.split("/").pop(), on: r === repo, run: () => { repo = r; paint(); } })))) : null;

  // Tiles and Effort are radio groups: one Tab stop, and arrows move the choice, as they do in any shell menu.
  const radioKeys = (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const box = e.currentTarget.parentNode, group = [...box.children], index = group.indexOf(e.currentTarget), place = group.length;
    const where = [...choose.querySelectorAll("[role=radiogroup]")].indexOf(box);
    group[(index + (["ArrowRight", "ArrowDown"].includes(e.key) ? 1 : place - 1)) % place].click();
    choose.querySelectorAll("[role=radiogroup]")[where].querySelector("[aria-checked=true]").focus();
  };
  const tile = (item, on, run) => h("button", { type: "button", class: `tile ${on ? "on" : ""}`, role: "radio", "aria-checked": on ? "true" : "false", tabIndex: on ? 0 : -1, onclick: run, onkeydown: radioKeys }, h("b", { textContent: item.name }), h("span", { textContent: item.say }));
  function paint() {
    const flags = [p.hub ? "--dangerously-skip-permissions" : `--permission-mode ${prefs.mode}`, `--model ${prefs.model}`, prefs.effort ? `--effort ${prefs.effort}` : null, prefs.agent ? `--agent ${prefs.agent}` : null].filter(Boolean).join(" ");
    preview.textContent = shell ? "zsh" : `${codeMode() ? "CLAUDE_CODE_EXPERIMENTAL_CODE_MODE=1 " : ""}claude ${flags}`;
    const first = boxes[0].value.trim();
    const working = busy();
    const waitingTasks = later.filter((t) => t.trim()).length;
    fill(note,
      startError ? h("span", { textContent: startError }) : !shell && working && !wantsTree() ? [h("span", { textContent: `${working} ${working === 1 ? "session is" : "sessions are"} already working in ${repoName()}.` }), h("button", { type: "button", textContent: "Give this one a worktree", onclick: () => { touched = true; isolate = true; paint(); } })]
      : !shell && !p.hub && !skipHint && prefs.mode !== "plan" && READS_LIKE_A_QUESTION.test(first) ? [h("span", { textContent: "This reads like a question. Plan keeps it read-only." }), h("button", { type: "button", textContent: "Use Plan", onclick: () => { prefs.mode = "plan"; keep(); paint(); } }), h("button", { type: "button", class: "dim", textContent: "Keep " + modeName(prefs.mode), onclick: () => { skipHint = true; paint(); } })]
      : null);
    if (!full) {
      fill(toolbar, pill(modeName(prefs.mode), "Mode", modeMenu), pill(modelName(prefs.model), "Model", modelMenu), agents.length ? pill(prefs.agent || "Claude", "Run as", agentMenu) : null, folderPill(),
        wantsTree() ? h("span", { class: "tree", title: "Gets its own worktree" }, svg(UI.branch)) : null,
        codeMode() ? h("span", { class: "code-on", title: "Starts in Code Mode" }, "Code Mode") : null,
        h("a", { class: "more", href: `#/p/${P(name)}/new`, title: "Several agents, effort and worktrees", onclick: () => { carried = { from: name, agent: prefs.agent, isolate, touched }; }, textContent: waitingTasks ? `${waitingTasks} more ${waitingTasks === 1 ? "task" : "tasks"}` : "More options" }), h("span", { class: "grow" }), startBtn);
      return;
    }
    fill(choose,
      shell ? null : [
        p.hub ? null : h("div", { class: "choice" }, h("h2", { textContent: "Mode" }), h("div", { class: "tiles modes", role: "radiogroup", "aria-label": "Mode" }, MODES.map((m) => tile(m, prefs.mode === m.id, () => { prefs.mode = m.id; keep(); paint(); })))),
        h("div", { class: "choice" }, h("h2", { textContent: "Model" }), h("div", { class: "tiles", role: "radiogroup", "aria-label": "Model" }, MODELS.map((m) => tile(m, prefs.model === m.id, () => { prefs.model = m.id; keep(); paint(); })))),
        h("div", { class: "choice row" },
          h("div", {}, h("h2", { textContent: "Effort" }), h("div", { class: "seg", role: "radiogroup", "aria-label": "Effort" }, [["", "Default"], ...EFFORTS.map((e) => [e, e === "xhigh" ? "Extra high" : e[0].toUpperCase() + e.slice(1)])].map(([id, text]) => h("button", { type: "button", class: prefs.effort === id ? "on" : "", role: "radio", "aria-checked": prefs.effort === id ? "true" : "false", tabIndex: prefs.effort === id ? 0 : -1, textContent: text, onclick: () => { prefs.effort = id; keep(); paint(); }, onkeydown: radioKeys })))),
          agents.length ? h("div", {}, h("h2", { textContent: "Run as" }), pill(prefs.agent || "Claude", "Run as", agentMenu)) : null,
          p.repos.length > 1 ? h("div", {}, h("h2", { textContent: "Folder" }), folderPill()) : null),
        p.hub ? null : h("div", { class: "choice extras" },
          boxes.length < 8 ? h("button", { type: "button", class: "quiet", onclick: () => { boxes.push(area()); paintPrompts(); paint(); boxes[boxes.length - 1].focus(); } }, uiIcon("plus"), "Add another agent") : null,
          h("label", { class: "check" }, h("input", { type: "checkbox", checked: wantsTree(), onchange: (e) => { touched = true; isolate = e.target.checked; paint(); } }), h("span", { textContent: boxes.length > 1 ? "Give each agent its own worktree" : "Give it its own worktree" })),
          h("label", { class: "check", title: "Experimental. Claude writes code that calls its tools. No phone link." }, h("input", { type: "checkbox", checked: codeMode(), onchange: (e) => { prefs.code = e.target.checked; keep(); paint(); } }), h("span", { textContent: "Code Mode" }))),
      ],
      p.hub ? null : h("div", { class: "choice extras end" }, h("button", { type: "button", class: "quiet", textContent: shell ? "Start a Claude session instead" : "Open a plain terminal instead", onclick: () => { shell = !shell; prompts.parentNode.style.display = shell ? "none" : ""; paint(); if (!shell) boxes[0].focus(); } })));
  }
  const start = once("Starting…", async () => {
    let result;
    try { result = await api("/api/sessions", { project: name, repo, tasks: shell ? [] : tasks(), isolate: wantsTree(), kind: shell ? "shell" : "claude", mode: prefs.mode, model: prefs.model, effort: prefs.effort, agent: prefs.agent, code: codeMode() }); }
    catch (error) { startError = error.known ? error.message : NO_ANSWER; paint(); boxes[0].focus(); return; }
    // Only what was started goes: tasks the dock is holding, or text a plain terminal didn't use, stay in the draft.
    const unsent = shell ? boxes.map((b) => b.value) : [...later];
    if (!shell) boxes.forEach((b) => { b.value = ""; });
    saved.set(draftKey, unsent.some((t) => t.trim()) ? unsent : null);
    await tick();
    // Started beside a split: the new sessions join it where Split would put them, up to four panes.
    // A pane's "Split right" or "Split down" holds the new one's place as "new".
    let layout = splitWith ? readLayout(splitWith) : null;
    if (layout) leavesOf(layout).filter((id) => id !== "new" && !session(id)).forEach((id) => { layout = layoutWithout(layout, id); });
    const extra = [];
    result.ids.forEach((id) => {
      if (layout && leavesOf(layout).includes("new")) layout = mapLeaves(layout, (leaf) => leaf === "new" ? id : leaf);
      else if (layout && leavesOf(layout).length >= MAX_PANES) extra.push(id);
      else layout = layoutAdd(layout, id);
    });
    goLayout(layout && layoutWithout(layout, "new"));
    if (extra.length) toast(`${extra.length} more in the sidebar`);
  }, startBtn);
  if (full && carried) {
    if (carried.texts) saved.set(draftKey, [...carried.texts, ...(saved.get(draftKey, null) || [])]);
    if (carried.agent && carried.from === name) prefs.agent = carried.agent;
    isolate = !!carried.isolate; touched = !!carried.touched;
    carried = null;
  }
  (saved.get(draftKey, null) || []).forEach((text, i) => {
    if (!full && i) { later.push(text); return; }
    if (!boxes[i]) boxes.push(area());
    boxes[i].value = text;
  });
  paintPrompts();
  paint();
  requestAnimationFrame(() => boxes.forEach((b) => { if (b.value) size(b); }));
  return {
    el,
    agents(list) { const changed = JSON.stringify(list) !== JSON.stringify(agents); agents = list; if (changed) paint(); },
    fill(text, mode) { const typed = boxes[0].value; if (typed.trim() && typed !== offered) later.unshift(typed); offered = text; boxes[0].value = text; keepDraft(); if (mode) { prefs.mode = mode; keep(); } size(boxes[0]); paint(); boxes[0].focus(); boxes[0].setSelectionRange(text.length, text.length); },
    useAgent(id) { prefs.agent = id; paint(); boxes[0].focus(); },
    focus() { boxes[0].focus(); size(boxes[0]); },
    handOver() { const texts = boxes.map((b) => b.value).filter((t) => t.trim()); carried = { texts: texts.length ? texts : null, isolate, touched }; saved.set(draftKey, null); },  // an agent belongs to its project, and an empty composer has nothing to carry
  };
}

// ── New session ──
function newSession(projectName, thenSplitWith) {
  if (!S.projects.length && projectName !== HUB) return toast("Create a project first.");
  const r = route();
  const name = projectName || (r.project && project(r.project) ? r.project : (S.sessions.find((s) => s.alive && project(s.project)) || { project: S.projects[0].name }).project);
  go(`#/p/${P(name)}/new${thenSplitWith ? `/${thenSplitWith}` : ""}`);
}
function pageNewSession(name, splitWith) {
  const p = project(name);
  const compose = composer({ name, full: true, splitWith });
  const chooser = p.hub ? h("h1", { class: "tail marked" }, slot(uiIcon("hub")), h("span", { class: "t", textContent: "Hub session" })) : S.projects.length > 1 ? h("button", { class: "pill big", title: "Project", "aria-haspopup": "menu", onclick: (e) => popover(e.currentTarget, S.projects.map((x) => ({ name: x.display, on: x.name === name, run: () => { if (x.name === name) return; compose.handOver(); go(`#/p/${P(x.name)}/new${splitWith ? `/${splitWith}` : ""}`); } }))) }, mark(p, 15), h("span", { class: "t", dir: "auto", textContent: p.display }), svg(UI.updown)) : crumbTo(p);
  setTop(p.hub ? [chooser] : [chooser, tail(splitWith ? "New session beside this one" : "New session")], [], true);
  bind([["⌘↩", "start"], ["esc", "leave the prompt"], ["i", "prompt"], ["tab", "choices"], ["← →", "change choice"]], { i: () => compose.focus() });
  const live = p.hub ? S.sessions.filter((s) => s.project === HUB && !gone(s)) : [];
  const root = h("div", { class: "page narrow" },
    p.hub ? h("div", { class: "hub-lead" },
      h("p", {}, "A Claude session that belongs to no project. It works on every project's memory store in ", h("code", { textContent: (S.hubwide || {}).stores || "~/agent-memory" }), ", so it can apply memory changes across all of them, and starts in your home folder."),
      h("p", { class: "hub-warn" }, h("b", { textContent: "Permissions are skipped." }), " It won't stop to ask before it edits a file or runs a command. It's told to write memory only through the kit's amk commands and never to unlock ORG.md. Say exactly what you want changed."),
      live.length ? h("div", { class: "hub-live" }, h("h2", { textContent: "Running now" }), live.map((s) => h("a", { class: "hub-run", href: `#/s/${s.id}` }, rowOrb(shownState(s)), h("span", { class: "t", dir: "auto", textContent: s.title }), h("time", { textContent: ago(s.created) })))) : null) : null,
    compose.el);
  view.append(root);
  compose.focus();
  if (!p.hub) api(`/api/p/${P(name)}/agents`).then((list) => compose.agents(list), () => {});  // without the list the composer just offers Claude
}

// ── Opening what a session shares ──
// One dark frame for everything a session shares: images get zoom, ←/→ and a filmstrip across the session's images;
// video, audio, PDFs and text sit in the same frame. Nothing from the web is loaded by the page itself: a link's card
// comes from the hub, fetched when the person points at the link or a chat shows its card (README, "The chat").
const fileUrl = (sid, path) => `/api/sessions/${sid}/file?path=${encodeURIComponent(path)}`;
const blobUrl = (sid, ref) => `/api/sessions/${sid}/blob?ref=${encodeURIComponent(ref)}`;
// A picture's small copy: `px` asks for a sharper one (320, 640 or 960 wide) where it's shown bigger. A picture a link
// names (`src`, through the hub's own /api/preview/image) has no small copy.
const thumbUrl = (sid, item, px) => item.src ? item.src : (item.blob ? `/api/sessions/${sid}/thumb?ref=${encodeURIComponent(item.blob)}` : `/api/sessions/${sid}/thumb?path=${encodeURIComponent(item.path)}`) + (px ? `&px=${px}` : "");
const EXT = { image: /\.(png|jpe?g|gif|webp|avif|svg)$/i, audio: /\.(mp3|m4a|wav|ogg|flac|aac)$/i, video: /\.(mp4|mov|webm)$/i, pdf: /\.pdf$/i };
const kindOf = (path) => Object.keys(EXT).find((k) => EXT[k].test(path)) || "text";
const openExternal = (url) => window.open(url, "_blank", "noopener,noreferrer");
const PV = {
  minus: '<path d="M3.5 8h9"/>', plus: '<path d="M8 3.5v9M3.5 8h9"/>', back: '<path d="m10 3-5 5 5 5"/>', on: '<path d="m6 3 5 5-5 5"/>',
  file: '<path d="M4 1.5h5l3 3v10H4z"/><path d="M9 1.5v3h3"/>', audio: '<path d="M6 12V3.5l7-1.5V10.5"/><circle cx="4.5" cy="12" r="1.5"/><circle cx="11.5" cy="10.5" r="1.5"/>',
  video: '<rect x="1.5" y="3.5" width="9" height="9"/><path d="m10.5 7 4-2.5v7l-4-2.5"/>', pdf: '<path d="M4 1.5h5l3 3v10H4z"/><path d="M9 1.5v3h3M6 9.5h4M6 11.5h3"/>',
  link: '<path d="M6.5 9.5 9.5 6.5"/><path d="M7.5 4.5 9 3a2.8 2.8 0 0 1 4 4l-1.5 1.5"/><path d="M8.5 11.5 7 13a2.8 2.8 0 0 1-4-4l1.5-1.5"/>',
};
const tidyPath = (text) => text.replace(/^file:\/\/(localhost)?/, "");
const shortPath = (path) => (path || "").replace(/^\/private\/tmp\/claude-\d+\/[^/]+\/[^/]+\//, "scratch/").replace(/^\/Users\/[^/]+/, "~");
const sizeWords = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
const clockOf = (date) => date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const whenShort = (seconds) => {
  if (!seconds) return "";
  const date = new Date(seconds * 1000), now = new Date(), day = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(now) - day(date)) / 86400000);
  if (days === 0) return clockOf(date);
  if (days === 1) return `Yesterday ${clockOf(date)}`;
  return date.getFullYear() === now.getFullYear() ? `${dayOf(seconds)} ${clockOf(date)}` : date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
};
const atOf = (item) => (item && item.at ? Date.parse(item.at) / 1000 : 0) || 0;
const factsKept = new Map();
const factsOf = (sid, path) => {
  const key = `${sid}\n${path}`, kept = factsKept.get(key);
  if (kept && Date.now() - kept.at < 30000) return kept.facts;
  const facts = api(`/api/sessions/${sid}/info?path=${encodeURIComponent(path)}`).catch(() => null);
  factsKept.set(key, { at: Date.now(), facts });
  return facts;
};
const sameFile = (item, sid, path, blob) => item.sid === sid && (blob ? item.blob === blob : !!item.path && (item.path === path || item.path.endsWith("/" + path.replace(/^(\.\/|~\/)/, ""))));
const checkFile = async (url) => {
  const response = await fetch(url, { headers: { Range: "bytes=0-0" } });
  if (!response.ok) throw known((await response.json().catch(() => ({}))).error || "That file can't be opened.");
};

// The frame: name and facts top left, the kind's own controls in the middle, open and close on the right.
function viewerFrame(label) {
  const name = h("b", { dir: "auto" }), meta = h("span", { class: "v-meta" });
  const middle = h("div", { class: "v-mid" });
  const external = h("a", { class: "icon", target: "_blank", rel: "noopener noreferrer", title: "Open in a new tab" }, uiIcon("external"));
  const stage = h("div", { class: "v-stage", tabindex: -1 });
  const dialog = h("dialog", { class: "preview viewer", "aria-label": label });
  const top = h("div", { class: "v-top" }, h("div", { class: "v-title" }, name, meta), middle,
    h("div", { class: "v-acts" }, external, h("button", { class: "icon", title: "Close", onclick: () => dialog.close() }, uiIcon("close"))));
  dialog.append(top, stage);
  return { dialog, name, meta, middle, external, stage };
}
const showFrame = (frame) => { sheet(frame.dialog); frame.stage.focus({ preventScroll: true }); };

const openPreview = guard(async ({ sid, path, blob, src, name, at, gallery, index }) => {
  if (document.querySelector("dialog.preview[open]")) return;
  path = path ? tidyPath(path) : path;
  const kind = blob || src ? "image" : kindOf(path);
  if (kind === "image") {
    if (!gallery) {
      const images = await api(`/api/sessions/${sid}/shared`).then((list) => list.filter((i) => i.kind === "image").map((i) => ({ ...i, sid })), () => []);
      index = images.findIndex((i) => sameFile(i, sid, path, blob));
      gallery = index >= 0 ? images : [{ sid, path, blob, name, at }, ...images];
      index = Math.max(0, index);
    }
    const first = gallery[index];
    await checkFile(first.src || (first.blob ? blobUrl(first.sid, first.blob) : fileUrl(first.sid, first.path)));
    return imageViewer(gallery, index);
  }
  const url = fileUrl(sid, path);
  const text = kind === "text" ? await api(`/api/sessions/${sid}/preview?path=${encodeURIComponent(path)}`) : (await checkFile(url), null);
  const title = name || path.split("/").pop();
  const frame = viewerFrame(title);
  frame.name.textContent = title;
  frame.dialog.classList.add(`is-${kind}`);
  frame.external.href = url;
  if (kind === "text") frame.external.remove();
  const body = kind === "video" ? h("video", { src: url, controls: true, autoplay: !reduced(), playsInline: true })
    : kind === "audio" ? h("div", { class: "v-audio" }, svg(PV.audio), h("audio", { src: url, controls: true, autoplay: !reduced() }))
    : kind === "pdf" ? h("iframe", { src: url, title })
    : textLines(text.text);
  frame.stage.append(body);
  const facts = await factsOf(sid, path);
  frame.meta.textContent = facts ? [facts.lines !== undefined ? `${facts.lines.toLocaleString("en-GB")} ${facts.lines === 1 ? "line" : "lines"}` : null, sizeWords(facts.size), whenShort(atOf({ at }) || facts.modified)].filter(Boolean).join(" · ") : whenShort(atOf({ at }));
  frame.meta.title = facts ? shortPath(facts.path) : "";
  frame.stage.addEventListener("click", (e) => { if (e.target === frame.stage) frame.dialog.close(); });
  showFrame(frame);
});
// Text with its line numbers, each line its own row so a wrapped line keeps one number.
const textLines = (text) => {
  const lines = text.replace(/\n$/, "").split("\n");
  const shown = lines.slice(0, 20000);
  return h("div", { class: "v-text" }, h("pre", { class: "v-lines", style: `--digits:${String(shown.length).length}` }, shown.map((line) => h("span", { textContent: line || " " }))),
    lines.length > shown.length ? h("div", { class: "empty-line", textContent: `${lines.length - shown.length} more lines aren't shown.` }) : null);
};

function imageViewer(gallery, start) {
  const frame = viewerFrame("Image");
  const { dialog, stage } = frame;
  const many = gallery.length > 1;
  let index = start, img = null, natural = [0, 0], scale = 1, fit = 1, tx = 0, ty = 0, token = 0;
  const pct = h("button", { class: "v-pct", type: "button", title: "Fit to the window (0). Actual size (1)", onclick: () => (scale > fit + 0.001 ? fitNow(true) : zoomTo(1, null, true)) });
  const zoomOut = h("button", { class: "icon", type: "button", title: "Zoom out (−)", onclick: () => zoomBy(1 / 1.5) }, svg(PV.minus));
  const zoomIn = h("button", { class: "icon", type: "button", title: "Zoom in (+)", onclick: () => zoomBy(1.5) }, svg(PV.plus));
  frame.middle.append(h("div", { class: "v-zoom", role: "group", "aria-label": "Zoom" }, zoomOut, pct, zoomIn));
  const prev = h("button", { class: "v-nav prev", type: "button", title: "Previous (←)", onclick: () => step(-1) }, svg(PV.back));
  const next = h("button", { class: "v-nav next", type: "button", title: "Next (→)", onclick: () => step(1) }, svg(PV.on));
  const canvas = h("div", { class: "v-canvas" });
  stage.append(canvas);
  if (many) stage.append(prev, next);
  const urlOf = (item) => item.src || (item.blob ? blobUrl(item.sid, item.blob) : fileUrl(item.sid, item.path));
  const strip = many ? h("div", { class: "v-strip", role: "toolbar", "aria-label": "Images in this session", "aria-orientation": "horizontal" },
    gallery.map((item, at) => h("button", { type: "button", class: "v-film", title: item.name, onclick: () => show(at) }, h("img", { src: thumbUrl(item.sid, item), alt: "", loading: "lazy", draggable: false })))) : null;
  if (strip) dialog.append(strip);

  const size = () => [canvas.clientWidth, canvas.clientHeight];
  const zoomed = () => scale > fit + 0.001;
  const clamp = () => {
    const [W, H] = size(), w = natural[0] * scale, hgt = natural[1] * scale;
    tx = w <= W ? (W - w) / 2 : Math.min(0, Math.max(W - w, tx));
    ty = hgt <= H ? (H - hgt) / 2 : Math.min(0, Math.max(H - hgt, ty));
  };
  const apply = (glide) => {
    if (!img) return;
    clamp();
    img.classList.toggle("glide", !!glide && !reduced());
    img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    img.classList.toggle("pixels", scale >= 2);
    stage.classList.toggle("zoomed", zoomed());
    pct.textContent = `${Math.round(scale * 100)}%`;
    zoomOut.disabled = !zoomed();
    zoomIn.disabled = scale >= 8;
  };
  const measure = () => { const [W, H] = size(); const room = phone.matches ? 0 : 48; fit = natural[0] ? Math.min(1, (W - room) / natural[0], (H - room) / natural[1]) : 1; };
  const fitNow = (glide) => { scale = fit; apply(glide); };
  const zoomTo = (target, at, glide) => {
    const [W, H] = size(), [px, py] = at || [W / 2, H / 2];
    const s = Math.min(8, Math.max(fit, target));
    tx = px - (px - tx) * (s / scale); ty = py - (py - ty) * (s / scale); scale = s;
    apply(glide);
  };
  const zoomBy = (factor) => zoomTo(scale * factor, null, true);
  const pointIn = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };

  const show = (at) => {
    if (at < 0 || at >= gallery.length) return;
    index = at;
    const item = gallery[at], mine = ++token, url = urlOf(item);
    frame.name.textContent = item.name || (item.path || "").split("/").pop();
    dialog.setAttribute("aria-label", frame.name.textContent);
    frame.external.href = url;
    prev.disabled = at === 0; next.disabled = at === gallery.length - 1;
    if (strip) strip.querySelectorAll(".v-film").forEach((b, i) => { b.toggleAttribute("aria-current", i === at); if (i === at) b.scrollIntoView({ block: "nearest", inline: "nearest" }); });
    const facts = item.path ? factsOf(item.sid, item.path) : Promise.resolve(null);
    const next_ = h("img", { src: url, alt: frame.name.textContent, draggable: false, class: "v-img" });
    const say = (dims) => facts.then((f) => {
      if (mine !== token) return;
      frame.meta.textContent = [many ? `${at + 1} of ${gallery.length}` : null, whenShort(atOf(item) || (f && f.modified)), dims, f ? sizeWords(f.size) : null].filter(Boolean).join(" · ");
      frame.meta.title = f ? shortPath(f.path) : "";
    });
    say("");
    next_.onload = () => {
      if (mine !== token) return;
      natural = [next_.naturalWidth || 1, next_.naturalHeight || 1];
      canvas.replaceChildren(next_);
      img = next_;
      measure();
      fitNow(false);
      say(`${natural[0]}×${natural[1]}`);
    };
    next_.onerror = () => { if (mine === token) { img = null; canvas.replaceChildren(h("div", { class: "empty-line", textContent: "This image can't be opened any more." })); } };
    [gallery[at - 1], gallery[at + 1]].forEach((near) => { if (near) new Image().src = urlOf(near); });
  };
  const step = (by) => show(index + by);

  // Pointer: drag pans a zoomed image, two fingers pinch, a sideways swipe at fit moves to the next image,
  // a click on the dark around the image closes.
  const pointers = new Map();
  let gesture = null;
  canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, pointIn(e));
    const pts = [...pointers.values()];
    gesture = pts.length === 2
      ? { pinch: true, dist: Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]), scale, mid: [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2], tx, ty }
      : { from: pointIn(e), tx, ty, moved: false, onImage: e.target === img };
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId) || !gesture) return;
    pointers.set(e.pointerId, pointIn(e));
    const pts = [...pointers.values()];
    if (gesture.pinch && pts.length === 2) {
      const dist = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]), mid = [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2];
      const s = Math.min(8, Math.max(fit, gesture.scale * dist / gesture.dist));
      tx = mid[0] - (gesture.mid[0] - gesture.tx) * (s / gesture.scale); ty = mid[1] - (gesture.mid[1] - gesture.ty) * (s / gesture.scale); scale = s;
      return apply(false);
    }
    const [x, y] = pointIn(e), dx = x - gesture.from[0], dy = y - gesture.from[1];
    if (Math.abs(dx) + Math.abs(dy) > 4) gesture.moved = true;
    if (zoomed()) { tx = gesture.tx + dx; ty = gesture.ty + dy; apply(false); stage.classList.add("dragging"); }
  });
  const lift = (e) => {
    if (!pointers.has(e.pointerId)) return;
    const end = pointIn(e);
    pointers.delete(e.pointerId);
    stage.classList.remove("dragging");
    if (!gesture || gesture.pinch) { if (!pointers.size) gesture = null; return; }
    const dx = end[0] - gesture.from[0], dy = end[1] - gesture.from[1];
    if (!zoomed() && many && Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.5) step(dx < 0 ? 1 : -1);
    else if (!gesture.moved && !gesture.onImage && e.type === "pointerup") dialog.close();
    gesture = null;
  };
  canvas.addEventListener("pointerup", lift);
  canvas.addEventListener("pointercancel", lift);
  canvas.addEventListener("dblclick", (e) => { if (e.target === img) { if (zoomed()) fitNow(true); else zoomTo(Math.max(fit * 2.5, 1), pointIn(e), true); } });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) return zoomTo(scale * Math.exp(-e.deltaY * 0.01), pointIn(e), false);  // a trackpad pinch arrives as a wheel with ctrl
    if (zoomed()) { tx -= e.deltaX; ty -= e.deltaY; apply(false); }
  }, { passive: false });
  dialog.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || (e.target.closest && e.target.closest("a, button") && (e.key === " " || e.key === "Enter"))) return;
    const act = { ArrowLeft: () => step(-1), ArrowRight: () => step(1), "+": () => zoomBy(1.5), "=": () => zoomBy(1.5), "-": () => zoomBy(1 / 1.5), 0: () => fitNow(true), 1: () => zoomTo(1, null, true) }[e.key];
    if (act) { e.preventDefault(); act(); }
  });
  const watch = new ResizeObserver(() => { const was = !zoomed(); measure(); if (was) fitNow(false); else apply(false); });
  watch.observe(canvas);
  dialog.addEventListener("close", () => watch.disconnect());
  showFrame(frame);
  show(start);
}

// Hover cards: what a path or link is, before it's opened. A file card reads the file's facts from the hub; a link
// card is fetched by the hub, and only after the pointer has rested on the link.
let hoverCard = null, hoverTimer = 0, hoverToken = 0;
const linkCards = new Map();  // url → card, from this page's own asks and what the hub already kept
const hideHover = () => { clearTimeout(hoverTimer); hoverToken++; if (hoverCard) { hoverCard.remove(); hoverCard = null; } };
const placeCard = (card, anchor) => {
  document.body.append(card);
  const w = card.offsetWidth, hgt = card.offsetHeight, room = 8;
  let x, y;
  if (anchor.rect) {
    const r = anchor.rect;
    x = r.left - w - 8 >= room ? r.left - w - 8 : Math.min(r.right + 8, innerWidth - w - room);
    y = Math.min(Math.max(room, r.top), innerHeight - hgt - room);
  } else {
    x = Math.min(anchor.x + 12, innerWidth - w - room);
    y = anchor.y - hgt - 12 >= room ? anchor.y - hgt - 12 : Math.min(anchor.y + 20, innerHeight - hgt - room);
  }
  card.style.left = `${Math.max(room, x)}px`;
  card.style.top = `${Math.max(room, y)}px`;
};
const linkParts = (url) => { try { const u = new URL(url); return { host: u.host.replace(/^www\./, ""), rest: (u.pathname === "/" ? "" : u.pathname) + u.search }; } catch { return { host: url, rest: "" }; } };
const pictureUrl = (id) => `/api/preview/image?id=${encodeURIComponent(id)}`;
const favicon = (card) => card && card.icon ? h("img", { class: "fav", src: pictureUrl(card.icon), alt: "", onerror: (e) => e.target.replaceWith(svg(PV.link)) }) : svg(PV.link);
const linkCardBody = (url, card, refused) => {
  const { host, rest } = linkParts(url);
  return [card && card.image ? h("img", { class: "lc-pic", src: pictureUrl(card.image), alt: "", onerror: (e) => e.target.remove() }) : null,
    h("div", { class: "lc-text" },
      h("div", { class: "lc-title" }, favicon(card), h("b", { dir: "auto", textContent: (card && card.title) || host })),
      refused ? h("div", { class: "lc-why", textContent: refused }) : card && card.description ? h("div", { class: "lc-desc", dir: "auto", textContent: card.description }) : card ? null : h("div", { class: "lc-desc quiet", textContent: "Looking…" }),
      card && card.title ? h("div", { class: "lc-host", textContent: card.site && card.site.toLowerCase() !== host.toLowerCase() ? `${card.site} · ${host}${rest}` : host + rest })
        : rest ? h("div", { class: "lc-host", textContent: rest }) : null)];
};
const askCard = async (url) => {
  if (linkCards.has(url)) return linkCards.get(url);
  const card = await api(`/api/preview/link?url=${encodeURIComponent(url)}`);
  linkCards.set(url, card);
  document.querySelectorAll(".t-row[data-url]").forEach((row) => { if (row.dataset.url === url && row.redraw) row.redraw(); });
  return card;
};
const showHover = (event, text, sid, anchor) => {
  hideHover();
  const mine = hoverToken, at = anchor || { x: event.clientX, y: event.clientY };
  if (/^https?:\/\//i.test(text)) {
    hoverTimer = setTimeout(async () => {
      if (mine !== hoverToken) return;
      const known_ = linkCards.get(text);
      if (anchor && known_ && !known_.description && !known_.image && !known_.refused) return;
      hoverCard = h("div", { class: "hover-card link-card", role: "tooltip" }, linkCardBody(text, known_, known_ && known_.refused));
      placeCard(hoverCard, at);
      if (known_) return;
      let card = null, refused = "";
      try { card = await askCard(text); refused = card.refused || ""; } catch (error) { refused = error.known ? error.message : ""; }
      if (mine !== hoverToken || !hoverCard) return;
      if (anchor && !refused && !(card && (card.description || card.image))) return hideHover();  // beside a list row it would only repeat the row
      hoverCard.replaceChildren(...clean(linkCardBody(text, card || {}, refused)));
      placeCard(hoverCard, at);
    }, 350);
    return;
  }
  const path = tidyPath(text), kind = kindOf(path), name = path.split("/").pop();
  const meta = h("div", { class: "fc-meta" });
  const head = h("div", { class: "fc-name" }, kind === "image" ? null : svg(PV[kind] || PV.file), h("b", { dir: "auto", textContent: name }));
  const lines = h("pre", { class: "fc-lines" });
  hoverCard = h("div", { class: `hover-card file-card k-${kind}`, role: "tooltip" },
    kind === "image" ? h("div", { class: "fc-pic" }, h("img", { src: thumbUrl(sid, { path }), alt: "", onerror: hideHover })) : null, head, meta, kind === "text" ? lines : null);
  placeCard(hoverCard, at);
  factsOf(sid, path).then((f) => {
    if (mine !== hoverToken || !hoverCard) return;
    if (!f) { meta.textContent = "Not a file this session can open"; return placeCard(hoverCard, at); }
    meta.textContent = [f.width ? `${f.width}×${f.height}` : null, f.lines !== undefined ? `${f.lines.toLocaleString("en-GB")} ${f.lines === 1 ? "line" : "lines"}` : null, sizeWords(f.size), agoWords(f.modified), shortPath(f.folder)].filter(Boolean).join(" · ");
    if (f.head && f.head.length) lines.append(...f.head.slice(0, 6).map((line) => h("span", { textContent: line || " " })));
    else lines.remove();
    placeCard(hoverCard, at);
  });
};
const activateTarget = (text, sid) => {
  hideHover();
  if (/^https?:\/\//i.test(text)) return openExternal(text);
  openPreview({ sid, path: tidyPath(text) });
};

// ── What a turn of the chat shows besides its words, as a messaging app does: pictures as tiles (a tap opens the
// viewer), video and recordings that play in place, PDFs as a file to open, and links as a card. A link's card is fetched
// by the hub when the card first comes into view; until then it shows the address.
const cardWatch = "IntersectionObserver" in window ? new IntersectionObserver((seen) => seen.forEach((e) => {
  if (!e.isIntersecting) return;
  cardWatch.unobserve(e.target);
  const url = e.target.dataset.url;
  askCard(url).then(() => e.target.redraw && e.target.redraw(), (error) => { linkCards.set(url, { refused: error.known ? error.message : "" }); e.target.redraw && e.target.redraw(); });
}), { rootMargin: "200px" }) : null;
const chatLinkCard = (url, sid) => {
  const a = h("a", { class: "m-link", href: url, target: "_blank", rel: "noopener noreferrer", "data-url": url });
  a.redraw = () => {
    const card = linkCards.get(url), { host, rest } = linkParts(url);
    if (card && card.kind === "image" && card.image && !a.noPicture) {  // a link to a picture shows the picture, fetched by the hub
      const src = pictureUrl(card.image), title = card.title || host;
      a.className = "m-link m-link-image";
      a.onclick = (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); openPreview({ sid, src, name: title, gallery: [{ sid, src, name: title, kind: "image" }], index: 0 }); };
      a.replaceChildren(h("img", { src, alt: title, loading: "lazy", decoding: "async", onload: stickChat, onerror: () => { a.noPicture = true; a.onclick = null; a.className = "m-link"; a.redraw(); } }),
        h("span", { class: "m-link-site" }, svg(PV.link), h("span", { textContent: host })));
      return;
    }
    const titled = card && card.title;
    a.classList.toggle("has-pic", !!(card && card.image));
    a.replaceChildren(...clean([card && card.image ? h("img", { class: "m-link-pic", src: pictureUrl(card.image), alt: "", loading: "lazy", onerror: (e) => { e.target.remove(); a.classList.remove("has-pic"); } }) : null,
      h("span", { class: "m-link-text" },
        h("span", { class: "m-link-site" }, favicon(card), h("span", { textContent: card && card.site && card.site.toLowerCase() !== host.toLowerCase() ? card.site : host })),
        h("b", { dir: "auto", textContent: titled ? card.title : (rest || host).slice(0, 140) }),
        card && card.description ? h("span", { class: "m-link-desc", dir: "auto", textContent: card.description }) : null)]));
  };
  a.redraw();
  if (!linkCards.has(url) && cardWatch) cardWatch.observe(a);
  return a;
};
const mediaUrl = (sid, m) => m.blob ? blobUrl(sid, m.blob) : fileUrl(sid, m.path);
// Video and recordings get their address only when they come near the screen, so a long chat doesn't ask for all of them.
const mediaWatch = "IntersectionObserver" in window ? new IntersectionObserver((seen) => seen.forEach((e) => {
  if (!e.isIntersecting) return;
  mediaWatch.unobserve(e.target);
  if (e.target.loadNow) e.target.loadNow();
}), { rootMargin: "600px 0px" }) : null;
const lazyMedia = (el, src) => {
  el.loadNow = () => { el.loadNow = null; el.preload = "metadata"; el.src = src; };
  if (mediaWatch) mediaWatch.observe(el); else el.loadNow();
  return el;
};
// A picture's tile keeps its shape before it loads (the server says its pixel size), so the chat doesn't jump.
// One picture alone is shown at its own shape, up to the turn's width and 360px high; several are a grid of tiles.
const picTile = (sid, m, i, gallery, one, more) => {
  const name = gallery[i].name, ratio = m.w && m.h ? m.w / m.h : 0;
  const tile = h("button", { type: "button", class: `m-pic${one && ratio ? " sized" : ""}`, title: name, style: one && ratio ? `--r:${ratio.toFixed(4)};--w:${m.w}px` : null,
    onclick: () => openPreview({ sid, path: m.path, blob: m.blob, src: m.src, name, gallery, index: i }) });
  tile.append(h("img", { src: thumbUrl(sid, m, one ? 960 : 640), alt: name, loading: "lazy", decoding: "async", draggable: false,
    onload: (e) => {
      const img = e.target, seen = img.naturalWidth / (img.naturalHeight || 1);
      if (one && ratio && Math.abs(seen - ratio) / ratio > 0.02) tile.style.setProperty("--r", seen.toFixed(4));  // a photo turned by its EXIF
      stickChat(e);
    },
    onerror: () => tile.classList.add("gone") }), more);
  return tile;
};
const videoTile = (sid, m, name) => {
  const frame = h("div", { class: "m-frame" });
  const video = h("video", { controls: true, playsinline: true, preload: "none", "aria-label": name,
    onloadedmetadata: (e) => { if (video.videoWidth && video.videoHeight) frame.style.setProperty("--r", (video.videoWidth / video.videoHeight).toFixed(4)); stickChat(e); },
    onerror: () => frame.classList.add("broken") });
  frame.append(lazyMedia(video, `${mediaUrl(sid, m)}#t=0.1`));
  return h("figure", { class: "m-video" }, frame,
    h("figcaption", {}, h("button", { type: "button", class: "m-open", title: "Open in the viewer", onclick: () => openPreview({ sid, path: m.path, name }) }, svg(PV.video), h("span", { dir: "auto", textContent: name }))));
};
const audioTile = (sid, m, name) => h("figure", { class: "m-audio" }, h("figcaption", {}, svg(PV.audio), h("span", { dir: "auto", textContent: name })),
  lazyMedia(h("audio", { controls: true, preload: "none", "aria-label": name }), mediaUrl(sid, m)));
// A PDF shows its first page (drawn by the hub) beside its name and size; the PDF icon if the page can't be drawn.
const pdfTile = (sid, m, name) => {
  const facts = h("small", { textContent: "PDF" });
  factsOf(sid, m.path).then((f) => { if (f && f.size) facts.textContent = `PDF · ${sizeWords(f.size)}`; });
  return h("button", { type: "button", class: "m-file m-pdf", title: "Open", onclick: () => openPreview({ sid, path: m.path, name }) },
    h("span", { class: "m-page" }, h("img", { src: thumbUrl(sid, m, 320), alt: "", loading: "lazy", decoding: "async", onerror: (e) => e.target.replaceWith(svg(PV.pdf)) })),
    h("span", { class: "m-file-text" }, h("span", { dir: "auto", textContent: name }), facts));
};
const mediaBlock = (sid, media, skip = () => false) => {
  const list = (media || []).filter((m) => !skip(m));
  if (!list.length) return null;
  const pics = list.filter((m) => m.kind === "image"), links = list.filter((m) => m.kind === "link").slice(0, 3);
  const plays = list.filter((m) => m.kind === "video" || m.kind === "audio"), docs = list.filter((m) => m.kind === "pdf");
  const name = (m) => m.name || (m.path || "").split("/").pop();
  const gallery = pics.map((m) => ({ sid, path: m.path, blob: m.blob, name: name(m), kind: "image" }));
  const one = pics.length === 1;
  return h("div", { class: "turn-media" },
    pics.length ? h("div", { class: `m-pics n${Math.min(pics.length, 4)}` }, pics.slice(0, 12).map((m, i) =>
      picTile(sid, m, i, gallery, one, i === 11 && pics.length > 12 ? h("span", { class: "m-more", textContent: `+${pics.length - 12}` }) : null))) : null,
    plays.map((m) => m.kind === "video" ? videoTile(sid, m, name(m)) : audioTile(sid, m, name(m))),
    docs.map((m) => pdfTile(sid, m, name(m))),
    links.map((m) => chatLinkCard(m.url, sid)));
};
// A chat that was at its end stays there while pictures and video load and grow the page.
function stickChat(e) {
  const log = e.target.closest(".chat-log, .reader");
  if (log && log.dataset.stuck !== "0") log.scrollTop = log.scrollHeight;
}
// A new turn joins the page without redrawing the turns before it, so a video that's playing keeps playing.
const drawTurns = (body, nodes) => {
  const want = clean(nodes);
  want.forEach((node, i) => { if (body.children[i] !== node) body.insertBefore(node, body.children[i] || null); });
  while (body.children.length > want.length) body.lastElementChild.remove();
};

// What a session shared, newest first, as a timeline: one time per turn, images as a row of thumbnails,
// files and links one row each. A link shows its title only once its card has been fetched for a hover.
const KIND_ICON = { audio: PV.audio, video: PV.video, pdf: PV.pdf, text: PV.file };
function sharedTimeline(items, images, onOpen) {
  const groups = [];
  items.forEach((item) => {
    const at = atOf(item), last = groups[groups.length - 1];
    if (last && Math.abs(last.at - at) <= 120) last.items.push(item); else groups.push({ at, items: [item] });
  });
  const row = (item) => {
    if (item.kind === "link") {
      const a = h("a", { class: "t-row", href: item.url, target: "_blank", rel: "noopener noreferrer", "data-url": item.url, "data-kind": "link",
        onmouseenter: (e) => showHover(e, item.url, item.sid, { rect: a.getBoundingClientRect() }), onmouseleave: hideHover, onfocus: (e) => showHover(e, item.url, item.sid, { rect: a.getBoundingClientRect() }), onblur: hideHover, onclick: hideHover });
      a.redraw = () => {
        const card = linkCards.get(item.url), { host, rest } = linkParts(item.url);
        a.replaceChildren(h("span", { class: "t-ic" }, favicon(card)), h("span", { class: "t-main" }, h("b", { dir: "auto", textContent: (card && card.title) || host }), h("small", { textContent: (card && card.title ? host : "") + rest || host })));
      };
      a.redraw();
      return a;
    }
    return h("button", { class: "t-row", type: "button", "data-kind": item.kind, title: shortPath(item.path), onclick: () => onOpen(item) },
      h("span", { class: "t-ic" }, svg(KIND_ICON[item.kind] || PV.file)),
      h("span", { class: "t-main" }, h("b", { dir: "auto", textContent: item.name }), h("small", { textContent: (item.by ? "subagent · " : "") + shortPath(item.path.slice(0, item.path.length - item.name.length - 1)) })));
  };
  return h("div", { class: "timeline" }, groups.map((group) => {
    const pics = group.items.filter((i) => i.kind === "image"), rest = group.items.filter((i) => i.kind !== "image");
    return h("div", { class: "t-group" },
      h("time", { class: "t-at", textContent: whenShort(group.at) || "Earlier" }),
      pics.length ? h("div", { class: "thumbs" }, pics.map((i) => h("button", { class: "thumb", type: "button", title: i.by ? `${i.name}, from a subagent` : i.name, onclick: () => onOpen(i) },
        h("img", { src: thumbUrl(i.sid, i), alt: i.name, loading: "lazy", draggable: false })))) : null,
      rest.map(row));
  }));
}

// Finds links and file paths on screen, including ones Claude's text wrapping split across two rows.
const URL_RE = /https?:\/\/[^\s<>"'`)\]}]+/g;
const PATH_RE = /(?:~\/|\/|\.{1,2}\/|[\w.-]+\/)[\w./@%+-]*\.(?:png|jpe?g|gif|webp|avif|svg|mp3|m4a|wav|ogg|flac|aac|mp4|mov|webm|pdf|md|txt|json|csv|log|py|js|ts|tsx|swift|sh|html|css|ya?ml|toml)\b/gi;
function linkProvider(term, sid) {
  const rowText = (y) => { const line = term.buffer.active.getLine(y); return line ? line.translateToString(true, 0, term.cols) : ""; };
  const continues = (a, b) => {
    const below = term.buffer.active.getLine(b);
    if (below && below.isWrapped) return true;  // the terminal wrapped it: one line on two rows
    const left = rowText(a), right = rowText(b);
    if (left.trimEnd().length < term.cols - 8 || !right.trim()) return false;
    const lastWord = left.trimEnd().split(/\s+/).pop();
    if (/\.[a-z0-9]{1,5}$/i.test(lastWord) && /^\s*(\/|~\/|https?:)/.test(right)) return false;  // a whole path, then another one
    return /[/\w.-]/.test(lastWord.slice(-1)) && (/^https?:/.test(lastWord) || lastWord.includes("/")) && /^\s*[\w./%?=&#~+-]+/.test(right);
  };
  return {
    provideLinks(lineNumber, callback) {
      let first = lineNumber - 1;
      while (first > 0 && lineNumber - 1 - first < 3 && continues(first - 1, first)) first--;
      let lastRow = first;
      while (lastRow - first < 3 && continues(lastRow, lastRow + 1)) lastRow++;
      const cells = [];
      let text = "";
      for (let y = first; y <= lastRow; y++) {
        const row = y === first ? rowText(y).trimEnd() : rowText(y).trimEnd().replace(/^\s+/, "");
        const lead = y === first ? 0 : rowText(y).length - rowText(y).trimStart().length;
        for (let i = 0; i < row.length; i++) cells.push({ x: lead + i + 1, y: y + 1 });
        text += row;
      }
      const links = [];
      const collect = (regex, tidy) => {
        for (const match of text.matchAll(regex)) {
          const value = tidy(match[0]);
          const start = cells[match.index], end = cells[match.index + value.length - 1];
          if (!start || !end || start.y > lineNumber || end.y < lineNumber) continue;
          links.push({ range: { start, end }, text: value, activate: (_, target) => activateTarget(target, sid), hover: (e, target) => showHover(e, target, sid), leave: hideHover });
        }
      };
      collect(URL_RE, (v) => v.replace(/[.,;:!?*_]+$/, ""));
      const urls = [...text.matchAll(URL_RE)].map((m) => [m.index, m.index + m[0].length]);
      for (const match of text.matchAll(PATH_RE)) {
        if (urls.some(([a, b]) => match.index >= a && match.index < b)) continue;
        const start = cells[match.index], end = cells[match.index + match[0].length - 1];
        if (!start || !end || start.y > lineNumber || end.y < lineNumber) continue;
        links.push({ range: { start, end }, text: match[0], activate: (_, target) => activateTarget(target, sid), hover: (e, target) => showHover(e, target, sid), leave: hideHover });
      }
      callback(links.length ? links : undefined);
    },
  };
}

const paneJump = (e) => e.altKey && !e.metaKey && !e.ctrlKey && /^Digit[1-4]$/.test(e.code) && route().name === "session" && route().ids.length > 1;
const THEME = { background: "#0a0f1e", foreground: "#e8edfb", cursor: "#8fb0ff", selectionBackground: "#2c3f73" };
// ── appearance: theme, accent, terminal font size, density and motion ──
// The Settings page sets them (pref names theme, accent, term_font_size, density, reduce_motion). theme.js applied the
// last ones this browser saw before the first paint; this confirms them from the server and applies every change live.
// Until the server's settings have come, the cached ones stand in, so a light page doesn't flash dark while it loads.
const TERM_FONT = 13;
// Paper's terminal: an ANSI palette deepened for a light ground, bright colours a step darker still, so they stand out.
// Claude Code draws in its own colours too, so the terminal also lifts any colour too faint to read (minimumContrastRatio).
const TERM_LIGHT = { background: "#fcfcfe", foreground: "#1b2338", cursor: "#2149d4", cursorAccent: "#fcfcfe", selectionBackground: "#c9d6fb",
  black: "#1d2436", red: "#c0223e", green: "#0f7a4f", yellow: "#8a5a00", blue: "#2453d1", magenta: "#8a3fc0", cyan: "#0b7285", white: "#5d6782",
  brightBlack: "#4c5670", brightRed: "#a3162f", brightGreen: "#0b6a43", brightYellow: "#6e4700", brightBlue: "#1d47c4", brightMagenta: "#7432a8", brightCyan: "#085e6e", brightWhite: "#3f4862" };
const liveTerms = new Set();  // every terminal open on the page, so a change reaches them at once
let appearanceKnown = false, appearanceNow = { theme: "dark" };
const appearancePrefs = () => {
  const before = appearanceKnown ? {} : window.hubAppearance ? window.hubAppearance.cached() : {};
  const want = (name, fallback) => pref(name, before[name] !== undefined ? before[name] : fallback);
  return { theme: want("theme", "dark"), accent: want("accent", ""), density: want("density", "comfortable"), reduce_motion: want("reduce_motion", "system"), term_font_size: want("term_font_size", TERM_FONT) };
};
const termFont = () => { const n = Number(appearancePrefs().term_font_size); return Number.isFinite(n) && n >= 8 && n <= 32 ? n : TERM_FONT; };
const termTheme = () => {
  const light = appearanceNow.theme === "light", css = getComputedStyle(document.documentElement);
  const base = light ? TERM_LIGHT : THEME;
  if (!appearanceNow.accent) return { ...base };
  return { ...base, cursor: css.getPropertyValue("--accent-ink").trim(), selectionBackground: css.getPropertyValue("--accent-sel").trim() };
};
function applyAppearance() {
  const prefs = appearancePrefs();
  if (window.hubAppearance) appearanceNow = window.hubAppearance.apply(prefs);
  const theme = termTheme(), size = termFont(), contrast = appearanceNow.theme === "light" ? 4.5 : 1;
  for (const t of liveTerms) {
    const o = t.term.options;
    o.theme = theme;
    if (o.minimumContrastRatio !== contrast) o.minimumContrastRatio = contrast;
    if (o.fontSize !== size) { o.fontSize = size; t.refit(); }
  }
}
window.addEventListener("hub:settings", () => { appearanceKnown = true; applyAppearance(); });
if (window.hubAppearance) window.hubAppearance.onSystem(applyAppearance);  // "system" turned light or dark, or motion changed
applyAppearance();
function openTerminal(s) {
  const host = h("div", { class: "term" });
  const term = new Terminal({ fontFamily: '"JetBrains Mono", Menlo, monospace', fontSize: termFont(), lineHeight: 1.15, cursorBlink: true, theme: termTheme(), minimumContrastRatio: appearanceNow.theme === "light" ? 4.5 : 1, macOptionIsMeta: true, scrollback: 0,
    linkHandler: { allowNonHttpProtocols: true, activate: (_, text) => activateTarget(text, s.id), hover: (e, text) => showHover(e, text, s.id), leave: hideHover } });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.registerLinkProvider(linkProvider(term, s.id));
  term.parser.registerOscHandler(52, (data) => {
    const value = data.split(";")[1];
    if (value && value !== "?") { try { navigator.clipboard.writeText(new TextDecoder().decode(Uint8Array.from(atob(value), (c) => c.charCodeAt(0)))); } catch { /* clipboard refused */ } }
    return true;
  });
  term.attachCustomKeyEventHandler((e) => !((e.metaKey && ["k", "b"].includes(e.key.toLowerCase())) || (e.ctrlKey && e.key === "`") || paneJump(e)));
  const state = { session: s, host, term, ws: null, closed: false, retry: 0, timer: null, observer: null, link: "connecting", nextAt: 0, onlink: null };
  liveTerms.add(state);
  const send = (message) => { if (state.ws && state.ws.readyState === 1) state.ws.send(JSON.stringify(message)); };
  // The connection, drawn over the terminal so its size never changes. Bytes typed while it's down aren't kept: a late Enter into a live agent is worse than a lost one, so the bar says so.
  const linkSay = h("span", { class: "sr-only", role: "status" });
  const barText = h("span", { "aria-hidden": "true" });
  const barRetry = h("button", { class: "retry", type: "button", textContent: "Retry now", onclick: () => { state.retry = 0; clearTimeout(state.timer); connect(); term.focus(); } });
  const bar = h("div", { class: "term-bar", hidden: true }, barText, barRetry);
  const drawBar = () => {
    const left = Math.ceil((state.nextAt - Date.now()) / 1000);
    bar.hidden = state.link === "open" || (state.link === "connecting" && Date.now() - state.since < 500);
    bar.classList.toggle("quiet", state.link === "connecting");
    barRetry.hidden = state.link === "connecting";
    barText.textContent = state.link === "connecting" ? "Connecting…" : `Not connected. Typing isn't sent. ${state.link === "failed" ? "Trying again every 30 seconds." : left > 0 ? `Reconnecting in ${left}s.` : "Reconnecting…"}`;
  };
  const setLink = (link) => {
    const was = state.link;
    state.link = link;
    drawBar();
    if (link === was) return;
    linkSay.textContent = link === "retrying" ? "Terminal disconnected. Reconnecting." : link === "failed" ? "Couldn't reconnect to this terminal." : link === "open" && was !== "connecting" ? "Terminal connected again." : "";
    if (state.onlink) state.onlink();
  };
  state.down = () => state.link === "retrying" || state.link === "failed";
  state.send = send;
  term.onData((d) => send({ t: "i", d }));
  term.onResize(({ cols, rows }) => send({ t: "r", c: cols, r: rows }));
  const connect = () => {
    if (state.closed || (state.ws && state.ws.readyState < 2)) return;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}/ws/term/${s.id}?cols=${term.cols}&rows=${term.rows}`);
    ws.binaryType = "arraybuffer";
    state.ws = ws;
    ws.onopen = () => { state.retry = 0; term.reset(); setLink("open"); };
    ws.onmessage = (event) => term.write(new Uint8Array(event.data));
    ws.onclose = (event) => {
      if (state.closed) return;
      if (event.code === 4000) { tick(); return; }  // the session ended: the next poll swaps the pane for its record
      state.retry = Math.min(state.retry + 1, 6);
      const failed = state.retry >= 6, wait = failed ? 30000 : 400 * 2 ** state.retry;
      state.nextAt = Date.now() + wait;
      state.timer = setTimeout(connect, wait);
      setLink(failed ? "failed" : "retrying");
    };
  };
  // A finger scrolls the terminal. The history lives in tmux (scrollback here is 0) and tmux reads the wheel, but
  // xterm.js sends a touch drag nowhere, so a drag becomes wheel events, one per row moved, and a flick coasts.
  const touchScroll = () => {
    let lastY = null, startY = 0, x = 0, y = 0, carry = 0, speed = 0, lastT = 0, coast = 0;
    const screen = () => term.element && term.element.querySelector(".xterm-screen");
    const perStep = s.kind === "claude" ? 1 : 5;  // Claude moves a row per wheel step; tmux's own history moves five
    const rowPx = () => { const el = screen(); return (el && term.rows ? el.clientHeight / term.rows : 16) * perStep; };
    const wheel = (px) => {
      carry += px;
      const row = rowPx(), rows = Math.trunc(carry / row), cell = row / perStep;
      if (!rows) return;
      carry -= rows * row;
      const el = screen();
      for (let i = 0; el && i < Math.min(Math.abs(rows), 40); i++) el.dispatchEvent(new WheelEvent("wheel", { deltaY: Math.sign(rows) * cell, deltaMode: 0, clientX: x, clientY: y, bubbles: true, cancelable: true }));
    };
    host.addEventListener("touchstart", (e) => {
      cancelAnimationFrame(coast); speed = 0; carry = 0;
      if (e.touches.length !== 1) { lastY = null; return; }
      ({ clientX: x, clientY: y } = e.touches[0]); lastY = startY = y; lastT = e.timeStamp;
    }, { passive: true, capture: true });
    host.addEventListener("touchmove", (e) => {
      if (lastY === null || e.touches.length !== 1) return;
      e.preventDefault();
      if (state.onScrollIntent && Math.abs(e.touches[0].clientY - startY) > 12 && state.onScrollIntent()) { lastY = null; return; }
      const now = e.touches[0].clientY, dy = lastY - now, dt = Math.max(1, e.timeStamp - lastT);
      speed = 0.8 * (dy / dt) + 0.2 * speed;
      lastY = now; lastT = e.timeStamp;
      wheel(dy);
    }, { passive: false, capture: true });
    host.addEventListener("touchend", (e) => {
      if (lastY === null || e.touches.length) return;
      lastY = null;
      if (Math.abs(speed) < 0.3 || e.timeStamp - lastT > 80) return;
      let v = speed * 16, prev = performance.now();  // pixels per frame, slowing like a list does
      const step = (t) => { const f = Math.min(3, (t - prev) / 16); prev = t; wheel(v * f); v *= 0.95 ** f; if (Math.abs(v) > 0.5) coast = requestAnimationFrame(step); };
      coast = requestAnimationFrame(step);
    }, { passive: true, capture: true });
  };
  // Only a terminal that is open and not yet disposed can be fitted: a pane rebuilt or held back on a phone has none to measure.
  state.refit = () => { if (state.started && !state.closed && host.clientWidth && host.clientHeight) fit.fit(); };
  state.start = () => {
    if (state.held || state.started) return;  // a phone's chat view holds the terminal back: opening it would squeeze the session to the phone's width
    state.started = true;
    term.open(host);
    host.append(linkSay, bar);
    touchScroll();
    fit.fit();
    state.since = Date.now();
    connect();
    setTimeout(drawBar, 520);
    state.ticker = setInterval(drawBar, 1000);
    let wait;
    state.observer = new ResizeObserver(() => { clearTimeout(wait); wait = state.wait = setTimeout(() => { if (!document.body.classList.contains("resizing")) state.refit(); }, 100); });
    state.observer.observe(host);
    term.focus();
  };
  // xterm queues a scroll-area sync for the next frame when its buffer resets or its size changes, and doesn't cancel it
  // on dispose: disposed in between, that frame reads a renderer that is gone. So the terminal goes after two frames,
  // once anything it queued has run; with the socket closed first, nothing new arrives to queue more.
  state.dispose = () => {
    if (state.closed) return;
    state.closed = true; liveTerms.delete(state); clearTimeout(state.timer); clearTimeout(state.wait); clearInterval(state.ticker); state.observer && state.observer.disconnect(); state.ws && state.ws.close();
    requestAnimationFrame(() => requestAnimationFrame(() => term.dispose()));
  };
  return state;
}

// ── C: live status. The orb, the ticking time, the pane strip, Changes, ports and peek ──
// An orb kept in a slot: redrawn only when its state changes, and drawn as a dot until the orb module has loaded.
const orbSlot = (holder, state, size, label) => {
  const ready = !!window.hubOrb;
  if (holder.dataset.orb === state && holder.dataset.ready === String(ready) && holder.firstChild) { if (label) holder.firstChild.setAttribute("aria-label", label); return holder; }
  holder.dataset.orb = state; holder.dataset.ready = String(ready);
  holder.replaceChildren(ready ? window.hubOrb(state, { size, label }) : dot(state, label));
  return holder;
};
window.addEventListener("hub-orbs-ready", () => document.querySelectorAll(".orb-slot[data-ready=false]").forEach((slot) => { slot.dataset.orb = ""; orbSlot(slot, slot.dataset.want || "idle", Number(slot.dataset.size) || 16); }));
const newOrb = (state, size, label) => { const slot = h("span", { class: "orb-slot", "data-size": size, "data-want": state, "aria-hidden": label ? undefined : "true" }); return orbSlot(slot, state, size, label); };
const setOrb = (slot, state, label) => { slot.dataset.want = state; return orbSlot(slot, state, Number(slot.dataset.size) || 16, label); };
DOT_WORDS.error = "Error";
const ORB_WORDS = { reasoning: "Thinking", compacting: "Compacting", retrying: "Retrying", working: "Working", waiting: "Needs you" };
// "12s", "1m 04s", "2h 05m": what has passed since an epoch second, in a width that doesn't jump.
const took = (since) => {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - since));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor(s / 60) % 60).padStart(2, "0")}m`;
};
const turnClock = (since, attrs = {}) => h("time", { ...attrs, class: `tick ${attrs.class || ""}`, "data-since": since, textContent: took(since) });
setInterval(() => document.querySelectorAll("time.tick[data-since]").forEach((el) => { const text = took(Number(el.dataset.since)); if (el.textContent !== text) el.textContent = text; }), 1000);
const tokens = (n) => n >= 1e6 ? `${+(n / 1e6).toFixed(n % 1e6 ? 1 : 0)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
const counts = (c) => [h("span", { class: "n-add", textContent: `+${c.added}` }), " ", h("span", { class: "n-del", textContent: `−${c.removed}` })];

// ── A choice Claude shows, answered here: a question of several (single or multiple choice, with words of your own),
// a permission, a plan to approve, a picker or a menu. The screen stays the truth: what is ticked, typed and which
// question is open are read back from it after each answer. Ticks and words wait here until they're sent, so the
// screen refreshing never loses them.
const qaDrafts = new Map();  // `${session}|${question}` → { picks: Set | null, words: { n: text } }
function questionPanel(id, { compact = false, onSent = () => {} } = {}) {
  const el = h("div", { class: `qa${compact ? " compact" : ""}` });
  let dialog = null, asking = "", shown = "", ident = "", busy = false, inflight = false, hold = 0;
  const qid = `qa-q-${id}-${compact ? "p" : "c"}`;
  const draft = () => { const key = `${id}|${ident}`; if (!qaDrafts.has(key)) qaDrafts.set(key, { picks: null, words: {} }); return qaDrafts.get(key); };
  const settle = () => { busy = false; clearTimeout(hold); el.removeAttribute("aria-busy"); };
  const send = async (payload, said) => {
    if (busy) return;
    busy = inflight = true; el.setAttribute("aria-busy", "true");
    try {
      await api(`/api/sessions/${id}/answer`, payload);
      inflight = false;
      qaDrafts.delete(`${id}|${ident}`);
      if (said) toast(said);
      shown = "";
      hold = setTimeout(settle, 2500);  // stays busy until the screen it led to is shown, so a second press can't land on the old one
      onSent(payload);
    } catch (error) { inflight = false; settle(); explain(error); }
  };
  const real = () => (dialog.steps || []).filter((s) => !s.submit);
  const wordsOf = (o) => { const kept = draft().words[o.n]; return kept !== undefined ? kept : o.value || ""; };
  const typeRow = () => dialog.options.find((o) => o.text === "type");
  const toggle = (n) => { const picks = draft().picks; if (picks.has(n)) picks.delete(n); else picks.add(n); draw(); };
  const next = () => {
    const row = typeRow();
    send({ picks: [...draft().picks], text: row ? wordsOf(row).trim() : undefined, next: true }, dialog.next ? null : "Ticks sent");
  };
  const step = (i) => { if (dialog.step != null && i !== dialog.step && i >= 0 && i < dialog.steps.length) send({ step: i }); };
  const choose = (o) => {
    if (dialog.multi) { if (o.text === "type") focusWords(o); else toggle(o.n); return; }
    if (o.text === "type" && !wordsOf(o).trim()) { focusWords(o); return; }
    send({ choice: o.n }, `Chose ${o.label}`);
  };
  const focusWords = (o) => { const input = el.querySelector(`[data-qa="t${o.n}"]`); if (input) input.focus(); };

  const optionButton = (o) => {
    const multi = dialog.multi;
    const on = multi ? draft().picks.has(o.n) : !!o.checked;
    return h("button", { type: "button", class: "qa-opt", role: multi ? "checkbox" : "radio", "aria-checked": on ? "true" : "false", "data-qa": `o${o.n}`, onclick: () => choose(o) },
      multi ? h("span", { class: "qa-box", "aria-hidden": "true" }, uiIcon("check")) : h("span", { class: "qa-n", "aria-hidden": "true", textContent: o.n }),
      h("span", { class: "qa-text" }, h("span", { class: "qa-label", dir: "auto", textContent: o.label }), o.description ? h("span", { class: "qa-desc", dir: "auto", textContent: o.description }) : null),
      multi ? h("kbd", { class: "qa-key", "aria-hidden": "true", textContent: o.n <= 9 ? o.n : "" }) : on ? h("span", { class: "qa-on", "aria-hidden": "true" }, uiIcon("check")) : null);
  };
  // A row that takes words: the words are its answer. In a multiple choice they tick it; elsewhere Enter sends them.
  const wordsRow = (o) => {
    const multi = dialog.multi;
    const hint = o.value || o.label === "Type something" ? "Type your own answer" : o.label;
    const input = h("input", { type: "text", class: "qa-input", value: wordsOf(o), placeholder: hint, "aria-label": `${hint}, option ${o.n}`,
      "data-qa": `t${o.n}`, enterkeyhint: multi ? "done" : "send", autocomplete: "off", autocapitalize: "sentences", spellcheck: true, maxLength: 2000 });
    const go = multi ? null : h("button", { type: "button", class: "qa-go", title: "Send", "aria-label": "Send your answer", disabled: !input.value.trim() }, uiIcon("send"));
    const box = multi ? h("span", { class: "qa-box", "aria-hidden": "true" }, uiIcon("check")) : h("span", { class: "qa-n", "aria-hidden": "true", textContent: o.n });
    const row = h("div", { class: "qa-opt qa-words", "data-on": input.value.trim() ? "1" : "0" }, box, input, go);
    const sendWords = () => { const words = input.value.trim(); if (multi) { next(); return; } if (!words) { input.focus(); return; } send({ choice: o.n, text: words }, "Sent"); };
    input.addEventListener("input", () => { draft().words[o.n] = input.value; row.dataset.on = input.value.trim() ? "1" : "0"; if (go) go.disabled = !input.value.trim(); });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); sendWords(); } });
    if (go) go.onclick = sendWords;
    row.addEventListener("click", (e) => { if (e.target === row || e.target === box) input.focus(); });
    return row;
  };

  const draw = () => {
    const d = dialog;
    const had = el.contains(document.activeElement) ? document.activeElement.dataset.qa : null;
    const steps = d.steps || [];
    const asks = real();
    const known = d.step != null;
    const nav = steps.length > 1 ? h("nav", { class: "qa-steps", "aria-label": "Questions" }, steps.map((s, i) => {
      const label = s.submit ? "Review" : s.label;
      const kids = [s.done ? h("span", { class: "qa-done", "aria-hidden": "true" }, uiIcon("check")) : null, h("span", { textContent: label })];
      const name = `${label}${s.done ? ", answered" : s.submit ? "" : ", not answered yet"}`;
      return known ? h("button", { type: "button", class: "qa-step", "data-qa": `s${i}`, "aria-current": i === d.step ? "step" : null, "aria-label": name, onclick: () => step(i) }, kids)
        : h("span", { class: "qa-step", "aria-label": name }, kids);
    })) : null;
    const count = d.kind === "review" ? null : asks.length > 1 && known && d.step < asks.length ? h("p", { class: "qa-count", textContent: `Question ${d.step + 1} of ${asks.length}` }) : null;
    const lead = d.kind === "permission" && asking && asking !== d.question ? h("p", { class: "qa-lead", dir: "auto", textContent: asking }) : null;
    const detail = !d.detail ? null : d.kind === "plan" ? h("div", { class: "qa-detail qa-plan", tabindex: "0", "aria-label": "Claude's plan" }, markdown(d.detail))
      : h("pre", { class: "qa-detail", tabindex: "0", "aria-label": d.kind === "permission" ? "What Claude asks to do" : "Details", dir: "auto", textContent: d.detail });
    const question = d.question ? h("p", { class: "qa-q", id: qid, dir: "auto", textContent: d.question }) : null;
    let body;
    if (d.kind === "review") {
      body = [
        d.warning ? h("p", { class: "qa-warn", role: "note" }, h("span", { class: "qa-warn-dot", "aria-hidden": "true" }), d.warning) : null,
        d.review && d.review.length ? h("dl", { class: "qa-review" }, d.review.map((r) => [h("dt", { dir: "auto", textContent: r.question }), h("dd", { dir: "auto", textContent: r.answer || "Not answered" })])) : null,
        h("div", { class: "qa-actions" }, d.options.map((o) => h("button", { type: "button", class: `btn big${o.n === 1 ? " primary" : ""}`, "data-qa": `o${o.n}`, onclick: () => send({ choice: o.n }, o.n === 1 ? "Answers sent" : `Chose ${o.label}`) },
          !compact && o.n <= 9 ? h("kbd", { "aria-hidden": "true", textContent: o.n }) : null, o.label))),
      ];
    } else if (d.kind === "menu") {
      body = h("div", { class: "qa-list", role: "group", "aria-labelledby": question ? qid : null, "aria-label": question ? null : "Choices" },
        d.rows.map((r) => h("button", { type: "button", class: "qa-opt", "data-qa": `r${r.row}`, "aria-current": r.row === d.cursor ? "true" : null, onclick: () => send({ row: r.row }, `Chose ${r.label}`) },
          h("span", { class: "qa-n", "aria-hidden": "true", textContent: r.row === d.cursor ? "❯" : "" }), h("span", { class: "qa-text" }, h("span", { class: "qa-label", dir: "auto", textContent: r.label })))));
    } else {
      const main = d.options.filter((o) => !o.apart);
      const apart = d.options.filter((o) => o.apart);
      const amend = d.kind === "permission" ? d.options.find((o) => o.n === d.text_option && o.text === "amend") : null;
      const words = amend ? h("input", { type: "text", class: "qa-input", "data-qa": `a${amend.n}`, placeholder: "Or tell Claude what to do instead", "aria-label": `${amend.label}, and tell Claude what to do instead`,
        value: draft().words[amend.n] || "", enterkeyhint: "send", autocomplete: "off", autocapitalize: "sentences", maxLength: 2000 }) : null;
      const amendGo = amend ? h("button", { type: "button", class: "qa-go", title: "Send", "aria-label": `${amend.label}, with your words`, disabled: !words.value.trim() }, uiIcon("send")) : null;
      if (amend) {
        const sendAmend = () => { const text = words.value.trim(); if (!text) { words.focus(); return; } send({ choice: amend.n, text }, "Sent"); };
        words.addEventListener("input", () => { draft().words[amend.n] = words.value; amendGo.disabled = !words.value.trim(); });
        words.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); sendAmend(); } });
        amendGo.onclick = sendAmend;
      }
      body = [
        h("div", { class: "qa-list", role: d.multi ? "group" : "radiogroup", "aria-labelledby": question ? qid : null, "aria-label": question ? null : "Choices" },
          main.map((o) => o.text === "type" ? wordsRow(o) : optionButton(o))),
        amend ? h("div", { class: "qa-opt qa-words qa-amend", title: `${amend.label}, with your words` }, words, amendGo) : null,
        d.multi ? h("div", { class: "qa-actions" }, h("button", { type: "button", class: "btn big primary qa-next", "data-qa": "next", onclick: next },
          d.next && d.next.label === "Submit" ? "Submit" : (d.next ? d.next.label : "Save ticks"), !compact ? h("kbd", { "aria-hidden": "true", textContent: "↵" }) : null)) : null,
        apart.length || (d.rows || []).length ? h("div", { class: "qa-apart" },
          apart.map((o) => h("button", { type: "button", class: "qa-quiet", "data-qa": `o${o.n}`, onclick: () => send({ choice: o.n }, `Chose ${o.label}`) }, o.label)),
          (d.rows || []).map((r) => h("button", { type: "button", class: "qa-quiet", "data-qa": `r${r.row}`, onclick: () => send({ row: r.row }, `Chose ${r.label}`) }, r.label))) : null,
      ];
    }
    el.dataset.kind = d.kind;
    fill(el, nav, count, lead, detail, question, body);
    if (had) {
      const again = el.querySelector(`[data-qa="${CSS.escape(had)}"]`);
      if (again) { again.focus({ preventScroll: true }); if (again.matches("input")) again.setSelectionRange(again.value.length, again.value.length); }
      else focusFirst();  // the next question: the keys stay with the panel
    }
  };

  const focusFirst = () => {
    const first = el.querySelector('.qa-opt[aria-checked="true"], .qa-list [data-qa], .qa-actions [data-qa]');
    if (first) first.focus({ preventScroll: true });
  };
  // Desk keys: digits choose (or tick), ↑ ↓ move, ← → open the question before or after, Enter sends or moves on.
  const focusables = () => [...el.querySelectorAll(".qa-list [data-qa], .qa-amend [data-qa], .qa-actions [data-qa], .qa-apart [data-qa]")];
  const key = (e) => {
    if (!dialog || busy || e.metaKey || e.ctrlKey || e.altKey) return false;
    const typing = e.target && e.target.matches && e.target.matches("input, textarea") && el.contains(e.target);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      const all = focusables();
      if (!all.length) return false;
      const at = all.indexOf(document.activeElement);
      const to = at < 0 ? (e.key === "ArrowDown" ? 0 : all.length - 1) : Math.max(0, Math.min(all.length - 1, at + (e.key === "ArrowDown" ? 1 : -1)));
      all[to].focus();
      return true;
    }
    if (typing) {
      if (e.key === "Escape" && e.target.value === "") { e.target.blur(); el.focus?.(); return false; }
      return false;
    }
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && dialog.steps && dialog.steps.length > 1 && dialog.step != null) { step(dialog.step + (e.key === "ArrowRight" ? 1 : -1)); return true; }
    if (/^[1-9]$/.test(e.key)) {
      const o = dialog.options.find((x) => x.n === Number(e.key));
      if (!o) return false;
      if (dialog.kind === "review") send({ choice: o.n }, o.n === 1 ? "Answers sent" : `Chose ${o.label}`);
      else if (o.text === "amend" && dialog.kind === "permission") send({ choice: o.n }, `Chose ${o.label}`);
      else choose(o);
      return true;
    }
    if (e.key === "Enter" && dialog.multi && !(document.activeElement && el.contains(document.activeElement) && document.activeElement.matches("button"))) { next(); return true; }
    return false;
  };
  el.addEventListener("keydown", (e) => { if (key(e)) { e.preventDefault(); e.stopPropagation(); } });

  return {
    el, key,
    has: () => !!dialog,
    clear() { dialog = null; shown = ""; inflight = false; settle(); },
    // Draws only what changed on screen: the same dialog read again draws nothing, so nothing jumps or loses focus.
    show(next_, asking_ = "") {
      const sign = JSON.stringify([next_, asking_]);
      if (sign === shown) return false;
      shown = sign; dialog = next_; asking = asking_;
      const fixed = next_.options.filter((o) => o.text !== "type" && !o.value).map((o) => o.label);
      ident = JSON.stringify([next_.kind, next_.step, next_.question, fixed]);
      const dr = draft();
      if (next_.multi && !dr.picks) dr.picks = new Set(next_.options.filter((o) => o.checked && !o.text && !o.apart).map((o) => o.n));
      if (!inflight) settle();
      draw();
      return true;
    },
    focus() { if (dialog) focusFirst(); },
  };
}

// ── Peek: the last reply or question beside the sidebar row, with a reply box. Space on a row opens it. ──
const reviewNotes = new Map();  // line comments not yet sent, per session, kept while the page is open
let peekOpen = null;
const closePeek = (refocus = true) => {
  if (!peekOpen) return;
  const { box, id, timer, away, onkey } = peekOpen;
  peekOpen = null;
  clearInterval(timer);
  document.removeEventListener("mousedown", away, true);
  document.removeEventListener("keydown", onkey, true);
  box.remove();
  const row = side.querySelector(`[data-sid="${CSS.escape(id)}"] a`);
  if (refocus && row && row.offsetParent) row.focus({ preventScroll: true });
};
window.hubPeek = (id) => {
  if (peekOpen && peekOpen.id === id) { closePeek(); return; }
  closePeek(false);
  const s0 = session(id);
  if (!s0) return;
  const orb = newOrb(orbState(s0), 16);
  const title = h("b", { dir: "auto", textContent: s0.title });
  const when = h("span", { class: "peek-when" });
  const body = h("div", { class: "peek-body", tabindex: "-1" });
  const choices = h("div", { class: "peek-choices", role: "group" });
  const input = h("textarea", { rows: 1, placeholder: "Reply", "aria-label": `Reply to ${s0.title}`, enterkeyhint: "send" });
  const hint = h("div", { class: "peek-keys" });
  const form = h("div", { class: "peek-reply" }, input);
  const open = h("a", { class: "icon", href: `#/s/${id}`, title: "Open session", "aria-label": "Open session", onclick: () => closePeek(false) }, uiIcon("corner"));
  const box = h("div", { class: "peek-pop", role: "dialog", "aria-label": `Peek: ${s0.title}`, tabindex: "-1" },
    h("header", {}, orb, h("span", { class: "peek-title" }, title, when), open, h("button", { class: "icon", title: "Close", "aria-label": "Close", onclick: () => closePeek() }, uiIcon("close"))),
    body, choices, form, hint);
  document.body.append(box);
  let data = null, sending = false, shownKey = "";
  const panel = questionPanel(id, { compact: true, onSent: async () => { await tick(); await load(true); setTimeout(() => peekOpen && peekOpen.box === box && load(true), 700); } });
  const place = () => {
    const row = side.querySelector(`[data-sid="${CSS.escape(id)}"]`);
    box.classList.toggle("sheet", phone.matches || !row || !row.offsetParent);
    if (box.classList.contains("sheet")) { box.style.left = box.style.top = ""; return; }
    const r = row.getBoundingClientRect();
    box.style.left = `${Math.round(r.right + 8)}px`;
    box.style.top = `${Math.round(Math.max(8, Math.min(r.top - 8, window.innerHeight - box.offsetHeight - 32)))}px`;
  };
  const answer = async (payload, label) => {
    if (sending) return;
    sending = true; box.setAttribute("aria-busy", "true");
    try {
      await api(`/api/sessions/${id}/answer`, payload);
      toast(label);
      input.value = ""; fit();
      await tick();
      await load(true);
    } catch (error) { explain(error); } finally { sending = false; box.removeAttribute("aria-busy"); }
  };
  const fit = () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 120)}px`; };
  input.addEventListener("input", fit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); const text = input.value.trim(); if (text) answer({ text }, "Sent"); }
  });
  const draw = () => {
    const s = session(id) || s0;
    setOrb(orb, orbState(s));
    box.dataset.state = s.state;
    title.textContent = s.title;
    const word = s.state === "working" ? (s.activity && /using|searching/.test(s.orb || "") ? "Working" : ORB_WORDS[s.orb] || "Working") : s.state === "error" ? "Error" : DOT_WORDS[shownState(s)] || "";
    fill(when, word, s.state === "working" && s.turn ? [" · ", turnClock(s.turn.since)] : null);
    if (!data) return;
    const key = JSON.stringify([data.text, data.dialog, data.options, data.error, data.live, s.state, s.asking, s.activity]);
    if (key === shownKey) return;
    shownKey = key;
    const options = data.dialog ? [] : data.options || [];
    if (data.dialog) {  // a choice on screen: the panel draws it, and draws again only what changed
      panel.show(data.dialog, s.asking);
      if (body.childNodes.length !== 1 || body.firstChild !== panel.el) fill(body, panel.el);
      fill(choices); choices.hidden = true;
      form.hidden = true;
      const many = (data.dialog.steps || []).length > 1 && data.dialog.step != null;
      const top = Math.min(9, data.dialog.options.length);
      fill(hint, top ? h("span", {}, h("kbd", { textContent: top > 1 ? `1–${top}` : "1" }), data.dialog.multi ? " tick" : " choose") : null, many ? h("span", {}, h("kbd", { textContent: "← →" }), " questions") : null,
        data.dialog.multi ? h("span", {}, h("kbd", { textContent: "↵" }), ` ${(data.dialog.next || {}).label || "next"}`.toLowerCase()) : null, h("span", {}, h("kbd", { textContent: "esc" }), " close"));
      hint.hidden = false;
      place();
      return;
    }
    panel.clear();
    const lead = s.state === "error" ? h("p", { class: "peek-ask err", dir: "auto", textContent: s.error })
      : s.state === "needs" && s.asking && !data.text.includes(s.asking) ? h("p", { class: "peek-ask", dir: "auto", textContent: s.asking }) : null;
    // Options that become buttons below aren't repeated in the text above them.
    const text = !data.dialog && options.length ? data.text.split("\n").filter((line) => !options.some((o) => new RegExp(`^\\s*${o.n}[.)]\\s`).test(line))).join("\n").trim() : data.text;
    const said = text && !data.dialog ? h("div", { class: "peek-said" }, markdown(text)) : null;
    const doing = s.state === "working" && s.activity ? h("p", { class: "peek-doing" }, h("span", { textContent: s.activity.tool }), " ", h("code", { textContent: s.activity.target })) : null;
    fill(body, lead, said, doing, !lead && !said && !doing ? h("div", { class: "empty-line", textContent: "Nothing said yet." }) : null);
    fill(choices, options.map((o) => h("button", { type: "button", class: "peek-choice", onclick: () => answer({ choice: o.n }, `Answered ${o.n}`) }, h("kbd", { textContent: o.n }), h("span", { dir: "auto", textContent: o.label }))),
      s.state === "error" ? h("button", { type: "button", class: "btn", onclick: once("Clearing…", async () => { await api(`/api/sessions/${id}/clear`, {}); await tick(); }) }, "Clear") : null);
    choices.hidden = !choices.childNodes.length;
    form.hidden = !data.live || !!data.dialog;
    fill(hint, h("span", {}, h("kbd", { textContent: "↵" }), " send"), options.length ? h("span", {}, h("kbd", { textContent: options.length > 1 ? `1–${options.length}` : "1" }), " choose") : null, h("span", {}, h("kbd", { textContent: "esc" }), " close"));
    hint.hidden = form.hidden && !options.length;
    if (form.hidden) fill(hint, options.length ? h("span", {}, h("kbd", { textContent: `1–${options.length}` }), " choose") : null, h("span", {}, h("kbd", { textContent: "esc" }), " close"));
    body.scrollTop = body.scrollHeight;
    place();
  };
  const load = async (quiet) => {
    try { data = await api(`/api/sessions/${id}/peek`); shownKey = quiet ? shownKey : ""; draw(); }
    catch (error) { if (!data) { fill(body, retryLine("This session didn't load.", () => load())); place(); } }
  };
  const away = (e) => { if (!box.contains(e.target) && !e.target.closest?.(`[data-sid="${CSS.escape(id)}"]`)) closePeek(false); };
  const onkey = (e) => {
    if (!box.contains(document.activeElement) && document.activeElement !== document.body) return;
    if (e.key !== "Escape" && data && data.dialog && panel.key(e)) { e.preventDefault(); e.stopPropagation(); return; }
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closePeek(); return; }
    if (data && data.dialog) return;
    const typing = document.activeElement === input;
    const options = (data && data.options) || [];
    if (!typing && /^[1-9]$/.test(e.key) && Number(e.key) <= options.length && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); e.stopPropagation(); answer({ choice: Number(e.key) }, `Answered ${e.key}`); return; }
    if (!typing && !form.hidden && e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) { input.focus(); }  // the key lands in the reply
  };
  document.addEventListener("mousedown", away, true);
  document.addEventListener("keydown", onkey, true);
  peekOpen = { box, id, away, onkey, draw, timer: setInterval(() => { if (document.activeElement !== input || !input.value) load(true); }, 3000) };
  draw(); place();
  box.focus({ preventScroll: true });
  load().then(() => {
    if (!peekOpen || peekOpen.box !== box) return;
    if (data && data.dialog) { if (!phone.matches) panel.focus(); }
    else if (!(data && data.options && data.options.length) && !form.hidden) input.focus({ preventScroll: true });
  });
};
window.addEventListener("resize", () => peekOpen && peekOpen.draw && (peekOpen.box.style.top = "", peekOpen.draw()));
window.addEventListener("hashchange", () => closePeek(false));

// On a phone a Claude session opens as a chat unless you last chose its terminal.
// A phone opens a Claude session as a chat; a desktop as its terminal. Each remembers the other choice once you make it.
const viewKey = () => phone.matches ? "phoneView" : "deskView";
const chatting = (s) => s.kind === "claude" && saved.get(viewKey(), phone.matches ? "chat" : "terminal") === "chat";
const pressKey = guard(async (id, key) => { await api(`/api/sessions/${id}/key`, { key }); });

// ── Session page: one terminal, or up to four in nested splits, side by side and stacked ──
function pageSession(startLayout) {
  let layout = startLayout, ids = leavesOf(layout);
  const stage = h("div", { class: "stage" });
  const panes = h("div", { class: "panes" });
  const sharedBox = h("aside", { class: "shared" });
  stage.append(panes);
  view.append(stage);
  const entries = new Map();
  let sharedKey = "", activeId = null, painted = false;
  // The right panel is kept per session: open or not, and how wide. A session you never set takes the last choice you made.
  const PANEL = { min: 240, max: 560, start: 316 };
  const panelFor = (id) => ({ on: saved.get("shared", window.innerWidth > 1100), w: saved.get("panelW", PANEL.start), ...(saved.get("panelBy", {})[id] || {}) });
  const keepPanel = (id, change) => {
    const all = saved.get("panelBy", {});
    delete all[id];
    all[id] = { ...panelFor(id), ...change };
    const ids = Object.keys(all);
    ids.slice(0, Math.max(0, ids.length - 60)).forEach((old) => delete all[old]);  // the newest sixty are plenty
    saved.set("panelBy", all);
    if ("on" in change) saved.set("shared", change.on);
    if ("w" in change) saved.set("panelW", change.w);
  };
  // On a phone the panel covers the conversation, so it starts shut there whatever the desk chose, and opening it
  // on the phone lasts for this page only: the desk's choice (shared, panelBy) is left as it was.
  let phonePanel = false;
  const panelOn = () => phone.matches ? phonePanel : panelFor(activeId).on;
  const panelEdge = h("div", { class: "panel-edge", role: "separator", tabindex: 0, "aria-orientation": "vertical", "aria-label": "Resize the panel", "aria-valuemin": PANEL.min, "aria-valuemax": PANEL.max, title: "Drag to resize, double-click to reset" });
  stage.append(panelEdge);
  const showWidth = (w) => { stage.style.setProperty("--shared-w", `${w}px`); panelEdge.setAttribute("aria-valuenow", w); };
  const applyPanel = () => showWidth(panelFor(activeId).w);
  const togglePanel = () => { if (phone.matches) phonePanel = !phonePanel; else keepPanel(activeId, { on: !panelOn() }); applyPanel(); drawShared(true); drawTop(); };
  let panelW = 0;
  // Dragging it narrower than it can be closes it; p or the panel button brings it back at the width it had.
  dragEdge(panelEdge, {
    move: (x) => {
      const w = stage.getBoundingClientRect().right - x;
      if (w < PANEL.min - 64) { panelW = 0; if (panelOn()) togglePanel(); return; }
      panelW = Math.round(Math.min(PANEL.max, Math.max(PANEL.min, w)));
      showWidth(panelW);
    },
    end: () => { if (panelW) keepPanel(activeId, { w: panelW }); panelW = 0; },
    reset: () => { keepPanel(activeId, { w: PANEL.start }); applyPanel(); },
    step: (by) => { const w = Math.min(PANEL.max, Math.max(PANEL.min, panelFor(activeId).w - by)); keepPanel(activeId, { w }); applyPanel(); },
  });
  // A file picker for phones, where nothing can be dragged. It sits outside the panel because the panel redraws.
  const picker = h("input", { type: "file", multiple: true, hidden: true, "aria-label": "Share a file", onchange: guard(async (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    if (!files.length) return;
    toast(`Sharing ${files.length === 1 ? files[0].name : `${files.length} files`}…`);
    await shareFiles(activeId, files);
    hideToast();
  }) });
  stage.append(picker);
  // The right panel always belongs to the pane you last clicked or typed in.
  const setActive = (id) => {
    if (id === activeId) return;
    activeId = id;
    entries.forEach((entry, key) => entry.pane.classList.toggle("active", key === id));
    showOnPhone();
    imagesSeen = null;
    applyPanel();
    if (painted) { drawRail(true); drawShared(true); drawTop(); }
  };
  // ── The layout: splits inside splits, with a gutter between each two parts. Panes move from one layout to the next
  // without being rebuilt, so every terminal that stays on screen stays connected. On a phone one pane shows at a time. ──
  const MIN_PANE = { h: 200, v: 120 };  // what a pane keeps, in pixels, while a gutter is dragged
  const switcher = h("div", { class: "pane-switch", role: "tablist", "aria-label": "Sessions in this split" });
  const refitAll = () => entries.forEach((entry) => entry.terminal && entry.terminal.refit());
  const applySizes = () => {
    panes.querySelectorAll(".layout-split").forEach((box) => {
      const node = box.splitNode;
      [...box.children].filter((el) => !el.classList.contains("gutter")).forEach((el, i) => { el.style.flex = `${node.z[i]} 1 0px`; });
      [...box.children].filter((el) => el.classList.contains("gutter")).forEach((g, i) => g.setAttribute("aria-valuenow", Math.round((100 * node.z[i]) / (node.z[i] + node.z[i + 1]))));
    });
  };
  const evenOut = (node) => { node.z = even(node.k.length); applySizes(); keepSizes(layout); refitAll(); };
  const gutterIn = (node, i) => {
    const across = node.d === "h";
    const g = h("div", { class: `gutter ${across ? "vertical" : "horizontal"}`, role: "separator", tabindex: 0, "aria-orientation": across ? "vertical" : "horizontal",
      "aria-label": across ? "Resize the panes beside each other" : "Resize the panes above and below", "aria-valuemin": 10, "aria-valuemax": 90, title: "Drag to resize. Double-click to even out." });
    // Terminals resize once, when the drag ends, so a drag never floods the sessions with size changes.
    g.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      g.setPointerCapture(e.pointerId);
      const a = g.previousElementSibling.getBoundingClientRect(), b = g.nextElementSibling.getBoundingClientRect();
      const start = across ? a.left : a.top, room = (across ? b.right : b.bottom) - start - (across ? g.offsetWidth : g.offsetHeight);
      const pair = node.z[i] + node.z[i + 1], least = Math.min(MIN_PANE[node.d], room / 2);
      document.body.classList.add("resizing");
      g.classList.add("dragging");
      const move = (m) => {
        const first = Math.min(room - least, Math.max(least, (across ? m.clientX : m.clientY) - start));
        node.z[i] = (pair * first) / room; node.z[i + 1] = pair - node.z[i];
        applySizes();
      };
      g.addEventListener("pointermove", move);
      g.addEventListener("lostpointercapture", () => {
        g.removeEventListener("pointermove", move);
        document.body.classList.remove("resizing");
        g.classList.remove("dragging");
        keepSizes(layout);
        refitAll();
      }, { once: true });
    });
    g.addEventListener("dblclick", () => evenOut(node));
    g.addEventListener("keydown", (e) => {
      const [less, more] = across ? ["ArrowLeft", "ArrowRight"] : ["ArrowUp", "ArrowDown"];
      const pair = node.z[i] + node.z[i + 1];
      if (e.key === "Enter") { node.z[i] = node.z[i + 1] = pair / 2; }
      else if (e.key === less || e.key === more) {
        const share = Math.min(0.9, Math.max(0.1, Math.round((node.z[i] / pair + (e.key === more ? 0.05 : -0.05)) * 20) / 20));
        node.z[i] = pair * share; node.z[i + 1] = pair - node.z[i];
      } else return;
      e.preventDefault();
      applySizes();
      keepSizes(layout);
      refitAll();
    });
    return g;
  };
  const drawSwitcher = () => {
    if (!phone.matches || ids.length < 2) return;
    const shown = ids.map((id) => { const s = session(id); return [id, s ? bareTitle(s) : "Session", s ? shownState(s) : "ended", id === activeId]; });
    if (!differs(switcher, JSON.stringify(shown))) return;
    fill(switcher, shown.map(([id, title, state, on]) => h("button", { type: "button", role: "tab", class: on ? "on" : "", "aria-selected": on ? "true" : "false", title,
      onclick: () => { setActive(id); focusPane(ids.indexOf(id)); } }, dot(state), h("span", { dir: "auto", textContent: title }))));
    const on = switcher.querySelector(".on");  // the chosen one stays in view, without scrolling the page
    requestAnimationFrame(() => { if (on && (on.offsetLeft < switcher.scrollLeft || on.offsetLeft + on.offsetWidth > switcher.scrollLeft + switcher.clientWidth)) switcher.scrollLeft = on.offsetLeft - 8; });
  };
  const showOnPhone = () => {
    if (!phone.matches) return;
    ids.forEach((id) => entries.get(id).pane.classList.toggle("away", ids.length > 1 && id !== activeId));
    drawSwitcher();
  };
  const arrange = () => {
    const had = panes.contains(document.activeElement) ? document.activeElement : null;
    panes.classList.toggle("multi", ids.length > 1);
    panes.classList.toggle("many", ids.length > 2);
    if (phone.matches) {
      panes.replaceChildren(...(ids.length > 1 ? [switcher] : []), ...ids.map((id) => { const pane = entries.get(id).pane; pane.style.flex = ""; return pane; }));
      showOnPhone();
    } else {
      const place = (node) => {
        if (!isSplit(node)) { const pane = entries.get(node).pane; pane.classList.remove("away"); return pane; }
        const box = h("div", { class: `layout-split ${node.d === "h" ? "across" : "down"}` });
        box.splitNode = node;
        node.k.forEach((kid, i) => { if (i) box.append(gutterIn(node, i - 1)); box.append(place(kid)); });
        return box;
      };
      const root = place(layout);
      panes.replaceChildren(root);
      root.style.flex = "1 1 0px";
      applySizes();
    }
    if (had && !panes.contains(document.activeElement) && had.isConnected) had.focus({ preventScroll: true });
  };
  const onPhoneChange = () => { phonePanel = false; arrange(); refitAll(); if (painted) { drawShared(true); drawTop(); } };
  phone.addEventListener("change", onPhoneChange);

  const shareFiles = async (sid, files) => {
    const terminal = entries.get(sid) && entries.get(sid).terminal;
    if (!terminal || !files.length) return;
    const many = files.length > 1;
    if (files.some((f) => f.size > 2e6)) toast(many ? `Uploading ${files.length} files…` : `Uploading ${files[0].name || "the file"}…`);
    for (const picked of files) {
      const file = await asJpeg(picked);
      const done = await upload(`/api/sessions/${sid}/upload?name=${encodeURIComponent(file.name || "pasted.png")}`, file);
      terminal.send({ t: "i", d: done.path.replace(/ /g, "\\ ") + " " });
    }
    if (entries.get(sid)) closeReader(entries.get(sid), false);
    if (toastEl.classList.contains("show") && !toastEl.classList.contains("sticky")) toast(many ? `${files.length} files are in the prompt.` : "The file is in the prompt.");
    terminal.term.focus();
  };
  // An iPhone photo can arrive as HEIC, which Claude can't read: Safari can draw it, so it goes up as a JPEG. A photo of
  // several megabytes is drawn smaller too: Claude doesn't see more than about 2,000 pixels, and a phone's upload is slow.
  const asJpeg = async (file) => {
    const heic = /heic|heif/i.test(file.type) || /\.(heic|heif)$/i.test(file.name || "");
    const big = /^image\/(jpeg|png|webp)$/i.test(file.type) && file.size > 2.5e6;
    if (!heic && !big) return file;
    try {
      const url = URL.createObjectURL(file), img = new Image();
      img.src = url;
      await img.decode();
      const scale = Math.min(1, (heic && !big ? 3000 : 2400) / Math.max(img.naturalWidth, img.naturalHeight)), canvas = document.createElement("canvas");
      canvas.width = Math.round(img.naturalWidth * scale); canvas.height = Math.round(img.naturalHeight * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      const blob = await new Promise((done) => canvas.toBlob(done, "image/jpeg", 0.9));
      return blob ? new File([blob], (file.name || "photo").replace(/\.(heic|heif|jpe?g|png|webp)$/i, "") + ".jpg", { type: "image/jpeg" }) : file;
    } catch { return file; }
  };
  // On a phone there's no dragging and little pasting: a button opens the photo library, the camera or Files.
  const attachButton = (id) => {
    const input = h("input", { type: "file", multiple: true, hidden: true, onchange: () => { const files = [...input.files]; input.value = ""; guard(shareFiles)(id, files); } });
    return h("button", { type: "button", class: "attach", title: "Share a photo or file with this session", "aria-label": "Attach", onclick: () => input.click() }, uiIcon("clip"), input);
  };
  const build = (id) => {
    const s = session(id);
    if (!(id in saved.get("panelBy", {}))) keepPanel(id, {});  // a pane on screen has been seen: from now on it keeps its own panel
    const head = h("div", { class: "pane-top", "data-drag-sid": id, "data-drag-pane": "" });
    const pane = h("div", { class: "pane", "data-sid": id, role: "group", "aria-label": s ? s.title : "Session" }, head);
    const entry = { id, head, pane, stopping: false, terminal: null };
    entries.set(id, entry);
    head.addEventListener("click", (e) => { if (entry.terminal && !e.target.closest("button, a")) entry.terminal.term.focus(); });
    pane.addEventListener("focusin", () => setActive(id));
    pane.addEventListener("pointerdown", () => setActive(id), true);
    if (s && s.alive) {
      const terminal = openTerminal(s);
      entry.terminal = terminal;
      terminal.onlink = () => drawHead(entry);
      entry.strip = s.kind === "claude" ? h("div", { class: "pane-strip", role: "status", hidden: true }) : null;
      if (chatting(s)) {
        terminal.held = true;
        pane.classList.add("chatting");
        pane.append(terminal.host, entry.strip || "");
        openChat(entry);
        return pane;
      }
      if (s.kind === "claude") {
        terminal.onScrollIntent = () => { if (!phone.matches) return false; openReader(entry); return true; };
        entry.readToggle = h("button", { type: "button", class: "read-toggle", textContent: "Read", onclick: () => entry.reader ? closeReader(entry) : openReader(entry) });
      }
      pane.append(terminal.host, entry.strip || "", h("div", { class: "drop-hint" }, h("span", { textContent: "Share with this session" })),
        h("div", { class: "keys" }, entry.readToggle || null, attachButton(id), [["Esc", "\x1b"], ["Tab", "\t"], ["↑", "\x1b[A"], ["↓", "\x1b[B"], ["⇧Tab", "\x1b[Z"], ["^C", "\x03"], ["Enter", "\r"]].map(([label, data]) =>
          h("button", { type: "button", textContent: label, onclick: () => { closeReader(entry, false); terminal.send({ t: "i", d: data }); terminal.term.focus(); } }))));
      terminal.host.addEventListener("paste", (e) => { const files = [...(e.clipboardData ? e.clipboardData.files : [])]; if (files.length) { e.preventDefault(); e.stopPropagation(); guard(shareFiles)(id, files); } }, true);
      pane.addEventListener("dragover", (e) => { if (!entry.terminal) return; e.preventDefault(); pane.classList.add("dropping"); });
      pane.addEventListener("dragleave", (e) => { if (!pane.contains(e.relatedTarget)) pane.classList.remove("dropping"); });
      pane.addEventListener("drop", (e) => { e.preventDefault(); pane.classList.remove("dropping"); guard(shareFiles)(id, [...e.dataTransfer.files]); });
    } else { entry.missing = !s; head.hidden = !s; showEnded(entry); }
    return pane;
  };
  const showEnded = (entry) => {
    const s = session(entry.id);
    if (s && s.kind === "claude") showRecord(entry); else showNote(entry);
  };
  // One turn of a conversation, as the record and the phone's reader draw it.
  // A file shared through the hub goes in as its path under uploads/: what you said shows it as a picture or its name, not the path.
  const UPLOADED = /(?:^|\s)(\/\S*?\/uploads\/[0-9a-f]{8}\/(?:\\ |\S)+)/g;
  const youTurn = (id, text, media) => {
    const shared = [...text.matchAll(UPLOADED)].map((m) => m[1].replace(/\\ /g, " "));
    const said = shared.length ? text.replace(UPLOADED, "").trim() : text;
    // An upload the server found as a picture, video, recording or PDF shows as one, like a pasted picture; the rest by name.
    const shown = (media || []).filter((m) => m.path).map((m) => m.path.split("/").pop());
    const rest = shared.filter((path) => !shown.includes(path.split("/").pop()));
    return h("div", { class: "turn you", role: "group", "aria-label": "You said" }, said ? h("div", { class: "said", dir: "auto" }, inline(said, { sid: id })) : null,
      mediaBlock(id, media),
      rest.length ? h("div", { class: "you-files" }, rest.map((path) => {
        const name = path.split("/").pop().replace(/^[0-9a-f]{4}-/, "");
        return kindOf(path) === "image" ? h("button", { type: "button", class: "you-shot", title: name, onclick: () => openPreview({ sid: id, path, name }) }, h("img", { src: thumbUrl(id, { path }), alt: name, loading: "lazy" }))
          : h("button", { type: "button", class: "you-file", onclick: () => openPreview({ sid: id, path, name }) }, uiIcon("clip"), h("span", { dir: "auto", textContent: name }));
      })) : null);
  };
  // Turns are kept by what they hold, so a redraw reuses the ones that didn't change (and a video keeps playing).
  const turnKept = new Map();
  const recordTurn = (id) => (item, i) => {
    const key = `${id}\n${i}\n${JSON.stringify(item)}`;
    if (turnKept.has(key)) return turnKept.get(key);
    const node = drawTurn(id, item);
    if (turnKept.size > 4000) turnKept.clear();
    turnKept.set(key, node);
    return node;
  };
  const drawTurn = (id, item) => item.kind === "you" ? youTurn(id, item.text, item.media)
    : item.kind === "claude" ? h("div", { class: "turn claude" }, markdown(item.text, { sid: id }), mediaBlock(id, item.media))
    : item.kind === "image" ? h("button", { class: "turn shot", title: "Open this image", onclick: () => openPreview({ sid: id, blob: item.blob, name: "Pasted image" }) }, h("img", { src: thumbUrl(id, item), alt: "Pasted image", loading: "lazy" }))
    : item.media && item.media.length ? h("div", { class: "turn made" }, stepsOf(item), mediaBlock(id, item.media))
    : stepsOf(item);
  const stepsOf = (item) => h("details", { class: "turn steps" }, h("summary", {}, traceBar(item.steps.map((step) => step.k)), h("span", { textContent: `${item.count} ${item.count === 1 ? "step" : "steps"}${item.errors ? `, ${item.errors} failed` : ""}` }), uiIcon("chev")),
        h("ol", {}, item.steps.map((step) => h("li", { class: step.k === "!" ? "failed" : "" }, h("i", { class: `k-${step.k === "!" ? "err" : step.k}` }), step.what)), item.count > item.steps.length ? h("li", { class: "more", textContent: `and ${item.count - item.steps.length} more` }) : null));
  // On a phone, scrolling Claude's own full-screen view is a round trip per step and leaves it scrolled up. So scrolling a
  // Claude session opens its conversation as a page that scrolls natively, kept up to date; the prompt is a tap away.
  const openReader = (entry) => {
    if (entry.reader || !entry.terminal) return;
    const body = h("div", { class: "record-body" });
    const box = h("div", { class: "record reader", tabindex: "-1", role: "region", "aria-label": "Conversation" }, body);
    box.addEventListener("scroll", () => { box.dataset.stuck = box.scrollTop + box.clientHeight >= box.scrollHeight - 48 ? "1" : "0"; }, { passive: true });
    entry.terminal.host.after(box);
    entry.pane.classList.add("reading");
    entry.reader = { box, timer: 0 };
    drawReadToggle(entry);
    let first = true;
    const stop = loadingIn(body, "Loading the conversation…", () => entry.reader && entry.reader.box === box);
    const load = () => {
      if (!box.isConnected) { clearInterval(entry.reader && entry.reader.box === box ? entry.reader.timer : 0); return; }
      api(`/api/sessions/${entry.id}/record`).then((rec) => {
        if (!entry.reader || entry.reader.box !== box) return;
        if (first) stop();
        const atEnd = first || box.scrollTop + box.clientHeight >= box.scrollHeight - 48;
        const last = rec.items[rec.items.length - 1];
        const sign = `${rec.earlier}:${rec.items.length}:${last ? JSON.stringify(last).length : 0}`;
        if (sign !== box.dataset.sign) {
          box.dataset.sign = sign;
          drawTurns(body, [rec.earlier ? h("div", { class: "empty-line", textContent: `${rec.earlier} earlier turns aren't shown.` }) : null,
            rec.items.length ? rec.items.map(recordTurn(entry.id)) : h("div", { class: "empty-line", textContent: "Nothing has been said yet." })]);
        }
        if (atEnd) box.scrollTop = box.scrollHeight;
        first = false;
      }).catch(() => { if (first) { stop(); fill(body, retryLine("The conversation didn't load.", () => { closeReader(entry, false); openReader(entry); })); } });
    };
    load();
    entry.reader.timer = setInterval(load, 4000);
  };
  const closeReader = (entry, focus = true) => {
    if (!entry.reader) return;
    clearInterval(entry.reader.timer);
    entry.reader.box.remove();
    entry.reader = null;
    entry.pane.classList.remove("reading");
    drawReadToggle(entry);
    if (focus && entry.terminal) entry.terminal.term.focus();
  };
  const drawReadToggle = (entry) => { if (entry.readToggle) entry.readToggle.textContent = entry.reader ? "Prompt" : "Read"; };
  // ── A phone talks to a Claude session as a chat: the conversation scrolls natively, a real text box sends, Claude's
  // choices are buttons, and the keys a choice needs are a tap away. The terminal is one button off, for anything else.
  const switchView = (entry, view) => {
    saved.set(viewKey(), view);
    if (entry.terminal) entry.terminal.dispose();  // the pane is built again: the old one's terminal must let go of its socket
    const fresh = build(entry.id);
    entry.pane.replaceWith(fresh);
    arrange();
    const next = entries.get(entry.id);
    next.terminal && next.terminal.start();
    drawHead(next);
    drawStrip(next);
    setActive(entry.id);
  };
  const openChat = (entry) => {
    const id = entry.id;
    const body = h("div", { class: "record-body" });
    const log = h("div", { class: "record reader chat-log", role: "log", "aria-label": "Conversation", tabindex: "-1" }, body);
    const ask = h("div", { class: "chat-ask", hidden: true });
    const draftKey = `chatDraft:${id}`;
    const input = h("textarea", { rows: 1, placeholder: "Message Claude", "aria-label": "Message Claude", enterkeyhint: "enter", autocapitalize: "sentences", spellcheck: true });
    input.value = saved.get(draftKey, "") || "";
    const send = h("button", { type: "button", class: "chat-send", title: "Send", "aria-label": "Send" }, uiIcon("send"));
    const note = h("div", { class: "chat-note", role: "status", hidden: true });
    const KEYSET = [["Esc", "esc"], ["↑", "up"], ["↓", "down"], ["Enter", "enter"], ["Space", "space"], ["Tab", "tab"], ["⇧Tab", "btab"], ["^C", "ctrl-c"]];
    const keyRow = h("div", { class: "chat-keys", hidden: !saved.get("chatKeys", false) },
      KEYSET.map(([label, key]) => h("button", { type: "button", textContent: label, onclick: () => pressKey(id, key).then(() => setTimeout(loadPeek, 400)) })));
    const keysBtn = h("button", { type: "button", class: "chat-tool", title: "Keys for Claude's menus", "aria-label": "Keys", "aria-pressed": keyRow.hidden ? "false" : "true",
      onclick: () => { keyRow.hidden = !keyRow.hidden; autoKeys = false; saved.set("chatKeys", !keyRow.hidden); keysBtn.setAttribute("aria-pressed", keyRow.hidden ? "false" : "true"); } }, uiIcon("keyboard"));
    // Photos and files wait beside the message as chips, each uploading on its own, and go with it when you send.
    // A chip that's still uploading holds Send back; one that failed says so and can be removed.
    const tray = h("div", { class: "chat-tray", hidden: true, role: "list", "aria-label": "Attached" });
    const attached = [];  // { file, url, path, state: "up" | "ok" | "err", why, el }
    const drawTray = () => {
      fill(tray, attached.map((a) => {
        const img = a.url ? h("img", { src: a.url, alt: "" }) : h("span", { class: "chip-ext", textContent: ((a.file.name || "file").split(".").pop() || "file").slice(0, 4) });
        return h("div", { class: `chat-chip is-${a.state}`, role: "listitem", title: a.why || a.file.name || "" },
          img, h("span", { class: "chip-name", dir: "auto", textContent: a.state === "up" ? "Uploading…" : a.state === "err" ? "Didn't upload" : !a.file.name || a.file.name === "image.png" ? "Pasted image" : a.file.name }),
          h("button", { type: "button", class: "chip-x", "aria-label": `Remove ${a.file.name || "this file"}`, onclick: () => { attached.splice(attached.indexOf(a), 1); if (a.url) URL.revokeObjectURL(a.url); drawTray(); paintSend(); } }, uiIcon("close")));
      }));
      tray.hidden = !attached.length;
    };
    const addFiles = async (list) => {
      const picked = [...list].filter((f) => f && f.size);
      if (!picked.length) return;
      say_("");
      const fresh = picked.map((file) => ({ file, url: /^image\//.test(file.type) ? URL.createObjectURL(file) : "", path: "", state: "up", why: "" }));
      attached.push(...fresh);
      drawTray(); paintSend();
      await Promise.all(fresh.map(async (a) => {
        try {
          const file = await asJpeg(a.file);
          const name = file.name && file.name !== "image.png" ? file.name : `pasted-${Date.now().toString(36)}.${(file.type.split("/")[1] || "png").replace("jpeg", "jpg")}`;
          const done = await upload(`/api/sessions/${id}/upload?name=${encodeURIComponent(name)}`, file);
          a.path = done.path; a.state = "ok";
        } catch (error) { a.state = "err"; a.why = error.known ? error.message : NO_ANSWER; say_(a.why); }
        drawTray(); paintSend();
      }));
    };
    const files = h("input", { type: "file", multiple: true, hidden: true, onchange: () => { const picked = [...files.files]; files.value = ""; addFiles(picked); } });
    const attach = h("button", { type: "button", class: "chat-tool", title: "Share a photo or file", "aria-label": "Attach a photo or file" }, uiIcon("clip"), files);
    attach.onclick = (e) => { if (e.target !== files) files.click(); };
    // A copied photo or screenshot pastes straight in; pasted text stays plain text in the box.
    input.addEventListener("paste", (e) => {
      const pasted = [...(e.clipboardData ? e.clipboardData.files : [])];
      if (!pasted.length) return;
      e.preventDefault();
      addFiles(pasted);
    });
    const dock = h("div", { class: "chat-dock" }, ask, note, keyRow, tray, h("div", { class: "chat-row" }, keysBtn, attach, input, send));
    dock.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); dock.classList.add("dropping"); } });
    dock.addEventListener("dragleave", (e) => { if (!dock.contains(e.relatedTarget)) dock.classList.remove("dropping"); });
    dock.addEventListener("drop", (e) => { e.preventDefault(); dock.classList.remove("dropping"); addFiles(e.dataTransfer.files); });
    // At a desk a file dropped anywhere on the conversation is attached too.
    log.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); dock.classList.add("dropping"); } });
    log.addEventListener("dragleave", (e) => { if (!log.contains(e.relatedTarget)) dock.classList.remove("dropping"); });
    log.addEventListener("drop", (e) => { if (!e.dataTransfer.files.length) return; e.preventDefault(); dock.classList.remove("dropping"); addFiles(e.dataTransfer.files); });
    log.addEventListener("scroll", () => { log.dataset.stuck = log.scrollTop + log.clientHeight >= log.scrollHeight - 64 ? "1" : "0"; }, { passive: true });
    entry.pane.append(log, dock);
    let data = null, sending = false, shownAsk = "", pending = null, autoKeys = false;
    const panel = questionPanel(id, { onSent: () => { shownAsk = ""; tick(); setTimeout(loadPeek, 150); setTimeout(loadPeek, 800); setTimeout(loadRecord, 900); } });
    entry.chat = { log, input };
    const fit = () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 160)}px`; };
    const keepDraft = () => saved.set(draftKey, input.value.trim() ? input.value : null);
    const blocked = () => data && data.dialog ? "Choose above first" : data && data.menu ? "Answer the menu first" : data && !data.live ? "Not taking messages" : "";
    const ready = () => attached.filter((a) => a.state === "ok");
    const paintSend = () => { send.disabled = sending || (!input.value.trim() && !ready().length) || attached.some((a) => a.state === "up") || !!blocked(); input.placeholder = blocked() || (sessionWorking() ? "Queue a message" : "Message Claude"); };
    const sessionWorking = () => (session(id) || {}).state === "working";
    const say_ = (text) => { note.hidden = !text; note.textContent = text || ""; };
    input.addEventListener("input", () => { fit(); keepDraft(); paintSend(); say_(""); });
    // On a phone Return makes a new line, as in any messaging app; ⌘↩ sends. At a desk Return sends and ⇧↩ is a new line.
    input.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || e.isComposing) return;
      if (e.metaKey || e.ctrlKey || (!phone.matches && !e.shiftKey && !e.altKey)) { e.preventDefault(); sendNow(); }
    });
    // The page follows the keyboard: the newest message stays in view above it.
    input.addEventListener("focus", () => setTimeout(() => { log.scrollTop = log.scrollHeight; }, 300));
    const sendNow = async () => {
      if (attached.some((a) => a.state === "up")) { say_("Wait for the upload to finish."); return; }
      const files_ = ready();
      const typed = input.value.trim();
      const text = [typed, files_.map((a) => a.path.replace(/ /g, "\\ ")).join(" ")].filter(Boolean).join("\n\n");
      if (!text || sending || blocked()) return;
      sending = true; paintSend(); send.setAttribute("aria-busy", "true");
      pending = h("div", { class: "turn you pending", role: "group", "aria-label": "Sending", "data-text": text }, typed ? h("div", { class: "said", dir: "auto", textContent: typed }) : null,
        files_.some((a) => a.url) ? h("div", { class: "pending-shots" }, files_.filter((a) => a.url).map((a) => h("img", { src: a.url, alt: "" }))) : null);
      body.append(pending);
      log.scrollTop = log.scrollHeight;
      try {
        await api(`/api/sessions/${id}/answer`, { text });
        input.value = ""; fit(); keepDraft();
        files_.forEach((a) => attached.splice(attached.indexOf(a), 1));
        setTimeout(() => files_.forEach((a) => a.url && URL.revokeObjectURL(a.url)), 15000);  // the sent bubble shows them until the conversation has the message
        drawTray();
        tick(); setTimeout(loadRecord, 700); setTimeout(loadPeek, 900);
      } catch (error) {
        if (pending) pending.remove();
        pending = null;
        say_(error.known ? error.message : NO_ANSWER);
      } finally { sending = false; send.removeAttribute("aria-busy"); paintSend(); }
    };
    send.onclick = sendNow;
    const choose = async (o) => {
      if (sending) return;
      sending = true;
      ask.setAttribute("aria-busy", "true");
      try { await api(`/api/sessions/${id}/answer`, { choice: o.n }); toast(`Chose ${o.label}`); shownAsk = ""; data = null; drawAsk(); tick(); setTimeout(loadPeek, 500); setTimeout(loadRecord, 900); }
      catch (error) { say_(error.known ? error.message : NO_ANSWER); setTimeout(loadPeek, 300); }
      finally { sending = false; ask.removeAttribute("aria-busy"); paintSend(); }
    };
    const drawAsk = () => {
      const options = (data && data.options) || [];
      const menu = data && !data.dialog ? data.menu || "" : "";
      const key = JSON.stringify([data && data.dialog, options, data && data.typed, menu]);
      if (key === shownAsk) return;
      shownAsk = key;
      const s = session(id) || {};
      if (data && data.dialog) {  // a choice on screen: the panel draws it, and draws again only what changed
        const fresh = !panel.has();
        panel.show(data.dialog, s.asking);
        if (ask.childNodes.length !== 1 || ask.firstChild !== panel.el) fill(ask, panel.el);
        ask.hidden = false;
        ask.classList.add("dialog");
        if (autoKeys) { keyRow.hidden = !saved.get("chatKeys", false); autoKeys = false; }
        keysBtn.setAttribute("aria-pressed", keyRow.hidden ? "false" : "true");
        paintSend();
        log.scrollTop = log.scrollHeight;
        const busyElsewhere = document.activeElement && document.activeElement !== input && document.activeElement.matches("input, textarea, select, [contenteditable]");
        if (fresh && !phone.matches && !busyElsewhere && !document.querySelector("dialog[open], .peek-pop")) panel.focus();  // at a desk the keys answer it at once
        return;
      }
      panel.clear();
      fill(ask,
        options.length ? h("div", { class: "chat-options", role: "group", "aria-label": "Choices" }, options.map((o) => h("button", { type: "button", class: "chat-option", onclick: () => choose(o) }, h("span", { class: "n", textContent: o.n }), h("span", { dir: "auto", textContent: o.label })))) : null,
        menu ? [h("p", { class: "chat-q" }, "Claude is showing a menu. Move with ↑ ↓, then Enter."), h("pre", { class: "chat-menu", textContent: menu })] : null,
        data && data.typed ? h("p", { class: "chat-q quiet" }, "Something is already typed in this session's terminal. ", h("button", { type: "button", class: "link", textContent: "Open the terminal", onclick: () => switchView(entry, "terminal") }), " to send or clear it.") : null);
      ask.hidden = !ask.childNodes.length;
      ask.classList.toggle("dialog", !!menu);
      // A menu needs the keys: they open for it, and close again after it unless you had them open anyway.
      if (menu && keyRow.hidden) { keyRow.hidden = false; autoKeys = true; }
      else if (!menu && autoKeys) { keyRow.hidden = !saved.get("chatKeys", false); autoKeys = false; }
      keysBtn.setAttribute("aria-pressed", keyRow.hidden ? "false" : "true");
      paintSend();
      if (menu) log.scrollTop = log.scrollHeight;
    };
    const loadPeek = () => {
      if (!log.isConnected || document.hidden) return;
      api(`/api/sessions/${id}/peek`).then((next) => { if (!log.isConnected) return; data = next; drawAsk(); paintSend(); }).catch(() => {});
    };
    let first = true;
    const stop = loadingIn(body, "Loading the conversation…", () => log.isConnected);
    const loadRecord = () => {
      if (!log.isConnected) return;
      api(`/api/sessions/${id}/record`).then((rec) => {
        if (!log.isConnected) return;
        if (first) stop();
        const atEnd = first || log.scrollTop + log.clientHeight >= log.scrollHeight - 64;
        const last = rec.items[rec.items.length - 1];
        const sign = `${rec.earlier}:${rec.items.length}:${last ? JSON.stringify(last).length : 0}`;
        if (sign !== log.dataset.sign) {
          log.dataset.sign = sign;
          // A message just sent stays shown until the conversation has it.
          const sent = pending ? pending.dataset.text.trim() : "";
          const keep = pending && !rec.items.slice(-4).some((it) => it.kind === "you" && it.text.trim() === sent) ? pending : null;
          if (!keep) pending = null;
          drawTurns(body, [rec.earlier ? h("div", { class: "empty-line", textContent: `${rec.earlier} earlier turns aren't shown.` }) : null,
            rec.items.length ? rec.items.map(recordTurn(id)) : h("div", { class: "empty-line", textContent: "Nothing has been said yet. Write below to start." }), keep]);
        }
        if (atEnd) log.scrollTop = log.scrollHeight;
        first = false;
      }).catch(() => { if (first) { stop(); fill(body, retryLine("The conversation didn't load.", loadRecord)); } });
    };
    loadRecord(); loadPeek();
    const timer = setInterval(() => { if (!log.isConnected) { clearInterval(timer); return; } if (!document.hidden) { loadRecord(); loadPeek(); } }, 3000);
    requestAnimationFrame(() => { fit(); paintSend(); });
    entry.chat.refresh = () => { paintSend(); const s = session(id); if (s && (s.state === "needs") !== !!(data && data.dialog)) loadPeek(); };
  };
  // A Claude session that isn't running is read as a conversation: its handoff on top, then what was said and done.
  const showRecord = (entry) => {
    const { id, pane } = entry;
    const box = h("div", { class: "record", tabindex: "-1" });
    const bar = h("div", { class: "record-top" });
    const body = h("div", { class: "record-body" });
    box.append(bar, body);
    pane.append(box);
    let folder = "";
    const askDelete = () => { const s = session(id); if (s) deleteSession(s); };
    const drawBar = (force) => {
      const s = session(id);
      if (!s) return;
      if (!differs(bar, s.state, s.closedAt ? agoWords(s.closedAt) : "", canResume(s), folder) && !force) return;
      const resume = h("button", { class: "btn primary", "data-key": "resume", disabled: !canResume(s), title: canResume(s) ? "Start Claude again with this whole conversation" : "Its folder or conversation is gone, so it can't be resumed" }, "Resume");
      resume.onclick = once("Resuming…", () => resumeSession(s), resume);
      fill(bar,
        h("span", { class: "record-when" }, s.state === "closed" ? `Closed ${s.closedAt ? agoWords(s.closedAt) : ""}` : "Ended", folder ? h("span", { class: "record-folder", textContent: folder }) : null),
        h("div", { class: "ended-acts" }, resume, h("button", { class: "btn", textContent: "Delete", "data-key": "delete", onclick: askDelete })));
    };
    entry.drawRecordBar = drawBar;
    drawBar();
    const stop = loadingIn(body, "Loading the conversation…", () => entries.get(id) === entry);
    api(`/api/sessions/${id}/record`).then((rec) => {
      stop();
      if (entries.get(id) !== entry) return;
      const note = rec.note ? h("section", { class: "handoff", "aria-label": "Handoff" }, h("h2", { textContent: "Handoff" }),
        rec.note.split("\n").filter((line) => line.trim()).map((line) => {
          const m = line.replace(/^[\s*_-]+|\*\*/g, "").match(/^(Done|Open|Next|Cleaned|Committed):?\s*(.*)$/i);
          return m ? h("p", {}, h("b", { textContent: m[1][0].toUpperCase() + m[1].slice(1).toLowerCase() }), h("span", { dir: "auto" }, inline(m[2]))) : h("p", { dir: "auto" }, inline(line));
        })) : null;
      folder = rec.folder || ""; drawBar(true);
      const turn = recordTurn(id);
      const age = (since) => { const d = (Date.now() / 1000 - since) / 86400; return d >= 1 ? `${Math.round(d)} ${Math.round(d) === 1 ? "day" : "days"}` : d * 24 >= 1 ? `${Math.round(d * 24)}h` : `${Math.max(1, Math.round(d * 1440))}m`; };
      const running = rec.running && rec.running.length ? h("section", { class: "still-running", "aria-label": "Still running" },
        h("h2", { textContent: "Still running from this folder" }),
        rec.running.map((r) => h("p", {}, h("b", { textContent: r.name }), h("span", { class: "mono", textContent: r.ports.map((n) => `:${n}`).join(" ") }),
          h("span", { class: "quiet", textContent: `pid ${r.pid} · up ${age(r.since)}` }), h("span", { class: "quiet path", title: r.folder, textContent: r.folder.replace(/^\/private\/tmp\/claude-\d+\/[^/]+\/[^/]+\//, "scratch/") }))),
        h("small", { textContent: "The hub only lists these. Stop one from a terminal if nothing needs it." })) : null;
      fill(body, note, running,
        rec.earlier ? h("div", { class: "empty-line", textContent: `${rec.earlier} earlier turns aren't shown.` }) : null,
        rec.items.length ? rec.items.map(turn) : h("div", { class: "empty-line", textContent: rec.kept ? "Nothing was said in this session." : "This session's conversation wasn't kept." }));
      if (!rec.note) box.scrollTop = box.scrollHeight;
    }).catch(() => { stop(); if (entries.get(id) === entry) fill(body, retryLine("The conversation didn't load.", () => { body.replaceChildren(); entry.drawRecordBar = null; box.remove(); showRecord(entry); })); });
  };
  const showNote = (entry) => {
    const { id, pane } = entry;
    const note = h("div", { class: "ended-note" });
    const rest = () => fill(note, h("span", { textContent: session(id) ? "This session has ended." : "That session no longer exists." }), h("div", { class: "ended-acts" },
      h("button", { class: "btn", textContent: "Close", "data-key": "close-note", onclick: () => leaveAfter(id) }),
      session(id) ? h("button", { class: "btn", textContent: "Delete", "data-key": "delete", onclick: askDelete }) : null));
    const askDelete = () => { const s = session(id); if (s) deleteSession(s); };
    rest();
    pane.append(note);
  };
  // A session that ends while it's on screen says so, and the terminal stops trying to reach it.
  const endTerminal = (entry) => {
    const hadFocus = entry.pane.contains(document.activeElement);
    closeReader(entry, false);
    entry.terminal.dispose();
    entry.terminal = null;
    entry.stopping = false;
    entry.pane.classList.remove("dropping");
    entry.pane.querySelectorAll(":scope > .term, :scope > .keys, :scope > .drop-hint, :scope > .pane-strip, :scope > .chat-log, :scope > .chat-dock").forEach((el) => el.remove());
    entry.pane.classList.remove("chatting");
    entry.chat = null;
    entry.strip = entry.stripOrb = null;
    showEnded(entry);
    say(`${(session(entry.id) || {}).title || "This session"} has ended.`);
    const first = entry.pane.querySelector(".record-top button:not(:disabled), .ended-note button");
    if (hadFocus && first) first.focus({ preventScroll: true });
  };
  const revive = (entry) => {
    const hadFocus = entry.pane.contains(document.activeElement);
    const fresh = build(entry.id);
    entry.pane.replaceWith(fresh);
    arrange();
    const next = entries.get(entry.id);
    next.terminal && next.terminal.start();
    drawHead(next);
    drawStrip(next);
    say(`${(session(entry.id) || {}).title || "This session"} is running again.`);
    if (hadFocus && next.terminal) next.terminal.term.focus();
  };
  const leaveAfter = (id) => {
    const rest = layoutWithout(layout, id);
    const s = session(id);
    if (rest) goLayout(rest); else go(s ? `#/p/${P(s.project)}` : "#/");
  };
  const drawHead = (entry) => {
    const s = session(entry.id);
    if (!s) return;
    // Mode and Model type into the pane, so only a running Claude gets them.
    const live = s.kind === "claude" && s.alive && s.state !== "ended" && s.state !== "closing";
    const closable = s.kind === "claude" && s.alive && canClose(s);
    const down = !!entry.terminal && entry.terminal.down();
    const tip = down ? "Not connected" : statusLine(s);
    const shown = down ? "offline" : shownState(s);
    const headDot = () => entry.head.querySelector(".dot");
    if (!differs(entry.head, s.state, s.title, s.mode, s.model, s.kind, s.alive, s.connected, s.phone, s.repo, s.isolate, s.project, entry.stopping, entry.full, entry.pending, down, ids.length, ids.indexOf(entry.id), !!entry.chat, phone.matches, (project(s.project) || {}).icon)) { if (headDot()) headDot().title = tip; return; }
    entry.pane.setAttribute("aria-label", s.title);
    // Switching can take seconds: the control says so, and a second choice waits for the first.
    const pendingWhile = (what, work) => guard(async () => {
      if (entry.pending) return;
      entry.pending = what; drawHead(entry);
      try { await work(); } finally { entry.pending = null; drawHead(entry); }
    })();
    const change = (what, value, label) => pendingWhile(what, async () => { await api(`/api/sessions/${s.id}/${what}`, { [what]: value }); toast(`Switched to ${label}`); await tick(); });
    const modeItems = MODES.map((m) => ({ ...m, on: s.mode === m.id, run: () => change("mode", m.id, m.name) }));
    const modelItems = MODELS.map((m) => ({ ...m, on: s.model === m.id, run: () => change("model", m.id, m.name) }));
    const connect = () => pendingWhile("phone", async () => { await api(`/api/sessions/${s.id}/phone`, {}); await tick(); });
    const canConnect = live && !s.connected && !s.code, phoneLink = s.phone && s.alive;
    const keyed = (el, key) => { el.dataset.key = key; return el; };
    const cut = (el) => el.scrollWidth > el.clientWidth;
    // Only a title that can open is a disclosure; one that fits has nothing to expand.
    const markName = (el) => {
      el.classList.toggle("cut", cut(el));
      if (entry.full || cut(el)) el.setAttribute("aria-expanded", entry.full ? "true" : "false"); else el.removeAttribute("aria-expanded");
    };
    const repoName = (s.repo || "").split("/").pop();
    const ask = entry.stopping && ids.length === 1 ? h("button", { class: "ask", textContent: "Stop session?", "data-key": "confirm-stop", onclick: () => stop() }) : null;
    const stop = once("Stopping…", async () => { await api(`/api/sessions/${s.id}/stop`, {}); await tick(); }, ask);
    fill(entry.head,
      dot(shown, tip), ids.length > 2 ? h("span", { class: "pane-n", textContent: `${ids.indexOf(entry.id) + 1}/${ids.length}` }) : null, ids.length > 1 && project(s.project) ? mark(project(s.project), 15) : null,
      h("button", { class: `name ${entry.full ? "full" : ""}`, type: "button", dir: "auto", textContent: s.title, "data-key": "name",
        onpointerenter: (e) => markName(e.currentTarget), onfocus: (e) => markName(e.currentTarget),
        onclick: (e) => { if (entry.full || cut(e.currentTarget)) { entry.full = !entry.full; drawHead(entry); } else if (entry.terminal && e.detail) entry.terminal.term.focus(); } }),
      live && s.project !== HUB ? keyed(pill(entry.pending === "mode" ? "Switching…" : modeName(s.mode) || "Mode", "Change mode", (anchor) => { if (!entry.pending) popover(anchor, modeItems); }), "mode") : null,
      live && s.project === HUB ? h("span", { class: "folder no-prompts", title: "Permissions are skipped in a hub session" }, "No prompts") : null,
      live ? keyed(pill(entry.pending === "model" ? "Switching…" : modelName(s.model) || "Model", "Change model for this session", (anchor) => { if (!entry.pending) popover(anchor, modelItems); }), "model") : null,
      s.isolate || (repoName && repoName !== s.project) ? h("span", { class: "folder" }, s.isolate ? svg(UI.branch) : null, repoName) : null,
      canConnect ? keyed(h("button", { class: "connect", "aria-busy": entry.pending === "phone" ? "true" : undefined, textContent: entry.pending === "phone" ? "Connecting…" : "Connect phone", onclick: connect }), "connect") : null,
      live ? keyed(h("button", { class: "icon pane-more", title: canConnect ? "Mode, model and phone" : "Mode and model", "aria-haspopup": "menu", onclick: (e) => popover(e.currentTarget, [
        ...(s.project === HUB ? [] : [{ group: "Mode" }, ...modeItems]), { group: "Model" }, ...modelItems,
        canConnect ? { name: "Connect phone", icon: "phone", run: connect } : null,
        phoneLink && entry.pane.clientWidth <= 240 ? { name: "Open on phone", icon: "phone", run: () => window.open(s.phone, "_blank", "noopener") } : null,
        { group: "Session" },
        closable ? { name: "Close session", icon: "stop", run: () => closeSession(s) } : null,
        { name: "Delete session…", icon: "close", run: () => deleteSession(s) },
      ].filter(Boolean)) }, uiIcon("dots")), "more") : null,
      phoneLink && !phone.matches ? h("a", { class: "icon", href: s.phone, target: "_blank", rel: "noopener noreferrer", title: "Open on phone", "data-key": "phone" }, uiIcon("phone")) : null,
      s.kind === "claude" && s.alive ? keyed(h("button", { class: "view-switch", type: "button", title: entry.chat ? "Show the terminal" : "Show as a chat", onclick: () => switchView(entry, entry.chat ? "terminal" : "chat") },
        uiIcon(entry.chat ? "term" : "chat"), h("span", { textContent: entry.chat ? "Terminal" : "Chat" })), "view") : null,
      ask,
      s.state === "closing" ? h("span", { class: "connect closing-word", role: "status", textContent: "Closing…" }) : null,
      phone.matches ? null : keyed(h("button", { class: "icon pane-split", type: "button", title: ids.length > 1 ? "Split, move or close this pane" : "Split this pane", "aria-haspopup": "menu", onclick: (e) => paneMenu(e.currentTarget, s.id) }, uiIcon("split")), "pane-split"),
      closable ? keyed(h("button", { class: "connect close-session", title: "End Claude and keep the conversation", onclick: () => closeSession(s) }, "Close session"), "close-session") : null,
      ids.length > 1
        ? h("button", { class: "icon", title: s.alive ? "Close pane. The session keeps running." : "Close pane", "data-key": "close", onclick: () => goLayout(layoutWithout(layout, s.id)) }, uiIcon("close"))
        : s.alive && s.kind !== "claude" ? h("button", { class: "icon", title: entry.stopping ? "Keep running" : "Stop session", "data-key": "stop", onclick: () => { entry.stopping = !entry.stopping; drawHead(entry); } }, uiIcon(entry.stopping ? "close" : "stop")) : null);
    const nameEl = entry.head.querySelector(".name");
    if (nameEl) markName(nameEl);
  };
  // ── C: the strip at the bottom of a pane says what runs now: orb · tool · target · elapsed · esc stop ──
  const drawStrip = (entry) => {
    const s = session(entry.id);
    if (!entry.strip || !s) return;
    const live = s.kind === "claude" && s.alive && s.state !== "closing";
    entry.strip.hidden = !live;
    if (!live) return;
    const a = s.activity, working = s.state === "working";
    const tool = working && a && /using|searching/.test(s.orb || "");
    const word = working ? (tool ? a.tool : ORB_WORDS[s.orb] || "Working") : s.state === "error" ? "Error" : s.state === "needs" ? "Needs you" : s.state === "finished" ? "Idle" : DOT_WORDS[shownState(s)] || "";
    const retry = s.retry && s.orb === "retrying" ? `${s.retry.said || "API error"}${s.retry.attempt ? ` · try ${s.retry.attempt}${s.retry.of ? ` of ${s.retry.of}` : ""}` : ""}` : "";
    const detail = working ? (tool ? a.target : retry) : s.state === "error" ? s.error : s.state === "needs" ? s.asking || "" : "";
    const state = orbState(s);
    if (!differs(entry.strip, s.state, s.orb, word, detail, working && s.turn ? s.turn.since : 0)) { setOrb(entry.stripOrb, state, word); return; }
    entry.strip.className = `pane-strip is-${s.state}`;
    entry.stripOrb = entry.stripOrb || newOrb(state, 16);
    setOrb(entry.stripOrb, state, word);
    const stopTurn = () => { if (entry.chat) pressKey(entry.id, "esc"); else if (entry.terminal) { entry.terminal.send({ t: "i", d: "\x1b" }); entry.terminal.term.focus(); } };
    fill(entry.strip, entry.stripOrb, h("span", { class: "strip-word", textContent: word }),
      detail ? h("span", { class: `strip-target ${tool ? "mono" : ""}`, dir: "auto", title: detail, textContent: detail }) : null,
      working && s.turn ? turnClock(s.turn.since, { class: "strip-time", "aria-label": "Time this turn" }) : null,
      h("span", { class: "strip-fill" }),
      working ? h("button", { type: "button", class: "strip-act", title: "Interrupt Claude (Esc)", onclick: stopTurn }, h("kbd", { textContent: "esc" }), "Stop") : null,
      s.state === "error" ? h("button", { type: "button", class: "strip-act", title: "Mark this session as no longer failed", onclick: once("Clearing…", async () => { await api(`/api/sessions/${s.id}/clear`, {}); await tick(); }) }, "Clear") : null);
  };

  // ── C: the right panel's status rail: what changed, how full the context is, what it listens on ──
  const rail = h("section", { class: "rail", "aria-label": "Changes, context and ports" });
  let portAsk = null;
  const drawRail = (force) => {
    const s = session(activeId);
    if (!s) { rail.replaceChildren(); rail.hidden = true; return; }
    if (!differs(rail, s.id, s.changes, s.context, s.ports, s.alive, portAsk, reviewing && reviewing.sid) && !force) return;
    const row = (label, ...value) => h("div", { class: "rail-row" }, h("span", { class: "rail-label", textContent: label }), h("div", { class: "rail-value" }, value));
    const c = s.changes;
    const changes = !c ? null : c.files ? row("Changes", h("button", { type: "button", class: "rail-link", "aria-expanded": reviewing && reviewing.sid === s.id ? "true" : "false", title: "Review the changes in this session's folder", onclick: () => (reviewing && reviewing.sid === s.id ? closeChanges() : openChanges(s.id)) },
      h("span", {}, h("span", { class: "mono" }, counts(c)), h("span", { class: "faint", textContent: ` · ${c.files} ${c.files === 1 ? "file" : "files"}` })), uiIcon("chev")))
      : row("Changes", h("span", { class: "faint", textContent: "None uncommitted" }));
    const x = s.context;
    const share = x ? Math.min(100, Math.round((x.used / x.limit) * 100)) : 0;
    const context = x ? row("Context", h("span", { class: `meter ${share >= 80 ? "high" : ""}`, role: "meter", "aria-valuemin": 0, "aria-valuemax": 100, "aria-valuenow": share, "aria-label": "Context used" }, h("i", { style: `width:${Math.max(2, share)}%` })),
      h("span", { class: "mono", title: `${x.used.toLocaleString("en-GB")} of ${x.limit.toLocaleString("en-GB")} tokens` }, `${share}%`, h("span", { class: "faint", textContent: ` of ${tokens(x.limit)}` }))) : null;
    const stopPort = (port) => once("Stopping…", async () => { await api(`/api/sessions/${s.id}/port-stop`, { port }); portAsk = null; toast(`Stopped :${port}`); await tick(); drawRail(true); });
    const host = /^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname) ? "localhost" : location.hostname;
    const ports = s.alive && s.ports && s.ports.length ? row("Ports", h("div", { class: "ports" }, s.ports.map((port) => portAsk === port
      ? h("span", { class: "port stopping" }, h("button", { type: "button", class: "ask", "data-key": `stop-port:${port}`, onclick: (e) => stopPort(port)(e) }, `Stop :${port}?`), h("button", { type: "button", class: "icon", title: "Keep it running", "aria-label": "Keep it running", onclick: () => { portAsk = null; drawRail(true); } }, uiIcon("close")))
      : h("span", { class: "port" }, h("a", { class: "port-open", href: `http://${host}:${port}/`, target: "_blank", rel: "noopener noreferrer", title: `Open ${host}:${port}` }, `:${port}`, uiIcon("external")),
          h("button", { type: "button", class: "icon", title: `Stop what listens on :${port}`, "aria-label": `Stop :${port}`, "data-key": `port:${port}`, onclick: () => { portAsk = port; drawRail(true); const ask = rail.querySelector(`[data-key="stop-port:${port}"]`); if (ask) ask.focus(); } }, uiIcon("stop")))))) : null;
    fill(rail, changes, context, ports);
    rail.hidden = !rail.childNodes.length;
  };

  // ── C: Changes, reviewed like a pull request: file list, one continuous scroll, viewed per file, line comments ──
  let reviewing = null;
  const closeChanges = () => {
    if (!reviewing) return;
    const { box, observer, sid } = reviewing;
    reviewing = null;
    observer.disconnect();
    box.remove();
    drawRail(true);
    const entry = entries.get(sid);
    if (entry && entry.terminal) entry.terminal.term.focus();
  };
  const openChanges = guard(async (sid) => {
    closeChanges();
    const s = session(sid);
    if (!s) return;
    const notes = reviewNotes.get(sid) || [];
    reviewNotes.set(sid, notes);
    const viewedAll = saved.get("viewed", {});
    const viewed = viewedAll[sid] || {};
    const summary = h("span", { class: "review-sum" });
    const send = h("button", { type: "button", class: "btn primary", hidden: true });
    const stale = h("button", { type: "button", class: "btn", hidden: true, title: "The folder changed since this was read", onclick: () => openChanges(sid) }, "Reload");
    const head = h("header", { class: "review-top" }, summary, h("span", { class: "strip-fill" }), stale, send,
      h("button", { type: "button", class: "icon", title: "Close (Esc)", "aria-label": "Close the changes", onclick: closeChanges }, uiIcon("close")));
    const list = h("nav", { class: "review-files", "aria-label": "Changed files" });
    const scroll = h("div", { class: "review-diff", tabindex: "-1" });
    const box = h("section", { class: "review", role: "region", "aria-label": `Changes in ${s.title}` }, head, h("div", { class: "review-main" }, list, scroll));
    stage.append(box);
    const observer = new IntersectionObserver((seen) => seen.forEach((e) => { if (e.isIntersecting && e.target.dataset.later) { delete e.target.dataset.later; fetchFile(e.target); } }), { root: scroll, rootMargin: "400px" });
    reviewing = { sid, box, observer, loaded: null };
    drawRail(true);
    box.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !e.target.closest("textarea")) { e.preventDefault(); e.stopPropagation(); closeChanges(); }
    });
    const stop = loadingIn(scroll, "Reading the changes…", () => reviewing && reviewing.box === box);
    let diff;
    try { diff = await api(`/api/sessions/${sid}/diff`); } catch (error) { stop(); fill(scroll, retryLine(error.known ? error.message : "The changes didn't load.", () => openChanges(sid))); return; }
    stop();
    if (!reviewing || reviewing.box !== box) return;
    reviewing.loaded = { added: diff.added, removed: diff.removed, files: diff.files.length };
    const sig = (f) => { let n = 0; const t = JSON.stringify([f.added, f.removed, f.hunks]); for (let i = 0; i < t.length; i++) n = (n * 31 + t.charCodeAt(i)) | 0; return String(n); };
    const isViewed = (f) => !!viewed[f.path] && viewed[f.path] === sig(f);
    const drawHeadline = () => {
      const seen = diff.files.filter(isViewed).length;
      fill(summary, h("span", { class: "mono" }, counts(diff)), h("span", { class: "faint", textContent: ` · ${diff.files.length} ${diff.files.length === 1 ? "file" : "files"}` }),
        seen ? h("span", { class: "faint", textContent: ` · ${seen} viewed` }) : null);
      send.hidden = !notes.length;
      send.textContent = `Send ${notes.length} ${notes.length === 1 ? "comment" : "comments"}`;
    };
    send.onclick = once("Sending…", async () => {
      await api(`/api/sessions/${sid}/review`, { comments: notes.map(({ path, line, quote, text }) => ({ path, line, quote, text })) });
      toast(`Sent ${notes.length} ${notes.length === 1 ? "comment" : "comments"}`);
      notes.length = 0;
      closeChanges();
      await tick();
    }, send);
    if (!diff.git) { fill(scroll, h("div", { class: "empty-line", textContent: `${diff.folder} isn't a git folder, so there's nothing to compare.` })); drawHeadline(); return; }
    if (!diff.files.length) { fill(scroll, h("div", { class: "empty-line", textContent: "Nothing uncommitted in this session's folder." })); drawHeadline(); return; }
    const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    const split = (path) => { const at = path.lastIndexOf("/"); return at < 0 ? ["", path] : [path.slice(0, at + 1), path.slice(at + 1)]; };
    const rowsHtml = (f) => f.hunks.map((hunk, hi) => `<div class="dh" aria-hidden="true">${hi || hunk.old > 1 || hunk.new > 1 ? "⋯" : ""}${hunk.head ? ` <span>${esc(hunk.head)}</span>` : ""}</div>`
      + hunk.rows.map((r, ri) => `<div class="dl ${r[0] === "+" ? "a" : r[0] === "-" ? "d" : r[0] === "\\" ? "n" : ""}" data-r="${hi}.${ri}"><span class="ln">${r[1] ?? ""}</span><span class="ln">${r[2] ?? ""}</span>`
        + `${r[0] === "\\" ? "" : `<button type="button" class="add-note" tabindex="-1" aria-label="Comment on this line">+</button>`}<code>${esc(r[3]) || " "}</code></div>`).join("")).join("");
    const drawNotes = (section, f, editing) => {
      section.querySelectorAll(".line-note").forEach((el) => el.remove());
      notes.filter((n) => n.path === f.path && n !== editing).forEach((n) => {
        const at = section.querySelector(`.dl[data-r="${n.r}"]`);
        const el = h("div", { class: "line-note", "data-r": n.r }, h("p", { dir: "auto", textContent: n.text }),
          h("div", { class: "line-note-acts" }, h("button", { type: "button", class: "line-note-btn", onclick: () => editNote(section, f, n.r, n) }, "Edit"),
            h("button", { type: "button", class: "line-note-btn", onclick: () => { notes.splice(notes.indexOf(n), 1); drawNotes(section, f); drawHeadline(); } }, "Delete")));
        if (at) at.after(el); else section.querySelector(".review-rows").append(el);
      });
    };
    const editNote = (section, f, r, existing) => {
      section.querySelectorAll(".line-note-edit").forEach((el) => el.remove());
      drawNotes(section, f, existing);
      const at = section.querySelector(`.dl[data-r="${r}"]`);
      if (!at) return;
      const [hi, ri] = r.split(".").map(Number);
      const row = f.hunks[hi].rows[ri];
      const area = h("textarea", { rows: 3, placeholder: "What should change here?", "aria-label": `Comment on ${f.path}, line ${row[2] ?? row[1]}` });
      area.value = existing ? existing.text : "";
      const done = () => { editor.remove(); drawNotes(section, f); };
      const save = () => {
        const text = area.value.trim();
        if (!text) return;
        if (existing) existing.text = text;
        else notes.push({ path: f.path, r, line: row[2] ?? row[1], quote: `${row[0] === "-" ? "- " : row[0] === "+" ? "+ " : ""}${row[3]}`.slice(0, 300), text });
        done(); drawHeadline();
      };
      const editor = h("div", { class: "line-note-edit" }, area, h("div", { class: "line-note-acts" },
        h("button", { type: "button", class: "btn primary", onclick: save }, existing ? "Save" : "Comment"),
        h("button", { type: "button", class: "btn", onclick: done }, "Cancel"), h("span", { class: "faint" }, h("kbd", { textContent: "⌘↵" }))));
      area.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); } if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(); } });
      at.after(editor);
      area.focus();
    };
    const bodyOf = (section, f) => {
      const rows = section.querySelector(".review-rows");
      if (f.hidden) return fill(rows, h("div", { class: "empty-line", textContent: "Not shown: a file like this can hold keys." }));
      if (f.binary) return fill(rows, h("div", { class: "empty-line", textContent: f.status === "added" ? "Not text, or too large to show." : "A binary file." }));
      if (!f.hunks) return fill(rows, h("div", { class: "empty-line", textContent: "Reading…" }));
      if (!f.hunks.length) return fill(rows, h("div", { class: "empty-line", textContent: "Only its mode changed." }));
      rows.innerHTML = rowsHtml(f) + (f.cut ? `<div class="empty-line">More lines than fit here. Open the file to read the rest.</div>` : "");
      drawNotes(section, f);
    };
    const fetchFile = async (section) => {
      const f = diff.files[Number(section.dataset.i)];
      try { Object.assign(f, await api(`/api/sessions/${sid}/diff?path=${encodeURIComponent(f.path)}`)); } catch (error) { fill(section.querySelector(".review-rows"), retryLine(error.known ? error.message : "This file didn't load.", () => fetchFile(section))); return; }
      bodyOf(section, f); drawFile(section, f); drawList();
    };
    const drawFile = (section, f) => {
      const [dir, name] = split(f.path);
      const on = isViewed(f);
      section.classList.toggle("viewed", on);
      fill(section.querySelector(".review-file-top"),
        h("button", { type: "button", class: "file-fold", "aria-expanded": on ? "false" : "true", title: on ? "Show" : "Fold", onclick: () => { section.classList.toggle("viewed"); section.querySelector(".file-fold").setAttribute("aria-expanded", section.classList.contains("viewed") ? "false" : "true"); } }, uiIcon("chev")),
        h("span", { class: "file-path", title: f.path }, dir ? h("span", { class: "faint", textContent: dir }) : null, h("b", { textContent: name })),
        f.status !== "changed" ? h("span", { class: `file-tag ${f.status}`, textContent: f.status === "added" ? "New" : "Deleted" }) : null,
        f.hidden || f.binary ? null : h("span", { class: "mono file-counts" }, counts(f)),
        h("label", { class: "file-viewed" }, h("input", { type: "checkbox", checked: on, onchange: (e) => {
          if (e.target.checked) viewed[f.path] = sig(f); else delete viewed[f.path];
          saved.set("viewed", { ...saved.get("viewed", {}), [sid]: viewed });
          drawFile(section, f); drawList(); drawHeadline();
          if (e.target.checked) { const next = section.nextElementSibling; if (next && section.getBoundingClientRect().top < scroll.getBoundingClientRect().top) section.scrollIntoView({ block: "start" }); }
        } }), "Viewed"));
    };
    const sections = diff.files.map((f, i) => {
      const section = h("section", { class: "review-file", "data-i": i, "aria-label": f.path }, h("header", { class: "review-file-top" }), h("div", { class: "review-rows" }));
      if (f.later) section.dataset.later = "1";
      drawFile(section, f); bodyOf(section, f);
      section.querySelector(".review-rows").addEventListener("click", (e) => {
        const line = e.target.closest(".dl");
        if (!line || line.classList.contains("n") || !(e.target.closest(".add-note") || e.target.closest(".ln"))) return;
        editNote(section, f, line.dataset.r);
      });
      return section;
    });
    const drawList = () => fill(list, diff.files.map((f, i) => {
      const [dir, name] = split(f.path);
      return h("button", { type: "button", class: `review-file-link ${isViewed(f) ? "viewed" : ""}`, title: f.path, onclick: () => { sections[i].scrollIntoView({ block: "start" }); sections[i].querySelector(".file-fold").focus({ preventScroll: true }); } },
        h("span", { class: "file-name" }, h("b", { textContent: name }), dir ? h("small", { textContent: dir.replace(/\/$/, "") }) : null),
        isViewed(f) ? svg(UI.check) : f.hidden || f.binary ? null : h("span", { class: "mono file-counts" }, counts(f)));
    }));
    fill(scroll, sections);
    sections.forEach((section) => observer.observe(section));
    drawList(); drawHeadline();
    scroll.focus({ preventScroll: true });
    reviewing.stale = () => { const c = (session(sid) || {}).changes; stale.hidden = !c || (c.added === diff.added && c.removed === diff.removed && c.files === diff.files.length); };
  });
  const splitMenu = (anchor) => {
    const items = [];
    if (ids.length >= MAX_PANES) items.push({ group: "Close a pane to add another" });
    else {
      [...new Set(S.sessions.map((s) => s.project))].forEach((name) => {
        const others = S.sessions.filter((s) => s.project === name && s.alive && !ids.includes(s.id));
        if (!others.length) return;
        items.push({ group: (project(name) || {}).display || name });
        others.forEach((s) => items.push({ name: s.title, dot: shownState(s), run: () => goLayout(layoutAdd(layout, s.id)) }));
      });
      items.push({ name: "New session beside this one", icon: "plus", run: () => newSession((session(activeId) || session(ids[0]) || {}).project, layoutText(layout)) });
    }
    if (ids.length > 1 && !phone.matches) items.push({ name: "Even out", icon: "split", run: () => { const walk = (n) => { if (isSplit(n)) { n.z = even(n.k.length); n.k.forEach(walk); } }; walk(layout); applySizes(); keepSizes(layout); refitAll(); } });
    popover(anchor, items);
  };
  // The keyboard's way to do what dragging does: split a pane with another session, move it, or close it.
  const paneMenu = (anchor, id) => {
    const here = session(id), name = (other) => session(other) ? bareTitle(session(other)) : "Session";
    const pick = (side) => () => {
      const items = [{ group: side === "right" ? `Open to the right of ${name(id)}` : `Open below ${name(id)}` }];
      const others = S.sessions.filter((s) => s.alive && !ids.includes(s.id));
      others.forEach((s) => items.push({ name: s.title, dot: shownState(s), run: () => { goLayout(layoutBeside(layout, id, s.id, side)); say(`${s.title} opened ${side === "right" ? "to the right of" : "below"} ${name(id)}`); } }));
      if (!others.length) items.push({ group: "No other session is running" });
      items.push({ name: "New session here", icon: "plus", run: () => newSession((here || {}).project, layoutText(layoutBeside(layout, id, "new", side))) });
      popover(anchor, items);
    };
    const moveTo = () => {
      const items = [];
      ids.filter((other) => other !== id).forEach((other) => {
        items.push({ group: name(other) });
        items.push({ name: "Swap places", icon: "move", run: () => goLayout(layoutSwap(layout, id, other)) });
        items.push({ name: "To its right", icon: "split", run: () => goLayout(layoutBeside(layout, other, id, "right")) });
        items.push({ name: "Below it", icon: "splitDown", run: () => goLayout(layoutBeside(layout, other, id, "bottom")) });
      });
      popover(anchor, items);
    };
    const full = ids.length >= MAX_PANES;
    popover(anchor, [
      full ? { group: "Four panes is the limit" } : null,
      full ? null : { name: "Split right…", icon: "split", say: "Open a session beside this one", run: pick("right") },
      full ? null : { name: "Split down…", icon: "splitDown", say: "Open a session under this one", run: pick("bottom") },
      ids.length > 1 ? { name: "Move…", icon: "move", say: "Swap it, or put it beside or under another pane", run: moveTo } : null,
      ids.length > 1 ? { name: "Close pane", icon: "close", say: here && here.alive ? "The session keeps running" : undefined, run: () => goLayout(layoutWithout(layout, id)) } : null,
    ].filter(Boolean));
  };
  // Where a dragged session would land on this page: beside, above or under the pane under the pointer, at the edge
  // of the whole split, or (a pane dragged onto another) in its place. Asked by the drag on every move.
  page.dropAt = (x, y, sid, fromPane) => {
    if (phone.matches) return null;
    const box = panes.getBoundingClientRect();
    if (x < box.left || x > box.right || y < box.top || y > box.bottom) return null;
    const inLayout = ids.includes(sid), full = !inLayout && ids.length >= MAX_PANES, title = session(sid) ? bareTitle(session(sid)) : "Session";
    const EDGE = 24;
    const edge = ids.length > 1 || !ids.includes(sid) ? [["left", x - box.left], ["right", box.right - x], ["top", y - box.top], ["bottom", box.bottom - y]].filter(([, d]) => d < EDGE).sort((a, b) => a[1] - b[1])[0] : null;
    if (edge && !(ids.length === 1 && ids[0] === sid)) {
      const side = edge[0], next = layoutEdge(layout, sid, side), rest = layoutWithout(layout, sid);
      const share = 1 / ((isSplit(rest) && rest.d === sideDir(side) ? rest.k.length : 1) + 1);
      const w = box.width * share, hgt = box.height * share;
      const rect = side === "left" ? { left: box.left, top: box.top, width: w, height: box.height } : side === "right" ? { left: box.right - w, top: box.top, width: w, height: box.height }
        : side === "top" ? { left: box.left, top: box.top, width: box.width, height: hgt } : { left: box.left, top: box.bottom - hgt, width: box.width, height: hgt };
      return { frame: box, rect, full, label: full ? "Four panes is the limit" : `${{ left: "Along the left", right: "Along the right", top: "Across the top", bottom: "Across the bottom" }[side]}`,
        drop: () => { if (full) return toast("Four panes is the limit. Close one to add another."); goLayout(next); say(`${title} placed ${side === "top" || side === "bottom" ? `across the ${side}` : `along the ${side}`}`); } };
    }
    const paneEl = document.elementFromPoint(x, y);
    const target = paneEl && paneEl.closest(".panes .pane");
    if (!target || !panes.contains(target)) return null;
    const tid = target.dataset.sid;
    if (tid === sid) return { frame: target.getBoundingClientRect(), rect: null, label: ids.length > 1 ? "Drop on another pane" : "Already open", drop: () => {} };
    const r = target.getBoundingClientRect(), rx = (x - r.left) / r.width, ry = (y - r.top) / r.height;
    if (fromPane && inLayout && Math.abs(rx - 0.5) < 0.2 && Math.abs(ry - 0.5) < 0.2) {
      return { frame: r, rect: { left: r.left, top: r.top, width: r.width, height: r.height }, label: "Swap places", center: true,
        drop: () => { goLayout(layoutSwap(layout, sid, tid)); say(`Swapped ${title} and ${(session(tid) || {}).title || "the other pane"}`); } };
    }
    const side = [["left", rx], ["right", 1 - rx], ["top", ry], ["bottom", 1 - ry]].sort((a, b) => a[1] - b[1])[0][0];
    const rect = side === "left" ? { left: r.left, top: r.top, width: r.width / 2, height: r.height } : side === "right" ? { left: r.left + r.width / 2, top: r.top, width: r.width / 2, height: r.height }
      : side === "top" ? { left: r.left, top: r.top, width: r.width, height: r.height / 2 } : { left: r.left, top: r.top + r.height / 2, width: r.width, height: r.height / 2 };
    const words = { left: "Split left", right: "Split right", top: "Split up", bottom: "Split down" }[side];
    return { frame: r, rect, full, label: full ? "Four panes is the limit" : words,
      drop: () => { if (full) return toast("Four panes is the limit. Close one to add another."); goLayout(layoutBeside(layout, tid, sid, side)); say(`${title} opened ${{ left: "to the left of", right: "to the right of", top: "above", bottom: "below" }[side]} ${(session(tid) || {}).title || "the pane"}`); } };
  };
  const drawTop = () => {
    const s = session(ids[0]);
    const p = s && project(s.project);
    setTop(ids.length > 1 ? [quietTail("Split")] : [p ? crumbTo(p) : null, quietTail(s ? (p ? bareTitle(s) : s.title) : "Session")].filter(Boolean), [
      phone.matches && ids.length === 1 ? null : ids.length < MAX_PANES
        ? h("button", { class: "btn", title: "Open another session beside this one. ⌘-click one in the sidebar does the same.", onclick: (e) => splitMenu(e.currentTarget) }, uiIcon("split"), "Split")
        : h("button", { class: "btn", title: "Four panes is the limit. Close one to add another.", "aria-label": "4 of 4 panes. Close one to add another.", onclick: (e) => splitMenu(e.currentTarget) }, uiIcon("split"), "4 of 4"),
      h("button", { class: `icon ${panelOn() ? "on" : ""}`, title: "Agents, images and links", "aria-pressed": panelOn() ? "true" : "false", onclick: togglePanel }, uiIcon("panel")),
    ], true);
  };
  const agentsOpen = new Set();
  let imagesSeen = null;
  const peek = (item) => {
    const entry = entries.get(item.sid);
    if (!entry) return;
    const old = entry.pane.querySelector(".peek");
    if (old) old.remove();
    const card = h("button", { class: "peek", title: "Open this image", onclick: () => { card.remove(); openPreview({ sid: item.sid, path: item.path, blob: item.blob, name: item.name, at: item.at }); } },
      h("img", { src: thumbUrl(item.sid, item), alt: item.name }));
    entry.pane.append(card);
    setTimeout(() => card.remove(), 8000);
  };
  const drawShared = guard(async (forceShow) => {
    if (panelOn() && !sharedBox.parentNode) stage.append(sharedBox);
    if (!panelOn()) sharedBox.remove();
    const asked = activeId;
    const present = [asked].filter((id) => id && session(id));
    let lists, crews;
    try {
      [lists, crews] = await Promise.all([
        Promise.all(present.map(async (id) => (await api(`/api/sessions/${id}/shared`)).map((item) => ({ ...item, sid: id })))),
        Promise.all(present.map(async (id) => (await api(`/api/sessions/${id}/agents`)).map((a) => ({ ...a, sid: id })))),
      ]);
    } catch {
      if (asked !== activeId || !panelOn()) return;
      if (!sharedBox.parentNode) stage.append(sharedBox);
      sharedKey = "";
      fill(sharedBox, retryLine("Subagents, images and links didn't load.", () => drawShared(true)));
      return;
    }
    if (asked !== activeId) return;
    const known = new Set();
    const items = lists.flat().filter((i) => { const k = i.url || i.path || `${i.sid}:${i.blob}`; if (known.has(k)) return false; known.add(k); return true; });
    const unseen = items.filter((i) => i.kind === "link" && !linkCards.has(i.url)).slice(0, 40);
    if (unseen.length) {  // only what the hub already fetched for a hover: listing links never fetches them
      const kept = await api(`/api/preview/cached?${unseen.map((i) => `url=${encodeURIComponent(i.url)}`).join("&")}`).catch(() => ({}));
      Object.entries(kept).forEach(([url, card]) => linkCards.set(url, card));
      if (asked !== activeId) return;
    }
    const of = (kind) => items.filter((i) => i.kind === kind);
    const images = of("image");
    const imageKey = (i) => i.path || `${i.sid}:${i.blob}`;
    if (imagesSeen && document.visibilityState === "visible") { const fresh = images.find((i) => !imagesSeen.has(imageKey(i))); if (fresh && !panelOn()) peek(fresh); }
    imagesSeen = new Set(images.map(imageKey));
    if (!panelOn()) { sharedBox.remove(); return; }
    if (!sharedBox.parentNode) stage.append(sharedBox);
    const crew = crews.flat();
    const owner = session(asked);
    const key = JSON.stringify([items, crew, asked, ids.length, owner && owner.title, owner && owner.state, owner && owner.asking, owner && owner.alive]);
    if (key === sharedKey && !forceShow) return;
    if (held() && !forceShow) return;  // the next poll draws it
    sharedKey = key;
    const opener = (i) => openPreview({ sid: i.sid, path: i.path, blob: i.blob, name: i.name, at: i.at, ...(i.kind === "image" ? { gallery: images, index: images.indexOf(i) } : {}) });
    const section = (title, nodes) => nodes.length ? h("section", {}, h("h2", { textContent: title }), nodes) : null;
    const running = crew.filter((a) => a.status === "running").length;
    const agentRow = (a) => {
      const open = h("details", { class: "subagent", open: agentsOpen.has(a.id), ontoggle: (e) => { if (e.target.open) agentsOpen.add(a.id); else agentsOpen.delete(a.id); } },
        h("summary", {}, dot(a.status === "running" ? "working" : a.status === "failed" ? "needs" : a.status === "stopped" ? "ended" : "finished"),
          h("span", { class: "sub-main" }, h("b", { textContent: a.what || a.type }), h("small", { textContent: a.status === "running" && a.now ? a.now : a.type })), uiIcon("chev")),
        traceBar(a.trace),
        h("div", { class: "sub-facts" }, a.tools ? h("span", { textContent: `${a.tools} tool ${a.tools === 1 ? "call" : "calls"}` }) : null, a.model ? h("span", { textContent: modelName(a.model) }) : null),
        a.result ? h("div", { class: "sub-block" }, h("h3", { textContent: "Reported" }), markdown(a.result)) : a.said ? h("div", { class: "sub-block" }, h("h3", { textContent: "Last said" }), h("p", { textContent: a.said })) : null,
        a.prompt ? h("div", { class: "sub-block" }, h("h3", { textContent: "Asked" }), h("p", { textContent: a.prompt })) : null);
      return open;
    };
    fill(sharedBox,
      ids.length > 1 && owner ? h("div", { class: "shared-for" }, dot(shownState(owner)), h("span", { class: "name", dir: "auto", textContent: owner.title })) : null,
      rail,
      crew.length ? h("section", {}, h("h2", {}, "Subagents", running ? h("span", { class: "n", textContent: `${running} running` }) : null), crew.map(agentRow)) : null,
      items.length ? section("Shared", [sharedTimeline(items, images, opener)]) : null,
      items.length || crew.length ? null : h("div", { class: "empty-line", textContent: `Subagents, images and links from this session show up here. ${phone.matches ? "Tap the paperclip under the terminal" : "Paste or drop a file into the terminal"} to share one.` }),
      owner && owner.alive ? h("button", { class: "quiet", type: "button", onclick: () => picker.click() }, uiIcon("plus"), "Share a file") : null);
  });

  ids.forEach(build);
  arrange();
  const focusPane = (index) => {
    const entry = entries.get(ids[index]);
    if (!entry) return;
    setActive(ids[index]);
    entry.pane.scrollIntoView({ block: "nearest" });
    if (entry.chat) return;  // focusing the message box would pop the phone's keyboard over the conversation
    if (entry.terminal) entry.terminal.term.focus();
    else { const first = entry.pane.querySelector(".record-top button:not(:disabled), .ended-note button"); if (first) first.focus({ preventScroll: true }); }
  };
  bind(() => inTerminal()
    ? [...(ids.length > 1 ? [[`⌥1–${ids.length}`, "pane"]] : []), ["⌃`", "leave terminal"]]
    : [["↵", "back to terminal"], ...(ids.length > 1 ? [[`1–${ids.length}`, "pane"]] : []), ...(ids.length < MAX_PANES ? [["s", "split"]] : []), ["p", "panel"], ["esc", "project"]], {
    Enter: () => focusPane(Math.max(0, ids.indexOf(activeId))), 1: () => focusPane(0), 2: () => focusPane(1), 3: () => focusPane(2), 4: () => focusPane(3),
    p: togglePanel,
    s: () => { const b = top_.querySelector(".btn"); if (b) splitMenu(b); },
    jump: focusPane,
  });
  entries.forEach((entry) => { entry.terminal && entry.terminal.start(); drawHead(entry); drawStrip(entry); });
  setActive(ids[0]);
  focusPane(0);
  painted = true;
  drawTop();
  drawRail(true);
  drawShared(true);
  // Going from one layout to another keeps every terminal that stays on screen connected.
  page.retarget = (nextLayout) => {
    const before = new Set(ids), next = leavesOf(nextLayout);
    layout = nextLayout;
    ids = next;
    entries.forEach((entry, id) => { if (!next.includes(id)) { entry.terminal && entry.terminal.dispose(); entry.pane.remove(); entries.delete(id); } });
    const fresh = next.filter((id) => !before.has(id));
    fresh.forEach(build);
    arrange();
    fresh.forEach((id) => { const entry = entries.get(id); entry.terminal && entry.terminal.start(); });
    if (!fresh.length) setTimeout(refitAll, 60);  // panes that only moved take their new size
    entries.forEach((entry) => { entry.stopping = false; drawHead(entry); drawStrip(entry); });
    imagesSeen = null;
    const target = fresh.length ? fresh[fresh.length - 1] : next.includes(activeId) ? activeId : next[0];
    setActive(target);
    focusPane(next.indexOf(target));
    drawTop();
    drawStatus();
    drawShared(true);
  };
  let polls = 0, shownTitles = "";
  page.update = () => {
    if (ids.some((id) => !session(id) && !entries.get(id).missing)) { let rest = layout; ids.filter((id) => !session(id)).forEach((id) => { rest = layoutWithout(rest, id); }); goLayout(rest); return; }
    entries.forEach((entry) => { if (entry.terminal && !session(entry.id).alive) endTerminal(entry); });  // a pane opened on an unknown id has no terminal
    // A resumed session comes back as a terminal in the same place.
    [...entries.values()].forEach((entry) => { const s = session(entry.id); if (!entry.terminal && s && s.alive) revive(entry); });
    entries.forEach((entry) => entry.drawRecordBar && entry.drawRecordBar());
    entries.forEach(drawHead);
    entries.forEach(drawStrip);
    entries.forEach((entry) => entry.chat && entry.chat.refresh && entry.chat.refresh());
    drawRail();
    if (reviewing) { if (!entries.get(reviewing.sid)) closeChanges(); else if (reviewing.stale) reviewing.stale(); }
    const titles = ids.map((id) => (session(id) || {}).title).join();
    if (titles !== shownTitles) { shownTitles = titles; drawTop(); }
    drawSwitcher();
    if (++polls % 2 === 0) drawShared();
  };
  page.leave = () => { closeChanges(); phone.removeEventListener("change", onPhoneChange); entries.forEach((entry) => entry.terminal && entry.terminal.dispose()); };
  page.selected = () => activeId;  // ⌘K acts on the pane you're in
}

// A sideways strip on a phone: the edge fades while more waits past it, and the chosen chip stays in view.
const stripCue = (list) => {
  const mark = () => list.classList.toggle("more", list.scrollLeft + list.clientWidth < list.scrollWidth - 1);
  list.addEventListener("scroll", mark, { passive: true });
  new ResizeObserver(mark).observe(list);
  return () => {
    const on = list.querySelector("a.on");
    if (on && list.scrollWidth > list.clientWidth) list.scrollLeft = Math.max(0, on.offsetLeft - list.offsetLeft - 16);
    mark();
  };
};

// ── Memory ──
// A pinned entry ends with the words the kit reads; on screen it carries the mark instead.
const pinsShown = (doc) => {
  doc.querySelectorAll("li, p").forEach((el) => {
    const last = el.lastChild;
    if (last && last.nodeType === 3 && / \(pin\)$/.test(last.textContent)) { last.textContent = last.textContent.replace(/ \(pin\)$/, " "); el.append(pinMark()); }
  });
  return doc;
};
function pageMemory(name, rest) {
  const p = project(name);
  const drawTop = () => { const now = project(name); if (now && differs(top_, "memory", tabsKey(now))) projectTop(now, "memory", []); };
  drawTop();
  page.update = drawTop;
  const root = h("div", { class: "page" });
  view.append(root);
  const results = h("div");
  const detail = h("div", { class: "doc" });
  const list = h("div", { class: "list" });
  const split = h("div", { class: "split" }, list, detail);
  const found = h("div", { class: "sr-only", role: "status" });
  const syncStrip = stripCue(list);
  let wait, searchId = 0, openId = 0, selected = rest || "ORG.md", canEdit = false;
  const clearSearch = () => { search.value = ""; clearTimeout(wait); searchId++; fill(results); found.textContent = ""; split.style.display = ""; navKey = selected; markNav(); };
  const focusFile = () => { const on = list.querySelector("a.on"); if (on) on.focus({ preventScroll: true }); };
  const runSearch = async () => {
    const q = search.value.trim(), asked = ++searchId;
    if (q.length < 2) { fill(results); found.textContent = ""; split.style.display = ""; navKey = selected; markNav(); return; }
    split.style.display = "none";
    navKey = "";
    markNav();
    const settled = loadingIn(results, "Searching…", () => asked === searchId);
    let hits;
    try { hits = await api(`/api/p/${P(name)}/search?q=${encodeURIComponent(q)}`); }
    catch { settled(); if (asked === searchId) fill(results, retryLine("Search didn't run.", runSearch)); return; }
    settled();
    if (asked !== searchId) return;
    found.textContent = hits.length ? `${hits.length} ${hits.length === 1 ? "match" : "matches"}` : `No matches for ${q}`;
    fill(results, hits.length
      ? h("div", { class: "sec" }, hits.map((hit, i) => h("a", { class: "hit", href: `#/p/${P(name)}/memory/${hit.path}`, "data-nav": `hit:${i}`,
        onclick: (e) => { const same = hit.path === selected; clearSearch(); if (same) { e.preventDefault(); open(hit.path); focusFile(); } } },
        h("small", { textContent: `${hit.path}:${hit.line}` }), h("span", { textContent: hit.text }))))
      : h("div", { class: "empty-line retry-line results-none" }, h("span", { textContent: `No matches for “${q}”` }), h("button", { class: "retry", textContent: "Clear search", onclick: () => { clearSearch(); search.focus(); } })));
    markNav();
  };
  const search = h("input", { class: "search", type: "search", placeholder: "Search memory", "aria-label": "Search memory", oninput: () => { clearTimeout(wait); wait = setTimeout(runSearch, 180); } });
  root.append(search, found, results, split);
  const open = async (path) => {
    const asked = ++openId;
    const settled = loadingIn(detail, "Loading…", () => asked === openId);
    let file;
    try { file = path === "pinned" ? { pins: await api(`/api/p/${P(name)}/pins`), content: "", editable: false, history: [] } : await api(`/api/p/${P(name)}/file?path=${encodeURIComponent(path)}`); }
    catch { settled(); if (asked === openId) fill(detail, retryLine("That file didn't load.", () => open(path))); return; }
    settled();
    if (asked !== openId) return;
    const titleOf = path === "steering" ? "Steering" : path === "pinned" ? "Pinned" : path;
    canEdit = file.editable;
    drawStatus();
    const focusEdit = () => { const b = detail.querySelector("[data-key=edit]"); if (b) b.focus({ preventScroll: true }); };
    const show_ = () => {
      page.dirty = null;
      // What every session is given first. A dream proposes a pin, and only your tick on that edit adds or removes one.
      if (file.pins) return fill(detail, h("div", { class: "doc-top" }, h("h2", { class: "doc-title", textContent: "Pinned" })),
        h("p", { class: "sec-note", textContent: "A dream proposes a pin or takes one off as an edit; your tick applies it. At most 8." }),
        file.pins.length ? h("ul", { class: "pins" }, file.pins.map((pin) => h("li", {}, h("a", { href: `#/p/${P(name)}/memory/${pin.file}`, dir: "auto", textContent: pin.title }), h("code", { textContent: pin.file.replace(/^project\//, "") }))))
          : h("p", { class: "empty-line", textContent: "Nothing is pinned yet." }));
      // A file that opens with its own heading is titled by it, with Edit on that line; the list already names the file.
      const doc = file.content.trim() ? pinsShown(markdown(file.content)) : null;
      const own = doc && doc.firstElementChild && doc.firstElementChild.tagName === "H3" ? doc.firstElementChild : null;
      if (own) own.remove();
      fill(detail,
        h("div", { class: "doc-top" }, own ? h("h2", { class: "doc-title", dir: "auto", textContent: own.textContent }) : h("h2", { textContent: titleOf }), file.editable ? h("button", { class: "btn", textContent: "Edit", "data-key": "edit", onclick: edit }) : null),
        doc || h("p", { class: "empty-line", textContent: path === "steering" ? "Tell dreaming what to look for and what to ignore." : "Nothing here yet" }),
        file.history.length ? h("section", { class: "history" }, h("h3", { textContent: "History" }), file.history.map((row) => h("div", { class: "h-row" },
          h("time", { dateTime: row.when, textContent: `${short(row.when.slice(0, 10))} ${row.when.slice(11, 16)}` }), h("span", { class: "who", textContent: row.agent }), h("span", { class: "why", dir: "auto" }, row.why, changeLine(row))))) : null);
    };
    const edit = () => {
      const area = h("textarea", { class: "edit", value: file.content, spellcheck: false, "aria-label": `Edit ${titleOf}`, onkeydown: (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveNow(); } } });
      page.dirty = () => area.value !== file.content;
      // A save that can't land says so here, stays until it's answered, and never touches what you typed.
      const trouble = h("div", { class: "edit-trouble", role: "alert" });
      const write = async () => {
        await api(`/api/p/${P(name)}/file`, { path, content: area.value, expect: file.hash });
        page.dirty = null;
        toast("Saved");
        await open(path);
        focusEdit();
      };
      const offer = (error) => {
        if (error.status !== 409) { fill(trouble, h("span", { textContent: error.known ? error.message : NO_ANSWER })); return; }
        const overwrite = h("button", { class: "btn", textContent: "Overwrite with mine", onclick: () => doOverwrite() });
        const doOverwrite = once("Overwriting…", async () => { const latest = await api(`/api/p/${P(name)}/file?path=${encodeURIComponent(path)}`); file.hash = latest.hash; await write(); }, overwrite);
        fill(trouble, h("span", { textContent: "This file changed while you were editing. Your text is still here." }),
          h("div", { class: "edit-acts" }, overwrite, h("button", { class: "btn", textContent: "Reload and lose mine", onclick: async () => {
            if (!await confirmStep({ title: "Lose your edits?", body: "The file reloads as it is now, and what you typed goes.", yes: "Reload and lose mine", no: "Keep editing" })) return;
            page.dirty = null; await open(path); focusEdit();
          } })));
      };
      const saveBtn = h("button", { class: "btn primary", textContent: "Save", title: "⌘S", onclick: () => saveNow() });
      const saveNow = once("Saving…", async () => { fill(trouble); try { await write(); } catch (error) { offer(error); area.focus(); } }, saveBtn);
      const cancel = async () => {
        if (page.dirty() && !await confirmStep({ title: `Discard your edits to ${titleOf}?`, body: "What you changed in this file hasn't been saved.", yes: "Discard edits", no: "Keep editing" })) { area.focus(); return; }
        show_();
        focusEdit();
      };
      fill(detail, h("div", { class: "doc-top" }, h("h2", { textContent: titleOf }), h("div", { class: "edit-acts" },
        h("button", { class: "btn", textContent: "Cancel", onclick: cancel }),
        saveBtn)), trouble, area);
      area.focus();
    };
    show_();
  };
  const paintChips = () => { list.querySelectorAll("a").forEach((a) => { const on = a.dataset.nav === selected; a.classList.toggle("on", on); if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }); syncStrip(); };
  const loadFiles = async () => {
    const settled = loadingIn(detail, "Loading…");
    let files;
    try { files = await api(`/api/p/${P(name)}/memory`); }
    catch { settled(); fill(list); fill(detail, retryLine("Memory didn't load.", loadFiles)); return; }
    settled();
    const baseOf = (path) => path.replace(/^(project|inbox)\//, "").replace(/^agents\/(.*)\/scratch\.md$/, "$1");
    const twice = (path) => files.filter((f) => baseOf(f.path) === baseOf(path)).length > 1;
    const link = (path, label) => h("a", { "data-nav": path, href: `#/p/${P(name)}/memory/${path}`, title: path, textContent: label || (twice(path) ? path : baseOf(path)) });
    const part = (test) => files.filter((f) => test(f.path)).map((f) => link(f.path));
    fill(list, part((x) => x === "ORG.md"), link("steering", "Steering"), link("pinned", "Pinned"), h("div", { class: "gap" }),
      part((x) => x.startsWith("project/")), h("div", { class: "gap" }),
      part((x) => x.startsWith("inbox/")), part((x) => x.startsWith("agents/")), h("div", { class: "gap" }),
      part((x) => x === "INDEX.md" || x === "CHANGELOG.md"));
    paintChips();
    navKey = selected;
    markNav();
    await open(selected);
  };
  loadFiles();
  // Opening another file only swaps the text, so focus, the strip and the list stay where they are.
  page.retarget = (next) => {
    selected = next || "ORG.md";
    paintChips();
    navKey = selected;
    markNav();
    open(selected);
    if (document.activeElement === document.body || document.activeElement === view) focusFile();
  };
  bind(() => [["j k", "move"], ["↵", "open"], ["/", "search"], ...(canEdit ? [["e", "edit"]] : []), ["esc", "project"]], {
    "/": () => search.focus(),
    e: () => { const area = detail.querySelector("textarea.edit"); if (area) { area.focus(); return; } const b = detail.querySelector("[data-key=edit]"); if (b) b.click(); },
  });
}

// ── Dreams ──
// The two sections that aren't plain memory changes each say what a tick does.
const SECTION_NOTES = {
  yours: "Only you change these. Applying leaves the ticked ones for you, with the two commands to run.",
  "own-notes": "Claude Code kept these outside memory, unchecked. Ticked ones become memory lines.",
  carry: "Facts from Claude Code's own notes that the dream checked. Each goes into the file it names; switch one off to leave it out.",
  unchecked: "Claude Code's own notes say these, and nothing could check them. Your tick is the check: tick only what you know holds.",
};
// A need's line is a sentence and where it shows: the sentence leads, the evidence follows quietly.
// A need's line: its sentence, then its evidence, then who can put it right (` · fix: …` or ` · yours: …`), which is shown in words of its own.
const needParts = (text) => { const at = text.indexOf(" · evidence: "); if (at < 0) return [text, ""]; const ev = text.slice(at + 13); const who = ev.search(/ · (fix|yours): /); return [text.slice(0, at), who < 0 ? ev : ev.slice(0, who)]; };
const stemOf = (file) => file.replace(/-proposal\.md$/, "");
const PART_WORDS = { applied: "Written", "already applied": "Already there", refused: "Refused", "left out": "Left out" };
// Claude's own notes, by what is left to do: dream, then apply, then turn them off. The command follows each sentence.
const ownNotesLeft = (own, applied) => !own.carried ? "Claude keeps its own notes for this project, outside memory. The next dream proposes the ones worth keeping. Once you've applied it, turn them off with "
  : applied ? "The newest dream carried Claude's own notes over and has been applied. What's left is to turn them off with "
  : "The newest dream lists the notes of Claude's own worth keeping. Tick and apply them, then turn them off with ";
// What became of a ticked item when the proposal was applied, from the kit's record of it.
const FATE_WORDS = { applied: "Applied", "already applied": "Already there", refused: "Refused", yours: "Yours to apply", "needs a session": "Waiting for a session" };
// `act` is the way to get on with one that waits for a session, once its proposal is closed: until then Apply's own session does it.
const fateLine = (fate, act) => !fate ? null : h("div", { class: `fate ${fate.result === "refused" ? "no" : ""}` }, h("b", { textContent: FATE_WORDS[fate.result] }),
  fate.result === "needs a session" ? h("span", { textContent: act ? "/dream apply in a session does it." : "The session that applies this proposal does it." }) : null, act || null,
  fate.reason && fate.result !== "yours" ? h("span", { dir: "auto", textContent: fate.reason }) : null,  // what to do with one of yours is said once, with its commands
  fate.commits.map((id) => h("code", { textContent: id })));
const copyButton = (text) => h("button", { class: "retry", type: "button", textContent: "Copy", onclick: guard(async () => { await navigator.clipboard.writeText(text); toast("Copied"); }) });
const CARRIED_LEAD = { delete: "Delete", merge: "Merge", split: "Split into", carry: "Carry from" };
function pageDreams(name, rest) {
  const root = h("div", { class: "page" });
  view.append(root);
  const metaBox = h("div", { class: "dream-top" });
  const list = h("div", { class: "list" });
  const detail = h("div", {});
  const syncStrip = stripCue(list);
  let data = { dreams: [], earlier: [], metrics: [], left: [], held: "", checks: [], problem: "", actions: [], needs: { open: [], problem: "" }, pins: [] }, current = null, wasDreaming = false, finished = "";
  // One proposal at most is open, and only that one is ticked, applied or dismissed. The kit's record says which.
  const reviewing = () => !!current && current.state === "open";
  const allItems = () => current.sections.flatMap((s) => s.items);
  const dreamButton = () => top_.querySelector("[data-key=dream-now]");
  // The kit starts no dream while another is alive or a proposal is open. Its sentence is the answer; a dream that is held can be given up.
  const askRelease = guard(async (sentence) => {
    const sure = await confirmStep({ title: "Give up the dream that is running?", body: `${sentence} Giving it up discards its batch and whatever its analysts found. Nothing in memory changes, and the next dream reads the same sessions.`, yes: "Give it up", no: "Leave it" });
    if (!sure) return;
    finished = (await api(`/api/p/${P(name)}/dream/release`, {})).said;
    say(finished);
    await loadDreams();
  });
  const runDream = once("Starting…", async () => {
    finished = "";
    try { await api(`/api/p/${P(name)}/dream/run`, {}); }
    catch (error) { if (!error.held) throw error; await loadDreams(); askRelease(error.message); return; }
    await tick();
  });
  const dreamNow = async (byKey) => {
    const p = project(name), b = dreamButton();
    if (!p || p.dreaming || !b || b.getAttribute("aria-busy")) return;
    if (byKey && !(await confirmStep({ title: "Dream now?", body: "Reviews recent sessions and proposes memory changes.", yes: "Dream now", no: "Cancel" }))) return;
    runDream({ currentTarget: dreamButton() });
  };
  // A run that ends says how it ended: the button coming back isn't an answer.
  const afterDream = guard(async () => {
    const before = data.dreams[0] && data.dreams[0].file;
    const fresh = await api(`/api/p/${P(name)}/dreams`);
    if ((fresh.dreams[0] && fresh.dreams[0].file) === before) { finished = "Finished with nothing new to review"; say(finished); drawMeta(); return; }
    finished = "";
    say("New dream ready to review");
    await loadDreams();
  });
  const drawMeta = () => {
    const p = project(name);
    if (!p) return;
    if (wasDreaming && !p.dreaming) afterDream();
    wasDreaming = p.dreaming;
    const hour = p.schedule ? p.schedule.hour : null;
    if (differs(top_, "dreams", tabsKey(p), p.dreaming, reviewing())) projectTop(p, "dreams", [h("button", { class: `btn ${reviewing() ? "" : "primary"}`, textContent: "Dream now", "data-key": "dream-now", "aria-disabled": p.dreaming ? "true" : undefined, onclick: () => dreamNow(false) })]);
    const own = p.setup.find((item) => item.key === "own-notes");
    const applied = !!p.latest && p.latest.state === "applied";
    // Three kinds of item a closed proposal left, by the kit's own word for each: approved and waiting to be done (oldest
    // first), handed to the next dream, and declined. Being ticked decides nothing here.
    const approved = data.left.filter((i) => i.waiting).sort((a, b) => a.at - b.at), waiting = data.left.filter((i) => !i.waiting && !i.declined), declined = data.left.filter((i) => i.declined);
    if (differs(tailBox, data.left, data.actions)) fill(tailBox,
      waiting.length ? h("details", { class: "sec carried" }, h("summary", { textContent: `${waiting.length} ${waiting.length === 1 ? "item waits" : "items wait"} for the next dream` }),
        h("p", { class: "sec-note", textContent: "Left unapplied when a proposal was closed: not ticked, refused by the store, or in a proposal you dismissed. The next dream proposes each again if what it reads still supports it." }), waiting.map(carried)) : null,
      declined.length ? h("details", { class: "sec carried" }, h("summary", { textContent: `${declined.length} declined` }),
        h("p", { class: "sec-note", textContent: "Passed over twice when a proposal was applied, so no dream proposes them again." }), declined.map(carried)) : null,
      // What only you may do, and was done: from this memory's own history, whichever way it was done. A line you don't recognise is worth a look.
      data.actions.length ? h("details", { class: "sec carried actions" }, h("summary", { textContent: "Done in your name" }),
        h("p", { class: "sec-note", textContent: "Changes to this memory that only you may make, newest first. The hub can't tell you from a program running as you on this Mac, so this list is how you would notice one." }),
        data.actions.map((a) => h("div", { class: "p" }, h("span", { class: "k", dir: "auto", textContent: a.what }), h("span", { class: "v" }, h("span", { class: "mono", textContent: new Date(a.at * 1000).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) }), a.hub ? h("small", { textContent: "through Dream Hub" }) : null)))) : null);
    if (differs(metaBox, p.schedule, p.dreaming, p.batch, finished, dreamCheck(p.check), own, applied, data.held, data.problem, data.checks, data.left, data.needs, needsAll)) fill(metaBox, h("div", { class: "dream-meta" },
      h("button", { class: `switch ${p.schedule ? "on" : ""}`, title: "Automatic dreams", "aria-pressed": p.schedule ? "true" : "false", onclick: guard(async () => { await api(`/api/p/${P(name)}/schedule`, { on: !p.schedule, hour }); await tick(); }) }),
      h("span", { textContent: dreamTiming(p.schedule) }),
      p.dreaming ? h("span", { textContent: p.batch ? `Dreaming over ${p.batch} sessions…` : "Dreaming…" }) : null,
      p.dreaming ? null : h("button", { class: "btn dream-now-m", type: "button", "data-key": "dream-now-m", textContent: "Dream now", onclick: () => dreamNow(false) })),
      dreamWhy(p.check),
      // What the kit said when a proposal was dismissed, a dream given up or a declined item let back in: its own words.
      finished && !p.dreaming ? h("p", { class: "dream-note said", role: "status", textContent: finished }) : null,
      data.held && !p.dreaming ? h("p", { class: "dream-note held" }, h("span", { textContent: data.held }), " ", h("button", { class: "retry", "data-key": "release", textContent: "Give it up", onclick: () => askRelease(data.held) })) : null,
      data.problem ? h("div", { class: "callout", role: "alert" }, h("p", { textContent: data.problem })) : null,
      needsBox(),
      data.checks.filter((line) => line !== data.problem).length ? h("div", { class: "callout checks" }, h("h2", { textContent: "The kit's check of this memory found" }),
        h("ul", {}, data.checks.filter((line) => line !== data.problem).map((line) => h("li", { dir: "auto", textContent: line })))) : null,
      own ? h("p", { class: "dream-note" }, ownNotesLeft(own, applied), h("code", { textContent: own.then }), ".") : null,
      approved.length ? h("details", { class: "sec carried" }, h("summary", { textContent: `${approved.length} approved, not yet done` }),
        h("p", { class: "sec-note", textContent: "You approved these and nobody has done them yet. They stay, through later proposals, until they are done or you take them back." }), approved.map(carried)) : null,
      null);
  };
  // What dreams said needs the person: not memory, so nothing here is ticked or applied. Each says who can put it right.
  // One an agent can fix (or one not sorted) is approved for the fixer, or rejected; one only the person can do is done,
  // or rejected. The kit's `approve`, `reject` and `done` decide; the fixer's run shows in its state. A rejected one is
  // gone from here: no dream says it again.
  let needsAll = false;
  const fixAt = () => data.needs.fix_hour === null || data.needs.fix_hour === undefined ? "" : `${String(data.needs.fix_hour).padStart(2, "0")}:00`;
  const needState = (need) => {
    const r = need.result;
    if (need.state === "approved") return data.needs.fixing ? "Approved. The fixer is running" : fixAt() ? `Approved. The fixer runs at ${fixAt()}` : "Approved. Run fixes now to start the fixer";
    if (need.state === "fixing") return "Being fixed";
    if (need.state === "fixed") return r.merged ? `Fixed: ${r.summary}, merged into ${r.merged}` : `Fixed on branch ${r.branch}, not merged: ${r.kept}. ${r.summary}`;
    if (need.state === "stopped") return `Stopped: ${r.summary}`;
    return "";
  };
  const needWho = (need) => need.who === "agent" ? `An agent can fix it in ${need.repo}: ${need.change}` : need.who === "you" ? `Only you: ${need.why}` : "Not sorted: the fixer works out where, or stops and says so";
  const askReject = (need) => guard(async () => {
    const sure = await confirmStep({ title: "Reject this?", body: "It stays on record as rejected, and no dream says it again.", yes: "Reject", no: "Keep it" });
    if (sure) await kitSays("reject", { words: need.text })();
  });
  const needActs = (need, i) => {
    const fixable = need.who !== "you";
    const approve = (word) => h("button", { class: "retry", "data-key": `approve:${i}`, textContent: word, title: "An agent makes the change in a worktree of its own and merges it when that is safe.", onclick: kitSays("approve", { words: need.text }) });
    const done = h("button", { class: "retry", "data-key": `done:${i}`, textContent: "Done", title: "Dealt with, or not wanted. A dream that sees it again says so again.", onclick: kitSays("done", { words: need.text }) });
    const reject = h("button", { class: "retry", "data-key": `reject:${i}`, textContent: "Reject", title: "No dream says it again.", onclick: askReject(need) });
    const acts = need.state === "open" ? (fixable ? [approve("Approve fix"), reject] : [done, reject])
      : need.state === "approved" ? [reject] : need.state === "fixed" ? [done] : need.state === "stopped" ? (fixable ? [approve("Approve again"), done, reject] : [done, reject]) : [];
    return acts.length ? h("div", { class: "need-acts" }, acts) : null;
  };
  const needsBox = () => {
    const open = data.needs.open;
    if (!open.length && !data.needs.problem) return null;
    const whence = (need) => [`said in ${stemOf(need.from)}`, need.said > 1 ? `${need.said} times, last in ${stemOf(need.last)}` : null].filter(Boolean).join(", ");
    const shared = open.length && open.every((n) => whence(n) === whence(open[0])) ? whence(open[0]) : "";
    const SHOW = 3, rest = needsAll || open.length <= SHOW + 1 ? 0 : open.length - SHOW;
    const yours = open.filter((n) => n.state === "open" || n.state === "stopped").length;
    const approved = open.some((n) => n.state === "approved");
    return h("section", { class: "callout needs", "aria-labelledby": "needs-title" },
      h("header", { class: "needs-head" }, h("h2", { id: "needs-title", textContent: yours ? `${yours} ${yours === 1 ? "thing needs" : "things need"} you` : "Needs you" }),
        shared ? h("span", { class: "needs-from", textContent: shared }) : null,
        approved && !data.needs.fixing ? h("button", { class: "retry need-run", "data-key": "fix-now", textContent: "Run fixes now", onclick: once("Starting…", async () => { await api(`/api/p/${P(name)}/dream/fix`, {}); say("The fixer is running"); await loadDreams(); }) }) : null),
      data.needs.problem ? h("p", { role: "alert", textContent: data.needs.problem }) : null,
      open.slice(0, open.length - rest).map((need, i) => {
        const [sentence, evidence] = needParts(need.text);
        const state = needState(need);
        return h("div", { class: `need-row ${need.state === "fixed" ? "closed" : ""}`, "data-nav": `need:${i}` },
          h("p", { dir: "auto", textContent: sentence }),
          h("div", { class: "need-sub" }, shared ? null : h("span", { textContent: whence(need) }), evidence ? h("span", { class: "mono", dir: "auto", textContent: evidence }) : null, h("span", { dir: "auto", textContent: needWho(need) })),
          state ? h("p", { class: `need-state ${need.state}`, dir: "auto", role: "status", textContent: state }) : null,
          needActs(need, i));
      }),
      rest ? h("button", { class: "disclose need-more", type: "button", "aria-expanded": "false", onclick: () => { needsAll = true; drawMeta(); const next = metaBox.querySelector(`[data-nav="need:${SHOW}"] button`); if (next) next.focus(); } }, h("span", { class: "chev" }, svg(UI.chev)), `${rest} more`) : null);
  };
  // An item a closed proposal left. What can be done with it is the person's step, and the kit's words come back:
  // a waiting one is done (in a terminal, or by a session) or taken back; a declined one can be let back in.
  const kitSays = (path, body) => once("One moment…", async () => { finished = (await api(`/api/p/${P(name)}/dream/${path}`, body)).said; say(finished); await loadDreams(); });
  const openIn = (path) => once("Opening…", async () => { const result = await api(`/api/p/${P(name)}/dream/${path}`, {}); await tick(); go(`#/s/${result.ids[0]}`); });
  const takeBack = (item) => guard(async () => {
    const sure = await confirmStep({ title: "Take back this approval?", body: "It stops waiting to be done. A dream may propose it again.", yes: "Take it back", no: "Leave it" });
    if (sure) await kitSays("withdraw", { item: item.item })();
  });
  const carried = (item) => h("div", { class: "change kept" },
    h("div", { class: "what" }, CARRIED_LEAD[item.action.split(" ")[0]] ? [h("b", { textContent: CARRIED_LEAD[item.action.split(" ")[0]] }), " "] : null, h("span", { dir: "auto" }, inline((item.action === "carry" ? item.file.replace(/^notes /, "") : item.quote || item.item).replace(/^- /, "")))),
    item.replaces ? h("div", { class: "was" }, h("span", { class: "was-word", textContent: "Replaces" }), h("del", { dir: "auto" }, inline(item.replaces.replace(/^- /, "")))) : null,
    h("div", { class: "sub", textContent: [item.file !== item.quote && item.action !== "carry" ? item.file : null, item.action === "carry" ? null : item.action, `from ${item.from.replace("-proposal.md", "")}`,
      item.waiting ? `approved ${agoWords(item.at)}` : null, item.waiting === "you" ? "waits for you" : item.waiting === "a session" ? "waits for a session" : null,
      item.waiting || item.declined ? null : item.ticked ? "ticked, not applied" : item.left ? "passed over once" : "not decided"].filter(Boolean).join(" · ") }),
    item.way ? h("div", { class: `fate ${item.dead ? "no" : ""}` }, h("span", { dir: "auto", textContent: item.way })) : null,
    item.waiting ? h("div", { class: "kept-acts" },
      item.dead ? null : item.waiting === "you" ? h("button", { class: "retry", "data-key": `yours:${item.id}`, textContent: "Open a terminal for it", onclick: openIn("yours") })
        : h("button", { class: "retry", "data-key": `session:${item.id}`, textContent: "Start a session for it", onclick: openIn("session") }),
      h("button", { class: "retry", "data-key": `withdraw:${item.id}`, textContent: "Take back", onclick: takeBack(item) })) : null,
    item.declined ? h("button", { class: "retry", "data-key": `forget:${item.id}`, textContent: "Allow it to be proposed again", onclick: kitSays("forget", { item: item.item }) }) : null);
  const tailBox = h("div", { class: "dream-tail" });
  root.append(metaBox, h("div", { class: "split" }, list, detail), tailBox);
  const stats = () => {
    const at = data.metrics.findLastIndex((m) => m.date === current.file.slice(0, 10));
    if (at < 0) return null;
    const [last, before] = [data.metrics[at], data.metrics[at - 1]];
    const delta = (a, b) => {
      if (b === undefined || !b) return null;
      const pct = Math.round((a - b) / b * 100);
      return pct ? h("em", { class: pct < 0 ? "good" : "bad", textContent: `${pct > 0 ? "+" : ""}${pct}%` }) : null;
    };
    const per = (m, key) => m.sessions ? Math.round(m[key] / m.sessions) : 0;
    return h("div", { class: "stats" },
      h("div", { class: "stat" }, h("b", { class: last.errors_per_100_tool_calls ? "" : "zero" }, String(last.errors_per_100_tool_calls), delta(last.errors_per_100_tool_calls, before && before.errors_per_100_tool_calls)), h("span", { textContent: "errors per 100 tool calls" })),
      h("div", { class: "stat" }, h("b", { class: per(last, "tool_calls") ? "" : "zero" }, String(per(last, "tool_calls")), delta(per(last, "tool_calls"), before && per(before, "tool_calls"))), h("span", { textContent: "tool calls per session" })),
      h("div", { class: "stat" }, h("b", { class: last.sessions ? "" : "zero" }, String(last.sessions)), h("span", { textContent: `sessions over ${last.days} days` })));
  };
  const change = (item, grouped) => {
    const readOnly = current.state !== "open";
    const box = h("input", { type: "checkbox", checked: item.checked, disabled: readOnly, onchange: guard(async () => {
      try {
        const result = await api(`/api/p/${P(name)}/dream/tick`, { file: current.file, line: item.line, checked: box.checked, expect: current.hash });
        current.hash = result.hash; item.checked = box.checked; drawApply(); drawCounts();
      } catch (error) { box.checked = !box.checked; throw error; }
    }) });
    const d = item.details, verb = item.action.split(" ")[0], gone = verb === "delete";
    const carry = verb === "carry" && item.facts.length;
    const lead = item.pin ? (item.pin === "pin" ? "Pin" : "Unpin") : carry ? "Carry from" : { delete: "Delete", merge: "Merge", split: "Split into" }[verb];
    // A pin changes nothing but the suffix, so the line is shown once, without it; a carry item names the note it comes from.
    const line = item.pin ? (item.pin === "pin" ? item.replaces : item.quote).replace(/^- /, "")
      : carry ? item.file.replace(/^notes /, "") : (item.quote || item.text).replace(/^- /, "");
    const fate = current.fates[item.id];
    const kept = carry ? item.facts.filter((f) => f.sign === "+").length : 0;
    // One faint line: the file when no group names it, how often it was seen and what it costs. The verb is already said.
    const sub = carry ? `${kept} of ${item.facts.length} ${item.facts.length === 1 ? "fact" : "facts"} carried`
      : [grouped ? null : item.file, d.seen && /^[\d~≥]/.test(d.seen) && `seen ${d.seen}`, d.cost && `cost ${d.cost}`].filter(Boolean).join(" · ");
    const openings = (list) => h("ul", { class: "parts" }, list.map((words) => h("li", { dir: "auto", textContent: `${words.replace(/^- /, "")}…` })));
    const why = d.why || d.evidence ? h("div", { class: "ev", hidden: true }, d.why ? h("p", { class: "ev-why" }, inline(d.why)) : null, d.evidence ? h("p", { class: "ev-from", dir: "auto", textContent: d.evidence }) : null) : null;
    const whyButton = why ? h("button", { type: "button", class: "ev-toggle", "aria-expanded": "false", "aria-label": "Why and evidence", title: "Why and evidence",
      onclick: (e) => { const opened = why.hidden; why.hidden = !opened; e.currentTarget.setAttribute("aria-expanded", opened ? "true" : "false"); } }, svg(UI.chev)) : null;
    // The box is named by its action line alone. The rest of the row still ticks it for a pointer.
    return h("div", { class: "change", "data-nav": `c:${item.line}`, onclick: (e) => { if (!e.target.closest("label, details, a, button, .facts, .ev") && !String(getSelection())) box.click(); } },
      h("label", { class: "tick" }, box, h("div", { class: gone ? "what del" : "what" }, lead ? [h("b", { textContent: lead }), " "] : null,
        verb === "split" || carry ? line.split(", ").map((file, i) => [i ? ", " : null, h("code", { textContent: file })]) : h("span", { dir: "auto" }, inline(line)),
        item.pin ? pinMark() : null)),
      h("div", { class: "body" },
        carry ? h("ul", { class: "facts" }, item.facts.map((f) => factRow(item, f, fate))) : null,
        // An edit shows the line that goes under the line that comes. A pin's two lines are the same line.
        item.replaces && !item.pin ? h("div", { class: "was" }, h("span", { class: "was-word", textContent: "Replaces" }), h("del", { dir: "auto" }, inline(item.replaces.replace(/^- /, "")))) : null,
        item.stands_for.length ? h("div", { class: "was" }, h("span", { class: "was-word", textContent: `In place of ${item.stands_for.length === 1 ? "1 line" : `${item.stands_for.length} lines`}` }), openings(item.stands_for)) : null,
        item.moves.map((move) => h("div", { class: "was" }, h("code", { textContent: move.file }), h("span", { class: "was-n", textContent: `${move.lines.length} ${move.lines.length === 1 ? "line" : "lines"}` }), openings(move.lines))),
        sub || fate || whyButton ? h("div", { class: "meta" }, whyButton, sub ? h("span", { class: "sub", textContent: sub }) : null,
          fateLine(fate, current.state !== "open" && data.left.some((i) => i.id === item.id && i.from === current.file && i.waiting === "a session")
            ? h("button", { class: "retry", "data-key": `fate-session:${item.id}`, textContent: "Start a session for it", onclick: openIn("session") }) : null),
          null) : null,
        why));
  };
  // A section's items, one group per file they change, in the order the dream wrote them. Mark a file viewed and it
  // folds; viewed is kept per browser, for the open proposal.
  const VIEWED = "hub.viewed";
  const viewedKey = () => `${name}/${current.file}`;
  const viewedSet = () => new Set(saved.get(VIEWED, {})[viewedKey()] || []);
  const setViewed = (key, on) => {
    const all = saved.get(VIEWED, {}), mine = new Set(all[viewedKey()] || []);
    if (on) mine.add(key); else mine.delete(key);
    delete all[viewedKey()];
    all[viewedKey()] = [...mine];
    saved.set(VIEWED, Object.fromEntries(Object.entries(all).slice(-20)));
  };
  const folds = new Map();
  const fileGroup = (section, file, items) => {
    const key = `${section.name}|${file}`, viewed = reviewing() && viewedSet().has(key);
    const folded = folds.has(key) ? folds.get(key) : viewed;
    const body = h("div", { class: "fg-body", hidden: folded }, items.map((item) => change(item, true)));
    const fold = (to) => { folds.set(key, to); body.hidden = to; toggle.setAttribute("aria-expanded", to ? "false" : "true"); group.classList.toggle("folded", to); };
    const toggle = h("button", { type: "button", class: "fg-toggle", "aria-expanded": folded ? "false" : "true", onclick: () => fold(!body.hidden) },
      h("span", { class: "chev-s" }, svg(UI.chev)), h("code", { dir: "auto", textContent: file }));
    const group = h("section", { class: `fgroup ${folded ? "folded" : ""}`, "aria-label": file },
      h("div", { class: "fg-head" }, toggle, h("span", { class: "fg-n" }),
        reviewing() ? h("label", { class: "fg-viewed" }, h("input", { type: "checkbox", checked: viewed, onchange: (e) => { setViewed(key, e.target.checked); fold(e.target.checked); drawCounts(); } }), h("span", { textContent: "Viewed" })) : null),
      body);
    group.items = items;
    return group;
  };
  const groupsOf = (section) => {
    const byFile = section.items.every((i) => i.file && !i.facts.length && !i.group) && section.kind !== "needs";
    if (!byFile) return [...new Set(section.items.map((i) => i.group))].map((g) => [g ? h("h3", { class: "sec-group", textContent: g }) : null, section.items.filter((i) => i.group === g).map((i) => change(i, false))]);
    return [...new Set(section.items.map((i) => i.file))].map((file) => fileGroup(section, file, section.items.filter((i) => i.file === file)));
  };
  // The totals stay in view while you review: what was proposed, what is ticked, and on an open proposal how many
  // files you have marked viewed.
  const reviewHead = h("div", { class: "review-head" });
  const drawCounts = () => {
    if (!current || current.gone) return;
    const items = allItems(), ticked = items.filter((i) => i.checked).length;
    const facts = items.filter((i) => i.facts.length && i.action.startsWith("carry"));
    const carried = facts.reduce((n, i) => n + i.facts.filter((f) => f.sign === "+").length, 0), offered = facts.reduce((n, i) => n + i.facts.length, 0);
    const groups = [...detail.querySelectorAll(".fgroup")];
    groups.forEach((g) => { g.querySelector(".fg-n").textContent = reviewing() ? `${g.items.filter((i) => i.checked).length} of ${g.items.length}` : String(g.items.length); });
    const viewed = groups.filter((g) => g.querySelector(".fg-viewed input:checked")).length;
    const state = current.state === "applied" ? `Applied ${dayOf(current.closed)}` : current.state === "dismissed" ? `Dismissed ${dayOf(current.closed)}. Its items went to the next dream.`
      : current.state === "earlier" ? "From before the kit kept a record of proposals. It can be read, and nothing in it can be changed." : "";
    fill(reviewHead, h("h2", { class: "sr-only", textContent: current.title }),
      h("div", { class: "totals" }, h("b", { textContent: String(items.length) }), " proposed", h("i", { textContent: "·" }), h("b", { textContent: String(ticked) }), current.state === "open" ? " ticked" : " approved",
        offered ? [h("i", { textContent: "·" }), h("b", { textContent: String(carried) }), ` of ${offered} ${offered === 1 ? "fact" : "facts"} carried`] : null),
      state ? h("div", { class: "dream-state", textContent: state }) : reviewing() && groups.length ? h("div", { class: "viewed-n", textContent: `${viewed} of ${groups.length} files viewed` }) : null);
  };
  // One fact of a carry item: on, it goes into the file it names; off, it is left out. Only the sign in the proposal
  // changes, so the item stays the one the dream wrote. Once applied, each fact says what the kit did with it.
  const factRow = (item, f, fate) => {
    const part = fate && fate.parts.find((p) => p.file === f.file && p.line === `${f.text}`);
    const on = f.sign === "+";
    const toggle = h("button", { type: "button", class: `switch small ${on ? "on" : ""}`, role: "switch", "aria-checked": on ? "true" : "false", disabled: current.state !== "open",
      "aria-label": `Carry: ${f.text.replace(/^- (\[[^\]]*\] )?/, "")}`, onclick: guard(async (e) => {
        e.stopPropagation();
        const result = await api(`/api/p/${P(name)}/dream/fact`, { file: current.file, line: f.line, carry: !on, expect: current.hash });
        current.hash = result.hash; f.sign = on ? "-" : "+";
        const row = toggle.closest(".change");
        row.replaceWith(change(item));
        markNav();
      }) });
    return h("li", { class: on ? "fact" : "fact out" }, toggle,
      h("div", {}, h("span", { class: "fact-line", dir: "auto" }, inline(f.text.replace(/^- (\[[^\]]*\] )?/, ""))),
        h("div", { class: "fact-sub" }, h("code", { textContent: f.file }), f.machine ? h("span", { textContent: `checked on this machine (${f.machine})` }) : null,
          part ? h("b", { class: part.result === "refused" ? "no" : "", textContent: PART_WORDS[part.result] }) : null,
          part && part.result === "refused" ? h("span", { dir: "auto", textContent: part.reason }) : null)));
  };
  const applyBar = h("div", { class: "applybar" });
  const applyNow = once("Applying…", async () => { const result = await api(`/api/p/${P(name)}/dream/apply`, { file: current.file }); await tick(); go(`#/s/${result.ids[0]}`); });
  const askApply = async () => {
    const b = applyBar.querySelector("button");
    if (!b || b.getAttribute("aria-disabled")) return;
    const ticked = allItems().filter((i) => i.checked), gone = ticked.filter((i) => i.action === "delete").length;
    const count = `${ticked.length} ${ticked.length === 1 ? "change" : "changes"}`;
    const yours = current.sections.filter((s) => s.kind === "yours").flatMap((s) => s.items).filter((i) => i.checked).length;
    const sure = await confirmStep({ title: `Apply ${count}?`, body: `An agent writes ${ticked.length === 1 ? "it" : "them"} into memory.${gone ? ` ${gone === 1 ? "One removes a line" : `${gone} remove lines`} from memory.` : ""}${yours ? ` ${yours === 1 ? "One is" : `${yours} are`} for ORG.md or Steering, and left for you to apply.` : ""}`, yes: `Apply ${count}`, no: "Keep reviewing" });
    if (sure) applyNow({ currentTarget: applyBar.querySelector("button") });
  };
  // Closing a proposal without applying it. Nothing is lost by it, and saying so is the point of asking.
  const askDismiss = guard(async () => {
    const sure = await confirmStep({ title: "Dismiss this proposal?", body: "Nothing in it is applied. Every item in it is handed to the next dream, and none counts as declined.", yes: "Dismiss", no: "Keep it" });
    if (!sure) return;
    finished = (await api(`/api/p/${P(name)}/dream/dismiss`, { file: current.file })).said;
    say(finished);
    await tick();
    await loadDreams();
  });
  const drawApply = () => {
    if (!current || applyBar.querySelector("[aria-busy]")) return;
    const ticked = allItems().filter((i) => i.checked).length;
    fill(applyBar, !reviewing() ? null : [h("button", { class: "btn primary big", "data-key": "apply", "aria-disabled": ticked ? undefined : "true", textContent: ticked ? `Apply ${ticked} ${ticked === 1 ? "change" : "changes"}` : "Tick changes to apply",
      onclick: (e) => { if (ticked) applyNow(e); } }), h("button", { class: "btn big", "data-key": "dismiss", textContent: "Dismiss", onclick: askDismiss })]);
  };
  // ORG.md and Steering are the person's tier: no agent applies them and the hub never lifts the lock. It shows the two
  // commands, and can open a terminal on the second, where the kit's own pass shows each change and asks before it writes.
  const yoursBox = (yours) => h("div", { class: "callout yours" }, h("h2", { textContent: `Yours to apply: ${yours.waiting} ${yours.waiting === 1 ? "change" : "changes"} to ORG.md or Steering` }),
    h("p", { textContent: "No agent applies these, and the hub doesn't either. Lift the lock on ORG.md yourself, then run the kit's pass: it shows each change, asks for a typed yes, and locks the file again." }),
    [yours.lift, yours.run].map((command) => h("div", { class: "command-row" }, h("code", { textContent: command }), copyButton(command))),
    h("button", { class: "btn", "data-key": "yours-terminal", textContent: "Open a terminal for it", onclick: once("Opening…", async () => {
      const result = await api(`/api/p/${P(name)}/dream/yours`, {});
      await tick();
      go(`#/s/${result.ids[0]}`);
    }) }));
  // What the dream read and did not propose, from the file it wrote beside the proposal: note by note, what was
  // stale, what could not be checked, what was checked here, and what was turned away. Read only.
  // The dream's Summary, read as what it is: the verdict on its own line, then one row per finding, each under the
  // dream's own word for it ("Biggest pattern", "Memory health"). The line naming the side file opens that file below.
  const SUMMARY_ROW = /^([A-Z][A-Za-z ]{2,30}?)(?: \(([^)]*)\))?: (.+)$/;
  const summaryOf = (text) => {
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    const rows = [], lead = [];
    for (const line of lines) {
      const m = line.match(SUMMARY_ROW);
      if (!m) { (rows.length ? rows[rows.length - 1].more : lead).push(line); continue; }
      rows.push({ word: m[1], file: m[2] || "", said: m[3], more: [] });
    }
    const openNotes = (e) => { e.preventDefault(); const d = detail.querySelector("details.not-proposed"); if (d) { d.open = true; d.scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" }); } };
    return h("div", { class: "summary" },
      lead.map((line) => h("p", { class: "summary-lead", dir: "auto" }, inline(line))),
      rows.length ? h("dl", { class: "summary-rows" }, rows.map((row) => [
        h("dt", { textContent: row.word }),
        h("dd", { dir: "auto" }, inline(row.said), row.more.map((m) => [" ", inline(m)]),
          row.file && current.notes ? [" ", h("a", { href: "#", class: "summary-more", onclick: openNotes, textContent: "Read them ›" })] : null)])) : null);
  };
  const notesBox = (notes) => h("details", { class: "sec not-proposed" }, h("summary", { textContent: "Read and not proposed" }),
    notes.sections.map((sec) => h("section", {}, h("h3", { textContent: sec.name }),
      sec.notes.length ? h("table", { class: "note-counts" }, h("tr", {}, h("th", { textContent: "Note" }), ["facts", "checked", "unchecked", "already in memory", "stale", "rejected"].map((w) => h("th", { textContent: w }))),
        sec.notes.map((n) => h("tr", {}, h("td", {}, h("code", { textContent: n.note.replace(/^[^/]*\//, "") }), n.because ? h("small", { dir: "auto", textContent: n.because }) : null),
          ["facts", "checked", "unchecked", "already in memory", "stale", "rejected"].map((w) => { const c = n.counts.find(([k]) => k === w); const v = c ? c[1] : 0; return h("td", { class: v ? "" : "zero", textContent: String(v) }); })))) : null,
      sec.lines.length ? h("ul", {}, sec.lines.map((line) => h("li", { dir: "auto" }, inline(line)))) : null)),
    h("p", { class: "sec-note" }, h("code", { textContent: notes.file })));
  let openId = 0;
  const open = async (file) => {
    const asked = ++openId;
    const settled = loadingIn(detail, "Reading this dream…", () => asked === openId);
    let answer;
    try { answer = await api(`/api/p/${P(name)}/dream?file=${encodeURIComponent(file)}`); }
    catch { settled(); if (asked === openId) fill(detail, retryLine("That dream didn't load.", () => open(file))); return; }
    settled();
    if (asked !== openId) return;
    current = answer;
    if (current.gone) {  // closed, and its file removed since: there is nothing to read, and saying so is the answer
      fill(detail, h("h2", { class: "gone-title", textContent: current.file.replace("-proposal.md", "") }),
        h("div", { class: "dream-state", textContent: `This proposal was ${current.state} on ${dayOf(current.closed)}, and its file has been removed since, so there is nothing to read.` }));
      drawApply(); drawMeta(); markNav();
      return;
    }
    const nodes = [reviewHead];
    const sections = current.sections;
    const summary = sections.find((s) => s.name === "Summary");
    if (summary) nodes.push(summaryOf(summary.text));
    nodes.push(stats());
    for (const section of sections.filter((s) => s.kind === "needs" && s.needs.length)) {
      // What this dream said needs you. One still open is listed once, at the top of the page, where it is closed.
      const open = new Set(data.needs.open.map((n) => n.text));
      const said = section.needs.filter((n) => n.resolved || !open.has(n.text));
      const still = section.needs.length - said.length;
      nodes.push(h("section", { class: "sec" }, h("h2", { textContent: "Needs you" }),
        h("p", { class: "sec-note", textContent: still ? `${still} ${still === 1 ? "is" : "are"} still open, listed at the top. Not memory: nothing here is ticked or applied.` : "Not memory: nothing here is ticked or applied." }),
        said.map((n) => { const [sentence, evidence] = needParts(n.text); return h("div", { class: `need-row ${n.resolved ? "" : "closed"}` },
          h("p", { dir: "auto" }, n.resolved ? h("b", { textContent: "Put right " }) : null, sentence),
          h("div", { class: "need-sub" }, n.resolved ? null : h("span", { textContent: "Closed since" }), evidence ? h("span", { class: "mono", dir: "auto", textContent: evidence }) : null)); })));
    }
    for (const section of sections) {
      if (!section.items.length && !section.skipped.length) continue;
      // What a dream lists beside the ticks in these two sections, such as notes it didn't carry over, stays in view.
      const beside = SECTION_NOTES[section.kind] ? section.text.split(/^Not memory, but needs you:\s*$/m)[0].trim() : "";
      nodes.push(h("section", { class: "sec" }, h("h2", { textContent: section.name.replace(/ \([^)]*\)$/, "") }),
        SECTION_NOTES[section.kind] ? h("p", { class: "sec-note", textContent: SECTION_NOTES[section.kind === "own-notes" && section.items.some((i) => i.facts.length) ? "carry" : section.kind] }) : null,
        groupsOf(section),
        // Notes a dream read and left behind: the subject and why, never the note itself.
        section.skipped.length ? h("div", { class: "skipped" }, h("h3", { textContent: "Not carried over" }),
          section.skipped.map((s) => h("div", { class: "skip" }, h("span", { class: "t", dir: "auto", textContent: s.subject }), h("span", { class: "why", dir: "auto", textContent: s.reason }), h("code", { textContent: s.file })))) : null,
        beside ? markdown(beside) : null));
    }
    for (const section of sections) {
      const parts = section.text.split(/^Not memory, but needs you:\s*$/m);
      if (parts[1]) nodes.push(h("div", { class: "callout" }, h("h2", { textContent: "Needs you, outside memory" }), markdown(parts[1])));
    }
    for (const section of sections.filter((s) => s.name !== "Summary" && s.kind !== "needs" && !s.items.length && !s.skipped.length && s.text)) {
      const text = section.text.split(/^Not memory, but needs you:\s*$/m)[0].trim();
      if (text && text !== "None waiting.") nodes.push(h("details", { class: "sec" }, h("summary", { textContent: section.name }), markdown(text)));
    }
    if (current.notes) nodes.push(notesBox(current.notes));
    if (current.record_problem) nodes.push(h("div", { class: "callout", role: "alert" }, h("p", { textContent: current.record_problem })));
    if (current.unread.length) nodes.push(h("section", { class: "sec" }, h("h2", { textContent: "Ticked lines the kit couldn't read as items" }),
      current.unread.map((row) => h("div", { class: "change kept" }, h("div", { class: "what" }, h("code", { dir: "auto", textContent: row.text })), fateLine(row)))));
    if (current.yours) nodes.push(yoursBox(current.yours));
    nodes.push(applyBar);
    fill(detail, nodes);
    drawCounts();
    drawApply();
    drawMeta();
    markNav();
  };
  const loadDreams = async () => {
    const asked = openId + 1;  // a file opened since then wins the panel
    const settled = loadingIn(detail, "Reading dreams…", () => asked > openId);
    try { data = await api(`/api/p/${P(name)}/dreams`); }
    catch { settled(); fill(detail, retryLine("Dreams didn't load.", loadDreams)); return; }
    settled();
    // Newest first, in the order the kit's record gives, never by file name: the second proposal of a day is "-2".
    const selected = rest || ((data.dreams.find((d) => d.state === "open") || data.dreams[0] || {}).file);
    fill(list, data.dreams.map((d) => h("a", { class: d.file === selected ? "on" : "", "aria-current": d.file === selected ? "page" : undefined, href: `#/p/${P(name)}/dreams/${d.file}`, title: `${d.file.replace("-proposal.md", "")}, ${d.state}` },
      d.file.replace("-proposal.md", ""), h("small", { textContent: d.state }))),
      // From before the kit kept a record of proposals: the store still holds them, to read.
      data.earlier.length ? h("div", { class: "list-title", textContent: "Earlier" }) : null,
      data.earlier.map((file) => h("a", { class: file === selected ? "on" : "", "aria-current": file === selected ? "page" : undefined, href: `#/p/${P(name)}/dreams/${file}`, textContent: file.replace("-proposal.md", "") })));
    drawMeta();
    syncStrip();
    if (selected) await open(selected);
    else fill(detail, h("div", { class: "empty-line", textContent: "No dreams yet. Dream now reviews recent sessions and proposes memory changes." }));
  };
  loadDreams();
  bind([["j k", "move"], ["x", "tick"], ["a", "apply"], ["r", "dream now"], ["esc", "project"]], {
    x: () => { const row = view.querySelector(".change.sel input"); if (row) row.click(); },
    a: () => askApply(),
    r: () => dreamNow(true),
    Enter: () => { const row = view.querySelector(".change.sel input"); if (row) row.click(); },
  });
  drawMeta();
  page.update = drawMeta;
}

// ── New project ──
function pageNew() {
  setTop([tail("New project")]);
  const root = h("div", { class: "page narrow form" });
  view.append(root);
  const problem = h("p", { id: "name-problem", class: "field-note" });
  const folderNote = h("p", { class: "field-note" });
  const setProblem = (text) => {
    problem.textContent = text;
    if (text) { name.setAttribute("aria-invalid", "true"); name.setAttribute("aria-describedby", "name-problem"); }
    else { name.removeAttribute("aria-invalid"); name.removeAttribute("aria-describedby"); }
  };
  const name = h("input", { type: "text", name: "project-name", spellcheck: false, autocapitalize: "off", placeholder: "my-project", oninput: () => setProblem("") });
  const boxes = h("div");
  const create = h("button", { type: "submit", class: "btn primary", textContent: "Create" });
  // Create waits to know the folders: an empty list that is really a failure would start a new repo by mistake.
  let folders = "loading";
  const markCreate = () => { if (folders === "ready") create.removeAttribute("aria-disabled"); else create.setAttribute("aria-disabled", "true"); };
  const doCreate = once("Creating…", async () => {
    if (!name.value.trim()) { setProblem("Give the project a name."); name.focus(); return; }
    let result;
    try { result = await api("/api/projects", { name: name.value.trim(), folders: [...boxes.querySelectorAll("input:checked")].map((b) => b.value) }); }
    catch (error) { setProblem(error.known ? error.message : NO_ANSWER); name.focus(); return; }
    await tick();
    go(`#/p/${P(result.name)}`);
  }, create);
  const load = async () => {
    folders = "loading";
    markCreate();
    folderNote.textContent = "";
    const settled = loadingIn(boxes, "Loading folders…");
    let list;
    try { list = await api("/api/folders"); }
    catch { settled(); folders = "failed"; markCreate(); fill(boxes, retryLine("Folders didn't load, so Create is off.", load)); return; }
    settled();
    folders = "ready";
    markCreate();
    fill(boxes, list.length ? list.map((f) => h("label", { class: "check folder" }, h("input", { type: "checkbox", value: f }), h("span", { textContent: f }))) : h("div", { class: "empty-line", textContent: "No folders in ~/projects yet." }));
  };
  root.append(h("form", { novalidate: true, onsubmit: (e) => {
    e.preventDefault();
    if (folders !== "ready") { folderNote.textContent = folders === "failed" ? "Load the folders first, so an existing one isn't missed." : "Wait for the folders."; return; }
    doCreate();
  } },
    h("label", { class: "field" }, h("span", { textContent: "Name" }), name), problem,
    h("div", { class: "field", role: "group", "aria-labelledby": "folders-label" }, h("span", { id: "folders-label", textContent: "Folders in your projects folder. Pick none to create a new one." }), boxes, folderNote),
    h("div", { class: "actions" }, h("span"), create)));
  load();
  bind([["↵", "create"], ["esc", "leave the field"]]);
  name.focus();
}

// ── The Dream Catcher: one session over every project's dreams, and what it left for you ──
// It decides; the hub carries out its verdicts (or, with the switch off, only shows them) and lists what waits on you,
// project by project, each with the catcher's one-line reason and the same choices the Dreams page gives.
const CATCH_VERDICT = { approve: "Approve", reject: "Reject", leave: "Leave for you" };
const CATCH_DID = { approve: "Approved", reject: "Rejected" };
const CATCH_KIND = { proposal: "Proposed change", need: "Needs you", inbox: "Inbox proposal" };
function pageCatcher() {
  const root = h("div", { class: "page narrow catcher" });
  view.append(root);
  const head = h("div", { class: "catcher-head" }), body = h("div", { class: "catcher-body" });
  root.append(head, body);
  let data = null, sig = "", loading = false;
  const load = async () => {
    if (loading) return;
    loading = true;
    try { data = await api("/api/catcher"); draw(); }
    catch (error) { if (!data) fill(body, retryLine(error.known ? error.message : NO_ANSWER, load)); }
    finally { loading = false; }
  };
  const start = once("Starting…", async () => {
    const result = await api("/api/catcher/run", {});
    await tick();
    await load();
    say(result.ids.length ? "The Dream Catcher is running" : "Nothing waited, so no session was started");
  });
  const setAuto = guard(async (on) => {
    if (on && !(await confirmStep({ title: "Let the Dream Catcher act for you?", body: "Its approvals and rejections are carried out as soon as a run ends: it ticks proposal items, approves fixes and rejects needs in your name, and applies a proposal once nothing in it waits on you. Everything it does is logged as the Dream Catcher's. What it isn't sure of, and what is always yours, waits here.", yes: "Let it act", no: "Only recommend" }))) return;
    await api("/api/catcher/auto", { auto: on });
    await tick();
    await load();
  });
  const decide = (item, verdict) => once("One moment…", async () => {
    const result = await api("/api/catcher/decide", { run: data.run.id, key: item.key, verdict });
    toast(result.said || "Done");
    await tick();
    await load();
  });
  const acceptAll = once("Carrying them out…", async () => {
    const result = await api("/api/catcher/accept", { run: data.run.id });
    say(result.said);
    toast(result.said);
    await tick();
    await load();
  });
  const projectName = (store) => (project(store) || {}).display || store;
  const sentence = (item) => {
    if (item.kind === "need") return needParts(item.text)[0];
    if (item.kind === "inbox") return oneLine(item.text.split("\n").find((l) => l.trim()) || item.file);
    return (item.quote || item.text).replace(/^- /, "");
  };
  const facts = (item) => [
    item.kind === "proposal" ? `${item.n ? `Item ${item.n} · ` : ""}${item.file}${item.action ? ` · ${item.action}` : ""}` : item.kind === "need" ? (item.who === "you" ? "Only you can put it right" : item.who === "agent" ? `An agent can fix it in ${item.repo}` : "Not sorted") : item.file,
    item.held && !(item.kind === "need" && item.who === "you") ? `Yours: ${item.held}` : null,
  ].filter(Boolean);
  const actions = (item, i) => {
    if (!item.open || !item.waits || data.run.phase !== "settled") return null;
    const btn = (verdict, word) => h("button", { class: "retry", type: "button", "data-key": `${verdict}:${i}`, textContent: word, onclick: decide(item, verdict) });
    if (item.kind === "inbox") return h("div", { class: "need-acts" }, h("a", { class: "retry", href: `#/p/${P(item.store)}/memory/${item.file}`, textContent: "Read it" }), btn("approve", "Leave it to the next dream"));
    const acts = item.kind === "need" && item.who === "you" ? [btn("done", "Done"), btn("reject", "Reject")]
      : [btn("approve", item.kind === "need" ? "Approve fix" : "Approve"), btn("reject", "Reject")];
    if (item.result === "recommended" && item.verdict === "reject") acts.reverse();
    return h("div", { class: "need-acts" }, acts);
  };
  const row = (item, i) => h("div", { class: `need-row catch-row ${item.waits && item.open ? "" : "closed"}`, "data-nav": `catch:${i}` },
    h("p", { dir: "auto" }, h("span", { class: "catch-kind", textContent: CATCH_KIND[item.kind] }), " ", h("span", { textContent: sentence(item) })),
    h("div", { class: "need-sub" }, facts(item).map((f) => h("span", { dir: "auto", textContent: f }))),
    item.reason ? h("p", { class: `catch-why ${item.verdict || ""}`, dir: "auto" },
      h("b", { textContent: item.result === "recommended" ? `Recommends: ${CATCH_VERDICT[item.verdict].toLowerCase()}. ` : CATCH_DID[item.verdict] && item.by === "dream-catcher" ? `${CATCH_DID[item.verdict]}. ` : "" }),
      h("span", { textContent: item.reason }), item.evidence ? h("small", { textContent: ` Checked: ${item.evidence}` }) : null) : null,
    (item.result === "failed" || item.result === "skipped") ? h("p", { class: "need-state", role: "status", textContent: item.said }) : null,
    !item.waits && item.said ? h("p", { class: "need-state fixed", role: "status", textContent: `${item.by ? "" : "You: "}${item.said}` }) : null,
    item.waits && !item.open ? h("p", { class: "need-state", textContent: "Decided elsewhere since." }) : null,
    actions(item, i));
  const byProject = (items) => {
    const order = [...new Set(items.map((i) => i.store))];
    return order.map((store) => h("section", { class: "catch-project", "aria-label": projectName(store) },
      h("header", { class: "catch-project-head" }, project(store) ? mark(project(store), 15) : null, h("h3", { dir: "auto", textContent: projectName(store) }),
        project(store) ? h("a", { class: "retry", href: `#/p/${P(store)}/dreams`, textContent: "Open Dreams" }) : null),
      items.filter((i) => i.store === store).map((item) => row(item, data.run.items.indexOf(item)))));
  };
  const status = () => {
    const run = data && data.run;
    if (!run) return "It hasn't run yet.";
    const when = agoWords(run.settled || run.started);
    if (run.phase === "running") return `Catching dreams, started ${agoWords(run.started)}.`;
    if (run.phase === "finished") return "Carrying out its verdicts…";
    if (run.phase === "stopped") return `The last run, ${when}, stopped before it finished, so nothing was done. Run it again.`;
    const n = (v) => run.items.filter((i) => i.verdict === v && i.result !== "left").length;
    const waiting = run.items.filter((i) => i.waits && i.open).length;
    if (!run.items.length) return `Last run ${when}: nothing waited on you.`;
    return `Last run ${when}: ${n("approve")} approved, ${n("reject")} rejected, ${waiting} ${waiting === 1 ? "waits" : "wait"} on you${run.acted ? "" : ". It only recommended"}.`;
  };
  const draw = () => {
    const c = S.catcher || {}, run = data.run;
    const running = c.phase === "running" || (run && run.phase === "running");
    setTop([tail("Dream Catcher")], [running ? null : h("button", { class: "btn primary", type: "button", "data-key": "catch-now", textContent: "Catch dreams now", onclick: start })].filter(Boolean));
    if (differs(head, data.auto, data.own, data.scope, running, status(), run && run.sid)) fill(head,
      h("p", { class: "catcher-lead", textContent: "Goes through every project's open dream proposals, what dreams said needs you, and inbox proposals. It checks each against the project's memory and code, decides what it can, and leaves you the rest with a reason." }),
      h("div", { class: "dream-meta" },
        h("button", { class: `switch ${data.auto ? "on" : ""}`, type: "button", role: "switch", "aria-checked": data.auto ? "true" : "false", "aria-label": "Act on its verdicts", onclick: () => setAuto(!data.auto) }),
        h("span", { textContent: data.auto ? "Acts on its verdicts" : "Only recommends" }),
        h("span", { class: "faint", textContent: `${data.scope.length} ${data.scope.length === 1 ? "project" : "projects"}` })),
      h("p", { class: "dream-note said", role: "status" }, h("span", { textContent: status() }), " ", running && run && run.sid ? h("a", { class: "retry", href: `#/s/${run.sid}`, textContent: "Watch it" }) : null),
      data.own.ready ? null : h("p", { class: "dream-note" }, "It has no memory of its own yet, so it doesn't learn across runs. To give it one, run ", h("code", { textContent: data.own.install }), " in a terminal. ", copyButton(data.own.install)));
    if (!run) { fill(body); return; }
    if (!differs(body, run)) return;
    const waiting = run.items.filter((i) => i.waits && i.open), handled = run.items.filter((i) => !(i.waits && i.open));
    const recommended = waiting.filter((i) => i.result === "recommended").length;
    fill(body,
      run.problems && run.problems.length ? h("div", { class: "callout", role: "alert" }, h("p", { textContent: `Its verdicts couldn't be read, so everything is left for you: ${run.problems.join("; ")}` })) : null,
      run.skipped.length ? h("p", { class: "dream-note", textContent: `Left alone this time: ${run.skipped.map((s) => `${projectName(s.store)} (${s.why})`).join(", ")}` }) : null,
      run.applying.length ? run.applying.map((a) => h("p", { class: "dream-note said" }, h("span", { textContent: `${projectName(a.store)}: ${a.said}` }), " ", a.sid ? h("a", { class: "retry", href: `#/s/${a.sid}`, textContent: "Open it" }) : null)) : null,
      run.phase === "settled" ? h("section", { class: "callout needs catch-wait", "aria-labelledby": "catch-wait-title" },
        h("header", { class: "needs-head" }, h("h2", { id: "catch-wait-title", textContent: waiting.length ? `${waiting.length} ${waiting.length === 1 ? "thing waits" : "things wait"} on you` : "Nothing waits on you" }),
          recommended ? h("button", { class: "btn primary need-run", type: "button", "data-key": "accept-all", textContent: `Accept all recommended (${recommended})`, onclick: acceptAll }) : null),
        waiting.length ? byProject(waiting) : h("p", { class: "sec-note", textContent: "It decided everything in its last run." })) : null,
      run.report ? h("details", { class: "sec catch-report", open: run.phase !== "settled" || !waiting.length }, h("summary", { textContent: "Its report" }), h("div", { class: "catch-report-text", dir: "auto", textContent: run.report })) : null,
      handled.length ? h("details", { class: "sec carried" }, h("summary", { textContent: `${handled.length} decided` }), byProject(handled)) : null);
  };
  page.update = () => { const c = S.catcher || {}; const now = JSON.stringify([c.run, c.phase, c.waiting, c.settled, c.auto]); if (now !== sig) { sig = now; load(); } };
  sig = JSON.stringify([(S.catcher || {}).run, (S.catcher || {}).phase, (S.catcher || {}).waiting, (S.catcher || {}).settled, (S.catcher || {}).auto]);
  setTop([tail("Dream Catcher")]);
  const settled = loadingIn(body, "Loading…");
  load().finally(settled);
}

// ── Jump anywhere, and act on the session you're on ──
// The session in hand: a sidebar row that holds focus, a selected row in a page's list, or the pane you're in.
const selectedSid = () => {
  const row = document.activeElement && document.activeElement.closest && document.activeElement.closest("#side [data-sid]");
  if (row && session(row.dataset.sid)) return row.dataset.sid;
  if (navKey && session(navKey) && view.querySelector(`[data-nav="${CSS.escape(navKey)}"].sel`)) return navKey;
  return page.selected ? page.selected() : null;
};
// ── Dragging a session into a split, from the sidebar, Home, a project's page or a pane's header, with a mouse or a
// trackpad. Pointer events rather than the browser's drag and drop: the zones follow the pointer exactly, a terminal
// under it never takes the drag, and a touch never starts one (a phone has no splits). Esc cancels. ──
(() => {
  let d = null;
  const ghost = h("div", { class: "drag-ghost", "aria-hidden": "true" });
  const frame = h("div", { class: "drop-frame", "aria-hidden": "true" });
  const preview = h("div", { class: "drop-preview", "aria-hidden": "true" }, h("span"));
  const place = (el, r) => { el.style.transform = `translate(${Math.round(r.left)}px, ${Math.round(r.top)}px)`; el.style.width = `${Math.round(r.width)}px`; el.style.height = `${Math.round(r.height)}px`; };
  const targetAt = (x, y) => {
    if (page.dropAt) return page.dropAt(x, y, d.sid, d.fromPane);
    if (d.fromPane) return null;
    // On a page without panes, a session dropped on the page opens there.
    const box = view.getBoundingClientRect();
    if (x < box.left || x > box.right || y < box.top || y > box.bottom) return null;
    const sid = d.sid;
    return { frame: box, rect: box, label: "Open here", drop: () => go(`#/s/${sid}`) };
  };
  const end = () => {
    if (!d) return;
    try { if (d.active && document.documentElement.hasPointerCapture(d.pointer)) document.documentElement.releasePointerCapture(d.pointer); } catch { /* already released */ }
    if (d.lifted) d.lifted.classList.remove("lifted");
    ghost.remove(); frame.remove(); preview.remove();
    document.body.classList.remove("session-dragging");
    d = null;
  };
  const begin = () => {
    d.active = true;
    const s = session(d.sid);
    fill(ghost, dot(s ? shownState(s) : "ended"), h("span", { class: "drag-text" }, h("b", { dir: "auto", textContent: s ? s.title : "Session" }), h("small")));
    frame.hidden = preview.hidden = true;
    document.body.append(frame, preview, ghost);
    document.body.classList.add("session-dragging");
    try { document.documentElement.setPointerCapture(d.pointer); } catch { /* the pointer is gone */ }
    const selection = window.getSelection();
    if (selection) selection.removeAllRanges();
    if (d.fromPane) { d.lifted = d.source.closest(".pane"); if (d.lifted) d.lifted.classList.add("lifted"); }
  };
  const move = (e) => {
    if (!d || e.pointerId !== d.pointer) return;
    if (!d.active) { if (Math.hypot(e.clientX - d.x, e.clientY - d.y) < 6) return; begin(); }
    e.preventDefault();
    ghost.style.transform = `translate(${e.clientX + 14}px, ${e.clientY + 16}px)`;
    const t = d.target = targetAt(e.clientX, e.clientY);
    const hint = ghost.querySelector("small");
    const landing = t && t.rect && !t.full;
    hint.textContent = !t ? (page.dropAt ? "Drop on a pane" : "") : t.rect ? "" : t.label;
    ghost.classList.toggle("over", !!landing);
    frame.hidden = !t || !t.rect;
    if (t && t.rect) place(frame, t.frame);
    if (!t || !t.rect) { preview.hidden = true; return; }
    const appearing = preview.hidden;
    preview.classList.toggle("fresh", appearing);
    preview.classList.toggle("refused", !!t.full);
    preview.classList.toggle("swap", !!t.center);
    preview.firstChild.textContent = t.label;
    place(preview, { left: t.rect.left + 2, top: t.rect.top + 2, width: Math.max(0, t.rect.width - 4), height: Math.max(0, t.rect.height - 4) });
    preview.hidden = false;
    if (appearing) { void preview.offsetWidth; preview.classList.remove("fresh"); }
  };
  const up = (e) => {
    if (!d || e.pointerId !== d.pointer) return;
    if (!d.active) { end(); return; }
    e.preventDefault();
    // The click that ends a drag isn't a click on what is under the pointer.
    const swallow = (c) => { c.preventDefault(); c.stopPropagation(); };
    window.addEventListener("click", swallow, { capture: true, once: true });
    setTimeout(() => window.removeEventListener("click", swallow, true), 0);
    const t = targetAt(e.clientX, e.clientY);
    end();
    if (t && t.rect) t.drop();
  };
  window.addEventListener("pointerdown", (e) => {
    if (d) end();
    if (e.button !== 0 || e.pointerType === "touch" || phone.matches || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const source = e.target.closest && e.target.closest("[data-drag-sid]");
    if (!source || !session(source.dataset.dragSid)) return;
    // Controls inside the row keep their own clicks; a link to the same session and a pane's title are part of the handle.
    const control = e.target.closest("button, a, input, textarea, select, [role=separator], .xterm, .popup");
    const handle = !control || control === source || (control.matches("a") && (control.getAttribute("href") || "") === `#/s/${source.dataset.dragSid}`) || control.matches(".pane-top .name");
    if (!handle) return;
    d = { sid: source.dataset.dragSid, source, fromPane: source.hasAttribute("data-drag-pane"), x: e.clientX, y: e.clientY, pointer: e.pointerId, active: false };
  }, true);
  window.addEventListener("pointermove", move, true);
  window.addEventListener("pointerup", up, true);
  window.addEventListener("pointercancel", end, true);
  window.addEventListener("blur", end);
  window.addEventListener("keydown", (e) => { if (d && d.active && e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); end(); say("Drag cancelled"); } }, true);
  // A link's own drag would take the pointer away: the hub's drag replaces it.
  window.addEventListener("dragstart", (e) => { if (e.target.closest && e.target.closest("[data-drag-sid]")) e.preventDefault(); }, true);
})();

// Peek is workstream C's popover beside the row. Until it's there, the row's state and line say the same in a toast.
const peekSession = (id) => {
  if (window.hubPeek) return window.hubPeek(id);
  const s = session(id);
  if (s) toast(`${s.title}: ${statusLine(s)}`);
};
// Rename happens in the row itself, so the sidebar has to be open, and in full, to hold it.
const editInSide = (s, kind) => { if (phone.matches) setSide(true); else setRail(false); startEdit(s, kind); };
const sessionActions = (s) => {
  const r = route(), shown = r.name === "session" && r.ids.includes(s.id);
  return [
    shown ? null : { text: "Open", keys: "↵", run: () => go(`#/s/${s.id}`) },
    r.name === "session" && !shown && s.alive && r.ids.length < MAX_PANES ? { text: "Open beside", keys: "⌘ click", run: () => goLayout(layoutAdd(r.layout, s.id)) } : null,
    { text: "Peek", keys: "space", run: () => peekSession(s.id) },
    { text: "Rename", run: () => editInSide(s, "rename") },
    s.phone && s.alive ? { text: "Copy the phone link", run: guard(async () => { await navigator.clipboard.writeText(s.phone); toast("Copied"); }) } : null,
    canClose(s) && s.alive ? { text: "Close session", run: () => closeSession(s) } : null,
    canResume(s) ? { text: "Resume", run: guard(() => resumeSession(s)) } : null,
    { text: "Delete…", run: () => deleteSession(s) },
  ].filter(Boolean).map((o) => ({ ...o, of: s }));
};
function openPalette() {
  if (document.querySelector("dialog.palette")) return;
  const sid = selectedSid(), held = sid && session(sid);
  const where = (s) => (project(s.project) || {}).display;
  const options = [
    ...(held ? sessionActions(held) : []),
    ...S.sessions.filter((s) => s.alive).map((s) => ({ text: s.title, where: where(s), orb: s, run: () => go(`#/s/${s.id}`) })),
    ...S.projects.flatMap((p) => [
      { text: p.display, mark: p, run: () => go(`#/p/${P(p.name)}`) },
      { text: "New session", where: p.display, mark: p, run: () => newSession(p.name) },
    ]),
    { text: "Home", keys: "g h", run: () => go("#/") },
    { text: "New project", run: () => go("#/new") },
    { text: "Keyboard shortcuts", keys: "?", run: openKeys },
  ];
  const label = held ? `Act on ${held.title}, or jump anywhere` : "Jump to a project or session";
  const dialog = h("dialog", { class: "palette", "aria-label": label });
  const input = h("input", { placeholder: held ? "Act on this session or jump anywhere" : "Jump to a project or session", "aria-label": label, spellcheck: false, role: "combobox", "aria-expanded": "true", "aria-autocomplete": "list", "aria-controls": "palette-results" });
  const results = h("div", { class: "results", id: "palette-results", role: "listbox", "aria-label": "Matches" });
  const foot = h("div", { class: "palette-foot", "aria-hidden": "true" });
  let chosen = 0, matches = options;
  const option = (o, i) => h("div", { class: `opt ${i === chosen ? "on" : ""}`, id: `palette-${i}`, role: "option", "aria-selected": i === chosen ? "true" : "false", onclick: () => pick(o), onmousemove: () => { if (chosen !== i) { chosen = i; paint(); } } },
    h("span", { class: "slot" }, o.mark ? mark(o.mark, 15) : o.orb ? orbOf(`pal:${o.orb.id}`, orbState(o.orb)) : null),
    h("span", { class: "t", dir: "auto" }, o.text, o.where ? h("span", { class: "where", textContent: ` — ${o.where}` }) : null),
    o.keys ? h("kbd", { textContent: o.keys }) : null);
  const paint = () => {
    const q = input.value.toLowerCase().trim();
    matches = options.filter((o) => `${o.text} ${o.where || ""}`.toLowerCase().includes(q)).slice(0, 40);
    chosen = Math.min(chosen, Math.max(matches.length - 1, 0));
    const acts = matches.filter((o) => o.of).length;
    // The held session's actions come first, under its own name; the rest of the list follows a hairline.
    fill(results, matches.length ? [
      acts ? h("div", { class: "pal-group", role: "presentation", dir: "auto", textContent: held.title }) : null,
      matches.map((o, i) => [i === acts && acts ? h("div", { class: "pal-rule", role: "presentation" }) : null, option(o, i)]),
    ] : h("div", { class: "empty-line", textContent: "No matches" }));
    fill(foot, h("span", {}, h("kbd", { textContent: "↑↓" }), h("kbd", { textContent: "↵" }), h("kbd", { textContent: "esc" })), h("span", { textContent: `${matches.length} ${matches.length === 1 ? "result" : "results"}` }));
    const on = results.querySelector(".opt.on");
    if (on) { input.setAttribute("aria-activedescendant", on.id); on.scrollIntoView({ block: "nearest" }); } else input.removeAttribute("aria-activedescendant");
  };
  const pick = (o) => { dialog.close(); o.run(); };
  input.addEventListener("input", () => { chosen = 0; paint(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); chosen = Math.min(chosen + 1, matches.length - 1); paint(); }
    if (e.key === "ArrowUp") { e.preventDefault(); chosen = Math.max(chosen - 1, 0); paint(); }
    if (e.key === "Enter" && matches[chosen]) pick(matches[chosen]);
  });
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  fill(dialog, input, results, foot);
  paint();
  sheet(dialog);
  input.focus();
}

// ── Every key, in one sheet docked at the left: the app stays usable beside it ──
const KEYS = [
  ["Anywhere", [["⌘K", "Actions for a session, or jump"], ["/", "Find a project or session"], ["?", "Show or hide this sheet"], ["⌘B", "Fold or unfold the sidebar"], ["g h", "Home"], ["g d", "Dreams of this project"], ["g m", "Memory of this project"], ["g n", "New session"], ["g s", "Go to the sidebar"], ["esc", "Leave a field, then go up a level"]]],
  ["Lists and the sidebar", [["j k", "Move down and up"], ["↵", "Open"], ["space", "Peek at a session"], ["⌘ click", "Open a session beside this one"]]],
  ["Session", [["↵", "Back to the terminal"], ["⌃`", "Leave or return to the terminal"], ["1–4", "Choose a pane"], ["⌥1–4", "Choose a pane while typing"], ["p", "Show or hide the panel"], ["s", "Split"]]],
  ["Project", [["i", "Go to the prompt"], ["n", "New session"], ["N", "New project, from Home"], ["m d", "Memory, Dreams"], [",", "Settings"], ["⌘↩", "Start a session"]]],
  ["Memory and Dreams", [["e", "Edit a memory file"], ["x a r", "Tick, apply, dream now"]]],
];
// A chord is written the way it's typed: "g then d".
const keyCaps = (keys) => {
  const chord = keys.match(/^(\S) (\S)$/);
  if (chord && keys[0] === "g") return h("span", { class: "caps" }, h("kbd", { textContent: chord[1] }), h("span", { class: "then", textContent: "then" }), h("kbd", { textContent: chord[2] }));
  return h("span", { class: "caps" }, keys.split(" ").map((k) => h("kbd", { textContent: k })));
};
function openKeys() {
  const open = document.querySelector("dialog.keys-help");
  if (open) { open.close(); return; }
  const back = document.activeElement;
  const dialog = h("dialog", { class: "keys-help", "aria-label": "Keyboard shortcuts" });
  const search = h("input", { type: "search", placeholder: "Find a key", "aria-label": "Find a key", spellcheck: false });
  const list = h("div", { class: "keys-list" });
  const paint = () => {
    const q = search.value.toLowerCase().trim();
    const groups = KEYS.map(([name, rows]) => [name, rows.filter(([keys, what]) => !q || what.toLowerCase().includes(q) || keys.toLowerCase().includes(q) || name.toLowerCase().includes(q))]).filter(([, rows]) => rows.length);
    fill(list, groups.length ? groups.map(([name, rows]) => h("section", {}, h("h2", { textContent: name }), h("div", { class: "keysheet" }, rows.flatMap(([keys, what]) => [keyCaps(keys), h("span", { textContent: what })]))))
      : h("div", { class: "empty-line", textContent: "No key does that" }));
  };
  search.addEventListener("input", paint);
  dialog.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); dialog.close(); } });
  dialog.addEventListener("close", () => { dialog.remove(); if (back && back.isConnected && back !== document.body) back.focus({ preventScroll: true }); });
  const checkButton = h("button", { type: "button", class: "linkish", textContent: "Check for updates" });
  checkButton.onclick = () => checkUpdates(checkButton);
  const credit = h("p", { class: "keys-credit" }, `Dream Hub${hubVersion ? ` ${hubVersion.commit} of ${hubVersion.date}` : ""} · `, checkButton, " · By ", h("a", { href: "https://github.com/ChristianAlmurr", target: "_blank", rel: "noopener noreferrer", textContent: "Christian Almurr" }));
  fill(dialog, h("div", { class: "keys-top" }, h("h1", { textContent: "Keyboard" }), h("button", { class: "icon", type: "button", title: "Close", onclick: () => dialog.close() }, uiIcon("close"))), search, list, credit);
  paint();
  document.body.append(dialog);
  dialog.show();
  search.focus();
}

// ── The sidebar as a list: j and k walk its rows by focus, so ↵ opens, space peeks and ⌘K acts on the one you're on ──
const sideItems = () => [...sideList.querySelectorAll("a.nav, button.side-fold")].filter((el) => el.offsetParent);
const moveSide = (step) => {
  if (phone.matches && !sideOpen()) setSide(true);
  const items = sideItems();
  if (!items.length) return;
  let at = items.indexOf(document.activeElement);
  // The first step lands on the row you're already on, so the walk starts where you are.
  if (at < 0) { const here = items.findIndex((el) => el.closest(".side-row.on") || el.classList.contains("on")); if (here >= 0) { items[here].focus(); return; } at = step > 0 ? -1 : items.length; }
  const next = items[Math.max(0, Math.min(items.length - 1, at + step))];
  next.focus();
  next.scrollIntoView({ block: "nearest" });
};
// The project you're in: the page's, the session's, or the sidebar row's under focus.
const projectHere = () => {
  const r = route();
  if (r.name === "project") return r.project;
  const s = session(selectedSid() || "");
  if (s) return s.project;
  const key = document.activeElement && document.activeElement.dataset && document.activeElement.dataset.key;
  return key && key.startsWith("p:") ? key.slice(2) : null;
};
const inProject = (tab) => () => { const name = projectHere(); if (name) go(`#/p/${P(name)}/${tab}`); else toast(`Choose a project first, then g ${tab[0]}`); };
const CHORDS = { h: () => go("#/"), d: inProject("dreams"), m: inProject("memory"), n: () => newSession(projectHere() || undefined), s: () => { side.contains(document.activeElement) || moveSide(0); } };
let chordTimer = null;
const chording = () => chordTimer !== null;
const endChord = () => { clearTimeout(chordTimer); chordTimer = null; drawStatus(); };
const startChord = () => { clearTimeout(chordTimer); chordTimer = setTimeout(endChord, 1500); drawStatus(); };

const isTyping = (target) => target && target.closest && target.closest('input:not([type=checkbox], [type=radio], [type=button], [type=submit], [type=file], [type=range], [type=color]), textarea, select, [contenteditable]:not([contenteditable="false"]), .xterm');
let enterAt = 0, enterHeld = false;
window.addEventListener("keyup", (e) => { if (e.key === "Enter") enterHeld = false; }, true);
window.addEventListener("keydown", (e) => {
  const key = e.key;
  if (key === "Enter" && (enterHeld || Date.now() - enterAt < 300) && inTerminal()) { e.preventDefault(); e.stopPropagation(); return; }  // the Enter that moved you here isn't meant for Claude
  if ((e.metaKey || e.ctrlKey) && key.toLowerCase() === "k") { e.preventDefault(); openPalette(); return; }
  if ((e.metaKey || e.ctrlKey) && key.toLowerCase() === "b") { e.preventDefault(); if (phone.matches) setSide(!sideOpen()); else setRail(!railed()); return; }
  if (e.ctrlKey && key === "`") {
    e.preventDefault();
    if (isTyping(document.activeElement)) document.activeElement.blur();
    else if (pageKeys.Enter && route().name === "session") pageKeys.Enter();
    return;
  }
  // This listener runs first (capture). Esc inside something that closes itself on Esc is that thing's, not "go up a page".
  if (key === "Escape" && e.target.closest && e.target.closest(".review, .peek-pop, .line-note-edit")) return;
  if (key === "Escape" && document.querySelector("dialog.keys-help") && !(e.target.closest && e.target.closest(".xterm"))) { e.preventDefault(); document.querySelector("dialog.keys-help").close(); return; }
  if (key === "Escape" && toastEl.classList.contains("sticky") && !(e.target.closest && e.target.closest(".xterm"))) { e.preventDefault(); hideToast(); return; }
  if (document.querySelector("dialog[open]:not(.keys-help), .popup")) return;
  if (key === "Escape" && sideEdit.id) { e.preventDefault(); closeEdit(); return; }
  if (key === "Escape" && sideOpen()) { e.preventDefault(); closeSide(); return; }
  if (paneJump(e) && pageKeys.jump) { e.preventDefault(); pageKeys.jump(Number(e.code.slice(5)) - 1); return; }
  if (isTyping(e.target)) {
    if (key === "Escape" && !e.target.closest(".xterm")) e.target.blur();
    return;
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (chording()) { const run = CHORDS[key]; endChord(); if (run) { e.preventDefault(); run(); } return; }
  const inSide = !!(e.target.closest && e.target.closest("#side"));
  // In the sidebar the arrows walk the rows too, and space peeks at the session on the row.
  if (inSide && (key === "ArrowDown" || key === "ArrowUp")) { e.preventDefault(); moveSide(key === "ArrowDown" ? 1 : -1); return; }
  if (key === " " && inSide && e.target.closest("[data-sid]") && e.target.matches("a.nav")) { e.preventDefault(); peekSession(e.target.closest("[data-sid]").dataset.sid); return; }
  // Letters work wherever the keyboard isn't typing. On a control, Enter, Space and arrows stay that control's own.
  const control = e.target.closest && e.target.closest("a[href], button, summary, label, input, [role=button], [role=radio], [role=menuitem], [role=separator]");
  if (control && (key === "Enter" || key === " " || key.startsWith("Arrow"))) return;
  if (key === "g" && !pageKeys.g) { e.preventDefault(); startChord(); return; }
  if ((key === "j" || key === "k") && (inSide || !navItems().length)) { e.preventDefault(); moveSide(key === "j" ? 1 : -1); return; }
  if (key === " " && navKey && session(navKey) && view.querySelector(`[data-nav="${CSS.escape(navKey)}"].sel`)) { e.preventDefault(); peekSession(navKey); return; }
  if (pageKeys[key]) { e.preventDefault(); if (key === "Enter" && route().name === "session") { enterAt = Date.now(); enterHeld = true; } pageKeys[key](); return; }
  if (key === "/") { e.preventDefault(); openPalette(); }
  else if (key === "?") { e.preventDefault(); openKeys(); }
  else if (key === "j" || key === "ArrowDown") { e.preventDefault(); moveNav(1); }
  else if (key === "k" || key === "ArrowUp") { e.preventDefault(); moveNav(-1); }
  else if (key === "Enter") { const selected = navItems().find((el) => el.classList.contains("sel")); if (selected) { e.preventDefault(); selected.click(); } }
  else if (key === "Escape") goUp();
}, true);

// Keys typed in a terminal go to Claude, so the status line changes with focus.
let hintsInTerminal = false;
const syncHints = () => { if (inTerminal() !== hintsInTerminal) { hintsInTerminal = !hintsInTerminal; drawStatus(); } };
window.addEventListener("focusin", syncHints);
window.addEventListener("focusout", () => setTimeout(syncHints));
// A file dropped beside a pane must not navigate away from the app.
for (const type of ["dragover", "drop"]) window.addEventListener(type, (e) => { if (e.dataTransfer && [...e.dataTransfer.types].includes("Files")) e.preventDefault(); });

window.addEventListener("hub-orbs-ready", () => { sideKey = ""; alerts.key = ""; render(); });
setTop([]);
fill(view, h("div", { class: "empty-line hold", textContent: "Connecting to the hub…" }));
drawSide();
drawStatus();
syncSide();
placeAlerts();
tick();
// A worker keeps time in a background tab, where the browser slows page timers to about once a minute.
const startClock = () => setInterval(tick, 3000);
try {
  const clock = new Worker("/ui/clock.js");
  clock.onmessage = () => tick();
  clock.onerror = () => { clock.terminate(); startClock(); };
} catch { startClock(); }
