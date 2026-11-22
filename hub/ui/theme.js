// The page's appearance: theme, accent, density and motion. It loads in <head>, after the stylesheets and before the
// body, so the first paint already has the theme this browser last used (kept in localStorage, "hub.appearance").
// app.js confirms it from the server's settings and calls hubAppearance.apply again (see applyAppearance there).
//   hubAppearance.apply({ theme, accent, density, reduce_motion }) -> what it resolved: { theme, still, ... }
// Theme "system" and motion "system" follow the media queries live. An accent is any CSS colour; the colours made from
// it (the button fill, the ink for links and focus, the wash behind selection) are measured against the theme's own
// surfaces and moved until they pass WCAG AA, so no choice can make text unreadable.
(() => {
  const root = document.documentElement;
  const KEY = "hub.appearance";
  const dark = matchMedia("(prefers-color-scheme: dark)"), still = matchMedia("(prefers-reduced-motion: reduce)");
  let last = {};

  // ── colour arithmetic, in sRGB 0..255 ──
  const probe = document.createElement("canvas").getContext("2d");
  const parse = (css) => {
    if (!css || !(window.CSS && CSS.supports("color", css))) return null;
    probe.fillStyle = "#000"; probe.fillStyle = css;
    const v = probe.fillStyle;  // "#rrggbb", or "rgba(r, g, b, a)" when it has alpha (the alpha is dropped)
    if (v[0] === "#") return [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16));
    const n = v.match(/[\d.]+/g);
    return n ? n.slice(0, 3).map(Number) : null;
  };
  const hex = (c) => "#" + c.map((x) => Math.round(Math.max(0, Math.min(255, x))).toString(16).padStart(2, "0")).join("");
  const lum = (c) => { const [r, g, b] = c.map((x) => { x /= 255; return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const mix = (a, b, t) => a.map((x, i) => x + (b[i] - x) * t);  // t of the way from a to b
  const WHITE = [255, 255, 255], BLACK = [0, 0, 0];
  // The nearest colour on the way from c to `toward` that reaches `ratio` against every one of `grounds`.
  const reach = (c, toward, grounds, ratio) => {
    for (let t = 0; t <= 1; t += 0.02) { const m = mix(c, toward, t); if (grounds.every((g) => contrast(m, g) >= ratio)) return m; }
    return toward;
  };
  const token = (name) => parse(getComputedStyle(root).getPropertyValue(name).trim());

  // An accent's four colours, for the theme now on the page (its tokens are read from the stylesheet).
  const ACCENT_VARS = ["--accent", "--on-accent", "--accent-ink", "--accent-wash", "--accent-sel"];
  const accentFor = (css, light) => {
    const c = parse(css);
    if (!c) return null;
    ACCENT_VARS.forEach((v) => root.style.removeProperty(v));  // read the theme's own surfaces, not the last accent's
    const ground = token("--ground"), surfaces = ["--ground", "--panel", "--field", "--raise"].map(token).filter(Boolean), ink = token("--ink");
    // The fill of primary buttons: first made to stand out from the surfaces it sits on (3:1, WCAG's bar for a control),
    // then white words on it when they pass, else the theme's darkest ink, else darkened until white passes.
    let fill = reach(c, light ? BLACK : WHITE, ["--panel", "--field"].map(token).filter(Boolean), 3), on = WHITE;
    if (contrast(fill, WHITE) < 4.5) {
      const deep = light ? token("--ink") : parse("#0b1020");  // dark words: the theme's own ink by day, the night's ground by night
      if (contrast(fill, deep) >= 4.5) on = deep; else fill = reach(fill, BLACK, [WHITE], 4.5);
    }
    // The wash behind a selected tile or your own chat bubble: a little of the accent in the ground.
    const wash = mix(ground, c, light ? 0.12 : 0.27);
    const washed = contrast(ink, wash) >= 7 ? wash : mix(ground, c, light ? 0.06 : 0.15);
    // Links, focus rings and the bar beside what is selected: AA on every surface and on the wash.
    const inkOf = reach(c, light ? BLACK : WHITE, [...surfaces, washed], 4.5);
    return { "--accent": hex(fill), "--on-accent": hex(on), "--accent-ink": hex(inkOf), "--accent-wash": hex(washed), "--accent-sel": hex(mix(ground, c, light ? 0.24 : 0.45)) };
  };

  // Every @media rule that asks about reduced motion, kept with its own text so "system" can put it back.
  const motionRules = [];
  const findMotion = (rules) => {
    for (const rule of rules) {
      if (rule.media && /prefers-reduced-motion/.test(rule.media.mediaText) && !motionRules.some((m) => m.rule === rule)) motionRules.push({ rule, text: rule.media.mediaText });
      if (rule.cssRules) findMotion(rule.cssRules);
    }
  };
  const setMotion = (mode) => {
    for (const sheet of document.styleSheets) { try { findMotion(sheet.cssRules); } catch (e) { /* not ours to read */ } }
    const yes = "(min-width: 0px)", no = "(max-width: -1px)";
    for (const { rule, text } of motionRules) {
      const want = mode === "system" ? text : text
        .replace(/\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)|\(\s*prefers-reduced-motion\s*\)/g, mode === "on" ? yes : no)
        .replace(/\(\s*prefers-reduced-motion\s*:\s*no-preference\s*\)/g, mode === "on" ? no : yes);
      if (rule.media.mediaText !== want) rule.media.mediaText = want;
    }
  };

  const apply = (prefs = {}) => {
    last = { ...prefs };
    const choice = ["light", "dark", "system"].includes(prefs.theme) ? prefs.theme : "dark";
    const theme = choice === "system" ? (dark.matches ? "dark" : "light") : choice;
    if (theme === "light") root.dataset.theme = "light"; else delete root.dataset.theme;
    root.dataset.density = prefs.density === "compact" ? "compact" : "comfortable";
    const motion = ["on", "off"].includes(prefs.reduce_motion) ? prefs.reduce_motion : "system";
    const calm = motion === "on" || (motion === "system" && still.matches);
    root.dataset.motion = calm ? "reduce" : "full";
    root.dataset.motionSet = motion;  // "system" is read from the media query each time, so it never lags a change
    setMotion(motion);
    const accent = prefs.accent ? accentFor(prefs.accent, theme === "light") : null;
    if (accent) { Object.entries(accent).forEach(([k, v]) => root.style.setProperty(k, v)); root.dataset.accent = ""; }
    else { ACCENT_VARS.forEach((v) => root.style.removeProperty(v)); delete root.dataset.accent; }
    // The phone's browser chrome takes the colour of the ground, and its status bar words the theme's ink.
    const ground = getComputedStyle(root).getPropertyValue("--ground").trim();
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta && ground) meta.content = ground;
    const bar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
    if (bar) bar.content = theme === "light" ? "default" : "black-translucent";
    try { localStorage.setItem(KEY, JSON.stringify(last)); } catch (e) { /* private mode: the next load starts dark */ }
    return { theme, choice, motion, still: calm, accent };
  };
  const cached = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const listeners = [];
  const follow = () => { apply(last); listeners.forEach((f) => f()); };
  dark.addEventListener("change", () => { if (last.theme === "system") follow(); });
  still.addEventListener("change", () => { if (!["on", "off"].includes(last.reduce_motion)) follow(); });
  window.hubAppearance = { apply, cached, contrast: (a, b) => contrast(parse(a), parse(b)), parse, onSystem: (f) => listeners.push(f) };
  apply(cached());
})();
