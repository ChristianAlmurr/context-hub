// The hub's one way to show what a session or a project is doing: a pixel orb, the hub's own variation of Thinking
// Orbs by Yogesh (MIT; the original is kept in ui/vendor/thinking-orbs.js with its licence). It is the same dot sphere
// (a Fibonacci spiral of dots, turned and tipped toward you, faded toward its back) seen through the hub's 2px pixel
// grid: its dots are square pixels that snap to that grid, its depth is four steps of one colour, and it moves in
// steps, ten a second, the way the projects' pixel marks would if they moved. app.js is a classic script, so this
// module hands it `window.hubOrb` once loaded (the name stays, so every call site does).
//   hubOrb(state, { size, label, still }) -> <svg class="orb orb-<state> look-<look>">
// `state` is a hub state (working, needs, finished, shell, ended, closing, closed, offline, no-claude, error), asks (a
// done turn that asks you something, unread), what a working Claude is doing (reasoning, searching, using, compacting,
// retrying, background, waiting, idle), or dreaming.
// Colour comes from CSS `color` (app.css, .orb-<state>), so every theme works unchanged.
//
// Every orb whose state is live moves, all the time, each state with its own motion and its own colour (app.css), so a
// glance tells working from thinking from a tool from a question: working turns, thinking wanders, searching sweeps, a
// tool types, compacting breathes, retrying winds back, needs you runs a light round its rim, closing lowers a lid.
// What is finished, idle or gone holds still. Under reduced motion each moving state holds one frame that still tells
// it apart. One timer draws them all, ten frames a second, only orbs on screen, and nothing in a hidden tab.
const TAU = Math.PI * 2, GOLDEN = Math.PI * (3 - Math.sqrt(5)), TILT = (20 * Math.PI) / 180;
const STEP = 100;  // ms between frames: stepped, like pixel art, and cheap
const ease = (x) => (1 - Math.cos(Math.PI * Math.min(1, Math.max(0, x)))) / 2;
const hash = (n) => { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); };

const WORDS = { working: "Working", searching: "Searching", using: "Using a tool", background: "Working in the background", reasoning: "Thinking",
  compacting: "Compacting", closing: "Closing", needs: "Needs you", waiting: "Needs you", finished: "Done", asks: "Done, asks you", idle: "Idle", shell: "Terminal",
  "no-claude": "Claude isn't running", ended: "Ended", closed: "Closed", offline: "Not connected", error: "Stopped with an error", retrying: "Retrying", dreaming: "Dreaming" };

// A frame is one level per grid cell: 0 empty, 1 full, 2, 3 and 4 fainter (app.css .orb .l1 to .l4).
// Brightness 0..1 becomes a level; anything under ~8% is left out, so the back of the sphere fades rather than hazes.
const level = (a) => (a >= 0.8 ? 1 : a >= 0.5 ? 2 : a >= 0.25 ? 3 : a >= 0.08 ? 4 : 0);

// ── The sphere ──
// Dots on a unit sphere, as the library lays them, about two fifths of the face lit at any size.
const spheres = new Map();
function sphere(n, dens = 1) {
  const key = `${n}:${dens}`;
  if (!spheres.has(key)) {
    const R = n * 0.42, count = Math.max(10, Math.round(0.85 * Math.PI * R * R * dens));
    spheres.set(key, Array.from({ length: count }, (_, i) => {
      const y = 1 - (2 * (i + 0.5)) / count, r = Math.sqrt(1 - y * y), th = i * GOLDEN;
      return [r * Math.cos(th), y, r * Math.sin(th)];
    }));
  }
  return spheres.get(key);
}
// Each dot turned by `yaw`, tipped toward you, then snapped to its grid cell. `fn` gets the cell, the view-space point and its depth.
function turn(n, pts, yaw, scale, fn) {
  const c = n / 2, R = n * 0.42 * scale, sy = Math.sin(yaw), cy = Math.cos(yaw), st = Math.sin(TILT), ct = Math.cos(TILT);
  for (const [x, y, z] of pts) {
    const z1 = -x * sy + z * cy, vx = x * cy + z * sy, vy = y * ct - z1 * st, vz = y * st + z1 * ct;
    const col = Math.floor(c + vx * R), row = Math.floor(c - vy * R);
    if (col >= 0 && row >= 0 && col < n && row < n) fn(row * n + col, vx, vy, vz, (vz + 1) / 2);
  }
}
// The brightest dot wins its cell.
const put = (f, k, a) => { const l = level(a); if (l && (!f[k] || l < f[k])) f[k] = l; };
// Depth: full at the front, gone just behind the rim.
const depth = (d) => Math.min(1, Math.max(0, (d - 0.22) / 0.6));
// Cells by their place on the disc: distance from the centre (in radii) and angle (0 right, counter-clockwise).
function disc(n, fn) {
  const c = n / 2, R = n * 0.42;
  for (let row = 0; row < n; row++) for (let col = 0; col < n; col++) {
    const dx = (col + 0.5 - c) / R, dy = (c - row - 0.5) / R;
    fn(row * n + col, Math.hypot(dx, dy), Math.atan2(dy, dx), col, row);
  }
}
// The disc's rim, one cell wide, all the way round.
const onRim = (n, r) => r <= 1.06 && r > 1.06 - 1.15 / (n * 0.42);
const globe = (f, n, yaw, k = 1, dens = 1, scale = 1) => turn(n, sphere(n, dens), yaw, scale, (cell, vx, vy, vz, d) => put(f, cell, k * depth(d)));
const angleOff = (a, b) => Math.atan2(Math.sin(a - b), Math.cos(a - b));

// ── Each state's look: draw(frame, n, t). `still` is the moment a moving look holds under reduced motion. ──
const LOOKS = {
  // Working: the globe turns, a lap every four seconds. Nothing else.
  working: { moves: true, still: 600, draw: (f, n, t) => globe(f, n, (t / 4000) * TAU) },
  // In the background (its turn is over, its agents work on): half the dots, at half strength, turning slower.
  background: { moves: true, still: 900, draw: (f, n, t) => globe(f, n, (t / 7000) * TAU, 0.6, 0.5) },
  // Thinking: the globe dims, and a short trail of light wanders over its face, a step every 200ms.
  reasoning: { moves: true, still: 5200, draw: (f, n, t) => {
    const yaw = (t / 9000) * TAU, at = (u) => [0.55 * Math.sin(u / 900), 0.5 * Math.sin(u / 610 + 1.3)];
    globe(f, n, yaw, 0.6);
    const step = Math.floor(t / 200) * 200;
    [0, 1, 2].forEach((back) => {
      const [hx, hy] = at(step - back * 200);
      let best = -1, near = Infinity;
      turn(n, sphere(n), yaw, 1, (cell, vx, vy, vz) => { const e = (vx - hx) ** 2 + (vy - hy) ** 2; if (vz > 0 && e < near) { near = e; best = cell; } });
      if (best >= 0 && (!f[best] || f[best] > back + 1)) f[best] = back + 1;
    });
  } },
  // Searching: the globe dims, and a beam crosses its face left to right, then rests a moment.
  searching: { moves: true, still: 900, draw: (f, n, t) => {
    const u = (t % 1600) / 1600, beam = -1.3 + 2.6 * ease(u / 0.7), on = u < 0.7;
    turn(n, sphere(n), (t / 9000) * TAU, 1, (cell, vx, vy, vz, d) => put(f, cell, Math.max(0.6 * depth(d), on && vz > -0.2 ? Math.exp(-(((vx - beam) / 0.22) ** 2)) : 0)));
  } },
  // Using a tool: the globe dims and turns slowly, and lines of pixels are typed across it, held, then cleared.
  using: { moves: true, still: 2300, draw: (f, n, t) => {
    globe(f, n, 0.6 + (t / 8000) * TAU, 0.55);
    const lines = rows(n), total = lines.reduce((s, l) => s + l.length, 0), per = 70;
    let typed = Math.floor((t % (total * per + 700)) / per);
    for (const line of lines) for (const cell of line) if (typed-- > 0) f[cell] = 1;
  } },
  // Compacting: the globe draws in by a quarter, holds, and lets go.
  compacting: { moves: true, still: 1900, draw: (f, n, t) => {
    const u = t % 2200, squeeze = u < 800 ? ease(u / 800) : u < 1200 ? 1 : u < 1900 ? 1 - ease((u - 1200) / 700) : 0;
    turn(n, sphere(n), (t / 5000) * TAU, 1 - 0.28 * squeeze, (cell, vx, vy, vz, d) => put(f, cell, depth(d) * (1 + 0.4 * squeeze)));
  } },
  // Closing (writing its handoff): a lid comes down over the turning globe and lifts again.
  closing: { moves: true, still: 900, draw: (f, n, t) => {
    const u = t % 3000, lid = 1.15 - 2.3 * (u < 1500 ? ease(u / 1500) : u < 2000 ? 1 : 1 - ease((u - 2000) / 1000));
    turn(n, sphere(n), (t / 6000) * TAU, 1, (cell, vx, vy, vz, d) => put(f, cell, vy > lid ? 0.4 * depth(d) : depth(d)));
  } },
  // Needs you: the fullest orb, with a solid rim and one bright pixel running round it, a lap every 1.6 seconds.
  needs: { moves: true, still: 700, draw: (f, n, t) => {
    globe(f, n, 0.4, 0.75, 1.5);
    const head = Math.PI / 2 - (t / 1600) * TAU;
    disc(n, (cell, r, ang) => { if (onRim(n, r)) f[cell] = Math.abs(angleOff(ang, head)) < 0.45 ? 1 : 2; });
  } },
  // Done, and it asks you something: the full orb of needs you, at rest, its rim whole. Close to needs, never quieter.
  asks: { draw: (f, n) => { globe(f, n, 0.4, 0.75, 1.5); disc(n, (cell, r) => { if (onRim(n, r)) f[cell] = 1; }); } },
  // Done: the globe at rest, lit from above. Read, its lit cap goes out (app.css), and it is the quietest mark there is.
  finished: { draw: (f, n) => {
    globe(f, n, 0.4, 0.55);
    disc(n, (cell, r, ang) => { if (r <= 1 && Math.sin(ang) * r > 0.3) f[cell] = 1; });
  } },
  // Idle: the globe at rest, evenly shaded.
  idle: { draw: (f, n) => globe(f, n, 0.4, 0.8) },
  // A terminal: a flat chequer of pixels, a screen rather than a sphere.
  shell: { draw: (f, n) => disc(n, (cell, r, ang, col, row) => { if (r <= 1.05 && (col + row) % 2 === 0) f[cell] = 2; }) },
  // Claude isn't running in the terminal: the chequer with its middle gone.
  "no-claude": { draw: (f, n) => disc(n, (cell, r, ang, col, row) => { if (r <= 1.05 && r > 0.5 && (col + row) % 2 === 0) f[cell] = 2; }) },
  // Ended: only the rim is left.
  ended: { draw: (f, n) => disc(n, (cell, r) => { if (onRim(n, r)) f[cell] = 2; }) },
  // Closed: the rim, with what settled at the bottom of it.
  closed: { draw: (f, n) => disc(n, (cell, r, ang) => { if (onRim(n, r)) f[cell] = 2; else if (r < 1 && Math.sin(ang) * r < -0.2) f[cell] = 3; }) },
  // Not connected: a broken rim.
  offline: { draw: (f, n) => disc(n, (cell, r, ang) => { if (onRim(n, r) && Math.floor(((ang + TAU) % TAU) / (TAU / 8)) % 2 === 0) f[cell] = 2; }) },
  // Stopped with an error: the globe has lost a piece of its upper right, which lies fallen at its foot.
  error: { draw: (f, n) => broken(f, n, 0.4, 0) },
  // Retrying: the broken globe turns, brakes and winds back a little, again and again, and its fallen piece climbs back.
  retrying: { moves: true, still: 1200, draw: (f, n, t) => broken(f, n, rewind(t), ease((t % 1600) / 1600)) },
  // Dreaming: a crescent moon, and the globe drifting slowly through it, its dots catching the light as they pass.
  dreaming: { moves: true, still: 0, draw: (f, n, t) => {
    const moon = new Set(), art = MOON[n];
    if (art) art.forEach((line, row) => [...line].forEach((ch, col) => { if (ch === "x") { moon.add(row * n + col); f[row * n + col] = 2; } }));
    else disc(n, (cell, r, ang) => { const x = r * Math.cos(ang) + 0.45, y = r * Math.sin(ang) - 0.06; if (r <= 1.02 && Math.hypot(x, y) > 0.84) { moon.add(cell); f[cell] = 2; } });
    turn(n, sphere(n), (t / 9000) * TAU, 1, (cell, vx, vy, vz, d) => { if (moon.has(cell) && depth(d) > 0.6) f[cell] = 1; });
  } },
};
LOOKS.waiting = LOOKS.needs;
// The moon by hand at the two smallest sizes, where a computed crescent thins to a bracket.
const MOON = {
  7: ["..xxx..", "....xx.", ".....xx", ".....xx", ".....xx", "....xx.", "..xxx.."],
  8: ["..xxxx..", ".....xx.", "......xx", "......xx", "......xx", "......xx", ".....xx.", "..xxxx.."],
};

// Using's lines, in grid cells: every other row through the middle of the disc, words broken by gaps.
const rowCache = new Map();
function rows(n) {
  if (!rowCache.has(n)) {
    const out = [], c = n / 2, R = n * 0.42, gap = n < 12 ? 2 : 3;
    for (let row = Math.ceil(c - R * 0.55); row < c + R * 0.55; row += gap) {
      const line = [], half = Math.sqrt(Math.max(0, R * R - (row + 0.5 - c) ** 2)) - 0.9;
      for (let col = Math.ceil(c - half); col < c + half; col++) if (n < 12 || hash(row * 31 + col) > 0.22) line.push(row * n + col);
      if (line.length) out.push(line);
    }
    rowCache.set(n, out);
  }
  return rowCache.get(n);
}
// The broken globe: a wedge of its upper right missing; `back` 0 leaves the piece at the foot, 1 lifts it partway home.
function broken(f, n, yaw, back) {
  turn(n, sphere(n), yaw, 1, (cell, vx, vy, vz, d) => {
    const ang = Math.atan2(vy, vx);
    if (!(ang > 0.15 && ang < 1.25 && Math.hypot(vx, vy) > 0.35)) put(f, cell, depth(d));
  });
  const lift = Math.round(back * Math.max(1, Math.floor(n * 0.2)));
  [[n - 2, n - 1], [n - 1, n - 2], [n - 1, n - 1]].forEach(([col, row]) => { f[(row - lift) * n + col] = 1; });
}
// Retrying's spin: turns for 1.2 seconds, then winds back two fifths of the way in 0.4, and again (the library's rewind).
function rewind(t) {
  const P = 1600, w = TAU / 4000, k = Math.floor(t / P), u = t - k * P, run = 1200 * w, back = 0.4 * run;
  const a = u < 1200 ? u * w : run - back * ease((u - 1200) / 400);
  return 0.4 + k * (run - back) + a;
}

// ── Frames, shared: every orb of one look and size draws the same frame, worked out once per step. ──
const frames = new Map();
function frame(state, n, t) {
  const key = `${state}|${n}`, at = Math.floor(t / STEP);
  let got = frames.get(key);
  if (got && got.at === at) return got.paths;
  const f = new Uint8Array(n * n);
  LOOKS[state].draw(f, n, at * STEP);
  const d = ["", "", "", "", ""];
  f.forEach((l, i) => { if (l) d[l] += `M${i % n} ${Math.floor(i / n)}h1v1h-1z`; });
  frames.set(key, (got = { at, paths: d }));
  return d;
}

// ── Motion: reduced as the person chose it (theme.js sets data-motion-set), else as the system asks. ──
const calm = matchMedia("(prefers-reduced-motion: reduce)");
const still = () => { const set = document.documentElement.dataset.motionSet; return set === "on" ? true : set === "off" ? false : calm.matches; };
let wasStill = still();

const SVG = "http://www.w3.org/2000/svg";
const moving = new Set();  // orbs whose look moves: { svg, state, n, paths, seen }
const paint = (orb, t) => {
  const d = frame(orb.state, orb.n, t);
  for (let l = 1; l <= 4; l++) if (orb.paths[l].getAttribute("d") !== d[l]) orb.paths[l].setAttribute("d", d[l]);
};
const stillAt = (orb) => LOOKS[orb.state].still || 0;
// One timer for every orb, running only while one that moves is on screen in a tab you can see. Each step every orb on
// screen gets its state's frame, worked out once for all orbs of that state and size.
let timer = 0;
const tick = () => {
  timer = 0;
  if (document.hidden || wasStill) return;
  const now = performance.now();
  let any = false;
  for (const orb of moving) if (orb.seen && orb.svg.isConnected) { paint(orb, now); any = true; }
  if (any) timer = setTimeout(tick, STEP - (now % STEP));
};
const wake = () => { if (!timer && !document.hidden && !wasStill) timer = setTimeout(tick, 0); };
const watch = "IntersectionObserver" in window
  ? new IntersectionObserver((seen) => { seen.forEach((e) => { const orb = e.target.__orb; if (orb) orb.seen = e.isIntersecting; }); wake(); })
  : null;
document.addEventListener("visibilitychange", wake);
// A change of the motion setting or the system's: every moving orb goes to its still frame, or moves on from it.
const motionChanged = () => {
  const now = still();
  if (now === wasStill) return;
  wasStill = now;
  for (const orb of moving) paint(orb, now ? stillAt(orb) : performance.now());
  wake();
};
calm.addEventListener("change", motionChanged);
new MutationObserver(motionChanged).observe(document.documentElement, { attributes: true, attributeFilter: ["data-motion-set"] });
// Orbs a redraw took off the page are let go, so the observer holds only what is on it.
setInterval(() => { for (const orb of moving) if (!orb.svg.isConnected) { if (watch) watch.unobserve(orb.svg); moving.delete(orb); } }, 5000);

// `still: true` holds the orb on its reduced-motion frame whatever the setting (the states sheet's last column).
window.hubOrb = (state, { size = 14, label, still: fixed = false } = {}) => {
  const look = LOOKS[state] ? state : "idle";
  const n = Math.max(6, Math.round(size / 2));  // one cell of the art is 2px, the projects' marks' grain, at every size
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${n} ${n}`);
  svg.setAttribute("width", n * 2);
  svg.setAttribute("height", n * 2);
  svg.setAttribute("shape-rendering", "crispEdges");
  svg.classList.add("orb", `orb-${state}`, `look-${look}`);
  svg.dataset.orb = state;
  if (label === false) svg.setAttribute("aria-hidden", "true");
  else { svg.setAttribute("role", "img"); svg.setAttribute("aria-label", label || WORDS[state] || state); }
  const paths = [null];
  for (let l = 1; l <= 4; l++) { const p = document.createElementNS(SVG, "path"); p.setAttribute("class", `l${l}`); svg.append(p); paths.push(p); }
  const orb = { svg, state: look, n, paths, seen: !watch };
  if (LOOKS[look].moves && fixed) paint(orb, stillAt(orb));
  else if (LOOKS[look].moves) {
    svg.__orb = orb;
    moving.add(orb);
    if (watch) watch.observe(svg);
    paint(orb, wasStill ? stillAt(orb) : performance.now());
    wake();
  } else paint(orb, 0);
  return svg;
};
window.dispatchEvent(new Event("hub-orbs-ready"));
