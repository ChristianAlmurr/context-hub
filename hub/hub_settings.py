"""Hub-wide settings: what the person chose for the whole hub, kept in config.json under "settings", read live.

The Settings page reads and writes them through GET and PUT /api/settings. Each one is named in SCHEMA, with its type,
its choices or range, its default and the words the page shows, so the page is built from the schema and a value that
doesn't fit it is never written. A write changes the "settings" key and nothing else: every other key of config.json
stays as it was, in its order and indentation, and the file is replaced whole, at mode 600, so it is never seen half
written. Access (login, origin, port and the key) is never read or written here: it is install.sh's.

Reading is live: the file is read again whenever it changes, so a change made on the page, or by hand, applies at
once. The rest of config.json still applies at start (hub_base.py), as it always has.

One setting is kept elsewhere: whether the Dream Catcher acts on its verdicts lives in the catcher's own file
(hub_catcher.py), which the switch on its page writes. The Settings page reads and writes that same file, so there is
one place it is kept, not two.

Also here: what is wrong with config.json (diagnostics), how the hub's parts are (health), what changed since the last
version the person saw, and `server.py --check`, which prints the first two for the terminal.
"""
import difflib, json, os, re, shlex, shutil, subprocess, threading, time
from pathlib import Path

from hub_base import APP, CONFIG, ENV, INSTALLED_CONFIG, KIT, LAUNCHD_JOBS, PORT, STATE, Malformed, Refused, pasteable, whole

KEY = "settings"
ACCESS = ("login", "origin", "port", "key")  # install.sh's, never this module's
NOTES = STATE / "settings-notes.json"  # what the page has shown once: the welcome card, the last version seen
LAUNCHD_LABEL = "ai.agent-hub"
_lock = threading.RLock()
_cache = {"stamp": None, "raw": None, "error": ""}

# The modes, efforts and built-in models a new session can start with. They match hub_data.py's MODES, EFFORTS and
# MODELS, and the words the composer shows in ui/app.js.
MODE_CHOICES = [["plan", "Plan"], ["manual", "Ask first"], ["acceptEdits", "Accept edits"], ["auto", "Auto"], ["bypassPermissions", "Skip permissions"]]
EFFORT_CHOICES = [["low", "Low"], ["medium", "Medium"], ["high", "High"], ["xhigh", "Extra high"], ["max", "Max"]]
BUILT_IN_MODELS = ["opus", "fable", "sonnet", "haiku"]
NOTIFY = [["system", "System"], ["banner", "In the hub"], ["off", "Off"]]
SOUNDS = [["off", "None"], ["chime", "Chime"], ["knock", "Knock"], ["bell", "Bell"]]
# The colours a project can be given: a curated set, each with a dark and a light tone in ui/app.css (--pc-<id>).
PROJECT_COLOURS = ["blue", "jade", "pink", "gold", "sky", "violet", "orange", "lime", "slate"]

SECTIONS = [
    {"id": "appearance", "title": "Appearance"},
    {"id": "notifications", "title": "Notifications & sound"},
    {"id": "sessions", "title": "New sessions"},
    {"id": "sidebar", "title": "Sidebar & navigation"},
    {"id": "catcher", "title": "Dream Catcher"},
    {"id": "features", "title": "Features"},
]


def _s(name, section, label, kind, default, **more):
    return {"name": name, "section": section, "label": label, "kind": kind, "default": default, **more}


# Every setting the hub knows. `kind` says which control the page builds and how a value is checked:
# choice (one of `choices`), switch (true or false), number (from `min` to `max`, whole when `step` is 1), colour
# (a CSS colour or ""), key (a key with modifiers), projects (project names), models (the model list), model (one of
# the models, or "").
SCHEMA = [
    _s("theme", "appearance", "Theme", "choice", "dark", choices=[["dark", "Dark"], ["light", "Light"], ["system", "Match system"]]),
    _s("accent", "appearance", "Accent", "colour", "", help="Buttons, selection and focus. Working and needs-you keep their own colours."),
    _s("term_font_size", "appearance", "Terminal text size", "number", 13, min=9, max=24, step=1, unit="px"),
    _s("density", "appearance", "Density", "choice", "comfortable", choices=[["comfortable", "Comfortable"], ["compact", "Compact"]]),
    _s("reduce_motion", "appearance", "Reduce motion", "choice", "system", choices=[["system", "Match system"], ["on", "On"], ["off", "Off"]]),
    _s("term_renderer", "appearance", "Terminal drawing", "choice", "auto", choices=[["auto", "Graphics card"], ["dom", "Plain"]],
       help="Plain is slower, but try it if a terminal ever draws wrongly."),
    _s("term_park_after", "appearance", "Let go of terminals in a hidden tab after", "number", 120, min=30, max=3600, step=30, unit="s",
       help="They reconnect as soon as you come back."),

    _s("notify_needs", "notifications", "A session needs you", "choice", "system", choices=NOTIFY),
    _s("notify_done", "notifications", "A turn finishes", "choice", "off", choices=NOTIFY),
    _s("notify_closed", "notifications", "A session closes", "choice", "system", choices=NOTIFY),
    _s("notify_catcher", "notifications", "The Dream Catcher finishes", "choice", "system", choices=NOTIFY),
    _s("sound_needs", "notifications", "Sound when a session needs you", "choice", "off", choices=SOUNDS, sound=True),
    _s("sound_done", "notifications", "Sound when a turn finishes", "choice", "off", choices=SOUNDS, sound=True),
    _s("sound_volume", "notifications", "Volume", "number", 0.6, min=0, max=1, step=0.05, unit="%"),
    _s("muted_projects", "notifications", "Quiet projects", "projects", [], help="No notification or sound comes from these."),

    _s("default_mode", "sessions", "Mode", "choice", "", choices=[["", "Last used"], *MODE_CHOICES]),
    _s("default_model", "sessions", "Model", "model", "", help="One of the models below, or the last one used."),
    _s("default_effort", "sessions", "Effort", "choice", "", choices=[["", "Claude's default"], *EFFORT_CHOICES]),
    _s("default_worktree", "sessions", "Give each session its own worktree", "switch", False),
    _s("models", "sessions", "Models", "models", [], help="What the model picker offers. Empty means the built-in list."),

    _s("sidebar_order", "sidebar", "Order sessions", "choice", "project", choices=[["project", "By project"], ["attention", "What needs you first"]]),
    _s("asks_as_needs", "sidebar", "A turn that ends with a question needs you", "switch", False,
       help="Off, it shows as Done · asks you."),
    _s("prefix_key", "sidebar", "Leave the terminal", "key", "Control+`", help="The key that takes you out of a terminal and back."),
    _s("max_panes", "sidebar", "Panes in a split", "number", 4, min=2, max=6, step=1),

    # Features: each newer part of the hub can be turned off here, and the hub then works as it did before it.
    # One block per feature group, so each can grow without touching the others.
    # ── tabs ──
    _s("feature_tabs", "features", "Session tabs", "switch", True, help="Open sessions as tabs along the top, like a browser."),
    _s("tabs_hide_single", "features", "Hide the tab bar with one tab", "switch", True, help="It comes back when you open a second session."),
    _s("feature_side_panel", "features", "Session side panel", "switch", True, help="Overview, changes, files, browser and artifacts beside a session."),
    # ── browser ──
    _s("feature_browser", "features", "Built-in browser", "switch", True, help="Open the pages your sessions serve, on desk and phone."),
    _s("feature_preview", "features", "Device preview", "switch", True, help="See a page as it looks on a phone, a tablet and a desk, side by side."),
    # ── artifacts ──
    _s("feature_artifacts", "features", "Artifacts", "switch", True, help="Everything a session made, opened right here: pages, documents, pictures and more."),
    # ── terminal ──
    # ── sidebar ──
    _s("feature_project_order", "features", "Reorder projects", "switch", True, help="Drag a project in the sidebar, or move it with ⌥↑ and ⌥↓. Every device keeps the order."),
    _s("project_order", "sidebar", "Project order", "order", [], hidden=True),
    _s("feature_hide_projects", "features", "Hide projects", "switch", True, help="Take a project out of the sidebar. Go to still finds it, and it still tells you when it needs you."),
    _s("hidden_projects", "sidebar", "Hidden projects", "projects", [], help="Out of the sidebar. Go to still finds them, and they still tell you when they need you."),
    _s("sidebar_side", "sidebar", "Sidebar", "choice", "left", choices=[["left", "On the left"], ["right", "On the right"]]),
    _s("feature_project_colours", "features", "Project colours", "switch", True, help="Give a project a colour from its ⋯ menu. It marks the project and its sessions everywhere."),
    _s("project_colours", "sidebar", "Project colours", "colour_map", {}, hidden=True),
    _s("feature_jump_numbers", "features", "Jump numbers", "switch", True, help="Hold ⌥ to see each pane's number. Go to numbers its first nine sessions for ⌥1–9."),
    _s("feature_notice_tools", "features", "Notice tools", "switch", True, help="Clear all, the last 50 notices kept on this device, swipe away on a phone, and toasts that wait while you point at them."),
    _s("notice_time", "notifications", "Notices stay", "choice", "auto", choices=[["auto", "As they always did"], ["5", "5 s"], ["10", "10 s"], ["30", "30 s"], ["stay", "Until dismissed"]],
       help="How long a notice or a passing message stays on screen, with Notice tools on. Pointing at one holds it."),
    _s("worktree_path", "sessions", "Where worktrees go", "worktree", "",
       help="Empty keeps them in the repo's .claude/worktrees. Use {repo}, {project}, {name} and {branch}; {parent} is the folder the repo is in."),
    _s("feature_title_sync", "features", "Names in step with Claude", "switch", True, help="A rename reaches Claude once its input is empty, and a /rename in Claude reaches the hub."),
    _s("feature_subagents", "features", "Subagents in the sidebar", "switch", True, help="A session's subagents, nested under its row with their state."),
    # ── end of features ──

    _s("dream_catcher_auto", "catcher", "Act on its verdicts", "switch", False, kept="catcher",
       help="Off, it only recommends. On, its approvals and rejections are carried out when a run ends."),
]
BY_NAME = {item["name"]: item for item in SCHEMA}

# Every key of config.json the hub reads, with what it must be. "settings" is this module's.
TOP = {
    "port": ("a whole number from 1 to 65535", lambda v: whole(v) and 1 <= v <= 65535),
    "projects": ("a folder", lambda v: isinstance(v, str) and v.strip() != ""),
    "kit": ("a folder", lambda v: isinstance(v, str) and v.strip() != ""),
    "path": ("a list of folders", lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v)),
    "no_vcs": ("a list of folders", lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v)),
    "private_folders": ("a list of folder names", lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v)),
    "login": ("a Tailscale login", lambda v: isinstance(v, str)),
    "origin": ("the hub's address, such as https://host:8443", lambda v: isinstance(v, str) and re.match(r"^https?://[^/\s]+$", v) is not None),
    "key": ("a key of 32 characters or more", lambda v: isinstance(v, str) and len(v) >= 32),
    "updates": ("true or false", lambda v: isinstance(v, bool)),
    "dream_catcher_store": ("a project name", lambda v: isinstance(v, str) and re.match(r"^[a-z0-9][a-z0-9-]{0,40}$", v) is not None),
    "dream_catcher_stores": ("a list of project names", lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v)),
    "dream_catcher_auto": ("true or false", lambda v: isinstance(v, bool)),
    "dream_catcher_model": ("one of " + ", ".join(BUILT_IN_MODELS), lambda v: v in BUILT_IN_MODELS),
    KEY: ("an object of settings", lambda v: isinstance(v, dict)),
}

COLOUR = re.compile(r"^(#[0-9a-fA-F]{3,4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|(rgb|rgba|hsl|hsla|oklch|oklab)\([0-9.,%\s/+-]{1,48}\)|[a-zA-Z]{3,24})$")
KEYNAME = re.compile(r"^(?:(?:Control|Alt|Shift|Meta)\+){0,3}(?:[A-Za-z0-9]|F[1-9]|F1[0-2]|[`\-=\[\];',./\\]|Space|Tab)$")
PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\]]{0,63}$")
COMMIT = re.compile(r"^[0-9a-f]{4,40}$")


# ── reading ──
def _read():
    """config.json as it is now, read again only when it changed: (the object or None, why it can't be used)."""
    path = Path(os.path.realpath(CONFIG))
    try:
        seen = os.stat(path)
        stamp = (seen.st_mtime_ns, seen.st_size, seen.st_ino)
    except OSError as error:
        return None, f"it can't be read ({error.strerror})"
    with _lock:
        if _cache["stamp"] == stamp:
            return _cache["raw"], _cache["error"]
        try:
            raw, why = json.loads(path.read_text()), ""
        except OSError as error:
            raw, why = None, f"it can't be read ({error.strerror})"
        except ValueError as error:
            raw, why = None, f"it isn't valid JSON: {error.msg} on line {error.lineno}, column {error.colno}"
        if raw is not None and not isinstance(raw, dict):
            raw, why = None, "it isn't a JSON object"
        _cache.update(stamp=stamp, raw=raw, error=why)
        return raw, why


def stored() -> dict:
    """The "settings" object as it is in the file, unchecked; {} when there is none or the file can't be used."""
    raw, _ = _read()
    found = (raw or {}).get(KEY)
    return dict(found) if isinstance(found, dict) else {}


def model_ids(models=None) -> list:
    """The ids a session may start with: the person's own list when there is one, and the built-in ones always, so a
    session started before the list changed can still be resumed."""
    listed = models if models is not None else value("models")
    return list(dict.fromkeys([*BUILT_IN_MODELS, *(m["id"] for m in listed)]))


def check(name: str, v, others=None):
    """The value as it is kept, or raise Malformed saying what it must be. `others` are the values it is written with."""
    item = BY_NAME[name]
    kind, label = item["kind"], item["label"]
    if kind == "choice":
        ids = [c[0] for c in item["choices"]]
        if v not in ids:
            raise Malformed(f"{label} must be one of {', '.join(repr(i) for i in ids)}.", name=name)
        return v
    if kind == "switch":
        if not isinstance(v, bool):
            raise Malformed(f"{label} is either on or off (true or false).", name=name)
        return v
    if kind == "number":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            raise Malformed(f"{label} must be a number.", name=name)
        if not item["min"] <= v <= item["max"]:
            raise Malformed(f"{label} must be from {item['min']} to {item['max']}.", name=name)
        if item["step"] == 1:
            if v != int(v):
                raise Malformed(f"{label} must be a whole number.", name=name)
            return int(v)
        return round(float(v), 4)
    if kind == "colour":
        if not isinstance(v, str) or (v and not COLOUR.match(v.strip())):
            raise Malformed("Use a colour such as #2f62f5, or leave it empty.", name=name)
        return v.strip()
    if kind == "key":
        if not isinstance(v, str) or not KEYNAME.match(v):
            raise Malformed("Use a key such as Control+` or Alt+j: Control, Alt, Shift or Meta, then one key.", name=name)
        if "+" not in v.rstrip("+") or v.split("+")[:-1] == ["Shift"]:
            raise Malformed("Hold Control, Alt or Meta with it, so the key still types in a terminal.", name=name)
        return v
    if kind == "projects":
        if not isinstance(v, list) or not all(isinstance(x, str) and PROJECT.match(x) for x in v) or len(v) > 500:
            raise Malformed(f"{label} must be a list of project names.", name=name)
        return sorted(set(v))
    if kind == "models":
        if not isinstance(v, list) or len(v) > 12:
            raise Malformed("The model list holds up to 12 models.", name=name)
        kept, ids = [], set()
        for m in v:
            if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not MODEL_ID.match(m["id"].strip()):
                raise Malformed("Each model needs an id Claude Code knows, such as opus or claude-sonnet-5-5.", name=name)
            mid = m["id"].strip()
            title = " ".join(str(m.get("name") or "").split())[:40] or mid
            say = " ".join(str(m.get("say") or "").split())[:80]
            if mid in ids:
                raise Malformed(f"{mid} is in the list twice.", name=name)
            ids.add(mid)
            kept.append({"id": mid, "name": title, "say": say})
        return kept
    # ── sidebar kinds: a project order, a colour per project, where worktrees go ──
    if kind == "order":
        if not isinstance(v, list) or not all(isinstance(x, str) and PROJECT.match(x) for x in v) or len(v) > 500:
            raise Malformed(f"{label} must be a list of project names.", name=name)
        return list(dict.fromkeys(v))
    if kind == "colour_map":
        if not isinstance(v, dict) or len(v) > 500 or not all(isinstance(k, str) and PROJECT.match(k) for k in v):
            raise Malformed(f"{label} must name projects.", name=name)
        if not all(c in PROJECT_COLOURS for c in v.values()):
            raise Malformed(f"Each colour must be one of {', '.join(PROJECT_COLOURS)}.", name=name)
        return {k: v[k] for k in sorted(v)}
    if kind == "worktree":
        import hub_worktrees
        if not isinstance(v, str):
            raise Malformed(f"{label} must be a folder.", name=name)
        return hub_worktrees.check_template(v)
    if kind == "model":
        listed = (others or {}).get("models")
        allowed = [""] + model_ids(listed if listed is not None else value("models"))
        if v not in allowed:
            raise Malformed(f"{label} must be one of the models in the list, or empty for the last one used.", name=name)
        return v
    raise Malformed(f"{label} can't be set.", name=name)


def _catcher_auto() -> bool:
    import hub_catcher  # imported here: the catcher imports the hub's data, which reads these settings
    return hub_catcher.auto()


def values() -> dict:
    """Every setting as it applies now: what the file holds when it fits the schema, else its default."""
    held, out = stored(), {}
    listed = {"models": _models_held(held)}
    for item in SCHEMA:
        name = item["name"]
        if item.get("kept") == "catcher":
            out[name] = _catcher_auto()
            continue
        out[name] = item["default"]
        if name in held:
            try:
                out[name] = check(name, held[name], listed)
            except Malformed:
                pass  # diagnostics() says so; the default applies meanwhile
    return out


def value(name: str):
    """One setting as it applies now. Cheap: the file is read only when it changed."""
    item = BY_NAME[name]
    if item.get("kept") == "catcher":
        return _catcher_auto()
    held = stored()
    if name in held:
        try:
            return check(name, held[name], held if name != "default_model" else {"models": _models_held(held)})
        except Malformed:
            pass
    return item["default"]


def _models_held(held):
    try:
        return check("models", held.get("models", []))
    except Malformed:
        return []


def schema() -> list:
    return [{k: v for k, v in item.items() if k != "kept"} for item in SCHEMA]


def defaults() -> dict:
    return {item["name"]: item["default"] for item in SCHEMA}


# ── writing ──
def _indent(text: str):
    """The indentation the file is written with, so a rewrite looks like the file did."""
    match = re.search(r"^\{\s*\n([ \t]+)\"", text)
    if not match:
        return None
    return match[1] if "\t" in match[1] else len(match[1])


def _replace(path: Path, text: str):
    spare = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(spare, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(spare, 0o600)
        os.replace(spare, path)
    except BaseException:
        spare.unlink(missing_ok=True)
        raise


def suggest(name: str) -> str:
    near = difflib.get_close_matches(name, [*BY_NAME, *ACCESS], n=1, cutoff=0.6)
    return f" Did you mean {near[0]}?" if near else ""


def write(body: dict) -> dict:
    """PUT /api/settings: set the named settings, each checked against the schema, and nothing else."""
    if not isinstance(body, dict) or not body:
        raise Malformed("Say which settings to change.")
    for name in body:
        if name in ACCESS:
            raise Refused(f"The {name} isn't changed here: it decides who can reach the hub. Run install.sh to change it.", name=name)
        if name not in BY_NAME:
            raise Malformed(f"There's no setting called {name}.{suggest(name)}", name=name)
    import hub_data
    hub_data.the_person("change the hub's settings")
    path = Path(os.path.realpath(CONFIG))
    with _lock:
        try:
            text = path.read_text()
            raw = json.loads(text)
        except OSError as error:
            raise Refused(f"{pasteable(path)} can't be read ({error.strerror}).")
        except ValueError as error:
            raise Refused(f"{pasteable(path)} isn't valid JSON (line {error.lineno}), so nothing was written. Fix it first: python3 hub/server.py --check says where.")
        if not isinstance(raw, dict):
            raise Refused(f"{pasteable(path)} isn't a JSON object, so nothing was written.")
        held = dict(raw.get(KEY)) if isinstance(raw.get(KEY), dict) else {}
        incoming = {k: v for k, v in body.items() if BY_NAME[k].get("kept") != "catcher"}
        after_models = check("models", incoming["models"]) if "models" in incoming else _models_held(held)
        checked = {name: check(name, v, {"models": after_models}) for name, v in incoming.items()}
        merged = {**held, **checked}
        if "models" in checked and merged.get("default_model") and merged["default_model"] not in model_ids(after_models):
            raise Malformed(f"The default model, {merged['default_model']}, isn't in the new list. Choose another default first.", name="models")
        for name in checked:  # a default is the same as no choice: the file keeps only what differs
            if checked[name] == BY_NAME[name]["default"]:
                merged.pop(name, None)
        if incoming:
            keys = list(raw)
            raw[KEY] = merged
            ascii_only = all(ord(c) < 128 for c in text)
            out = json.dumps(raw, indent=_indent(text), ensure_ascii=ascii_only) + ("\n" if text.endswith("\n") else "")
            again = json.loads(out)
            if any(again.get(k) != raw.get(k) for k in keys if k != KEY):  # never: but a write that would lose a key doesn't happen
                raise Refused("The settings couldn't be written without changing something else, so nothing was written.")
            _replace(path, out)
            _cache["stamp"] = None
    if "dream_catcher_auto" in body:
        import hub_catcher
        hub_catcher.set_auto({"auto": check("dream_catcher_auto", body["dream_catcher_auto"])})
    return page()


# ── what the page shows once ──
def notes() -> dict:
    try:
        found = json.loads(NOTES.read_text())
        return found if isinstance(found, dict) else {}
    except (OSError, ValueError):
        return {}


def _note(**changes):
    with _lock:
        now = {**notes(), **changes}
        NOTES.parent.mkdir(parents=True, exist_ok=True)
        spare = NOTES.with_suffix(".tmp")
        spare.write_text(json.dumps(now))
        os.replace(spare, NOTES)
    return now


def welcome() -> str:
    """The first-run card on Home: "open" from the first time the hub finds a config with no settings, until the person
    dismisses it ("done"); "" for a hub that had settings before there was a card."""
    held = notes().get("welcome")
    if held in ("open", "done"):
        return held
    raw, _ = _read()
    state = "open" if raw is not None and KEY not in raw else "done"
    _note(welcome=state)
    return state


def dismiss_welcome(body=None) -> dict:
    _note(welcome="done")
    return {"welcome": "done"}


# ── the whole answer ──
def access() -> dict:
    """Who can reach the hub and where, shown and never changed here. The key is never shown."""
    raw, _ = _read()
    raw = raw or {}
    return {"login": str(raw.get("login") or ""), "origin": str(raw.get("origin") or ""), "port": PORT,
            "way": "tailscale" if raw.get("login") else "key", "config": pasteable(Path(CONFIG))}


def page() -> dict:
    """GET /api/settings."""
    raw, why = _read()
    return {"values": values(), "schema": schema(), "sections": SECTIONS, "defaults": defaults(), "builtin_models": BUILT_IN_MODELS,
            "configured": raw is not None and KEY in raw, "welcome": welcome(), "access": access(), "problems": diagnostics()}


# ── diagnostics: what is wrong with config.json, each with a fix ──
def diagnostics() -> list:
    raw, why = _read()
    where = pasteable(Path(CONFIG))
    if raw is None:
        return [{"level": "error", "text": f"config.json can't be used: {why}. Every setting falls back to its default.",
                 "fix": f"Open {where} in an editor and fix it, then run python3 hub/server.py --check."}]
    out = []
    for key, v in raw.items():
        if key not in TOP:
            near = difflib.get_close_matches(key, list(TOP), n=1, cutoff=0.6) or difflib.get_close_matches(key, list(BY_NAME), n=1, cutoff=0.6)
            hint = f" Did you mean {near[0]}?" if near else ""
            inside = " It's a setting: it belongs inside \"settings\"." if key in BY_NAME else ""
            out.append({"level": "warn", "text": f"config.json has a key the hub doesn't know: {key}. It's ignored.{hint}{inside}",
                        "fix": f"Rename it or remove it in {where}."})
        elif not TOP[key][1](v):
            out.append({"level": "warn", "text": f"{key} in config.json should be {TOP[key][0]}, so the hub uses its default.",
                        "fix": f"Change it in {where}, then restart the hub."})
    for key in ("projects", "kit"):
        if isinstance(raw.get(key), str) and raw[key].strip() and not Path(os.path.expanduser(raw[key])).is_dir():
            out.append({"level": "warn", "text": f"The {key} folder in config.json, {raw[key]}, doesn't exist.", "fix": f"Make the folder, or change {key} in {where}."})
    if not raw.get("login") and not (isinstance(raw.get("key"), str) and len(raw["key"]) >= 32):
        out.append({"level": "error", "text": "config.json has no login and no key, so the hub won't start.", "fix": "Run install.sh again."})
    held = raw.get(KEY)
    if isinstance(held, dict):
        for name, v in held.items():
            if name not in BY_NAME:
                out.append({"level": "warn", "text": f"There's no setting called {name}. It's ignored.{suggest(name)}", "fix": f"Rename it or remove it under \"settings\" in {where}."})
                continue
            if BY_NAME[name].get("kept") == "catcher":
                out.append({"level": "warn", "text": f"{name} under \"settings\" is ignored: the Dream Catcher's switch is kept in its own file.", "fix": "Remove it, and use the switch in Settings instead."})
                continue
            try:
                check(name, v, {"models": _models_held(held)})
            except Malformed as bad:
                out.append({"level": "warn", "text": f"{name} is ignored: {bad}", "fix": "Set it again in Settings, or fix it by hand."})
    try:
        import hub_catcher
        chosen = json.loads(hub_catcher.CHOICE.read_text()).get("auto")
    except (OSError, ValueError, AttributeError):
        chosen = None
    if isinstance(raw.get("dream_catcher_auto"), bool) and isinstance(chosen, bool) and chosen != raw["dream_catcher_auto"]:
        out.append({"level": "info", "text": f"dream_catcher_auto in config.json says {str(raw['dream_catcher_auto']).lower()}, and the Dream Catcher's switch says {str(chosen).lower()}. The switch wins.",
                    "fix": f"Remove dream_catcher_auto from {where}, so the switch is the only place it's set."})
    return out


# ── health: the hub's parts, each with a fix ──
def _version_of(cmd: list) -> str:
    try:
        done = subprocess.run(cmd, env=ENV, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or done.stderr).strip().splitlines()[0] if done.returncode == 0 and (done.stdout or done.stderr).strip() else ""


_health = {"at": 0.0, "rows": None}


def health(body=None, fresh=False) -> dict:
    """GET /api/settings/health: config diagnostics, then claude, tmux, the hooks, the kit and launchd."""
    if fresh or _health["rows"] is None or time.time() - _health["at"] > 60:
        _health.update(at=time.time(), rows=_parts())
    problems = diagnostics()
    return {"config": problems, "parts": _health["rows"], "at": _health["at"]}


def _parts() -> list:
    import hub_data
    rows = []
    claude = shutil.which("claude", path=ENV["PATH"]) or hub_data.CLAUDE
    said = _version_of([claude, "--version"]) if Path(claude).exists() else ""
    rows.append({"name": "Claude Code", "ok": bool(said), "text": said or "Claude Code isn't found.",
                 "fix": "" if said else "Install Claude Code (curl -fsSL https://claude.ai/install.sh | bash), or add its folder to \"path\" in config.json."})
    said = _version_of([hub_data.TMUX, "-V"])
    rows.append({"name": "tmux", "ok": bool(said), "text": said or "tmux isn't found.", "fix": "" if said else "brew install tmux"})
    event = APP / "hub_event.py"
    hooked = all(p.exists() and shlex.quote(str(event)) in p.read_text() for p in (hub_data.HOOKS, hub_data.HUB_SETTINGS)) if event.exists() else False
    rows.append({"name": "Hooks", "ok": hooked, "text": "Every session the hub starts reports to it." if hooked else "The hooks that tell the hub what a session is doing aren't in place.",
                 "fix": "" if hooked else "Restart the hub: it writes them as it starts."})
    amk = KIT / "bin" / "amk"
    rows.append({"name": "Memory kit", "ok": amk.exists(), "text": pasteable(KIT) if amk.exists() else f"No kit at {pasteable(KIT)}.",
                 "fix": "" if amk.exists() else "Set \"kit\" in config.json to the agent-memory-kit folder, then restart the hub."})
    installed = Path(os.path.realpath(CONFIG)) == Path(os.path.realpath(INSTALLED_CONFIG))
    if not installed:
        rows.append({"name": "launchd", "ok": None, "text": "This is a second instance: launchd doesn't keep it running.", "fix": ""})
    else:
        plist = LAUNCHD_JOBS / f"{LAUNCHD_LABEL}.plist"
        try:
            loaded = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"], capture_output=True, text=True, timeout=5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            loaded = False
        ok = plist.exists() and loaded
        rows.append({"name": "launchd", "ok": ok, "text": "Starts the hub at login and restarts it if it stops." if ok else
                     ("The job is there but not loaded." if plist.exists() else "No launchd job: the hub stops when you log out."),
                     "fix": "" if ok else (f"launchctl bootstrap gui/$(id -u) {pasteable(plist)}" if plist.exists() else "Run install.sh and say yes to the launchd job.")})
    return rows


# ── about: the version, the branch followed, and what's new since the version the person last saw ──
def about() -> dict:
    import hub_update
    version = hub_update.version()
    head = hub_update.out("rev-parse", "HEAD") if version else ""
    seen = notes().get("seen")
    if head and not (isinstance(seen, str) and COMMIT.match(seen)):
        _note(seen=head)  # the first version this hub shows is where What's new starts from
        seen = head
    news = []
    if head and seen != head and hub_update.git("merge-base", "--is-ancestor", seen, head).returncode == 0:
        rows = hub_update.out("log", "--no-merges", "-30", "--format=%h%x09%cs%x09%s", f"{seen}..{head}").splitlines()
        news = [dict(zip(("commit", "date", "subject"), row.split("\t", 2))) for row in rows if row.count("\t") >= 2]
    elif head and seen != head:
        _note(seen=head)  # a version that isn't behind this one (another branch): nothing to tell
    last = hub_update.last()
    return {"version": version, "branch": last.get("branch") or "", "current": hub_update.out("symbolic-ref", "--short", "-q", "HEAD") if version else "",
            "updates": hub_update.enabled(), "news": news, "recent": [] if news or not version else
            [dict(zip(("commit", "date", "subject"), row.split("\t", 2))) for row in hub_update.out("log", "--no-merges", "-6", "--format=%h%x09%cs%x09%s").splitlines() if row.count("\t") >= 2]}


def seen(body=None) -> dict:
    import hub_update
    head = hub_update.out("rev-parse", "HEAD")
    if head:
        _note(seen=head)
    return about()


def forget_starts(body=None) -> dict:
    """Every project forgets the choices its last session started with, so the hub's defaults apply everywhere."""
    import hub_data
    hub_data.the_person("reset every project's session choices")
    gone = 0
    for path in hub_data.PROFILES.glob("*.start.json"):
        path.unlink(missing_ok=True)
        gone += 1
    return {"forgot": gone}


# ── server.py --check ──
def cli_check() -> int:
    """Print what is wrong with config.json and how the hub's parts are. 0 when nothing is wrong, 1 otherwise."""
    print(f"Config: {pasteable(Path(CONFIG))}")
    problems = diagnostics()
    for p in problems:
        print(f"  {'✗' if p['level'] == 'error' else '!' if p['level'] == 'warn' else '·'} {p['text']}")
        if p.get("fix"):
            print(f"      Fix: {p['fix']}")
    if not problems:
        print("  ✓ Nothing wrong.")
    print("Parts:")
    rows = _parts()
    for row in rows:
        print(f"  {'✓' if row['ok'] else '·' if row['ok'] is None else '✗'} {row['name']}: {row['text']}")
        if row.get("fix"):
            print(f"      Fix: {row['fix']}")
    return 1 if any(p["level"] in ("error", "warn") for p in problems) or any(r["ok"] is False for r in rows) else 0
