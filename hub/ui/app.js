"use strict";
// Context Hub. Everything from the server is placed with textContent: memory and chat hold text from transcripts and the web.

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
  gear: '<path d="M6.9 1.8h2.2l.3 1.7 1.2.5 1.4-1 1.6 1.6-1 1.4.5 1.2 1.7.3v2.2l-1.7.3-.5 1.2 1 1.4-1.6 1.6-1.4-1-1.2.5-.3 1.7H6.9l-.3-1.7-1.2-.5-1.4 1-1.6-1.6 1-1.4-.5-1.2-1.7-.3V6.9l1.7-.3.5-1.2-1-1.4 1.6-1.6 1.4 1 1.2-.5Z"/><circle cx="8" cy="8" r="2"/>',
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
  if (!sticky) toast.timer = setTimeout(hideToast, noticeLeft("toast", 5000));
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
  dreaming: "Dreaming", reasoning: "Thinking", searching: "Searching", using: "Using a tool", compacting: "Compacting", retrying: "Retrying", background: "Working in the background", waiting: "Waiting", idle: "Idle", asks: "Done, asks you" };
// The terminal is still open but Claude has left it: that isn't Ended.
const shownState = (s) => s.state === "ended" && s.alive ? "no-claude" : s.state;
// A name stays on one line when it fits, so "web-shop" doesn't break at its hyphen.
const nb = (text) => h("span", { class: "nb", dir: "auto", textContent: text });
const dot = (state, title) => state ? h("span", { class: `dot ${state}`, role: "img", "aria-label": DOT_WORDS[state] || state, title }) : h("span", { class: "dot", "aria-hidden": "true" });
// Motion as the person chose it (theme.js resolves "system" from the media query), else as the system asks.
const reduced = () => { const set = document.documentElement.dataset.motionSet; return set === "on" ? true : set === "off" ? false : matchMedia("(prefers-reduced-motion: reduce)").matches; };
const P = (name) => encodeURIComponent(name);
const ago = (seconds) => {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 90) return "now";
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return dayOf(seconds);  // one date format (feat/polish-pages): relative under a day, then "21 Nov"
};
const agoWords = (seconds) => ago(seconds) === "now" ? "just now" : Date.now() / 1000 - seconds < 86400 ? `${ago(seconds)} ago` : `on ${dayOf(seconds)}`;
// ── Dream timing: the kit's scheduler checks every hour and dreams when one is due and the project is idle; an older daily job checks at its hour ──
const WEEKDAYS = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"];
const clockHour = (hour) => `${String(hour).padStart(2, "0")}:00`;
// A job made before the daily check runs on one weekday, and reads that way until the project is switched off and on again.
const weekly = (schedule) => !!schedule && schedule.weekday !== null && schedule.weekday !== undefined;
const dreamTiming = (schedule, lead = "") => !schedule ? "Automatic dreams"
  : schedule.hourly ? "Automatic dreams · checked hourly, dreams when idle"
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
// Every date the hub writes: "21 Nov", with the year only when it isn't this one. ISO dates stay in tooltips.
const dayOf = (at) => { const d = new Date(at * 1000); return d.toLocaleDateString("en-GB", d.getFullYear() === new Date().getFullYear() ? { day: "numeric", month: "short" } : { day: "numeric", month: "short", year: "numeric" }); };
// A dream's file stem, "2026-11-21-2", as that date: "21 Nov, 2nd" for the second dream of a day.
const stemDay = (stem) => { const m = /^(\d{4}-\d{2}-\d{2})(?:-(\d+))?/.exec(stem || ""); const n = m && Number(m[2]), th = n % 100 > 10 && n % 100 < 14 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th"; return m ? `${dayOf(Date.parse(`${m[1]}T12:00:00`) / 1000)}${m[2] ? `, ${n}${th}` : ""}` : stem; };
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
  const tile = h("span", { class: "mark", style: `width:${edge}px;height:${edge}px;--c:${projectColour(p.name) || IDENTITY[nameHash(p.name) % IDENTITY.length]}` });
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
// A feature switch from Settings › Features. Off, the hub works as it did before that feature: its code must check this.
const feature = (name) => pref(`feature_${name}`, true) !== false;
// Panels a session can show beside it (Settings › Features › Session side panel). A feature adds one with addPanel():
// { id, title, icon, feature, order, available(s) → bool, render(s, box) → node, leave?() }. The side panel lists those
// whose feature is on and that are available for the session, in `order`; Overview is 0.
const PANELS = [];
const addPanel = (panel) => { const at = PANELS.findIndex((p) => p.id === panel.id); if (at >= 0) PANELS[at] = panel; else PANELS.push(panel); PANELS.sort((a, b) => (a.order ?? 50) - (b.order ?? 50)); };
const panelsFor = (s) => PANELS.filter((p) => (!p.feature || feature(p.feature)) && (!p.available || p.available(s)));
const view = document.getElementById("view");
const top_ = document.getElementById("top");
const side = document.getElementById("side");
let page = { key: "", update: null, leave: null };
const hub = { ready: false, down: false };
const banner = h("div", { class: "banner", hidden: true }, h("span", { textContent: "Context Hub isn't answering. Retrying every 3 seconds." }), h("button", { class: "retry", textContent: "Retry now", onclick: once("Retrying…", () => tick()) }));
top_.after(banner);
const staleBanner = h("div", { class: "banner stale", hidden: true }, h("span", { textContent: "Context Hub was updated. This page is from the version before: reload to use the new one." }), h("button", { class: "retry", textContent: "Reload", onclick: () => location.reload() }));
banner.after(staleBanner);
// ── a newer Context Hub: said quietly, installed only when the person presses Update ──
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
  updateText.textContent = u.state === "by hand" ? `Context Hub has an update. ${u.why}`
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
  const hints = chording() ? [["g", "then"], ["h", "home"], ["d", "dreams"], ["m", "memory"], ["n", "new session"], ["s", "sidebar"], [",", "settings"]] : prefix.armed ? prefixHints() : typeof pageHints === "function" ? pageHints() : pageHints;
  fill(status_, hints.map(([keys, word]) => h("span", {}, h("kbd", { textContent: keys }), word)), inTerminal() || prefix.armed ? null : [hints.some(([keys]) => keys === "/") ? null : h("span", {}, h("kbd", { textContent: "/" }), "go to"), h("span", {}, h("kbd", { textContent: "?" }), "keys")],
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
  else if (r.name === "new" || r.name === "settings") go("#/");
};
// How many panes a split takes: four, or up to six (max_panes) on a screen wide enough to give each one room.
const WIDE_SCREEN = 1600;
const paneLimit = () => { const want = Math.round(Number(pref("max_panes", 4))) || 4; return Math.max(2, Math.min(6, window.innerWidth >= WIDE_SCREEN ? want : Math.min(want, 4))); };
let MAX_PANES = paneLimit();
const limitWords = () => `${["", "One", "Two", "Three", "Four", "Five", "Six"][MAX_PANES]} panes is the limit`;
["resize", "hub:settings"].forEach((name) => window.addEventListener(name, () => { MAX_PANES = paneLimit(); }));
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
  if (parts[0] === "s" && parts[1] && parts[2] === "artifacts" && feature("artifacts") && /^[a-f0-9]{8}$/.test(parts[1])) return { name: "artifacts", sid: parts[1], project: (session(parts[1]) || {}).project, pick: parts.slice(3).join("/") };
  if (parts[0] === "s" && parts[1]) {
    const [text, zoom] = parts[1].split("~"), layout = readLayout(text);
    if (layout) { const ids = leavesOf(layout); return { name: "session", ids, layout, zoom: ids.length > 1 && ids.includes(zoom) ? zoom : null }; }
  }
  if (parts[0] === "p" && parts[1]) return { name: "project", project: parts[1], tab: parts[2] || "home", rest: parts.slice(3).join("/") };
  if (parts[0] === "new") return { name: "new" };
  if (parts[0] === "catcher") return { name: "catcher" };
  if (parts[0] === "settings") return { name: "settings", tab: parts[1] || "" };
  // The built-in browser and the device preview (ui/browser.js), while their switches are on: #/browser[/<sid>[/<address>]].
  if ((parts[0] === "browser" || parts[0] === "preview") && window.hubBrowser && feature(parts[0])) {
    const sid = /^[a-f0-9]{8}$/.test(parts[1] || "") ? parts[1] : "";  // #/browser/<address> works too, with no session
    return { name: parts[0], sid, url: sid || parts[1] === "-" ? parts.slice(2).join("/") : parts.slice(1).join("/") };
  }
  return { name: "now" };
};
// Hub-wide sessions belong to no project (project "@hub"). The page shows them under the hub's own project, the home
// project the server names in S.hubwide.home (the store whose roots list this hub's repository). A hub with no such
// project keeps them under one row of their own, which answers to project() like a project does.
const HUB = "@hub";
const hubProject = () => ({ name: HUB, display: "Hub sessions", hub: true, repos: [(S.hubwide || {}).folder || "~/agent-memory"], icon: null, setup: [], lessons: 0 });
const project = (name) => name === HUB ? hubProject() : S.projects.find((p) => p.name === name);
const hubHome = () => { const name = (S.hubwide || {}).home; return name ? S.projects.find((p) => p.name === name) || null : null; };
const ownerName = (s) => s.project === HUB && hubHome() ? hubHome().name : s.project;  // the project a session shows under
const ownerOf = (s) => project(ownerName(s));
const sessionsOf = (name) => S.sessions.filter((s) => ownerName(s) === name);
const hubRow = () => hubHome() ? [] : [hubProject()];  // the row of their own, only while there is no home project
const isHubHome = (p) => !!p && !!hubHome() && hubHome().name === p.name;
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
    isHubHome(p) ? { name: "New hub-wide session", icon: "hub", run: () => newSession(HUB) } : null,
    { name: "Project settings…", icon: "gear", run: () => projectSettings(p.name) },
    { group: "Folder" },
    ...groups().map((f) => ({ name: f.name, icon: "folder", on: now === f.id, run: () => { if (now !== f.id) changeGroups({ op: "move", project: p.name, id: f.id }, `Moved to ${f.name}`); } })),
    now ? { name: "Out of its folder", icon: "close", run: () => changeGroups({ op: "move", project: p.name, id: null }, "Out of its folder") } : null,
    { name: "New folder…", icon: "folderPlus", run: () => newFolder([p.name]) },
    { group: "Notices" },
    { name: isMuted(p.name) ? "Unmute notices and sounds" : "Mute notices and sounds", icon: "bell", run: () => toggleMute(p) },
    ...projectMenuExtras(p),
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
const attention = (name) => S.sessions.filter((s) => s.state === "needs" && (!name || ownerName(s) === name)).length
  + S.projects.filter((p) => (!name || p.name === name) && openReview(p)).length;
const liveClaude = (name) => sessionsOf(name).filter((s) => s.alive && s.kind === "claude");
const go = (hash) => { location.hash = hash; };

const crumbTo = (p) => h("a", { href: `#/p/${P(p.name)}` }, mark(p, 15), h("span", { class: "t", dir: "auto", textContent: p.display }));
// The phone layout: a narrow screen, or a touch screen too short for the desk's (a phone on its side). app.css asks the same.
const phone = matchMedia("(max-width: 760px), (pointer: coarse) and (max-height: 500px)");
// The phone's keyboard covers the page from below: the app takes the height that's left, so a message box stays above it.
if (window.visualViewport) {
  const vv = window.visualViewport;
  // Only at scale 1: pinched in, the visual viewport is the zoomed-in piece of the page, and sizing the app to it
  // would shrink the whole layout under the person's fingers (and pull the page back while they pan).
  const fitView = () => {
    if (Math.abs(vv.scale - 1) > 0.01) return;
    document.documentElement.style.setProperty("--vvh", `${Math.round(vv.height)}px`);
    // The keyboard is up when it takes a real piece of the window. A field that took focus without a tap (the terminal's,
    // as a session opens) shows no keyboard on iOS, so this, not focus, is what lets a phone on its side fold its bars away.
    document.body.classList.toggle("keyboard", phone.matches && window.innerHeight - vv.height > 120);
    if (phone.matches && (window.scrollY || document.documentElement.scrollTop)) window.scrollTo(0, 0);
  };
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
  document.body.dataset.sidebar = sidebarAt();
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
    const w = sidebarAt() === "right" ? side.getBoundingClientRect().right - x : x - side.getBoundingClientRect().left;
    if (w < SIDE.min - 48) { if (!shell.rail) { shell.w = widthBefore; setRail(true); } return; }
    shell.w = clampSide(w);
    if (shell.rail) setRail(false); else applyShell();
  },
  end: keepShell,
  reset: () => { shell.w = SIDE.start; keepShell(); if (shell.rail) setRail(false); else applyShell(); },
  step: (by) => { if (sidebarAt() === "right") by = -by; if (shell.rail) { if (by > 0) setRail(false); return; } if (shell.w + by < SIDE.min) { setRail(true); return; } shell.w = clampSide(shell.w + by); keepShell(); applyShell(); },
});
phone.addEventListener("change", () => { applyShell(); sideKey = ""; drawSide(); });
applyShell();

// ── The orb: the hub's status mark, a pixel dot orb (ui/orbs.js) ──
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
// A finished turn that asks you something, unread, is the rose orb of needs you, held still: close to needs, never quieter.
const orbState = (s) => s.state === "working" ? (s.orb || "working") : s.state === "error" ? "error" : s.state === "finished" && asksYou(s) && !isRead(s) ? "asks" : shownState(s);
// Line two of a session row: what it is doing or asking, in the state's colour. The orb already says which state.
const rowLine = (s) => {
  const state = shownState(s);
  if (state === "working") return s.activity ? [s.activity.tool, s.activity.target].filter(Boolean).join(" ") : oneLine(s.now);
  if (state === "needs") return oneLine(s.asking) || "Needs your input";
  if (state === "error") return oneLine(s.error) || "Stopped with an error";
  if (state === "finished" && s.asks) return oneLine(s.asking) || "Asks you";
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
  // On a session at a desk the tabs are this bar's row (polish-session): the page's name stays, for screen readers and the title.
  const merged = tabsMerged(), scrolled = tabsStrip.scrollLeft;
  top_.classList.toggle("with-tabs", merged);
  fill(top_,
    markMenu(h("button", { class: "icon menu-btn", title: "Menu", "aria-expanded": sideOpen() ? "true" : "false", onclick: () => setSide(!sideOpen()) }, uiIcon("menu"))),
    merged ? tabsBar : null,
    merged ? h("div", { class: "crumbs sr-only" }, h("h1", { class: "tail", dir: "auto", textContent: crumbs.map((c) => c.textContent).filter(Boolean).join(" / ") })) : h("div", { class: "crumbs" }, trail),
    h("div", { class: "actions-top" }, actions, tabsTopButton(), h("button", { class: "icon find-btn", type: "button", title: "Go to a session", "aria-label": "Go to a session", onclick: () => openPalette() }, uiIcon("find"))));
  if (merged) { tabsStrip.scrollLeft = scrolled; showTabOn(); markTabsEdge(); }  // moving the row resets its scroll: the front tab stays in view
};
const tail = (text) => h("h1", { class: "tail", dir: "auto", textContent: text });
// The page still has a name for the tab and for screen readers when something on screen already shows it.
const quietTail = (text) => h("h1", { class: "tail sr-only", dir: "auto", textContent: text });
// A page header's secondary actions: one ⋯ at its trailing edge, after the primary action (feat/nav).
const moreButton = (label, open, key) => h("button", { class: "icon top-more", type: "button", title: label, "aria-label": label, "aria-haspopup": "menu", "data-key": key, onclick: (e) => open(e.currentTarget) }, uiIcon("dots"));

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
const isOpen = (p, r) => { const v = expanded()[p.name]; return v === undefined ? r.project === p.name || sessionsOf(p.name).some((s) => s.alive) || (r.name === "session" && r.ids.some((id) => session(id) && ownerName(session(id)) === p.name)) : v; };
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
    c.phase === "running" ? h("span", { class: "state" }, orbOf("catcher", "dreaming")) : c.waiting ? h("span", { class: "count", textContent: c.waiting }) : null);
};
// When a run is carried out, a notification says how much it left for you (if notifications are on and the app isn't in front).
let catcherSeen;
const noticeCatcher = () => {
  const c = S.catcher || {}, mark = c.phase === "settled" ? `${c.run}:${c.settled}` : "";
  if (catcherSeen !== undefined && mark && mark !== catcherSeen) {
    const body = c.waiting ? `${c.waiting} ${c.waiting === 1 ? "thing waits" : "things wait"} for you` : "It decided everything. Nothing waits for you.";
    tell(pref("notify_catcher", "system"), { inFront: false, native: { title: "Dream Catcher", body, tag: "hub-catcher", open: () => go("#/catcher") },
      banner: { key: "catcher", kind: "catcher", icon: "catcher", title: "Dream Catcher", line: body, open: () => go("#/catcher") } });
  }
  if (mark || catcherSeen === undefined) catcherSeen = mark;
};
// A project's mark rolls up its sessions: needs you, then a finished turn you haven't read, then working, then dreaming.
const projectOrb = (p, sessions) => {
  const kind = attention(p.name) ? "needs" : rollupOf(sessions);
  return kind ? orbOf(`p:${p.name}`, ROLLUP_ORB[kind]) : p.dreaming ? orbOf(`p:${p.name}`, "dreaming") : null;
};
let sideLive = "";
const drawSide = () => {
  if (sideEdit.kind === "rename" && side.querySelector(".side-input")) return;
  const r = route(), order = railed() ? "rail" : sideOrder();
  // What is listed, and in what order, rebuilds the list; what a listed session is doing is patched in place (patchSide).
  const key = JSON.stringify([location.hash, hub.ready, hub.down, sideEdit, settingsProblems(), order, !!window.hubOrb, S.projects.map((p) => [p.name, p.display, p.icon, openReview(p), p.dreaming, p.needs]),
    S.sessions.map((s) => [s.id, s.title, s.project, s.alive, gone(s) ? s.state : ""]), order === "attention" ? attentionOrder().map((s) => [s.id, attentionKind(s)]) : order === "rail" ? [homeNeeds(), S.projects.map((p) => attention(p.name))] : null,
    expanded(), iconStamp, S.groups, saved.get("foldersShut", {}), catcherShown(), sidebarExtrasKey(), saved.get("termsOpen", {}), S.sessions.map((s) => s.kind === "shell" && shownState(s) === "shell" && s.created), Math.floor(Date.now() / 300000), saved.get("hub.tabs", [])]);
  const live = sideNow();
  if (key === sideKey) { if (live !== sideLive) { sideLive = live; patchSide(); } return; }
  sideKey = key; sideLive = live;
  const before = order === "attention" ? rowsAt() : new Map();
  sideList.classList.toggle("by-attention", order === "attention");
  if (order === "rail") drawRail(r); else if (order === "attention") drawByAttention(r); else drawTree(r);
  decorateSide(order);
  patchSide();
  moveRows(before);
  markSideEdge();
  if (document.body.dataset.jumpKeys) showJumps(document.body.dataset.jumpKeys);  // rows rebuilt while ⌥ is held keep their numbers
  const input = sideList.querySelector(".side-input");
  if (input) { input.focus(); input.select(); }
};
// ── The sidebar's parts (feat/nav): places at the top, the list with its own controls in its header, Settings at the foot ──
// Places: Go to (a desk's way in to ⌘K; a phone has it in the top bar), Home and the Dream Catcher. Home's count is the
// count on Home's own Needs you tab, so the two never disagree on one screen.
const homeNeeds = () => S.sessions.filter((s) => s.state === "needs" || s.state === "error").length
  + S.projects.filter((p) => openReview(p)).length + S.projects.filter((p) => p.needs).length + S.projects.filter((p) => p.waits && p.waits.you).length;
const goToRow = () => h("button", { type: "button", class: "nav side-go", "data-key": "goto", title: "Go to a session, project, board or setting", onclick: () => { closeSide(); openPalette(); } },
  slot(uiIcon("find")), h("span", { class: "label", textContent: "Go to" }), h("kbd", { class: "side-kbd", "aria-hidden": "true", textContent: "⌘K" }));
const homeRow = (r) => {
  const count = homeNeeds();
  return h("a", { class: `nav ${r.name === "now" ? "on" : ""}`, href: "#/", onclick: closeSide, "aria-current": r.name === "now" ? "page" : undefined, "data-key": "home" },
    slot(uiIcon("home")), h("span", { class: "label", textContent: "Home" }), count ? h("span", { class: "count", textContent: count }) : null);
};
const sidePlaces = (r) => [phone.matches ? null : goToRow(), homeRow(r), catcherRow(r)];
// A section of the list: its name, and the controls that act on it at its trailing edge.
const sideSection = (word, attrs, ...acts) => h("div", { ...attrs, class: `side-title with-act ${(attrs && attrs.class) || ""}` }, h("span", { textContent: word }), h("span", { class: "side-acts" }, acts));
const newProjectAct = () => h("a", { class: "side-title-act", href: "#/new", title: "New project", "aria-label": "New project", "data-key": "new-project", onclick: closeSide }, uiIcon("plus"));
// Settings: a labelled row at the foot, in every way the sidebar is drawn, with a count when Health finds problems.
const settingsProblems = () => settingsData ? (settingsData.problems || []).filter((p) => p.level !== "info").length : 0;
const settingsRow = (r) => {
  const on = r.name === "settings", n = settingsProblems(), label = n ? `Settings, ${n} ${n === 1 ? "problem" : "problems"}` : "Settings";
  return h("a", { class: `nav side-settings ${railed() ? "rail-item" : ""} ${on ? "on" : ""}`, href: "#/settings", onclick: closeSide, "aria-current": on ? "page" : undefined, "data-key": "settings", title: railed() ? `${label} (⌘,)` : undefined, "aria-label": label },
    slot(uiIcon("gear"), railed() && n ? h("span", { class: "rail-count", "aria-hidden": "true" }) : null), railed() ? null : h("span", { class: "label", textContent: "Settings" }), !railed() && n ? h("span", { class: "count", "aria-hidden": "true", textContent: n }) : null,
    !railed() && !n && !phone.matches ? h("kbd", { class: "side-kbd", "aria-hidden": "true", textContent: "⌘," }) : null);
};
const drawSideFoot = (r) => fill(sideEnd, h("div", { class: `side-row foot-row ${railed() ? "rail-foot" : ""}` }, settingsRow(r), phone.matches ? null : sideToggle()));
const sideToggle =() => h("button", { class: "icon side-toggle", type: "button", title: railed() ? "Expand the sidebar (⌘B)" : "Collapse the sidebar (⌘B)", "aria-label": railed() ? "Expand the sidebar" : "Collapse the sidebar", "aria-expanded": railed() ? "false" : "true", "aria-controls": "side", "data-key": "side-toggle", onclick: () => setRail(!railed()) }, uiIcon("sidebar"));
const IDLE_TERMINAL = 1800;  // seconds before an untouched terminal counts as idle in the sidebar
function drawTree(r) {
  const projectNode = (p) => {
    const open = isOpen(p, r);
    const sessions = sessionsOf(p.name);
    const activeHome = r.name === "project" && r.project === p.name && r.tab === "home";
    const heldInside = !open && r.name === "session" && r.ids.some((id) => session(id) && ownerName(session(id)) === p.name);
    // Closed and ended sessions fold away under the running ones, and open by themselves when one of them is on screen.
    const all = sessions.filter((s) => !gone(s));
    // Two or more idle terminals fold into one row, "Terminals 3" (feat/polish-pages). Idle: a plain terminal over half an
    // hour old that isn't on screen, in a tab, being renamed, or running subagents. One you just opened stays in view.
    const tabbed = JSON.stringify(saved.get("hub.tabs", []));
    const idleTerm = (s) => s.kind === "shell" && shownState(s) === "shell" && Date.now() / 1000 - (s.created || 0) > IDLE_TERMINAL && !tabbed.includes(s.id)
      && !(s.agents && s.agents.list && s.agents.list.length) && !(r.name === "session" && r.ids.includes(s.id)) && sideEdit.id !== s.id;
    const terms = all.filter(idleTerm).length >= 2 ? all.filter(idleTerm) : [];
    const live = all.filter((s) => !terms.includes(s));
    const termsOpen = !!saved.get("termsOpen", {})[p.name];
    const past = sessions.filter(gone).sort((a, b) => (b.closedAt || b.created) - (a.closedAt || a.created));
    const pastOpen = !!saved.get("closedOpen", {})[p.name] || (r.name === "session" && past.some((s) => r.ids.includes(s.id))) || past.some((s) => sideEdit.id === s.id);
    const pastWord = past.every((s) => s.state === "ended") ? "Ended" : "Closed";
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
          sideLines(s, false)),
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
        terms.length ? h("button", { class: "side-fold terms-fold", type: "button", "aria-expanded": termsOpen ? "true" : "false", "data-key": `terms:${p.name}`,
          onclick: () => { saved.set("termsOpen", { ...saved.get("termsOpen", {}), [p.name]: !termsOpen }); sideKey = ""; drawSide(); const again = sideList.querySelector(`[data-key="terms:${CSS.escape(p.name)}"]`); if (again) again.focus({ preventScroll: true }); } },
          h("span", { class: `slot chev ${termsOpen ? "open" : ""}`, "aria-hidden": "true" }, svg(UI.chev)), h("span", { textContent: "Terminals" }), h("span", { class: "fold-n", textContent: terms.length })) : null,
        terms.length && termsOpen ? h("div", { class: "side-past side-terms" }, terms.map(sessionRow)) : null,
        past.length ? h("button", { class: "side-fold", type: "button", "aria-expanded": pastOpen ? "true" : "false", "data-key": `fold:${p.name}`,
          onclick: () => { saved.set("closedOpen", { ...saved.get("closedOpen", {}), [p.name]: !pastOpen }); sideKey = ""; drawSide(); const again = sideList.querySelector(`[data-key="fold:${CSS.escape(p.name)}"]`); if (again) again.focus({ preventScroll: true }); } },
          h("span", { class: `slot chev ${pastOpen ? "open" : ""}`, "aria-hidden": "true" }, svg(UI.chev)), h("span", { textContent: pastWord }), h("span", { class: "fold-n", textContent: past.length })) : null,
        past.length && pastOpen ? h("div", { class: "side-past" }, past.map(sessionRow)) : null) : null,
    );
  };
  // Folders first, in the order you put them, each with its projects; then the projects in no folder.
  const shut = saved.get("foldersShut", {});
  const folderNode = (f) => {
    const inside = sideProjects().filter((p) => groupOf(p.name) === f.id);
    const holds = inside.some((p) => (r.project === p.name) || (r.name === "session" && r.ids.some((id) => session(id) && ownerName(session(id)) === p.name)));
    const open = !shut[f.id] || holds;
    const waiting = inside.reduce((n, p) => n + attention(p.name), 0), working = S.sessions.some((s) => inside.some((p) => p.name === ownerName(s)) && s.state === "working");
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
  const loose = sideProjects().filter((p) => !groupOf(p.name));
  const looseDrop = (e) => { const name = e.dataTransfer.getData("text/x-hub-project"); e.currentTarget.classList.remove("drop-on"); if (name && groupOf(name)) { e.preventDefault(); changeGroups({ op: "move", project: name, id: null }, "Out of its folder"); } };
  fill(sideList,
    h("div", { class: "brand" }, slot(h("i")), h("span", { class: "label", textContent: "Context Hub" })),
    sidePlaces(r),
    hubRow().map(projectNode),
    sideSection("Projects", { ondragover: (e) => { if ([...e.dataTransfer.types].includes("text/x-hub-project")) { e.preventDefault(); e.currentTarget.classList.add("drop-on"); } }, ondragleave: (e) => e.currentTarget.classList.remove("drop-on"), ondrop: looseDrop },
      sideOrderToggle(), h("button", { class: "side-title-act", type: "button", title: "New folder", "aria-label": "New folder", "data-key": "new-folder", onclick: () => newFolder() }, uiIcon("folderPlus")), newProjectAct()),
    groups().map(folderNode),
    loose.map(projectNode),
    hiddenProjectsRow(r, projectNode),
    hub.ready && !S.projects.length ? h("div", { class: "side-none" }, h("a", { class: "in-link", href: "#/new", onclick: closeSide, textContent: "Create your first project" })) : null);
  drawSideFoot(r);
}
// The rail keeps what you supervise: each project's mark and an orb for every session still running under it.
function drawRail(r) {
  const count = homeNeeds();
  const item = (attrs, label, ...kids) => h("a", { ...attrs, class: `nav rail-item ${attrs.class || ""}`, title: label, "aria-label": label, onclick: closeSide }, slot(...kids));
  fill(sideList,
    h("div", { class: "brand" }, slot(h("i")), h("span", { class: "sr-only", textContent: "Context Hub" })),
    h("button", { type: "button", class: "nav rail-item side-go", title: "Go to (⌘K)", "aria-label": "Go to", "data-key": "goto", onclick: () => openPalette() }, slot(uiIcon("find"))),
    item({ href: "#/", class: r.name === "now" ? "on" : "", "aria-current": r.name === "now" ? "page" : undefined, "data-key": "home" }, count ? `Home, ${count} ${count === 1 ? "needs" : "need"} you` : "Home", uiIcon("home"), count ? h("span", { class: "rail-count", "aria-hidden": "true" }) : null),
    item({ href: "#/catcher", class: r.name === "catcher" ? "on" : "", "aria-current": r.name === "catcher" ? "page" : undefined, "data-key": "catcher" }, catcherLabel(), uiIcon("catcher"), (S.catcher || {}).waiting ? h("span", { class: "rail-count", "aria-hidden": "true" }) : null),
    [...hubRow(), ...groups().flatMap((f) => sideProjects().filter((p) => groupOf(p.name) === f.id)), ...sideProjects().filter((p) => !groupOf(p.name))].map((p) => {
      const live = sessionsOf(p.name).filter((s) => !gone(s));
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
  drawSideFoot(r);
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
// ── A session's state, as the server decides it (feat/detect): Done · asks you, why, and the sessions a restart took ──
// A finished turn whose last sentence asks you something stays done, with asks. The asks_as_needs setting counts it as needs.
const applyAsks = (sessions) => {
  const needs = pref("asks_as_needs", false) === true;
  (sessions || []).forEach((s) => { if (!s.asks) return; if (needs && s.state === "finished") s.state = "needs"; else if (!needs && s.state === "needs") s.state = "finished"; });
  return sessions;
};
const asksTag = () => h("span", { class: "asks-tag", textContent: "asks you" });
// A hub-wide session shown under the home project carries the hub mark before its name, so it reads apart from the project's own.
const HUBWIDE_TIP = "Hub-wide session: works on every project's memory, with no permission prompts";
const hubwideTag = (s) => s.project === HUB && hubHome() ? h("span", { class: "hubwide-tag", role: "img", "aria-label": "hub-wide", title: HUBWIDE_TIP }, uiIcon("hub")) : null;
window.addEventListener("hub:settings", () => { applyAsks(S.sessions); sideKey = ""; drawSide(); if (page.update) page.update(); });
const lostNow = () => S.sessions.filter((s) => s.lost && !s.alive);
const resumeLost = async (ids) => {
  const res = await api("/api/lost/resume", ids ? { ids } : {});
  const back = res.resumed.length, bad = Object.keys(res.failed).length;
  toast(bad ? (back ? `Resumed ${back}. ${bad} couldn't be resumed.` : bad === 1 ? "It couldn't be resumed." : `${bad} couldn't be resumed.`) : back === 1 ? "Resumed" : `Resumed ${back} sessions`, !!bad);
  await tick();
};
const dismissLost = async () => { await api("/api/lost/dismiss", {}); await tick(); };
// Home's notice after a restart: every session that was running, Resume all, or one at a time. A failed one keeps its error.
const lostPanel = () => {
  const lost = lostNow();
  if (!lost.length) return null;
  const n = lost.length;
  return h("section", { class: "panel lost", "aria-labelledby": "lost-h" },
    h("header", {}, h("h2", { id: "lost-h", textContent: `${n === 1 ? "1 session was" : `${n} sessions were`} running when the Mac restarted` }),
      h("span", { class: "lost-acts" },
        h("button", { class: "btn", type: "button", "data-key": "lost:dismiss", onclick: once("Hiding…", dismissLost) }, "Not now"),
        h("button", { class: "btn primary", type: "button", "data-key": "lost:all", onclick: once("Resuming…", () => resumeLost()) }, n === 1 ? "Resume" : `Resume all ${n}`))),
    h("div", { class: "qlist" }, lost.map((s) => {
      const p = ownerOf(s);
      return h("div", { class: "qrow lost-row", "data-sid": s.id },
        rowOrb("ended", ROW_ORB),
        h("span", { class: "q-main" }, h("a", { class: "q-t", href: `#/s/${s.id}`, dir: "auto", textContent: s.title }),
          s.lost.error ? h("span", { class: "q-line err", dir: "auto", title: s.lost.error, textContent: s.lost.error }) : h("span", { class: "q-line", dir: "auto", textContent: oneLine(s.said) || oneLine(s.task) || "Ready to resume" })),
        h("span", { class: "q-meta" }, p ? [mark(p, 15), h("span", { class: "q-p", dir: "auto", textContent: p.display })] : null,
          h("button", { class: "btn lost-one", type: "button", "data-key": `lost:${s.id}`, "aria-label": `${s.lost.error ? "Try again" : "Resume"}: ${s.title}`, onclick: once("Resuming…", () => resumeLost([s.id])) }, s.lost.error ? "Try again" : "Resume")));
    })));
};
const statusLine = (s) => s.state === "error" ? (s.error || "Something went wrong") : s.state === "working" ? `Working${s.now ? `: ${s.now}` : ""}` : s.state === "needs" ? (s.asking || "Needs your input") : s.state === "finished" ? (s.asks ? `Done · asks you${s.asking ? `: ${s.asking}` : ""}` : `Done${s.said ? `: ${s.said}` : ""}`) : s.state === "shell" ? "Terminal"
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
  // A session in a worktree of its own can take its checkout with it. Only once nothing is uncommitted: the commit step
  // runs first, and if files are still left the checkout stays and the hub asks again, naming them.
  const tree = check.tree && check.tree.checkout !== false && !check.noVcs ? check.tree : null;
  const treeBox = h("input", { type: "checkbox", checked: !!tree && !tree.changed });
  const treeNote = h("p", { class: "close-hint" });
  const syncTree = () => {
    if (!tree) return;
    treeNote.hidden = !treeBox.checked;
    treeNote.textContent = tree.changed ? "If files are still uncommitted when it closes, the checkout stays and you're asked before anything is lost."
      : `${tree.branch} stays${tree.ahead ? `, with its ${countOf(tree.ahead, "commit")}` : ""}. The session can't be resumed once its checkout is gone.`;
  };
  treeBox.addEventListener("change", syncTree);
  const dialog = h("dialog", { class: "confirm close-sheet", "aria-label": `Close ${s.title}` });
  const stay = h("button", { type: "button", class: "btn", textContent: "Keep running", onclick: () => dialog.close() });
  const agree = h("button", { type: "button", class: "btn primary", textContent: "Close session" });
  agree.onclick = once("Closing…", async () => {
    const commit = !commitBox.disabled && commitBox.checked;
    watchClose(s.id);
    const done = await api(`/api/sessions/${s.id}/close`, { note: box.checked, commit, hint: commit ? hint.value.trim() : "", ...(tree && treeBox.checked ? { removeTree: true } : {}) });
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
    tree ? h("label", { class: "check" }, treeBox, h("span", {}, "Remove the checkout ", h("span", { class: "check-aside", textContent: "(keeps the branch)" }))) : null,
    tree ? treeNote : null,
    busy ? h("p", { class: "close-hint", textContent: busy }) : null,
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  syncCommit();
  syncTree();
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
  const left = r.left && !(r.tree && r.tree.changed) ? `${r.left} uncommitted ${r.left === 1 ? "change" : "changes"} left${folder ? ` in ${folder}` : ""}.` : "";
  const handoff = r.commit && !r.handoff ? "No handoff came back." : "";
  return [committed, left, handoff, treeWords(r.tree)].filter(Boolean).join(" ");
};
const noticeClosed = () => {
  const watch = closeWatch();
  let changed = false;
  S.sessions.forEach((s) => {
    if (s.state === "closing" && !(s.id in watch)) { watch[s.id] = Date.now(); changed = true; }
    if (s.state !== "closed" || !(s.id in watch)) return;
    delete watch[s.id]; changed = true;
    const words = closedWords(s), mode = pref("notify_closed", "system");
    const tree = (s.closeResult || {}).tree;
    // Asked to remove its checkout, and files were still uncommitted: the second ask, naming them.
    if (tree && tree.kept && tree.changed && document.visibilityState === "visible" && !document.querySelector("dialog[open]")) setTimeout(() => removeCheckout(s.project, s.repo, { ...tree, checkout: true }), 0);
    say(`${bareTitle(s)} has closed. ${words}`);
    if (mode === "off") return;
    logNotice({ key: `closed:${s.id}`, kind: "closed", title: `Closed: ${bareTitle(s)}`, line: words || "The conversation is kept.", sid: s.id });
    toast(`Closed “${bareTitle(s)}”. ${words || "The conversation is kept."}`, true);
    if (mode === "system" && notifyState() === "on" && (document.visibilityState !== "visible" || !document.hasFocus())) {
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
const rowTip = (s) => [s.title, statusLine(s) === s.title ? "" : statusLine(s), s.why ? `Why: ${s.why}` : ""].filter(Boolean).join("\n");
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
  s.kind !== "claude" && s.alive ? { name: "Stop terminal…", run: () => stopTerminal(s) } : null,
  canResume(s) ? { name: "Resume", run: guard(() => resumeSession(s)) } : null,
  { name: "Delete…", run: () => deleteSession(s) },
].filter(Boolean));
function renameRow(s) {
  const commit = (byKey) => {
    if (sideEdit.id !== s.id) return;
    const name = input.value.trim().replace(/\s+/g, " ").slice(0, 80);
    const live = session(s.id) || s;  // polls replaced S while this row was being edited
    if (name && name !== live.title) { live.title = name; api(`/api/sessions/${s.id}/rename`, { title: name }).then(renamed, (error) => { toast(error.known ? error.message : NO_ANSWER, true); tick(); }); }
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

// ── Worktrees: the checkout a session of its own works in, its branch, and tidying both away once the work is safe ──
// The server measures each branch against the one it came from (hub_worktrees.py). Nothing here deletes without saying
// what goes: uncommitted files and unmerged commits each need a second yes that names how many.
const countOf = (n, one, many) => `${n} ${n === 1 ? one : many || `${one}s`}`;
// The hub names a branch hub/<project>-<title>-<id>: under its project, the project's part says nothing new.
const treeName = (t, project) => {
  const name = (t.branch || "").replace(/^hub\//, ""), lead = `${(project || "").toLowerCase().replace(/[^a-z0-9]+/g, "-")}-`;
  return lead.length > 1 && name.startsWith(lead) && name.length > lead.length + 4 ? name.slice(lead.length) : name;
};
// The one fact that matters most first: what would be lost, then what isn't merged yet, then that it's done.
const treeFacts = (t) => [
  t.checkout === false ? "no checkout" : null,
  t.changed ? `${t.changed} changed` : null,
  t.ahead ? `${t.ahead} ahead` : null,
  t.behind && !t.merged ? `${t.behind} behind` : null,
  t.merged ? "merged" : t.fresh && !t.changed ? "no commits yet" : null,
].filter(Boolean);
const treeTip = (t) => [t.branch, ...treeFacts(t)].join(" · ");
const treeWords = (t) => !t ? "" : t.removed ? `Its checkout is removed and ${t.branch} is kept.`
  : t.kept ? (t.changed ? `Its checkout is kept: ${countOf(t.changed, "file")} ${t.changed === 1 ? "is" : "are"} still uncommitted.` : `Its checkout is kept. ${t.why || ""}`.trim()) : "";
const treeState = (t) => t.changed ? "dirty" : t.merged ? "merged" : t.ahead ? "ahead" : "";
const treeChip = (s) => {
  const t = s.tree, facts = treeFacts(t);
  return h("button", { type: "button", class: `tree-chip ${treeState(t)}`, title: `${treeTip(t)}\nShow the worktree`, "aria-haspopup": "dialog", "data-key": "tree",
    "aria-label": `Worktree ${treeTip(t)}`, onclick: () => treeSheet(s.project, s.repo, t, s) },
    svg(UI.branch), h("span", { class: "tree-name", dir: "ltr", textContent: treeName(t, s.project) }),
    facts.length ? h("span", { class: "tree-facts", textContent: facts.join(" · ") }) : null,
    facts.length ? h("span", { class: "tree-fact", textContent: facts[0] }) : null);
};
const filesList = (files, total, label) => files && files.length ? h("ul", { class: "close-files", "aria-label": label },
  files.map((f) => h("li", { dir: "auto", title: f, textContent: f })), total > files.length ? h("li", { class: "more", textContent: `and ${total - files.length} more` }) : null) : null;
// The facts of one checkout, and what can be done with it from here.
const treeSheet = (name, repo, t, s) => {
  const dialog = h("dialog", { class: "confirm tree-sheet", "aria-label": `Worktree ${t.branch}` });
  const running = s && (s.alive || s.state === "closing");
  const done = h("button", { type: "button", class: "btn", textContent: "Done", onclick: () => dialog.close() });
  const remove = t.checkout !== false && !running ? h("button", { type: "button", class: "btn", textContent: "Remove checkout…", onclick: () => { dialog.close(); removeCheckout(name, repo, t); } }) : null;
  const branchGo = t.checkout === false && !t.missing ? h("button", { type: "button", class: "btn", textContent: "Delete branch…", onclick: () => { dialog.close(); deleteBranch(name, repo, t); } }) : null;
  fill(dialog,
    h("h1", {}, h("span", { class: "tree-title", dir: "ltr", textContent: t.branch })),
    h("div", { class: "sheet-facts" }, t.base ? h("span", { textContent: `from ${t.base}` }) : null, ...treeFacts(t).map((f) => h("span", { textContent: f }))),
    h("p", { class: "sheet-lead", textContent: t.missing ? "This branch isn't there any more."
      : t.merged ? `Its work is in ${t.base}. The checkout and the branch can go.`
      : t.ahead ? `${countOf(t.ahead, "commit")} on this branch ${t.ahead === 1 ? "isn't" : "aren't"} in ${t.base || "its base"} yet.`
      : "Nothing has been committed on this branch yet." }),
    t.changed ? h("div", { class: "close-warn", role: "note" }, dot("needs"), h("div", { class: "close-warn-body" },
      h("p", {}, h("b", { textContent: `${countOf(t.changed, "uncommitted file")}` }), " in the checkout."), filesList(t.files, t.changed, "Uncommitted files"))) : null,
    t.path && t.checkout !== false ? h("p", { class: "close-hint tree-path", dir: "ltr", textContent: t.path }) : null,
    running ? h("p", { class: "close-hint", textContent: "Its session is still running. Close it to remove the checkout." }) : null,
    h("div", { class: "actions" }, s && s.id && !(location.hash === `#/s/${s.id}`) ? h("a", { class: "retry", href: `#/s/${s.id}`, textContent: "Open the session", onclick: () => dialog.close() }) : h("span"),
      h("div", { class: "right" }, branchGo, remove, done)));
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  sheet(dialog);
  done.focus();
};
// Removing a checkout keeps its branch. A clean one goes at once; one with uncommitted files asks again, naming them.
const removeCheckout = guard(async (name, repo, t, after) => {
  const ask = { repo, path: t.path };
  if (!t.changed) {
    try {
      await api(`/api/p/${P(name)}/worktrees/remove`, ask);
    } catch (error) {
      if (!/uncommitted/.test(error.message)) throw error;
      const fresh = await api(`/api/p/${P(name)}/worktrees`);  // something was written there since it was looked at
      const row = fresh.repos.flatMap((r) => r.rows).find((r) => r.path === t.path);
      if (row) return removeCheckout(name, repo, row, after);
      throw error;
    }
    toast(`Removed the checkout. ${t.branch} is kept.`);
    if (after) after();
    return tick();
  }
  const dialog = h("dialog", { class: "confirm", "aria-label": "Remove the checkout and lose its uncommitted files" });
  const stay = h("button", { type: "button", class: "btn", textContent: "Keep it", onclick: () => dialog.close() });
  const agree = h("button", { type: "button", class: "btn danger", textContent: `Remove and lose ${countOf(t.changed, "file")}` });
  agree.onclick = once("Removing…", async () => {
    await api(`/api/p/${P(name)}/worktrees/remove`, { ...ask, force: true, expect: t.changed });
    dialog.close();
    toast(`Removed the checkout and ${countOf(t.changed, "uncommitted file")}. ${t.branch} is kept.`);
    if (after) after();
    await tick();
  }, agree);
  fill(dialog,
    h("h1", {}, `Lose ${countOf(t.changed, "uncommitted file")}?`),
    h("p", { class: "sheet-lead" }, "The checkout of ", h("span", { class: "mono", dir: "ltr", textContent: t.branch }), ` still has ${t.changed === 1 ? "a file that was never committed" : "files that were never committed"}. Removing it deletes ${t.changed === 1 ? "it" : "them"} for good. The branch and its commits stay.`),
    filesList(t.files, t.changed, "Files that would be lost"),
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  sheet(dialog);
  stay.focus();
});
// A merged (or empty) branch goes at once. One with commits that aren't merged needs the box ticked that names how many.
const deleteBranch = guard(async (name, repo, t, after) => {
  if (t.merged || t.fresh) {
    await api(`/api/p/${P(name)}/worktrees/branch`, { repo, branch: t.branch });
    toast(`Deleted ${t.branch}.${t.merged ? ` Its work is in ${t.base}.` : ""}`);
    if (after) after();
    return tick();
  }
  const dialog = h("dialog", { class: "confirm", "aria-label": `Delete ${t.branch}` });
  const stay = h("button", { type: "button", class: "btn", textContent: "Keep it", onclick: () => dialog.close() });
  const agree = h("button", { type: "button", class: "btn danger", textContent: "Delete branch", disabled: true });
  const sure = h("input", { type: "checkbox", onchange: () => { agree.disabled = !sure.checked; } });
  agree.onclick = once("Deleting…", async () => {
    await api(`/api/p/${P(name)}/worktrees/branch`, { repo, branch: t.branch, force: true, expect: t.ahead });
    dialog.close();
    toast(`Deleted ${t.branch} and its ${countOf(t.ahead, "unmerged commit")}.`);
    if (after) after();
    await tick();
  }, agree);
  fill(dialog,
    h("h1", {}, "Delete ", h("span", { class: "tree-title", dir: "ltr", textContent: t.branch }), "?"),
    h("div", { class: "close-warn", role: "note" }, dot("needs"), h("div", { class: "close-warn-body" },
      h("p", {}, h("b", { textContent: `${countOf(t.ahead, "commit")} ${t.ahead === 1 ? "isn't" : "aren't"} merged` }), ` into ${t.base || "its base"}. Deleting the branch loses ${t.ahead === 1 ? "it" : "them"}, and the hub can't bring ${t.ahead === 1 ? "it" : "them"} back.`))),
    h("label", { class: "check" }, sure, h("span", { textContent: `Delete ${countOf(t.ahead, "unmerged commit")} for good` })),
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  sheet(dialog);
  stay.focus();
});
// "Clean up merged": what it would do comes first, and only what was shown is done.
const cleanMerged = guard(async (name, after) => {
  const preview = await api(`/api/p/${P(name)}/worktrees/clean`, {});
  const plan = preview.plan || [], skip = preview.skip || [];
  const dialog = h("dialog", { class: "confirm tree-clean", "aria-label": "Clean up merged worktrees" });
  const stay = h("button", { type: "button", class: "btn", textContent: plan.length ? "Cancel" : "Done", onclick: () => dialog.close() });
  const agree = plan.length ? h("button", { type: "button", class: "btn primary", textContent: `Clean up ${plan.length}` }) : null;
  if (agree) agree.onclick = once("Cleaning up…", async () => {
    const done = await api(`/api/p/${P(name)}/worktrees/clean`, { keys: plan.map((i) => i.key) });
    dialog.close();
    toast(`Cleaned up ${countOf(done.done.length, "merged branch", "merged branches")}.${done.left.length ? ` ${countOf(done.left.length, "was", "were")} left: ${done.left[0].why}` : ""}`, !!done.left.length);
    if (after) after();
    await tick();
  }, agree);
  const line = (i, why) => h("li", {}, h("span", { class: "mono", dir: "ltr", textContent: i.branch }), h("small", { textContent: why || (i.path ? "checkout and branch" : "branch") }));
  fill(dialog,
    h("h1", {}, "Clean up merged worktrees"),
    h("p", { class: "sheet-lead", textContent: plan.length ? "Their work is already in the branch they came from, so nothing is lost." : "Nothing merged is waiting to be cleaned up." }),
    plan.length ? h("ul", { class: "tree-plan", "aria-label": "To remove" }, plan.map((i) => line(i))) : null,
    skip.length ? h("p", { class: "close-hint tree-skip-head", textContent: `Left alone: ${countOf(skip.length, "merged branch", "merged branches")}` }) : null,
    skip.length ? h("ul", { class: "tree-plan skip", "aria-label": "Left alone" }, skip.map((i) => line(i, i.why))) : null,
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, stay, agree)));
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  sheet(dialog);
  (agree || stay).focus();
});
// The project page's list: every checkout and every left-over branch, with what can be done to each.
const treesPanel = (name, data, reload) => {
  const repos = (data && data.repos) || [];
  const rows = repos.flatMap((r) => r.rows.map((t) => ({ ...t, repo: r.repo, repoName: r.name })));
  const off = repos.filter((r) => r.noVcs);
  if (!rows.length && !off.length) return null;
  const many = repos.filter((r) => r.rows.length).length > 1;
  const merged = rows.filter((t) => t.merged).length;
  const line = (t) => {
    const s = t.session && session(t.session.id);
    const running = s ? s.alive || s.state === "closing" : t.session && (t.session.alive || t.session.closing);
    return h("div", { class: "tree-row" },
      h("button", { type: "button", class: "tree-main", title: `${treeTip(t)}\nShow the worktree`, "aria-haspopup": "dialog", onclick: () => treeSheet(name, t.repo, t, s || t.session) },
        h("span", { class: `tree-mark ${treeState(t)}` }, svg(UI.branch)),
        h("span", { class: "tree-text" },
          h("span", { class: "tree-name", dir: "ltr", textContent: treeName(t, name) }),
          h("small", { textContent: [many ? t.repoName : null, t.session ? (running ? "running" : bareTitle(s || { ...t.session, project: name })) : t.path ? "no session" : null, ...treeFacts(t)].filter(Boolean).join(" · ") }))),
      h("span", { class: "tree-acts" },
        t.session && !(location.hash === `#/s/${t.session.id}`) && s ? h("a", { class: "retry", href: `#/s/${t.session.id}`, textContent: "Open" }) : null,
        t.path && !running ? h("button", { type: "button", class: "retry", textContent: "Remove", title: t.changed ? `Remove the checkout and lose ${countOf(t.changed, "uncommitted file")}` : "Remove the checkout. The branch is kept.", onclick: () => removeCheckout(name, t.repo, t, reload) }) : null,
        !t.path && !t.missing ? h("button", { type: "button", class: `retry ${t.merged || t.fresh ? "" : "warn"}`, textContent: "Delete", title: t.merged ? "Delete the branch. Its work is merged." : t.fresh ? "Delete the branch. It has no commits." : `Delete the branch and its ${countOf(t.ahead, "unmerged commit")}`, onclick: () => deleteBranch(name, t.repo, t, reload) }) : null));
  };
  return panel("Worktrees", merged ? h("button", { type: "button", class: "retry", textContent: `Clean up merged (${merged})`, onclick: () => cleanMerged(name, reload) }) : null,
    rows.map(line),
    off.map((r) => h("p", { class: "close-hint tree-off", textContent: `The hub never runs git in ${r.name} (no_vcs), so its worktrees aren't listed.` })));
};

// ── Sessions waiting for you: a card in the app, and a browser notification when you are elsewhere ──
const notifyState = () => !("Notification" in window) ? "none" : Notification.permission === "granted" ? (saved.get("notify", true) ? "on" : "off") : Notification.permission;
const postNotification = (title, options) => { try { return new Notification(title, options); } catch { return null; } };
const toggleNotify = guard(async () => {
  if (Notification.permission === "denied") { toast("Allow notifications for this site in your browser settings"); return; }
  if (Notification.permission === "default") {
    const answer = await Notification.requestPermission();
    saved.set("notify", answer === "granted");
    if (answer === "granted") postNotification("Context Hub", { body: "You'll hear from me when a session needs you." });
  } else saved.set("notify", !saved.get("notify", true));
  sideKey = "";
  drawSide();
});
// Notifications live in Settings › Notifications & sound. Home asks once, under the queue it is about: only while this
// browser was never asked, while notify_needs is "system", and until it is answered either way (feat/nav).
const notifyAsk = () => !saved.get("notifyAsked", false) && notifyState() === "default" && pref("notify_needs", "system") === "system";
const notifyPrompt = () => {
  if (!notifyAsk()) return null;
  const done = () => { saved.set("notifyAsked", true); if (page.update) page.update(); };
  return h("section", { class: "panel notify-ask", "aria-labelledby": "notify-ask-t" },
    h("span", { class: "slot", "aria-hidden": "true" }, uiIcon("bell")),
    h("p", { id: "notify-ask-t", textContent: "Get a notice on this device when a session needs you" }),
    h("span", { class: "notify-ask-acts" },
      h("button", { type: "button", class: "btn", "data-key": "notify-later", textContent: "Not now", onclick: () => { done(); toast("Settings › Notifications turns them on any time"); } }),
      h("button", { type: "button", class: "btn primary", "data-key": "notify-on", textContent: "Turn on", onclick: async () => { await toggleNotify(); done(); } })));
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
  const key = JSON.stringify([cards.map((s) => [s.id, s.title, s.asking]), more, barred()]);
  if (key === alerts.key) return;
  alerts.key = key;
  fill(alertsList, cards.map((s) => h("div", { class: "alert" },
    h("button", { class: "alert-open", "data-key": `alert:${s.id}`, title: s.asking || undefined, onclick: () => openWaiting(s.id) }, slot(orbOf(`a:${s.id}`, "needs")),
      h("span", { class: "alert-text" }, h("b", { dir: "auto", textContent: bareTitle(s) || (ownerOf(s) || {}).display || s.project }),
        h("small", { dir: "auto" }, ownerOf(s) ? h("span", { class: "alert-proj" }, mark(ownerOf(s), 12), " ", ownerOf(s).display, " · ") : null, oneLine(s.asking) || "Needs your input"))),
    h("button", { class: "icon", title: "Dismiss", "data-key": `dismiss:${s.id}`, onclick: () => { alerts.dismissed.add(s.id); drawAlerts(); } }, uiIcon("close")))),
    more ? h("a", { class: "alert-more", href: "#/", textContent: `${more} more` }) : null,
    barred() && cards.length ? h("button", { class: "alert-next", type: "button", "data-key": "alert-next", title: "Next session that needs you", "aria-label": "Next session that needs you", onclick: nextForYou }, h("span", { textContent: "Next" }), svg(UI.chev)) : null);
};
const noticeNeeds = () => {
  const waiting = S.sessions.filter((s) => s.state === "needs");
  const now = new Set(waiting.map((s) => s.id));
  alerts.dismissed.forEach((id) => { if (!now.has(id)) alerts.dismissed.delete(id); });
  alerts.native.forEach((note, id) => { if (!now.has(id)) { note.close(); alerts.native.delete(id); } });
  alerts.seen = now;  // the notice itself is noticeChanges', once the wait has held for two polls
};
const titleNow = () => {
  const r = route(), p = r.project && project(r.project);
  const name = r.name === "session" ? (r.ids.length > 1 ? "Split" : (session(r.ids[0]) || {}).title || "Not found")
    : r.name === "new" ? "New project"
    : r.name === "catcher" ? "Dream Catcher"
    : r.name === "settings" ? "Settings"
    : r.name === "artifacts" ? `Artifacts · ${(session(r.sid) || {}).title || "Session"}`
    : r.name === "browser" ? "Browser" : r.name === "preview" ? "Device preview"
    : r.name === "project" && p && p.hub && hubHome() ? `New hub-wide session · ${hubHome().display}`
    : r.name === "project" && p ? (r.tab === "home" ? p.display : `${{ memory: "Memory", dreams: "Dreams", new: "New session", artifacts: "Artifacts" }[r.tab]} · ${p.display}`)
    : "";
  const { needs: waiting, done, working } = attentionCounts();
  // A tab is narrow and cut from the end, so the counts lead: what waits on you first, then what finished unread, then what's at work.
  const counts = [waiting ? `${waiting} waiting` : "", done ? `${done} done` : "", working ? `${working} working` : ""].filter(Boolean).join(", ");
  document.title = `${counts ? `(${counts}) ` : ""}${name ? `${name} · ` : ""}Context Hub`;
  drawFavicon(waiting ? "needs" : done ? "done" : working ? "working" : "");
};
// The tab's icon carries the same news: a rose diamond when something waits on you, a blue check when a turn finished
// unread, a jade square while any work runs.
const FAVICON = { "": "", needs: "%3Cpath d='M24 15l7 7-7 7-7-7z' fill='%23ff5c8a'/%3E", done: "%3Cpath d='M17.5 22.5l4 4 8-9' fill='none' stroke='%238fb0ff' stroke-width='3.2' stroke-linecap='square'/%3E", working: "%3Crect x='19' y='17' width='10' height='10' fill='%232dd4a0'/%3E" };
const faviconEl = document.querySelector("link[rel=icon]");
let faviconShown = null;
const drawFavicon = (state) => {
  if (!faviconEl || faviconShown === state) return;
  faviconShown = state;
  faviconEl.href = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%230b1020'/%3E%3Crect x='${state ? 7 : 12}' y='7' width='8' height='18' fill='%232f62f5'/%3E${FAVICON[state]}%3C/svg%3E`;
};
const refreshTips = () => side.querySelectorAll("[data-sid]").forEach((row) => { const s = session(row.dataset.sid); if (s) row.title = rowTip(s); });
document.getElementById("scrim").addEventListener("click", () => { closeSide(); drawPhoneBar(); });
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
  // Leaving runs once: what it does (a preview undone, a setting announced) may draw again, and must not leave again.
  const was = page, leave = page.leave; page.leave = null; page.update = null;
  if (leave) leave();
  if (page !== was) return;  // leaving drew the new page already
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
  drawTabs();
  drawStatus();
  drawAlerts();
  drawStateCounts();
  drawPhoneBar();
  titleNow();
  revealRow();
  if (!hub.ready) return;
  const r = route();
  if (r.name === "new") return show("new", pageNew);
  if (r.name === "catcher") return show("catcher", pageCatcher);
  if (r.name === "settings") return show("settings", pageSettings);
  if (r.name === "artifacts") return show(`artifacts:s:${r.sid}`, () => pageArtifacts({ sid: r.sid }, r.pick));
  if (r.name === "browser" || r.name === "preview") return show(`${r.name}:${r.sid}:${r.url}`, () => window.hubBrowser.page(r));
  if (r.name === "session") {
    const key = `s:${layoutText(r.layout)}`;
    if (page.key !== key && r.ids.every((id) => !session(id))) return show(`missing:${key}`, () => {
      setTop([tail("Not found")]);
      view.append(h("div", { class: "page narrow" }, h("div", { class: "empty-line retry-line" }, h("span", { textContent: "That session no longer exists." }), h("a", { class: "retry", href: "#/", textContent: "Go home" }))));
    });
    if (page.key !== key && page.key.startsWith("s:") && page.retarget) { page.key = key; page.retarget(r.layout); return; }
    return show(key, () => pageSession(r.layout));
  }
  // #/p/@hub was the hub-wide sessions' own page; with a home project it is that project's Overview, and only
  // #/p/@hub/new (the page that starts one) stays.
  if (r.name === "project" && r.project === HUB && hubHome() && r.tab !== "new") return location.replace(`#/p/${P(hubHome().name)}`);
  if (r.name === "project" && r.project === HUB) return show(`newsession:${HUB}:${r.tab === "new" ? r.rest : ""}`, () => pageNewSession(HUB, r.tab === "new" ? r.rest : ""));
  if (r.name === "project" && project(r.project)) {
    if (r.tab === "new") return show(`newsession:${r.project}:${r.rest}`, () => pageNewSession(r.project, r.rest));
    if (r.tab === "memory") {
      const key = `memory:${r.project}:${r.rest}`;
      if (page.key !== key && page.retarget && page.key.startsWith(`memory:${r.project}:`)) { page.key = key; page.retarget(r.rest); return; }
      return show(key, () => pageMemory(r.project, r.rest));
    }
    if (r.tab === "dreams") return show(`dreams:${r.project}:${r.rest}`, () => pageDreams(r.project, r.rest));
    if (r.tab === "artifacts" && feature("artifacts")) return show(`artifacts:p:${r.project}`, () => pageArtifacts({ project: r.project }, r.rest));
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
const settle = guard(async () => { carryNames(); carryReads(); readWatched(); noticeNeeds(); noticeChanges(); noticeClosed(); noticeCatcher(); noticeTriggers(); render(); refreshTips(); });
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
  say(down ? "Context Hub isn't answering. Retrying every 3 seconds." : "Connected");
  if (!hub.ready) fill(view);
  drawSide();
};
const tick = async () => {
  let state;
  try { state = await api("/api/state"); } catch { setDown(true); return; }
  await takeState(state);
};
// One way in for a fresh state, whether a poll fetched it or the server pushed it. A poll that set out before a push
// landed can arrive after it: the older state is dropped, so nothing steps back.
const takeState = async (state) => {
  if (state.at && S.at && state.at < S.at && state.version === S.version) return;
  if (!state.reads && S.reads) state.reads = S.reads;  // read marks this answer doesn't carry stay as they were, so nothing blinks unread
  S = state;
  applyAsks(S.sessions);
  hub.ready = true;
  setDown(false);
  // A page loaded from an earlier build of the hub shows things the new one no longer accepts: say so, once, and offer to reload.
  if (!hub.version) hub.version = state.version;
  else if (state.version && state.version !== hub.version && !hub.stale) { hub.stale = true; staleBanner.hidden = false; say("Context Hub was updated. Reload to use the new version."); }
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
  const p = ownerOf(s);
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
        s.kind === "claude" ? [h("span", { textContent: s.project === HUB ? "No prompts" : modeName(s.mode) }), h("span", { textContent: modelName(s.model) }), s.code ? h("span", { textContent: "Code Mode" }) : null] : s.title === "Terminal" ? null : h("span", { textContent: "Terminal" }),
        s.isolate ? h("span", { title: s.tree ? treeTip(s.tree) : "Has its own worktree", class: "tree" }, svg(UI.branch)) : null,
        h("time", { textContent: ago(s.created) })),
      h("span"),
      s.agents && s.agents.doing && s.agents.doing.length ? h("span", { class: "strip-crew" }, s.agents.doing.map((what) => h("div", {}, h("i"), what))) : null),
    s.phone ? h("button", { class: "icon strip-phone", title: "Open on phone", "data-key": `phone:${s.id}`, onclick: () => openExternal(s.phone) }, uiIcon("phone")) : null);
};
// The home project's panel of hub-wide sessions (README, "Hub sessions"): the ones running (those asking you are in Needs
// you above it), the ended ones folded, and the way to start one, beside the project's own composer.
const hubPanel = (list, endedOpen, toggle) => {
  const live = list.filter((s) => !gone(s)).sort((a, b) => b.created - a.created);
  const ended = list.filter(gone).sort((a, b) => (b.closedAt || b.created) - (a.closedAt || a.created));
  const working = live.filter((s) => s.state === "working").length;
  const endedWord = ended.every((s) => s.state === "ended") ? "ended" : "closed";
  return h("section", { class: "panel board hub-panel", "aria-labelledby": "hub-panel-t" },
    h("header", {}, h("h2", { id: "hub-panel-t" }, h("span", { class: "hub-mark", "aria-hidden": "true" }, uiIcon("hub")), "Hub-wide sessions", working ? h("span", { class: "h-n", textContent: `${working} working` }) : null),
      h("button", { class: "btn", type: "button", "data-key": "hub-new", title: "Model and effort only: no mode, no worktree", onclick: () => newSession(HUB) }, uiIcon("plus"), h("span", { textContent: "New hub-wide session" }))),
    h("p", { class: "hub-note", textContent: "They belong to no project: each works on every project's memory from your home folder, with no permission prompts." }),
    live.map((s) => strip(s)),
    ended.length ? h("button", { class: "disclose", "aria-expanded": endedOpen ? "true" : "false", onclick: toggle }, h("span", { class: `chev ${endedOpen ? "open" : ""}` }, svg(UI.chev)), `${ended.length} ${endedWord}`) : null,
    endedOpen ? ended.map((s) => strip(s)) : null);
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
// The orb where it is ready, the old dot until the module has loaded; pages redraw once it has.
let orbsReady = !!window.hubOrb;
window.addEventListener("hub-orbs-ready", () => { orbsReady = true; if (page.update) page.update(); });
const rowOrb = (state, size = 14) => h("span", { class: `row-orb s-${state}`, role: "img", "aria-label": DOT_WORDS[state] || state },
  window.hubOrb ? window.hubOrb(state, { size, label: false }) : dot(state));
const ROW_ORB = 16;  // the queue's two-line rows
// A finished turn or a closed session is read once you open it, on any device: the marks are kept on the server
// (POST /api/reads, `reads` in /api/state), so reading on the phone clears the desk. What it said is part of the mark,
// so the next turn that finishes is unread again. A mark made here counts at once, before the server has answered.
const READ_KEY = "hub.read";  // where this browser kept its marks before they moved to the server
const DONE_FOR = 86400;  // a closed session stays in Done for a day
const isDone = (s) => s.state === "finished" || (s.state === "closed" && !!s.closedAt && Date.now() / 1000 - s.closedAt < DONE_FOR);
const readMark = (s) => `${s.state === "needs" && s.asks ? "finished" : s.state}:${s.said || s.note || ""}`.slice(0, 200);
const readsMine = new Map();  // id -> the mark (or null for unread) this page set and the server hasn't shown back yet
const readsNow = () => S.reads || {};
const isRead = (s) => (readsMine.has(s.id) ? readsMine.get(s.id) : readsNow()[s.id]) === readMark(s);
const sendReads = (marks) => api("/api/reads", { marks }).then((answer) => {
  if (answer && answer.reads) S.reads = answer.reads;
  Object.entries(marks).forEach(([id, mark]) => { if (readsMine.get(id) === mark) readsMine.delete(id); });
}, () => { /* kept here; the next mark tries again */ });
const setRead = (ids, on) => {
  const marks = {};
  ids.forEach((id) => { const s = session(id); const mark = s && on ? readMark(s) : null; if (isRead(s || { id }) === on && s) return; marks[id] = mark; readsMine.set(id, mark); });
  if (!Object.keys(marks).length) return;
  sendReads({ ...Object.fromEntries(readsMine), ...marks });
  sideKey = "";  // the sidebar's marks and order change with what is read
};
// Marks this browser kept before move to the server once, where the server has none for that session.
const carryReads = () => {
  const old = saved.get(READ_KEY, null);
  if (!old || !hub.ready) return;
  const marks = {};
  Object.entries(old).forEach(([id, mark]) => { if (session(id) && typeof mark === "string" && !(id in readsNow())) marks[id] = mark; });
  try { localStorage.removeItem(READ_KEY); } catch { /* nothing kept */ }
  if (Object.keys(marks).length) sendReads(marks);
};
const sessionIds = (url) => { const m = (url || "").match(/#\/s\/([^/?~]+)/); return m ? decodeURIComponent(m[1]).split(",") : []; };
// Opening a session reads it; so does leaving it, for a turn that finished while you watched.
window.addEventListener("hashchange", (e) => {
  const ids = [...sessionIds(e.oldURL), ...sessionIds(e.newURL)].filter((id) => { const s = session(id); return s && isDone(s); });
  if (ids.length) setRead(ids, true);
});
// ── Attention: what each session asks of you, in one word, and the order that puts what needs you first ──
// needs: it waits on you (or stopped with an error). done: a turn finished and you haven't read it. working. idle: the
// rest that is still open. A turn that ends on a question is done, and says it asks you, unless asks_as_needs is on.
const asksYou = (s) => !!s.asks && (s.state === "finished" || s.state === "needs");
const attentionKind = (s) => {
  if (!s || gone(s)) return null;
  if (asksYou(s)) return pref("asks_as_needs", false) ? "needs" : isRead(s) ? "idle" : "done";
  if (s.state === "needs" || s.state === "error") return "needs";
  if (s.state === "finished") return isRead(s) ? "idle" : "done";
  if (s.state === "working" || s.state === "closing") return "working";
  return "idle";
};
const ATTENTION_BANDS = [["needs", "Needs you"], ["done", "Done"], ["working", "Working"], ["idle", "Idle"]];
const ATTENTION_RANK = { needs: 0, done: 1, working: 2, idle: 3 };
// When each session came into the band it is in. A first sight takes the last time its hooks spoke; after that the
// time this page saw it change, so a working row keeps its place while its tools come and go.
const attentionSince = new Map();
const sinceOf = (s, kind) => {
  const was = attentionSince.get(s.id);
  if (was && was.kind === kind) return was.at;
  const at = was ? Date.now() / 1000 : s.changedAt || (s.turn && s.turn.since) || (s.activity && s.activity.since) || s.closedAt || s.created || 0;
  attentionSince.set(s.id, { kind, at });
  return at;
};
// Every open session, needs first, then done and unread, then working, then idle; inside each, the newest change first.
// The one ordering for the sidebar, the rail and anything that walks to "the next one that needs you".
function attentionOrder(sessions = S.sessions) {
  return sessions.map((s) => ({ s, kind: attentionKind(s) })).filter((x) => x.kind)
    .map((x) => ({ ...x, at: sinceOf(x.s, x.kind) }))
    .sort((a, b) => ATTENTION_RANK[a.kind] - ATTENTION_RANK[b.kind] || b.at - a.at)
    .map((x) => x.s);
}
const attentionCounts = (sessions = S.sessions) => {
  const counts = { needs: 0, done: 0, working: 0, idle: 0 };
  sessions.forEach((s) => { const kind = attentionKind(s); if (kind) counts[kind]++; });
  return counts;
};
// What a group of sessions shows as one mark: needs, then done and unread, then working.
const rollupOf = (sessions) => { const kinds = new Set(sessions.map(attentionKind)); return ["needs", "done", "working"].find((k) => kinds.has(k)) || null; };
const ROLLUP_ORB = { needs: "needs", done: "finished", working: "working" };
const stillMotion = () => { const want = pref("reduce_motion", "system"); return want === "on" || (want !== "off" && reduced()); };

// A setting changed from here rather than the Settings page (the sidebar's order, a muted project). The settings store
// keeps it for every device (PUT /api/settings, one name at a time); this browser remembers it too, so a toggle works
// before that store answers, or where there is none.
const saveSetting = (name, value) => {
  SETTINGS = { ...SETTINGS, [name]: value };
  saved.set(`hub.setting.${name}`, value);
  window.dispatchEvent(new Event("hub:settings"));
  const body = JSON.stringify({ [name]: value });
  const save = typeof saveSettings === "function" ? saveSettings({ [name]: value })
    : fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body });
  Promise.resolve(save).catch(() => { /* kept in this browser */ });
};
const localSetting = (name, fallback) => saved.get(`hub.setting.${name}`, fallback);
const sideOrder = () => pref("sidebar_order", localSetting("sidebar_order", "project")) === "attention" ? "attention" : "project";
const mutedProjects = () => { const list = pref("muted_projects", localSetting("muted_projects", [])); return Array.isArray(list) ? list : []; };
const isMuted = (name) => mutedProjects().includes(name);
const toggleMute = (p) => {
  const on = !isMuted(p.name);
  saveSetting("muted_projects", on ? [...mutedProjects(), p.name] : mutedProjects().filter((n) => n !== p.name));
  toast(on ? `No notices or sounds from ${p.display}` : `Notices from ${p.display} are back on`);
};
const ORDER_ICON = '<path d="M2.5 4h11M2.5 8h7.5M2.5 12h4"/>';
const sideOrderToggle = () => {
  const by = sideOrder() === "attention";
  return h("button", { class: "icon side-order", type: "button", "aria-pressed": by ? "true" : "false", "data-key": "side-order",
    title: by ? "Sorted by what needs you. Sort by project" : "Sort by what needs you", "aria-label": "Sort by what needs you",
    onclick: () => { saveSetting("sidebar_order", by ? "project" : "attention"); sideKey = ""; drawSide(); const again = sideList.querySelector('[data-key="side-order"]'); if (again) again.focus({ preventScroll: true }); } }, svg(ORDER_ICON));
};

// ── The sidebar between rebuilds ──
// A rebuild happens when what is listed or its order changes. A poll that only changed what sessions are doing, or
// which are read, updates those rows where they are: no flicker, and hover, focus and scroll stay put.
const linesSig = (s, withProject) => JSON.stringify([bareTitle(s), !!hubwideTag(s), gone(s) ? "" : rowLine(s), turnSince(s), shownState(s), asksYou(s), withProject ? (ownerOf(s) || {}).display || s.project : ""]);
const sideLines = (s, withProject) => {
  const line = gone(s) ? "" : rowLine(s), from = turnSince(s), p = withProject ? ownerOf(s) : null;
  const label = h("span", { class: "label", dir: "auto", textContent: bareTitle(s) });
  // Sorted by attention, a row says whose it is after its name, so the line under it keeps its room for what it does.
  const tag = hubwideTag(s);
  const lines = h("span", { class: "lines" }, withProject ? h("span", { class: "head" }, tag, label, h("span", { class: "proj", dir: "auto", textContent: p ? p.display : s.project })) : tag ? h("span", { class: "head" }, tag, label) : label,
    line || from ? h("span", { class: `sub st-${shownState(s)}` }, asksYou(s) ? asksTag() : null, h("span", { class: "what", dir: "auto", textContent: line }), from ? ticking(from) : null) : null);
  lines.dataset.sig = linesSig(s, withProject);
  return lines;
};
const railLabel = (s) => { const line = rowLine(s); return `${s.title}, ${DOT_WORDS[shownState(s)] || s.state}${line ? `: ${line}` : ""}`; };
const sideNow = () => JSON.stringify([S.sessions.map((s) => [s.id, orbState(s), rowLine(s), turnSince(s), shownState(s), attentionKind(s), s.asks, s.why]), attention(), homeNeeds(), S.projects.map((p) => attention(p.name))]);
const patchSide = () => {
  const withProject = sideList.classList.contains("by-attention");
  sideList.querySelectorAll(".side-row[data-sid]").forEach((row) => {
    const s = session(row.dataset.sid), nav = row.querySelector(":scope > .nav");
    if (!s || !nav) return;
    const tip = rowTip(s);
    if (row.title !== tip) row.title = tip;
    const holder = nav.querySelector(":scope > .slot"), orb = orbOf(`s:${s.id}`, orbState(s));
    if (holder && holder.firstChild !== orb) holder.replaceChildren(orb);
    const kind = attentionKind(s);
    row.classList.toggle("done-unread", kind === "done");
    row.classList.toggle("done-read", s.state === "finished" && kind !== "done" && kind !== "needs");
    const lines = nav.querySelector(":scope > .lines");
    if (lines && lines.dataset.sig !== linesSig(s, withProject)) {
      const next = sideLines(s, withProject);
      lines.replaceWith(next);
      row.classList.toggle("two", !!next.querySelector(".sub"));
    }
    if (nav.classList.contains("rail-item")) { const label = railLabel(s); if (nav.title !== label) { nav.title = label; nav.setAttribute("aria-label", label); } }
  });
  sideList.querySelectorAll(".side-group[data-project]").forEach((group) => {
    const p = project(group.dataset.project), spot = group.querySelector(":scope > .side-row.project .state");
    if (!p || !spot) return;
    const want = projectOrb(p, sessionsOf(p.name));
    if (want ? spot.firstChild !== want || spot.childNodes.length !== 1 : spot.firstChild) spot.replaceChildren(...(want ? [want] : []));
  });
  // A shut folder shows what its projects roll up to; an open one, how many it holds.
  sideList.querySelectorAll(".side-folder[data-folder]").forEach((folder) => {
    const nav = folder.querySelector(":scope > .folder-row > .folder-nav"), end = nav && nav.lastElementChild;
    if (!end) return;
    const inside = sideProjects().filter((p) => groupOf(p.name) === folder.dataset.folder);
    const kind = inside.some((p) => attention(p.name)) ? "needs" : rollupOf(S.sessions.filter((s) => inside.some((p) => p.name === ownerName(s))));
    const want = !folder.classList.contains("open") && kind ? `orb:${kind}` : `n:${inside.length}`;
    if (end.dataset.shows === want) return;
    const next = want.startsWith("orb:") ? h("span", { class: "state" }, rowOrb(ROLLUP_ORB[kind])) : h("span", { class: "fold-n", textContent: inside.length });
    next.dataset.shows = want;
    end.replaceWith(next);
  });
  const home = sideList.querySelector('.nav[data-key="home"]:not(.rail-item)');
  if (home) {
    const count = homeNeeds(), had = home.querySelector(":scope > .count");
    if (!count && had) had.remove();
    else if (count && had) { if (had.textContent !== String(count)) had.textContent = count; }
    else if (count) home.append(h("span", { class: "count", textContent: count }));
  }
  pruneOrbs();
};
// Rows that move glide to their new place (each from where it was), and a new row fades in. Reduced motion: they jump.
const rowsAt = () => new Map([...sideList.querySelectorAll(".side-row[data-sid]")].map((row) => [row.dataset.sid, row.getBoundingClientRect().top]));
const moveRows = (before) => {
  if (!before.size || stillMotion() || !Element.prototype.animate) return;
  sideList.querySelectorAll(".side-row[data-sid]").forEach((row) => {
    const was = before.get(row.dataset.sid);
    if (was === undefined) { row.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: "ease-out" }); return; }
    const by = was - row.getBoundingClientRect().top;
    if (Math.abs(by) > 1) row.animate([{ transform: `translateY(${by}px)` }, { transform: "none" }], { duration: 240, easing: "cubic-bezier(.23, 1, .32, 1)" });
  });
};
// The sidebar sorted by what needs you: one list in bands, each row with its project, and the projects under it.
function drawByAttention(r) {
  const order = attentionOrder().filter((s) => !isHiddenProject(ownerName(s)));
  const row = (s) => {
    if (sideEdit.id === s.id) return renameRow(s);
    const shown = r.name === "session" && r.ids.includes(s.id);
    const addable = r.name === "session" && s.alive && !shown;
    const beside = () => { closeSide(); if (r.ids.length < MAX_PANES) goLayout(layoutAdd(r.layout, s.id)); else toast("Close a pane first"); };
    return h("div", { class: `side-row ${shown ? "on" : ""}`, title: rowTip(s), "data-sid": s.id },
      h("a", { class: "nav session", href: `#/s/${s.id}`, "aria-current": shown ? "page" : undefined, "data-key": `s:${s.id}`, "data-drag-sid": s.id,
        oncontextmenu: (e) => { e.preventDefault(); sessionMenu(e.currentTarget, s); },
        onclick: (e) => { if ((e.metaKey || e.ctrlKey || e.shiftKey) && addable) { e.preventDefault(); beside(); } else if (shown && r.ids.length > 1 && !e.metaKey && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); closeSide(); pageKeys.jump(r.ids.indexOf(s.id)); } else closeSide(); } },
        slot(orbOf(`s:${s.id}`, orbState(s))), sideLines(s, true)),
      addable && r.ids.length < MAX_PANES ? h("button", { class: "hover-add", title: `Open ${s.title} beside`, "data-key": `beside:${s.id}`, onclick: beside }, uiIcon("split")) : null,
      h("button", { class: "hover-add more", title: `Actions for ${s.title}`, "aria-haspopup": "menu", "data-key": `more:${s.id}`, onclick: (e) => sessionMenu(e.currentTarget, s) }, uiIcon("dots")));
  };
  const projectRow = (p) => {
    const on = r.name === "project" && r.project === p.name && r.tab === "home";
    const menu = (anchor) => projectMenu(anchor, p);
    return h("div", { class: `side-group ${p.hub ? "hub-group" : ""}`, "data-project": p.name },
      h("div", { class: `side-row project ${on ? "on" : ""}` },
        h("a", { class: "nav", href: `#/p/${P(p.name)}`, onclick: closeSide, "aria-current": on ? "page" : undefined, "data-key": `p:${p.name}`, oncontextmenu: p.hub ? undefined : (e) => { e.preventDefault(); menu(e.currentTarget); } },
          slot(p.hub ? uiIcon("hub") : mark(p, 15)), h("span", { class: "label", dir: "auto", textContent: p.display }), h("span", { class: "state" }, projectOrb(p, sessionsOf(p.name)))),
        p.hub ? null : h("button", { class: "hover-add more", title: `Actions for ${p.display}`, "aria-haspopup": "menu", "data-key": `pmore:${p.name}`, onclick: (e) => menu(e.currentTarget) }, uiIcon("dots")),
        h("button", { class: "hover-add", title: p.hub ? "New hub session: every project's memory, no permission prompts" : `New session in ${p.display}`, "data-key": `new:${p.name}`, onclick: () => newSession(p.name) }, uiIcon("plus"))));
  };
  const bands = ATTENTION_BANDS.map(([kind, word]) => [kind, word, order.filter((s) => attentionKind(s) === kind)]).filter(([, , list]) => list.length);
  fill(sideList,
    h("div", { class: "brand" }, slot(h("i")), h("span", { class: "label", textContent: "Context Hub" })),
    sidePlaces(r),
    sideSection("Sessions", {}, sideOrderToggle()),
    bands.length ? bands.map(([kind, word, list]) => h("section", { class: `side-band band-${kind}`, "aria-label": `${word}, ${list.length}` },
      h("div", { class: "side-title band-title", "aria-hidden": "true" }, h("span", { textContent: word }), h("span", { class: "fold-n", textContent: list.length })), list.map(row)))
      : hub.ready ? h("div", { class: "side-none", textContent: "No sessions open" }) : null,
    sideSection("Projects", {}, newProjectAct()),
    [...hubRow(), ...groups().flatMap((f) => sideProjects().filter((p) => groupOf(p.name) === f.id)), ...sideProjects().filter((p) => !groupOf(p.name))].map(projectRow),
    hiddenProjectsRow(r, projectRow),
    hub.ready && !S.projects.length ? h("div", { class: "side-none", textContent: "No projects yet" }) : null);
  drawSideFoot(r);
}
window.addEventListener("hub:settings", () => { sideKey = ""; alerts.key = ""; if (hub.ready) render(); });

// A finished turn you are looking at is read: the session is on screen and the page is in front of you.
const readWatched = () => {
  const r = route();
  if (r.name !== "session" || document.visibilityState !== "visible" || (!phone.matches && !document.hasFocus())) return;
  const ids = r.ids.filter((id) => { const s = session(id); return s && isDone(s) && !isRead(s); });
  if (ids.length) setRead(ids, true);
};
document.addEventListener("visibilitychange", () => { if (hub.ready) { readWatched(); render(); } });
window.addEventListener("focus", () => { if (hub.ready) { readWatched(); render(); } });

// ── Notices: a card in the hub (a banner), or the browser's own notification when the hub isn't in front ──
// Needs you and finished each have a setting: system, banner or off. A state is told only once it has held for two
// polls, so a permission auto mode approves at once never rings. A newer notice replaces the same session's older
// one. Nothing is told for the session you are looking at, or for a muted project.
const noticeBox = h("div", { id: "notices", "aria-live": "polite" });
document.body.append(noticeBox);
const NOTICE_MS = { needs: 8000, done: 5000, closed: 8000, catcher: 6000 };
const dropNotice = (card) => { if (!card.isConnected) return; card.classList.add("leaving"); setTimeout(() => card.remove(), stillMotion() ? 0 : 160); };
const showNotice = ({ key, kind, orb, icon, title, line, open }) => {
  const old = noticeBox.querySelector(`[data-notice="${CSS.escape(key)}"]`);
  const card = h("div", { class: `notice n-${kind}`, "data-notice": key, "data-kind": kind, "data-left": noticeLeft(kind, NOTICE_MS[kind] || 6000) },
    h("button", { class: "notice-open", type: "button", "data-key": `notice:${key}`, onclick: () => { dropNotice(card); if (open) open(); } },
      slot(orb ? rowOrb(orb) : icon ? uiIcon(icon) : null),
      h("span", { class: "alert-text" }, h("b", { dir: "auto", textContent: title }), line ? h("small", { dir: "auto", textContent: line }) : null)),
    h("button", { class: "icon", type: "button", title: "Dismiss", "aria-label": "Dismiss", onclick: () => dropNotice(card) }, uiIcon("close")));
  if (old) old.replaceWith(card); else noticeBox.prepend(card);
  if (!old && !stillMotion() && card.animate) card.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: 200, easing: "cubic-bezier(.23, 1, .32, 1)" });
  [...noticeBox.querySelectorAll(".notice")].slice(3).forEach((extra) => extra.remove());
};
// A notice waits while the hub is out of sight, and while you point at it or it holds focus.
setInterval(() => {
  if (document.visibilityState !== "visible") return;
  [...noticeBox.querySelectorAll(".notice")].forEach((card) => {
    if (card.matches(":hover, :focus-within") || card.classList.contains("leaving")) return;
    const left = Number(card.dataset.left) - 500;
    card.dataset.left = left;
    if (left <= 0) dropNotice(card);
  });
}, 500);
const dropNoticeOf = (key) => { const card = noticeBox.querySelector(`[data-notice="${CSS.escape(key)}"]`); if (card) dropNotice(card); };
const hubAway = () => document.visibilityState !== "visible" || !document.hasFocus();
// How a notice is told: "system" is the browser's notification while the hub isn't in front, and a banner while it is;
// "banner" is only ever the banner. Returns where it went.
const tell = (mode, { native, banner, inFront = true }) => {
  if (mode === "off") return null;
  logNotice(banner);
  if (mode === "system" && hubAway() && notifyState() === "on") {
    const note = postNotification(native.title, { body: native.body, tag: native.tag });
    if (note) { note.onclick = () => { note.close(); window.focus(); if (native.open) native.open(); }; return note; }
  }
  if (mode === "banner" || inFront) showNotice(banner);
  return null;
};
const notices = { poll: null, ready: false, held: new Map(), said: new Map(), native: new Map(), blockedSaid: false };
const noticeKind = (s) => { const kind = attentionKind(s); return kind === "needs" && s.state !== "error" ? "needs" : kind === "done" ? "done" : null; };
const noticeMark = (s, kind) => `${kind}|${kind === "needs" ? oneLine(s.asking) : readMark(s)}`;
const noticeChanges = () => {
  if (!hub.ready || S.at === notices.poll) return;  // once per poll, however often the page settles
  notices.poll = S.at;
  // A done notice goes once the turn is read or a new one starts; a needs notice, once the wait ends (noticeNeeds).
  notices.native.forEach((note, id) => { const s = session(id); if (!s || noticeKind(s) !== "done") { note.close(); notices.native.delete(id); } });
  [...noticeBox.querySelectorAll('[data-notice^="s:"]')].forEach((card) => { const s = session(card.dataset.notice.slice(2)); if (!s || noticeKind(s) !== card.dataset.kind) dropNotice(card); });
  S.sessions.forEach((s) => {
    const kind = noticeKind(s);
    if (!kind) {
      notices.held.delete(s.id);
      if (attentionKind(s) !== "idle") notices.said.delete(s.id);  // a new turn may be told again; reading one may not
      return;
    }
    const mark = noticeMark(s, kind);
    if (!notices.ready) { notices.said.set(s.id, mark); return; }  // what was so when the page opened isn't news
    if (notices.said.get(s.id) === mark) return;
    const held = notices.held.get(s.id);
    if (!held || held !== mark) { notices.held.set(s.id, mark); return; }
    notices.held.delete(s.id);
    notices.said.set(s.id, mark);
    if (isMuted(ownerName(s)) || watching(s.id)) return;
    deliver(s, kind);
  });
  [...notices.said.keys()].forEach((id) => { if (!session(id)) { notices.said.delete(id); notices.held.delete(id); } });
  notices.ready = true;
};
const deliver = (s, kind) => {
  const where = (ownerOf(s) || {}).display || s.project;
  const sound = pref(kind === "needs" ? "sound_needs" : "sound_done", "off");
  if (sound !== "off") playSound(sound);
  const open = () => openWaiting(s.id);
  const line = kind === "needs" ? oneLine(s.asking) || `Needs your input in ${where}` : asksYou(s) ? `Asks you: ${oneLine(s.asking || s.said)}` : oneLine(s.said) || `Finished in ${where}`;
  const mode = pref(kind === "needs" ? "notify_needs" : "notify_done", kind === "needs" ? "system" : "off");
  // In front, a session that needs you already has its card in the sidebar or the bar; the banner is for "banner".
  const note = tell(mode, { native: { title: s.title, body: line, tag: `hub-${s.id}`, open }, inFront: kind === "done",
    banner: { key: `s:${s.id}`, kind, orb: kind === "needs" ? "needs" : "finished", title: bareTitle(s), line: `${where} · ${line}`, open } });
  if (note) (kind === "needs" ? alerts.native : notices.native).set(s.id, note);
};

// ── Sounds: three short tones made here with Web Audio, no files. Off unless chosen. ──
// A browser lets a page play sound only after a click or a key on it, so the first one unlocks the hub's audio.
const SOUNDS = {
  chime: [{ f: 784, dur: .5, gain: .5 }, { f: 1175, at: .12, dur: .8, gain: .42 }],  // a rising fifth
  knock: [{ f: 190, to: 80, dur: .13, type: "triangle", gain: 1, attack: .002 }, { f: 190, to: 80, at: .17, dur: .13, type: "triangle", gain: .8, attack: .002 }],
  bell: [{ f: 523.25, dur: 1.8, gain: .5 }, { f: 1046.5, dur: 1.1, gain: .16 }, { f: 1444, dur: .7, gain: .1 }, { f: 2093, dur: .4, gain: .05 }],
};
let audio = null;
const audioNow = () => {
  if (!audio) { const Ctx = window.AudioContext || window.webkitAudioContext; if (!Ctx) return null; try { audio = new Ctx(); } catch { return null; } }
  return audio;
};
const wantsSound = () => pref("sound_needs", "off") !== "off" || pref("sound_done", "off") !== "off";
const unlockAudio = () => { if (!wantsSound() && !audio) return; const a = audioNow(); if (a && a.state === "suspended") a.resume().catch(() => {}); };
["pointerdown", "keydown"].forEach((name) => window.addEventListener(name, unlockAudio, true));
const playSound = async (name, volume) => {
  const shape = SOUNDS[name], a = shape && audioNow();
  if (!a) return false;
  if (a.state !== "running") { try { await Promise.race([a.resume(), new Promise((done) => setTimeout(done, 300))]); } catch { /* still locked */ } }
  if (a.state !== "running") {
    if (!notices.blockedSaid) { notices.blockedSaid = true; showNotice({ key: "sound", kind: "done", icon: "bell", title: "Sounds are on", line: "Click anywhere in the hub once to let them play." }); }
    return false;
  }
  const level = Math.max(0, Math.min(1, Number(volume !== undefined ? volume : pref("sound_volume", 0.6)) || 0));
  const out = a.createGain();
  out.gain.value = level * 0.5;
  out.connect(a.destination);
  const start = a.currentTime + 0.02;
  shape.forEach(({ f, to, at = 0, dur, type = "sine", gain, attack = 0.008 }) => {
    const osc = a.createOscillator(), env = a.createGain(), t = start + at;
    osc.type = type;
    osc.frequency.setValueAtTime(f, t);
    if (to) osc.frequency.exponentialRampToValueAtTime(to, t + dur);
    env.gain.setValueAtTime(0.0001, t);
    env.gain.exponentialRampToValueAtTime(gain, t + attack);
    env.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(env).connect(out);
    osc.start(t);
    osc.stop(t + dur + 0.05);
  });
  return true;
};
// For the Settings page's Play buttons: hubPlaySound("chime"), with an optional volume from 0 to 1 (or { volume }).
window.hubPlaySound = (name, volume) => playSound(name, volume && typeof volume === "object" ? volume.volume : volume);
window.hubSounds = Object.keys(SOUNDS);

// ── The phone's counts: "2 need you · 3 done · 5 working", each opening that tab on Home ──
let homeTabWanted = null;
// On a phone's session page, where the chat owns the foot and the bottom bar steps aside, the menu button carries what
// needs you: a 6px mark (rose when a session needs you, the accent when one finished unread) and the counts in its
// name. The drawer it opens leads with Home and its count. It was a row of its own; folded here (polish-session), the
// session keeps two bars above it.
const menuCounts = () => {
  if (!(phone.matches && hub.ready && route().name === "session")) return null;
  const c = attentionCounts(), parts = [[c.needs, c.needs === 1 ? "needs you" : "need you"], [c.done, "done"], [c.working, "working"]].filter(([n]) => n);
  return { kind: c.needs ? "needs" : c.done ? "done" : "", label: ["Menu", ...parts.map(([n, word]) => `${n} ${word}`)].join(", ") };
};
const markMenu = (button) => {
  const m = menuCounts();
  button.setAttribute("aria-label", m ? m.label : "Menu");
  const had = button.querySelector(".menu-hot");
  if (!m || !m.kind) { if (had) had.remove(); return button; }
  if (had) had.className = `menu-hot c-${m.kind}`; else button.append(h("i", { class: `menu-hot c-${m.kind}`, "aria-hidden": "true" }));
  return button;
};
const drawStateCounts = () => { const button = top_.querySelector(".menu-btn"); if (button) markMenu(button); };
// ── The phone's bottom bar (feat/nav): the four places in thumb reach, on every page but a session's, whose foot is
// its chat. Home carries Home's own count; Projects opens the drawer's list; Go to; Settings. A field in use hides it,
// so the keyboard keeps the room. ──
const phoneBar = h("nav", { id: "phone-bar", "aria-label": "Places", hidden: true });
view.after(phoneBar);
const phoneBarShown = () => phone.matches && hub.ready && route().name !== "session";
const drawPhoneBar = () => {
  const show = phoneBarShown();
  document.body.classList.toggle("has-phone-bar", show);
  phoneBar.hidden = !show;
  if (!show) { drawn.delete(phoneBar); return; }
  const r = route(), n = homeNeeds();
  const at = r.name === "now" ? "home" : r.name === "settings" ? "settings" : r.name === "project" || r.name === "new" ? "projects" : "";
  if (!differs(phoneBar, at, n, sideOpen())) return;
  const slot_ = (key, word, icon, attrs, badge) => h(attrs.href ? "a" : "button", { ...attrs, type: attrs.href ? undefined : "button", class: `pb-item ${at === key ? "on" : ""}`, "data-key": `pb:${key}`, "aria-current": at === key ? "page" : undefined },
    h("span", { class: "pb-icon" }, uiIcon(icon), badge ? h("span", { class: "pb-badge", textContent: badge > 99 ? "99+" : String(badge) }) : null), h("span", { class: "pb-word", textContent: word }),
    badge ? h("span", { class: "sr-only", textContent: `, ${badge} ${badge === 1 ? "needs" : "need"} you` }) : null);
  fill(phoneBar,
    slot_("home", "Home", "home", { href: "#/" }, n),
    slot_("projects", "Projects", "folder", { "aria-haspopup": "true", "aria-expanded": sideOpen() ? "true" : "false", onclick: () => { setSide(!sideOpen()); drawPhoneBar(); } }),
    slot_("goto", "Go to", "find", { onclick: () => openPalette() }),
    slot_("settings", "Settings", "gear", { href: "#/settings" }));
};
document.addEventListener("focusin", (e) => { if (phone.matches && isTyping(e.target)) document.body.classList.add("typing"); });
document.addEventListener("focusout", () => setTimeout(() => { if (!isTyping(document.activeElement)) document.body.classList.remove("typing"); }));
// A field taken out of the page while it loses focus (a drawer rename that commits on blur) sends its focusout from
// outside the document, so the line above never hears it. The keyboard going away says the same.
if (window.visualViewport) visualViewport.addEventListener("resize", () => { if (!isTyping(document.activeElement)) document.body.classList.remove("typing"); });
phone.addEventListener("change", drawPhoneBar);
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
  const open = sessionsOf(p.name).filter((s) => s.alive).length;
  const asking = sessionsOf(p.name).some((s) => s.state === "needs");
  const dreamsWait = (p.needs || 0) + (openReview(p) ? 1 : 0) + ((p.waits && p.waits.you) || 0);
  const tab = (key, word, href, count, hot) => h("a", { class: `ptab ${key === at ? "on" : ""}`, href, "aria-current": key === at ? "page" : undefined, "data-key": `tab:${key}` },
    h("span", { textContent: word }), count ? h("b", { class: hot ? "hot" : "", textContent: String(count) }) : null);
  return h("nav", { class: "ptabs", "aria-label": p.display },
    tab("home", "Overview", `#/p/${P(p.name)}`, open, asking),
    tab("memory", "Memory", `#/p/${P(p.name)}/memory`, p.lessons),
    tab("dreams", "Dreams", `#/p/${P(p.name)}/dreams`, dreamsWait, true),
    feature("artifacts") ? tab("artifacts", "Artifacts", `#/p/${P(p.name)}/artifacts`) : null);
};
const tabsKey = (p) => [feature("artifacts"), p.display, p.icon, iconStamp, p.lessons, p.needs, openReview(p), p.waits, sessionsOf(p.name).map((s) => [s.alive, s.state])];
// The top bar of a project's pages: its mark and name, then the tabs. On a phone the name gives way to the tabs.
// Its ⋯ ends every one of them: the same menu as the project's row in the sidebar, Project settings among it.
const projectTop = (p, at, actions) => setTop([
  at === "home" ? h("h1", { class: "tail marked" }, mark(p, 20), h("span", { class: "t", dir: "auto", textContent: p.display }))
    : [h("a", { class: "crumb-home", href: `#/p/${P(p.name)}`, title: p.display }, mark(p, 20), h("span", { class: "t", dir: "auto", textContent: p.display })), quietTail(at === "memory" ? "Memory" : at === "artifacts" ? "Artifacts" : "Dreams")],
  projectTabs(p, at)], [...actions, moreButton(`Actions for ${p.display}`, (anchor) => projectMenu(anchor, p), "project-more")], true);

// ── Dream questions (feat/polish-pages): one wording and one row for what dreams leave you, wherever it shows ──
// A dream question is something a dream wrote down that a person has to decide. Home shows each project's first one,
// a project's Overview its first few, Dreams every one with its choices, and the Dream Catcher every project's with its
// verdicts. Each is the same row as Home's queue: a mark, the question, and a line that says what it is and whose.
const questionsWord = (n) => `${n} dream ${n === 1 ? "question" : "questions"}`;
const changesWord = (n) => `${n} memory ${n === 1 ? "change" : "changes"}`;
const askRow = ({ nav, href, state = "needs", title, line, lineCls = "", p, extra, meta, acts, closed, cls = "", tag = "span" }) => h("div", { class: `qrow ask-row ${cls} ${closed ? "closed" : ""}`, "data-nav": nav,
  onclick: href ? (e) => { if (!e.target.closest("a, button, input, details")) go(href); } : undefined },
  rowOrb(closed ? "ended" : state, ROW_ORB),
  h("span", { class: "q-main" }, href ? h("a", { class: "q-t", href, dir: "auto", textContent: title }) : h(tag === "p" ? "p" : "span", { class: "q-t", dir: "auto", textContent: title }),
    line ? h(lineCls ? "div" : "span", { class: `q-line ${lineCls}`, dir: "auto", title: typeof line === "string" ? line : undefined }, p ? [mark(p, 12), " "] : null, line) : null, extra || null),
  meta || acts ? h("span", { class: "q-meta" }, meta || null, acts || null) : null);
// What a project's dreams leave for you, as rows: a proposal to review, its questions, and approved changes only you
// apply. Outside the project each row names it, and only its first question shows, with how many more.
const dreamRows = (p, inProject) => {
  const href = `#/p/${P(p.name)}/dreams`, whose = (word) => inProject ? word : `${p.display} · ${word}`, rows = [];
  if (openReview(p)) rows.push({ nav: `r:${p.name}`, href, title: `Review ${changesWord(p.latest.changes)}`, line: whose("Dream proposal"), lineP: inProject ? null : p, at: p.latest.written });
  if (p.needs) {
    const asks = (p.asks || []).slice(0, inProject ? 3 : 1);
    if (!asks.length) rows.push({ nav: `n:${p.name}`, href, title: questionsWord(p.needs), line: whose("Open Dreams to answer"), lineP: inProject ? null : p });
    asks.forEach((a, i) => rows.push({ nav: i ? `n:${p.name}:${i}` : `n:${p.name}`, href, title: a.text, lineP: inProject ? null : p, at: a.at,
      line: whose(["Dream question", a.state === "stopped" ? "the fixer stopped" : null, !inProject && p.needs > 1 ? `${p.needs - 1} more` : null].filter(Boolean).join(" · ")) }));
    if (inProject && p.needs > asks.length) rows.push({ nav: `n:${p.name}:more`, href, title: `${p.needs - asks.length} more in Dreams`, line: "Dream questions", state: "needs" });
  }
  if (p.waits && p.waits.you) rows.push({ nav: `w:${p.name}`, href, title: `${p.waits.you} approved ${p.waits.you === 1 ? "change waits" : "changes wait"} for you`, line: whose("ORG.md or Steering, which only you apply"), lineP: inProject ? null : p });
  return rows;
};

function pageNow() {
  const TABS = [["needs", "Needs you"], ["working", "Working"], ["done", "Done"]];
  let chosen = homeTabWanted, shown = "needs", rows = { needs: [], working: [], done: [] }, everything = false;
  homeTabWanted = null;
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
    const fact = open ? `${open} open` : !p.schedule ? null  // setting up is said on the project's page, not on every card
      : p.schedule.hourly ? "Dreams when idle"
      : weekly(p.schedule) ? `Dreams ${WEEKDAYS[p.schedule.weekday % 7].slice(0, 3)} ${clockHour(p.schedule.hour)}` : `Dreams daily ${clockHour(p.schedule.hour)}`;
    const state = attention(p.name) ? "needs" : sessionsOf(p.name).some((s) => s.state === "working") ? "working" : p.dreaming ? "dreaming" : null;
    return h("a", { class: "card", href: `#/p/${P(p.name)}`, "data-nav": `p:${p.name}` },
      h("div", { class: "card-top" }, mark(p, 30), h("div", { class: "card-name" }, h("b", { dir: "auto", textContent: p.display }), repos.length ? h("span", { textContent: repos.join("  ") }) : null), state ? rowOrb(state) : null),
      h("div", { class: "card-line" }, h("span", { textContent: fact || "" }), h("span", { textContent: `${p.lessons} lessons` })));
  };
  // One row: what it is and the line under it, then whose and how long ago. Rows are links; Done rows also toggle read.
  const qRow = (row) => h("div", { class: `qrow ${row.read ? "read" : ""}`, "data-nav": row.nav, "data-drag-sid": row.sid && session(row.sid) ? row.sid : undefined, onclick: (e) => { if (!e.target.closest("a, button")) go(row.href); } },
    rowOrb(row.state, ROW_ORB),
    h("span", { class: "q-main" }, h("a", { class: "q-t", href: row.href, dir: "auto", textContent: row.title }), row.line ? h("span", { class: "q-line", dir: "auto", title: row.line }, row.lineP ? [mark(row.lineP, 12), " "] : null, row.asks ? asksTag() : null, row.line) : null),
    h("span", { class: "q-meta" }, row.p ? [mark(row.p, 15), h("span", { class: "q-p", dir: "auto", textContent: row.p.display })] : null, row.at ? h("time", { textContent: ago(row.at) }) : null),
    row.sid && shown === "done" ? h("button", { class: "q-act", type: "button", "data-key": `read:${row.sid}`, textContent: row.read ? "Mark unread" : "Mark read", onclick: () => toggleRead(row) }) : null);
  const queue = () => {
    const p = (name) => project(name);
    const countOf = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    rows.needs = [
      ...S.sessions.filter((s) => s.state === "needs" || s.state === "error").map((s) => ({ nav: s.id, sid: s.id, href: `#/s/${s.id}`, state: s.state, title: s.title, line: s.state === "error" ? s.error || "Stopped with an error" : oneLine(s.asking) || "Needs your input", p: ownerOf(s), at: s.activity && s.activity.since })),
      ...S.projects.flatMap((x) => dreamRows(x, false)).map((row) => ({ ...row, state: "needs" })),
    ];
    rows.working = [
      ...S.sessions.filter((s) => s.state === "working" || s.state === "closing").sort((a, b) => b.created - a.created).map((s) => ({ nav: s.id, sid: s.id, href: `#/s/${s.id}`, state: orbState(s), title: s.title,
        line: s.state === "closing" ? "Tidying up and writing a handoff" : s.activity ? `${s.activity.tool} ${s.activity.target || ""}`.trim() : s.now || "Working", p: ownerOf(s), at: (s.turn && s.turn.since) || s.created })),
      ...S.projects.filter((x) => x.dreaming).map((x) => ({ nav: `d:${x.name}`, href: `#/p/${P(x.name)}/dreams`, state: "working", title: "Dreaming", line: x.batch ? `Reading ${countOf(x.batch, "session", "sessions")}` : null, p: x })),
    ];
    rows.done = S.sessions.filter(isDone).map((s) => ({ nav: s.id, sid: s.id, href: `#/s/${s.id}`, state: orbState(s) === "asks" ? "asks" : s.state, title: s.title, line: s.state === "closed" ? noteLine(s.note) || "Closed" : asksYou(s) ? oneLine(s.asking) || s.said || "Done" : s.said || "Done", asks: asksYou(s), p: ownerOf(s), at: s.closedAt, read: isRead(s) }))
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
    if (differs(top_, "home", phone.matches)) dashTop([tail("Home")], [phone.matches ? h("button", { class: "icon", type: "button", "data-key": "home-new", title: "New session", "aria-label": "New session", onclick: () => newSession() }, uiIcon("plus"))
      : h("button", { class: "btn primary", "data-key": "home-new", textContent: "New session", onclick: () => newSession() }),
      moreButton("More on Home", (anchor) => popover(anchor, [{ name: "New project", icon: "plus", run: () => go("#/new") }, { name: "New folder…", icon: "folderPlus", run: () => newFolder() }]), "home-more")]);
    const key = JSON.stringify([S.projects, S.groups, S.boards, S.sessions.map((s) => [s.id, s.title, s.state, s.asking, s.error, s.now, s.said, s.note, s.closedAt, s.activity, s.turn, s.tally, s.alive, isDone(s) && isRead(s), s.asks, s.lost]), Math.floor(Date.now() / 60000), data, failed, iconStamp, orbsReady, chosen, everything, phone.matches, welcomeKey(), notifyAsk()]);
    if (key === last) return;
    last = key;
    const metrics = data ? Object.values(data.metrics) : [];
    const calls = metrics.reduce((n, m) => n + m.tool_calls, 0), errors = metrics.reduce((n, m) => n + m.tool_errors, 0);
    const health = [`${S.projects.reduce((n, p) => n + p.lessons, 0)} lessons`, calls ? `${(100 * errors / calls).toFixed(1)} errors per 100 tool calls` : null].filter(Boolean).join(" · ");
    fill(root,
      lostPanel(),
      S.projects.length ? queue() : null,
      S.projects.length ? notifyPrompt() : null,
      boardsPanel(),
      welcomeCard(),
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

// ── A project's Overview (feat/polish-pages): what needs you, then the prompt, what runs, how it went, worktrees, agents ──
// Nothing here is an empty panel: a part with nothing to say is left out, and "Nothing is running" is one line.
function pageHome(name) {
  const dash = h("div", { class: "dash overview" });
  const compose = composer({ name });
  const ideasBox = h("div", { class: "ideas" });
  view.append(h("div", { class: "workspace" }, dash));
  const needsBox = h("div", { class: "needs-box" });
  const composeBox = h("section", { class: "panel compose-panel", "aria-label": "Start a session" }, ideasBox, compose.el);
  const boardBox = h("div", { class: "board-box" });
  const hubBox = h("div", { class: "hub-box" });  // the home project's: hub-wide sessions, and the way to start one
  const setupBox = h("div", { class: "setup-box" });
  const rail = h("div", { class: "panel-row rail" });
  const mainRest = h("div", { class: "col-rest" });
  const chartsBox = h("div", { class: "panel-row charts" });
  const treesBox = h("div", { class: "trees-box" });  // the project's worktrees: checkouts and left-over branches
  dash.append(needsBox, composeBox, boardBox, hubBox, chartsBox, mainRest, treesBox, rail, setupBox);
  let trees = null, treeSig = "";
  const loadTrees = async () => { try { trees = await api(`/api/p/${P(name)}/worktrees`); } catch { /* the list waits for the next load */ } if (!held()) drawTrees(); };
  const drawTrees = () => {
    // A session in a worktree that starts, closes or changes its checkout asks for the list again.
    const sig = JSON.stringify(S.sessions.filter((s) => s.project === name && s.isolate).map((s) => [s.id, s.alive, s.state, s.tree && s.tree.checkout]));
    if (trees && sig !== treeSig && treeSig) { treeSig = sig; loadTrees(); return; }
    treeSig = sig;
    if (differs(treesBox, trees)) fill(treesBox, treesPanel(name, trees, loadTrees));
  };
  let data = null, last = "", endedOpen = false, hubEndedOpen = false, failed = false;
  bind([["j k", "move"], ["↵", "open"], ["i", "prompt"], ["n", "new session"], ["m", "memory"], ["d", "dreams"], [",", "project settings"]], {
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
    // The home project's Overview holds the hub-wide sessions too (README, "Hub sessions"), in a panel of their own.
    const hubwide = isHubHome(p) ? S.sessions.filter((s) => s.project === HUB) : [];
    const sessions = S.sessions.filter((s) => s.project === name);
    const count = (state) => sessions.filter((s) => s.state === state).length;
    const working = count("working"), waiting = count("needs");
    if (differs(top_, "project", tabsKey(p))) projectTop(p, "home", []);
    const ages = sessions.map((s) => ({ ...s, age: Math.round((Date.now() / 1000 - s.created) / 60) }));
    const hubAges = hubwide.map((s) => ({ ...s, age: Math.round((Date.now() / 1000 - s.created) / 60) }));
    const key = JSON.stringify([p, ages, hubAges, data, iconStamp, endedOpen, hubEndedOpen, failed, !!hubHome()]);
    if (key === last) return;
    last = key;
    const order = { needs: 0, working: 1, finished: 2, shell: 3 };
    const gone = (s) => (s.state === "ended" || s.state === "closed") && !s.alive;
    const asking = sessions.filter((s) => !gone(s) && (s.state === "needs" || s.state === "error"));
    const hubAsking = hubwide.filter((s) => !gone(s) && (s.state === "needs" || s.state === "error"));
    const active = sessions.filter((s) => !gone(s) && !asking.includes(s)).sort((a, b) => (order[a.state] ?? 3) - (order[b.state] ?? 3) || b.created - a.created);
    const ended = sessions.filter(gone).sort((a, b) => (b.closedAt || b.created) - (a.closedAt || a.created));
    const endedWord = ended.every((s) => s.state === "ended") ? "ended" : "closed";
    const metric = data && data.metrics[data.metrics.length - 1];
    if (differs(setupBox, p.setup)) fill(setupBox, p.setup.length ? panel("Finish setting up", null, p.setup.map((item, i) => h("a", { class: "notice", href: item.go === "sessions" || item.go === "commit" ? `#/p/${P(name)}` : `#/p/${P(name)}/${item.go}`, "data-nav": `setup:${i}`,
        onclick: item.go === "sessions" ? (e) => { e.preventDefault(); openClaude(name); } : item.go === "commit" ? guard(async (e) => { e.preventDefault(); await api(`/api/p/${P(name)}/commit-kit`, { repo: item.repo }); toast("Committed"); await tick(); }) : undefined }, dot(), h("span", { class: "t", textContent: item.text }), item.go === "commit" ? h("span", { class: "go", textContent: "Commit" }) : null))) : null);
    // What needs you here: its sessions that ask, then what its dreams left, in Home's own rows.
    const needRows = [...[...asking, ...hubAsking].map((s) => ({ nav: s.id, href: `#/s/${s.id}`, state: s.state, title: bareTitle(s), line: `${s.project === HUB ? "Hub-wide · " : ""}${s.state === "error" ? s.error || "Stopped with an error" : oneLine(s.asking) || "Needs your input"}`, at: s.activity && s.activity.since })),
      ...dreamRows(p, true)];
    if (differs(needsBox, needRows)) fill(needsBox, needRows.length ? h("section", { class: "panel needs-here", "aria-labelledby": "needs-here-t" },
      h("header", {}, h("h2", { id: "needs-here-t" }, "Needs you", h("span", { class: "h-n need", textContent: String(needRows.filter((r) => !r.nav.endsWith(":more")).length) }))),
      h("div", { class: "qlist" }, needRows.map((row) => askRow({ ...row, p: row.lineP, meta: row.at ? h("time", { textContent: ago(row.at) }) : null })))) : null);
    if (differs(boardBox, ages, endedOpen)) fill(boardBox, active.length || (ended.length && endedOpen) ? h("section", { class: "panel board" },
      h("header", {}, h("h2", {}, "Sessions", working ? h("span", { class: "h-n", textContent: `${working} working` }) : null), active.some((s) => s.trace && s.trace.length) ? legend() : null),
      active.map((s) => strip(s)),
      ended.length ? h("button", { class: "disclose", "aria-expanded": endedOpen ? "true" : "false", onclick: () => { endedOpen = !endedOpen; last = ""; draw(); } }, h("span", { class: `chev ${endedOpen ? "open" : ""}` }, svg(UI.chev)), `${ended.length} ${endedWord}`) : null,
      endedOpen ? ended.map((s) => strip(s)) : null)
      : h("div", { class: "board-quiet" }, h("span", { class: "empty-line", textContent: asking.length ? "Nothing else is running." : ended.length ? "Nothing is running." : "Nothing has run here yet." }),
        ended.length ? h("button", { class: "disclose", "aria-expanded": "false", onclick: () => { endedOpen = true; last = ""; draw(); } }, h("span", { class: "chev" }, svg(UI.chev)), `${ended.length} ${endedWord}`) : null));
    if (differs(hubBox, hubAges, hubEndedOpen, isHubHome(p))) fill(hubBox, isHubHome(p) ? hubPanel(hubwide.filter((s) => !hubAsking.includes(s)), hubEndedOpen, () => { hubEndedOpen = !hubEndedOpen; last = ""; draw(); }) : null);
    drawTrees();
    if (differs(mainRest, data && data.activity, failed)) fill(mainRest,
      failed && !data ? retryLine("This project's details didn't load. Retrying in 20 seconds.", load) : null,
      data && data.activity.length ? panel("Activity", feedLegend(), feed(data.activity, false)) : null);
    if (differs(ideasBox, suggestions())) fill(ideasBox, suggestions().map((idea) => h("button", { class: "idea", onclick: () => compose.fill(idea.prompt, idea.mode) }, uiIcon("corner"), h("span", { textContent: idea.text }))));
    const schedule = p.schedule;
    const hour = schedule ? schedule.hour : null;  // none: the kit puts the project on its hourly scheduler
    const mix = toolMix(sessions);
    const before = data && data.metrics[data.metrics.length - 2];
    const errorRate = metric && metric.tool_calls ? h("span", { class: "head-fact", textContent: `${metric.errors_per_100_tool_calls} errors per 100 calls at the last dream${before && before.tool_calls ? `, vs ${before.errors_per_100_tool_calls} the dream before` : ""}` }) : null;
    if (differs(chartsBox, data && data.pulse, mix, metric)) fill(chartsBox,
      data && data.pulse.length && data.pulse.some((d) => d.n) ? panel("Commits and memory writes, 14 days", null, barsChart(data.pulse)) : null,
      mix ? panel("Tool calls", errorRate, mix) : null);
    if (differs(rail, data, schedule, dreamCheck(p.check))) fill(rail,
      data ? panel("Agents you can run", data.agents.length ? buildAgent() : null,
        data.agents.length ? data.agents.map((a) => h("button", { class: "agent-row", onclick: () => showAgent(a) }, h("b", { textContent: a.name }), a.description ? h("span", { textContent: a.description }) : null))
          : h("div", { class: "empty-line retry-line" }, h("button", { class: "retry", textContent: "Build a new agent", onclick: newAgent }))) : null,
      panel(data ? "Repositories" : null, null, data ? data.repos.map((r) => h("div", { class: "p" }, h("span", { class: "k", textContent: r.name }), h("span", { class: "v" }, h("span", { class: "mono", textContent: r.branch }), r.dirty ? h("small", { textContent: `${r.dirty} changed` }) : null))) : null,
        h("div", { class: "p dream-row" }, h("span", { class: "k", textContent: dreamTiming(schedule, "Dreams ") }), h("button", { class: `switch ${schedule ? "on" : ""}`, title: "Automatic dreams", "aria-pressed": schedule ? "true" : "false", onclick: guard(async () => { await api(`/api/p/${P(name)}/schedule`, { on: !schedule, hour }); await tick(); }) })),
        dreamWhy(p.check)));
    markNav();
  };
  const load = async () => {
    loadTrees();
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
  const close = (refocus = true) => { popup.remove(); document.removeEventListener("mousedown", away, true); window.removeEventListener("hashchange", left); if (refocus) { if (anchor.isConnected) anchor.focus(); else returnTo(home, anchorSpot); } if (row) row.classList.remove("menu-open"); };
  const left = () => close(false);  // a page left by a back swipe or a link takes its menu with it; the new page keeps its focus
  const away = (e) => { if (!popup.contains(e.target)) close(); };
  const popup = h("div", { class: "popup menu", role: "menu", "aria-label": anchor.title || anchor.textContent, style: `${above ? `bottom:${window.innerHeight - rect.top + 6}px` : `top:${rect.bottom + 6}px`};left:${Math.max(8, Math.min(rect.left, window.innerWidth - 320))}px`,
    onkeydown: (e) => {
      const rows = [...popup.querySelectorAll("button")];
      const at = rows.indexOf(document.activeElement);
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
      if (e.key === "Tab") close();
      if (e.key === "ArrowDown") { e.preventDefault(); rows[(at + 1) % rows.length].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); rows[(at - 1 + rows.length) % rows.length].focus(); }
      const by = listPage(e, popup, "button");
      if (by) { e.preventDefault(); rows[Math.max(0, Math.min(rows.length - 1, (at < 0 ? 0 : at) + by))].focus(); }
    } },
    items.map((item) => item.group ? h("div", { class: "menu-group", textContent: item.group }) : h("button", { role: "on" in item ? "menuitemradio" : "menuitem", "aria-checked": "on" in item ? (item.on ? "true" : "false") : undefined, class: item.on ? "on" : "", onclick: () => { close(); item.run(); } },
      item.dot ? dot(item.dot) : item.icon ? uiIcon(item.icon) : null,
      h("span", { class: "menu-text" }, h("b", { dir: "auto", textContent: item.name }), item.say ? h("small", { textContent: item.say }) : null), item.on ? svg(UI.check) : null)));
  (anchor.closest("dialog") || document.body).append(popup);
  document.addEventListener("mousedown", away, true);
  window.addEventListener("hashchange", left);
  const firstRow = popup.querySelector("button.on") || popup.querySelector("button");
  if (firstRow) firstRow.focus(); else popup.tabIndex = -1, popup.focus();
}
const pill = (text, title, run) => h("button", { type: "button", class: "pill", title, "aria-haspopup": "menu", onclick: (e) => run(e.currentTarget) }, h("span", { textContent: text }), svg(UI.updown));

// ── Composer: the same object on a project's page and on New session ──
let carried = null;
const READS_LIKE_A_QUESTION = /^(plan|how|why|what|review|audit|investigate|explain|compare|should|research|look into)\b/i;
function composer({ name, full, splitWith }) {
  const prefs = { ...startPrefs(name), agent: "" };  // the project's own last choice, else the hub's defaults (Settings)
  const keep = () => keepStart(name, prefs);
  const p = project(name);
  let agents = [], shell = false, touched = false, isolate = false, skipHint = false, repo = p.repos[0], startError = "";
  // What you've typed stays with the project until it's started. The dock shows the first task and holds on to the rest.
  const draftKey = `draft:${name}`, later = [];
  let offered = "";  // the last idea placed in the box: replacing it loses nothing you typed
  const keepDraft = () => { const texts = [...boxes.map((b) => b.value), ...later]; saved.set(draftKey, texts.some((t) => t.trim()) ? texts : null); };

  const area = () => {
    const el = h("textarea", { rows: full ? 3 : 1, spellcheck: true, "aria-label": "Task for Claude", placeholder: full ? "Describe the task" : "What should Claude do?",
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
  const wantsTree = () => !shell && !p.hub && (touched ? isolate : tasks().length > 1 || pref("default_worktree", false));
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
  const alive = S.sessions.find((s) => s.alive && project(ownerName(s)));  // a hub-wide one counts as its home project's
  const name = projectName || (r.project && project(r.project) ? r.project : alive ? ownerName(alive) : S.projects[0].name);
  go(`#/p/${P(name)}/new${thenSplitWith ? `/${thenSplitWith}` : ""}`);
}
function pageNewSession(name, splitWith) {
  const p = project(name);
  const compose = composer({ name, full: true, splitWith });
  const chooser = p.hub ? h("h1", { class: "tail marked" }, slot(uiIcon("hub")), h("span", { class: "t", textContent: "Hub sessions" })) : S.projects.length > 1 ? h("button", { class: "pill big", title: "Project", "aria-haspopup": "menu", onclick: (e) => popover(e.currentTarget, [...S.projects.map((x) => ({ name: x.display, on: x.name === name, run: () => { if (x.name === name) return; compose.handOver(); go(`#/p/${P(x.name)}/new${splitWith ? `/${splitWith}` : ""}`); } })),
    ...(hubHome() && !splitWith ? [{ group: hubHome().display }, { name: "Hub-wide session", icon: "hub", run: () => { compose.handOver(); go(`#/p/${P(HUB)}/new`); } }] : [])]) }, mark(p, 15), h("span", { class: "t", dir: "auto", textContent: p.display }), svg(UI.updown)) : crumbTo(p);
  // With a home project, a hub-wide session starts from that project's page, and its header says so.
  setTop(p.hub ? (hubHome() ? [crumbTo(hubHome()), tail("New hub-wide session")] : [chooser]) : [chooser, tail(splitWith ? "New session beside this one" : "New session")], [], true);
  bind([["⌘↩", "start"], ["esc", "leave the prompt"], ["i", "prompt"], ["tab", "choices"], ["← →", "change choice"]], { i: () => compose.focus() });
  const live = p.hub && !hubHome() ? S.sessions.filter((s) => s.project === HUB && !gone(s)) : [];  // with a home project they're on its Overview
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
function linkProvider(term, sid, { rows = 3, open = (e, target) => activateTarget(target, sid) } = {}) {
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
      while (first > 0 && lineNumber - 1 - first < rows && continues(first - 1, first)) first--;
      let lastRow = first;
      while (lastRow - first < rows && continues(lastRow, lastRow + 1)) lastRow++;
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
          links.push({ range: { start, end }, text: value, activate: open, hover: (e, target) => showHover(e, target, sid), leave: hideHover });
        }
      };
      collect(URL_RE, (v) => v.replace(/[.,;:!?*_]+$/, ""));
      const urls = [...text.matchAll(URL_RE)].map((m) => [m.index, m.index + m[0].length]);
      for (const match of text.matchAll(PATH_RE)) {
        if (urls.some(([a, b]) => match.index >= a && match.index < b)) continue;
        const start = cells[match.index], end = cells[match.index + match[0].length - 1];
        if (!start || !end || start.y > lineNumber || end.y < lineNumber) continue;
        links.push({ range: { start, end }, text: match[0], activate: open, hover: (e, target) => showHover(e, target, sid), leave: hideHover });
      }
      callback(links.length ? links : undefined);
    },
  };
}

const paneJump = (e) => e.altKey && !e.metaKey && !e.ctrlKey && /^Digit[1-6]$/.test(e.code) && route().name === "session" && route().ids.length > 1;
const THEME = { background: "#0a0f1e", foreground: "#e8edfb", cursor: "#8fb0ff", selectionBackground: "#2c3f73" };
// ── appearance: theme, accent, terminal font size, density and motion ──
// The Settings page sets them (pref names theme, accent, term_font_size, density, reduce_motion). theme.js applied the
// last ones this browser saw before the first paint; this confirms them from the server and applies every change live.
// Until the server's settings have come, the cached ones stand in, so a light page doesn't flash dark while it loads.
const TERM_FONT = 13;
// Morning paper's terminal: the paper and ink of the light theme, and an ANSI palette deepened for paper, the bright
// colours a step darker still, so they stand out. Each of the 16 passes 4.5:1 on the terminal's paper.
// Claude Code draws in its own colours too, so the terminal also lifts any colour too faint to read (minimumContrastRatio).
const TERM_LIGHT = { background: "#fdfcfa", foreground: "#131928", cursor: "#234ab9", cursorAccent: "#fdfcfa", selectionBackground: "#cbd4ec",
  black: "#202635", red: "#b42f52", green: "#1f744f", yellow: "#8d5e05", blue: "#2d54bc", magenta: "#7f42a6", cyan: "#097689", white: "#6a6f7b",
  brightBlack: "#5e636f", brightRed: "#a01642", brightGreen: "#04623f", brightYellow: "#734c02", brightBlue: "#1e41a8", brightMagenta: "#6d3093", brightCyan: "#056070", brightWhite: "#373d4b" };
// ── The light terminal's 256 colours (16 to 255) ──
// Claude Code paints for a dark terminal, and tmux hands its colours on as the 256-colour palette. On paper its dark
// bands (behind your own message, a diff's added and removed lines) were dark strips, and its pale words faded. So in
// light each of those 240 colours is turned round in lightness, in OKLab: the same hue, as far from the paper as it was
// from the night. Black lands on the paper, white on the ink, and a dim band becomes a faint tint of its own hue.
// The curve (power 1.6) keeps bands faint and words dark, and a band keeps less of its colour than a word does. Dark keeps xterm's own 256 colours.
const termLight256 = (() => {
  const lin = (v) => (v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  const gam = (v) => 255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
  const lab = (c) => {
    const [r, g, b] = c.map(lin);
    const [l, m, s] = [0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b, 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b, 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b].map(Math.cbrt);
    return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
  };
  const rgb = ([L, a, b]) => {
    const [l, m, s] = [L + 0.3963377774 * a + 0.2158037573 * b, L - 0.1055613458 * a - 0.0638541728 * b, L - 0.0894841775 * a - 1.291485548 * b].map((v) => v ** 3);
    return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  };
  const of = (css) => [1, 3, 5].map((i) => parseInt(css.slice(i, i + 2), 16));
  const xterm = (n) => {  // the standard 256-colour palette: a 6x6x6 cube, then 24 greys
    if (n >= 232) { const v = 8 + 10 * (n - 232); return [v, v, v]; }
    const k = n - 16, step = (i) => (i ? 55 + 40 * i : 0);
    return [step(Math.floor(k / 36)), step(Math.floor(k / 6) % 6), step(k % 6)];
  };
  const paper = lab(of(TERM_LIGHT.background)), ink = lab(of(TERM_LIGHT.foreground)), night = lab(of(THEME.background))[0];
  return Array.from({ length: 240 }, (_, i) => {
    const [L, a, b] = lab(xterm(i + 16)), t = Math.max(0, (L - night) / (1 - night)) ** 1.6;
    const to = [paper[0] + (ink[0] - paper[0]) * t, paper[1] + (ink[1] - paper[1]) * t, paper[2] + (ink[2] - paper[2]) * t];
    let c = rgb(to);
    for (let k = 0.45 + 0.6 * t; k >= 0; k -= 0.05) { c = rgb([to[0], to[1] + a * k, to[2] + b * k]); if (c.every((v) => v >= 0 && v <= 1)) break; }
    return "#" + c.map((v) => Math.round(gam(Math.max(0, Math.min(1, v)))).toString(16).padStart(2, "0")).join("");
  });
})();
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
  const base = light ? { ...TERM_LIGHT, extendedAnsi: termLight256 } : THEME;
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
// ── Terminal smoothness: the GPU renderer, one write per frame, sockets let go in a hidden tab, copy feedback ──
// The WebGL renderer draws a busy pane in a fraction of the DOM renderer's time. A browser without WebGL 2, or one
// that takes the context back (a GPU reset, too many contexts), keeps or returns to the DOM renderer.
const termRenderer = (term) => {
  if (pref("term_renderer", "auto") === "dom" || !window.WebglAddon) return "dom";
  try {
    const gl = new WebglAddon.WebglAddon();
    gl.onContextLoss(() => { try { gl.dispose(); } catch { /* already gone */ } });
    term.loadAddon(gl);
    return "webgl";
  } catch { return "dom"; }
};
// Output that arrives in many small pieces is handed to the terminal once a frame. A hidden tab draws no frames, so
// there it goes straight through, and so does a burst big enough that holding it would only add delay.
const termOutput = (term) => {
  const parts = []; let bytes = 0, frame = 0, fresh = false;
  const flush = () => {
    frame = 0;
    if (!parts.length) return;
    if (fresh) { fresh = false; term.reset(); }  // in the same frame as the redraw that follows, so the screen never blanks
    let data = parts[0];
    if (parts.length > 1) { data = new Uint8Array(bytes); let at = 0; for (const part of parts) { data.set(part, at); at += part.length; } }
    parts.length = 0; bytes = 0;
    term.write(data);
  };
  return {
    take(data) {
      parts.push(data); bytes += data.length;
      if (document.hidden || bytes > 262144) { cancelAnimationFrame(frame); flush(); }
      else if (!frame) frame = requestAnimationFrame(flush);
    },
    drop() { cancelAnimationFrame(frame); frame = 0; parts.length = 0; bytes = 0; },
    restart() { cancelAnimationFrame(frame); frame = 0; parts.length = 0; bytes = 0; fresh = true; },  // what comes next draws the whole screen
  };
};
// A quiet "Copied" in the corner of the pane, when a selection reaches the clipboard (tmux's OSC 52, or the browser's copy).
const termCopied = () => {
  const el = h("span", { class: "term-copied", role: "status" });
  let timer = 0;
  return {
    el,
    say() { clearTimeout(timer); el.textContent = "Copied"; el.classList.add("show"); timer = setTimeout(() => { el.classList.remove("show"); timer = setTimeout(() => { el.textContent = ""; }, 200); }, 1200); },
    drop() { clearTimeout(timer); },
  };
};
let parkTimer = 0;
document.addEventListener("visibilitychange", () => {
  clearTimeout(parkTimer);
  if (document.hidden) parkTimer = setTimeout(() => liveTerms.forEach((t) => t.park()), Number(pref("term_park_after", 120)) * 1000);
  else liveTerms.forEach((t) => t.unpark());
});
function openTerminal(s) {
  const host = h("div", { class: "term" });
  const term = new Terminal({ fontFamily: '"JetBrains Mono", Menlo, monospace', fontSize: termFont(), lineHeight: 1.15, cursorBlink: true, theme: termTheme(), minimumContrastRatio: appearanceNow.theme === "light" ? 4.5 : 1, macOptionIsMeta: true, scrollback: 0,
    linkHandler: { allowNonHttpProtocols: true, activate: (_, text) => activateTarget(text, s.id), hover: (e, text) => showHover(e, text, s.id), leave: hideHover } });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.registerLinkProvider(termLinks(term, s.id));
  const copied = termCopied();
  term.parser.registerOscHandler(52, (data) => {
    const value = data.split(";")[1];
    if (value && value !== "?") { try { const text = new TextDecoder().decode(Uint8Array.from(atob(value), (c) => c.charCodeAt(0))); if (!(state.clip && state.clip(text))) navigator.clipboard.writeText(text).then(copied.say, () => { /* clipboard refused */ }); } catch { /* clipboard refused */ } }
    return true;
  });
  host.addEventListener("copy", copied.say);
  term.attachCustomKeyEventHandler((e) => !((e.metaKey && ["k", "b"].includes(e.key.toLowerCase())) || isPrefix(e) || paneJump(e) || (state.key && state.key(e))));
  const state = { session: s, host, term, ws: null, quiet: false, closed: false, retry: 0, timer: null, observer: null, link: "connecting", nextAt: 0, onlink: null };
  liveTerms.add(state);
  termExtras(state, copied);
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
  // A tab hidden for a while lets its terminals go, so the hub stops sending what nobody sees; back in view, each
  // reconnects at once and tmux draws the screen again. A phone that suspended the page comes back the same way.
  state.park = () => { if (state.closed || state.parked || !state.started) return; state.parked = true; clearTimeout(state.timer); if (state.ws) state.ws.close(); };
  state.unpark = () => {
    if (state.closed || !state.started || state.held) return;  // held: a phone's chat has let it go until the terminal shows again
    const was = state.parked;
    state.parked = false;
    if (was || state.down() || !state.ws || state.ws.readyState > 1) { state.retry = 0; clearTimeout(state.timer); state.since = Date.now(); setLink("connecting"); connect(); }  // the last screen stays until tmux draws it again
  };
  state.send = send;
  // Quiet: still attached, but sent nothing to draw while the chat is in front of it, and on a phone (ignoreSize) never
  // sizing the session. Shown again, the server sends a reset and tmux draws the whole screen; till then the last one stays.
  const quietMessage = () => ({ t: "q", on: !!state.quiet, size: state.quiet !== "nosize" });
  state.setQuiet = (on, ignoreSize = false) => {
    const next = on ? (ignoreSize ? "nosize" : "mute") : false;
    if (state.quiet === next) return;
    state.quiet = next;
    send(quietMessage());
  };
  const output = termOutput(term);
  term.onData((d) => send({ t: "i", d }));
  term.onResize(({ cols, rows }) => send({ t: "r", c: cols, r: rows }));
  // A terminal that connects quietly with nothing on its screen yet takes tmux's first screen before it goes quiet, so
  // it has something to show the moment it is chosen (and after a phone's chat let it go: the screen stays).
  const connect = () => {
    if (state.closed || (state.ws && state.ws.readyState < 2)) return;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const asked = { mute: !!state.quiet && !!state.drawn, nosize: state.quiet === "nosize" };
    const ws = new WebSocket(`${scheme}://${location.host}/ws/term/${s.id}?cols=${term.cols}&rows=${term.rows}${s.pop ? "&pop=1" : ""}${asked.mute ? "&mute=1" : ""}${asked.nosize ? "&nosize=1" : ""}`);
    ws.binaryType = "arraybuffer";
    state.ws = ws;
    ws.onopen = () => {
      state.retry = 0; output.restart(); setLink("open");  // the last screen stays until tmux's first draw replaces it, in one frame
      // Chosen or put behind the chat while it was connecting: the server hears what the URL no longer says.
      if (state.quiet ? asked.nosize !== (state.quiet === "nosize") : asked.mute || asked.nosize) send(quietMessage());
    };
    let first = !asked.mute;
    ws.onmessage = (event) => {
      if (typeof event.data === "string") { if (event.data.includes('"reset"')) output.restart(); return; }
      output.take(new Uint8Array(event.data));
      state.drawn = true;
      if (first) { first = false; if (state.quiet) setTimeout(() => { if (state.quiet && state.ws === ws) send(quietMessage()); }, 120); }  // the screen's first draw, then quiet
    };
    ws.onclose = (event) => {
      if (state.closed || state.parked) return;
      if (event.code === 4000) { if (state.onEnded) state.onEnded(); else tick(); return; }  // the session ended: the next poll swaps the pane for its record
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
  state.refit = () => { if (state.opened && !state.closed && host.clientWidth && host.clientHeight) fit.fit(); };
  // Prepared: the terminal is drawn into its place and sized, with no socket yet. A phone's chat prepares the one behind
  // it once the conversation is drawn, so a first switch to the terminal only has to connect.
  state.prepare = () => {
    if (state.opened || state.closed) return;
    state.opened = true;
    term.open(host);
    state.renderer = termRenderer(term);
    host.append(linkSay, bar, copied.el);
    touchScroll();
    fit.fit();
    let wait;
    state.observer = new ResizeObserver(() => { clearTimeout(wait); wait = state.wait = setTimeout(() => { if (!document.body.classList.contains("resizing")) state.refit(); }, 100); });
    state.observer.observe(host);
  };
  state.start = ({ focus = true } = {}) => {
    if (state.held || state.started || state.closed) return;  // a phone's chat view holds the terminal back: opening it would squeeze the session to the phone's width
    state.prepare();
    state.started = true;
    liveTerms.add(state);
    state.refit();
    state.since = Date.now();
    connect();
    setTimeout(drawBar, 520);
    state.ticker = setInterval(drawBar, 1000);
    if (focus) term.focus();
  };
  // xterm queues a scroll-area sync for the next frame when its buffer resets or its size changes, and doesn't cancel it
  // on dispose: disposed in between, that frame reads a renderer that is gone. So the terminal goes after two frames,
  // once anything it queued has run; with the socket closed first, nothing new arrives to queue more.
  state.dispose = () => {
    if (state.closed) return;
    state.closed = true; clearTimeout(state.timer); clearTimeout(state.wait); clearInterval(state.ticker); state.observer && state.observer.disconnect(); state.ws && state.ws.close();
    output.drop(); copied.drop(); liveTerms.delete(state);
    requestAnimationFrame(() => requestAnimationFrame(() => term.dispose()));
  };
  return state;
}

// ── The terminal's extras, from herdr's most-asked (Settings › Features, the terminal's switches): long links in one
// piece, copying as the person chooses, half-page scrolling and a scratch shell. Each reads its switch every time it
// acts, so a change applies at once; off, the terminal does what it did before. ──
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
const touchFirst = () => phone.matches || matchMedia("(hover: none)").matches;
const loopbackUrl = (url) => { try { return ["127.0.0.1", "localhost", "[::1]", "::1"].includes(new URL(url).hostname); } catch { return false; } };
// A page a session serves on this Mac opens in the hub's own browser when that feature is on and has said how to open
// one (window.hubBrowser.open). Anything else opens as it always did.
const openLink = (text, sid) => {
  hideHover();
  if (/^https?:\/\//i.test(text) && loopbackUrl(text) && feature("browser") && window.hubBrowser && typeof window.hubBrowser.open === "function") return window.hubBrowser.open({ url: text, sid });
  return activateTarget(text, sid);
};
// On a phone, with feature_link_chip on, a tap on a link offers Open and Copy, so a finger that meant to scroll never opens one.
let linkChipEl = null;
const awayFromChip = (e) => { if (linkChipEl && !linkChipEl.contains(e.target)) dropLinkChip(); };
const dropLinkChip = () => {
  if (!linkChipEl) return;
  linkChipEl.remove(); linkChipEl = null;
  document.removeEventListener("pointerdown", awayFromChip, true);
};
const linkChip = (event, text, sid) => {
  dropLinkChip();
  hideHover();  // the link's card would only cover the choice
  const copy = h("button", { type: "button", class: "btn", textContent: "Copy", onclick: async () => {
    try { await navigator.clipboard.writeText(text); copy.textContent = "Copied"; say("Link copied"); const mine = linkChipEl; setTimeout(() => { if (linkChipEl === mine) dropLinkChip(); }, 700); }
    catch { copy.textContent = "Couldn't copy"; }
  } });
  const open = h("button", { type: "button", class: "btn primary", textContent: "Open", onclick: () => { dropLinkChip(); openLink(text, sid); } });
  linkChipEl = h("div", { class: "popup link-chip", role: "dialog", "aria-label": "Link", onkeydown: (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); dropLinkChip(); } } },
    h("span", { class: "link-chip-text", dir: "auto", title: text, textContent: text.replace(/^https?:\/\//i, "") }), h("span", { class: "link-chip-acts" }, open, copy));
  document.body.append(linkChipEl);
  const w = linkChipEl.offsetWidth, tall = linkChipEl.offsetHeight, room = 8;
  const x = Math.max(room, Math.min(event.clientX - w / 2, innerWidth - w - room));
  const y = event.clientY - tall - 16 >= room ? event.clientY - tall - 16 : Math.min(event.clientY + 20, innerHeight - tall - room);
  linkChipEl.style.left = `${Math.round(x)}px`; linkChipEl.style.top = `${Math.round(y)}px`;
  setTimeout(() => document.addEventListener("pointerdown", awayFromChip, true), 0);
  open.focus({ preventScroll: true });
};
const linkOpen = (sid) => (event, text) => {
  if (feature("link_chip") && touchFirst() && event && event.clientX !== undefined) return linkChip(event, text, sid);
  openLink(text, sid);
};
// Long links in one piece (feature_wrapped_links): a link may run on for 30 rows, as a sign-in link does on a phone,
// rather than 4, and is underlined and opened whole from any of them; ⌘-click and Ctrl-click open it too (xterm passes
// every click to the link). The provider is chosen on each look, so the switch applies to the next hover.
const WRAPPED_ROWS = 30;
const termLinks = (term, sid) => {
  const plain = linkProvider(term, sid), whole = linkProvider(term, sid, { rows: WRAPPED_ROWS, open: linkOpen(sid) });
  return { provideLinks: (y, done) => (feature("wrapped_links") ? whole : plain).provideLinks(y, done) };
};
// What a selection does (copy_on_select): "clipboard" copies it when you let go, as tmux always has; "manual" holds it
// until ⌘C (Ctrl+Shift+C elsewhere) or a tap on the note that says so; "off" never copies it. tmux hands a selection over
// the way a program copies (OSC 52), so a copy counts as a selection only when the pointer let go of this terminal just
// before; a program's own copy still goes straight to the clipboard.
const SELECTED_WITHIN = 1500;
const termExtras = (state, copied) => {
  let held = "", timer = 0;
  const note = h("button", { type: "button", class: "term-held", hidden: true, title: "Copy the selection" });
  state.host.append(note);
  const drop = () => { held = ""; note.hidden = true; clearTimeout(timer); };
  const take = () => {
    if (!held) return false;
    const text = held;
    drop();
    navigator.clipboard.writeText(text).then(copied.say, () => toast("The browser didn't allow the copy. Try once more."));
    return true;
  };
  note.addEventListener("click", (e) => { e.stopPropagation(); take(); state.term.focus(); });
  ["pointerup", "dblclick"].forEach((name) => state.host.addEventListener(name, () => { state.letGoAt = Date.now(); }, true));
  state.host.addEventListener("pointerdown", (e) => { if (e.target !== note && !note.contains(e.target)) drop(); }, true);
  // True when the selection is handled here and not copied at once.
  state.clip = (text) => {
    const mode = pref("copy_on_select", "clipboard");
    if (mode === "clipboard" || Date.now() - (state.letGoAt || 0) > SELECTED_WITHIN) return false;
    if (mode === "off") return true;
    held = text;
    fill(note, h("span", { textContent: "Selected" }), h("span", { class: "faint", textContent: touchFirst() ? "Tap to copy" : `${IS_MAC ? "⌘C" : "Ctrl+Shift+C"} to copy` }));
    note.hidden = false;
    clearTimeout(timer); timer = setTimeout(drop, 30000);
    return true;
  };
  // True when the key is the hub's and never reaches the terminal.
  state.key = (e) => {
    if (e.type !== "keydown") return false;
    const c = e.key.toLowerCase() === "c" && ((e.metaKey && !e.ctrlKey && !e.altKey) || (e.ctrlKey && e.shiftKey && !e.metaKey));
    if (held && c) { e.preventDefault(); return take(); }
    if (held && !["Shift", "Meta", "Control", "Alt"].includes(e.key)) drop();
    // ⇧PgUp and ⇧PgDn (feature_page_keys): half a screen of tmux's history. xterm.js kept these keys and, with no
    // history of its own, did nothing with them; now they go on to tmux, which scrolls (hub_terminal.py binds them).
    if (feature("page_keys") && e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey && (e.key === "PageUp" || e.key === "PageDown")) {
      e.preventDefault();
      if (state.send) state.send({ t: "i", d: e.key === "PageUp" ? "\x1b[5;2~" : "\x1b[6;2~" });
      return true;
    }
    return false;
  };
};

// ── Scratch (feature_scratch): a quick shell over the session, in its folder. It runs in a tmux session of its own,
// pop-<sid>, which no list shows as a session. Hidden, it keeps running; Close ends it; it ends with its session.
// On a desk it floats over the panes and leaves the layout as it was; on a phone it fills the screen. ──
const scratchLive = new Set();  // sessions with a scratch shell running, as the server last said
const scratch = { sid: null, el: null, terminal: null, back: null, holder: null, watch: null };
const scratchShown = () => !!scratch.el;
const refreshScratches = async () => {
  try {
    const { live } = await api("/api/terminal/scratch");
    const before = [...scratchLive].sort().join();
    scratchLive.clear(); live.forEach((id) => scratchLive.add(id));
    if (before !== live.join() && route().name === "session" && page.update) page.update();
  } catch { /* the marks stay as they were */ }
};
const placeScratch = () => {
  if (!scratch.el || phone.matches) { if (scratch.el) scratch.el.removeAttribute("style"); return; }
  const panes = scratch.holder.querySelector(".panes");
  if (!panes) return;
  const w = Math.min(panes.offsetWidth - 48, 1100), tall = Math.max(220, Math.min(panes.offsetHeight - 48, Math.round(panes.offsetHeight * 0.72)));
  scratch.el.style.cssText = `left:${Math.round(panes.offsetLeft + (panes.offsetWidth - w) / 2)}px;top:${Math.round(panes.offsetTop + (panes.offsetHeight - tall) / 2)}px;width:${Math.round(w)}px;height:${tall}px`;
};
const hideScratch = (focusBack = true) => {
  if (!scratch.el) return;
  const { el, terminal, back, watch } = scratch;
  Object.assign(scratch, { sid: null, el: null, terminal: null, back: null, holder: null, watch: null });
  if (watch) watch.disconnect();
  window.removeEventListener("resize", placeScratch);
  phone.removeEventListener("change", placeScratch);
  if (terminal) terminal.dispose();
  el.remove();
  if (focusBack && back && back.isConnected) back.focus({ preventScroll: true });
  if (route().name === "session" && page.update) page.update();
};
// Stopping something that runs asks the same way wherever it's asked from: a plain terminal from its pane, the sidebar,
// Go to or a split, and a scratch shell with a program still running in it.
const confirmStop = ({ title, running }) => confirmStep({ title: `Stop “${title}”?`, body: running ? `${running} is still running in it, and stops too. Nothing in the terminal is kept.` : "What runs in it stops. Nothing in the terminal is kept.", yes: "Stop", no: "Keep running" });
const stopTerminal = guard(async (s) => {
  if (!(await confirmStop({ title: s.title }))) return;
  await api(`/api/sessions/${s.id}/stop`, {});
  toast(`Stopped ${s.title}`);
  await tick();
});
const closeScratch = guard(async (sid) => {
  const now = await api("/api/terminal/scratch", { sid, op: "state" });
  if (now.alive && now.busy && !(await confirmStop({ title: "Scratch", running: now.busy }))) return;
  await api("/api/terminal/scratch", { sid, op: "close" });
  scratchLive.delete(sid);
  if (scratch.sid === sid) hideScratch();
  say("Scratch terminal closed");
});
const showScratch = guard(async (s, holder) => {
  if (!feature("scratch") || !s || !s.alive) return;
  if (scratch.el && scratch.sid === s.id) { hideScratch(); return; }
  hideScratch(false);
  const back = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
  const opened = await api("/api/terminal/scratch", { sid: s.id, op: "open" });
  scratchLive.add(s.id);
  const terminal = openTerminal({ ...s, kind: "shell", pop: true });
  terminal.onEnded = () => { scratchLive.delete(s.id); if (scratch.sid === s.id) hideScratch(); say("The scratch terminal ended"); };
  const keys = `${prefixSpec().label} t`;
  const el = h("section", { class: "scratch", role: "dialog", "aria-label": `Scratch terminal for ${s.title}`, "data-sid": s.id },
    h("header", { class: "scratch-top" },
      uiIcon("term"), h("b", { textContent: "Scratch" }), h("span", { class: "scratch-where", dir: "auto", title: opened.folder, textContent: shortPath(opened.folder) }),
      h("span", { class: "grow" }),
      phone.matches ? null : h("span", { class: "scratch-keys faint" }, h("kbd", { textContent: keys }), " hides"),
      h("button", { type: "button", class: "btn", "data-key": "scratch-hide", title: `Hide it. It keeps running, and ${keys} brings it back.`, onclick: () => hideScratch() }, "Hide"),
      h("button", { type: "button", class: "btn", "data-key": "scratch-close", title: "End this shell", onclick: () => closeScratch(s.id) }, "Close")),
    terminal.host,
    // A phone has no Esc, Tab, arrows or ^C: the same row of keys as under a pane.
    h("div", { class: "keys" }, [["Esc", "\x1b"], ["Tab", "\t"], ["↑", "\x1b[A"], ["↓", "\x1b[B"], ["^C", "\x03"], ["Enter", "\r"]].map(([label, data]) =>
      h("button", { type: "button", textContent: label, onclick: () => { terminal.send({ t: "i", d: data }); terminal.term.focus(); } }))));
  holder.append(el);
  Object.assign(scratch, { sid: s.id, el, terminal, back, holder });
  placeScratch();
  window.addEventListener("resize", placeScratch);
  phone.addEventListener("change", placeScratch);
  const panes = holder.querySelector(".panes");
  if (panes && window.ResizeObserver) { scratch.watch = new ResizeObserver(placeScratch); scratch.watch.observe(panes); }
  terminal.start();
  if (route().name === "session" && page.update) page.update();
});
// The pane header's way in, with a mark while one runs hidden. Its glyph is a prompt with a corner, so it never reads as
// the Terminal view beside it.
UI.scratch = '<path d="m2.5 5.5 3 2.5-3 2.5M7.5 12.5h4"/><path d="M10.5 2.5h3v3"/>';
const scratchButton = (s, onClick) => feature("scratch") && s.alive
  ? h("button", { class: `icon pane-scratch ${scratchLive.has(s.id) ? "live" : ""} ${scratch.sid === s.id ? "on" : ""}`, type: "button", "data-key": "scratch",
    title: `Scratch terminal (${prefixSpec().label} t)${scratchLive.has(s.id) && scratch.sid !== s.id ? ". One is running." : ""}`, "aria-pressed": scratch.sid === s.id ? "true" : "false", onclick: onClick }, uiIcon("scratch"))
  : null;

// ── Pane layouts (feature_pane_layouts): three shapes a split can take, in the order its panes are in now ──
const LAYOUT_SHAPES = [["columns", "Side by side"], ["main", "Main and stack"], ["grid", "Grid"]];
const layoutShape = (kind, list) => {
  const n = list.length;
  if (n < 2) return list[0];
  if (kind === "columns") return { d: "h", k: list, z: even(n) };
  if (kind === "main") return n === 2 ? { d: "v", k: list, z: even(2) } : { d: "h", k: [list[0], { d: "v", k: list.slice(1), z: even(n - 1) }], z: [0.6, 0.4] };
  const across = Math.ceil(Math.sqrt(n)), rows = [];
  for (let i = 0; i < n; i += across) rows.push(list.slice(i, i + across));
  return tidyLayout({ d: "v", k: rows.map((r) => r.length === 1 ? r[0] : { d: "h", k: r, z: even(r.length) }), z: even(rows.length) });
};
// The shapes that differ for this many panes: two panes have side by side and stacked.
const layoutChoices = (list) => {
  const seen = new Set();
  return LAYOUT_SHAPES.map(([kind, word]) => [kind, list.length === 2 && kind === "main" ? "Stacked" : word, tidyLayout(layoutShape(kind, list))])
    .filter(([, , tree]) => { const t = treeText(tree); if (seen.has(t)) return false; seen.add(t); return true; });
};
const sameShape = (a, b) => treeText(a) === treeText(b);
// Every pane one place on, the last first; each place keeps its size.
const rotatedLayout = (n) => { const ids = leavesOf(n), next = [ids[ids.length - 1], ...ids.slice(0, -1)]; let i = 0; return mapLeaves(n, () => next[i++]); };

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
const ORB_WORDS = { reasoning: "Thinking", searching: "Searching", using: "Using a tool", compacting: "Compacting", retrying: "Retrying", background: "In the background", working: "Working", waiting: "Needs you" };
// "12s", "1m 04s", "2h 05m": what has passed since an epoch second, in a width that doesn't jump.
const took = (since) => {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - since));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor(s / 60) % 60).padStart(2, "0")}m`;
};
// A turn's clock. Past an hour a running count says little, so it says when the turn began instead, quietly.
const LONG_TURN = 3600;
const turnWords = (since) => {
  if (Date.now() / 1000 - since < LONG_TURN) return took(since);
  const at = new Date(since * 1000), today = at.toDateString() === new Date().toDateString();
  return `since ${today ? "" : `${at.toLocaleDateString("en-GB", { weekday: "short" })} `}${at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
};
const turnClock = (since, attrs = {}) => h("time", { ...attrs, class: `tick ${attrs.class || ""} ${Date.now() / 1000 - since >= LONG_TURN ? "long" : ""}`, "data-since": since, dateTime: new Date(since * 1000).toISOString(), textContent: turnWords(since) });
setInterval(() => document.querySelectorAll("time.tick[data-since]").forEach((el) => { const text = turnWords(Number(el.dataset.since)); if (el.textContent !== text) { el.textContent = text; el.classList.toggle("long", text.startsWith("since")); } }), 1000);
const tokens = (n) => n >= 1e6 ? `${+(n / 1e6).toFixed(n % 1e6 ? 1 : 0)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
const counts = (c) => [h("span", { class: "n-add", textContent: `+${c.added}` }), " ", h("span", { class: "n-del", textContent: `−${c.removed}` })];

// ── A choice Claude shows, answered here: a question of several (single or multiple choice, with words of your own),
// a permission, a plan to approve, a picker or a menu. The screen stays the truth: what is ticked, typed and which
// question is open are read back from it after each answer. Ticks and words wait here until they're sent, so the
// screen refreshing never loses them.
const qaDrafts = new Map();  // `${session}|${question}` → { picks: Set | null, words: { n: text } }
function questionPanel(id, { compact = false, onSent = () => {}, tools = null } = {}) {
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
    // A chat already names what Claude asks in its pane's head, so only the compact peek repeats it above the details.
    const lead = compact && d.kind === "permission" && asking && asking !== d.question ? h("p", { class: "qa-lead", dir: "auto", textContent: asking }) : null;
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
    // The host's own tools (a chat's keys) sit in the row you type in, or with the quiet choices at the end: one place
    // to type, and one send, while Claude asks.
    const kit = tools ? tools().filter(Boolean) : [];
    if (kit.length) {
      const row = el.querySelector(".qa-words:not(.qa-amend)") || el.querySelector(".qa-amend");
      if (row) { const go = row.querySelector(".qa-go"); if (go) go.before(...kit); else row.append(...kit); }
      else { let apart = el.querySelector(".qa-apart"); if (!apart) { apart = h("div", { class: "qa-apart" }); el.append(apart); } apart.append(h("span", { class: "qa-fill" }), ...kit); }
    }
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
  const why = h("span", { class: "peek-why", hidden: true });  // why the session is in its state: a hook, the screen, the status file
  const body = h("div", { class: "peek-body", tabindex: "-1" });
  const choices = h("div", { class: "peek-choices", role: "group" });
  const input = h("textarea", { rows: 1, placeholder: "Reply", "aria-label": `Reply to ${s0.title}`, enterkeyhint: "send" });
  const hint = h("div", { class: "peek-keys" });
  const form = h("div", { class: "peek-reply" }, input);
  const open = h("a", { class: "icon", href: `#/s/${id}`, title: "Open session", "aria-label": "Open session", onclick: () => closePeek(false) }, uiIcon("corner"));
  const box = h("div", { class: "peek-pop", role: "dialog", "aria-label": `Peek: ${s0.title}`, tabindex: "-1" },
    h("header", {}, orb, h("span", { class: "peek-title" }, title, when, why), open, h("button", { class: "icon", title: "Close", "aria-label": "Close", onclick: () => closePeek() }, uiIcon("close"))),
    body, choices, form, hint);
  document.body.append(box);
  let data = null, sending = false, shownKey = "";
  const panel = questionPanel(id, { compact: true, onSent: async () => { await tick(); await load(true); setTimeout(() => peekOpen && peekOpen.box === box && load(true), 700); } });
  const place = () => {
    const row = side.querySelector(`[data-sid="${CSS.escape(id)}"]`);
    box.classList.toggle("sheet", phone.matches || !row || !row.offsetParent);
    if (box.classList.contains("sheet")) { box.style.left = box.style.top = ""; return; }
    const r = row.getBoundingClientRect();
    box.style.left = `${Math.round(sidebarAt() === "right" ? r.left - 8 - box.offsetWidth : r.right + 8)}px`;
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
    const word = s.state === "working" ? (s.activity && /using|searching/.test(s.orb || "") ? "Working" : ORB_WORDS[s.orb] || "Working") : s.state === "error" ? "Error" : asksYou(s) ? "Done · asks you" : DOT_WORDS[shownState(s)] || "";
    fill(when, word, s.state === "working" && s.turn ? [" · ", turnClock(s.turn.since)] : null);
    why.textContent = s.why ? `Why: ${s.why}` : ""; why.title = why.textContent; why.hidden = !s.why;
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
  const applyPanel = () => showWidth(Math.min(PANEL.max, panelFor(activeId).w));
  const togglePanel = () => { const inside = feature("side_panel") && sharedBox.contains(document.activeElement); if (phone.matches) phonePanel = !phonePanel; else keepPanel(activeId, { on: !panelOn() }); applyPanel(); drawShared(true); drawTop(); if (inside && !panelOn()) backToPane(); };
  let panelW = 0;
  // Dragging it narrower than it can be closes it; p or the panel button brings it back at the width it had.
  dragEdge(panelEdge, {
    move: (x) => {
      const box = stage.getBoundingClientRect(), w = panelLeft() ? x - box.left : box.right - x;  // the panel sits opposite the sidebar
      if (w < PANEL.min - 64) { panelW = 0; if (panelOn()) togglePanel(); return; }
      panelW = Math.round(Math.min(PANEL.max, Math.max(PANEL.min, w)));
      showWidth(panelW);
    },
    end: () => { if (panelW) keepPanel(activeId, { w: panelW }); panelW = 0; },
    reset: () => { keepPanel(activeId, { w: PANEL.start }); applyPanel(); },
    step: (by) => { const w = Math.min(PANEL.max, Math.max(PANEL.min, panelFor(activeId).w - (panelLeft() ? -by : by))); keepPanel(activeId, { w }); applyPanel(); },
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
    noteVisit(id);
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
      [...box.children].filter((el) => !el.classList.contains("gutter") && !el.classList.contains("zoom-on")).forEach((el, i) => { el.style.flex = `${node.z[i]} 1 0px`; });
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
  const onPhoneChange = () => { phonePanel = false; arrange(); syncZoom(); refitAll(); if (painted) { drawShared(true); drawTop(); } };
  phone.addEventListener("change", onPhoneChange);
  // ── Zoom: one pane fills the split. The others stay where they are, hidden and still connected, so restoring is
  // instant and no terminal behind it is resized. The hash keeps it (#/s/<layout>~<id>), so a reload does too. ──
  let zoomed = null;
  const zoomGhost = h("div", { class: "zoom-ghost", "aria-hidden": "true" });  // holds the zoomed pane's place in the split
  const toggleZoom = (id = activeId) => { if (ids.length > 1) go(zoomHash(layout, zoomed ? null : id)); };
  const syncZoom = () => {
    const r = route(), want = r.name === "session" && ids.length > 1 && ids.includes(r.zoom) ? r.zoom : null;
    if (want === zoomed && (!want || phone.matches || zoomGhost.isConnected)) return false;
    zoomed = want;
    panes.classList.toggle("zoomed", !!zoomed);
    zoomGhost.remove();
    entries.forEach((entry, id) => { entry.pane.classList.toggle("zoom-on", id === zoomed); entry.pane.inert = !!zoomed && id !== zoomed; });
    if (zoomed && !phone.matches) { const pane = entries.get(zoomed).pane; zoomGhost.style.flex = pane.style.flex; pane.before(zoomGhost); }
    if (zoomed) setActive(zoomed);
    if (painted) { drawTop(); drawStatus(); say(zoomed ? `${(session(zoomed) || {}).title || "The pane"} fills the split` : "The whole split again"); }
    return true;
  };
  // Panes by direction, from where they are on screen: the nearest one that way, preferring one level with this one.
  const slotOf = (id) => id === zoomed && zoomGhost.isConnected ? zoomGhost : entries.get(id).pane;
  const paneDir = (dir, swap) => {
    if (ids.length < 2 || phone.matches || !entries.get(activeId)) return;
    const a = slotOf(activeId).getBoundingClientRect(), across = dir === "left" || dir === "right";
    let best = null, bestScore = Infinity;
    ids.forEach((id) => {
      if (id === activeId) return;
      const b = slotOf(id).getBoundingClientRect();
      const ahead = { left: a.left - b.right, right: b.left - a.right, up: a.top - b.bottom, down: b.top - a.bottom }[dir];
      if (ahead < -4) return;
      const apart = across ? Math.max(0, Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom)) : Math.max(0, Math.max(a.left, b.left) - Math.min(a.right, b.right));
      const centre = across ? Math.abs(a.top + a.bottom - b.top - b.bottom) : Math.abs(a.left + a.right - b.left - b.right);
      const score = apart * 1000 + Math.max(0, ahead) + centre / 100;
      if (score < bestScore) { bestScore = score; best = id; }
    });
    if (!best) { say(`No pane ${{ left: "to the left", right: "to the right", up: "above", down: "below" }[dir]}`); return; }
    const other = (session(best) || {}).title || "the other pane";
    if (swap) { go(zoomHash(layoutSwap(layout, activeId, best), zoomed)); say(`Swapped with ${other}`); }
    else if (zoomed) go(zoomHash(layout, best));  // the zoom moves with you
    else focusPane(ids.indexOf(best));
  };

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
    head.addEventListener("dblclick", (e) => { if (ids.length > 1 && !phone.matches && (!e.target.closest("button, a") || e.target.closest(".name"))) { e.preventDefault(); toggleZoom(id); } });
    pane.addEventListener("focusin", () => setActive(id));
    pane.addEventListener("pointerdown", () => setActive(id), true);
    if (s && s.alive) {
      const terminal = openTerminal(s);
      entry.terminal = terminal;
      terminal.onlink = () => drawHead(entry);
      entry.strip = s.kind === "claude" ? h("div", { class: "pane-strip", role: "status", hidden: true }) : null;
      // The terminal and the chat share one body and both stay once made: a switch shows one and hides the other, so
      // neither is built again. The hidden terminal keeps its size underneath (see "The chat" in the README).
      terminal.host.id = `term-${id}`;
      terminal.host.setAttribute("role", "tabpanel");
      terminal.host.setAttribute("aria-label", "Terminal");
      entry.body = h("div", { class: "pane-body" }, terminal.host);
      if (s.kind === "claude") {
        terminal.onScrollIntent = () => { if (!phone.matches) return false; openReader(entry); return true; };
        entry.readToggle = h("button", { type: "button", class: "read-toggle", textContent: "Read", onclick: () => entry.reader ? closeReader(entry) : openReader(entry) });
      }
      pane.append(entry.body, h("div", { class: "drop-hint" }, h("span", { textContent: "Share with this session" })),
        h("div", { class: "keys" }, entry.readToggle || null, attachButton(id), [["Esc", "\x1b"], ["Tab", "\t"], ["↑", "\x1b[A"], ["↓", "\x1b[B"], ["⇧Tab", "\x1b[Z"], ["^C", "\x03"], ["Enter", "\r"]].map(([label, data]) =>
          h("button", { type: "button", textContent: label, onclick: () => { closeReader(entry, false); terminal.send({ t: "i", d: data }); terminal.term.focus(); } }))));
      terminal.host.addEventListener("paste", (e) => { const files = [...(e.clipboardData ? e.clipboardData.files : [])]; if (files.length) { e.preventDefault(); e.stopPropagation(); guard(shareFiles)(id, files); } }, true);
      pane.addEventListener("dragover", (e) => { if (!entry.terminal || entry.chat) return; e.preventDefault(); pane.classList.add("dropping"); });  // the chat takes its own drops
      pane.addEventListener("dragleave", (e) => { if (!pane.contains(e.relatedTarget)) pane.classList.remove("dropping"); });
      pane.addEventListener("drop", (e) => { if (entry.chat) return; e.preventDefault(); pane.classList.remove("dropping"); guard(shareFiles)(id, [...e.dataTransfer.files]); });
      if (chatting(s)) {
        // The terminal connects quietly once the chat is drawn, so the first switch to it is instant too: at a desk
        // hidden at its own size, on a phone never sizing the session (so it isn't squeezed to the phone's width).
        terminal.held = true;
        pane.classList.add("chatting");
        terminal.host.inert = true;
        openChat(entry);
        setTimeout(() => { if (entries.get(id) === entry) behindChat(entry); }, 400);
      }
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
    // A long message (a pasted summary runs to thousands of words) shows its first lines, and Show all opens the rest.
    const long = said.length > 900 || said.split("\n").length > 14;
    const more = long ? h("button", { type: "button", class: "linkish said-more", "aria-expanded": "false", textContent: "Show all",
      onclick: (e) => { const turn = e.currentTarget.closest(".turn"), open = turn.classList.toggle("open"); e.currentTarget.textContent = open ? "Show less" : "Show all"; e.currentTarget.setAttribute("aria-expanded", String(open)); } }) : null;
    return h("div", { class: `turn you ${long ? "long" : ""}`, role: "group", "aria-label": "You said" }, said ? h("div", { class: "said", dir: "auto" }, inline(said, { sid: id })) : null, more,
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
  // Chat and Terminal are two views of one pane, both kept once made: a switch flips which shows, at once, and builds
  // nothing again. The chat polls only while it shows. Behind the chat the terminal stays attached but quiet (sent
  // nothing to draw), keeps its size at a desk, and on a phone never sizes the session and lets go after a minute.
  // Shown again it keeps its last screen until tmux has drawn it afresh.
  const CHAT_LET_GO = 60000;
  const letGoLater = (entry) => {
    const terminal = entry.terminal;
    clearTimeout(terminal.letGo);
    terminal.letGo = setTimeout(() => { if (entry.chat && entries.get(entry.id) === entry) { terminal.held = true; terminal.park(); } }, CHAT_LET_GO);
  };
  // The terminal behind the chat, attached and quiet: it takes one screen and then is sent nothing to draw. On a phone
  // it never sizes the session (ignore-size) and lets go a minute after it was last wanted. Called once the chat is
  // drawn, and again when a finger or pointer comes down on Terminal, so a terminal let go reconnects before the click.
  const behindChat = (entry) => {
    const terminal = entry.terminal;
    if (!terminal || terminal.closed || !entry.chat) return;
    terminal.setQuiet(true, phone.matches);
    terminal.held = false;
    if (terminal.started) terminal.unpark(); else terminal.start({ focus: false });
    if (phone.matches) letGoLater(entry);
  };
  const switchView = (entry, view, how = "click") => {
    saved.set(viewKey(), view);
    const chat = view === "chat", terminal = entry.terminal;
    if (!terminal || chat === !!entry.chat) return;
    const inSeg = !!(document.activeElement && document.activeElement.closest && document.activeElement.closest(".view-seg"));
    entry.pane.classList.toggle("chatting", chat);
    if (chat) {
      closeReader(entry, false);
      terminal.host.inert = true;
      terminal.setQuiet(true, phone.matches);
      if (phone.matches && terminal.started) letGoLater(entry);
      if (entry.chatKept) entry.chatKept.show(); else openChat(entry);
    } else {
      entry.chatKept && entry.chatKept.hide();
      entry.chat = null;
      terminal.host.inert = false;
      terminal.held = false;
      clearTimeout(terminal.letGo);
      terminal.refit();
      terminal.setQuiet(false);
      if (terminal.started) terminal.unpark();
      else if (terminal.opened) terminal.start({ focus: false });
      else requestAnimationFrame(() => setTimeout(() => { if (!entry.chat && entries.get(entry.id) === entry) { terminal.start({ focus: how !== "key" }); } }, 0));  // drawing a terminal takes a moment: the choice shows first
    }
    drawHead(entry);
    drawStrip(entry);
    setActive(entry.id);
    // A key in the tabs keeps focus on them (the chosen tab); a click hands it to what it opened, as a terminal wants.
    const tab = entry.head.querySelector('.view-seg [aria-selected="true"]');
    if (inSeg && how === "key" && tab) tab.focus();
    else if (!chat && document.activeElement !== terminal.term.textarea) terminal.term.focus();
    else if (chat && !phone.matches && inSeg) entry.chat.input.focus({ preventScroll: true });
  };
  const openChat = (entry, hidden = false) => {
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
    // While Claude asks, its question is the one place to type: the message box and its send step aside (.asking), and
    // the keys button joins the question's own row.
    const row = h("div", { class: "chat-row" }, keysBtn, attach, input, send);
    const dock = h("div", { class: "chat-dock" }, ask, note, keyRow, tray, row);
    dock.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); dock.classList.add("dropping"); } });
    dock.addEventListener("dragleave", (e) => { if (!dock.contains(e.relatedTarget)) dock.classList.remove("dropping"); });
    dock.addEventListener("drop", (e) => { e.preventDefault(); dock.classList.remove("dropping"); addFiles(e.dataTransfer.files); });
    // At a desk a file dropped anywhere on the conversation is attached too.
    log.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); dock.classList.add("dropping"); } });
    log.addEventListener("dragleave", (e) => { if (!log.contains(e.relatedTarget)) dock.classList.remove("dropping"); });
    log.addEventListener("drop", (e) => { if (!e.dataTransfer.files.length) return; e.preventDefault(); dock.classList.remove("dropping"); addFiles(e.dataTransfer.files); });
    log.addEventListener("scroll", () => { log.dataset.stuck = log.scrollTop + log.clientHeight >= log.scrollHeight - 64 ? "1" : "0"; }, { passive: true });
    const viewBox = h("div", { class: "chat-view", id: `chat-${id}`, role: "tabpanel", "aria-label": "Chat" }, log, dock);
    entry.body.append(viewBox);
    let data = null, sending = false, shownAsk = "", pending = null, autoKeys = false;
    const panel = questionPanel(id, { tools: () => [keysBtn], onSent: () => { shownAsk = ""; tick(); setTimeout(loadPeek, 150); setTimeout(loadPeek, 800); setTimeout(loadRecord, 900); } });
    entry.chat = entry.chatKept = { log, input, view: viewBox };
    const showing = () => entry.chat === entry.chatKept && log.isConnected;
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
        dock.classList.add("asking");
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
      dock.classList.toggle("asking", !!menu);  // a menu takes keys, not words: the message box steps aside for it too
      if (!keysBtn.isConnected || !row.contains(keysBtn)) row.prepend(keysBtn);
      // A menu needs the keys: they open for it, and close again after it unless you had them open anyway.
      if (menu && keyRow.hidden) { keyRow.hidden = false; autoKeys = true; }
      else if (!menu && autoKeys) { keyRow.hidden = !saved.get("chatKeys", false); autoKeys = false; }
      keysBtn.setAttribute("aria-pressed", keyRow.hidden ? "false" : "true");
      paintSend();
      if (menu) log.scrollTop = log.scrollHeight;
    };
    const loadPeek = () => {
      if (!showing() || document.hidden) return;
      api(`/api/sessions/${id}/peek`).then((next) => { if (!log.isConnected) return; data = next; drawAsk(); paintSend(); }).catch(() => {});
    };
    let first = true;
    const stop = loadingIn(body, "Loading the conversation…", () => log.isConnected);
    const loadRecord = (force) => {
      if (!(force === true ? log.isConnected : showing())) return;
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
    // A pane being built isn't on the page yet: the first load waits for it rather than for the next tick (3 s).
    if (log.isConnected) { loadRecord(true); loadPeek(); } else setTimeout(() => { loadRecord(true); loadPeek(); }, 0);
    const timer = setInterval(() => { if (!log.isConnected) { clearInterval(timer); return; } if (!document.hidden) { loadRecord(); loadPeek(); } }, 3000);
    requestAnimationFrame(() => { fit(); paintSend(); });
    // Hidden, it stays as it was, scrolled where you left it; shown again it is up to date at once.
    entry.chatKept.hide = () => { viewBox.inert = true; };
    entry.chatKept.show = () => {
      viewBox.inert = false;
      entry.chat = entry.chatKept;
      if (log.dataset.stuck !== "0") requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });  // read after the switch has painted, not in it
      shownAsk = ""; loadRecord(); loadPeek(); paintSend();
    };
    if (hidden) { entry.chat = null; viewBox.inert = true; }
    entry.chatKept.refresh = () => { paintSend(); const s = session(id); if (s && (s.state === "needs") !== !!(data && data.dialog)) loadPeek(); };
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
    entry.pane.querySelectorAll(":scope > .pane-body, :scope > .keys, :scope > .drop-hint, :scope > .pane-strip").forEach((el) => el.remove());
    entry.pane.classList.remove("chatting");
    entry.chat = entry.chatKept = null;
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
    if (!differs(entry.head, s.state, s.title, s.mode, s.model, s.kind, s.alive, s.connected, s.phone, s.repo, s.isolate, s.tree, s.project, entry.full, entry.pending, down, ids.length, ids.indexOf(entry.id), !!entry.chat, phone.matches, (project(s.project) || {}).icon, feature("scratch"), scratchLive.has(s.id), scratch.sid === s.id)) { if (headDot()) headDot().title = tip; return; }
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
    // One row, one height (polish-session): the name, mode and model as quiet words, the state the strip says, then
    // Chat|Terminal (the head's one outlined control), scratch, split and ⋯. Connect phone, Open on phone, Close
    // session and Delete live in ⋯; below 560px so do mode and model, and below 360px the view too.
    const narrow = () => entry.pane.clientWidth <= 560;
    const viewTo = (chat, how) => () => { if (!!entry.chat !== chat) switchView(entry, chat ? "chat" : "terminal", how); };
    // Chat|Terminal is a pair of tabs: the chosen one is filled, bold, in ink, with a bar under it; ← → move between them
    // and show at once. A pointer resting on Chat fetches the conversation, so a first switch finds it drawn; a finger
    // or pointer coming down on Terminal reconnects a terminal the chat let go, in the moment before the click.
    const viewKeys = (e) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const chat = e.key === "Home" ? true : e.key === "End" ? false : !entry.chat;
      if (!!entry.chat !== chat) viewTo(chat, "key")(); else { const tab = entry.head.querySelector('.view-seg [aria-selected="true"]'); if (tab) tab.focus(); }
    };
    const warm = () => { if (!entry.chatKept && entry.terminal && entry.body && s.alive) openChat(entry, true); };
    const viewSeg = s.kind === "claude" && s.alive ? h("div", { class: "seg view-seg", role: "tablist", "aria-label": "Show this session as", onkeydown: viewKeys },
      [[true, "Chat", "Show as a chat"], [false, "Terminal", "Show the terminal"]].map(([chat, word, title]) => {
        const on = !!entry.chat === chat;
        return h("button", { type: "button", role: "tab", class: on ? "on" : "", id: `view-${entry.id}-${chat ? "chat" : "term"}`, "aria-selected": on ? "true" : "false", tabindex: on ? "0" : "-1",
          "aria-controls": chat ? (entry.chatKept ? `chat-${entry.id}` : undefined) : `term-${entry.id}`, "data-key": on ? "view-on" : "view", "data-word": word, title,
          onclick: viewTo(chat), onpointerenter: chat ? warm : undefined, onfocus: chat ? warm : undefined, onpointerdown: chat ? undefined : () => behindChat(entry) }, h("span", { textContent: word }));
      })) : null;
    const moreItems = () => [
      ...(narrow() && live ? [...(s.project === HUB ? [] : [{ group: "Mode" }, ...modeItems]), { group: "Model" }, ...modelItems] : []),
      viewSeg && entry.pane.clientWidth <= 360 ? { name: entry.chat ? "Show the terminal" : "Show as a chat", icon: entry.chat ? "term" : "chat", run: viewTo(!entry.chat) } : null,
      canConnect ? { name: "Connect phone", icon: "phone", run: connect } : null,
      phoneLink && !phone.matches ? { name: "Open on phone", icon: "phone", run: () => window.open(s.phone, "_blank", "noopener") } : null,
      { group: "Session" },
      closable ? { name: "Close session", icon: "stop", say: "End Claude and keep the conversation", run: () => closeSession(s) } : null,
      { name: "Delete session…", icon: "close", run: () => deleteSession(s) },
    ].filter(Boolean);
    fill(entry.head,
      dot(shown, tip), ids.length > 2 ? h("span", { class: "pane-n", textContent: `${ids.indexOf(entry.id) + 1}/${ids.length}` }) : null, ids.length > 1 && ownerOf(s) ? mark(ownerOf(s), 15) : null,
      h("button", { class: `name ${entry.full ? "full" : ""}`, type: "button", dir: "auto", textContent: s.title, "data-key": "name",
        onpointerenter: (e) => markName(e.currentTarget), onfocus: (e) => markName(e.currentTarget),
        onclick: (e) => { if (entry.full || cut(e.currentTarget)) { entry.full = !entry.full; drawHead(entry); } else if (entry.terminal && e.detail) entry.terminal.term.focus(); } }),
      live && s.project !== HUB ? keyed(pill(entry.pending === "mode" ? "Switching…" : modeName(s.mode) || "Mode", "Change mode", (anchor) => { if (!entry.pending) popover(anchor, modeItems); }), "mode") : null,
      live && s.project !== HUB ? h("span", { class: "pill-sep", "aria-hidden": "true", textContent: "·" }) : null,
      live && s.project === HUB ? h("span", { class: "folder no-prompts", title: "Permissions are skipped in a hub session" }, "No prompts") : null,
      live ? keyed(pill(entry.pending === "model" ? "Switching…" : modelName(s.model) || "Model", "Change model for this session", (anchor) => { if (!entry.pending) popover(anchor, modelItems); }), "model") : null,
      s.tree ? treeChip(s) : s.isolate || (repoName && repoName !== s.project) ? h("span", { class: "folder" }, s.isolate ? svg(UI.branch) : null, repoName) : null,
      entry.strip || null,
      entry.pending === "phone" ? h("span", { class: "connect-word", role: "status", textContent: "Connecting…" }) : null,
      s.state === "closing" ? h("span", { class: "connect-word closing-word", role: "status", textContent: "Closing…" }) : null,
      viewSeg ? keyed(viewSeg, "view-seg") : null,
      scratchButton(s, () => showScratch(s, stage)),
      phone.matches ? null : keyed(h("button", { class: "icon pane-split", type: "button", title: ids.length > 1 ? "Split, move or close this pane" : "Split this pane", "aria-haspopup": "menu", onclick: (e) => paneMenu(e.currentTarget, s.id) }, uiIcon("split")), "pane-split"),
      live || closable ? keyed(h("button", { class: "icon pane-more", title: "More: phone, close the session", "aria-label": "More for this session", "aria-haspopup": "menu", onclick: (e) => popover(e.currentTarget, moreItems()) }, uiIcon("dots")), "more") : null,
      ids.length > 1
        ? h("button", { class: "icon", title: s.alive ? "Close pane. The session keeps running." : "Close pane", "data-key": "close", onclick: () => goLayout(layoutWithout(layout, s.id)) }, uiIcon("close"))
        : s.alive && s.kind !== "claude" ? h("button", { class: "icon", title: "Stop terminal…", "data-key": "stop", onclick: () => stopTerminal(s) }, uiIcon("stop")) : null);
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
    const tool = working && a && /using|searching/.test(s.orb || ""), behind = working && s.orb === "background";
    const word = working ? (tool ? a.tool : ORB_WORDS[s.orb] || "Working") : s.state === "error" ? "Error" : s.state === "needs" ? "Needs you" : s.state === "finished" ? (s.asks ? "Asks you" : "Idle") : DOT_WORDS[shownState(s)] || "";
    const retry = s.retry && s.orb === "retrying" ? `${s.retry.said || "API error"}${s.retry.attempt ? ` · try ${s.retry.attempt}${s.retry.of ? ` of ${s.retry.of}` : ""}` : ""}` : "";
    // In a chat the question is drawn below, with its choices: the strip names the state and leaves the words to it.
    const detail = working ? (tool ? a.target : behind && a ? [a.tool, a.target].filter(Boolean).join(" ") : retry) : s.state === "error" ? s.error : (s.state === "needs" || asksYou(s)) && !entry.chat ? s.asking || "" : "";
    const state = orbState(s);
    if (!differs(entry.strip, s.state, s.orb, word, detail, working && s.turn ? s.turn.since : 0)) { setOrb(entry.stripOrb, state, word); return; }
    entry.strip.className = `pane-strip is-${s.state}${asksYou(s) ? " is-asks" : ""}`;
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
    if (!differs(rail, s.id, s.changes, s.context, s.ports, s.alive, portAsk, reviewing && reviewing.sid, feature("browser")) && !force) return;
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
      : h("span", { class: "port" }, feature("browser") && window.hubBrowser ? h("a", { class: "port-open", href: window.hubBrowser.routeFor("browser", s.id, `http://localhost:${port}/`), title: `Open localhost:${port} in the browser` }, `:${port}`, uiIcon("globe"))
          : h("a", { class: "port-open", href: `http://${host}:${port}/`, target: "_blank", rel: "noopener noreferrer", title: `Open ${host}:${port}` }, `:${port}`, uiIcon("external")),
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
      [...new Set(S.sessions.map(ownerName))].forEach((name) => {
        const others = sessionsOf(name).filter((s) => s.alive && !ids.includes(s.id));
        if (!others.length) return;
        items.push({ group: (project(name) || {}).display || name });
        others.forEach((s) => items.push({ name: s.title, dot: shownState(s), run: () => goLayout(layoutAdd(layout, s.id)) }));
      });
      items.push({ name: "New session beside this one", icon: "plus", run: () => newSession((session(activeId) || session(ids[0]) || {}).project, layoutText(layout)) });
    }
    popover(anchor, [...items, ...wholeSplit()]);
  };
  // What acts on the whole split: its board, its sizes and its shape. The split menu and each pane's menu both have it.
  const wholeSplit = () => {
    const items = [];
    if (ids.length > 1) { const board = boardFor(layout); items.push({ group: "Board" }, board ? { name: `Saved as ${board.name}`, icon: "check", say: "Rename or delete it on Home", run: () => go("#/") } : { name: "Save as a board…", icon: "board", say: "Name this split to open it again", run: () => saveBoard(layout) }); }
    if (ids.length > 1 && !phone.matches) items.push({ name: "Even out", icon: "split", run: () => { const walk = (n) => { if (isSplit(n)) { n.z = even(n.k.length); n.k.forEach(walk); } }; walk(layout); applySizes(); keepSizes(layout); refitAll(); } });
    if (ids.length > 1 && !phone.matches && feature("pane_layouts")) {
      items.push({ group: "Layout" }, ...layoutChoices(ids).map(([kind, word, tree]) => ({ name: word, icon: kind === "main" ? "splitDown" : kind === "grid" ? "board" : "split", on: sameShape(tree, layout), run: () => useShape(tree, word) })),
        { name: "Rotate", icon: "move", say: `Every pane one place on (${prefixSpec().label} o)`, run: rotatePanes });
    }
    return items;
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
      full ? { group: limitWords() } : null,
      full ? null : { name: "Split right…", icon: "split", say: "Open a session beside this one", run: pick("right") },
      full ? null : { name: "Split down…", icon: "splitDown", say: "Open a session under this one", run: pick("bottom") },
      ids.length > 1 ? { name: zoomed === id ? "Restore the split" : "Zoom", icon: "zoom", say: zoomed === id ? "Show every pane again" : "Fill the split with this pane", run: () => toggleZoom(id) } : null,
      ids.length > 1 ? { name: "Move…", icon: "move", say: "Swap it, or put it beside or under another pane", run: moveTo } : null,
      ids.length > 1 ? { name: "Close pane", icon: "close", say: here && here.alive ? "The session keeps running" : undefined, run: () => goLayout(layoutWithout(layout, id)) } : null,
      here && here.alive && here.kind !== "claude" ? { name: "Stop terminal…", icon: "stop", say: "Ends what runs in it", run: () => stopTerminal(here) } : null,
      ...wholeSplit(),
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
      return { frame: box, rect, full, label: full ? limitWords() : `${{ left: "Along the left", right: "Along the right", top: "Across the top", bottom: "Across the bottom" }[side]}`,
        drop: () => { if (full) return toast(`${limitWords()}. Close one to add another.`); goLayout(next); say(`${title} placed ${side === "top" || side === "bottom" ? `across the ${side}` : `along the ${side}`}`); } };
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
    return { frame: r, rect, full, label: full ? limitWords() : words,
      drop: () => { if (full) return toast(`${limitWords()}. Close one to add another.`); goLayout(layoutBeside(layout, tid, sid, side)); say(`${title} opened ${{ left: "to the left of", right: "to the right of", top: "above", bottom: "below" }[side]} ${(session(tid) || {}).title || "the pane"}`); } };
  };
  const drawTop = () => {
    const s = session(ids[0]);
    const p = s && ownerOf(s);
    const board = ids.length > 1 ? boardFor(layout) : null;
    setTop(ids.length > 1 ? [tail(board ? board.name : `Split · ${ids.length} sessions`)] : [p ? crumbTo(p) : null, tail(s ? (p ? bareTitle(s) : s.title) : "Session")].filter(Boolean), [
      zoomed ? h("button", { class: "btn zoom-pill", title: "One pane fills the split. z or esc shows them all again.", onclick: () => toggleZoom() }, uiIcon("zoom"), h("span", { textContent: "Zoomed" }), h("span", { class: "faint", textContent: "· Restore" })) : null,
      // At a desk each pane's head splits it (its split menu holds the board, sizes and layout too), so the header has
      // no Split of its own; a full split says so in plain words. A phone has no pane menu, so it keeps this button.
      !phone.matches ? (ids.length >= MAX_PANES ? h("span", { class: "top-count", title: `${limitWords()}. Close one to add another.`, textContent: `${ids.length} of ${MAX_PANES}` }) : null)
        : ids.length === 1 ? null : ids.length < MAX_PANES
        ? h("button", { class: "btn", title: "Open another session beside this one. ⌘-click one in the sidebar does the same.", onclick: (e) => splitMenu(e.currentTarget) }, uiIcon("split"), "Split")
        : h("button", { class: "btn", title: `${limitWords()}. Close one to add another.`, "aria-label": `${ids.length} of ${MAX_PANES} panes. Close one to add another.`, onclick: (e) => splitMenu(e.currentTarget) }, uiIcon("split"), `${ids.length} of ${MAX_PANES}`),
      h("button", { class: `icon ${panelOn() ? "on" : ""}`, title: feature("side_panel") ? "Side panel (p)" : "Agents, images and links", "aria-pressed": panelOn() ? "true" : "false", onclick: togglePanel }, uiIcon("panel")),
    ], ids.length > 1);
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
  // ── The side panel (feature_side_panel): the right panel hosts Overview, Changes, Shared and the panels other
  // features add (sidePanelHost). Off, the panel below is drawn as it always was. ──
  let hostDrawing = false, hostWas = feature("side_panel");
  const backToPane = () => focusPane(Math.max(0, ids.indexOf(activeId)));
  const panelHost = sidePanelHost({ box: sharedBox, sid: () => activeId, ctx: {
    get sid() { return activeId; }, rail, drawRail: () => drawRail(true),
    review: async (path) => {
      const sid = activeId;
      await openChanges(sid);
      const at = path && reviewing && reviewing.sid === sid ? [...reviewing.box.querySelectorAll(".review-file")].find((el) => el.getAttribute("aria-label") === path) : null;
      if (at) { at.scrollIntoView({ block: "start" }); const fold = at.querySelector(".file-fold"); if (fold) fold.focus({ preventScroll: true }); }
    },
    shared: () => { sharedKey = ""; if (!hostDrawing) drawShared(true); },
    hide: () => { if (panelOn()) togglePanel(); backToPane(); },
    back: backToPane,
    multi: () => ids.length > 1,
  } });
  const drawHost = () => { hostDrawing = true; try { panelHost.draw(); } finally { hostDrawing = false; } };
  const drawShared = guard(async (forceShow) => {
    const sp = feature("side_panel");
    sharedBox.classList.toggle("side-panel", sp);
    PANEL.max = sp ? 760 : 560;
    if (panelOn() && !sharedBox.parentNode) stage.append(sharedBox);
    if (!panelOn()) { sharedBox.remove(); if (sp) panelHost.leave(); }
    if (sp && panelOn()) drawHost();
    else if (!sp && sharedBox.querySelector(":scope > .sp-head")) { panelHost.leave(); sharedKey = ""; sharedBox.replaceChildren(); }
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
      if (sp) { if (panelHost.current() === "shared") fill(panelHost.body, retryLine("Subagents, images and links didn't load.", () => drawShared(true))); return; }
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
    if (sp && panelHost.current() !== "shared") return;  // another of the side panel's tabs is the one showing
    const crew = crews.flat();
    const owner = session(asked);
    const key = JSON.stringify([feature("artifacts"), items, crew, asked, ids.length, owner && owner.title, owner && owner.state, owner && owner.asking, owner && owner.alive]);
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
    const sharedEmpty = h("div", { class: "empty-line", textContent: `Subagents, images and links from this session show up here. ${phone.matches ? "Tap the paperclip under the terminal" : "Paste or drop a file into the terminal"} to share one.` });
    if (sp) {
      fill(panelHost.body, h("div", { class: "sp-shared" },
        feature("artifacts") && owner && owner.kind === "claude" ? h("a", { class: "quiet art-all", href: `#/s/${asked}/artifacts`, title: "Pages, documents, pictures and data this session made" }, svg(UI.artifacts), "Everything it made") : null,
        crew.length ? h("section", {}, h("h2", {}, "Subagents", running ? h("span", { class: "n", textContent: `${running} running` }) : null), crew.map(agentRow)) : null,
        items.length ? section("Shared", [sharedTimeline(items, images, opener)]) : null,
        items.length || crew.length ? null : sharedEmpty,
        owner && owner.alive ? h("button", { class: "quiet", type: "button", onclick: () => picker.click() }, uiIcon("plus"), "Share a file") : null));
      return;
    }
    fill(sharedBox,
      ids.length > 1 && owner ? h("div", { class: "shared-for" }, dot(shownState(owner)), h("span", { class: "name", dir: "auto", textContent: owner.title })) : null,
      rail,
      feature("artifacts") && owner && owner.kind === "claude" ? h("a", { class: "quiet art-all", href: `#/s/${asked}/artifacts`, title: "Pages, documents, pictures and data this session made" }, svg(UI.artifacts), "Everything it made") : null,
      crew.length ? h("section", {}, h("h2", {}, "Subagents", running ? h("span", { class: "n", textContent: `${running} running` }) : null), crew.map(agentRow)) : null,
      items.length ? section("Shared", [sharedTimeline(items, images, opener)]) : null,
      items.length || crew.length ? null : h("div", { class: "empty-line", textContent: `Subagents, images and links from this session show up here. ${phone.matches ? "Tap the paperclip under the terminal" : "Paste or drop a file into the terminal"} to share one.` }),
      owner && owner.alive ? h("button", { class: "quiet", type: "button", onclick: () => picker.click() }, uiIcon("plus"), "Share a file") : null);
  });

  ids.forEach(build);
  arrange();
  refreshScratches();
  // ── Pane layouts (feature_pane_layouts): even out, a shape from LAYOUT_SHAPES in turn, or every pane one place on ──
  const evenAll = () => {
    if (ids.length < 2 || phone.matches) return;
    const walk = (n) => { if (isSplit(n)) { n.z = even(n.k.length); n.k.forEach(walk); } };
    walk(layout); applySizes(); keepSizes(layout); refitAll();
    say("Panes evened out");
  };
  const useShape = (tree, word) => { goLayout(tree); say(`${word}`); };
  const nextLayout = () => {
    if (ids.length < 2 || phone.matches) { say("Layouts are for a split on a wider screen"); return; }
    const shapes = layoutChoices(ids), at = shapes.findIndex(([, , tree]) => sameShape(tree, layout));
    const [, word, tree] = shapes[(at + 1) % shapes.length];
    useShape(tree, word);
  };
  const rotatePanes = () => { if (ids.length < 2 || phone.matches) return; goLayout(rotatedLayout(layout)); say("Panes rotated"); };
  const focusPane = (index) => {
    const entry = entries.get(ids[index]);
    if (!entry) return;
    setActive(ids[index]);
    entry.pane.scrollIntoView({ block: "nearest" });
    if (entry.chat) return;  // focusing the message box would pop the phone's keyboard over the conversation
    if (entry.terminal) entry.terminal.term.focus();
    // On opening a closed session Resume takes the keys without a ring: a ring with nothing pressed yet reads as a double border.
    else { const first = entry.pane.querySelector(".record-top button:not(:disabled), .ended-note button"); if (first) first.focus({ preventScroll: true, focusVisible: painted ? undefined : false }); }
  };
  bind(() => inTerminal()
    ? [...(ids.length > 1 ? [[`⌥1–${ids.length}`, "pane"]] : []), [prefixSpec().label, "leave terminal"], [`${prefixSpec().label} n`, "next for you"]]
    : [["↵", "back to terminal"], ...(ids.length > 1 ? [[`1–${ids.length}`, "pane"], ["z", zoomed ? "restore" : "zoom"]] : []), ...(ids.length < MAX_PANES ? [["s", "split"]] : []), ["p", "panel"], ["esc", zoomed ? "restore" : "project"]], {
    Enter: () => focusPane(Math.max(0, ids.indexOf(activeId))), 1: () => focusPane(0), 2: () => focusPane(1), 3: () => focusPane(2), 4: () => focusPane(3), 5: () => focusPane(4), 6: () => focusPane(5),
    p: togglePanel,
    P: () => { if (!feature("side_panel")) return; if (!panelOn()) togglePanel(); requestAnimationFrame(() => panelHost.focus()); },
    s: () => { const entry = entries.get(activeId), b = (entry && entry.pane.querySelector(".pane-split")) || top_.querySelector(".btn:not(.zoom-pill)"); if (b) splitMenu(b); },
    z: () => toggleZoom(),
    Escape: () => { if (scratchShown()) hideScratch(); else if (zoomed) toggleZoom(); else goUp(); },
    jump: focusPane,
    paneDir,
    scratch: () => { const s = session(activeId); if (s && s.alive) showScratch(s, stage); else say("Only a running session has a scratch terminal"); },
    evenOut: evenAll, nextLayout, rotate: rotatePanes,
  });
  entries.forEach((entry) => { entry.terminal && entry.terminal.start(); drawHead(entry); drawStrip(entry); });
  syncZoom();
  setActive(zoomed || ids[0]);
  focusPane(Math.max(0, ids.indexOf(zoomed)));
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
    if (scratch.sid && !next.includes(scratch.sid)) hideScratch(false);
    const fresh = next.filter((id) => !before.has(id));
    fresh.forEach(build);
    arrange();
    syncZoom();
    fresh.forEach((id) => { const entry = entries.get(id); entry.terminal && entry.terminal.start(); });
    if (!fresh.length) setTimeout(refitAll, 60);  // panes that only moved take their new size
    entries.forEach((entry) => { entry.stopping = false; drawHead(entry); drawStrip(entry); });
    imagesSeen = null;
    const target = zoomed ? zoomed : fresh.length ? fresh[fresh.length - 1] : next.includes(activeId) ? activeId : next[0];
    setActive(target);
    focusPane(next.indexOf(target));
    drawTop();
    drawStatus();
    drawShared(true);
  };
  let polls = 0, shownTitles = "";
  page.update = () => {
    if (syncZoom()) focusPane(ids.indexOf(zoomed || activeId));
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
    const titles = ids.map((id) => (session(id) || {}).title).join() + ((ids.length > 1 && boardFor(layout)) || {}).name;
    if (titles !== shownTitles) { shownTitles = titles; drawTop(); }
    drawSwitcher();
    if (feature("side_panel") !== hostWas) { hostWas = !hostWas; drawShared(true); drawTop(); }
    else if (hostWas && panelOn() && sharedBox.isConnected) drawHost();
    if (++polls % 2 === 0) drawShared();
  };
  page.leave = () => { panelHost.leave(); hideScratch(false); closeChanges(); phone.removeEventListener("change", onPhoneChange); entries.forEach((entry) => entry.terminal && entry.terminal.dispose()); };
  page.selected = () => activeId;  // ⌘K acts on the pane you're in
  page.drawTop = drawTop;  // the tabs ask for it when they join or leave the header
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
    if (list.picker) list.picker();
  };
};
// On a phone a long list of files or dreams is one 44px row (feat/polish-pages): it opens the phone's own picker, with
// every item in the list's groups, where a row of chips used to hide most of them. The list itself stays for a desk.
const listPicker = (list, label) => {
  const select = h("select", { class: "picker-select", "aria-label": label, onchange: (e) => { if (e.target.value) go(e.target.value); } });
  list.picker = () => {
    const kids = [];
    let group = null;
    [...list.children].forEach((el) => {
      if (el.classList.contains("list-title")) { group = h("optgroup", { label: el.textContent }); kids.push(group); return; }
      if (el.tagName !== "A") return;
      const small = el.querySelector("small");
      const opt = h("option", { value: el.getAttribute("href"), textContent: [el.firstChild && el.firstChild.nodeType === 3 ? el.firstChild.textContent : el.textContent, small ? small.textContent : null].filter(Boolean).join(" · ") });
      opt.selected = el.classList.contains("on");
      if (group) group.append(opt); else kids.push(opt);
    });
    fill(select, kids);
    box.hidden = !select.options.length;
  };
  const box = h("label", { class: "picker", hidden: true }, h("span", { class: "picker-label", textContent: label }), select, h("span", { class: "picker-chev", "aria-hidden": "true" }, svg(UI.chev)));
  return box;
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
  root.append(search, listPicker(list, "File"), found, results, split);
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
    // Groups with their names (feat/polish-pages): what you set, what the project learned, what agents left, the index.
    const titled = (word, links) => links.length ? [h("div", { class: "list-title", textContent: word }), links] : null;
    fill(list, titled("Principles", [...part((x) => x === "ORG.md"), link("steering", "Steering"), link("pinned", "Pinned")]),
      titled("Project", part((x) => x.startsWith("project/"))),
      titled("Agents' notes", [...part((x) => x.startsWith("inbox/")), ...part((x) => x.startsWith("agents/"))]),
      titled("Index", part((x) => x === "INDEX.md" || x === "CHANGELOG.md")));
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
        data.actions.map((a) => h("div", { class: "p" }, h("span", { class: "k", dir: "auto", textContent: a.what }), h("span", { class: "v" }, h("span", { class: "mono", textContent: new Date(a.at * 1000).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) }), a.hub ? h("small", { textContent: "through Context Hub" }) : null)))) : null);
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
    if (need.state === "approved") return data.needs.fixing ? "Approved. The fixer is running" : fixAt() ? `Approved. The fixer runs at ${fixAt()}` : data.needs.fix_before_dream ? "Approved. The fixer runs just before the next dream" : "Approved. Run fixes now to start the fixer";
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
    const reject = h("button", { class: "retry risky", "data-key": `reject:${i}`, textContent: "Reject", title: "No dream says it again.", onclick: askReject(need) });
    const acts = need.state === "open" ? (fixable ? [approve("Approve fix"), reject] : [done, reject])
      : need.state === "approved" ? [reject] : need.state === "fixed" ? [done] : need.state === "stopped" ? (fixable ? [approve("Approve again"), done, reject] : [done, reject]) : [];
    return acts.length ? h("div", { class: "need-acts" }, acts) : null;
  };
  const needsBox = () => {
    const open = data.needs.open;
    if (!open.length && !data.needs.problem) return null;
    const whence = (need) => [`Asked on ${stemDay(stemOf(need.from))}`, need.said > 1 ? `${need.said} times, last on ${stemDay(stemOf(need.last))}` : null].filter(Boolean).join(", ");
    const shared = open.length && open.every((n) => whence(n) === whence(open[0])) ? whence(open[0]) : "";
    const SHOW = 3, rest = needsAll || open.length <= SHOW + 1 ? 0 : open.length - SHOW;
    const yours = open.filter((n) => n.state === "open" || n.state === "stopped").length;
    const approved = open.some((n) => n.state === "approved");
    return h("section", { class: "callout needs", "aria-labelledby": "needs-title" },
      h("header", { class: "needs-head" }, h("h2", { id: "needs-title", textContent: yours ? questionsWord(yours) : "Dream questions" }),
        shared ? h("span", { class: "needs-from", textContent: shared }) : null,
        approved && !data.needs.fixing ? h("button", { class: "retry need-run", "data-key": "fix-now", textContent: "Run fixes now", onclick: once("Starting…", async () => { await api(`/api/p/${P(name)}/dream/fix`, {}); say("The fixer is running"); await loadDreams(); }) }) : null),
      data.needs.problem ? h("p", { role: "alert", textContent: data.needs.problem }) : null,
      open.slice(0, open.length - rest).map((need, i) => {
        const [sentence, evidence] = needParts(need.text);
        const state = needState(need);
        return askRow({ nav: `need:${i}`, cls: "need-row", tag: "p", title: sentence, closed: need.state === "fixed", state: ["approved", "fixing"].includes(need.state) ? "working" : "needs",
          line: [shared ? null : h("span", { textContent: whence(need) }), evidence ? h("span", { class: "mono", dir: "auto", textContent: evidence }) : null, h("span", { dir: "auto", textContent: needWho(need) })], lineCls: "need-sub",
          extra: state ? h("p", { class: `need-state ${need.state}`, dir: "auto", role: "status", textContent: state }) : null, acts: needActs(need, i) });
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
    h("div", { class: "sub", textContent: [item.file !== item.quote && item.action !== "carry" ? item.file : null, item.action === "carry" ? null : item.action, `from ${stemDay(item.from.replace("-proposal.md", ""))}`,
      item.waiting ? `approved ${agoWords(item.at)}` : null, item.waiting === "you" ? "waits for you" : item.waiting === "a session" ? "waits for a session" : null,
      item.waiting || item.declined ? null : item.ticked ? "ticked, not applied" : item.left ? "passed over once" : "not decided"].filter(Boolean).join(" · ") }),
    item.way ? h("div", { class: `fate ${item.dead ? "no" : ""}` }, h("span", { dir: "auto", textContent: item.way })) : null,
    item.waiting ? h("div", { class: "kept-acts" },
      item.dead ? null : item.waiting === "you" ? h("button", { class: "retry", "data-key": `yours:${item.id}`, textContent: "Open a terminal for it", onclick: openIn("yours") })
        : h("button", { class: "retry", "data-key": `session:${item.id}`, textContent: "Start a session for it", onclick: openIn("session") }),
      h("button", { class: "retry", "data-key": `withdraw:${item.id}`, textContent: "Take back", onclick: takeBack(item) })) : null,
    item.declined ? h("button", { class: "retry", "data-key": `forget:${item.id}`, textContent: "Allow it to be proposed again", onclick: kitSays("forget", { item: item.item }) }) : null);
  const tailBox = h("div", { class: "dream-tail" });
  list.classList.add("dream-list");
  root.append(listPicker(list, "Dream"), metaBox, h("div", { class: "split" }, list, detail), tailBox);
  const stats = () => {
    const at = data.metrics.findLastIndex((m) => m.date === current.file.slice(0, 10));
    if (at < 0) return null;
    const [last, before] = [data.metrics[at], data.metrics[at - 1]];
    const delta = (a, b) => {
      if (b === undefined || !b) return null;
      const pct = Math.round((a - b) / b * 100);
      return pct ? h("em", { class: pct < 0 ? "good" : "bad", textContent: `${pct > 0 ? "+" : "−"}${Math.abs(pct)}% vs the dream before` }) : null;
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
      nodes.push(h("section", { class: "sec" }, h("h2", { textContent: "Dream questions" }),
        h("p", { class: "sec-note", textContent: still ? `${still} ${still === 1 ? "is" : "are"} still open, listed at the top. Questions for you, not memory changes.` : "Questions for you, not memory changes." }),
        said.map((n) => { const [sentence, evidence] = needParts(n.text); return askRow({ cls: "need-row", tag: "p", title: `${n.resolved ? "Put right: " : ""}${sentence}`, closed: !n.resolved, state: n.resolved ? "finished" : "ended",
          line: [n.resolved ? null : h("span", { textContent: "Closed since" }), evidence ? h("span", { class: "mono", dir: "auto", textContent: evidence }) : null], lineCls: "need-sub" }); })));
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
      if (parts[1]) nodes.push(h("div", { class: "callout" }, h("h2", { textContent: "Questions for you, outside memory" }), markdown(parts[1])));
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
      stemDay(d.file.replace("-proposal.md", "")), h("small", { textContent: d.state }))),
      // From before the kit kept a record of proposals: the store still holds them, to read.
      data.earlier.length ? h("div", { class: "list-title", textContent: "Earlier" }) : null,
      data.earlier.map((file) => h("a", { class: file === selected ? "on" : "", "aria-current": file === selected ? "page" : undefined, href: `#/p/${P(name)}/dreams/${file}`, title: file.replace("-proposal.md", ""), textContent: stemDay(file.replace("-proposal.md", "")) })));
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
const CATCH_KIND = { proposal: "Dream proposal", need: "Dream question", inbox: "Inbox proposal" };
// The page (feat/polish-pages): what it is and whether it acts, then what waits on you, project by project, then its last
// runs. What waits is every project's dream questions and proposals, in Home's own rows: the ones its last run judged
// carry its verdict and the choices, and the ones it hasn't seen yet say so and open Dreams. So the page is never empty
// while a dream has left you something, even before its first run.
function pageCatcher() {
  const root = h("div", { class: "page catcher" });
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
    const btn = (verdict, word) => h("button", { class: `retry ${verdict === "reject" ? "risky" : ""}`, type: "button", "data-key": `${verdict}:${i}`, textContent: word, onclick: decide(item, verdict) });
    if (item.kind === "inbox") return h("div", { class: "need-acts" }, h("a", { class: "retry", href: `#/p/${P(item.store)}/memory/${item.file}`, textContent: "Read it" }), btn("approve", "Leave it to the next dream"));
    const acts = item.kind === "need" && item.who === "you" ? [btn("done", "Done"), btn("reject", "Reject")]
      : [btn("approve", item.kind === "need" ? "Approve fix" : "Approve"), btn("reject", "Reject")];
    if (item.result === "recommended" && item.verdict === "reject") acts.reverse();  // what it recommends comes first
    return h("div", { class: "need-acts" }, acts);
  };
  // A judged item: the question, a line of what it is and whose, its verdict with why, and the choices.
  const row = (item, i) => askRow({ nav: `catch:${i}`, cls: "need-row catch-row", tag: "p", closed: !(item.waits && item.open), title: sentence(item),
    state: item.result === "recommended" ? "needs" : "needs",
    line: [h("span", { class: "catch-kind", textContent: CATCH_KIND[item.kind] }), ...facts(item).map((f) => h("span", { dir: "auto", textContent: f }))], lineCls: "need-sub",
    extra: [item.reason ? h("p", { class: `catch-why ${item.verdict || ""}`, dir: "auto" },
      h("b", { textContent: item.result === "recommended" ? `Recommends: ${CATCH_VERDICT[item.verdict].toLowerCase()}. ` : CATCH_DID[item.verdict] && item.by === "dream-catcher" ? `${CATCH_DID[item.verdict]}. ` : "" }),
      h("span", { textContent: item.reason }), item.evidence ? h("small", { textContent: ` Checked: ${item.evidence}` }) : null) : null,
      (item.result === "failed" || item.result === "skipped") ? h("p", { class: "need-state", role: "status", textContent: item.said }) : null,
      !item.waits && item.said ? h("p", { class: "need-state fixed", role: "status", textContent: `${item.by ? "" : "You: "}${item.said}` }) : null,
      item.waits && !item.open ? h("p", { class: "need-state", textContent: "Decided elsewhere since." }) : null],
    acts: actions(item, i) });
  const groupHead = (store, n) => h("header", { class: "catch-project-head" }, project(store) ? mark(project(store), 15) : null, h("h3", { dir: "auto", textContent: projectName(store) }),
    n ? h("span", { class: "fold-n", textContent: String(n) }) : null, project(store) ? h("a", { class: "retry", href: `#/p/${P(store)}/dreams`, textContent: "Open Dreams" }) : null);
  const byProject = (items) => [...new Set(items.map((i) => i.store))].map((store) => h("section", { class: "catch-project", "aria-label": projectName(store) },
    groupHead(store), items.filter((i) => i.store === store).map((item) => row(item, data.run.items.indexOf(item)))));
  // Everything that waits, by project: the run's verdicts where it judged that project, else what its dreams left, unseen.
  const waitingNow = () => {
    const run = data.run, judged = run && run.phase === "settled" ? run.items.filter((i) => i.waits && i.open) : [];
    const stores = [...new Set([...judged.map((i) => i.store), ...S.projects.filter((p) => !p.hub && dreamRows(p, true).length).map((p) => p.name)])];
    return stores.map((store) => {
      const mine = judged.filter((i) => i.store === store), p = project(store);
      const rows = mine.length ? mine.map((item) => row(item, run.items.indexOf(item)))
        : p ? dreamRows(p, true).map((r) => askRow({ ...r, line: r.nav.endsWith(":more") ? r.line : `${r.line} · not checked yet`, meta: r.at ? h("time", { textContent: ago(r.at) }) : null })) : [];
      return { store, n: mine.length || (p ? dreamRows(p, true).filter((r) => !r.nav.endsWith(":more")).length + Math.max(0, (p.needs || 0) - Math.min(3, (p.asks || []).length)) : 0), rows };
    }).filter((g) => g.rows.length);
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
  const runWords = (r) => r.phase === "running" ? "Running now" : r.phase === "finished" ? "Carrying out its verdicts" : r.phase === "stopped" ? "Stopped before it finished"
    : `${r.approved} approved · ${r.rejected} rejected · ${r.left} left for you`;
  const runsList = () => {
    const recent = data.recent || [];
    if (!recent.length) return null;
    return h("section", { class: "catch-runs", "aria-labelledby": "catch-runs-t" }, h("h2", { id: "catch-runs-t", textContent: "Last runs" }),
      h("div", { class: "run-rows" }, recent.map((r) => h("div", { class: `run-row ${r.phase}` },
        h("time", { dateTime: r.started ? new Date(r.started * 1000).toISOString() : undefined, title: r.started ? new Date(r.started * 1000).toLocaleString("en-GB") : undefined, textContent: r.started ? whenShort(r.started) : "" }),
        h("span", { class: "run-what", textContent: runWords(r) }),
        h("span", { class: "run-how", textContent: r.phase === "settled" ? (r.acted ? "Acted" : "Recommended") : "" })))));
  };
  const draw = () => {
    const c = S.catcher || {}, run = data.run;
    const running = c.phase === "running" || (run && run.phase === "running");
    setTop([tail("Dream Catcher")], [running ? null : h("button", { class: "btn primary", type: "button", "data-key": "catch-now", textContent: "Catch dreams now", onclick: start })].filter(Boolean));
    if (differs(head, data.auto, data.own, data.scope, running, status(), run && run.sid)) fill(head,
      h("p", { class: "catcher-lead", textContent: "Checks every project's open dream proposals and questions against its memory and code, decides what it can, and leaves you the rest with a reason." }),
      h("div", { class: "dream-meta" },
        h("button", { class: `switch ${data.auto ? "on" : ""}`, type: "button", role: "switch", "aria-checked": data.auto ? "true" : "false", "aria-label": "Act on its verdicts", onclick: () => setAuto(!data.auto) }),
        h("span", { textContent: data.auto ? "Acts on its verdicts" : "Only recommends" }),
        h("span", { class: "faint", textContent: `Reads ${data.scope.length} ${data.scope.length === 1 ? "project" : "projects"}` })),
      h("p", { class: "dream-note said", role: "status" }, h("span", { textContent: status() }), " ", running && run && run.sid ? h("a", { class: "retry", href: `#/s/${run.sid}`, textContent: "Watch it" }) : null),
      data.own.ready ? null : h("p", { class: "dream-note" }, "It has no memory of its own yet, so it doesn't learn across runs. To give it one, run ", h("code", { textContent: data.own.install }), " in a terminal. ", copyButton(data.own.install)));
    const groups = waitingNow();
    if (!differs(body, run, groups.map((g) => [g.store, g.n]), S.projects.map((p) => [p.name, p.needs, p.asks, openReview(p), p.waits]), data.recent)) return;
    const handled = run ? run.items.filter((i) => !(i.waits && i.open)) : [];
    const recommended = run && run.phase === "settled" ? run.items.filter((i) => i.waits && i.open && i.result === "recommended").length : 0;
    const total = groups.reduce((n, g) => n + g.n, 0);
    fill(body,
      run && run.problems && run.problems.length ? h("div", { class: "callout", role: "alert" }, h("p", { textContent: `Its verdicts couldn't be read, so everything is left for you: ${run.problems.join("; ")}` })) : null,
      run && run.skipped.length ? h("p", { class: "dream-note", textContent: `Left alone this time: ${run.skipped.map((s) => `${projectName(s.store)} (${s.why})`).join(", ")}` }) : null,
      run && run.applying.length ? run.applying.map((a) => h("p", { class: "dream-note said" }, h("span", { textContent: `${projectName(a.store)}: ${a.said}` }), " ", a.sid ? h("a", { class: "retry", href: `#/s/${a.sid}`, textContent: "Open it" }) : null)) : null,
      h("section", { class: "catch-wait", "aria-labelledby": "catch-wait-title" },
        h("header", { class: "needs-head" }, h("h2", { id: "catch-wait-title" }, "Waiting on you", total ? h("span", { class: "h-n need", textContent: String(total) }) : null),
          recommended ? h("button", { class: "btn primary need-run", type: "button", "data-key": "accept-all", textContent: `Accept all recommended (${recommended})`, onclick: acceptAll }) : null),
        groups.length ? groups.map((g) => h("section", { class: "catch-project", "aria-label": projectName(g.store) }, groupHead(g.store, g.n), h("div", { class: "qlist" }, g.rows)))
          : h("p", { class: "empty-line", textContent: run && run.phase === "settled" && run.items.length ? "It decided everything in its last run." : "No project has a dream question or proposal waiting." })),
      runsList(),
      run && run.report ? h("details", { class: "sec catch-report", open: run.phase !== "settled" || !total }, h("summary", { textContent: "Its last report" }), h("div", { class: "catch-report-text", dir: "auto", textContent: run.report })) : null,
      handled.length ? h("details", { class: "sec carried" }, h("summary", { textContent: `${handled.length} decided in its last run` }), byProject(handled)) : null);
  };
  page.update = () => { const c = S.catcher || {}; const now = JSON.stringify([c.run, c.phase, c.waiting, c.settled, c.auto]); if (now !== sig) { sig = now; load(); } else if (data) draw(); };
  sig = JSON.stringify([(S.catcher || {}).run, (S.catcher || {}).phase, (S.catcher || {}).waiting, (S.catcher || {}).settled, (S.catcher || {}).auto]);
  setTop([tail("Dream Catcher")]);
  const settled = loadingIn(body, "Loading…");
  load().finally(settled);
}

// ── Settings: hub-wide, kept in config.json under "settings", the same on every device ──
// GET /api/settings gives the values, the schema the page is built from, and each default. A control saves the moment
// it changes, says "Saved" beside itself or why not, and every change fills SETTINGS and fires "hub:settings".
let settingsData = null;
const BUILT_IN_MODELS = MODELS.slice();  // the picker's own list, for when Settings holds none
const putSettings = async (body) => {
  const response = await fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => { throw known(NO_ANSWER); });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(known(data.error || NO_ANSWER), { status: response.status });
  return data;
};
const announceSettings = () => window.dispatchEvent(new Event("hub:settings"));
const takeSettings = (data) => {
  const first = !settingsData, changed = first || JSON.stringify(data.values) !== JSON.stringify(settingsData.values);
  settingsData = data;
  SETTINGS = { ...data.values };
  if (changed) announceSettings();
  // New sessions start from these: a composer drawn before they arrived is drawn again.
  if (first && route().name === "project" && route().tab === "new") { page.key = ""; render(); }
};
const loadSettings = async () => { try { takeSettings(await api("/api/settings")); } catch { /* the page keeps today's behaviour until they load */ } };
// saveSettings({name: value}): keep them, fill SETTINGS and fire "hub:settings". Other features call it too.
const saveSettings = async (changes) => { const data = await putSettings(changes); takeSettings(data); return data; };
window.saveSettings = saveSettings;
// While a control is dragged or hovered, the page shows its value without keeping it; letting go keeps it or puts it back.
const previewSetting = (name, value) => { SETTINGS = { ...SETTINGS, [name]: value }; announceSettings(); };
const unpreviewSettings = () => { if (settingsData) { SETTINGS = { ...settingsData.values }; announceSettings(); } };
// The model picker offers the list in Settings when there is one. MODELS is changed in place, so every picker follows it.
window.addEventListener("hub:settings", () => {
  const own = pref("models", []);
  const next = own.length ? own.map((m) => ({ id: m.id, name: m.name || m.id, say: m.say || "" })) : BUILT_IN_MODELS;
  if (JSON.stringify(next) !== JSON.stringify(MODELS)) MODELS.splice(0, MODELS.length, ...next);
});
// A change made on another device arrives when this one is looked at again, and at least once a minute.
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && settingsData) loadSettings(); });
setInterval(() => { if (document.visibilityState === "visible" && route().name !== "settings") loadSettings(); }, 60000);
let keyCatcher = null;

// What a project's new sessions start with: its own last choice (kept on the server, so phone and desk agree), else the
// hub's defaults, else what this browser remembered before there were defaults, else Auto and the first model.
const knownModel = (id) => MODELS.some((m) => m.id === id);
const startPrefs = (name) => {
  const own = (project(name) || {}).start, legacy = saved.get(`prefs:${name}`, {}) || {};
  const firstModel = knownModel("opus") ? "opus" : (MODELS[0] || {}).id || "";
  if (own) return { mode: own.mode || "auto", model: knownModel(own.model) ? own.model : pref("default_model", "") || firstModel, effort: own.effort || "", code: !!own.code };
  const model = [pref("default_model", ""), legacy.model].find(knownModel) || firstModel;
  return { mode: pref("default_mode", "") || legacy.mode || "auto", model, effort: pref("default_effort", "") || legacy.effort || "", code: !!legacy.code };
};
const keepStart = (name, prefs) => {
  const choice = { mode: prefs.mode, model: prefs.model, effort: prefs.effort, code: !!prefs.code };
  saved.set(`prefs:${name}`, choice);
  const p = project(name);
  if (!p || p.hub) return;
  p.start = choice;
  api(`/api/p/${P(name)}/start`, choice).catch(() => { /* this browser still remembers it */ });
};

const SETTING_PAGES = () => [
  ...((settingsData && settingsData.sections) || [{ id: "appearance", title: "Appearance" }, { id: "notifications", title: "Notifications & sound" }, { id: "sessions", title: "New sessions" }, { id: "terminal", title: "Terminal" }, { id: "sidebar", title: "Sidebar & navigation" }, { id: "catcher", title: "Dream Catcher" }, { id: "features", title: "Features" }]),
  { id: "keyboard", title: "Keyboard" }, { id: "health", title: "Health" }, { id: "access", title: "Access" }, { id: "about", title: "About" },
];
// Settings' sections, in three groups (feat/nav): how the hub is for you, how sessions run, and the hub itself. A section
// the server adds later joins Sessions.
const SETTING_GROUPS = [["You", ["appearance", "notifications", "keyboard"]], ["Sessions", ["sessions", "terminal", "sidebar", "catcher", "features"]], ["System", ["health", "access", "about"]]];
const settingGroups = () => {
  const all = SETTING_PAGES(), known = SETTING_GROUPS.flatMap(([, ids]) => ids);
  return SETTING_GROUPS.map(([word, ids]) => [word, [...ids.map((id) => all.find((x) => x.id === id)).filter(Boolean), ...(word === "Sessions" ? all.filter((x) => !known.includes(x.id)) : [])]]);
};
const SETTING_LEADS = {
  appearance: "How the hub looks on this and every other device.",
  notifications: "What tells you, and how. System notifications appear even when the hub isn't in front.",
  sessions: "What a new session starts with. A project keeps the choice its last session started with, and that wins.",
  terminal: "How a session's terminal looks and copies, and the lines it tells you about.",
  sidebar: "How the sidebar lists sessions and projects, and how many panes a split holds.",
  catcher: "The Dream Catcher reads what dreams left for you and recommends what to do with each.",
  features: "Turn any of the newer parts of the hub on or off. Off, the hub works as it did before it.",
  keyboard: "Every key the hub knows, the same as the ? sheet. The key that leaves a terminal is yours to choose.",
  health: "What's wrong with the config, and whether the parts the hub needs are in place.",
  access: "Who can reach this hub, and where. These are set by install.sh, so they're only shown here.",
  about: "The version you run, what changed, and how to support the project.",
};
const ACCENTS = [["", "Cobalt"], ["#7c5cff", "Violet"], ["#0891b2", "Ocean"], ["#d97706", "Amber"], ["#64748b", "Slate"]];
const keyWords = (combo) => combo.split("+").map((k) => ({ Control: "⌃", Alt: "⌥", Shift: "⇧", Meta: "⌘", Space: "Space" }[k] || k));
const comboOf = (e) => {
  if (["Control", "Alt", "Shift", "Meta"].includes(e.key)) return "";
  const named = e.code === "Backquote" ? "`" : e.code === "Space" ? "Space" : e.code === "Tab" ? "Tab" : /^Key[A-Z]$/.test(e.code) ? e.code.slice(3).toLowerCase() : /^Digit\d$/.test(e.code) ? e.code.slice(5) : e.key.length === 1 ? e.key : e.key;
  return [e.ctrlKey && "Control", e.altKey && "Alt", e.shiftKey && "Shift", e.metaKey && "Meta", named].filter(Boolean).join("+");
};

// The first-run card on Home: shown from the first time the hub finds no settings, until it's dismissed.
const welcomeKey = () => settingsData ? [settingsData.welcome, settingsData.values, saved.get("hub.settingsSeen", {})] : null;
const welcomeCard = () => {
  if (!settingsData || settingsData.welcome !== "open") return null;
  const v = settingsData.values, d = settingsData.defaults, seen = saved.get("hub.settingsSeen", {});
  const changed = (section) => settingsData.schema.some((item) => item.section === section && JSON.stringify(v[item.name]) !== JSON.stringify(d[item.name]));
  const steps = [["appearance", "Pick a theme and accent"], ["notifications", "Choose what tells you, and how"], ["sessions", "Set what new sessions start with"], ["health", "Check the hub's health"]];
  const done = (id) => changed(id) || !!seen[id];
  const dismiss = once("…", async () => { settingsData = { ...settingsData, welcome: "done" }; render(); await api("/api/settings/welcome", {}); });
  return h("section", { class: "panel welcome", "aria-labelledby": "welcome-title" },
    h("header", {}, h("h2", { id: "welcome-title", textContent: "Make the hub yours" }), h("button", { class: "icon", type: "button", title: "Dismiss for good", "data-key": "welcome-dismiss", onclick: dismiss }, uiIcon("close"))),
    h("ul", { class: "welcome-list" }, steps.map(([id, text]) => h("li", { class: done(id) ? "done" : "" },
      h("a", { href: `#/settings/${id}`, "data-key": `welcome:${id}` }, h("span", { class: "welcome-tick", "aria-hidden": "true" }, done(id) ? svg(UI.check) : null), h("span", { textContent: text }), done(id) ? h("span", { class: "sr-only", textContent: ", done" }) : null)))),
    steps.every(([id]) => done(id)) ? h("div", { class: "welcome-end" }, h("span", { textContent: "All set." }), h("button", { class: "btn", type: "button", textContent: "Done", onclick: dismiss })) : null);
};

// After an update, once: what changed since the version you last saw. About lists it too.
const newsBanner = h("div", { class: "banner update news", hidden: true });
updateBanner.after(newsBanner);
const paintNews = (about) => {
  const n = (about && about.news || []).length;
  if (!n || route().name === "settings") { newsBanner.hidden = true; return; }
  fill(newsBanner, h("span", { textContent: `Context Hub was updated: ${n} ${n === 1 ? "change" : "changes"} since you last looked.` }),
    h("a", { class: "retry", href: "#/settings/about", textContent: "What's new" }),
    h("button", { class: "retry", type: "button", textContent: "Dismiss", onclick: () => { newsBanner.hidden = true; api("/api/settings/seen", {}).catch(() => {}); } }));
  newsBanner.hidden = false;
};
api("/api/settings/about").then(paintNews, () => {});

function pageSettings() {
  const root = h("div", { class: "page settings" });
  const nav = h("nav", { class: "set-nav", "aria-label": "Settings" });
  const body = h("div", { class: "set-body" });
  root.append(nav, body);
  view.append(root);
  bind([["esc", "back"]], { Escape: () => go(phone.matches && !listOnly() ? "#/settings" : "#/") });
  const said = {};  // a row's last word: "Saved", or why not
  let shownTab = "", snapshot = null, health = null, about = null, healthAt = 0, sig = "";
  const tabNow = () => { const t = route().tab; return SETTING_PAGES().some((s) => s.id === t) ? t : "appearance"; };
  // On a phone, #/settings is the list of sections and each section a page under it, with Settings to go back.
  const listOnly = () => phone.matches && !SETTING_PAGES().some((s) => s.id === route().tab);
  let topSig = "";
  const drawTop = () => {
    const tab = tabNow(), sig = JSON.stringify([listOnly(), tab, phone.matches]);
    if (sig === topSig) return;
    topSig = sig;
    root.classList.toggle("list-only", listOnly());
    if (phone.matches && !listOnly()) setTop([h("a", { class: "crumb", href: "#/settings", "data-key": "settings-back" }, h("span", { class: "t", textContent: "Settings" })), tail((SETTING_PAGES().find((x) => x.id === tab) || {}).title || "")]);
    else setTop([tail("Settings")]);
  };
  drawTop();
  const sayIn = (name, text, bad) => {
    said[name] = { text, bad };
    const el = body.querySelector(`[data-said="${CSS.escape(name)}"]`);
    if (el) { el.textContent = text; el.classList.toggle("bad", !!bad); el.classList.add("on"); el.setAttribute("role", bad ? "alert" : "status"); }
    clearTimeout(sayIn[name]);
    if (!bad) sayIn[name] = setTimeout(() => { delete said[name]; const now = body.querySelector(`[data-said="${CSS.escape(name)}"]`); if (now) now.classList.remove("on"); }, 1800);
  };
  const save = async (changes, name = Object.keys(changes)[0]) => {
    try { await saveSettings(changes); sayIn(name, "Saved"); draw(true); return true; }
    catch (error) { unpreviewSettings(); sayIn(name, error.message, true); draw(true); return false; }
  };
  const radioKeys = (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const group = [...e.currentTarget.parentNode.querySelectorAll("[role=radio]")], at = group.indexOf(e.currentTarget);
    const next = group[(at + (["ArrowRight", "ArrowDown"].includes(e.key) ? 1 : group.length - 1)) % group.length];
    next.focus(); next.click();
  };
  const value = (name) => settingsData.values[name];

  // One control for each kind in the schema.
  const control = (item) => {
    const name = item.name, now = value(name), id = `set-${name}`;
    if (item.kind === "choice" || item.kind === "model") {
      const choices = item.kind === "model" ? [["", "Last used"], ...MODELS.map((m) => [m.id, m.name])] : item.choices;
      return h("div", { class: "seg", role: "radiogroup", "aria-labelledby": `${id}-label` }, choices.map(([v, text]) => h("button", { type: "button", role: "radio", class: now === v ? "on" : "", "aria-checked": now === v ? "true" : "false", tabIndex: now === v ? 0 : -1, "data-key": `${id}:${v}`, textContent: text,
        onkeydown: radioKeys, onclick: () => { if (now !== v) save({ [name]: v }); } })));
    }
    if (item.kind === "switch") {
      const flip = async () => {
        if (name === "dream_catcher_auto" && !now && !(await confirmStep({ title: "Let the Dream Catcher act for you?", body: "Its approvals and rejections are carried out as soon as a run ends. Everything it does is logged as the Dream Catcher's. What it isn't sure of, and what is always yours, waits for you.", yes: "Let it act", no: "Only recommend" }))) return;
        await save({ [name]: !now });
        if (name === "dream_catcher_auto") tick();
      };
      return h("button", { type: "button", class: `switch ${now ? "on" : ""}`, role: "switch", "aria-checked": now ? "true" : "false", "aria-labelledby": `${id}-label`, "data-key": id, onclick: flip });
    }
    if (item.kind === "number") {
      const shown = (v) => item.unit === "%" ? `${Math.round(v * 100)}%` : `${v}${item.unit || ""}`;
      const out = h("output", { class: "set-value", for: id, textContent: shown(now) });
      const live = item.section === "appearance" || item.section === "terminal" || name === "sound_volume";
      const range = h("input", { type: "range", id, min: item.min, max: item.max, step: item.step, value: now, "aria-labelledby": `${id}-label`, "aria-valuetext": shown(now), "data-key": id,
        oninput: (e) => { const v = Number(e.target.value); out.textContent = shown(v); e.target.setAttribute("aria-valuetext", shown(v)); if (live) previewSetting(name, v); },
        onchange: (e) => { const v = Number(e.target.value); if (v !== value(name)) save({ [name]: v }); },
        onkeydown: (e) => { if (e.key === "Escape") { e.stopPropagation(); e.target.value = value(name); out.textContent = shown(value(name)); unpreviewSettings(); } } });
      return h("div", { class: "set-range" }, range, out);
    }
    if (item.kind === "colour") {
      const custom = now && !ACCENTS.some(([v]) => v === now);
      const picker = h("input", { type: "color", value: custom ? (now.length === 7 ? now : "#2f62f5") : "#2f62f5", "aria-label": "Your own colour", tabIndex: -1,
        oninput: (e) => previewSetting(name, e.target.value), onchange: (e) => save({ [name]: e.target.value }) });
      const swatch = ([v, label], i) => h("button", { type: "button", role: "radio", class: `swatch ${now === v ? "on" : ""}`, "aria-checked": now === v ? "true" : "false", "aria-label": label, title: label, tabIndex: now === v || (!ACCENTS.some(([x]) => x === now) && i === 0) ? 0 : -1, "data-key": `${id}:${v}`,
        style: `--sw:${v || "#2f62f5"}`, onkeydown: radioKeys, onclick: () => { if (now !== v) save({ [name]: v }); },
        onpointerenter: () => { if (matchMedia("(hover: hover)").matches) previewSetting(name, v); }, onpointerleave: () => { if (matchMedia("(hover: hover)").matches) unpreviewSettings(); } });
      return h("div", { class: "swatches", role: "radiogroup", "aria-labelledby": `${id}-label` }, ACCENTS.map(swatch),
        h("label", { class: `swatch own ${custom ? "on picked" : ""}`, title: "Custom colour", style: custom ? `--sw:${now}` : "" }, picker, custom ? null : h("span", { class: "own-plus", "aria-hidden": "true" }, uiIcon("plus")), h("span", { class: "sr-only", textContent: "Custom colour" })));
    }
    if (item.kind === "key") {
      const recording = h("button", { type: "button", class: "btn key-rec", "aria-labelledby": `${id}-label`, "aria-describedby": `${id}-help`, "data-key": id }, h("span", { class: "caps" }, keyWords(now).map((k) => h("kbd", { textContent: k }))), h("span", { class: "faint", textContent: "Change" }));
      recording.onclick = () => {
        fill(recording, h("span", { textContent: "Press the keys…" }));
        recording.classList.add("on");
        const take = (e) => {
          e.preventDefault(); e.stopPropagation();
          if (e.key === "Tab" && !e.ctrlKey && !e.altKey && !e.metaKey) { done(); return; }
          if (e.key === "Escape") { done(); return; }
          const combo = comboOf(e);
          if (!combo) return;
          done();
          if (combo !== value(name)) save({ [name]: combo });
        };
        const done = () => { keyCatcher = null; recording.removeEventListener("blur", done); recording.classList.remove("on"); draw(true); };
        keyCatcher = take;
        recording.addEventListener("blur", done);
      };
      return recording;
    }
    if (item.kind === "projects") {
      if (!S.projects.length) return h("span", { class: "faint", textContent: "No projects yet." });
      return h("div", { class: "set-checks", role: "group", "aria-labelledby": `${id}-label` }, S.projects.map((p) => h("label", { class: "check" },
        h("input", { type: "checkbox", checked: now.includes(p.name), "data-key": `${id}:${p.name}`, onchange: (e) => save({ [name]: e.target.checked ? [...now, p.name] : now.filter((x) => x !== p.name) }) }),
        mark(p, 15), h("span", { dir: "auto", textContent: p.display }))));
    }
    if (item.kind === "models") return modelsEditor(item);
    if (item.kind === "triggers") return triggersEditor(item, { now, save, redraw: () => draw(true) });
    if (SETTING_CONTROLS[item.kind]) return SETTING_CONTROLS[item.kind](item, { save, sayIn, value });
    return h("span", { class: "faint", textContent: JSON.stringify(now) });
  };

  // The model list: empty means the built-in one. Editing starts from what the picker shows now.
  let editingModels = null;
  const modelsEditor = (item) => {
    const own = value("models");
    if (!editingModels) {
      return h("div", { class: "models-view" },
        h("ul", { class: "models-list" }, (own.length ? own : BUILT_IN_MODELS).map((m) => h("li", {}, h("b", { textContent: m.name }), h("code", { textContent: m.id }), m.say ? h("span", { class: "faint", textContent: m.say }) : null))),
        h("div", { class: "set-acts" }, h("button", { type: "button", class: "btn", "data-key": "models-edit", textContent: own.length ? "Edit the list" : "Use my own list", onclick: () => { editingModels = (own.length ? own : BUILT_IN_MODELS).map((m) => ({ ...m })); draw(true); const first = body.querySelector(".models-edit input"); if (first) first.focus(); } }),
          own.length ? h("button", { type: "button", class: "quiet", "data-key": "models-reset", textContent: "Go back to the built-in list", onclick: () => save({ models: [] }, "models") }) : null));
    }
    const rows = editingModels;
    const field = (m, key, label, width) => h("input", { type: "text", value: m[key] || "", placeholder: label, "aria-label": label, spellcheck: false, style: width ? `flex:${width}` : "", oninput: (e) => { m[key] = e.target.value; } });
    const keepList = async () => {
      const list = rows.map((m) => ({ id: (m.id || "").trim(), name: (m.name || "").trim(), say: (m.say || "").trim() })).filter((m) => m.id || m.name);
      if (await save({ models: list }, "models")) { editingModels = null; draw(true); }
    };
    return h("div", { class: "models-edit" },
      rows.map((m, i) => h("div", { class: "model-row" }, field(m, "id", "Model id, such as opus", 2), field(m, "name", "Name shown", 2), field(m, "say", "One line about it", 3),
        h("button", { type: "button", class: "icon", title: `Remove ${m.name || m.id || "this model"}`, onclick: () => { rows.splice(i, 1); draw(true); } }, uiIcon("close")))),
      h("div", { class: "set-acts" },
        rows.length < 12 ? h("button", { type: "button", class: "quiet", onclick: () => { rows.push({ id: "", name: "", say: "" }); draw(true); const inputs = body.querySelectorAll(".model-row:last-child input"); if (inputs[0]) inputs[0].focus(); } }, uiIcon("plus"), "Add a model") : null,
        h("span", { class: "grow" }),
        h("button", { type: "button", class: "btn", textContent: "Cancel", onclick: () => { editingModels = null; draw(true); } }),
        h("button", { type: "button", class: "btn primary", textContent: "Keep this list", onclick: keepList })));
  };

  const row = (item) => {
    const id = `set-${item.name}`, s = said[item.name], many = (item.choices || []).length > 4 || item.kind === "model";
    const wide = ["models", "projects", "worktree", "triggers"].includes(item.kind) || many;
    const playable = (name) => name !== "off" && (!Array.isArray(window.hubSounds) || window.hubSounds.includes(name));
    const play = item.sound && typeof window.hubPlaySound === "function" ? h("button", { type: "button", class: "btn play", disabled: !playable(value(item.name)), "data-key": `${id}:play`, title: "Play this sound", onclick: () => window.hubPlaySound(value(item.name), value("sound_volume")) }, "Play") : null;
    return h("div", { class: `set-row ${wide ? "wide" : ""} ${item.kind === "switch" ? "inline" : ""} ${many ? "many" : ""}`, "data-setting": item.name },
      h("div", { class: "set-label" }, h("span", { id: `${id}-label`, class: "set-name", textContent: item.label }), item.help ? h("span", { id: `${id}-help`, class: "set-help", textContent: item.help }) : null),
      h("div", { class: "set-control" }, control(item), play),
      h("span", { class: `set-said ${s ? "on" : ""} ${s && s.bad ? "bad" : ""}`, "data-said": item.name, role: s && s.bad ? "alert" : "status", textContent: s ? s.text : "" }));
  };
  const schemaRows = (section) => settingsData.schema.filter((item) => item.section === section && !item.hidden).map(row);

  const sections = {
    appearance: () => {
      const names = settingsData.schema.filter((i) => i.section === "appearance").map((i) => i.name);
      const now = Object.fromEntries(names.map((n) => [n, value(n)]));
      if (!snapshot) snapshot = now;
      const moved = JSON.stringify(now) !== JSON.stringify(snapshot);
      return [schemaRows("appearance"),
        moved ? h("div", { class: "set-undo", role: "status" }, h("span", { textContent: "Changed. Every device shows it now." }), h("button", { type: "button", class: "btn", "data-key": "appearance-cancel", textContent: "Cancel changes", onclick: async () => { if (await save(snapshot, names[0])) say("Appearance put back"); } })) : null];
    },
    notifications: () => {
      const state = notifyState();
      const word = { on: "On in this browser", off: "Off in this browser", denied: "Blocked by this browser", default: "Not allowed yet in this browser", none: "This browser can't show them" }[state];
      return [h("div", { class: "set-row" }, h("div", { class: "set-label" }, h("span", { class: "set-name", textContent: "System notifications" }), h("span", { class: "set-help", textContent: word })),
        h("div", { class: "set-control" }, state === "none" ? null : h("button", { type: "button", class: "btn", "data-key": "notify-browser", textContent: state === "on" ? "Turn off here" : state === "denied" ? "How to allow" : "Turn on here", onclick: async () => { await toggleNotify(); draw(true); } }))),
        schemaRows("notifications")];
    },
    sessions: () => [schemaRows("sessions"), h("div", { class: "set-row" }, h("div", { class: "set-label" }, h("span", { class: "set-name", textContent: "Projects' own choices" }),
      h("span", { class: "set-help", textContent: `${S.projects.filter((p) => p.start).length} of ${S.projects.length} projects keep the choice their last session started with.` })),
      h("div", { class: "set-control" }, h("button", { type: "button", class: "btn", "data-key": "forget-starts", disabled: !S.projects.some((p) => p.start), textContent: "Use these everywhere", onclick: guard(async () => {
        if (!(await confirmStep({ title: "Use these defaults in every project?", body: "Each project forgets the mode, model and effort its last session started with. Its next session starts from the defaults above.", yes: "Use everywhere", no: "Keep them" }))) return;
        await api("/api/settings/forget-starts", {}); await tick(); toast("Every project starts from the defaults"); draw(true);
      }) })))],
    sidebar: () => schemaRows("sidebar"),
    terminal: () => schemaRows("terminal"),
    features: () => schemaRows("features"),
    catcher: () => [schemaRows("catcher"), h("p", { class: "set-note" }, "The switch on the Dream Catcher's page is the same one. ", h("a", { class: "in-link", href: "#/catcher", textContent: "Open the Dream Catcher" }))],
    keyboard: () => [schemaRows("keyboard"), ...KEYS.map(([group, keys]) => h("section", { class: "set-keys" }, h("h3", { textContent: group }), h("div", { class: "keysheet" }, keys.flatMap(([keys_, what]) => [keyCaps(keys_), h("span", { textContent: what })]))))],
    health: () => {
      if (!health) return h("div", { class: "empty-line", role: "status", textContent: "Checking…" });
      const mark_ = (ok) => h("span", { class: `health-mark ${ok === true ? "ok" : ok === false ? "bad" : "na"}`, role: "img", "aria-label": ok === true ? "Fine" : ok === false ? "Problem" : "Not checked" }, ok === true ? svg(UI.check) : ok === false ? svg(UI.close) : null);
      const command = (text) => /^(launchctl|brew|python3|tailscale) /.test(text);
      const fix = (text) => text ? h("div", { class: "health-fix" }, h("span", { class: "faint", textContent: "Fix: " }), command(text) ? [h("code", { textContent: text }), copyButton(text)] : h("span", { textContent: text })) : null;
      return [
        h("h3", { class: "set-sub", textContent: "Config" }),
        health.config.length ? health.config.map((p) => h("div", { class: "health-row" }, mark_(p.level === "info" ? null : false), h("div", {}, h("div", { textContent: p.text }), fix(p.fix))))
          : h("div", { class: "health-row" }, mark_(true), h("div", { textContent: "config.json is fine." })),
        h("h3", { class: "set-sub", textContent: "Parts" }),
        health.parts.map((p) => h("div", { class: "health-row" }, mark_(p.ok), h("div", {}, h("div", {}, h("b", { textContent: p.name }), " ", h("span", { class: "faint", textContent: p.text })), fix(p.fix)))),
        h("div", { class: "set-acts" }, h("button", { type: "button", class: "btn", "data-key": "health-again", textContent: "Check again", onclick: once("Checking…", async () => { health = await api("/api/settings/health?fresh=1"); healthAt = Date.now(); draw(true); }) }),
          h("span", { class: "faint", textContent: "In a terminal: python3 hub/server.py --check" }))];
    },
    access: () => {
      const a = settingsData.access;
      const fact = (label, text) => h("div", { class: "set-row" }, h("div", { class: "set-label" }, h("span", { class: "set-name", textContent: label })), h("div", { class: "set-control" }, h("code", { class: "set-fact", textContent: text || "—" })));
      return [fact("Way in", a.way === "tailscale" ? "Tailscale, as one login" : "This Mac only, with a key"), a.way === "tailscale" ? fact("Login", a.login) : null, fact("Address", a.origin), fact("Port", String(a.port)), fact("Kept in", a.config),
        h("p", { class: "set-note", textContent: a.way === "tailscale" ? "Change them by running install.sh again." : "Change them by running install.sh again. The key is never shown here; install.sh --new-key makes a new one." })];
    },
    about: () => {
      if (!about) return h("div", { class: "empty-line", role: "status", textContent: "Loading…" });
      const v = about.version, list = about.news.length ? about.news : about.recent;
      const check = h("button", { type: "button", class: "btn", "data-key": "update-check", textContent: "Check for updates now", disabled: !about.updates });
      check.onclick = () => checkUpdates(check);
      return [
        h("div", { class: "set-row" }, h("div", { class: "set-label" }, h("span", { class: "set-name", textContent: "Version" }), h("span", { class: "set-help", textContent: about.branch ? `Follows ${about.branch}${about.current && about.current !== about.branch ? `. This copy is on ${about.current}` : ""}.` : about.current ? `On ${about.current}.` : "" })),
          h("div", { class: "set-control" }, h("code", { class: "set-fact", textContent: v ? `${v.commit} · ${v.date}` : "Not a git clone" }))),
        h("div", { class: "set-row" }, h("div", { class: "set-label" }, h("span", { class: "set-name", textContent: "Updates" }), h("span", { class: "set-help", textContent: about.updates ? "Checked once a day. Nothing installs until you press Update." : "Daily checks are off in config.json (\"updates\": false)." })),
          h("div", { class: "set-control" }, check)),
        h("div", { class: "set-row" }, h("div", { class: "set-label" }, h("span", { class: "set-name", textContent: "Completely free" }), h("span", { class: "set-help", textContent: "Context Hub is free and open source, with no paid tier. If it saves you time, you can support its work on Ko-fi." })),
          h("div", { class: "set-control" }, h("a", { class: "btn", "data-key": "support", href: "https://ko-fi.com/krisoalmurr", target: "_blank", rel: "noopener noreferrer", textContent: "Support on Ko-fi" }))),
        h("h3", { class: "set-sub", textContent: about.news.length ? "What's new" : "Recent changes" }),
        list.length ? h("ul", { class: "about-news" }, list.map((c) => h("li", {}, h("span", { textContent: c.subject }), h("time", { class: "faint", textContent: c.date })))) : h("div", { class: "empty-line", textContent: "Nothing to show." })];
    },
  };

  const draw = (force) => {
    if (!settingsData) { fill(body, h("div", { class: "empty-line", role: "status", textContent: "Loading settings…" })); return; }
    const tab = tabNow();
    const problems = (health ? health.config.filter((p) => p.level !== "info").length + health.parts.filter((p) => p.ok === false).length : settingsData.problems.filter((p) => p.level !== "info").length);
    const now = JSON.stringify([tab, listOnly(), settingsData.values, S.projects.map((p) => [p.name, p.display, !!p.start]), notifyState(), problems, !!health, !!about, editingModels && editingModels.length, typeof window.hubPlaySound]);
    if (!force && now === sig) return;
    sig = now;
    if (tab !== shownTab) {
      if (shownTab === "appearance") snapshot = null;
      shownTab = tab;
      saved.set("hub.settingsSeen", { ...saved.get("hub.settingsSeen", {}), [tab]: true });
      if (tab === "health" && (!health || Date.now() - healthAt > 60000)) api("/api/settings/health").then((d) => { health = d; healthAt = Date.now(); draw(true); }, (e) => { health = { config: [{ level: "error", text: e.message, fix: "" }], parts: [] }; draw(true); });
      if (tab === "about") api("/api/settings/about").then((d) => { about = d; draw(true); if (d.news.length) api("/api/settings/seen", {}).then(paintNews, () => {}); }, () => {});
    }
    drawTop();
    const list = listOnly();
    fill(nav, settingGroups().map(([word, items]) => h("div", { class: "set-group", role: "group", "aria-label": word }, h("span", { class: "set-group-t", "aria-hidden": "true", textContent: word }),
      items.map((s) => h("a", { href: `#/settings/${s.id}`, class: s.id === tab && !list ? "on" : "", "aria-current": s.id === tab && !list ? "page" : undefined, "data-key": `tab:${s.id}` },
        h("span", { textContent: s.title }), s.id === "health" && problems ? h("span", { class: "set-badge", "aria-label": `, ${problems} ${problems === 1 ? "problem" : "problems"}`, textContent: problems }) : null, list ? svg(UI.chev) : null)))));
    if (list) { fill(body); return; }
    const current = SETTING_PAGES().find((s) => s.id === tab);
    fill(body, h("h2", { class: "set-title", textContent: current.title }), h("p", { class: "set-lead", textContent: SETTING_LEADS[tab] || "" }), h("div", { class: `set-rows set-${tab}` }, (sections[tab] || (() => schemaRows(tab)))()));
  };
  const follow = () => draw(false);
  window.addEventListener("hub:settings", follow);
  const onPhone = () => { topSig = ""; draw(true); };
  phone.addEventListener("change", onPhone);
  page.leave = () => { window.removeEventListener("hub:settings", follow); phone.removeEventListener("change", onPhone); unpreviewSettings(); };
  page.update = () => { if (route().tab !== shownTab) { body.scrollTop = 0; view.scrollTop = 0; } draw(false); };
  if (!settingsData) loadSettings().then(() => draw(true)); else { loadSettings(); draw(true); }
}
const settingsPalette = () => [{ text: "Settings", run: () => go("#/settings") }, ...SETTING_PAGES().map((s) => ({ text: s.title, where: "Settings", run: () => go(`#/settings/${s.id}`) }))];
loadSettings();

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
    s.kind !== "claude" && s.alive ? { text: "Stop terminal…", run: () => stopTerminal(s) } : null,
    canResume(s) ? { text: "Resume", run: guard(() => resumeSession(s)) } : null,
    { text: "Delete…", run: () => deleteSession(s) },
  ].filter(Boolean).map((o) => ({ ...o, of: s }));
};
// ── Navigation: one prefix key, from anywhere and from inside a terminal too, to the session that needs you, the next
// or the last one, a pane by number or by direction, zoom, split, Go to or a board. Each lands in the terminal it opens. ──
UI.find = '<circle cx="7" cy="7" r="4.25"/><path d="m10.2 10.2 3.3 3.3"/>';
UI.zoom = '<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>';
UI.board = '<rect x="2" y="2.5" width="5" height="5"/><rect x="9" y="2.5" width="5" height="5"/><rect x="2" y="8.5" width="5" height="5"/><rect x="9" y="8.5" width="5" height="5"/>';
// The order sessions ask for you in: what needs you, what finished and you haven't read, what is at work, the rest;
// the newest change first in each. Kept in this one place so it and the sidebar's attention order can become one.
// One ranking with the sidebar's (attentionKind): a closed session ranks last.
const attentionRank = (s) => { const kind = attentionKind(s); return kind ? ATTENTION_RANK[kind] : 4; };
const changedAt = (s) => { const kind = attentionKind(s); return kind ? sinceOf(s, kind) : s.closedAt || s.created || 0; };
const byAttention = (list) => [...list].sort((a, b) => attentionRank(a) - attentionRank(b) || changedAt(b) - changedAt(a));
// The sidebar's order, live sessions only: the hub's own, then each folder's projects, then the projects in none.
const sideSessions = () => {
  const live = S.sessions.filter((s) => !gone(s));
  if (sideOrder() === "attention") return byAttention(live).filter((s) => !isHiddenProject(ownerName(s)));
  const names = [...hubRow().map((p) => p.name), ...groups().flatMap((f) => sideProjects().filter((p) => groupOf(p.name) === f.id).map((p) => p.name)), ...sideProjects().filter((p) => !groupOf(p.name)).map((p) => p.name)];
  return names.flatMap((name) => live.filter((s) => ownerName(s) === name));
};
// The session you're in and the one before it, kept per browser, so l still knows the way back after a reload.
const visits = { now: null, before: null, ...saved.get("visits", {}) };
const noteVisit = (id) => { if (!id || id === visits.now) return; visits.before = visits.now; visits.now = id; saved.set("visits", { now: visits.now, before: visits.before }); };
const hereSid = () => route().name === "session" && page.selected ? page.selected() : null;
const zoomHash = (n, id) => `${layoutHash(n)}${id && isSplit(n) && leavesOf(n).includes(id) ? `~${id}` : ""}`;
// A pane already on screen takes focus (and the zoom, when one is zoomed); any other session opens on its own page.
const goTo = (id) => {
  if (!session(id)) return;
  const r = route();
  if (r.name === "session" && r.ids.includes(id)) { if (r.zoom && r.zoom !== id) go(zoomHash(r.layout, id)); else if (pageKeys.jump) pageKeys.jump(r.ids.indexOf(id)); return; }
  if (tabsFocus(id)) return;
  go(`#/s/${id}`);
};
const forYou = () => { const all = byAttention(S.sessions); return [...all.filter((s) => attentionRank(s) === 0), ...all.filter((s) => attentionRank(s) === 1)]; };
const nextForYou = () => {
  const list = forYou(), here = hereSid(), at = list.findIndex((s) => s.id === here);
  if (!list.length || (list.length === 1 && at === 0)) { toast(list.length ? "Nothing else needs you" : "Nothing needs you, and nothing finished is unread"); return; }
  goTo(list[(at + 1) % list.length].id);
};
const stepSession = (step) => {
  const list = sideSessions();
  if (!list.length) { toast("No session is running"); return; }
  const at = list.findIndex((s) => s.id === (hereSid() || visits.now));
  goTo((at < 0 ? list[step > 0 ? 0 : list.length - 1] : list[(at + step + list.length) % list.length]).id);
};
const lastSession = () => {
  const here = hereSid(), back = here && here === visits.now ? visits.before : visits.now;
  if (!back || !session(back) || back === here) { toast("No earlier session to go back to"); return; }
  goTo(back);
};

// ── Boards: a split you named, kept on the server like folders, so the desk and the phone share them ──
const boards = () => S.boards || [];
const boardFor = (n) => { const text = layoutText(n); return boards().find((b) => b.layout === text) || null; };
const boardTree = (b) => { try { return b.layout.includes("(") ? parseTree(b.layout) : legacyLayout(b.layout.split(",")); } catch { return null; } };
const boardSessions = (b) => { const tree = boardTree(b); return tree ? leavesOf(tree).map(session).filter(Boolean) : []; };
// One mark for the board: needs you beats working beats finished and unread beats running; all gone, it's closed.
const boardState = (b) => {
  const list = boardSessions(b);
  return list.some((s) => attentionRank(s) === 0) ? "needs" : list.some((s) => s.state === "working" || s.state === "closing") ? "working"
    : list.some((s) => attentionRank(s) === 1) ? "finished" : list.some((s) => s.alive) ? "idle" : "closed";
};
const changeBoards = guard(async (body, said) => { await api("/api/boards", body); await tick(); if (said) toast(said); });
const saveBoard = guard(async (layout) => {
  const name = await askName({ title: "Save this split as a board", yes: "Save board", placeholder: "Review pair, Frontend trio…" });
  if (!name) return;
  await api("/api/boards", { op: "create", name, layout: layoutText(layout), sizes: sizeLists(layout) });
  await tick();
  const at = boards().findIndex((b) => b.name === name);
  toast(at >= 0 && at < 9 ? `Saved. ${prefixSpec().label} then ⇧${at + 1} opens ${name}.` : `Saved ${name}.`);
});
// Opens at the sizes it was saved with. A session deleted since leaves the board; one closed since shows its record.
const openBoard = (which) => {
  const b = typeof which === "number" ? boards()[which] : which;
  if (!b) { toast(boards().length ? `There's no board ${which + 1}` : "No boards yet. Save a split from its Split menu."); return; }
  let tree = boardTree(b), at = 0;
  const sized = (n) => { if (!isSplit(n)) return n; const z = (b.sizes || [])[at++]; return { ...n, z: Array.isArray(z) && z.length === n.k.length ? z : n.z, k: n.k.map(sized) }; };
  tree = tree && sized(tree);
  if (tree) leavesOf(tree).filter((id) => !session(id)).forEach((id) => { tree = tree && layoutWithout(tree, id); });
  if (!tree) { toast(`The sessions of ${b.name} are gone`); return; }
  goLayout(tree);
};
const boardMenu = (anchor, b) => {
  const at = boards().findIndex((x) => x.id === b.id), last = boards().length - 1;
  popover(anchor, [
    { name: "Rename…", icon: "gear", run: guard(async () => { const name = await askName({ title: "Rename board", value: b.name, yes: "Rename" }); if (name && name !== b.name) await changeBoards({ op: "rename", id: b.id, name }); }) },
    at > 0 ? { name: "Move up", icon: "updown", say: `Becomes ⇧${at}`, run: () => changeBoards({ op: "shift", id: b.id, by: -1 }) } : null,
    at < last ? { name: "Move down", icon: "updown", say: at + 2 <= 9 ? `Becomes ⇧${at + 2}` : undefined, run: () => changeBoards({ op: "shift", id: b.id, by: 1 }) } : null,
    { name: "Delete board…", icon: "close", run: guard(async () => {
      const ok = await confirmStep({ title: `Delete the board ${b.name}?`, body: "Only the saved layout goes. Its sessions keep running.", yes: "Delete board", no: "Keep it" });
      if (ok) await changeBoards({ op: "delete", id: b.id }, "Board deleted");
    }) },
  ].filter(Boolean));
};
// Home lists them, each with its rolled-up mark, what is in it and the key that opens it.
const boardsPanel = () => {
  if (!boards().length) return null;
  const n = Math.min(9, boards().length), keys = n === 1 ? "⇧1 opens it" : `⇧1–${n} opens one`;
  return panel("Boards", phone.matches ? null : h("span", { class: "head-fact", textContent: `${prefixSpec().label} then ${keys}` }),
    h("div", { class: "board-list" }, boards().map((b, i) => {
      const list = boardSessions(b), places = [...new Set(list.map((s) => s.project))].map(project).filter(Boolean);
      return h("div", { class: "board-row", "data-nav": `b:${b.id}`, onclick: (e) => { if (!e.target.closest("a, button")) openBoard(b); } },
        rowOrb(boardState(b), ROW_ORB),
        h("span", { class: "q-main" }, h("a", { class: "q-t", href: `#/s/${b.layout}`, dir: "auto", textContent: b.name, onclick: (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); openBoard(b); } }),
          h("span", { class: "q-line", dir: "auto", textContent: list.length ? list.map(bareTitle).join(", ") : "Its sessions are gone" })),
        h("span", { class: "q-meta" }, places.slice(0, 3).map((p) => mark(p, 15)), i < 9 && !phone.matches ? h("kbd", { class: "board-key", title: `${prefixSpec().label} then ⇧${i + 1}`, textContent: `⇧${i + 1}` }) : null),
        h("button", { class: "icon board-more", type: "button", title: `Actions for ${b.name}`, "aria-haspopup": "menu", "data-key": `bmore:${b.id}`, onclick: (e) => boardMenu(e.currentTarget, b) }, uiIcon("dots")));
    })));
};

// ── The prefix: pref("prefix_key"), ⌃` by default. Pressed in a terminal it leaves it, as it always did, and the status
// line lists what the next key does. No key, or esc, and you're simply out. On a session page outside the terminal,
// no key takes you back into it, as before. It never uses ⌃⌥, VoiceOver's own keys, and its keys never reach Claude. ──
const MOD_SIGNS = { control: "⌃", ctrl: "⌃", alt: "⌥", option: "⌥", shift: "⇧", meta: "⌘", cmd: "⌘", command: "⌘" };
const prefixSpec = () => {
  const parts = String(pref("prefix_key", "Control+`") || "Control+`").split("+").map((part) => part.trim());
  const key = parts.pop() || "`", mods = parts.map((m) => m.toLowerCase());
  return { key, ctrl: mods.includes("control") || mods.includes("ctrl"), alt: mods.includes("alt") || mods.includes("option"), shift: mods.includes("shift"),
    meta: mods.includes("meta") || mods.includes("cmd") || mods.includes("command"), label: mods.map((m) => MOD_SIGNS[m] || m).join("") + (key.length === 1 ? key.toUpperCase() : key) };
};
// By the key's character, or by where it sits: with ⌥ held a Mac types another character (macOptionIsMeta aside).
const codeOf = (key) => key === "`" ? "Backquote" : /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : /^[0-9]$/.test(key) ? `Digit${key}` : key.toLowerCase() === "space" ? "Space" : "";
const isPrefix = (e) => {
  const p = prefixSpec();
  if (e.ctrlKey !== p.ctrl || e.altKey !== p.alt || e.metaKey !== p.meta || e.shiftKey !== p.shift) return false;
  return (e.key || "").toLowerCase() === p.key.toLowerCase() || (!!codeOf(p.key) && e.code === codeOf(p.key));
};
const prefix = { armed: false, timer: 0, from: "page" };
const backToTerminal = () => { if (route().name === "session" && pageKeys.Enter && !document.querySelector("dialog[open]:not(.keys-help)")) pageKeys.Enter(); };
const armPrefix = () => {
  const el = document.activeElement;
  prefix.from = inTerminal() ? "terminal" : isTyping(el) ? "field" : "page";
  if (prefix.from !== "page") el.blur();
  prefix.armed = true;
  clearTimeout(prefix.timer);
  prefix.timer = setTimeout(() => endPrefix(true), prefix.from === "page" ? 1500 : 4000);
  status_.classList.add("armed");
  drawStatus();
  say(`${prefixSpec().label}: press a key, or esc`);
};
const endPrefix = (timedOut) => {
  if (!prefix.armed) return;
  clearTimeout(prefix.timer);
  prefix.armed = false;
  status_.classList.remove("armed");
  drawStatus();
  if (timedOut && prefix.from === "page") backToTerminal();
};
const DIRS = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down", H: "left", J: "down", K: "up", L: "right" };
const prefixAction = (e) => {
  const key = e.key;
  if (key === "Escape") return () => {};
  if (isPrefix(e) || key === "Enter") return backToTerminal;
  if (e.metaKey || e.ctrlKey || e.altKey) return null;
  if (e.shiftKey && /^Digit[1-9]$/.test(e.code)) return () => openBoard(Number(e.code.slice(5)) - 1);
  const dir = DIRS[e.shiftKey && /^[hjkl]$/i.test(key) ? key.toUpperCase() : key];
  if (dir) return () => { if (pageKeys.paneDir) pageKeys.paneDir(dir, e.shiftKey); else say("Directions move between the panes of a split"); };
  if (/^Digit[1-9]$/.test(e.code)) return () => { const r = route(), n = Number(e.code.slice(5)); if (r.name === "session" && pageKeys.jump && n <= r.ids.length) pageKeys.jump(n - 1); else say(`There's no pane ${n}`); };
  return { n: nextForYou, j: () => stepSession(1), k: () => stepSession(-1), l: lastSession, "/": openPalette, "?": openKeys,
    z: () => { if (pageKeys.z) pageKeys.z(); }, s: () => { if (pageKeys.s && route().name === "session") pageKeys.s(); }, ...termPrefixKeys() }[key] || null;
};
const prefixHints = () => {
  const r = route(), here = r.name === "session", many = here && r.ids.length > 1;
  return [[prefixSpec().label, "then"], ["n", "next for you"], ["j k", "next, previous"], ["l", "last"],
    ...(many ? [[`1–${r.ids.length}`, "pane"], ["←→↑↓", "move"], ["⇧←", "swap"], ["z", r.zoom ? "restore" : "zoom"]] : []),
    ...(here && r.ids.length < MAX_PANES ? [["s", "split"]] : []), ...termPrefixHints(here, many), ["/", "go to"], ...(boards().length ? [[`⇧1–${Math.min(9, boards().length)}`, "board"]] : []),
    ["esc", prefix.from === "page" ? "cancel" : "stay out"]];
};
window.addEventListener("pointerdown", () => endPrefix(false), true);
window.addEventListener("blur", () => endPrefix(false));

// ── Go to (⌘K, / or the phone's search button): every session, found by any words across its name, project, folder,
// branch, the tool it is on, what it asks and what it said last. Attention order before you type, filters by state,
// closed sessions under a line with Resume, and the commands it always had. ──
const GOTO_FILTERS = [["all", "All"], ["needs", "Needs you"], ["working", "Working"], ["done", "Done"]];
const filterOf = (s) => attentionRank(s) === 0 ? "needs" : s.state === "working" || s.state === "closing" ? "working" : isDone(s) ? "done" : "";
const folderOf = (s) => (s.repo || "").split("/").pop() || "";
const placeOf = (s) => { const p = (ownerOf(s) || {}).display || s.project; return [...new Set([p, folderOf(s) !== s.project ? folderOf(s) : "", s.branch].filter(Boolean))].join(" · "); };
const findText = (s) => [s.title, (ownerOf(s) || {}).display, s.project, folderOf(s), s.branch, s.activity && s.activity.tool, s.activity && s.activity.target,
  s.asking, s.said, s.now, s.note, s.kind === "shell" ? "terminal" : ""].filter(Boolean).join("\n").toLowerCase();
let gotoFilter = "all";
function openPalette() {
  if (document.querySelector("dialog.palette")) return;
  endPrefix(false);
  gotoFilter = "all";  // each Go to starts with everything; a filter is a choice for this one look
  const sid = selectedSid(), held = sid && session(sid);
  const actions = held ? sessionActions(held) : [];
  const asOption = (s) => ({ text: bareTitle(s), where: (ownerOf(s) || {}).display, orb: s, sid: s.id, line: gone(s) ? noteLine(s.note) || DOT_WORDS[s.state] || "" : rowLine(s),
    find: findText(s), filter: filterOf(s), closed: gone(s), place: placeOf(s), run: () => goTo(s.id), resume: canResume(s) ? guard(() => resumeSession(s)) : null });
  const live = byAttention(S.sessions.filter((s) => !gone(s))).map(asOption);
  const closed = S.sessions.filter(gone).sort((a, b) => changedAt(b) - changedAt(a)).map(asOption);
  const commands = [
    ...boards().map((b, i) => ({ text: b.name, where: "Board", icon: "board", keys: i < 9 ? `${prefixSpec().label} ⇧${i + 1}` : undefined, run: () => openBoard(b) })),
    ...S.projects.flatMap((p) => [
      { text: p.display, mark: p, where: isHiddenProject(p.name) ? "Hidden" : undefined, run: () => go(`#/p/${P(p.name)}`) },
      { text: "New session", where: p.display, mark: p, run: () => newSession(p.name) },
    ]),
    { text: "Home", keys: "g h", run: () => go("#/") },
    { text: "New project", run: () => go("#/new") },
    { text: "Keyboard shortcuts", keys: "?", run: openKeys },
    ...(feature("notice_tools") ? [{ text: "Recent notices", icon: "history", run: openNoticeLog }] : []),
    ...settingsPalette(),
    ...(window.hubBrowser ? window.hubBrowser.palette(held) : []),
  ];
  const label = held ? `Act on ${held.title}, or go anywhere` : "Go to a session or project";
  const dialog = h("dialog", { class: "palette", "aria-label": label });
  const input = h("input", { type: "text", placeholder: held ? "Act on this session, or go anywhere" : "Go to a session, project or board", "aria-label": label, spellcheck: false, autocomplete: "off", enterkeyhint: "go",
    role: "combobox", "aria-expanded": "true", "aria-autocomplete": "list", "aria-controls": "palette-results" });
  const close = h("button", { class: "icon palette-close", type: "button", title: "Close", "aria-label": "Close", onclick: () => dialog.close() }, uiIcon("close"));
  const chips = h("div", { class: "goto-chips", role: "group", "aria-label": "Show" });
  const results = h("div", { class: "results", id: "palette-results", role: "listbox", "aria-label": "Matches" });
  const foot = h("div", { class: "palette-foot" });
  let chosen = 0, matches = [], jumpable = [];
  const option = (o, i) => h("div", { class: `opt ${o.line ? "two" : ""} ${o.closed ? "past" : ""} ${i === chosen ? "on" : ""}`, id: `palette-${i}`, role: "option", "aria-selected": i === chosen ? "true" : "false", style: colourEdge(o.orb ? o.orb.project : o.mark ? o.mark.name : ""),
    onclick: (e) => { if (!e.target.closest(".opt-act")) pick(o); }, onmousemove: () => { if (chosen !== i) { chosen = i; mark_(); } } },
    h("span", { class: "slot" }, o.mark ? mark(o.mark, 15) : o.orb ? orbOf(`pal:${o.orb.id}`, orbState(o.orb)) : o.icon ? uiIcon(o.icon) : null),
    h("span", { class: "opt-main" }, h("span", { class: "t", dir: "auto" }, o.text, o.where ? h("span", { class: "where", textContent: ` — ${o.where}` }) : null),
      o.line ? h("span", { class: `opt-line st-${o.closed ? "ended" : shownState(o.orb)}`, dir: "auto", textContent: o.line }) : null),
    o.resume ? h("button", { class: "opt-act", type: "button", tabIndex: -1, textContent: "Resume", title: "Resume this conversation (⌘↵)", onclick: () => { dialog.close(); o.resume(); } }) : null,
    o.keys ? h("kbd", { textContent: o.keys }) : o.jump ? h("kbd", { class: "jump-n", textContent: `⌥${o.jump}` }) : null);
  // Typed is:needs, is:working, is:done or is:all filter as the chips do, since typed letters go to the search box.
  const query = () => {
    let only = gotoFilter;
    const words = input.value.toLowerCase().split(/\s+/).filter((w) => { const m = /^is:(all|needs|working|done)$/.exec(w); if (m) only = m[1]; return w && !m; });
    return { only, words };
  };
  const mark_ = () => {
    results.querySelectorAll(".opt").forEach((el) => { const on = el.id === `palette-${chosen}`; el.classList.toggle("on", on); el.setAttribute("aria-selected", on ? "true" : "false"); });
    const on = results.querySelector(".opt.on");
    if (on) { input.setAttribute("aria-activedescendant", on.id); on.scrollIntoView({ block: "nearest" }); } else input.removeAttribute("aria-activedescendant");
    const o = matches[chosen];
    fill(foot, h("span", { class: "foot-keys", "aria-hidden": "true" }, h("kbd", { textContent: "↑↓" }), h("kbd", { textContent: "↵" }), o && o.resume ? [h("kbd", { textContent: "⌘↵" }), "resume"] : null, h("kbd", { textContent: "esc" })),
      h("span", { class: "foot-place", dir: "auto", textContent: o && o.place ? o.place : "" }),
      h("span", { class: "foot-n", role: "status", textContent: `${matches.length} ${matches.length === 1 ? "result" : "results"}` }));
  };
  const paint = () => {
    const { only, words } = query();
    const fits = (o) => words.every((w) => (o.find || `${o.text} ${o.where || ""}`.toLowerCase()).includes(w));
    const sessionsIn = (list) => list.filter((o) => (only === "all" || o.filter === only) && fits(o));
    const acts = only === "all" ? actions.filter(fits) : [];
    const now = sessionsIn(live).slice(0, 80);
    jumpable = feature("jump_numbers") ? now.slice(0, 9) : [];
    live.forEach((o) => { o.jump = jumpable.indexOf(o) + 1 || 0; });
    const past = sessionsIn(closed), pastShown = past.slice(0, words.length || only !== "all" ? 40 : 6);
    const cmds = only === "all" ? commands.filter(fits) : [];
    matches = [...acts, ...now, ...pastShown, ...cmds];
    chosen = Math.min(chosen, Math.max(matches.length - 1, 0));
    fill(chips, GOTO_FILTERS.map(([key, word]) => {
      const n = key === "all" ? 0 : S.sessions.filter((s) => filterOf(s) === key).length;
      return h("button", { type: "button", class: `goto-chip ${only === key ? "on" : ""}`, "aria-pressed": only === key ? "true" : "false", "data-filter": key,
        onclick: () => { gotoFilter = key; input.value = input.value.replace(/(^|\s)is:\S*/g, " ").trim(); chosen = 0; paint(); input.focus(); } },
        h("span", { textContent: word }), key === "all" ? null : h("b", { class: n ? `n-${key}` : "zero", textContent: String(n) }));
    }));
    let i = 0;
    const rows = (list) => list.map((o) => option(o, i++));
    // The held session's actions come first, under its name; sessions next; closed ones and the commands each after a line.
    fill(results, matches.length ? [
      acts.length ? [h("div", { class: "pal-group", role: "presentation", dir: "auto", textContent: held.title }), rows(acts)] : null,
      now.length ? [acts.length ? h("div", { class: "pal-rule", role: "presentation" }) : null, rows(now)] : null,
      pastShown.length ? [h("div", { class: "pal-sep", role: "presentation" }, h("span", { textContent: "Closed" }), past.length > pastShown.length ? h("span", { class: "faint", textContent: `${pastShown.length} of ${past.length}, type to find the rest` }) : null), rows(pastShown)] : null,
      cmds.length ? [acts.length || now.length || pastShown.length ? h("div", { class: "pal-rule", role: "presentation" }) : null, rows(cmds)] : null,
    ] : h("div", { class: "empty-line", textContent: only === "all" ? "No matches" : `Nothing ${{ needs: "needs you", working: "is working", done: "is done" }[only]}${words.length ? " with those words" : ""}` }));
    mark_();
  };
  const pick = (o, resume) => { dialog.close(); if (resume && o.resume) o.resume(); else o.run(); };
  input.addEventListener("input", () => { chosen = 0; paint(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); chosen = Math.min(chosen + 1, matches.length - 1); mark_(); }
    if (e.key === "ArrowUp") { e.preventDefault(); chosen = Math.max(chosen - 1, 0); mark_(); }
    const by = listPage(e, results, ".opt");
    if (by) { e.preventDefault(); chosen = Math.max(0, Math.min(matches.length - 1, chosen + by)); mark_(); }
    if (e.key === "Enter" && matches[chosen]) { e.preventDefault(); pick(matches[chosen], e.metaKey || e.ctrlKey); }
    if (e.altKey && !e.metaKey && !e.ctrlKey && /^Digit[1-9]$/.test(e.code) && jumpable[Number(e.code.slice(5)) - 1]) { e.preventDefault(); e.stopPropagation(); pick(jumpable[Number(e.code.slice(5)) - 1]); }
  });
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  fill(dialog, h("div", { class: "palette-top" }, uiIcon("find"), input, close), chips, results, foot);
  paint();
  sheet(dialog);
  input.focus();
}

// ── Every key, in one sheet docked at the left: the app stays usable beside it ──
const KEYS = [
  ["Anywhere", [["⌘K", "Go to a session, or act on the one in hand"], ["/", "Go to a session, project or board"], ["?", "Show or hide this sheet"], ["⌘B", "Fold or unfold the sidebar"], ["g h", "Home"], ["g d", "Dreams of this project"], ["g m", "Memory of this project"], ["g n", "New session"], ["g s", "Go to the sidebar"], ["g ,", "Settings"], ["⌘,", "Settings"], ["esc", "Leave a field, then go up a level"]]],
  ["Lists and the sidebar", [["j k", "Move down and up"], ["↵", "Open"], ["space", "Peek at a session"], ["⌘ click", "Open a session beside this one"]]],
  ["Session", [["↵", "Back to the terminal"], ["1–4", "Choose a pane"], ["⌥1–4", "Choose a pane while typing"], ["z", "Zoom a pane, or show the whole split"], ["p", "Show or hide the panel"], ["s", "Split"], ["esc", "Restore a zoomed pane, then go up"]]],
  ["Project", [["i", "Go to the prompt"], ["n", "New session"], ["N", "New project, from Home"], ["m d", "Memory, Dreams"], [",", "Project settings"], ["⌘↩", "Start a session"]]],
  ["Memory and Dreams", [["e", "Edit a memory file"], ["x a r", "Tick, apply, dream now"]]],
];
// ── The terminal's keys (Settings › Features): after the prefix, t for the scratch shell, e, space and o for the
// panes of a split; PgUp and PgDn page through Go to and menus; the Terminal group of the key sheet says which apply ──
const termPrefixKeys = () => ({
  ...(feature("scratch") ? { t: () => { if (route().name === "session" && pageKeys.scratch) pageKeys.scratch(); else say("Open a session first, then its scratch terminal"); } } : {}),
  ...(feature("pane_layouts") ? { e: () => pageKeys.evenOut && pageKeys.evenOut(), " ": () => pageKeys.nextLayout && pageKeys.nextLayout(), o: () => pageKeys.rotate && pageKeys.rotate() } : {}),
});
const termPrefixHints = (here, many) => [
  ...(here && feature("scratch") ? [["t", "scratch"]] : []),
  ...(many && feature("pane_layouts") ? [["e", "even out"], ["space", "layout"], ["o", "rotate"]] : []),
];
const termAfterRows = () => [
  ...(feature("scratch") ? [["t", "Scratch terminal for this session: show or hide"]] : []),
  ...(feature("pane_layouts") ? [["e", "Even out the panes"], ["space", "Next layout: side by side, main and stack, grid"], ["o", "Rotate the panes"]] : []),
];
// How far PgUp and PgDn move in a list: what fits in it, at least one row. 0 for any other key.
const listPage = (e, box, rows) => {
  if (!feature("page_keys") || (e.key !== "PageUp" && e.key !== "PageDown") || e.metaKey || e.ctrlKey || e.altKey) return 0;
  const row = box.querySelector(rows), fits = row && row.offsetHeight ? Math.max(1, Math.floor(box.clientHeight / row.offsetHeight) - 1) : 8;
  return e.key === "PageUp" ? -fits : fits;
};
const TERM_KEYS = ["Terminal", []];
KEYS.push(TERM_KEYS);
const fillTermKeys = () => {
  TERM_KEYS[1] = [
    ...(feature("wrapped_links") ? [["⌘ click", "Open a link, even one that wraps onto the next rows"]] : []),
    ...(pref("copy_on_select", "clipboard") === "manual" ? [[IS_MAC ? "⌘C" : "⌃⇧C", "Copy what you selected"]] : []),
    ...(feature("page_keys") ? [["⇧PgUp ⇧PgDn", "Scroll half a screen"], ["PgUp PgDn", "Page through Go to and menus"]] : []),
    ...(feature("scratch") ? [[`${prefixSpec().label} t`, "Scratch terminal"]] : []),
  ];
  const at = KEYS.indexOf(TERM_KEYS);
  if (!TERM_KEYS[1].length && at >= 0) KEYS.splice(at, 1);
  else if (TERM_KEYS[1].length && at < 0) KEYS.push(TERM_KEYS);
};
fillTermKeys();
window.addEventListener("hub:settings", fillTermKeys);

// ── Alerts from terminal output (feature_triggers): the server matched a session's new line against a pattern
// (hub_terminal.py). Each browser tells each one once, as a notice or the system's notification when the hub isn't in
// front; one that came while no page was open is told when one opens, if it came in the last six hours. ──
NOTICE_MS.trigger = 9000;
const TRIGGER_FRESH = 6 * 3600;
const noticeTriggers = () => {
  const list = S.triggers;
  if (!Array.isArray(list)) return;
  const newest = list.reduce((most, t) => Math.max(most, t.at || 0), 0);
  const seen = saved.get("triggerSeen", null);
  if (seen === null) { saved.set("triggerSeen", Math.max(newest, Date.now() / 1000)); return; }  // this browser's first look: nothing is news yet
  const fresh = list.filter((t) => t.at > seen && Date.now() / 1000 - t.at < TRIGGER_FRESH);
  if (newest > seen) saved.set("triggerSeen", newest);
  if (!feature("triggers")) return;
  fresh.slice(-3).forEach((t) => {
    const s = session(t.sid);
    if (isMuted(s ? ownerName(s) : t.project) || (s && watching(s.id) && document.visibilityState === "visible" && document.hasFocus())) return;
    const where = ((s ? ownerOf(s) : project(t.project)) || {}).display || t.project || "A session";
    const title = s ? bareTitle(s) : where;
    const open = () => { if (session(t.sid)) goTo(t.sid); };
    tell("system", { native: { title: `${title}: ${t.line}`.slice(0, 120), body: `Matched ${t.pattern}`, tag: `hub-trigger-${t.id}`, open },
      banner: { key: `t:${t.id}`, kind: "trigger", icon: "bell", title, line: `${where} · ${t.line}`, open } });
  });
};

// Settings › Features › Patterns to watch for: a list of patterns, each for every project or one, and a field to try
// them on some output before keeping them. The server checks each one compiles; the try uses the server's matching.
let triggerEdit = null;  // the list being edited, kept across the page's redraws
const triggersEditor = (item, { now, save, redraw }) => {
  const kept = Array.isArray(now) ? now : [];
  const whereWord = (name) => name ? (project(name) || {}).display || name : "Every project";
  if (!triggerEdit) {
    return h("div", { class: "triggers-view" },
      kept.length ? h("ul", { class: "triggers-list" }, kept.map((t) => h("li", {}, h("code", { textContent: t.pattern }), h("span", { class: "faint", textContent: whereWord(t.project) }))))
        : h("p", { class: "faint", textContent: "None yet. error|failed is a good first one." }),
      h("div", { class: "set-acts" }, h("button", { type: "button", class: "btn", "data-key": "triggers-edit", textContent: kept.length ? "Edit patterns" : "Add a pattern",
        onclick: () => { triggerEdit = { rows: kept.length ? kept.map((t) => ({ ...t })) : [{ pattern: "", project: "" }], sample: "" }; redraw(); const first = document.querySelector(".trigger-row input"); if (first) first.focus(); } })));
  }
  const rows = triggerEdit.rows;
  const result = h("div", { class: "trigger-result", role: "status", "aria-live": "polite" });
  let wait = 0;
  const tryThem = () => {
    clearTimeout(wait);
    wait = setTimeout(async () => {
      const sample = triggerEdit && triggerEdit.sample;
      const live = rows.filter((t) => t.pattern.trim());
      if (!sample || !sample.trim() || !live.length) { fill(result, sample && sample.trim() ? h("span", { class: "faint", textContent: "Add a pattern to try it." }) : null); return; }
      try {
        const answers = await Promise.all(live.map((t) => api("/api/terminal/test", { pattern: t.pattern, text: sample })));
        fill(result, live.map((t, i) => { const a = answers[i]; return h("div", { class: `trigger-try ${a.ok ? (a.lines.length ? "hit" : "miss") : "bad"}` },
          h("code", { textContent: t.pattern }), h("span", { textContent: !a.ok ? a.error : a.lines.length ? `tells you about ${a.lines.length === 1 ? "1 line" : `${a.lines.length} lines`}: ${a.lines.slice(0, 2).join(" · ")}` : "matches nothing here" })); }));
      } catch (error) { fill(result, h("span", { class: "bad", textContent: error.message })); }
    }, 250);
  };
  const keep = async () => {
    const list = rows.map((t) => ({ pattern: t.pattern.trim(), project: t.project || "" })).filter((t) => t.pattern);
    if (await save({ [item.name]: list }, item.name)) { triggerEdit = null; redraw(); }
  };
  const choices = [["", "Every project"], ...S.projects.map((p) => [p.name, p.display])];
  const editor = h("div", { class: "triggers-edit" },
    rows.map((t, i) => h("div", { class: "trigger-row" },
      h("input", { type: "text", value: t.pattern, placeholder: "error|failed", "aria-label": `Pattern ${i + 1}`, spellcheck: false, autocapitalize: "off", "data-key": `trigger-${i}`, oninput: (e) => { t.pattern = e.target.value; tryThem(); } }),
      h("select", { "aria-label": `Where pattern ${i + 1} applies`, onchange: (e) => { t.project = e.target.value; } }, choices.map(([v, text]) => h("option", { value: v, selected: v === (t.project || ""), textContent: text }))),
      h("button", { type: "button", class: "icon", title: `Remove ${t.pattern || "this pattern"}`, onclick: () => { rows.splice(i, 1); redraw(); } }, uiIcon("close")))),
    h("div", { class: "set-acts" }, rows.length < 20 ? h("button", { type: "button", class: "quiet", "data-key": "trigger-add", onclick: () => { rows.push({ pattern: "", project: "" }); redraw(); const all = document.querySelectorAll(".trigger-row input"); if (all.length) all[all.length - 1].focus(); } }, uiIcon("plus"), "Add a pattern") : null),
    h("label", { class: "trigger-sample" }, h("span", { class: "set-help", textContent: "Try them: paste some output" }),
      h("textarea", { rows: 3, spellcheck: false, value: triggerEdit.sample, placeholder: "npm ERR! Test failed. See above for more details.", "data-key": "trigger-sample", oninput: (e) => { triggerEdit.sample = e.target.value; tryThem(); } })),
    result,
    h("div", { class: "set-acts" }, h("span", { class: "grow" }),
      h("button", { type: "button", class: "btn", textContent: "Cancel", onclick: () => { triggerEdit = null; redraw(); } }),
      h("button", { type: "button", class: "btn primary", "data-key": "trigger-keep", textContent: "Keep these patterns", onclick: keep })));
  tryThem();
  return editor;
};

// A chord is written the way it's typed: "g then d".
const keyCaps = (keys) => {
  const chord = keys.match(/^(\S) (\S)$/);
  if (chord && keys[0] === "g") return h("span", { class: "caps" }, h("kbd", { textContent: chord[1] }), h("span", { class: "then", textContent: "then" }), h("kbd", { textContent: chord[2] }));
  return h("span", { class: "caps" }, keys.split(" ").map((k) => h("kbd", { textContent: k })));
};
// The prefix's keys, under its own heading: its key is a setting, and so is how many panes a split takes.
const keyGroups = () => {
  const p = prefixSpec().label, n = `1–${MAX_PANES}`;
  const after = [`After ${p}`, [[p, "Leave the terminal; the next key acts"], ["n", "Next session that needs you, then what finished"], ["j k", "Next or previous session"], ["l", "The last session you were in"],
    [n, "A pane by number"], ["← → ↑ ↓", "The pane that way"], ["⇧ ←", "Swap with the pane that way, or ⇧H J K L"], ["z", "Zoom the pane, or restore"], ["s", "Split"], ...termAfterRows(), ["/", "Go to"], ["⇧1–9", "Open a board"], ["↵", "Back to the terminal"], ["esc", "Stay out of the terminal"]]];
  return [...KEYS, ...tabsKeyGroups()].flatMap((group) => group[0] === "Session" ? [[group[0], group[1].map(([keys, what]) => [keys.replace("1–4", n), what])], after] : [group]);
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
    const groups = keyGroups().map(([name, rows]) => [name, rows.filter(([keys, what]) => !q || what.toLowerCase().includes(q) || keys.toLowerCase().includes(q) || name.toLowerCase().includes(q))]).filter(([, rows]) => rows.length);
    fill(list, groups.length ? groups.map(([name, rows]) => h("section", {}, h("h2", { textContent: name }), h("div", { class: "keysheet" }, rows.flatMap(([keys, what]) => [keyCaps(keys), h("span", { textContent: what })]))))
      : h("div", { class: "empty-line", textContent: "No key does that" }));
  };
  search.addEventListener("input", paint);
  dialog.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); dialog.close(); } });
  dialog.addEventListener("close", () => { dialog.remove(); if (back && back.isConnected && back !== document.body) back.focus({ preventScroll: true }); });
  const checkButton = h("button", { type: "button", class: "linkish", textContent: "Check for updates" });
  checkButton.onclick = () => checkUpdates(checkButton);
  const credit = h("p", { class: "keys-credit" }, `Context Hub${hubVersion ? ` ${hubVersion.commit} of ${hubVersion.date}` : ""} · `, checkButton, " · By ", h("a", { href: "https://github.com/ChristianAlmurr", target: "_blank", rel: "noopener noreferrer", textContent: "Christian Almurr" }));
  fill(dialog, h("div", { class: "keys-top" }, h("h1", { textContent: "Keyboard" }), h("button", { class: "icon", type: "button", title: "Close", onclick: () => dialog.close() }, uiIcon("close"))), search, list, credit);
  paint();
  document.body.append(dialog);
  dialog.show();
  search.focus();
}

// ── Session tabs (Settings › Features › Session tabs) ──
// Every session you open becomes a tab along the top of the main area, as in a browser. A tab holds what the hash
// holds: one session, or a split (its layout, h(a,v(b,c))). So a split or a board is one tab, and splitting, closing a
// pane, swapping or zooming inside it changes that tab, not the list. Opening a session from the sidebar, Home or Go to
// focuses the tab that holds it (a pane of a split tab gets the focus), or opens a tab after the one you were in. ×,
// a middle click or ⌫ on a tab closes the tab only; the session keeps running. Tabs are kept per browser (hub.tabs).
// On a phone they are a count in the top bar that opens a sheet. Off, nothing here draws and the hub is as it was.
const TABS_KEY = "hub.tabs", TABS_MAX = 40;
// With the sidebar on the right (body[data-sidebar=right], the sidebar feature's), the session's panel takes the left.
const panelLeft = () => document.body.dataset.sidebar === "right";
// A project's colour, where the sidebar feature gives projects one (projectColour, feature_project_colours).
const tabColour = (list) => { try { return list.length === 1 && typeof projectColour === "function" && feature("project_colours") ? projectColour(list[0].project) || "" : ""; } catch { return ""; } };
const MAC = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || "");
const TAB_MOD = MAC ? "⌘" : "Ctrl+";
// seen: the layout the page shows now ("" off a session page); last: the tab you were in most lately; target: a tab the
// person picked, which is switched to and never rewritten; pane: a pane to focus once its tab shows.
const tabs = { list: [], seen: "", last: "", target: null, pane: null, dragged: 0, shownOn: "" };
{
  const kept = saved.get(TABS_KEY, null);
  if (kept && Array.isArray(kept.list)) tabs.list = kept.list.filter((t) => t && typeof t.l === "string" && t.l).slice(0, TABS_MAX).map((t) => ({ l: t.l, z: typeof t.z === "string" ? t.z : null }));
  if (kept && typeof kept.last === "string") tabs.last = kept.last;
}
const keepTabs = () => saved.set(TABS_KEY, { list: tabs.list, last: tabs.last });
const tabLeaves = (t) => t.l.split(/[(),]/).filter((part) => part && part !== "h" && part !== "v");
const tabSessions = (t) => tabLeaves(t).map(session).filter(Boolean);
const tabHash = (t) => `#/s/${t.l}${t.z && tabLeaves(t).length > 1 && tabLeaves(t).includes(t.z) ? `~${t.z}` : ""}`;
const tabsWanted = () => feature("tabs") && tabs.list.length >= (pref("tabs_hide_single", true) ? 2 : 1);
// One mark for a tab: its session's own, or for a split what needs you beats finished and unread beats working.
const tabState = (list) => {
  if (list.length === 1) return orbState(list[0]);
  const kind = rollupOf(list);
  return kind ? ROLLUP_ORB[kind] : list.some((s) => s.alive) ? (list.every((s) => s.kind === "shell") ? "shell" : "idle") : "closed";
};
const tabTitle = (t, list) => {
  if (list.length === 1) return bareTitle(list[0]);
  const board = boards().find((b) => b.layout === t.l);
  if (board) return board.name;
  return list.length ? `${bareTitle(list[0])} + ${list.length - 1}` : "Closed session";
};
const tabWhere = (list) => {
  if (list.length > 1) return `${list.length} panes`;
  const p = list[0] && ownerOf(list[0]);
  return p ? (p.hub ? "Hub" : p.display) : "";
};
const tabTip = (t, list) => list.length === 1 ? rowTip(list[0]) : list.map((s) => `${bareTitle(s)}: ${DOT_WORDS[orbState(s)] || s.state}`).join("\n");
// Follows the hash. Called by render() before the page draws, so it only reads the route.
const syncTabs = () => {
  if (!feature("tabs") || !hub.ready) return;
  const before = tabs.list.length;
  tabs.list = tabs.list.filter((t) => tabLeaves(t).some((id) => session(id)));  // a tab whose sessions were all deleted goes
  const r = route();
  if (r.name !== "session") { tabs.seen = ""; tabs.target = null; if (tabs.list.length !== before) keepTabs(); return; }
  const text = layoutText(r.layout);
  let at = tabs.list.findIndex((t) => t.l === text);
  if (text !== tabs.seen) {
    const was = tabs.list.findIndex((t) => t.l === tabs.seen);
    const inside = tabs.target !== text && was >= 0 && tabLeaves(tabs.list[was]).some((id) => r.ids.includes(id));
    if (inside) {  // the split changed shape from within: the same tab, and a tab that held the result already merges into it
      tabs.list[was] = { l: text, z: null };
      if (at >= 0 && at !== was) tabs.list.splice(at, 1);
      at = tabs.list.findIndex((t) => t.l === text);
    } else if (at < 0) {
      const after = tabs.list.findIndex((t) => t.l === (was >= 0 ? tabs.seen : tabs.last));
      at = after >= 0 ? after + 1 : tabs.list.length;
      tabs.list.splice(at, 0, { l: text, z: null });
      while (tabs.list.length > TABS_MAX) { const old = tabs.list.findIndex((t) => t.l !== text); tabs.list.splice(old, 1); }
      at = tabs.list.findIndex((t) => t.l === text);
    }
  }
  tabs.seen = tabs.last = text;
  tabs.target = null;
  if (at >= 0) tabs.list[at].z = r.zoom || null;
  keepTabs();
  if (tabs.pane && r.ids.includes(tabs.pane)) {
    const id = tabs.pane;
    tabs.pane = null;
    setTimeout(() => { const now = route(); if (now.name === "session" && now.ids.includes(id) && pageKeys.jump) pageKeys.jump(now.ids.indexOf(id)); }, 0);
  }
};
const openTab = (i) => {
  const t = tabs.list[i];
  if (!t) return;
  if (t.l === tabs.seen) { if (pageKeys.Enter) pageKeys.Enter(); return; }
  tabs.target = t.l;
  go(tabHash(t));
};
const closeTab = (i) => {
  const t = tabs.list[i];
  if (!t) return;
  const showing = t.l === tabs.seen, list = tabSessions(t), title = tabTitle(t, list);
  const hadFocus = tabsBar.contains(document.activeElement);
  tabs.list.splice(i, 1);
  if (tabs.last === t.l) tabs.last = "";
  keepTabs();
  if (showing) {
    const next = tabs.list[i] || tabs.list[i - 1];
    if (next) openTab(tabs.list.indexOf(next));
    else go(list[0] ? `#/p/${P(list[0].project)}` : "#/");
  }
  drawTabs();
  if (hadFocus) { const near = tabsStrip.querySelectorAll(".tab-main")[Math.min(i, tabs.list.length - 1)]; if (near) near.focus({ preventScroll: true }); }
  say(`Closed the tab ${title}. ${list.some((s) => s.alive) ? "The session keeps running." : ""}`.trim());
};
const moveTab = (i, by) => {
  const j = i + by;
  if (j < 0 || j >= tabs.list.length) return;
  const [t] = tabs.list.splice(i, 1);
  tabs.list.splice(j, 0, t);
  keepTabs();
  drawTabs();
  const link = tabsStrip.querySelector(`[data-key="${CSS.escape(`tab:${t.l}`)}"]`);
  if (link) link.focus({ preventScroll: true });
  say(`Moved to place ${j + 1} of ${tabs.list.length}`);
};
// A session on a split tab: that tab opens and the session's pane takes the focus. None when it's on screen already,
// when it has a tab of its own, or when no tab holds it (then the hash opens a tab as usual).
const tabFor = (id) => {
  const r = route();
  if ((r.name === "session" && r.ids.includes(id)) || tabs.list.some((t) => t.l === id)) return null;
  return tabs.list.find((t) => tabLeaves(t).includes(id)) || null;
};
// At a desk only: a phone shows one pane at a time, so a session opened there opens on its own, as before.
const tabsFocus = (id) => {
  if (!feature("tabs") || phone.matches) return false;
  const t = tabFor(id);
  if (!t) return false;
  tabs.pane = id;
  openTab(tabs.list.indexOf(t));
  return true;
};
document.addEventListener("click", (e) => {
  if (!feature("tabs") || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest && e.target.closest('a[href^="#/s/"]');
  if (!a || a.closest("#tabs, .tabs-sheet")) return;
  const m = (a.getAttribute("href") || "").match(/^#\/s\/([0-9a-f]{8})$/);
  if (m && tabsFocus(m[1])) e.preventDefault();
}, true);

// The bar, at a desk: a row of tabs that scrolls sideways when they don't fit, and a list of them all at its end.
const tabsStrip = h("div", { class: "tabs-strip", role: "list" });
const tabsMore = h("button", { type: "button", class: "icon tabs-more", title: "All tabs", "aria-haspopup": "menu", hidden: true, onclick: (e) => tabsMenu(e.currentTarget) }, svg('<path d="m4 6 4 4 4-4"/>'));
const tabsBar = h("nav", { id: "tabs", "aria-label": "Tabs" }, tabsStrip, tabsMore);
const markTabsEdge = () => {
  const over = tabsStrip.scrollWidth > tabsStrip.clientWidth + 1;
  tabsMore.hidden = !over;
  tabsStrip.classList.toggle("more-left", over && tabsStrip.scrollLeft > 1);
  tabsStrip.classList.toggle("more-right", over && tabsStrip.scrollLeft + tabsStrip.clientWidth < tabsStrip.scrollWidth - 1);
};
tabsStrip.addEventListener("scroll", markTabsEdge, { passive: true });
// The tab in front is kept in view by scrolling the row alone: scrollIntoView would move the page under it too.
const showTabOn = () => {
  const on = tabsStrip.querySelector(".tab.on");
  if (!on) return;
  const left = on.offsetLeft - tabsStrip.offsetLeft, right = left + on.offsetWidth;
  if (left < tabsStrip.scrollLeft) tabsStrip.scrollLeft = Math.max(0, left - 24);
  else if (right > tabsStrip.scrollLeft + tabsStrip.clientWidth) tabsStrip.scrollLeft = right - tabsStrip.clientWidth + 24;
};
new ResizeObserver(() => { showTabOn(); markTabsEdge(); }).observe(tabsStrip);
tabsStrip.addEventListener("wheel", (e) => { if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && tabsStrip.scrollWidth > tabsStrip.clientWidth) { e.preventDefault(); tabsStrip.scrollLeft += e.deltaY; } }, { passive: false });
const tabRow = (t, i) => {
  const list = tabSessions(t), on = t.l === tabs.seen, one = list.length === 1 ? list[0] : null;
  const title = tabTitle(t, list), where = tabWhere(list);
  const read = !!one && one.state === "finished" && attentionKind(one) === "idle";
  const link = h("a", { class: "tab-main", href: tabHash(t), "data-key": `tab:${t.l}`, "aria-current": on ? "page" : undefined, title: tabTip(t, list), draggable: "false",
    "aria-label": `${title}${where ? `, ${where}` : ""}, ${DOT_WORDS[tabState(list)] || ""}`,
    onclick: (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); if (Date.now() - tabs.dragged > 250) openTab(tabs.list.indexOf(t)); },
    onauxclick: (e) => { if (e.button === 1) { e.preventDefault(); closeTab(tabs.list.indexOf(t)); } },
    onmousedown: (e) => { if (e.button === 1) e.preventDefault(); },  // no autoscroll under the middle button
    onkeydown: (e) => {
      const at = tabs.list.indexOf(t), links = [...tabsStrip.querySelectorAll(".tab-main")];
      if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); closeTab(at); }
      else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && e.shiftKey) { e.preventDefault(); moveTab(at, e.key === "ArrowLeft" ? -1 : 1); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); const next = links[at + (e.key === "ArrowLeft" ? -1 : 1)]; if (next) next.focus(); }
      else if (e.key === "Home" || e.key === "End") { e.preventDefault(); const next = links[e.key === "Home" ? 0 : links.length - 1]; if (next) next.focus(); }
    } },
    h("span", { class: "tab-orb" }, orbOf(`tab:${t.l}`, tabState(list))),
    list.length > 1 ? h("span", { class: "tab-split" }, uiIcon("split")) : null,
    h("span", { class: "tab-t", dir: "auto", textContent: title }),
    where ? h("span", { class: "tab-p", dir: "auto", textContent: where }) : null);
  const colour = tabColour(list);
  return h("div", { class: `tab ${on ? "on" : ""} ${read ? "read" : ""} ${one && attentionKind(one) === "needs" ? "hot" : ""} ${colour ? "coloured" : ""}`, role: "listitem", "data-tab": t.l, style: colour ? `--tab-pc:${colour}` : undefined }, link,
    h("button", { type: "button", class: "tab-x", tabindex: "-1", title: "Close tab. The session keeps running.", "aria-label": `Close the tab ${title}`, onclick: () => closeTab(tabs.list.indexOf(t)) }, uiIcon("close")));
};
// On a session page at a desk the tabs take the top bar's row, beside the panel button, so a session has two bars
// above it, not four (polish-session). Elsewhere they stay their own row above the page's header.
const tabsMerged = () => hub.ready && tabsWanted() && !phone.matches && route().name === "session";
function drawTabs() {
  syncTabs();
  drawTabsButton();
  const want = hub.ready && tabsWanted() && !phone.matches;
  if (!want) { if (tabsBar.isConnected) tabsBar.remove(); drawn.delete(tabsStrip); if (top_.classList.contains("with-tabs") && page.drawTop) page.drawTop(); return; }
  const merged = tabsMerged();
  if (merged !== top_.classList.contains("with-tabs") && page.drawTop) page.drawTop();  // the header draws the tabs in, or lets them go
  if (merged && tabsBar.parentNode !== top_) { const menu = top_.querySelector(".menu-btn"); if (menu) menu.after(tabsBar); else top_.prepend(tabsBar); drawn.delete(tabsStrip); }
  if (!merged && tabsBar.nextElementSibling !== top_) { top_.before(tabsBar); drawn.delete(tabsStrip); }
  const sig = tabs.list.map((t) => { const list = tabSessions(t); return [t.l, t.z, tabTitle(t, list), tabWhere(list), tabState(list), list.map((s) => [attentionKind(s), s.state, s.said || "", s.asking || ""])]; });
  if (!differs(tabsStrip, sig, tabs.seen, orbsReady)) return;
  const scroll = tabsStrip.scrollLeft;
  fill(tabsStrip, tabs.list.map(tabRow));
  tabsStrip.scrollLeft = scroll;
  if (tabs.shownOn !== tabs.seen) showTabOn();
  tabs.shownOn = tabs.seen;
  markTabsEdge();
  pruneOrbs();
}
const tabsMenu = (anchor) => popover(anchor, tabs.list.map((t, i) => {
  const list = tabSessions(t);
  return { name: tabTitle(t, list), say: [tabWhere(list), i < 9 ? `${TAB_MOD}${i + 1}` : ""].filter(Boolean).join(" · "), dot: tabState(list), on: t.l === tabs.seen, run: () => openTab(i) };
}));
// Drag a tab sideways to move it. Mouse only: a touch scrolls the row.
tabsStrip.addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || e.pointerType !== "mouse") return;
  const tab = e.target.closest(".tab");
  if (!tab || e.target.closest(".tab-x")) return;
  const startX = e.clientX, grab = startX - tab.getBoundingClientRect().left;
  let moving = false;
  const slide = (x) => {
    tab.style.transform = "";
    const box = tabsStrip.getBoundingClientRect(), natural = tab.getBoundingClientRect().left;
    const left = Math.min(box.right - tab.offsetWidth, Math.max(box.left, x - grab));
    tab.style.transform = `translateX(${Math.round(left - natural)}px)`;
  };
  const move = (m) => {
    if (!moving) {
      if (Math.abs(m.clientX - startX) < 5) return;
      moving = true;
      tab.classList.add("dragging");
      tabsStrip.classList.add("reordering");
    }
    const others = [...tabsStrip.children].filter((el) => el !== tab);
    const before = others.find((el) => { const r = el.getBoundingClientRect(); return m.clientX < r.left + r.width / 2; }) || null;
    if (before !== tab.nextElementSibling && !(before === null && tab === tabsStrip.lastElementChild)) {
      const from = new Map(others.map((el) => [el, el.getBoundingClientRect().left]));
      tabsStrip.insertBefore(tab, before);
      if (!stillMotion()) others.forEach((el) => {
        const shift = from.get(el) - el.getBoundingClientRect().left;
        if (!shift) return;
        el.style.transition = "none"; el.style.transform = `translateX(${shift}px)`;
        requestAnimationFrame(() => { el.style.transition = ""; el.style.transform = ""; });
      });
    }
    const box = tabsStrip.getBoundingClientRect();
    if (m.clientX < box.left + 24) tabsStrip.scrollLeft -= 12; else if (m.clientX > box.right - 24) tabsStrip.scrollLeft += 12;
    slide(m.clientX);
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    window.removeEventListener("pointercancel", up);
    if (!moving) return;
    tab.classList.remove("dragging");
    tabsStrip.classList.remove("reordering");
    tab.style.transform = "";
    const order = [...tabsStrip.children].map((el) => el.dataset.tab);
    tabs.list = order.map((l) => tabs.list.find((t) => t.l === l)).filter(Boolean);
    tabs.dragged = Date.now();
    keepTabs();
    drawn.delete(tabsStrip);
    drawTabs();
    say(`Moved to place ${order.indexOf(tab.dataset.tab) + 1} of ${order.length}`);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
  window.addEventListener("pointercancel", up);
});
// ⌘1–⌘8 open the tab in that place and ⌘9 the last, as a browser does (Ctrl on other systems). Not while a dialog,
// a menu or Settings' key recorder has the keyboard. Its keys never reach a terminal.
window.addEventListener("keydown", (e) => {
  if (!feature("tabs") || e.defaultPrevented || keyCatcher || e.altKey || e.shiftKey || !/^Digit[1-9]$/.test(e.code)) return;
  if (!(MAC ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey)) return;
  if (document.querySelector("dialog[open]:not(.keys-help):not(.tabs-sheet), .popup") || !tabs.list.length) return;
  e.preventDefault();
  e.stopPropagation();
  const n = Number(e.code.slice(5)), i = n === 9 ? tabs.list.length - 1 : n - 1;
  if (!tabs.list[i]) { say(`There's no tab ${n}`); return; }
  const sheetOpen = document.querySelector("dialog.tabs-sheet[open]");
  if (sheetOpen) sheetOpen.close();
  openTab(i);
}, true);

// On a phone: a count in the top bar (setTop puts it there, drawTabs keeps it current), opening a sheet of the tabs.
const tabsButtonWords = () => { const needs = tabs.list.filter((t) => tabSessions(t).some((s) => attentionKind(s) === "needs")).length; return [tabs.list.length, needs]; };
// The phone's tabs: a stack glyph and the plain count, never a keycap; a 6px rose mark when one needs you.
UI.tabs = '<rect x="2.5" y="5.5" width="9" height="8" rx="1"/><path d="M5 3h8.5v8"/>';
function tabsTopButton() {
  if (!hub.ready || !tabsWanted() || !phone.matches) return null;
  const [n, needs] = tabsButtonWords();
  return h("button", { type: "button", class: "icon tabs-count", title: "Tabs", "aria-label": `${n} tabs${needs ? `, ${needs} need you` : ""}`, "aria-haspopup": "dialog", onclick: openTabsSheet },
    uiIcon("tabs"), h("span", { class: "tabs-n", textContent: n > 99 ? "99+" : String(n) }), needs ? h("i", { class: "tabs-hot", "aria-hidden": "true" }) : null);
}
function drawTabsButton() {
  const have = top_.querySelector(".tabs-count"), want = tabsTopButton();
  if (!want) { if (have) have.remove(); return; }
  if (have && have.getAttribute("aria-label") === want.getAttribute("aria-label")) return;
  if (have) have.replaceWith(want);
  else { const find = top_.querySelector(".find-btn"); if (find) find.before(want); }
}
function openTabsSheet() {
  const old = document.querySelector("dialog.tabs-sheet");
  if (old) old.close();
  const list = h("ul", { class: "tabs-list", "aria-label": "Tabs" });
  const dialog = h("dialog", { class: "tabs-sheet", "aria-label": "Tabs" });
  const paint = () => {
    if (!tabs.list.length) { dialog.close(); return; }
    fill(list, tabs.list.map((t, i) => {
      const items = tabSessions(t), on = t.l === tabs.seen, one = items.length === 1 ? items[0] : null;
      const line = one ? rowLine(one) || DOT_WORDS[shownState(one)] || "" : items.map(bareTitle).join(", ");
      return h("li", { class: `tabs-row ${on ? "on" : ""}` },
        h("a", { href: tabHash(t), "aria-current": on ? "page" : undefined, "data-key": `sheet:${t.l}`, onclick: (e) => { e.preventDefault(); dialog.close(); openTab(i); } },
          h("span", { class: "row-orb" }, orbOf(`sheet:${t.l}`, tabState(items), 16)),
          h("span", { class: "tabs-lines" }, h("span", { class: "tabs-head" }, h("b", { dir: "auto", textContent: tabTitle(t, items) }), h("span", { class: "tabs-where", dir: "auto", textContent: tabWhere(items) })),
            line ? h("span", { class: `tabs-line st-${one ? shownState(one) : tabState(items)}`, dir: "auto", textContent: line }) : null)),
        h("button", { type: "button", class: "icon tabs-x", "aria-label": `Close the tab ${tabTitle(t, items)}`, onclick: () => { closeTab(i); paint(); } }, uiIcon("close")));
    }));
  };
  fill(dialog, h("div", { class: "tabs-sheet-top" }, h("h1", { textContent: "Tabs" }), h("span", { class: "faint", textContent: "Closing a tab leaves its session running" }),
    h("button", { type: "button", class: "icon", title: "Close", "aria-label": "Close", onclick: () => dialog.close() }, uiIcon("close"))), list);
  paint();
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });  // a tap on the backdrop
  sheet(dialog);
  const on = list.querySelector(".tabs-row.on a") || list.querySelector("a");
  if (on) { on.focus({ preventScroll: true }); const row = on.closest("li"); if (row.offsetTop + row.offsetHeight > list.clientHeight) list.scrollTop = row.offsetTop - 8; }
}
phone.addEventListener("change", () => { drawn.delete(tabsStrip); drawTabs(); });
window.addEventListener("hub:settings", () => { drawn.delete(tabsStrip); drawTabs(); });

// ── The session side panel (Settings › Features › Session side panel) ──
// The right panel of a session page becomes a host for panelsFor(s): a row of tabs, Overview first, over the panel
// that is chosen. Besides the fields addPanel's comment names, a panel may have update(s, box, ctx), called with each
// new state while it shows; render(s, box, ctx) runs once when it is chosen or the session changes, and leave() when
// it goes. ctx is the page's: { sid, rail, review(path), shared(), hide(), multi() }. Which panel was chosen last is
// kept per browser (sidePanel); open or shut, and how wide, stay the page's own, per session, as before.
const SP_KEY = "sidePanel";
const sidePanelHost = ({ box, sid, ctx }) => {
  const tabsRow = h("div", { class: "sp-tabs", role: "tablist", "aria-label": "Side panel" });
  const head = h("div", { class: "sp-head" }, tabsRow,
    h("button", { type: "button", class: "icon sp-close", title: "Hide the panel (p)", "aria-label": "Hide the panel", onclick: () => ctx.hide() }, uiIcon("close")));
  const owner = h("div", { class: "sp-for", hidden: true });
  const body = h("div", { class: "sp-body", role: "tabpanel", tabindex: "-1" });
  let shown = { id: null, sid: null, panel: null };
  const list = () => { const s = session(sid()); return s ? panelsFor(s) : []; };
  const current = () => { const all = list(), want = saved.get(SP_KEY, "overview"); return all.find((p) => p.id === want) || all[0] || null; };
  const leave = () => { const was = shown.panel; shown = { id: null, sid: null, panel: null }; if (was && was.leave) { try { was.leave(); } catch { /* a panel's own trouble stays its own */ } } };
  const pick = (id, focus) => {
    saved.set(SP_KEY, id);
    draw();
    if (focus) focusTab();
  };
  const focusTab = () => { const on = tabsRow.querySelector('[aria-selected="true"]'); if (on) on.focus({ preventScroll: true }); };
  const stripEdge = () => { tabsRow.classList.toggle("more", tabsRow.scrollLeft + tabsRow.clientWidth < tabsRow.scrollWidth - 1); tabsRow.classList.toggle("more-left", tabsRow.scrollLeft > 1); };
  // The chosen tab is always in view, clear of the faded edges, measured on screen: the row alone scrolls.
  const showChosen = () => {
    const on = tabsRow.querySelector('[aria-selected="true"]'), row = tabsRow.getBoundingClientRect();
    if (on && row.width) {
      const r = on.getBoundingClientRect(), fade = 24;
      if (r.left < row.left + (tabsRow.scrollLeft > 1 ? fade : 0)) tabsRow.scrollLeft -= row.left - r.left + (on.previousElementSibling ? fade : 0);
      else if (r.right > row.right - fade) tabsRow.scrollLeft += r.right - row.right + (on.nextElementSibling ? fade : 0);
    }
    stripEdge();
  };
  tabsRow.addEventListener("scroll", stripEdge, { passive: true });
  new ResizeObserver(showChosen).observe(tabsRow);
  // The tabs follow the ARIA pattern: ←/→ (and Home, End) move and choose, Esc goes back to the pane.
  tabsRow.addEventListener("keydown", (e) => {
    const all = [...tabsRow.querySelectorAll('[role="tab"]')], at = all.indexOf(document.activeElement);
    const to = { ArrowLeft: at - 1, ArrowRight: at + 1, Home: 0, End: all.length - 1 }[e.key];
    if (to !== undefined && all.length) { e.preventDefault(); const next = all[(to + all.length) % all.length]; pick(next.dataset.panel, true); }
  });
  box.addEventListener("keydown", (e) => { if (e.key === "Escape" && !e.defaultPrevented && !(e.target.closest && e.target.closest("input, textarea, .review"))) { e.preventDefault(); e.stopPropagation(); ctx.back(); } });
  const draw = (force) => {
    const s = session(sid()), all = list(), p = current();
    if (box.firstChild !== head) box.replaceChildren(head, owner, body);
    if (differs(tabsRow, all.map((x) => [x.id, x.title]), p && p.id)) {
      // Reading panels (Overview, Changes, Shared) are words; tools a feature adds with an icon (Artifacts, Browser,
      // Devices) are their icon, named on hover and to screen readers, after a rule. A wide panel shows their names too.
      fill(tabsRow, all.map((x, i) => {
        const tool = !!(x.icon && UI[x.icon]), first = tool && !(all[i - 1] && all[i - 1].icon && UI[all[i - 1].icon]);
        return h("button", { type: "button", role: "tab", class: `sp-tab ${tool ? "sp-tool" : ""} ${first && i ? "sp-tool-first" : ""}`, "data-panel": x.id, "data-key": `sp:${x.id}`, id: `sp-tab-${x.id}`,
          title: tool ? x.title : undefined, "aria-selected": p && x.id === p.id ? "true" : "false", tabindex: p && x.id === p.id ? "0" : "-1", onclick: () => pick(x.id) },
          tool ? uiIcon(x.icon) : null, h("span", { class: tool ? "sp-tool-name" : "", textContent: x.title }));
      }));
      const on = tabsRow.querySelector('[aria-selected="true"]');
      if (on) body.setAttribute("aria-labelledby", on.id);
      requestAnimationFrame(showChosen);
    }
    const several = ctx.multi() && s;
    owner.hidden = !several;
    if (several && differs(owner, s.id, s.title, shownState(s))) fill(owner, dot(shownState(s)), h("span", { class: "name", dir: "auto", textContent: s.title }));
    if (!s || !p) { leave(); fill(body, h("div", { class: "empty-line", textContent: "Nothing to show for this session." })); return; }
    if (force || shown.id !== p.id || shown.sid !== s.id) {
      leave();
      shown = { id: p.id, sid: s.id, panel: p };
      body.replaceChildren();
      body.scrollTop = 0;
      try { const node = p.render(s, body, ctx); if (node) body.append(node); }
      catch { fill(body, retryLine(`${p.title} didn't open.`, () => draw(true))); }
    } else if (p.update) {
      try { p.update(s, body, ctx); } catch { /* the next state tries again */ }
    }
  };
  return { draw, leave, focus: focusTab, current: () => (current() || {}).id || null, body, pick };
};
// What the Overview and Changes panels read: GET /api/sessions/<id>/overview, kept a few seconds here as on the server,
// and asked again while gh is still looking for a pull request.
const overviews = new Map();
const overviewOf = (sid, fresh) => {
  const kept = overviews.get(sid);
  if (kept && !fresh && Date.now() - kept.at < 3000) return kept.promise;
  const promise = api(`/api/sessions/${sid}/overview`);
  overviews.set(sid, { at: Date.now(), promise });
  promise.catch(() => overviews.delete(sid));
  return promise;
};
const copyText = async (text, said = "Copied") => {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const area = h("textarea", { style: "position:fixed;opacity:0;pointer-events:none" });
    area.value = text;
    document.body.append(area);
    area.select();
    const ok = document.execCommand && document.execCommand("copy");
    area.remove();
    if (!ok) { toast("This browser didn't let the hub copy. Select the text instead.", true); return; }
  }
  toast(said);
};
const spRow = (label, ...value) => h("div", { class: "sp-row" }, h("span", { class: "sp-label", textContent: label }), h("div", { class: "sp-value" }, value));
const spWhen = (seconds) => seconds ? h("time", { dateTime: new Date(seconds * 1000).toISOString(), title: new Date(seconds * 1000).toLocaleString("en-GB"), textContent: agoWords(seconds) }) : h("span", { class: "faint", textContent: "Not yet" });
const spShort = (url) => url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
UI.github = '<path d="M6 13.5c-3 .9-3-1.5-4.2-1.8M10 15.5v-2.3a2 2 0 0 0-.6-1.6c2-.2 4.1-1 4.1-4.5a3.5 3.5 0 0 0-1-2.4 3.2 3.2 0 0 0 0-2.4s-.8-.2-2.6 1a8.9 8.9 0 0 0-4.7 0C3.4 2.1 2.6 2.3 2.6 2.3a3.2 3.2 0 0 0 0 2.4 3.5 3.5 0 0 0-1 2.4c0 3.5 2.1 4.3 4.1 4.5a2 2 0 0 0-.6 1.6v2.3"/>';
UI.pr = '<circle cx="4.5" cy="3.5" r="1.5"/><circle cx="4.5" cy="12.5" r="1.5"/><circle cx="11.5" cy="12.5" r="1.5"/><path d="M4.5 5v6M11.5 11V6.5a2 2 0 0 0-2-2H7M8.5 3 7 4.5 8.5 6"/>';
UI.copy = '<rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 5.5v-2a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2"/>';
UI.memory = '<path d="M3 2.5h7.5L13 5v8.5H3Z"/><path d="M5.5 7h5M5.5 9.5h5M5.5 12h3"/>';
UI.link = UI.shared;
const overviewPanel = {
  id: "overview", title: "Overview", order: 0, feature: "side_panel",
  render(s, box, ctx) {
    box.dataset.sid = s.id;
    const top = h("div", { class: "sp-overview" });
    box.append(top);
    const stop = loadingIn(top, "Reading where this session works…", () => box.dataset.sid === s.id && top.isConnected);
    const paint = (o) => {
      stop();
      if (!top.isConnected || box.dataset.sid !== s.id) return;
      const now = session(s.id) || s, p = project(now.project);
      const section = (title, ...rows) => { const kids = rows.flat().filter(Boolean); return kids.length ? h("section", { class: "sp-section" }, h("h2", { textContent: title }), kids) : null; };
      const linkRow = (icon, main, sub, href, extra) => h("div", { class: "sp-link" }, h("span", { class: "sp-icon" }, uiIcon(icon)),
        h("span", { class: "sp-link-main" }, href ? h("a", { href, target: href.startsWith("#") ? undefined : "_blank", rel: href.startsWith("#") ? undefined : "noopener noreferrer", dir: "auto", textContent: main }) : h("span", { dir: "auto", textContent: main }),
          sub ? h("small", { dir: "auto", textContent: sub }) : null), extra || null);
      const repo = o.repo_url ? linkRow(o.host === "github.com" ? "github" : "external", spShort(o.repo_url).split("/").slice(1).join("/"), o.host, o.repo_url) : null;
      const pr = o.pr ? linkRow("pr", `#${o.pr.number} ${o.pr.title}`, `${o.pr.draft ? "Draft" : o.pr.state === "open" ? "Open" : o.pr.state === "merged" ? "Merged" : o.pr.state === "closed" ? "Closed" : o.pr.state} pull request`, o.pr.url)
        : o.pr_pending ? linkRow("pr", "Looking for a pull request…", "", null) : o.repo_url && o.host === "github.com" && o.pr_said === "none" ? linkRow("pr", "No pull request for this branch", "", null) : null;
      const finder = o.at_mac && o.exists ? h("button", { type: "button", class: "quiet sp-act", title: "Show this folder in Finder, on this Mac", onclick: once("Opening…", async () => { await api(`/api/sessions/${s.id}/reveal`, {}); }) }, "Open in Finder") : null;
      const folder = o.folder ? h("div", { class: "sp-link sp-folder" }, h("span", { class: "sp-icon" }, uiIcon("folder")),
        h("span", { class: "sp-link-main" }, h("code", { dir: "auto", title: o.path, textContent: o.folder }),
          o.exists ? h("span", { class: "sp-acts" }, h("button", { type: "button", class: "quiet sp-act", title: o.path, onclick: () => copyText(o.path, "Path copied") }, uiIcon("copy"), "Copy path"), finder) : h("small", { textContent: "Not there any more" }))) : null;
      const tree = now.tree || null;
      const branchSub = o.worktree ? `Worktree of ${o.worktree.main}` : tree ? "Worktree" : o.detached ? "Detached HEAD" : "";
      const treeFacts = tree ? [tree.ahead ? `${tree.ahead} ahead` : "", tree.changed ? `${tree.changed} uncommitted` : "", tree.merged ? "merged" : ""].filter(Boolean).join(" · ") : "";
      const branch = o.branch ? h("div", { class: "sp-link" }, h("span", { class: "sp-icon" }, uiIcon("branch")),
        h("span", { class: "sp-link-main" }, h("code", { dir: "auto", textContent: o.branch }), branchSub || treeFacts ? h("small", { dir: "auto", textContent: [branchSub, treeFacts].filter(Boolean).join(" · ") }) : null)) : null;
      const memory = o.memory && p && !p.hub ? linkRow("memory", `Memory of ${p.display}`, p.lessons ? `${p.lessons} ${p.lessons === 1 ? "lesson" : "lessons"}` : "", `#/p/${P(p.name)}/memory`) : null;
      const noGit = o.no_vcs ? h("p", { class: "sp-note", textContent: "The hub never runs git in this folder." }) : !o.git && o.exists && now.project !== HUB ? h("p", { class: "sp-note", textContent: "Not a git repository." }) : null;
      const claude = now.kind === "claude";
      const facts = [
        claude ? spRow("Model", h("span", { textContent: modelName(now.model) || now.model || "Default" })) : spRow("Kind", h("span", { textContent: "Terminal" })),
        claude && now.mode ? spRow("Mode", h("span", { textContent: modeName(now.mode) || now.mode })) : null,
        claude && now.effort ? spRow("Effort", h("span", { textContent: now.effort })) : null,
        spRow("Started", spWhen(now.created)),
        o.active || now.changedAt ? spRow("Active", spWhen(o.active || now.changedAt)) : null,
        o.transcript ? spRow("Transcript", h("code", { class: "sp-id", title: o.transcript, textContent: o.transcript.slice(0, 8) }),
          h("button", { type: "button", class: "icon", title: "Copy the transcript id", "aria-label": "Copy the transcript id", onclick: () => copyText(o.transcript, "Transcript id copied") }, uiIcon("copy"))) : null,
      ];
      const links = (o.links || []).map((l) => h("div", { class: "sp-url" }, webLink(l.url, spShort(l.url), s.id)));
      fill(top,
        section("Links", repo, pr, folder, branch, memory, noGit),
        ctx.rail ? h("section", { class: "sp-section" }, h("h2", { textContent: "Now" }), ctx.rail) : null,
        section("Session", facts),
        links.length ? section("From the chat", links) : null);
      if (ctx.rail) ctx.drawRail();
      if (o.pr_pending && box.dataset.sid === s.id) setTimeout(() => { if (top.isConnected && box.dataset.sid === s.id) overviewOf(s.id, true).then(paint, () => {}); }, 2500);
    };
    box.overviewPaint = paint;
    overviewOf(s.id).then(paint, (error) => { stop(); if (top.isConnected) fill(top, retryLine(error.known ? error.message : "The overview didn't load.", () => overviewOf(s.id, true).then(paint))); });
  },
  // A new state: the facts the page already has redraw at once; what only the server knows, at most every ten seconds.
  update(s, box) {
    const key = JSON.stringify([s.model, s.mode, s.effort, s.title, s.tree, s.changes, s.state === "working"]);
    const due = Date.now() - (box.overviewAsked || 0) > 10000;
    if (key === box.overviewKey && !due) return;
    box.overviewKey = key;
    box.overviewAsked = Date.now();
    if (box.overviewPaint) overviewOf(s.id, due).then(box.overviewPaint, () => {});
  },
};
const changesPanel = {
  id: "changes", title: "Changes", order: 10, feature: "side_panel",
  available: (s) => s.project !== HUB,
  render(s, box, ctx) {
    box.dataset.sid = s.id;
    const top = h("div", { class: "sp-changes" });
    box.append(top);
    const stop = loadingIn(top, "Reading the changes…", () => box.dataset.sid === s.id && top.isConnected);
    const paint = (o) => {
      stop();
      if (!top.isConnected || box.dataset.sid !== s.id) return;
      if (o.no_vcs) return fill(top, h("div", { class: "empty-line", textContent: "The hub never runs git in this folder." }));
      if (!o.git) return fill(top, h("div", { class: "empty-line", textContent: o.exists ? "This folder isn't a git repository." : "This session's folder isn't there any more." }));
      const files = o.files || [];
      if (!files.length) return fill(top, h("div", { class: "empty-line", textContent: "Nothing changed since the last commit." }));
      const added = files.reduce((n, f) => n + (f.added || 0), 0), removed = files.reduce((n, f) => n + (f.removed || 0), 0);
      const name = (path) => { const at = path.lastIndexOf("/"); return at < 0 ? ["", path] : [path.slice(0, at + 1), path.slice(at + 1)]; };
      fill(top,
        h("div", { class: "sp-changes-top" }, h("span", { class: "mono" }, counts({ added, removed })), h("span", { class: "faint", textContent: ` · ${files.length} ${files.length === 1 ? "file" : "files"}` }),
          h("span", { class: "strip-fill" }), h("button", { type: "button", class: "btn", onclick: () => ctx.review() }, "Review")),
        h("ul", { class: "sp-files", "aria-label": "Changed files" }, files.map((f) => {
          const [dir, file] = name(f.path);
          return h("li", {}, h("button", { type: "button", class: "sp-file", title: `Review ${f.path}`, onclick: () => ctx.review(f.path) },
            h("span", { class: `sp-mark ${f.new ? "is-new" : ""}`, "aria-label": f.new ? "New" : "Changed", textContent: f.new ? "A" : "M" }),
            h("span", { class: "sp-path" }, dir ? h("span", { class: "sp-dir", dir: "rtl" }, h("bdi", { dir: "ltr", textContent: dir })) : null, h("span", { class: "sp-name", dir: "auto", textContent: file })),
            f.binary ? h("span", { class: "sp-n faint", textContent: "binary" }) : f.new ? h("span", { class: "sp-n mono n-add", textContent: `+${f.added}` }) : h("span", { class: "sp-n mono" }, counts(f))));
        })));
    };
    box.changesPaint = paint;
    box.changesKey = JSON.stringify(s.changes);
    overviewOf(s.id).then(paint, (error) => { stop(); if (top.isConnected) fill(top, retryLine(error.known ? error.message : "The changes didn't load.", () => overviewOf(s.id, true).then(paint))); });
  },
  update(s, box) {
    const key = JSON.stringify(s.changes);
    if (key === box.changesKey) return;
    box.changesKey = key;
    if (box.changesPaint) overviewOf(s.id, true).then(box.changesPaint, () => {});
  },
};
// Subagents, images, files and links: what the right panel showed before, drawn by the page as it always was.
const sharedPanel = { id: "shared", title: "Shared", order: 20, feature: "side_panel", render(s, box, ctx) { ctx.shared(); } };
[overviewPanel, changesPanel, sharedPanel].forEach(addPanel);
// The keys sheet names these only while their feature is on.
const tabsKeyGroups = () => [
  feature("tabs") ? ["Tabs", [[`${TAB_MOD}1–8`, "The tab in that place"], [`${TAB_MOD}9`, "The last tab"], ["← →", "Move between tabs, on the tab bar"], ["⇧← ⇧→", "Move the tab, on the tab bar"], ["⌫", "Close the tab, on the tab bar"]]] : null,
  feature("side_panel") ? ["Side panel", [["p", "Show or hide it"], ["⇧P", "Go into it, opening it if it's hidden"], ["← →", "Another panel, on its tabs"], ["esc", "Back to the session"]]] : null,
].filter(Boolean);

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
const CHORDS = { ",": () => go("#/settings"), h: () => go("#/"), d: inProject("dreams"), m: inProject("memory"), n: () => newSession(projectHere() || undefined), s: () => { side.contains(document.activeElement) || moveSide(0); } };
let chordTimer = null;
const chording = () => chordTimer !== null;
const endChord = () => { clearTimeout(chordTimer); chordTimer = null; drawStatus(); };
const startChord = () => { clearTimeout(chordTimer); chordTimer = setTimeout(endChord, 1500); drawStatus(); };

const isTyping = (target) => target && target.closest && target.closest('input:not([type=checkbox], [type=radio], [type=button], [type=submit], [type=file], [type=range], [type=color]), textarea, select, [contenteditable]:not([contenteditable="false"]), .xterm');
let enterAt = 0, enterHeld = false;
window.addEventListener("keyup", (e) => { if (e.key === "Enter") enterHeld = false; }, true);
window.addEventListener("keydown", (e) => {
  if (keyCatcher) { keyCatcher(e); return; }  // Settings is recording a key: it goes there and nowhere else
  const key = e.key;
  if (key === "Enter" && (enterHeld || Date.now() - enterAt < 300) && inTerminal()) { e.preventDefault(); e.stopPropagation(); return; }  // the Enter that moved you here isn't meant for Claude
  if ((e.metaKey || e.ctrlKey) && key.toLowerCase() === "k") { e.preventDefault(); openPalette(); return; }
  if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && key === ",") { e.preventDefault(); go("#/settings"); return; }  // ⌘, as every Mac app (feat/nav)
  if ((e.metaKey || e.ctrlKey) && key.toLowerCase() === "b") { e.preventDefault(); if (phone.matches) setSide(!sideOpen()); else setRail(!railed()); return; }
  // The prefix waits for one key; anything it doesn't know goes on as usual.
  if (prefix.armed && !["Shift", "Control", "Alt", "Meta", "CapsLock", "Fn"].includes(key)) {
    const run = prefixAction(e);
    endPrefix(false);
    if (run) { e.preventDefault(); e.stopPropagation(); run(); return; }
  }
  if (isPrefix(e)) {
    e.preventDefault();
    if (!document.querySelector("dialog[open]:not(.keys-help), .popup")) armPrefix();
    return;
  }
  // This listener runs first (capture). Esc inside something that closes itself on Esc is that thing's, not "go up a page".
  if (key === "Escape" && e.target.closest && e.target.closest(".review, .peek-pop, .line-note-edit, .side-panel")) return;
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

// ── Artifacts: what a session made, opened right here (Settings › Features › Artifacts; hub_artifacts.py) ──
// #/s/<id>/artifacts lists a session's, #/p/<project>/artifacts a project's, and a key after either picks one. The side
// panel shows the same list. Files come from /api/sessions/<id>/raw/<path>, where an HTML page runs sandboxed in an
// origin of its own (never the hub's) and an SVG is only ever an image. With the switch off, none of it is drawn.
UI.artifacts = '<path d="M3 2.5h6.5l3.5 3.5v7.5H3z"/><path d="M9.5 2.5V6H13"/><path d="m6.5 8.5-1.5 1.5 1.5 1.5M9.5 8.5l1.5 1.5-1.5 1.5"/>';
const ART_KINDS = [["html", "Pages"], ["markdown", "Docs"], ["image", "Images"], ["pdf", "PDFs"], ["video", "Video"], ["audio", "Audio"], ["data", "Data"], ["code", "Code"], ["text", "Text"], ["link", "Links"]];
const ART_WORD = { html: "Page", markdown: "Document", image: "Image", pdf: "PDF", video: "Video", audio: "Recording", data: "Data", code: "Code", text: "Text", link: "Published link" };
const ART_ICON = {
  html: '<rect x="1.5" y="2.5" width="13" height="11" rx="1"/><path d="M1.5 5.5h13"/>',
  markdown: '<path d="M4 1.5h5l3 3v10H4z"/><path d="M9 1.5v3h3M6 8h4M6 10.5h4"/>',
  image: '<rect x="2" y="3" width="12" height="10" rx="1"/><circle cx="6" cy="6.5" r="1.2"/><path d="m2.5 12 4-4 3 3 2-2 2.5 2.5"/>',
  pdf: PV.pdf, video: PV.video, audio: PV.audio,
  data: '<rect x="2" y="2.5" width="12" height="11"/><path d="M2 6h12M2 9.5h12M6.5 2.5v11"/>',
  code: '<path d="m5.5 4.5-3.5 3.5 3.5 3.5M10.5 4.5l3.5 3.5-3.5 3.5"/>',
  text: PV.file, link: PV.link,
};
const ART_ACT = {
  download: '<path d="M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10"/>',
  copy: '<rect x="5" y="5" width="8.5" height="8.5" rx="1"/><path d="M3 10.5V3a.5.5 0 0 1 .5-.5H10"/>',
  zoom: '<circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3M5 7h4M7 5v4"/>',
  browser: '<rect x="1.5" y="2.5" width="13" height="11" rx="1"/><path d="M1.5 5.5h13M8 8v3M6.5 9.5h3"/>',
};
const artKey = (item) => item.url || item.path;
const artRaw = (item, extra = "") => `/api/sessions/${item.sid}/raw${item.path.split("/").map(encodeURIComponent).join("/")}${extra}`;
const artFresh = (item) => artRaw(item, `?v=${Math.round((item.mtime || 0) * 1000)}`);
const artWhen = (item) => item.when || item.mtime || atOf(item);
const artLinkName = (item) => { const card = linkCards.get(item.url), host = linkParts(item.url).host; return (card && card.title) || (/(^|\.)claude\.(ai|site)$/.test(host) ? "Claude artifact" : host); };
// On the home project's list, a hub-wide session's artifact carries the hub mark, as the session does in the sidebar.
const artHubwide = () => h("span", { class: "hubwide-tag", role: "img", "aria-label": "hub-wide", title: HUBWIDE_TIP }, uiIcon("hub"));
const artHash = (where, key) => `${where.sid ? `#/s/${where.sid}/artifacts` : `#/p/${P(where.project)}/artifacts`}${key ? `/${encodeURIComponent(key)}` : ""}`;
// "Open in browser": the browser feature's own opener when it has one, else its route.
const artOpenInBrowser = (url, title) => (window.hubBrowser && window.hubBrowser.open) ? window.hubBrowser.open({ url, title }) : go(`#/browser/${encodeURIComponent(url)}`);

// Code, lightly: comments, strings, numbers and keywords, one line at a time, for the languages a session writes most.
const ART_HASH = /^(py|sh|bash|zsh|rb|yml|yaml|toml|r|pl|ex|exs|dockerfile|makefile|ini|tf)$/;
const ART_WORDS = new Set(("and as async await break case catch class const continue def default defer del do elif else enum except export extends false final finally fn for from func function go guard if impl import in interface is lambda let match mod mut new nil none not null or package pass private protected pub public raise return self static struct super switch this throw throws true try type typeof undefined use val var void when where while with yield None True False").split(" "));
const artTokens = (line, ext) => {
  if (line.length > 1200) return [line];
  const comment = ART_HASH.test(ext) ? "#.*$" : ext === "css" ? "\\/\\*.*?(?:\\*\\/|$)" : ext === "sql" ? "--.*$" : "\\/\\/.*$|\\/\\*.*?(?:\\*\\/|$)";
  const re = new RegExp(`(${comment})|("(?:[^"\\\\]|\\\\.)*"?|'(?:[^'\\\\]|\\\\.)*'?|\`(?:[^\`\\\\]|\\\\.)*\`?)|(\\b\\d[\\d_.xXa-fA-F]*\\b)|([A-Za-z_$][\\w$]*)`, "g");
  const out = [];
  let last = 0, m;
  while ((m = re.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index));
    const cls = m[1] ? "c" : m[2] ? "s" : m[3] ? "n" : ART_WORDS.has(m[4]) ? "k" : "";
    out.push(cls ? h("i", { class: `tk-${cls}`, textContent: m[0] }) : m[0]);
    last = re.lastIndex;
  }
  if (last < line.length) out.push(line.slice(last));
  return out;
};
const artCode = (text, ext) => {
  const lines = text.replace(/\n$/, "").split("\n"), shown = lines.slice(0, 20000);
  return h("div", { class: "art-code-wrap" }, h("pre", { class: "art-code", style: `--digits:${String(shown.length).length}` },
    shown.map((line, i) => h("span", {}, i < 4000 ? artTokens(line, ext) : line))),
  lines.length > shown.length ? h("div", { class: "empty-line", textContent: `${lines.length - shown.length} more lines aren't shown.` }) : null);
};
// A CSV or TSV as a table: quoted cells kept whole, numbers right-aligned.
const artCsv = (text, sep) => {
  const rows = [];
  let row = [], cell = "", quoted = false;
  for (let i = 0; i < text.length && rows.length <= 2001; i++) {
    const c = text[i];
    if (quoted) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') quoted = false; else cell += c; continue; }
    if (c === '"' && !cell) quoted = true;
    else if (c === sep) { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const head = rows[0] || [], rest = rows.slice(1, 2001);
  const numeric = head.map((_, col) => rest.length > 0 && rest.every((r) => r[col] === undefined || r[col] === "" || /^-?[\d.,]+%?$/.test(r[col].trim())));
  return h("div", { class: "art-table-wrap" },
    h("table", { class: "art-table" },
      h("thead", {}, h("tr", {}, head.map((cell, col) => h("th", { class: numeric[col] ? "num" : "", textContent: cell })))),
      h("tbody", {}, rest.map((r) => h("tr", {}, head.map((_, col) => h("td", { class: numeric[col] ? "num" : "", textContent: r[col] === undefined ? "" : r[col] })))))),
    rows.length > 2001 ? h("div", { class: "empty-line", textContent: "Showing the first 2,000 rows." }) : null);
};
// JSON as a tree: objects and arrays fold, the first two levels open.
const artJson = (value) => {
  let budget = 6000;
  const leaf = (v) => h("span", { class: `jv ${v === null ? "j-null" : typeof v === "string" ? "j-str" : typeof v === "number" ? "j-num" : "j-bool"}`, textContent: typeof v === "string" ? JSON.stringify(v) : String(v) });
  const node = (key, v, depth) => {
    if (--budget < 0) return null;
    const label = key === null ? null : h("span", { class: "jk", textContent: `${key}: ` });
    if (v === null || typeof v !== "object") return h("div", { class: "jrow" }, label, leaf(v));
    const pairs = Array.isArray(v) ? v.map((x, i) => [i, x]) : Object.entries(v);
    const brief = Array.isArray(v) ? `[${pairs.length}]` : `{${pairs.length}}`;
    if (!pairs.length) return h("div", { class: "jrow" }, label, h("span", { class: "jv j-null", textContent: Array.isArray(v) ? "[]" : "{}" }));
    return h("details", { class: "jnode", open: depth < 2 }, h("summary", {}, label, h("span", { class: "jb", textContent: brief })),
      h("div", { class: "jkids" }, pairs.slice(0, 500).map(([k, x]) => node(k, x, depth + 1)), pairs.length > 500 ? h("div", { class: "jrow faint", textContent: `${pairs.length - 500} more` }) : null));
  };
  return h("div", { class: "art-json" }, node(null, value, 0));
};
const artData = (text, item) => {
  if (item.ext === "csv" || item.ext === "tsv") return artCsv(text, item.ext === "tsv" ? "\t" : ",");
  try {
    const value = item.ext === "jsonl" || item.ext === "ndjson" ? text.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l)) : JSON.parse(text);
    return artJson(value);
  } catch { return h("div", {}, h("div", { class: "empty-line", textContent: "This isn't valid JSON, so it shows as text." }), artCode(text, "json")); }
};

// Find where in the conversation the session made it: open the session, read its conversation, light the latest turn
// that names it.
const artReveal = (item) => {
  const needle = item.kind === "link" ? item.url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "") : item.name;
  go(`#/s/${item.sid}`);
  let tries = 0;
  const look = () => {
    const pane = document.querySelector(`.pane[data-sid="${CSS.escape(item.sid)}"]`);
    let log = pane && pane.querySelector(".record-body");
    if (pane && !log && tries === 0) { const read = pane.querySelector(".read-toggle"); if (read) read.click(); }
    const turns = log ? [...log.querySelectorAll(".turn")] : [];
    const hit = turns.reverse().find((t) => (t.textContent || "").includes(needle) || [...t.querySelectorAll("button[title], a[href]")].some((el) => (el.title || el.href || "").includes(needle)));
    if (hit) {
      [hit, ...hit.querySelectorAll("details")].forEach((d) => { if (d.tagName === "DETAILS" && (d.textContent || "").includes(needle)) d.open = true; });
      hit.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
      hit.classList.remove("art-found"); void hit.offsetWidth; hit.classList.add("art-found");
      setTimeout(() => hit.classList.remove("art-found"), 2600);
      say(`Shown where ${item.kind === "link" ? "the link" : item.name} was made`);
      return;
    }
    if (++tries < 30) setTimeout(look, 200);
    else if (log) toast("That point of the conversation is too far back to show here.");
  };
  setTimeout(look, 250);
};

// The list and the viewer. `where` is { sid } or { project }. `narrow()` says one column (a phone, the side panel):
// the list, then one artifact full size with a way back. `keep(key, open)` keeps the pick where the page wants it (the
// hash), or nowhere (the panel).
function artifactsBrowser(where, { narrow, keep }) {
  let items = [], kind = "all", query = "", sel = null, viewing = false, loaded = false, loadedOnce = false, fetchedAt = 0, busy = null, shown = "", watchSig = "", alive = true;
  const root = h("div", { class: "art" });
  const search = h("input", { class: "search art-search", type: "search", placeholder: "Filter by name", "aria-label": "Filter artifacts by name", autocomplete: "off", spellcheck: false,
    oninput: () => { query = search.value.trim().toLowerCase(); drawList(); } });
  const chips = h("div", { class: "art-chips", role: "group", "aria-label": "Show" });
  const list = h("div", { class: "art-list", role: "listbox", "aria-label": "Artifacts" });
  const listSide = h("div", { class: "art-side" }, h("div", { class: "art-tools" }, search, chips), list);
  const back = h("button", { class: "icon art-back", type: "button", title: "Back to the list", onclick: () => closeView() }, svg(PV.back));
  const name = h("b", { dir: "auto" }), meta = h("span", { class: "art-meta" });
  const acts = h("div", { class: "art-acts" });
  const body = h("div", { class: "art-body", tabindex: "-1" });
  const head = h("div", { class: "art-head" }, back, h("div", { class: "art-title" }, name, meta), acts);
  const pane = h("section", { class: "art-view", "aria-label": "Artifact" }, head, body);
  root.append(listSide, pane);
  const one = () => narrow();
  const filtered = () => items.filter((i) => (kind === "all" || i.kind === kind) && (!query || `${i.name || ""} ${i.rel || ""} ${i.url || ""} ${i.title || ""}${i.hubwide ? " hub-wide" : ""}`.toLowerCase().includes(query)));
  const find = (key) => items.find((i) => artKey(i) === key);
  const layout = () => { root.classList.toggle("narrow", one()); root.classList.toggle("viewing", one() && viewing && !!find(sel)); root.classList.toggle("empty", loaded && !items.length); };

  const drawChips = () => {
    const counts = {};
    items.forEach((i) => { counts[i.kind] = (counts[i.kind] || 0) + 1; });
    const kinds = ART_KINDS.filter(([k]) => counts[k]);
    if (kind !== "all" && !counts[kind]) kind = "all";
    chips.hidden = kinds.length < 2;
    fill(chips, [["all", "All", items.length], ...kinds.map(([k, word]) => [k, word, counts[k]])].map(([k, word, n]) =>
      h("button", { type: "button", class: `art-chip ${kind === k ? "on" : ""}`, "aria-pressed": kind === k ? "true" : "false", "data-key": `kind:${k}`,
        onclick: () => { kind = k; drawChips(); drawList(); } }, word, h("b", { textContent: String(n) }))));
  };
  const rowOf = (item) => {
    const key = artKey(item), on = key === sel;
    const rel = shortPath(item.rel || item.path || ""), dir = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
    const where_ = item.kind === "link" ? linkParts(item.url).host + linkParts(item.url).rest : [dir, ART_WORD[item.kind], item.size !== undefined ? sizeWords(item.size) : null].filter(Boolean).join(" · ");
    return h("button", { type: "button", class: `art-row${on ? " on" : ""}`, role: "option", "aria-selected": on ? "true" : "false", tabindex: on ? 0 : -1, "data-key": `art:${key}`, "data-nav": `art:${key}`,
      title: item.kind === "link" ? item.url : shortPath(item.path), onclick: () => pick(key, true) },
      h("span", { class: `art-ic k-${item.kind}` }, svg(ART_ICON[item.kind] || PV.file)),
      h("span", { class: "art-main" }, h("b", { dir: "auto", textContent: item.kind === "link" ? artLinkName(item) : item.name }),
        h("small", { dir: "auto" }, where.project && item.hubwide ? artHubwide() : null, where.project && item.title ? `${where_} · ${item.title}` : where_)),
      h("time", { class: "art-when", title: whenShort(artWhen(item)), textContent: ago(artWhen(item)) }));
  };
  const drawList = () => {
    const rows = filtered();
    if (!loaded) return;
    if (!items.length) {
      fill(list, h("div", { class: "empty-line art-none" }, where.sid ? "Nothing yet. Pages, documents, pictures and data this session writes show up here." : "Nothing yet. What this project's sessions make shows up here."));
      return;
    }
    if (!rows.length) { fill(list, h("div", { class: "empty-line art-none", textContent: "Nothing matches." })); return; }
    fill(list, rows.map(rowOf));
    if (!list.querySelector('[tabindex="0"]')) { const first = list.querySelector(".art-row"); if (first) first.tabIndex = 0; }
  };
  const focusRow = (key) => { const row = list.querySelector(`[data-key="${CSS.escape(`art:${key}`)}"]`); if (row) { row.focus({ preventScroll: true }); row.scrollIntoView({ block: "nearest" }); } };
  const move = (step) => {
    const rows = filtered();
    if (!rows.length) return;
    const at = rows.findIndex((i) => artKey(i) === sel);
    const next = rows[step === Infinity ? rows.length - 1 : step === -Infinity ? 0 : Math.max(0, Math.min(rows.length - 1, at < 0 ? 0 : at + step))];
    pick(artKey(next), false);
    focusRow(artKey(next));
  };
  list.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const act = { ArrowDown: () => move(1), ArrowUp: () => move(-1), Home: () => move(-Infinity), End: () => move(Infinity),
      Enter: () => { if (sel) openView(); } }[e.key];
    if (act) { e.preventDefault(); e.stopPropagation(); act(); }
  });

  // Picking shows it at a desk; on one column it opens only when asked (a tap, Enter).
  function pick(key, open) {
    if (!find(key)) return;
    sel = key;
    list.querySelectorAll(".art-row").forEach((row) => { const on = row.dataset.key === `art:${key}`; row.classList.toggle("on", on); row.setAttribute("aria-selected", on ? "true" : "false"); row.tabIndex = on ? 0 : -1; });
    if (!one()) { showItem(find(key)); keep && keep(key, false); }
    else if (open) openView();
  }
  function openView() {
    if (!sel) return;
    if (one()) { viewing = true; layout(); showItem(find(sel)); keep && keep(sel, true); back.focus({ preventScroll: true }); }
    else body.focus({ preventScroll: true });
  }
  function closeView(fromHash) {
    if (!viewing) return false;
    viewing = false;
    layout();
    stopMedia();
    if (!fromHash && keep) keep(null, true);
    requestAnimationFrame(() => focusRow(sel));
    return true;
  }
  const stopMedia = () => body.querySelectorAll("video, audio").forEach((m) => m.pause());

  const act = (title, icon, run, href) => href
    ? h("a", { class: "icon", href, target: "_blank", rel: "noopener noreferrer", title, "aria-label": title, ...(run ? { download: run } : {}) }, svg(icon))
    : h("button", { class: "icon", type: "button", title, onclick: run }, svg(icon));
  const copy = (text, said) => guard(async () => { await navigator.clipboard.writeText(text); toast(said); })();
  const drawActs = (item) => {
    const file = item.kind !== "link";
    fill(acts,
      item.kind === "html" && feature("browser") ? act("Open in the browser", ART_ACT.browser, () => artOpenInBrowser(location.origin + artRaw(item), item.name)) : null,
      item.kind === "image" ? act("Zoom", ART_ACT.zoom, () => zoom(item)) : null,
      act("Show in chat", UI.chat, () => artReveal(item)),
      act(file ? "Copy path" : "Copy link", ART_ACT.copy, () => copy(file ? item.path : item.url, file ? "Path copied" : "Link copied")),
      file ? act("Download", ART_ACT.download, item.name, artRaw(item, "?download=1")) : null,
      act("Open in a new tab", UI.external, null, file ? artFresh(item) : item.url));
  };
  const zoom = (item) => {
    const pics = filtered().filter((i) => i.kind === "image");
    const gallery = (pics.length ? pics : [item]).map((i) => ({ sid: i.sid, src: artFresh(i), name: i.name, kind: "image", at: i.at }));
    imageViewer(gallery, Math.max(0, pics.indexOf(item)));
  };
  const metaOf = (item) => [ART_WORD[item.kind], item.size !== undefined ? sizeWords(item.size) : null, item.versions > 1 ? `${item.versions} versions` : null,
    whenShort(artWhen(item)), where.project && item.hubwide ? "Hub-wide" : null, where.project && item.title ? item.title : null, item.by ? "by a subagent" : null].filter(Boolean).join(" · ");
  let token = 0;
  async function showItem(item, again) {
    if (!item) { shown = ""; fill(name); fill(meta); fill(acts); fill(body, h("div", { class: "empty-line art-pick", textContent: items.length ? "Pick one to see it here." : "" })); return; }
    const stamp = `${artKey(item)}\n${item.mtime || ""}\n${item.size || ""}`;
    if (stamp === shown && !again) return;
    const same = shown.split("\n")[0] === artKey(item), changed = same && stamp !== shown;
    shown = stamp;
    const mine = ++token;
    name.textContent = item.kind === "link" ? artLinkName(item) : item.name;
    meta.textContent = metaOf(item);
    meta.title = item.kind === "link" ? item.url : shortPath(item.path);
    pane.setAttribute("aria-label", name.textContent);
    drawActs(item);
    if (changed) { const fresh = h("span", { class: "art-updated", textContent: "Updated" }); meta.append(" · ", fresh); setTimeout(() => fresh.remove(), 4000); }
    const scroll = same ? body.scrollTop : 0;
    const put = (...nodes) => { if (mine !== token) return; fill(body, ...nodes); body.dataset.kind = item.kind; body.dataset.shown = artKey(item); if (scroll) body.scrollTop = scroll; };
    if (!same) { fill(body); delete body.dataset.shown; }  // another file: never its words under this one's name
    if (item.kind === "link") {
      const host = linkParts(item.url).host;
      return put(h("div", { class: "art-link" }, chatLinkCard(item.url, item.sid),
        h("p", { class: "faint", textContent: /(^|\.)claude\.(ai|site)$/.test(host) ? "Published on claude.ai. It opens there, signed in as you." : "Published on the web. It opens in a new tab." }),
        h("a", { class: "btn primary", href: item.url, target: "_blank", rel: "noopener noreferrer" }, uiIcon("external"), `Open ${host}`)));
    }
    if (item.kind === "html") return put(h("iframe", { class: "art-frame", src: artFresh(item), title: item.name, sandbox: "allow-scripts allow-popups allow-downloads allow-modals", referrerPolicy: "no-referrer" }));
    if (item.kind === "image") {
      return put(h("div", { class: `art-pic${item.ext === "svg" ? " vector" : ""}` }, h("img", { src: artFresh(item), alt: item.name, draggable: false, ondblclick: () => zoom(item), onerror: (e) => e.target.replaceWith(h("div", { class: "empty-line", textContent: "This image can't be opened." })) })));
    }
    if (item.kind === "pdf") return put(h("iframe", { class: "art-frame pdf", src: artFresh(item), title: item.name }));
    if (item.kind === "video") return put(h("div", { class: "art-play" }, h("video", { src: artFresh(item), controls: true, playsInline: true, preload: "metadata" })));
    if (item.kind === "audio") return put(h("div", { class: "art-play audio" }, svg(PV.audio), h("audio", { src: artFresh(item), controls: true, preload: "metadata" })));
    const stop = loadingIn(body, "Opening…", () => mine === token);
    let text;
    try { text = await api(`/api/sessions/${item.sid}/artifact-text?path=${encodeURIComponent(item.path)}`); }
    catch (error) { stop(); if (mine === token) put(retryLine(error.message || "That file didn't open.", () => showItem(item, true))); return; }
    stop();
    const cut = text.truncated ? h("div", { class: "empty-line", textContent: `Showing the first ${sizeWords(text.text.length)} of ${sizeWords(text.size)}.` }) : null;
    if (item.kind === "markdown") return put(h("article", { class: "art-doc" }, markdown(text.text, { sid: item.sid })), cut);
    if (item.kind === "data") return put(artData(text.text, item), cut);
    if (item.kind === "code") return put(artCode(text.text, item.ext || ""), cut);
    put(artCode(text.text, "txt"), cut);
  }

  const load = async () => {
    if (busy) return busy;
    busy = (async () => {
      try {
        const data = await api(where.sid ? `/api/sessions/${where.sid}/artifacts` : `/api/p/${P(where.project)}/artifacts`);
        if (!alive) return;
        const before = JSON.stringify(items.map((i) => [artKey(i), i.mtime, i.size, i.at]));
        items = data.items || [];
        loaded = true; fetchedAt = Date.now();
        if (sel && !find(sel)) { sel = null; viewing = false; }
        if (!sel && !one() && items.length) sel = artKey(filtered()[0] || items[0]);
        const unseen = items.filter((i) => i.kind === "link" && !linkCards.has(i.url)).slice(0, 40);
        if (unseen.length) {  // only cards the hub already fetched: listing links never fetches them
          const kept = await api(`/api/preview/cached?${unseen.map((i) => `url=${encodeURIComponent(i.url)}`).join("&")}`).catch(() => ({}));
          Object.entries(kept).forEach(([url, card]) => linkCards.set(url, card));
        }
        if (before !== JSON.stringify(items.map((i) => [artKey(i), i.mtime, i.size, i.at])) || !loadedOnce) { loadedOnce = true; drawChips(); drawList(); }
        layout();
        if (!one() || viewing) showItem(find(sel));
      } catch (error) {
        if (!alive) return;
        if (!loaded) fill(list, retryLine(error.message || "The artifacts didn't load.", () => load()));
      } finally { busy = null; }
    })();
    return busy;
  };
  // Live: the push stream redraws the page whenever a session moves. A session that moved on, or is working, has its
  // list read again (at most every 1.5 s; every 8 s regardless), and the file on show reloads when it changed on disk.
  const refresh = () => {
    if (!alive) return;
    layout();
    const mine = S.sessions.filter((s) => where.sid ? s.id === where.sid : s.project === where.project);
    const sig = JSON.stringify(mine.map((s) => [s.id, s.state, s.activity, s.turn, s.said, s.alive]));
    const working = mine.some((s) => s.state === "working");
    if (Date.now() - fetchedAt < 1500) return;
    if (sig !== watchSig || (working && Date.now() - fetchedAt > 4000) || (!document.hidden && Date.now() - fetchedAt > 8000)) { watchSig = sig; load(); }
  };
  // From the hash: a key there is the pick, and on one column it is open.
  const setPick = (key) => {
    if (!loaded) { sel = key || sel; viewing = !!key && one(); return; }
    if ((key || null) === (one() ? (viewing ? sel : null) : sel) || (!one() && !key)) return;
    if (key && find(key)) { sel = key; drawList(); if (one()) { viewing = true; layout(); showItem(find(key)); } else showItem(find(key)); }
    else if (one()) closeView(true);
  };
  layout();
  fill(list, h("div", { class: "empty-line art-none", role: "status", textContent: "Looking for what this made…" }));
  load();
  return {
    root, load, refresh, setPick, move, back: () => closeView(), viewing: () => one() && viewing,
    focusList: () => { const row = list.querySelector('[tabindex="0"]') || list.querySelector(".art-row"); if (row) row.focus({ preventScroll: true }); },
    leave: () => { alive = false; stopMedia(); },
  };
}

// The page: #/s/<id>/artifacts or #/p/<project>/artifacts, with the pick after it.
function pageArtifacts(where, pick) {
  let pushedOpen = false;
  const browser = artifactsBrowser(where, {
    narrow: () => phone.matches,
    keep: (key, open) => {
      const hash = artHash(where, key);
      if (open && key) { pushedOpen = true; go(hash); }  // one column: back closes it
      else if (open && !key && pushedOpen) { pushedOpen = false; history.back(); }
      else history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
    },
  });
  const drawTop = () => {
    const now = where.sid ? session(where.sid) : null, p = project(where.sid ? (now ? now.project : "") : where.project);
    if (!differs(top_, "artifacts", where, now && now.title, p && tabsKey(p), phone.matches)) return;
    if (where.project && p) { projectTop(p, "artifacts", []); return; }
    setTop([p && !phone.matches ? crumbTo(p) : null, now ? h("a", { class: "crumb-session", href: `#/s/${now.id}`, title: "Back to the session" }, h("span", { class: "t", dir: "auto", textContent: p ? bareTitle(now) : now.title })) : null, tail("Artifacts")].filter(Boolean),
      [now && !phone.matches ? h("a", { class: "btn", href: `#/s/${now.id}`, title: "Back to the session" }, uiIcon("term"), "Session") : null]);
  };
  drawTop();
  view.append(h("div", { class: "art-page" }, browser.root));
  if (pick) browser.setPick(pick);
  const leaveTo = () => go(where.sid ? `#/s/${where.sid}` : `#/p/${P(where.project)}`);
  bind(() => browser.viewing() ? [["esc", "back to the list"]] : [["↑ ↓", "move"], ["↵", phone.matches ? "open" : "view"], ["esc", where.sid ? "session" : "project"]], {
    Escape: () => { if (!browser.back()) leaveTo(); },
    j: () => browser.move(1), k: () => browser.move(-1), ArrowDown: () => browser.focusList(), ArrowUp: () => browser.focusList(),
  });
  if (!phone.matches) setTimeout(() => browser.focusList(), 50);  // a phone keeps its keyboard down
  window.addEventListener("resize", browser.refresh);
  phone.addEventListener("change", drawTop);
  page.update = () => { const r = route(); drawTop(); browser.setPick(r.name === "artifacts" ? r.pick : r.rest); browser.refresh(); };
  page.leave = () => { browser.leave(); window.removeEventListener("resize", browser.refresh); phone.removeEventListener("change", drawTop); };
}

// The side panel's Artifacts: the same list, in one column, the pick shown full size with a way back.
const artPanels = new Set();
addPanel({
  id: "artifacts", title: "Artifacts", icon: "artifacts", feature: "artifacts", order: 40,
  available: (s) => !!s && s.kind === "claude",
  render: (s, box) => {
    const browser = artifactsBrowser({ sid: s.id }, { narrow: () => true, keep: null });
    const node = h("div", { class: "art-panel" }, browser.root, h("a", { class: "quiet art-all", href: `#/s/${s.id}/artifacts` }, uiIcon("external"), "Open full size"));
    let seen = false;
    const end = () => { clearInterval(timer); browser.leave(); artPanels.delete(end); };
    const timer = setInterval(() => { if (node.isConnected) { seen = true; browser.refresh(); } else if (seen) end(); }, 1500);
    artPanels.add(end);
    return node;
  },
  leave: () => [...artPanels].forEach((end) => end()),
});

window.addEventListener("hub-orbs-ready", () => { sideKey = ""; alerts.key = ""; render(); });
setTop([]);
fill(view, h("div", { class: "empty-line hold", textContent: "Connecting to the hub…" }));
drawSide();
drawStatus();
syncSide();
placeAlerts();
// ── Live state: the server pushes what changed, and the 3-second poll stays as the fallback ──
// /api/stream (Server-Sent Events) sends the whole state once, then only what changed: the rows of the sessions that
// did, and any other part that did. While the stream is heard from (a ping comes at least every 10 seconds) the poll
// rests. A phone suspends a page and its connections in the background: back in view, a stream not heard from lately
// is opened again, and a poll fills the gap at once.
const PUSH_QUIET = 15000;
const push = { source: null, base: null, seq: 0, heard: 0, opened: 0, wait: 1000, timer: 0 };
const pushLive = () => !!(push.source && push.base && Date.now() - push.heard < PUSH_QUIET);
const pushCopy = (value) => typeof structuredClone === "function" ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const pushPatch = (d) => {
  const base = push.base, rows = new Map(base.sessions.map((s) => [s.id, s]));
  d.rows.forEach((s) => rows.set(s.id, s));
  d.gone.forEach((id) => rows.delete(id));
  base.sessions = (d.order || base.sessions.map((s) => s.id)).map((id) => rows.get(id)).filter(Boolean);
  Object.assign(base, d.set);
  d.unset.forEach((key) => delete base[key]);
  base.at = d.at;
};
const pushOpen = () => {
  clearTimeout(push.timer); push.timer = 0;
  if (push.source) push.source.close();
  push.source = null; push.base = null;
  if (!window.EventSource) return;
  const source = push.source = new EventSource("/api/stream");
  push.opened = Date.now();
  const heard = () => { push.heard = Date.now(); push.wait = 1000; };
  const take = () => { takeState(pushCopy(push.base)).catch(() => {}); };
  source.addEventListener("full", (e) => { if (push.source !== source) return; const d = JSON.parse(e.data); push.base = d.state; push.seq = d.seq; heard(); take(); });
  source.addEventListener("diff", (e) => {
    if (push.source !== source) return;
    const d = JSON.parse(e.data);
    if (!push.base || d.base !== push.seq) { pushOpen(); return; }  // a missed step: start over from a whole state
    pushPatch(d); push.seq = d.seq; heard(); take();
  });
  source.addEventListener("ping", (e) => { if (push.source !== source) return; heard(); if (push.base && JSON.parse(e.data).seq !== push.seq) pushOpen(); });
  source.onerror = () => {
    if (push.source !== source) return;
    push.base = null;  // the poll carries on until the stream is back
    if (source.readyState === 2) { push.source = null; push.timer = setTimeout(pushOpen, push.wait); push.wait = Math.min(push.wait * 2, 30000); }
  };
};
// What the clock does every 3 seconds: while the stream is live, a poll every other time, as a cheap check on it (the
// server answers from the state the stream comes from); else a poll each time, and a stream gone quiet is opened again.
let clockTurn = 0;
const clockTick = () => {
  if (pushLive()) { if (++clockTurn % 2 === 0) tick(); return; }
  if (!push.timer && (!push.source || Date.now() - Math.max(push.heard, push.opened) > 2 * PUSH_QUIET)) pushOpen();
  tick();
};
const pushBack = () => { if (!pushLive()) { pushOpen(); tick(); } };
document.addEventListener("visibilitychange", () => { if (!document.hidden) pushBack(); });
window.addEventListener("pageshow", (e) => { if (e.persisted) pushBack(); });
window.addEventListener("online", pushBack);
tick();
pushOpen();
// A worker keeps time in a background tab, where the browser slows page timers to about once a minute.
const startClock = () => setInterval(clockTick, 3000);
try {
  const clock = new Worker("/ui/clock.js");
  clock.onmessage = clockTick;
  clock.onerror = () => { clock.terminate(); startClock(); };
} catch { startClock(); }

// ── Sidebar, projects and notices (feat/sidebar): herdr's most-voted asks, each with a switch in Settings › Features ──
// Shared code calls the function declarations below (hoisted, so the first drawSide can use them). Each one checks its
// own switch and, off, gives back exactly what the hub did before. Their state lives in SB, made at the end of this block.
var SB = null;

// The side the sidebar sits on (sidebar_side). body[data-sidebar="left"|"right"] says it, so whatever sits beside the
// sidebar, such as the tabs' side panel, can take the other side.
function sidebarAt() { return pref("sidebar_side", "left") === "right" ? "right" : "left"; }

// ── Project order (feature_project_order, project_order) and hidden projects (feature_hide_projects, hidden_projects) ──
// The order is one list of project names, kept in settings, so every device agrees. Inside a folder, and among the
// projects in none, projects follow it; one it doesn't name yet (a new project) comes after those it does. Sorted by
// what needs you, the sessions keep their attention order and the project list below them follows this one.
function sideOrdered(list) {
  const order = feature("project_order") ? pref("project_order", []) : [];
  if (!Array.isArray(order) || !order.length) return list;
  const at = new Map(order.map((name, i) => [name, i]));
  return list.map((p, i) => [p, at.has(p.name) ? at.get(p.name) : order.length + i]).sort((a, b) => a[1] - b[1]).map(([p]) => p);
}
function hiddenNames() { const list = feature("hide_projects") ? pref("hidden_projects", []) : []; return Array.isArray(list) ? list : []; }
function isHiddenProject(name) { return hiddenNames().includes(name); }
// The projects the sidebar lists, in their order. A hidden one stays reachable from Go to and the Hidden row.
function sideProjects() { return sideOrdered(S.projects).filter((p) => !isHiddenProject(p.name)); }
function hiddenProjects() { return sideOrdered(S.projects).filter((p) => isHiddenProject(p.name)); }
// "Hidden (n)", after the projects: it opens to list them. What they roll up to shows on it, so a hidden project that
// needs you still shows here, as well as in the alerts and notices it always had (unless it is muted).
function hiddenProjectsRow(r, build) {
  const list = hiddenProjects();
  if (!list.length) return null;
  const holds = list.some((p) => r.project === p.name || (r.name === "session" && r.ids.some((id) => session(id) && ownerName(session(id)) === p.name)));
  const open = !!saved.get("hiddenOpen", false) || holds;
  const inside = S.sessions.filter((s) => list.some((p) => p.name === ownerName(s)));
  const kind = list.some((p) => attention(p.name)) ? "needs" : rollupOf(inside);
  const toggle = () => { saved.set("hiddenOpen", !open); sideKey = ""; drawSide(); const again = sideList.querySelector('[data-key="hidden-projects"]'); if (again) again.focus({ preventScroll: true }); };
  return [h("button", { class: "side-fold hidden-fold", type: "button", "aria-expanded": open ? "true" : "false", "data-key": "hidden-projects", onclick: toggle,
    title: open ? "Hide these again" : "Show the hidden projects" },
    h("span", { class: `slot chev ${open ? "open" : ""}`, "aria-hidden": "true" }, svg(UI.chev)), h("span", { textContent: "Hidden" }),
    !open && kind ? h("span", { class: "state" }, rowOrb(ROLLUP_ORB[kind])) : h("span", { class: "fold-n", textContent: list.length })),
    open ? h("div", { class: "side-hidden" }, list.map(build)) : null];
}
function setHidden(p, on) {
  const now = pref("hidden_projects", []).filter((n) => n !== p.name);
  saveSetting("hidden_projects", on ? [...now, p.name] : now);
  toast(on ? `${p.display} is hidden. Go to, and Hidden at the foot of the list, still find it.` : `${p.display} is back in the sidebar`);
}
// The order every project is in now, as names: what a move starts from and writes back whole.
function fullOrder() { return sideOrdered(S.projects).map((p) => p.name); }
function moveProject(name, target, after) {
  if (!name || !target || name === target) return;
  const order = fullOrder().filter((n) => n !== name);
  const at = order.indexOf(target);
  if (at < 0) return;
  order.splice(after ? at + 1 : at, 0, name);
  saveSetting("project_order", order);
  const from = groupOf(name), to = groupOf(target);
  if (from !== to) changeGroups({ op: "move", project: name, id: to || null }, to ? `Moved to ${(groups().find((f) => f.id === to) || {}).name || "the folder"}` : "Out of its folder");
  sideKey = ""; drawSide();
}
// One step up or down among the projects beside it (the same folder, or none), by ⌥↑ ⌥↓ or the ⋯ menu.
function stepProject(name, by) {
  const peers = sideProjects().filter((p) => groupOf(p.name) === groupOf(name));
  const at = peers.findIndex((p) => p.name === name), next = peers[at + by];
  if (at < 0 || !next) { say(by < 0 ? "It's first already" : "It's last already"); return false; }
  moveProject(name, next.name, by > 0);
  say(`Moved ${by < 0 ? "up" : "down"}`);
  return true;
}

// ── Project colours (feature_project_colours, project_colours): one of a curated set, each with a dark and a light tone
// that keeps 3:1 against every surface it sits on. Shown by the project's mark, an edge on its rows, and in Go to.
// Other parts read projectColour(name): "var(--pc-<id>)", or "" for none. ──
function colourChoices() { return [["blue", "Blue"], ["jade", "Jade"], ["pink", "Pink"], ["gold", "Gold"], ["sky", "Sky"], ["violet", "Violet"], ["orange", "Orange"], ["lime", "Lime"], ["slate", "Slate"]]; }
function colourOf(name) {
  if (!feature("project_colours")) return "";
  const map = pref("project_colours", {}) || {}, id = map[name];
  return colourChoices().some(([c]) => c === id) ? id : "";
}
function projectColour(name) { const id = colourOf(name); return id ? `var(--pc-${id})` : ""; }
function colourEdge(name) { const c = name && projectColour(name); return c ? `--pc:${c}` : undefined; }
function pickColour(p) {
  const now = colourOf(p.name);
  const dialog = h("dialog", { class: "confirm colour-sheet", "aria-label": `Colour for ${p.display}` });
  const choose = (id) => { const map = { ...(pref("project_colours", {}) || {}) }; if (id) map[p.name] = id; else delete map[p.name]; saveSetting("project_colours", map); dialog.close(); };
  const keys = (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const all = [...dialog.querySelectorAll("[role=radio]")], at = all.indexOf(e.currentTarget);
    all[(at + (["ArrowRight", "ArrowDown"].includes(e.key) ? 1 : all.length - 1)) % all.length].focus();
  };
  const swatch = ([id, word]) => h("button", { type: "button", role: "radio", class: `swatch pc ${now === id ? "on" : ""}`, "aria-checked": now === id ? "true" : "false", "aria-label": word, title: word,
    tabIndex: now === id ? 0 : -1, style: id ? `--sw:var(--pc-${id})` : "", "data-colour": id, onkeydown: keys, onclick: () => choose(id) }, id ? null : uiIcon("close"));
  fill(dialog, h("h1", { textContent: `Colour for ${p.display}` }), h("p", { class: "sheet-lead", textContent: "It marks the project and its sessions wherever they're listed." }),
    h("div", { class: "swatches pc-swatches", role: "radiogroup", "aria-label": "Colour" }, swatch(["", "None"]), colourChoices().map(swatch)),
    h("div", { class: "actions" }, h("span"), h("div", { class: "right" }, h("button", { type: "button", class: "btn", textContent: "Cancel", onclick: () => dialog.close() }))));
  if (!now) dialog.querySelector("[role=radio]").tabIndex = 0;
  sheet(dialog);
  (dialog.querySelector("[role=radio][tabindex='0']") || dialog.querySelector("[role=radio]")).focus();
}
// What the sidebar adds to a project's ⋯ menu.
function projectMenuExtras(p) {
  const items = [];
  if (feature("project_order") || feature("project_colours") || feature("hide_projects")) items.push({ group: "In the sidebar" });
  if (feature("project_order") && !isHiddenProject(p.name)) {
    const peers = sideProjects().filter((x) => groupOf(x.name) === groupOf(p.name)), at = peers.findIndex((x) => x.name === p.name);
    if (at > 0) items.push({ name: "Move up", say: "⌥↑", icon: "updown", run: () => stepProject(p.name, -1) });
    if (at >= 0 && at < peers.length - 1) items.push({ name: "Move down", say: "⌥↓", icon: "updown", run: () => stepProject(p.name, 1) });
  }
  if (feature("project_colours")) items.push({ name: colourOf(p.name) ? "Change colour…" : "Colour…", icon: "colour", run: () => pickColour(p) });
  if (feature("hide_projects")) items.push(isHiddenProject(p.name) ? { name: "Show in the sidebar", icon: "eye", run: () => setHidden(p, false) } : { name: "Hide from the sidebar", icon: "eyeOff", run: () => setHidden(p, true) });
  return items.length > 1 ? items : [];
}
UI.colour = '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5v11" /><path d="M8 2.5a5.5 5.5 0 0 1 0 11Z" fill="currentColor"/>';
UI.eye = '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z"/><circle cx="8" cy="8" r="2"/>';
UI.eyeOff = '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z"/><path d="m3 13 10-10"/>';
UI.history = '<path d="M2.5 8a5.5 5.5 0 1 0 1.6-3.9"/><path d="M2.5 2.5v2.5H5"/><path d="M8 5v3l2 1.5"/>';

// ── After the sidebar is drawn: colours on its rows, projects that move, and each session's subagents ──
// What changes the drawing beyond what the sidebar's own key already says: the subagents under each live session.
function sidebarExtrasKey() {
  return JSON.stringify([sidebarAt(), feature("subagents") ? S.sessions.filter((s) => !gone(s) && s.agents && s.agents.list && s.agents.list.length).map((s) => [s.id, s.agents.list.map((a) => [a.id, a.state, a.what])]) : 0,
    saved.get("crewOpen", {})]);
}
function decorateSide(order) {
  const rail = order === "rail";
  // Colours: a group carries its project's, and a row sorted by attention carries its session's project's.
  sideList.querySelectorAll(".side-group[data-project]").forEach((g) => { const edge = colourEdge(g.dataset.project); g.classList.toggle("tinted", !!edge && !rail); if (edge) g.style.cssText = edge; });
  if (order === "attention") sideList.querySelectorAll(".side-band .side-row[data-sid]").forEach((row) => { const s = session(row.dataset.sid), edge = s && colourEdge(s.project); row.classList.toggle("tinted", !!edge); if (edge) row.style.cssText = edge; });
  if (rail) return;
  if (feature("project_order")) sideList.querySelectorAll(".side-group[data-project]:not(.hub-group) > .side-row.project").forEach(armProjectRow);
  if (feature("subagents")) sideList.querySelectorAll(".side-row[data-sid]").forEach((row) => { const s = session(row.dataset.sid); if (s && !gone(s)) { const crew = crewOf(s); if (crew) row.after(crew); } });
}
// A project row takes another dropped before or after it (a line shows where), and moves with ⌥↑ ⌥↓ while it has focus.
function armProjectRow(row) {
  const name = row.parentNode.dataset.project;
  if (isHiddenProject(name)) return;
  const half = (e) => e.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2;
  const clear = () => row.classList.remove("drop-before", "drop-after");
  row.addEventListener("dragstart", () => { SB.dragging = name; });
  row.addEventListener("dragend", () => { SB.dragging = null; sideList.querySelectorAll(".drop-before, .drop-after").forEach((el) => el.classList.remove("drop-before", "drop-after")); });
  row.addEventListener("dragover", (e) => {
    if (![...e.dataTransfer.types].includes("text/x-hub-project") || SB.dragging === name) return;
    e.preventDefault(); e.stopPropagation();
    e.dataTransfer.dropEffect = "move";
    const after = half(e);
    row.classList.toggle("drop-after", after); row.classList.toggle("drop-before", !after);
  });
  row.addEventListener("dragleave", clear);
  row.addEventListener("drop", (e) => {
    const moving = e.dataTransfer.getData("text/x-hub-project");
    clear();
    if (!moving || moving === name) return;
    e.preventDefault(); e.stopPropagation();
    moveProject(moving, name, half(e));
    say(`Moved ${(project(moving) || {}).display || moving}`);
  });
  const link = row.querySelector(":scope > a.nav");
  if (link) {
    link.setAttribute("aria-keyshortcuts", "Alt+ArrowUp Alt+ArrowDown");
    link.addEventListener("keydown", (e) => {
      if (!e.altKey || e.metaKey || e.ctrlKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
      e.preventDefault(); e.stopPropagation();
      if (stepProject(name, e.key === "ArrowUp" ? -1 : 1)) { const again = sideList.querySelector(`[data-key="p:${CSS.escape(name)}"]`); if (again) again.focus({ preventScroll: true }); }
    });
  }
}

// ── Subagents under the session that started them (feature_subagents): read-only, from what the state already carries
// (agents.list: the latest six, running first). One line says how many and how many run; it opens to one row each. ──
const CREW_WORDS = { running: "Running", done: "Done", failed: "Failed", stopped: "Stopped" };
function crewOf(s) {
  const list = (s.agents && s.agents.list) || [];
  if (!list.length) return null;
  const running = list.filter((a) => a.state === "running").length, total = (s.agents && s.agents.total) || list.length;
  const kept = saved.get("crewOpen", {}), open = s.id in kept ? !!kept[s.id] : false;  // folded until you open it, so projects stay in view (feat/polish-pages)
  const toggle = () => { saved.set("crewOpen", { ...saved.get("crewOpen", {}), [s.id]: !open }); sideKey = ""; drawSide(); const again = sideList.querySelector(`[data-key="crew:${CSS.escape(s.id)}"]`); if (again) again.focus({ preventScroll: true }); };
  const word = `${total} ${total === 1 ? "subagent" : "subagents"}${running ? `, ${running} running` : ""}`;
  return h("div", { class: "side-crew", "data-crew": s.id },
    h("button", { class: "crew-fold", type: "button", "aria-expanded": open ? "true" : "false", "data-key": `crew:${s.id}`, onclick: toggle, title: open ? "Fold the subagents" : "Show the subagents" },
      h("span", { class: `slot chev ${open ? "open" : ""}`, "aria-hidden": "true" }, svg(UI.chev)), h("span", { class: "crew-word", textContent: word })),
    open ? h("ul", { class: "crew-list", "aria-label": `Subagents of ${s.title}` }, list.map((a) => h("li", { class: `crew-row c-${a.state}`, title: `${a.type}: ${a.what}` },
      h("span", { class: "crew-mark", role: "img", "aria-label": CREW_WORDS[a.state] || a.state }), h("span", { class: "crew-what", dir: "auto", textContent: a.what }),
      h("span", { class: "crew-state", textContent: CREW_WORDS[a.state] || a.state })))) : null);
}

// ── Jump numbers (feature_jump_numbers): the keys that go somewhere by number show that number. Hold ⌥ (⌥1–6 picks a
// pane), or press the prefix (then 1–6, or ⇧1–9 for a board), and each pane of a split, and its row in the sidebar,
// shows its number. Go to numbers its first nine sessions, opened with ⌥1–9. ⌘1–9 is left to the tabs.
// body[data-jump-keys="alt"|"prefix"] is set while they show, for anything else that numbers itself. ──
function showJumps(how) {
  const r = route(), on = how && feature("jump_numbers") && r.name === "session" && r.ids.length > 1;
  document.querySelectorAll("[data-jump]").forEach((el) => el.removeAttribute("data-jump"));
  if (!on) { delete document.body.dataset.jumpKeys; return; }
  document.body.dataset.jumpKeys = how;
  r.ids.slice(0, 6).forEach((id, i) => {
    document.querySelectorAll(`.pane[data-sid="${CSS.escape(id)}"], #side .side-row[data-sid="${CSS.escape(id)}"], #side .side-row[data-sid="${CSS.escape(id)}"] > .nav`).forEach((el) => { el.dataset.jump = String(i + 1); });
  });
}

// ── Notices (feature_notice_tools, notice_time): how long they stay, Clear all, swipe away, and a history per device ──
// How long a notice (or a passing toast) stays, in ms: today's own time unless notice_time says otherwise.
function noticeLeft(kind, fallback) {
  const want = feature("notice_tools") ? pref("notice_time", "auto") : "auto";
  if (want === "stay") return kind === "toast" ? Math.max(fallback, 10000) : Infinity;  // a passing toast still passes
  const n = Number(want);
  return Number.isFinite(n) && n > 0 ? n * 1000 : fallback;
}
// The last 50 notices, kept in this browser (hub.noticeLog), newest first. Only while the switch is on.
function logNotice(banner) {
  if (!banner || !feature("notice_tools")) return;
  const key = String(banner.key || ""), sid = banner.sid || (key.startsWith("s:") ? key.slice(2) : "");
  const entry = { at: Date.now(), kind: banner.kind || "", title: String(banner.title || "").slice(0, 120), line: String(banner.line || "").slice(0, 240), sid,
    go: sid ? `#/s/${sid}` : banner.kind === "catcher" ? "#/catcher" : "" };
  saved.set("hub.noticeLog", [entry, ...saved.get("hub.noticeLog", [])].slice(0, 50));
}
function openNoticeLog() {
  if (document.querySelector("dialog.notice-log")) return;
  const dialog = h("dialog", { class: "notice-log", "aria-label": "Recent notices" });
  const draw = () => {
    const list = saved.get("hub.noticeLog", []);
    fill(dialog, h("header", { class: "log-top" }, h("h1", { textContent: "Recent notices" }), h("span", { class: "faint", textContent: "On this device" }),
      list.length ? h("button", { type: "button", class: "btn", "data-key": "log-clear", textContent: "Clear", onclick: () => { saved.set("hub.noticeLog", []); draw(); dialog.querySelector(".log-close").focus(); } }) : null,
      h("button", { type: "button", class: "icon log-close", title: "Close", "aria-label": "Close", onclick: () => dialog.close() }, uiIcon("close"))),
      list.length ? h("ul", { class: "log-list" }, list.map((n, i) => {
        const s = n.sid && session(n.sid), live = !n.sid || !!s;
        return h("li", {}, h("button", { type: "button", class: `log-row n-${n.kind}`, "data-key": `log:${i}`, disabled: !n.go || !live, title: !live ? "That session is gone" : undefined,
          onclick: () => { dialog.close(); if (n.sid) openWaiting(n.sid); else if (n.go) go(n.go); } },
          slot(n.kind === "needs" ? rowOrb("needs") : n.kind === "done" ? rowOrb("finished") : uiIcon(n.kind === "catcher" ? "catcher" : "bell")),
          h("span", { class: "alert-text" }, h("b", { dir: "auto", textContent: n.title }), n.line ? h("small", { dir: "auto", textContent: n.line }) : null),
          h("time", { class: "faint", dateTime: new Date(n.at).toISOString(), textContent: agoWords(n.at / 1000) })));
      })) : h("div", { class: "empty-line", textContent: "No notices yet. What tells you something shows here too, for when you missed it." }));
  };
  draw();
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  sheet(dialog);
  (dialog.querySelector(".log-row:not(:disabled)") || dialog.querySelector(".log-close")).focus();
}
// After a rename: when Claude couldn't be told yet, say when it will be.
function renamed(answer) { if (answer && answer.pending) toast("Renamed. Claude gets the new name once its input is empty."); }

// ── Where worktrees go (worktree_path): a field with the placeholders, and a live preview of where one would go ──
var SETTING_CONTROLS = {
  worktree: (item, { save, sayIn, value }) => {
    const now = value(item.name) || "";
    const shown = h("div", { class: "wt-preview", role: "status", "aria-live": "polite" });
    const input = h("input", { type: "text", class: "wt-input", value: now, placeholder: ".claude/worktrees/{name}", spellcheck: false, autocomplete: "off", "aria-labelledby": `set-${item.name}-label`, "aria-describedby": `set-${item.name}-help`, "data-key": `set-${item.name}` });
    let timer = 0, asked = 0;
    const ask = async () => {
      const mine = ++asked, text = input.value.trim();
      const first = (S.projects.find((p) => !p.hub) || {}).name || "";
      try {
        const answer = await api(`/api/settings/worktree-preview?template=${encodeURIComponent(text)}&project=${encodeURIComponent(first)}`);
        if (mine !== asked) return;
        fill(shown, answer.ok ? [h("span", { class: "faint", textContent: "A new worktree goes in " }), h("code", { textContent: answer.path }),
          answer.outside ? h("span", { class: "faint", textContent: ". Outside the repo, Claude may ask once to trust the folder." }) : null]
          : h("span", { class: "bad", textContent: answer.why }));
        shown.classList.toggle("bad", !answer.ok);
      } catch { /* the preview waits for the next keystroke */ }
    };
    const keep = async () => { const text = input.value.trim(); if (text !== (value(item.name) || "")) await save({ [item.name]: text }); };
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(ask, 180); });
    input.addEventListener("change", keep);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); keep(); } if (e.key === "Escape") { e.stopPropagation(); input.value = value(item.name) || ""; ask(); } });
    const example = (text) => h("button", { type: "button", class: "chip", textContent: text, onclick: () => { input.value = text; ask(); input.focus(); } });
    ask();
    return h("div", { class: "wt-field" }, input, shown, h("div", { class: "wt-examples" }, h("span", { class: "faint", textContent: "Try" }),
      example("{parent}/{repo}-worktrees/{name}"), example(".worktrees/{branch}"), now ? h("button", { type: "button", class: "quiet", textContent: "Back to .claude/worktrees", onclick: () => { input.value = ""; save({ [item.name]: "" }); } }) : null));
  },
};

// ── This block's state and listeners ──
SB = { dragging: null, altTimer: 0 };
// Hold ⌥ a moment and the numbers show; let go and they're gone. A prefix shows them while it waits for its key.
window.addEventListener("keydown", (e) => {
  if (e.key === "Alt" && !e.repeat && !e.metaKey && !e.ctrlKey) { clearTimeout(SB.altTimer); SB.altTimer = setTimeout(() => showJumps("alt"), 350); }
  else if (e.key !== "Alt") clearTimeout(SB.altTimer);
  // F2 renames the session in hand: the sidebar row with focus, or the pane you're in.
  if (e.key === "F2" && !e.metaKey && !e.ctrlKey && !e.altKey && !document.querySelector("dialog[open], .popup")) {
    const sid = selectedSid(), s = sid && session(sid);
    if (s) { e.preventDefault(); editInSide(s, "rename"); }
  }
});
window.addEventListener("keyup", (e) => { if (e.key === "Alt") { clearTimeout(SB.altTimer); if (document.body.dataset.jumpKeys === "alt") showJumps(null); } });
window.addEventListener("blur", () => { clearTimeout(SB.altTimer); showJumps(null); });
new MutationObserver(() => showJumps(status_.classList.contains("armed") ? "prefix" : null)).observe(status_, { attributes: true, attributeFilter: ["class"] });
window.addEventListener("hashchange", () => showJumps(null));
// A setting changed: the side the sidebar is on applies at once.
window.addEventListener("hub:settings", () => { applyShell(); document.body.classList.toggle("notice-tools", feature("notice_tools")); });
document.body.classList.toggle("notice-tools", feature("notice_tools"));
// Toasts wait while you point at them (with the notice tools on; they let the pointer through otherwise).
toastEl.addEventListener("pointerenter", () => { if (feature("notice_tools") && !toastEl.classList.contains("sticky")) clearTimeout(toast.timer); });
toastEl.addEventListener("pointerleave", () => { if (feature("notice_tools") && !toastEl.classList.contains("sticky") && toastEl.classList.contains("show")) { clearTimeout(toast.timer); toast.timer = setTimeout(hideToast, 2000); } });
// Clear all and the history, over the notices once two are up.
const clearAll = h("button", { type: "button", class: "chip", "data-key": "notice-clear", textContent: "Clear all", onclick: () => { noticeBox.querySelectorAll(".notice").forEach(dropNotice); } });
const noticeTools = h("div", { class: "notice-tools-bar" }, h("button", { type: "button", class: "chip", "data-key": "notice-history", textContent: "Recent", title: "The last 50 notices on this device", onclick: openNoticeLog }), clearAll);
const syncNoticeTools = () => {
  const up = noticeBox.querySelectorAll(".notice:not(.leaving)").length, want = feature("notice_tools") && up >= 1;
  clearAll.hidden = up < 2;
  if (want && noticeBox.lastElementChild !== noticeTools) noticeBox.append(noticeTools);
  else if (!want && noticeTools.parentNode) noticeTools.remove();
};
new MutationObserver(syncNoticeTools).observe(noticeBox, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
// On a phone, a notice swipes away sideways.
noticeBox.addEventListener("pointerdown", (e) => {
  const card = e.target.closest(".notice");
  if (!card || e.pointerType !== "touch" || !feature("notice_tools")) return;
  const x0 = e.clientX, y0 = e.clientY;
  let dx = 0, sideways = null;
  const move = (m) => {
    dx = m.clientX - x0;
    if (sideways === null && (Math.abs(dx) > 8 || Math.abs(m.clientY - y0) > 8)) sideways = Math.abs(dx) > Math.abs(m.clientY - y0);
    if (sideways) { card.style.transform = `translateX(${dx}px)`; card.style.opacity = String(Math.max(0.2, 1 - Math.abs(dx) / 240)); }
  };
  const up = () => {
    window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up);
    if (sideways && Math.abs(dx) > 80) { card.style.transition = stillMotion() ? "none" : "transform .16s var(--out), opacity .16s"; card.style.transform = `translateX(${dx > 0 ? 120 : -120}%)`; dropNotice(card); }
    else { card.style.transition = stillMotion() ? "none" : "transform .2s var(--out), opacity .2s"; card.style.transform = ""; card.style.opacity = ""; setTimeout(() => { card.style.transition = ""; }, 220); }
    if (sideways) card.addEventListener("click", (c) => { c.stopPropagation(); c.preventDefault(); }, { capture: true, once: true });
  };
  window.addEventListener("pointermove", move); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
});
applyShell();
