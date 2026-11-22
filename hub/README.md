# Dream Hub: the hub

The control-room half of Dream Hub: a private web page on your Mac for projects on the agent memory kit. Create
them, read their memory, run and review dreams, and run several Claude Code sessions in browser terminals. Every
Claude session also starts with Remote Control, so it can be followed from the Claude app on your phone.

This is the hub's full reference. Start with the [README at the top of the repository](../README.md). Open the hub at
the address `install.sh` printed (`http://127.0.0.1:8491/?key=…` the first time, on this Mac only; or your Tailscale
address). The design reasoning is in `docs/brief.md`.

## How it works

| Part | Where |
|---|---|
| Server (Python standard library, loopback only) | `server.py`, launchd job `ai.agent-hub` (optional; `install.sh` offers it) |
| Reads and writes for projects, memory, dreams and sessions | `hub_data.py` |
| Link cards (fetched under guards), file facts for hover cards, image thumbnails | `hub_preview.py` |
| Everything asked of the agent memory kit: the scripts it runs, the kit files it reads | `hub_kit.py`, and nowhere else |
| Which hub this is, and what its commands run in | `hub_base.py` |
| Session state from Claude Code hooks | `hub_event.py`, written to `~/.local/state/agent-hub/events/` |
| What a session is doing now: tool, turn, orb, error, context, changes, ports; Clear, Stop a port, peek | `hub_status.py` |
| The built-in browser and device preview: the preview listener, its tickets, suggestions, Health's row | `hub_browser.py`, `ui/browser.js` |
| A session's changes, read with git: the count, the review, line comments sent back | `hub_diff.py` |
| The state kept fresh while a page watches, and its changes pushed to open pages | `hub_push.py`, `GET /api/stream` |
| What a session made, found in its transcript and served sandboxed to the viewer | `hub_artifacts.py` |
| Terminals | tmux on its own socket (`tmux -L agent-hub`), so they outlive the browser and the server |
| The Dream Catcher: its runs, and carrying out its verdicts; its instructions; the check its session runs | `hub_catcher.py`, `dream_catcher.md`, `catcher_verdicts.py` |
| What a test run talks to | `tests/instance.py` |
| Interface (no build step) | `ui/` |
| Install or reinstall | `sh install.sh` at the top of the repository |

It holds almost no state of its own: projects are the stores in `~/agent-memory`, and proposals are the files in
each store's `dreams/`. Session metadata is in `~/.local/state/agent-hub/sessions/`.

## A second instance

Six things make an instance, and each comes from an environment variable.

| Variable | What it sets | The installed hub's value |
|---|---|---|
| `HUB_PORT` | Loopback port the server listens on | `8491`, or the config's `port` |
| `HUB_STATE` | Sessions, hook events, records, uploads, project names and icons | `~/.local/state/agent-hub` |
| `HUB_TMUX` | Name of the tmux socket | `agent-hub` |
| `HUB_CONFIG` | File holding the owner's login and the app's origin | `~/.config/agent-hub/config.json` |
| `HUB_KIT` | The agent memory kit: its template, installer, dream runner and scripts | the config's `kit`, else the `agent-memory-kit` folder beside the hub, else `~/tools/agent-memory-kit` |
| `HUB_JOBS` | Folder the dream jobs are read from | `~/Library/LaunchAgents`, launchd's own |

It is all or nothing. With none of them set, the server is the installed hub. With any of them set it is a second
instance and all six must be: a missing one, an empty one, a relative path or a port outside 1 to 65535 stops the
server with one sentence naming the variable, before it touches anything. So a second server can never run half on the
installed hub's state folder, socket, config or dream jobs. The rule is `read_instance` in `hub_base.py`; the tests use it too. A
session's hook gets its hub's state folder from `HUB_STATE` in the session's own environment, and refuses an empty or
relative one.

The top-level `install.sh` installs the one hub this Mac has and nothing else. It refuses to run while any `HUB_*` variable is set.
A second instance is started by hand and is never installed.

The kit schedules dreams through launchd and nowhere else, so only a hub whose `HUB_JOBS` is launchd's own folder
asks it to. A hub with any other folder reads the dream jobs it finds there, makes new projects without a dream job
(`AGENT_KIT_NO_SCHEDULE=1` to the kit's installer), never asks launchd anything, and refuses the dream switch with a
sentence saying why. That is what lets a second instance run without touching launchd.

What a second instance has to itself: its port, its sessions and terminals, its hook events, records and uploads, its
project names and icons, its config, and the folder it reads dream jobs from. What it shares with the installed hub, because these belong to the Mac:

- the stores in `~/agent-memory` and the folders in your projects folder, so both list the same projects
- the kit's state folder, `~/.local/state/agent-memory`
- `~/.claude`: Claude Code's transcripts, settings and its own notes

So a second instance is for trying the hub's code, not for trying things on a project you care about.

To run one beside the installed hub, with a config whose origin is its own loopback address:

    mkdir -p /tmp/hub2
    echo '{"login": "you@example.com", "origin": "http://127.0.0.1:8492"}' >/tmp/hub2/config.json
    export HUB_PORT=8492 HUB_STATE=/tmp/hub2/state HUB_TMUX=agent-hub-2 HUB_CONFIG=/tmp/hub2/config.json HUB_KIT=$(cd ../agent-memory-kit && pwd) HUB_JOBS=/tmp/hub2/jobs
    /usr/bin/python3 server.py

A seventh, `HUB_PREVIEW_PORT`, is optional: the port of the instance's preview listener (see "The browser and the
device preview"), the hub's port + 1 when unset. Set it when that port is taken; a listener that can't bind says so in
the log and in Health, and the hub runs on without it.

It answers only requests that carry that login and that Host, as a hub behind Tailscale Serve does (a config with a `key` and no `login` works as on the installed hub too). Stop it by its PID, then end
its terminals with `tmux -L agent-hub-2 kill-server`.

## Home

Home leads with what needs you, as a queue with three tabs, each with its count: **Needs you** (a session asking,
a proposal to review, what dreams found, approved changes only you can apply), **Working** (sessions in a turn and
dreams running) and **Done** (turns that finished, and sessions closed in the last day). The first tab with something
in it is shown; a zero never leads. `1`, `2`, `3` switch tabs, `j`/`k` move, `↵` opens. A Done row is unread until you
open its session or press `e` (**Mark read**, and again to mark it unread). Read is kept on the server
(`reads.json` in the hub's state folder, `POST /api/reads`, `reads` in `/api/state`), so reading a finish on the phone
clears it at the desk. A mark is keyed to what the session last said, so its next finished turn is unread again. Marks
a browser kept before (`hub.read` in `localStorage`) move to the server once.

Below the queue, a card per project says one thing: how many sessions are open, else that setup isn't finished,
else when it dreams. The repo line is left out when it only repeats the project's name. Activity folds the rows one
dream wrote into one line, which opens.

A project's pages (its sessions, Memory, Dreams) share tabs in the top bar: Sessions with how many are open, Memory
with how many lessons, Dreams with how many things there wait for you. `m` and `d` still jump to them.

## Projects and sessions

Each project has a homepage (`#/p/<name>`) with its sessions nested under it in the sidebar. A session has its own
page (`#/s/<id>`), and up to four can share one (six on a screen at least 1600px wide, when the `max_panes` setting says 6), side by side and stacked in any mix. Drag a session (its sidebar row, its row on
Home or a project's page, or a pane's header) onto a pane: the half it would take (left, right, top or bottom) is filled
as you move, a drop on the edge of the whole split runs the full height or width, and a pane dropped on another's centre
swaps places. Esc cancels. The drag is pointer events, mouse or trackpad; a touch never starts one. Each pane's split
button does the same from the keyboard (Split right…, Split down…, Move…, Close pane), and **Split**, the sidebar's split
button or ⌘-click add a session where the old grid would have. The hash says the layout: `#/s/a,b` is side by side (and
`a,b,c`, `a,b,c,d` the old grid, so older links open as they did); any other shape is written out, `h(a,v(b,c))` for a
beside b over c (`h` side by side, `v` stacked). Drag the gutters, or focus one and use the arrow keys, to size the panes;
Enter or a double-click evens them out. Sizes are kept per layout in this browser (`layoutSizes`). The right panel follows
the pane you last clicked. ⌥1–4 jumps between panes. `z` (or the prefix then `z`, the pane menu's Zoom, or a double-click on a pane's
header) zooms one pane to fill the split; the others stay connected and keep their size underneath, the hash keeps it
(`#/s/<layout>~<id>`), and `z` or Esc shows the whole split again. On a phone one pane of a split shows at a time, with a row of its
sessions above it to switch between them. The right panel starts shut there, whatever the desk chose; opening it on the phone lasts for that page.

**The shell.** Drag the sidebar's right edge to make it 180 to 420px wide. Drag it past the narrow end, press ⌘B or use
the button at its foot, and it folds to a 48px rail: each project's mark and an orb for every session still running
under it, each named on hover. The right panel of a session resizes the same way from its left edge (240 to 560px), and
dragging it shut closes it. Each session keeps its own panel, open or shut and how wide; one you haven't opened yet takes
the last choice you made. All of this is kept per browser (`localStorage`), so a phone and the Mac each keep their own.

Every session row in the sidebar has its orb and, while it is live, a second line in its state's colour: the tool and
target it is on with the turn's elapsed time (from `activity` and `turn` in `/api/state`, when the server sends them),
the question it asks, or what it said last. A finished turn you haven't read keeps its cube lit; once read it goes
faint. A project row, and a folder that is shut, show one orb for what is under them: needs you, then a finish you
haven't read, then working, then dreaming. The tab's title leads with the counts, `(1 waiting, 3 done, 2 working)`,
and its icon gains a rose diamond, a blue check or a jade square.

**Keys.** `?` docks a searchable sheet of every key at the left, and the app stays usable beside it. j and k walk the
sidebar (on a page with its own list, they walk that list, and walk the sidebar once focus is in it); ↵ opens, space
peeks at the session on the row. `g` then `h` goes home, `g d` and `g m` open this project's Dreams and Memory, `g n`
starts a session, `g s` goes to the sidebar. ⌘K (or `/`, or the search button in a phone's top bar) opens Go to, led by actions for the session in hand (the
sidebar row with focus, or the pane you're in): Open, Peek, Rename, Close, Resume, Copy the phone link, Delete… Below them every
session, in attention order before you type (needs you, finished and unread, working, the rest), with what it is doing
or asking. Every word typed must match, across its name, project, folder, branch, the tool it is on, what it asks and
what it said last; Needs you, Working and Done filter it (or type `is:needs`, `is:working`, `is:done`). Closed sessions
follow a line, with Resume (⌘↵); the projects, boards and commands come last.

**The prefix.** ⌃` (the `prefix_key` setting) works from anywhere, inside a terminal too: it leaves the terminal, as
it always did, and the status line lists what one more key does. `n` opens the next session that needs you, then the
finished ones you haven't read; `j` and `k` the next and previous in the sidebar; `l` the last one you were in; `1`–`6`
a pane; the arrows (or ⇧H J K L to swap) move to or swap with the pane that way; `z` zooms; `s` splits; `/` opens Go to;
⇧1–9 opens a board. Focus lands in the terminal it opens. Esc, or no key, leaves you out of the terminal; pressed outside
one on a session page, no key takes you back in. Its keys never reach the terminal, and it uses no ⌃⌥ chord, which
VoiceOver keeps. On a phone the alert bar's **Next** does what `n` does.

**Boards.** The Split menu's **Save as a board…** names the split in front of you. Boards are kept on the server
(`boards.json` in the state folder, like folders), so every browser has them; Home lists them with one mark for all
their sessions (needs you beats working beats finished), and the prefix then ⇧1–9 opens one at the sizes it was saved
with. A session deleted since leaves the board; a closed one shows its record, with Resume. Rename, reorder and delete
from the board's `⋯` on Home.

**The terminal's extras** (each a switch in Settings › Features, from herdr's most-asked; `hub_terminal.py` and the
terminal block of `app.js`). A link that wraps onto the next rows is underlined and opens whole from any of them, for up
to 30 rows; ⌘-click opens it too, and a page a session serves on this Mac opens in the hub's own browser once that
feature says how (`window.hubBrowser.open`). On a phone, with **ask before opening a link** on (it is off at first, since a
tap used to open at once), a tap offers Open and Copy. **Selecting text in a terminal** copies when you let go, as
tmux always did, or holds it for ⌘C (Ctrl+Shift+C elsewhere, or a tap on the note), or never copies; a program's own copy
still goes through. A double-click takes a whole path, link or flag (tmux's `word-separators`). ⇧PgUp and ⇧PgDn scroll
tmux's history by half a screen (xterm.js kept those keys and did nothing with them); PgUp and PgDn page through Go to
and menus. The prefix then `t` opens a **scratch terminal**: a shell in the session's folder, over the panes on a desk
and full screen on a phone, in a tmux session of its own (`pop-<sid>`) that no list shows. Hidden (the prefix and `t`
again, Hide, or Esc outside the shell) it keeps running; Close ends it, asking first while a program runs in it; it ends
with its session. In a split, the prefix then `e` evens the panes out, space goes to the next layout (side by side, main
and stack, grid) and `o` rotates them, every pane one place on; the Split menu lists the same. **Alerts from terminal
output** watch for the patterns you list (a regular expression each, for every project or one): the server looks only at
panes that printed since its last look and only while a pattern is set, counts a line the first time it shows and never
the line the cursor is on or a command you typed, tells at most three a minute per session, and keeps the last 50 in
`triggers.json`. A page tells each as a notice, or the system's notification when the hub isn't in front, including one
that came while no page was open (within six hours). Stopping a plain terminal asks the same question from its pane, a
split's pane menu, the sidebar and Go to; a Claude session closes through the one Close dialog everywhere.

A session's `⋯` menu in the sidebar renames or deletes it (Delete is also in a running pane's `⋯` menu and on a closed or ended pane). A rename is kept with the session on the server, so every browser sees it. A running Claude session is also sent `/rename <project> · <new title>`, which Claude runs at once; not when something is typed in its input, because the command would land on the end of it. With `feature_title_sync` on, a rename that couldn't be sent waits (`renamePending` in the session's record) and goes as soon as the input is empty and no dialog is open, and a `/rename` typed in Claude itself reaches the hub: Claude writes its name into the transcript (`custom-title`), and when that changes and isn't the hub's own doing, the hub takes it (`sync_title` in `hub_data.py`). F2 renames the session in hand, the sidebar row with focus or the pane you're in; Esc leaves the name as it was.

A session needs you when Claude asks permission or a dialog is open on its screen, whatever the hooks last said. A turn
that finishes on a question (its last sentence ends in `?`, read from the transcript by `question_in` in `hub_data.py`)
is **Done · asks you**: done, with a small "asks you" tag in the sidebar and on Home, and `asks: true` in the state.
The setting `asks_as_needs` (in config.json's `"settings"`, and `pref("asks_as_needs")` in the page) counts it as
needs instead. Needs shows in the sidebar and, when the app isn't in front, as a browser notification (turn on from
the sidebar). A worker in `ui/clock.js` keeps polling in background tabs.

How the state is decided is `decide` in `hub_status.py`. The screen is read only where Claude draws its own lines: the
footer under its input box ("esc to interrupt"), a live dialog's rows, and key hints that end the screen. A reply that
quotes those words sits higher up and can't pass for them. A picker you opened yourself (`/model`) needs nothing. A
change from working to finished is held until a later poll still sees it (`Settle`, at least 0.7 s), so the state
doesn't blink between tool calls; a finish the Stop hook reports, with no spinner on screen, shows at once. Each
session says why it is in its state (`why`: `hook: Stop at 14:02`, `screen: permission prompt`, `screen: spinner`,
`status file: idle since the last hook`), in its row's tooltip and in Peek.

While a Claude session runs, the poll stamps `alive_at` (in `alive.json` in the state folder, at most once a minute).
A session whose stamp is older than the Mac's last start, or the tmux server's, was running when it went down: Home
leads with "N sessions were running when the Mac restarted", with **Resume all** and a Resume per session. One that
can't be resumed stays there with its error and **Try again**; **Not now** forgets the lot, and each stays resumable
from its pane. A session you stop while the Mac is up loses its stamp at the next poll, so it is never counted. See "What needs you" below for read marks, notices and sounds.

**Close session** (pane header, or the `⋯` menus) ends a Claude session and keeps its conversation. It first asks Claude
to tidy up and write a four-line handoff (Done, Open, Next, Cleaned) unless you untick that; Claude must be idle with nothing typed for the handoff.
When the folder has uncommitted changes the dialog lists them (`close_check`) and offers **Commit them first**, on by
default, with an optional hint for the message. Then the prompt (`handoff_prompt`) first asks Claude to commit its own
work: only the files it changed in this session, staged by name, never secrets, in the repo's own style with its hooks,
never pushing or amending; anything it isn't sure of stays uncommitted, and the handoff gets a fifth line, Committed.
It isn't offered for a folder the hub never runs git in (`no_vcs`), one that isn't a git folder, a hub session, or a
session in Plan mode (the dialog says why). The hub itself never commits. When the close ends (the handoff came, or the
wait ran out) the hub reads what was committed since it asked and what is still uncommitted (`closeResult` on the
session) and says so wherever you are in the app, as a toast, and as a browser notification when the app isn't in front.
The sessions it is waiting on are kept in this browser (`closeWatch`), so a reload in between still hears it. A closed pane shows the
conversation as a record, handoff on top, with **Resume**, which runs `claude --resume <id>` in the same folder with the
same mode, model, effort and agent, so Claude continues the same session with its whole history.

**Worktrees.** A session of its own works in `<repo>/.claude/worktrees/<name>` (or where `worktree_path` puts it, below) on a branch `hub/<name>`, and its session
keeps the branch it came from and the commit it started at. Its pane header has a chip with the branch, how many commits
it is ahead, how many files are uncommitted, and "merged" once its work is in the branch it came from (by ancestry, or
every commit having an equal one there); on a phone or a narrow pane, the one fact that matters most. Tapping it shows
the details. The close dialog adds **Remove the checkout (keeps the branch)**, ticked when nothing is uncommitted. It
runs after the commit step: a clean checkout is removed with `git worktree remove`, never forced; one with files still
uncommitted is kept, and the hub then asks again, naming the files that removing it would lose. A session whose checkout
is gone can't be resumed. The project page lists every checkout under `.claude/worktrees` and every `hub/*` or
`worktree-*` branch left without one, with its session, ahead, uncommitted and merged; **Remove** takes a checkout (a
second yes, naming the files, if any are uncommitted), **Delete** takes a branch whose checkout is gone (a merged or
empty one at once; one with unmerged commits only after a box that says how many is ticked), and **Clean up merged**
shows what it would remove before it removes it, leaving any with uncommitted files or a running session.
**Where they go.** The `worktree_path` setting (Settings › New sessions) places new checkouts elsewhere, by a template:
`{parent}/{repo}-worktrees/{name}` keeps them in a folder beside the repo, `.worktrees/{branch}` inside it. A relative
template is from the repo; `{parent}` is the repo's folder, `~` home. `{repo}`, `{project}`, `{name}` and `{branch}`
(`hub/<name>` as `hub-<name>`) are filled with plain names, and `{name}` or `{branch}` must be in the last folder, so each
checkout has its own. It must land inside the repo (never in `.git`) or in a folder of its own inside the projects folder,
with no `..`: `check_template` in `hub_worktrees.py` refuses anything else, and the field previews the folder a new
worktree would get for a real project. A template that can't be used for some repo (one outside the projects folder)
leaves that repo's worktrees in `.claude/worktrees`. Empty is today's place. A checkout placed this way is kept with its
session (`tree.placed`), and is the hub's to list and remove like the others; a folder beside it that no session placed
is not. The server
(`hub_worktrees.py`) checks all of it again: only folders git lists as worktrees of the project's folder, directly in
its `.claude/worktrees`, never the main checkout, nothing while a session runs there, and the count of files or commits
the person agreed to lose must still be the count, or nothing happens. No git runs in a `no_vcs` folder: its list says so.

The tidy-up rules sent with the prompt: stop only servers and processes this session started, never launchd services
or Docker containers; wait on a PID or `pgrep -x`, never `pgrep -f` (it matches its own loop);
delete only test residue inside the session's temp folder (`/private/tmp/claude-<uid>/`) or its project folder, never
`~/Library/Caches` or the npm, pip and Homebrew caches. The prompt goes in as one bracketed paste through a tmux buffer:
typed keys that long arrive as a paste and Claude keeps only the tail.

Claude's memory isn't relied on. A closed session's record asks the hub, each time it opens, for servers still listening
whose working folder is inside the session's folder, leaving out launchd jobs and anything under a running hub session.
They are listed as "Still running from this folder" with port, pid and uptime. The hub never stops them.

Claude Code deletes its own transcripts after 30 days, so the hub copies each closed or ended session's transcript (and
its subagents) into `~/.local/state/agent-hub/records/<id>/`. The record reads from that copy once Claude's is gone,
and Resume puts it back where Claude looks for it. A close interrupted by a hub restart finishes on the next poll,
without its note.

Plain terminals keep Stop, which ends the process. The ✕ in a grid only closes the pane.

**Delete** (`delete_session` in `hub_data.py`) asks first, in a dialog that says which session it is (project, when it last
ran and started, its size), whether it runs now, that the conversation can't be resumed or read in the hub afterwards,
what goes to the Trash, and whether the memory kit has read it: from the kit's own record of its last dream
(`last_dream` in its state file), all of it, only up to that dream, or none of it, in which case what it taught is lost
to memory. The kit's searchable archive copy (`~/.local/state/agent-memory/sessions/<store>/`) is said to be kept, and
is: the hub never touches it. Keep is the default; Esc and a click outside cancel. Deleting ends a running session
first (its own tmux session, by exact name, and waits for its processes to exit), then moves Claude's transcript, the
folder beside it (subagents), the hub's record and the uploads into one new folder in `~/.Trash`, with the session's
own record and a note of where each item was, and forgets its hook events. Only transcripts the hub itself recorded for
the session are moved, and only when they resolve to a `<uuid>.jsonl` directly inside a folder of
`~/.claude/projects`; nothing from the request is used as a path. A session that is closing is refused. The
`/dismiss` endpoint the test scripts clean up with still removes without the Trash; the page no longer uses it.

The status mark is a pixel cube (`ui/orbs.js`, drawn on the 2px grain of the projects' marks, three faces in three
tones of one colour; every state is on one sheet in `docs/cube-states.html`). Each state has its own shape and at most
one motion, in whole pixels: working builds itself pixel by pixel from the bottom (thinking turns face by face,
compacting and closing settle from the top), jade; needs you lifts its lid, rose, the one that moves to draw the eye;
done is still with its top face lit, blue, and faint once you have read it; idle and a terminal are still and
solid; ended, closed and not connected are an outline; an error has lost a block of its right face to the corner,
rose, and that block blinks while the API retries; a project that is dreaming shimmers across its faces, blue. With
reduced motion each holds still and still differs by shape (two thirds built, the lid up). A cube off screen doesn't
animate. Where a cube can't draw yet (the first moments of a page) the older marks stand in:

| Dot | Meaning |
|---|---|
| Pulsing jade square | Working |
| Rose diamond | Needs you |
| Rose cross | Error: the API stopped the turn, or Claude's process is gone. **Clear** in the pane's strip |
| Blue check | Done |
| Jade tray, pulsing | Closing: writing its handoff |
| Tray | Closed: a record you can read or resume |
| Hollow square | Ended on its own |
| `>` | Plain terminal |

A rename changes only the display name, kept with the icon in `~/.local/state/agent-hub/projects/`. The store, folders
and schedules keep their original names, so nothing that depends on them breaks.

## What needs you

The hub is built so you never hunt for the session that needs you. In code it is one word per session,
`attentionKind(s)` in `ui/app.js`: **needs** (it waits on you, or stopped with an error), **done** (a turn finished
and you haven't read it), **working**, or **idle**. A turn that ends on a question (`asks` from the server) counts as
done, "asks you", unless the `asks_as_needs` setting is on. `attentionOrder(sessions)` puts them in that order, the
newest change first inside each. The sidebar sorts by it, and anything that walks to the next session that needs you
can use the same order.

**Read.** Opening a session reads its finish, and so does a finish that comes while it is on screen and the page is in
front of you. Read marks are on the server (see Home), so every device agrees.

**The sidebar's order.** The button in the sidebar's header (or the `sidebar_order` setting, `project` or `attention`)
sorts it by what needs you: one list in bands, Needs you, Done, Working and Idle, each row with its project after its
name, and the projects under it. Rows glide to their new place when the order changes (they jump with reduced motion).
Between those changes a poll updates rows in place, so a working session's line changes without the list being redrawn,
and hover, focus and scroll stay put.

**Notices.** `notify_needs` (default `system`) and `notify_done` (default `off`) each take `system`, `banner` or `off`.
`system` is the browser's notification while the hub isn't in front, and a card in the hub while it is (for needs, the
sidebar's card already says it); `banner` is only ever the card in the hub. A state is told only once it has held for two
polls, so a permission auto mode approves at once never rings. A newer notice replaces the same session's older one,
and a notice goes when the wait ends or the finish is read. Nothing is told for the session you are looking at, or for
a project in `muted_projects` (a project's `⋯` menu mutes it). Closing a session and the Dream Catcher follow
`notify_closed` and `notify_catcher` the same way; both default to `system`, as they behaved before the settings.

**How long, and what was said** (`feature_notice_tools`, `notice_time`). A notice stays its own time (needs 8 s, done
5 s, closed 8 s, the Dream Catcher 6 s), or what `notice_time` says: 5, 10 or 30 seconds, or until dismissed. A passing
message (a toast) takes the same seconds, waits while the pointer is on it, and still passes when the setting is "until
dismissed". Under the notices, **Recent** opens the last 50 told on this device (`hub.noticeLog` in localStorage), each
opening what it was about, and **Clear all** shows once two are up. On a phone a notice swipes away sideways. Go to has
**Recent notices** too.

**Sounds.** `sound_needs` and `sound_done` pick `chime`, `knock`, `bell` or `off` (the default), at `sound_volume`
(0 to 1, default 0.6). The tones are made in the page with Web Audio; `window.hubPlaySound(name, volume)` plays one. A
browser lets a page play sound only after a click or a key on it: the first one unlocks the hub's audio, and if a sound
was due before that, the hub says so once.

**On a phone,** a row under the top bar counts what is open, `2 need you · 3 done · 5 working`; each opens that tab on
Home.

## Folders of projects

Projects can be sorted into folders, in the sidebar and in Home's Projects panel. The folder button beside "Projects"
in the sidebar makes one; a project's `⋯` menu (or right-click) moves it into a folder, out of one, or into a new one,
and on a computer a project row can be dragged onto a folder, or onto "Projects" to take it out. A folder's own `⋯`
renames it, moves it up or down, or deletes it, which puts its projects back at the top level. A folder only sorts:
the store, its repos, sessions and memory stay where they are. Folders are kept on the server in
`~/.local/state/agent-hub/folders.json` (`set_groups` in `hub_data.py`, `POST /api/groups`), so every browser sees the
same ones; whether a folder is open is kept per browser (`foldersShut` in localStorage).

**Arranging the sidebar.** Each of these has its switch in Settings › Features; off, the sidebar is as it was.
- **The order** (`feature_project_order`). Drag a project row before or after another (a line shows where it lands; onto
  a project in a folder, it moves into that folder too), or focus it and press ⌥↑ or ⌥↓, or use its `⋯` menu's Move up
  and Move down, which is how it's done on a phone. The order is one list of names, `project_order` in the settings, so
  every device agrees; a project it doesn't name yet comes after those it does. It orders the projects inside each folder
  and those in none, the rail, and what the prefix's `j` and `k` walk. Sorted by what needs you, the sessions keep their
  attention order and the project list under them follows this one.
- **Hidden projects** (`feature_hide_projects`, `hidden_projects`). A project's `⋯` menu hides it, or Settings › Sidebar
  ticks it. It leaves the sidebar and the rail, and **Hidden (n)** at the foot of the list opens to show it; Go to still
  lists it, marked Hidden, with its sessions. It still tells you when it needs you, as every project does: the alert card,
  the notice and the sound, and the Hidden row shows the needs-you mark. Muting is what silences a project.
- **Colours** (`feature_project_colours`, `project_colours`). A project's `⋯` menu → Colour… picks one of nine (blue,
  jade, pink, gold, sky, violet, orange, lime, slate), or none. Each has a tone for the dark theme and one for the light
  (`--pc-<name>` in `app.css`), at least 3:1 on every surface it sits on. It colours the project's mark everywhere, runs a
  2px edge down its rows in the sidebar, and edges its sessions in Go to. Other parts read `projectColour(name)` in
  `app.js`: `var(--pc-<name>)`, or `""`.
- **The side** (`sidebar_side`, `left` or `right`, in Settings › Sidebar). On the right, the shell turns round: the edge
  still drags (toward the sidebar makes it wider), ⌘B still folds it to the rail, Peek opens on its left, notices move to
  the left corner, and on a phone the drawer comes from the right. `body[data-sidebar]` says which side it is on, so a
  panel placed beside the session can take the other one.
- **Subagents** (`feature_subagents`). A live session that started subagents has a line under its row, `3 subagents,
  1 running`, open while one runs: a row each with what it was asked and Running, Done, Failed or Stopped. It reads
  `agents.list` in `/api/state` (`counts` in `hub_agents.py`: the latest six, running first), so it costs nothing more.
- **Jump numbers** (`feature_jump_numbers`). Hold ⌥, or press the prefix, and each pane of a split shows the number that
  picks it (⌥1–6, the prefix then 1–6), and so does its row in the sidebar; `body[data-jump-keys]` is `alt` or
  `prefix` meanwhile. Go to numbers its first nine sessions, and ⌥1–9 opens one. ⌘1–9 is left alone.

## Hub sessions

**Hub sessions**, the row under Home, are Claude sessions that belong to no project (`HUB_PROJECT`, `@hub`, a name no
store can have), for memory changes across every store in `~/agent-memory`. One starts with
`--dangerously-skip-permissions` and an appended system prompt (`HUB_BRIEF` in `hub_data.py`): name store files by
their whole path, write memory only through the kit's `amk` verbs with `AGENT_MEMORY_DIR` set to the store, never
touch ORG.md, INDEX.md, CHANGELOG.md or the store policy files, never lift ORG.md's lock, never run git in the two
`NO_VCS` repos, and say which store each change went to.

No repo's settings apply to it, so it gets its own, `hub-session-settings.json` in the hub's state folder: the hub's
hooks, the kit's deny rules for the stores (the `~/agent-memory/*` ones and `Bash(chflags *)`, read from the kit's
`settings.snippet.json`), and the kit's Bash guard, `guard_memory.py`, run from the kit's folder. It starts in the home
folder, not in `~/agent-memory`: the guard knows a store by `agent-memory/<store>` in a path, which a path relative to
the stores' folder (`my-app/ORG.md`) doesn't have. The guard still can't follow `cd agent-memory && … my-app/ORG.md`
(the kit's limit, the same in a repo); ORG.md's lock and the `chflags` deny rule hold there, and `memcheck.py` reports
any write around the protocol. It gets no `--add-dir`: each added folder would ask to be trusted at every start.

The page that starts one (`#/p/@hub`) offers model and effort only, no mode and no worktree, and lists the hub sessions
running. A hub session has no Changes, no Mode control and no "Still running from this folder" (its folder is the home
folder); its header says "No prompts", and the files it shares can be previewed from the stores and `~/projects`,
not the whole home folder. The kit doesn't archive or dream on it, because it ran in no store's repo.

## The Dream Catcher

**Dream Catcher**, pinned under Home in the sidebar with its own mark, is a Claude session on call that goes through
everything dreams left waiting on you, decides what it can, and leaves you the rest. Its count is what its last run
left for you; while it runs its orb works. Its page (`#/catcher`) has **Catch dreams now**, the switch for whether it acts,
the last run's report, and what waits on you, project by project, each with the catcher's one-line reason, what it
checked, and the same choices Dreams gives (Approve or Approve fix, Reject, Done for a need only you can put right).

**What it looks at.** Every store in scope (`"dream_catcher_stores"` in the config, every store when unset): the open
proposal's unticked items, needs that are open or stopped, and the files in `inbox/`. A store a dream holds or runs on,
or whose fixer runs, is left out of the run with why (`dream_owner.py`, the hub's own tmux sessions), and so is an open
proposal that is being applied. `hub_catcher.gather` writes the list as `manifest.json` in a run folder
(`dream-catcher/runs/<id>/` in the hub's state folder) before the session starts. The manifest also carries what became
of earlier verdicts, so a run can see where you went against one.

**What is always yours.** Decided by the hub before the session sees an item (`held_back` in `catcher_verdicts.py`):
ORG.md and Steering, unchecked facts (your tick is the check), deleting a memory line, a decision or preference of a
person, anything about credentials or money, a need only you can put right, an inbox proposal about ORG.md or
Steering. Such an item allows only "leave".

**The session.** A hub session (home folder, the kit's guard and the stores' deny rules, permissions skipped) with
`dream_catcher.md` appended to the hub session's rules. It reads each store's ORG.md, INDEX.md and the `project/` files
its items touch, `roots.txt` and the repositories' README and CLAUDE.md, checks each item, and writes `verdicts.jsonl`
(one `{"key", "verdict", "reason", "evidence"}` per item) and `report.md`. Then it runs
`catcher_verdicts.py check <run folder>`, which reads the verdicts with the same function the hub uses and writes
`finished.json` only when every item has exactly one allowed verdict. It never approves anything itself: the kit's guard
stops the person's commands in it as in every session (`tests/catcher_check.py` checks this).

**Carrying the verdicts out.** When a run has finished, the hub (`hub_catcher.settle`, started from the poll) goes
through the items one by one, through its own functions: approve on a proposal item is `tick`, reject leaves it
unticked (a no when the proposal is applied), approve or reject on a need is `decide_need` (the kit's `approve` or
`reject`), and an inbox item it approves is left for the next dream. Before each it checks again that no dream holds
the store, that the proposal is still open and not being applied, and that the item is still in it; otherwise the item
waits for you, with why. Each result is written to `results.jsonl` as it is done, so a crash halfway leaves every line
true, and the next pass does what is left and nothing twice. A proposal is applied (`apply_dream`, the same session Apply
starts) only when every unticked item in it was decided no and something is ticked: an item waiting on you holds it
back, because applying would count it as a no. Each act goes into `person-actions.jsonl` with `"by": "dream-catcher"`
and its reason, and Dreams' **Done in your name** marks it as the Dream Catcher's.

**Act or recommend.** `"dream_catcher_auto": true` in the config lets it act; unset, it only recommends, and
**Accept all recommended** carries the recommendations out as yours. The switch on its page overrides the config once
used (`dream-catcher/settings.json`). When a run is carried out, its own store's `notify.sh` says how many things wait,
and the page sends a browser notification when notifications are on.

**Its own memory.** `sh hub/dream-catcher-install.sh [folder]` makes a folder (`~/projects/dream-catcher` by default) and
a store for it, `dream-catcher`, through the kit's `install-store.sh`. From then on its sessions run in that folder, so
the kit archives and dreams on them like any project's, and that store's dreams are among what it catches. Start Claude
there once to trust the folder. Without the store it runs as a plain hub session and learns nothing across runs.

## The chat

A running Claude session opens on a phone as a chat, not a terminal. At a desk it opens as its terminal, and **Chat** in
the pane's header shows the same chat there (kept as `deskView`, beside the phone's `phoneView`). At a desk Return
sends and ⇧Return makes a new line, and a file dropped anywhere on the conversation is attached.

**What a turn shows.** Each turn of the record carries `media`: what it names or what a tool made, found by the server
(`_media_finder` in `hub_data.py`) with the same rule as the Shared panel, so only files the session may share
(`resolve_shared`'s folders, never a secret) and only web links. It shows inside the conversation, at the point it was shared:

- a picture you paste, or send with the paperclip, inside what you said
- under Claude's words, the files they name: a path (absolute, `~/`, `./` or relative to the session's folder), a path
  with spaces in `code`, the target of `[label](path)` or `![label](path)`, a `file://` address, or a bare file name
  that is in the session's folder
- under a run of steps, what those steps made or looked at: a file written (Write), a picture or PDF read (Read), files
  handed over with SendUserFile, a file a command made (named in it and changed since it started), a screenshot a tool
  returned (MCP tools such as Chrome or computer use included), and what a subagent saw or made, under the step that started it
- a file is shown once in an exchange: where Claude's words name it, or else under the first steps that touched it

How each looks, at a desk and on a phone:

- pictures as tiles; one picture alone at its own shape (no wider than the turn, at most 360px high), its space kept
  before it loads from the pixel size the server reads. A tap opens the viewer, with ←/→ across that turn's pictures
- video and recordings play in place with their controls, never on their own, and are asked for only when they come
  near the screen; a video keeps a 16:9 frame until it knows its shape. The name under a video opens the viewer
- a PDF as its first page (drawn once with `sips`), its name and size; a tap opens it
- up to three links as cards, title, description, site and picture. A card is fetched by the hub (`/api/preview/link`,
  public addresses only) when it first scrolls into view; until then it shows the address. A link to a PNG, JPEG, GIF
  or WebP is its own card: the picture, through `/api/preview/image` under the same guards (512 KB, checked by its first bytes)

In the words themselves links are links, `[label](url)` is the label, and a file path in `code` opens in the viewer.
A new turn joins the page without redrawing the turns before it (`drawTurns`), so a video that is playing keeps
playing, and the record is parsed once per change of the transcript (`_record_cache`).

## On a phone

On a phone the chat is how a running Claude session opens. The conversation is the session's record, polled
every 3 seconds, and scrolls natively. Under it:

- the strip says what Claude is doing, with **Stop** (Esc) while it works
- a choice Claude shows is answered here, in the same panel at a desk and on a phone (see **Choices** below)
- a menu with no cursor row the hub can read is shown as its text, and the keys open for it
- a text box that grows as you type: Return makes a new line, the send button sends it as one paste and Enter
  (`/answer`), and while Claude works the message waits in its queue. A draft is kept per session in this browser
- the paperclip uploads photos and files and puts their paths in the message; HEIC goes up as JPEG
- the keyboard button opens a row of keys for Claude's menus (Esc, ↑, ↓, Enter, Space, Tab, ⇧Tab, ^C), sent through
  `POST /api/sessions/<id>/key`, which takes only those keys

The chat doesn't connect the terminal, so a phone no longer squeezes the session to its own width while you read.
**Terminal** in the pane's header switches to the terminal and **Chat** switches back; the choice is kept per
browser (`phoneView` in localStorage). The page takes the height the keyboard leaves (`visualViewport`), so the box stays above it.
A session that needs you and is the page in front of you on a phone isn't also shown in the alert bar.

## Appearance

Five settings change how the hub looks; the Settings page sets them and they apply at once, without a reload.

- **Theme:** Midnight ink, the dark default; Paper, a light one; or match the system, which follows it live. Paper is
  the same hue with its steps turned round, and every text colour in it passes WCAG AA on every surface it is used on.
  The terminal gets its own light palette, and lifts any colour Claude Code draws too faint to read
  (`minimumContrastRatio`). The media viewer stays dark in both. The phone's browser chrome takes the theme's colour.
- **Accent:** any CSS colour, for links, focus rings, selection and primary buttons. The colours made from it are
  measured against the theme's surfaces and moved until they pass, so no choice makes text unreadable. Jade, rose and the
  blue of Done keep their meaning and don't follow it.
- **Terminal font size**, applied to open terminals, which refit.
- **Density:** compact tightens the sidebar's rows and the chat, for a long list of sessions.
- **Reduce motion:** follow the system, or on or off whatever it says.

All colours are custom properties in `app.css` (`:root` for Midnight ink, `:root[data-theme=light]` for Paper). `ui/theme.js`
loads in the page's head and applies the last choice this browser saw (`hub.appearance` in localStorage) before the
first paint, so a light page never flashes dark; `applyAppearance` in `app.js` then confirms it from the server's
settings. New CSS keeps to the tokens, and asks about motion with `@media (prefers-reduced-motion: reduce)` as before:
theme.js rewrites those rules when the person overrides the system.

## Dreams

The kit's launchd job checks each store once a day at one hour and dreams only when a dream is due. The switch on a
project's page and on Dreams turns that job on and off through the kit's `schedule-dream.sh`, and says the hour of the
daily check. Under it, both pages say why the last dream ran and what the last check found, in the kit's own words,
read from the kit's state file, `~/.local/state/agent-memory/<store>.json`: that a dream is running, with who and since
when; that an open proposal holds a due dream back, with the day its person was last reminded; that the check is
holding back after a try that wrote no proposal. Any key of the file may be missing or null (the last check is void
once a dream finishes), and until the kit has written the file the pages say nothing. A file the kit itself would refuse gets one
plain line saying so and where it is. The rule is the kit's (`load()` and `trusted()` in its `scripts/dream_due.py`),
mirrored in `dream_check_of` because the kit has no command that only reads the file; `tests/test_hub.py` compares the
two case by case. A job made before the daily check still runs on one weekday and reads that way ("Dreams Sundays
18:00") until you switch it off and on.

**Proposals, by the kit's record.** Which proposals a project has, and whether each is open, applied or dismissed, is
what the kit's `scripts/dream_proposal.py --json` says, in the order it says it. The hub doesn't sort file names (the
second proposal of a day is `<date>-2-proposal.md`), doesn't guess from the store's history, and doesn't list a file
in `dreams/` that the record doesn't know. A project has one open proposal at most:

- Only the open proposal can be ticked and applied. Apply opens a session that runs `/dream apply`, which closes the
  proposal itself. A closed one says when it was applied or dismissed.
- Once a proposal has been applied, each ticked item says what became of it, from the record the kit's
  `dream_apply.py` writes beside the proposal (`<stem>-applied.json`, joined to the items by the kit's item id, so an
  item rewritten after it was applied is another item): applied, with its
  commits; already there; refused, with the reason; yours to apply; waiting for the apply session. A ticked line the
  kit couldn't read as an item is listed too, so nothing ticked vanishes. Nothing about what was applied is guessed.
- **Yours to apply.** ORG.md and Steering are your tier: no agent applies them, and neither does the hub. The proposal
  shows the two commands, each with Copy: `chflags nouchg <store>/ORG.md`, then `python3 scripts/dream_apply.py --yours`
  in the project's folder, which shows each change, asks for a typed yes, and locks the file again. **Open a terminal
  for it** starts that second command in a terminal in the hub; while the lock is on it says so and stays open for
  you to lift it. The hub never lifts the lock for this.
- **Dismiss** closes the open proposal without applying it (`dream_proposal.py dismiss <name>`). It asks first and says
  what it means: nothing is applied, every item goes to the next dream, none counts as declined. What the kit prints
  is shown.
- Under the switch, Dreams says what closed proposals left, in three groups, sorted by the kit's own word for each
  item (`waiting` in the record) and by nothing else:
  - **Approved, not yet done**, oldest first: you approved it and it waits for you (ORG.md, Steering) or for a session
    (a skill, a scratchpad, an inbox item). It stays through later proposals until it is done or you take it back.
    Each says where it came from, how long ago, and what gets it done, in the kit's sentence; one whose proposal or
    record is gone says that nothing can do it any more. **Open a terminal for it** or **Start a session for it**
    (`/dream apply`, which does these with or without an open proposal) does it; **Take back** runs
    `dream_proposal.py withdraw` and shows the kit's answer. They can't be ticked again.
  - **Wait for the next dream**: not ticked, refused by the store, or in a proposal you dismissed.
  - **Declined**: passed over twice when a proposal was applied, so no dream proposes them again.
  An item is known by its proposal and its id, never by its number: scratchpad and inbox items have none. **May be proposed again** on a declined item
  runs `dream_proposal.py forget` for it and shows the kit's answer.
- **Dream now** first asks the kit who is dreaming (`dream_owner.py`) and which proposal is open (`dream_proposal.py`).
  If a dream is alive or a proposal is open, it shows that sentence and starts nothing. A dream that holds the project
  is also said on the Dreams page, with **Give it up** (`dream_owner.py release`), which asks first and shows what the
  kit discarded.
- What the kit's `memcheck.py` finds wrong with the store is listed on Dreams: a record of proposals it can't read, a
  proposal no dream finished, writes around the protocol. The hub had no place for these before.

A proposal reads as a code review. Its totals (proposed, ticked, facts carried) stay at the top while you scroll.
Changes are grouped by the file they change, in the order the dream wrote them, each group with its ticks and
**Viewed**: a viewed file folds, and viewed is kept in this browser for that proposal (`hub.viewed`). Under each
change is one faint line (how often it was seen, what it costs, and once applied what became of it); the dream's why
and its evidence are behind the chevron that starts the line. Apply and Dismiss stay docked at the bottom. What needs
you sits above the proposals: three at a time, then "more", with its buttons at the row's edge.

A proposal is read in the shape the kit's `/dream` writes it. Under each change:

- an **edit** shows the line it replaces, struck through, under the line that comes. The `replaces:` line is taken whole
- a **merge** shows the one line that stays and the opening words of the lines it stands for
- a **split** shows each new file and the lines that move there
- a decision, or an approach that worked, is an added line like any other

- a **pin** (an edit whose two lines differ only by ` (pin)` at the end) shows the line once, with the pin mark and
  "Pin" or "Unpin" in place of the struck-through line

Two sections sit beside the memory changes. Ticks in **ORG.md and Steering** are text only you change: applying leaves
them for you (see Yours to apply). **Claude's own notes** come from the notes Claude Code keeps by itself for a folder.
There, a carry item moves the checked facts of one note into memory, and each fact has its own switch: off turns its
`+` into a `-` in the proposal, so that fact is left out when the item is applied. That one character is all the hub
writes, on the open proposal only, refused if the file changed since you saw it (as a tick is). The kit reads every
sign as `+` when it names the item (`item_id`, mirrored in `hub_kit.py`), so switching a fact keeps the item the dream
wrote. Once applied, each fact says what the kit did with it (the `parts` of its row): written, already there,
refused, left out. **Unchecked facts from Claude's own notes** are ordinary add items nothing could check: your tick is
the check, and the hub never ticks one for you. Older proposals list the notes left behind as "Not carried over".

**Needs you.** What a dream found that needs you and isn't memory (a bug, a README to fix, a question only you can
answer) is kept by the kit in `dreams/needs.json` until you close it. Dreams lists each one at the top, with the
proposal that said it, the evidence and who can put it right: an agent, in which repository and what to change; only
you, and why; or not sorted (said before dreams said who). The homepage counts the ones that wait for you per project.
One an agent can fix, or one not sorted, has **Approve fix** and **Reject**; one that is yours has **Done** and
**Reject**. Each runs the kit's `dream_proposal.py approve|reject|done "<its words>"` and shows what the kit said, and
each is yours alone, like the rest of the person's tier. After that the row says what became of it, in plain words:
"Approved. The fixer runs at 16:00" (two hours before the dream), "Being fixed", "Fixed: …, merged into main" or
"Fixed on branch fix/…, not merged: <why>", "Stopped: <why>" (with **Approve again**). A rejected one leaves the list,
and no dream says it again; a done one too, until a dream sees it again. **Run fixes now** starts the kit's
`run-fix.sh` for what is approved, in a terminal of its own (`hub-fix-<project>`); the fixer is described in the kit's
README. The hub never writes the file, and never puts a tick box on these. In a proposal, its "Needs you" section shows only what isn't
listed at the top: lines closed since, and the ones a dream found put right.

**Read and not proposed.** Proposals written since 12 November 2026 have a file beside them, `<stem>-notes.md`, that
the dream writes and the kit commits with the proposal: each of Claude's own notes with its counts, what was stale,
what could not be checked, what was checked on this machine, what was turned away. It is shown, read only, at the
end of the proposal. It is not a proposal and is never listed as one.

**Pins.** A pinned entry is a line of `project/*.md` that ends ` (pin)`, at most 8 per store. Memory lists them under
**Pinned**, by title (no date, no suffix), and marks them in the file. Only a dream's edit that you tick adds or
removes one: the hub's editor refuses an ORG.md save that would change a pin.

While a folder of a project has such notes and Claude Code still keeps them, the project's page lists "Move Claude's own
notes into memory" under Finish setting up. Whether it still keeps them, and where, is the kit's rule and nobody
else's: the hub runs the kit's `scripts/own_notes.py` and reads its answer (managed settings, the folder's local and
shared settings, then your own; the `CLAUDE_CODE_DISABLE_AUTO_MEMORY` switch in an `env` block before
`autoMemoryEnabled`; on by default). The answer is kept until a file it rests on changes, and for a minute at most. An
index file with nothing in it isn't a note. Dreams says what is left to do: dream, then tick and apply, then run the
kit's `retire-auto-memory.sh <store>`, after which the row goes.

A dream job that can't be read shows no timing, and when the kit can't answer about the notes the row is left out. Each
is logged once per change of the file, and the other projects are unaffected.

**The change log.** Where the hub shows a memory write (a file's history in Memory, the activity lists), an edit shows
the line before and after and a removal the line that went. The kit packs those into the log row; its own
`memwrite.change` takes them apart, through `hub_kit.py`, and the hub never splits that text itself.

## Live status and review

**How fresh it is.** While a page is open, the server keeps the state itself (`hub_push.py`). Four times a second it
looks at what is cheap to read: each tmux window's last output (`#{window_activity}`) and the files the hooks, the hub
and Claude write. When something moved it recomputes the sessions with the same functions `/api/state` uses, but
captures again only the panes that printed since their last capture; the process table is reused for 2 seconds.
Projects, which cost more, are recomputed beside it every 3 seconds, as the poll did, and after any write. Each open page gets what
changed over `GET /api/stream` (Server-Sent Events): the whole state once, then only the rows and parts that changed,
and a ping at least every 10 seconds. So a change reaches the page in about a quarter of a second, where the poll took
up to 4.5. A pane that keeps printing (a spinner, a build) recomputes at most every 0.4 seconds; hook events and a pane
that was quiet, at once. Measured with 31 sessions: a recompute takes about 60 ms where the whole state took about 330.

The 3-second poll stays as the fallback. While the stream is heard from it runs every other turn only, as a check, and
the server answers it from the loop's state rather than computing one. A stream that errors is opened again
by the browser after 2 seconds, or by the page with a growing wait; a missed step, or a page that falls 64 messages
behind, starts over from a whole state. A phone suspends the page in the background: back in view, a stream not heard
from in 15 seconds is opened again and a poll fills the gap at once. With no page open, the loop does nothing.
`/api/state` answers from the loop's state while it is fresh, and never from one older than the last write.

**Terminals.** A terminal draws with xterm.js's WebGL renderer (`ui/vendor/addon-webgl.js`, the release that matches
the vendored xterm.js 5.5), and falls back to the DOM renderer where there is no WebGL 2 or when the browser takes the
context back; the setting `term_renderer` set to `"dom"` keeps it there. Output is handed to the terminal once a frame,
however many pieces it came in. A tab hidden for 2 minutes (`term_park_after`, in seconds) closes its terminals'
sockets, so the server stops sending what nobody sees; back in view each connects again at once, and tmux draws the
screen as it is. When tmux copies a selection (OSC 52) or the browser copies one, the pane says **Copied**, quietly, in
its corner.

Each session in `/api/state` carries what it is doing now. The hook (`hub_event.py`) records the tool that starts
and ends, the turn's start, a compaction and an API failure in the session's event file; the rest is read from the
transcript (from where the last poll stopped), git and lsof. git and lsof run in the background and the poll takes
their last answer, so a slow folder never slows the page. Fields that can't be known are null, never "working".

```
s.activity  {tool, target, since} | null   the tool running now, or the last one this turn (target: a path from the
                                           session's folder, a command, a pattern, a page)
s.turn      {since} | null                 when the current turn started; only while working
s.orb       working | reasoning | searching | using | compacting | waiting | idle | retrying
            reasoning between tools, searching for a read or search tool, using for any other, retrying while the API
            retries and for an error; waiting when it needs you; idle otherwise
s.state     also "error", with s.error: one sentence ("The API stopped this turn: 529 Overloaded.", "Claude stopped
            while it was working, and its process is gone.")
s.context   {used, limit} | null           tokens in the last reply's usage; 1M for current models, 200K for Haiku 4.5 and older
s.changes   {added, removed, files} | null against the last commit, staged or not, new files' lines included
s.ports     [int]                          what processes in the session's pane listen on (not Claude, not its shell)
s.retry     {said, attempt, of}            only while the API is retrying
```

**Is it alive.** A Claude session runs under its pane's `zsh -c "claude …; exec zsh -l"` (tmux runs it in its default shell). Once the shell has taken the
pane over, Claude is gone; if the hooks last said it was working or asking, that is an error, not "working". Esc stops
a turn without the Stop hook, so a "working" the hooks left behind is checked against Claude's own status file
(`~/.claude/sessions/<pid>.json`): idle since after the last event, with nothing on screen still running or asking,
reads as finished. **Clear** marks the error seen; the session reads idle again (or "Claude isn't running").

**The pane strip.** At each Claude pane's foot: orb · tool · target · the turn's time · `esc` Stop (sends Esc). It
says Needs you with the question, Asks you with the question a finished turn ends on, Error with its sentence and Clear, Idle otherwise, and keeps its height so the
terminal never resizes as turns start and end. The header's dot stands down while the strip shows.

**The right panel's rail.** Changes (`+42 −7 · 5 files`, opening the review), Context (a meter, its share of the window)
and Ports, each with Open (on this host, in a new tab) and Stop. Stop asks first, then stops only processes in that
session's pane: never Claude, its shell, this hub, or another session's process; anything else is refused.

**The review.** Over the session's panes: the files on the left, every diff in one scroll, **Viewed** per file (kept
in the browser until the file changes again). git is read only: `diff`, `--numstat`, `ls-files` and `rev-parse`, with
no optional locks, no external diff or textconv driver and no fsmonitor. A file is shown only if git lists it as
changed; a path from the page must be one of those, and git internals, keys and dotenv files are listed by name with no
content. Click a line number (or the **+** beside a line) to comment; **Send N comments** pastes them into the
session as one message, `path:line`, the line quoted, your words, the way Close sends its prompt.

**Peek.** `window.hubPeek(id)` (Space on a sidebar row) opens a popover beside the row, or a sheet on a phone: the
last reply, the choice Claude is showing (in the panel described under **Choices**), or the error with Clear. ↵ sends
the reply box as one paste; a number key answers a numbered question in a reply with the number as the reply. It refuses to paste while something is typed in the session, and a grey suggestion in Claude's input isn't
taken for typing (`typed_now` reads the screen with its colours).

**Choices.** Whatever Claude shows to be answered is read off its screen (`dialog_in` and `menu_dialog` in
`hub_status.py`, with the screen's colours from `capture-pane -e`) and drawn by one panel (`questionPanel` in
`ui/app.js`), in the chat and in a peek:

- AskUserQuestion: its questions as steps (answered ones ticked, the open one marked, "Question 2 of 3"); a step or
  ←/→ opens another. A single choice is a radio group: a tap or its digit picks and moves on. A multiple choice is a
  group of checkboxes ticked here, then sent with **Next** (or **Submit**) at once. Each option's description is
  its second line, never part of its label. "Type something" is a text field, "Chat about this" a quiet link below.
  The last step lists every answer as Claude has it, with **Submit answers** and **Cancel**.
- A permission prompt shows what it would run (the command or the diff) and its options; a field below sends **No**
  with words for Claude (Tab to amend, in the terminal). A plan to approve shows the plan, its options, and
  "Tell Claude what to change" as a field. A picker shows each row's description; a menu without numbers (trust this
  folder) is a row per choice.
- At a desk digits choose (or tick), ↑/↓ move, ←/→ change question, ↵ sends; on a phone every target is 44 px or more.

`POST /api/sessions/<id>/answer` presses the keys a person would and reads the screen after each: `{"choice": n}`
(its digit, or ↑/↓ and Enter where a digit would be typed into a text row or can't reach it), `{"choice": n, "text":
"…"}` (the cursor to that row, Tab first for a permission's Yes or No, `C-e C-u` to clear what was there, the words as
one bracketed paste, then Enter once the screen shows them), `{"picks": [n…], "text": "…", "next": true}` (only the
boxes that differ are toggled, then the typed row, then Next), `{"step": i}` (←/→, off a text row first, where they
would move the caret) and `{"row": i}` (an unnumbered row, then Enter). What it sends is refused when the screen
no longer shows that choice. The dialog in `/peek` keeps `question` and `options[].n/.label`, and adds `kind`
(question, review, permission, plan, choice, menu), `steps`/`step`, `multi`, `options[].description/.checked/
.text/.value/.apart/.row`, `text_option`, `next`, `rows`, `cursor`, `review`, `warning` and `detail`.

## What a session shares

Links and file paths on screen are clickable, including ones wrapped across two rows. In the chat they show inside the conversation (see The chat). Paste or drop a file into a
terminal to share it with Claude.

**The viewer.** Everything a session shares opens in one dark, full-screen frame, with the file's name, time and size
at the top left. An image fits the screen; `+` `-` (or the buttons, a pinch, ⌘-scroll) zoom, `0` fits and `1` is actual
size, a drag pans, a double-click zooms where you clicked, and past 200% the pixels stay square so you can check
alignment. ←/→ (or a swipe on a phone) and the filmstrip move through all of the session's images, whether you opened
one from the terminal, the Shared panel, a pasted image in a record, or the picture that pops up when a new one
arrives. Video, audio, PDFs and text (with line numbers) open in the same frame. `esc` closes it.

**Hover cards.** Resting the pointer on a path in a terminal shows what it is: an image's picture, size and pixels; a
text file's lines, size and first lines; when it changed and where it lives. Resting on a link shows its card: title,
description, site and picture, as the page describes itself.

**The Shared panel** lists the chat's images, files, audio and links, read from the transcript, as a timeline, newest
first: one time per turn, images as a row of thumbnails (small copies made once with `sips` and kept under the hub's
state folder), the rest one row each. A link shows its title and icon once its card has been fetched.

Only a session's project, its uploads, the Claude scratch space, Downloads and Desktop can be opened, never keys, dotenv
files or git internals. Local files open sandboxed.

**Remote images and links.** The page never loads anything from the web: its policy is `img-src 'self' data:`, because a
chat could otherwise send data out through an image address. Clicking a link opens it in a new tab. A link's card is
fetched by the hub (`hub_preview.py`), and only when you rest the pointer on that link (350 ms) or focus it: never
because a link appeared in a transcript, and never for the list in the Shared panel, which only asks the hub which
cards it already has (`/api/preview/cached`, which fetches nothing). The card's picture and icon come through the hub
too (`/api/preview/image`), and only pictures a fetched card named. Every fetch, at every hop of a redirect, keeps to:

- http and https only, on ports 80, 443, 8080 and 8443, with no name or password in the address;
- the name is resolved by the hub and every address it gives must be public: nothing on this Mac (loopback), the home
  network (private ranges), link-local (cloud metadata), multicast, reserved space or the tailnet's `100.64.0.0/10`,
  IPv4 hidden in IPv6 included. The connection goes to the address that was checked, so a second lookup can't swap one in;
- two seconds for the whole fetch, at most 512 KB read (a page is read up to that point; a bigger picture is refused),
  web pages only for a card, and PNG, JPEG, GIF, WebP and ICO pictures checked by their first bytes (never SVG);
- no cookies, no referrer, and a User-Agent (`Mozilla/5.0 (compatible; LinkPreview)`) that names no one.

Cards are kept for a week and refusals for ten minutes, under `previews/` in the hub's state folder. A request for a
card from another site in the browser (`Sec-Fetch-Site: cross-site`) is refused. A card does still tell the page's
owner that your Mac looked at that address, once, when you pointed at it.

## Artifacts

Everything a session made that you'd want to look at, opened in the hub (Settings › Features › **Artifacts**; off, the
hub is as it was). `#/s/<id>/artifacts` lists a session's, `#/p/<project>/artifacts` (the project's **Artifacts** tab)
every session's in the project, and the side panel has the same list. The session's right panel links to it:
**Everything it made**. `hub_artifacts.py` is the server's half.

**What counts.** Read from the transcript and its subagents', newest first: files it wrote (Write, Edit, MultiEdit,
NotebookEdit); files a shell command wrote, when the command says so (`>`, `>>`, `-o`, `--output`, `tee`, the target of
`cp` or `mv`, after a leading `cd`) and the file changed after the command started; files handed over with
`SendUserFile`; pages, pictures, media and data it named in what it said, inside its folders; and pages it published:
a claude.ai artifact, a deploy on a known host (Vercel, Netlify, Cloudflare Pages, GitHub Pages and the like), or a
URL a tool with deploy, publish or artifact in its name answered with. A file is one row, at its latest version, with
how many times it was written; only while it is still there; never a key, dotenv or `.git` file. A project's list
merges its sessions' and names the session each came from.

**The viewer.** A list with each kind's mark, the name, where it is, and how long ago; filter by kind or by typing.
Beside it, at a desk, the one picked: an HTML page in a sandboxed frame, markdown in the hub's own type, pictures
(the hub's zoom viewer on a double-click or Zoom), SVG only as a picture, PDFs in the browser's viewer, video and audio
with their players, CSV and TSV as a table, JSON and JSONL as a tree that folds, code with line numbers and light
highlighting, other text as text, and a published link as its card. Its actions: open in a new tab, download, copy the
path (or link), **Show in chat** (the session's conversation, opened at the latest turn that made it, lit for a moment)
and, for a page while the browser is on, open it there. ↑/↓ (or j/k) move and show, ↵ moves into the viewer, Esc goes
back. On a phone and in the side panel it is one column: the list, then the one picked full screen with a back button;
the phone's own back works too, since the pick is in the hash. While the page is open the list is read again when a
session moves (the push stream) and every few seconds besides, and the file on show reloads when it changed on disk,
saying **Updated**.

**Safety.** A file's bytes come from `/api/sessions/<id>/raw/<its absolute path>`, and only when the session listed it
or it is inside the session's own folders (the project's folders, the session's folder or worktree, its uploads): no
`..` or `.` segment, no secret-looking name, no folder the hub never serves, at most 200 MB, read in ranges. Text for the
viewer is at most 2 MB, and says when it was cut. Each answer has its own type and `nosniff`. An HTML page comes with
`Content-Security-Policy: sandbox allow-scripts allow-popups allow-downloads allow-modals` (never allow-same-origin),
`connect-src 'none'`, `form-action 'none'` and `frame-ancestors 'self'`, and the viewer's frame has the same sandbox:
the page runs in an opaque origin of its own, even opened in a tab, and can load its own folder's pictures and styles
and web assets but can't fetch anything. Everything else is sandboxed with no script. The hub refuses every other
`/api` request that comes from such a page or another site (`Origin: null`, or `Sec-Fetch-Site` cross-site or
same-site), so nothing a session made can read the state or type into a terminal. On a hub with a key instead of a
login (this Mac only), the hub's cookie stays with the hub's own pages, so a page's own pictures don't load in the frame.

## Remote Control

A session's title is `<project> · <title>`, in the hub and in Claude: every Claude session starts with
`claude --name "<title>" --remote-control "<title>"`, so the Claude app's Remote Control list, the `/resume` picker,
the terminal title and the hub all say which project a session belongs to. The project is its display name (`Hub` for
hub sessions); a title that already starts with it, like `my-app 9484`, is used as it is, and the name is cut to 60
characters. A rename gets the project in front too. Where the project is said just before the title (the session's row
under its project in the sidebar, the crumb after the project's) the title leaves it out. Resume and **Connect phone** use the same name, and a rename sends `/rename` to a running session. The phone link comes from
`bridgeSessionId` in `~/.claude/sessions/<pid>.json`, a Claude Code file with no documented format, so a future
version could move it. If a session isn't connected, its title bar shows **Connect phone**.

**Code Mode** (the checkbox beside the worktree one in More options) starts a project session with
`CLAUDE_CODE_EXPERIMENTAL_CODE_MODE=1` in its environment, Claude Code's switch for its experimental
[Code Mode](https://code.claude.com/docs/en/code-mode). Code Mode refuses to start with Remote Control, so such a session
starts without `--remote-control` and can't connect a phone. It's kept in the session's meta, because Claude resumes a
Code Mode session only with the variable set. The first Code Mode session on the Mac asks once, in its terminal, to
confirm. Hub sessions never use it.

Dreams run with `claude -p`, which has no interactive session, so they don't appear on the phone.
**Apply** opens a normal session, which does.

## The browser and the device preview

A session's dev server listens on this Mac's loopback (`localhost:5173`, say). From a phone, "localhost" is the phone,
so the hub brings those pages to you. **Browser** (`#/browser`, `#/browser/<session>`, a session's ports in its right
panel, or ⌘K) has an address bar with back, forward, reload, **Copy link** and **Open in a new tab**. Focus the
address, or open it empty, for one tap to what the session printed (`http://localhost:…` in its screen and transcript)
and its own ports, then every web server of yours listening on loopback (`lsof`, three seconds at most, kept five; each
asked once for its page's title, so a database or Claude Code's own ports aren't offered, nor another hub). Another feature opens an address there with `hubBrowser.open({url})`, or `#/browser/<address>`. It keeps
the last address per session in this browser. A server that isn't running gets a card that says so and opens the page
once it starts. An https site is framed as it is when it allows that; one that refuses (`X-Frame-Options`, or
`frame-ancestors`, read by the hub under the link cards' guards) gets **Open in a new tab** instead of a blank frame.

**Device preview** (`#/preview`) shows the same page in an iPhone (390 × 844), a small phone (375 × 667), an iPad
(820 × 1180), a laptop (1440 × 900) or a size of your own, side by side at a desk, all at one scale that fits (or at
100%, to scroll), each with its own rotate and reload, and **Reload all**. The devices keep in step: a link followed in
one is followed in all. On a phone it is one device at a time, with a picker. Both are side panels too
(`addPanel`, ids `browser` and `preview`), and each has its switch in Settings › Features (`feature_browser`,
`feature_preview`). Off, nothing of them is left: no route, panel, Go to entry or Health row, the session's ports open
`http://<host>:<port>` in a new tab as before, the API answers 404 and the hub's page has its old policy, word for word.

**How a page gets to you.** The pages come through a second listener of the hub's, on its own port
(`HUB_PREVIEW_PORT`, the hub's port + 1), which is a different origin from the hub's: a page there can never call the
hub's `/api` or open a terminal, and the hub refuses any API request from it (its Origin, or `Sec-Fetch-Site` other
than same-origin). The listener runs while either switch is on and stops when both are off.

- The hub page asks the hub for a ticket for one port (`GET /api/browser/ticket?port=`): signed with a secret made at
  each start, for two minutes, for that port only. The frame opens `/__hub/go?port=&path=&t=` on the listener, which
  sets two HttpOnly cookies, a pass (who you are, twelve hours) and the port, and redirects to the path. Every request
  at the root then goes to that port, so the app runs at `/` as it does on localhost: its router, its absolute links
  and its hot reload work unchanged.
- `/p/<port>/<path>` does the same for an address typed or pasted into a browser's own bar (`Sec-Fetch-Site: none`),
  which is the link **Copy link** gives. A page can't move the listener to another port: only a ticket or your own
  typing can.
- The owner check is the hub's: the Host must be the hub's host, this Mac's loopback or `localhost`; then the
  `Tailscale-User-Login`, or in a key-only hub the key's cookie, or the pass. Writes and WebSockets must come from the
  preview's own origin, and another site can't pull from it.
- Only `127.0.0.1` and `::1` are proxied, on any port but the hub's own (this hub's port and listener, the installed
  hub's and its listener's). There is no way to name a host.
- To the dev server, a request comes from `localhost:<port>`: its Host, Origin and Referer say so, and the hub's
  cookies and your login never reach it. Back come redirects to its own address (kept in the preview; to another
  loopback port, through a ticket the listener signs), its cookies without `Domain` (so they behave as on localhost,
  where every port already shares one set of cookies), its body streamed as it comes (large files, server-sent events),
  and WebSocket upgrades, piped both ways, which is hot reload. Its own `X-Frame-Options` and `frame-ancestors` are
  replaced by one that lets only the hub frame it. A page asked for as a document comes plain, and a small helper goes
  in after its doctype: it tells the hub the page's address and title, and goes back, forward or reloads when asked.
- One port at a time per browser: opening another port moves every frame of that browser there, and a frame left on
  the old one says so, with Reload.

**On the phone, once.** The listener is on loopback like the hub, so Tailscale has to serve it, one time, on the Mac:

    tailscale serve --bg --https=<preview port> http://127.0.0.1:<preview port>

with `<preview port>` your hub's port + 1 (8492 for the installed hub on 8491), or your `HUB_PREVIEW_PORT`. The hub
never runs it. Until it is done, Settings › Health says the phone can't reach the preview yet, with this command built
from your config, and the browser on a phone says the same in place of a page. At a desk on this Mac the browser works
before that: when the hub's own address for the preview doesn't answer, it uses the listener's loopback address, its
pass kept as a partitioned cookie (Chrome; Safari keeps no cookie for another site's frame, so add the mapping there).
A dev app's own sign-in cookies may not stick in that frame either; with the mapping they do.

## Settings

The gear at the foot of the sidebar (or ⌘K, Settings) opens one page, a section at a time: Appearance,
Notifications & sound, New sessions, Sidebar & navigation, Dream Catcher, Keyboard, Health, Access and About. On a
phone the sections are a row to swipe above the page.

What is set there is the same on every device: it is kept in `config.json` under `"settings"`, and only there. Each
setting is named in `SCHEMA` in `hub_settings.py`, with its kind, its choices or range, its default and the words the
page shows; the page is built from it. `GET /api/settings` gives `{values, schema, defaults}`, `PUT /api/settings`
takes the names to change. A write checks every value against the schema (an unknown name is refused with a
did-you-mean), changes the `"settings"` key and nothing else, keeps the file's other keys and indentation, and
replaces the file whole at mode 600. `login`, `origin`, `port` and `key` are never read or written there: Access shows
the first three, and install.sh changes them. The file is read again whenever it changes, so a change made on the page
or by hand applies at once.

In the page every control saves as soon as it changes and says Saved beside itself, or why not. The page fills
`SETTINGS` and fires `hub:settings` on `window` after each change; every feature reads its own setting with
`pref(name, fallback)`, the fallback being what it did before there were settings. Appearance previews as a slider
moves or a colour is pointed at, and Cancel changes puts back what it was when you opened the section.

New sessions: a project keeps the mode, model, effort and Code Mode its last session started with, on the server
(`<state>/projects/<name>.start.json`), and that wins. Where a project has none, the composer starts from the defaults
in Settings, and where those are empty, from what the browser remembered before. A start that names nothing (a
script, Open Claude) takes the defaults on the server. **Use these everywhere** makes every project forget its own
choice. The model list there replaces the built-in one in every picker; a session can start with any model in it.

The Dream Catcher's switch is kept in its own file, `<state>/dream-catcher/settings.json`, as its page writes it;
Settings writes the same file, so there is one switch. `"dream_catcher_auto"` at the top of the config is only the
starting point before the switch is first used, and Health says when the two disagree.

Health lists what is wrong with the config and whether Claude Code, tmux, the hub's hooks, the kit and the launchd job
are in place, each with a fix. `python3 hub/server.py --check` prints the same in a terminal and exits 1 when
something is wrong. About shows the version and the branch followed, checks for updates, and lists what changed since
the version you last saw; after an update a banner offers it once.

Home shows a small checklist the first time the hub finds no settings, until you dismiss it.

## Access

The terminal is full shell access. The server only listens on 127.0.0.1. `~/.config/agent-hub/config.json` (mode 600,
written by `install.sh`) says how it is reached, in one of two ways:

- **On this Mac only** (`"key"`, no `"login"`): open `<origin>/?key=<key>` once; the hub answers with a cookie that
  holds the key (HttpOnly, SameSite=Strict, this origin only) and from then on every request needs it, the app's Host,
  and for writes and terminals the app's exact Origin. Anyone who can read the config file, or open the key's address
  from this browser's history, can get in: treat the key like a password, and run `sh install.sh --new-key` to change it.
- **Behind Tailscale Serve** (`"login"`): Tailscale Serve is the only way in, from your other devices too. Every
  request needs the owner's `Tailscale-User-Login`, the app's Host, and for writes and terminals the app's exact
  Origin.

Either way, programs already running on this Mac as you can reach loopback and read the config, as they could use your
shell anyway. Other accounts on the same Mac can reach loopback too; the key (or the login) is what keeps them out.

**What the owner check protects against, and what it doesn't.** Every request needs three values: the owner's login
(or the key), the app's Host, and for writes the app's Origin. That keeps out other people on the tailnet and other
sites in your browser. It does not keep out a program running as you on this Mac: the three values sit in
`~/.config/agent-hub/config.json`, which any such program can read, so an agent session here could call the hub with
`curl` and do what the kit keeps agents from doing directly: save `ORG.md`, dismiss a proposal, take back or re-allow
an item, give up a dream. A header can't tell you from a program running as you, and the hub doesn't pretend to with a
secret the same program could read. What it does instead:

- Everything done through the hub that only you may do is written down (`person-actions.jsonl` in the hub's state
  folder) with the time and the store commit it left, and Dreams lists **Done in your name** from the store's own
  history, marking what came through the hub. A line you don't recognise is how you would notice.
- An `ORG.md` save is sealed by the kit (`memcheck.py --seal`: a log row and a commit under the store's lock). If the
  kit can't seal it, the file is put back and you are told. If principles are ever left unlocked, the kit's check
  says so on Dreams.
- One function, `the_person` in `hub_data.py`, is asked before each of these. Today it decides nothing more than the
  three values already did. A real proof that you are there (a password, Touch ID) goes in that one place.

**Repos the hub never runs git or jj in.** `NO_VCS` in `hub_base.py` is the config's `"no_vcs"` list: repos that
aren't only yours, such as a partner's repo where the kit's files stay untracked on purpose, or a shared company
monorepo (each a path from the home folder, or a whole path). Every git call the hub makes goes through `run` in `hub_base.py` or `git` in `hub_diff.py`, and both refuse
one aimed at those folders or anything inside them, so nothing is committed there and no worktree is made there. Their
sessions show no Changes, the project page shows no git log for them, "Commit the kit" is never offered, and a
session of its own (which needs a worktree) is refused with a sentence. Writing a file there, such as Steering, is
still the hub's to do. `tests/guards_check.py` checks this offline.

**Steering in a store with several repos.** The Steering block lives in `.claude/commands/dream.md` of every repo of a
store and must be the same in each. A save writes all of them or none: every file is read first (it must be there,
its block must be the one you opened, and the blocks must agree), the new files are written beside the old ones,
then swapped in, and if a swap fails the ones already swapped go back. Blocks that differ between repos are refused
rather than overwritten.

## What stays manual

- Answering Claude's first-run questions in a new folder (trust, MCP servers). The session shows as needing you.
- Writing `ORG.md` and Steering.
- Ticking a proposal's changes.
- Applying approved `ORG.md` and Steering changes: lifting the lock and running the kit's `dream_apply.py --yours`.
- Running `retire-auto-memory.sh` once a dream has carried Claude's own notes over.
- Merging a worktree's branch. The hub shows when it is merged and then cleans it up; it never merges.

## Deploying a new version

- Restart the server: `launchctl kickstart -k gui/$(id -u)/ai.agent-hub`.
- Open tabs are told. Each poll carries the build the server runs; a page from an earlier build shows "Dream Hub was
  updated" with **Reload**. Until it is reloaded it may show what the new server no longer accepts, and get a refusal.
- Proposals from before the kit kept a record are not in the kit's record. They are listed on Dreams under **Earlier**, to read; nothing in them can be ticked or applied.
- Deploy the kit first, or together: without the kit's `dream_proposal.py` and `own_notes.py` the hub says so in
  place of the proposals and leaves the "Claude's own notes" row out.

## Tests

`tests/dialog_check.py` is offline too: it reads the screens in `tests/screens/`, captured from real Claude Code panes,
and checks every kind of choice above. `tests/detect_check.py` is offline: from the same screens it checks how a state
is decided, that a finished reply quoting "trust this folder", "Enter to confirm" or "esc to interrupt" reads as done,
and how a finish is held. `tests/restart_check.py` (why, asks, `asks_as_needs`, `alive_at`, a restart and Resume all,
with real sessions) and `tests/detect_browser_check.py <folder>` (the same in the page, desk and phone) need the app. `tests/questions_check.py` answers them for real from the page, at a desk and
on a phone, in headless Chrome. `tests/guards_check.py`, `tests/media_check.py` and `tests/catcher_check.py` are offline: no server, no Claude session (`/usr/bin/python3 tests/guards_check.py`, with the
six variables of a second instance set). `media_check.py` feeds made-up transcript lines for every way a picture, video,
recording or PDF reaches a chat to the chat builder, and checks what it may and may not show. The others need the app running, and start real, short Claude sessions (which
cost usage and also appear on the phone while they run).

    /usr/bin/python3 tests/test_hub.py
    /usr/bin/python3 tests/browser_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/lifecycle_check.py
    /usr/bin/python3 tests/status_check.py
    /usr/bin/python3 tests/media_browser_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/questions_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/split_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/worktrees_check.py
    /usr/bin/python3 tests/worktrees_browser_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/settings_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/navigation_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/theme_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/push_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/artifacts_check.py
    /usr/bin/python3 tests/artifacts_browser_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/preview_proxy_check.py
    /usr/bin/python3 tests/preview_browser_check.py <folder-for-screenshots>
    /usr/bin/python3 tests/terminal_check.py <folder-for-screenshots>

They run only against a second instance: all six variables, with `HUB_JOBS` a throwaway folder and a port, state
folder and tmux socket that are not the installed hub's (`tests/instance.py` compares the folders as they really are,
and stops with a sentence otherwise). Start one as above and run them with the same variables:

    export HUB_PORT=8492 HUB_STATE=/tmp/hub2/state HUB_TMUX=agent-hub-2 HUB_CONFIG=/tmp/hub2/config.json HUB_KIT=$(cd ../agent-memory-kit && pwd) HUB_JOBS=/tmp/hub2/jobs
    /usr/bin/python3 tests/test_hub.py

Each makes a throwaway project, `hub-test-throwaway-<pid>` (a folder in your projects folder, a store in `~/agent-memory`),
works in it and removes it, along with what the kit and Claude Code kept for it, whether or not the server is still
answering. The store holds a note, `THROWAWAY-TEST-STORE.md`, saying what it is. These can't live anywhere else: the
kit makes every store in `~/agent-memory`, and the Claude sessions the tests start need the real home folder to be
signed in. So don't sync the kit into a store of that name while a test runs. `/usr/bin/python3 tests/sweep.py` removes
the ones whose test run is no longer going, and says which; each test script does the same when it starts, and ends by checking that
launchd's folder holds what it held before: no test makes a dream job there. Dream jobs are written by the tests into
the instance's own folder. The project's alert script is swapped for one that sends nothing, so a test dream never
reaches a phone.

Dreams, proposals and their states are made by the kit's own scripts in the throwaway project: its collector and
`dream_finish.py` (with the proposal's text supplied in place of the model's), `dream_apply.py`, its `--yours` pass in a
hub terminal, `dream_proposal.py applied`, the hub's own Dismiss, and `dream_due.py`. A prompt goes to a session as one
paste, the way the hub's own Close does, because typed keys that long arrive as a paste and Claude keeps only the tail. No test asks a real project or store for anything. Claude Code's
own entry for the throwaway folder in `~/.claude.json` is left, because that file isn't the hub's to edit.

`status_check.py` checks every field above against real sessions (a tool running, a turn finishing, an API failure, a
killed Claude), the review's path guards, Stop's reach, peek's answers and review comments; its first block reads screens
and patches without a session. `browser_check.py` opens the origin in the instance's config in headless Chrome and adds the owner's login header
itself, as Tailscale Serve does for a hub behind it. It needs Google Chrome in `/Applications`. `split_check.py` drags sessions into
splits with real pointer events (halves, a nested column, a swap, the split's edge, a fifth refused, Esc), sizes the
gutters by mouse and keys over a reload, opens an old `a,b,c,d` link, uses each pane's menu, checks a phone's switcher
and shut panel, and closes a real Haiku session with "Commit them first", checking the commit, the Committed line and the notice. `navigation_check.py` presses the prefix inside real terminals (n, l, j, k, directions,
swap, zoom, ⇧1 for a board) and checks no key reaches a shell, zooms over a reload, opens six panes on a wide screen,
saves, opens and deletes a board, searches Go to (and times it over 300 sessions), and uses a phone's search button and
alert bar Next; what each session is doing is laid over `/api/state` in the page, so it starts no Claude.

`push_check.py` checks the screen cache in process (a pane is captured again exactly when it printed, even within the
same second), the stream (owner only, the whole state then diffs that add up to `/api/state`, a start and a rename
within a second, pings), the page (it follows the stream, its poll slows, a dead stream comes back) and the terminal
(the DOM renderer without WebGL and the WebGL one with it, output written once a frame, a socket let go in a hidden tab
and back on return, the Copied note), with plain terminals only.

`preview_proxy_check.py` checks the preview listener over the wire against a small dev server it starts on loopback
(`tests/devserver.py`): the owner check, tickets, every port it refuses, pages with their helper, redirects, cookies,
8 MB both chunked and with a length, uploads, a stream, a WebSocket echo, that the hub's API and terminals refuse the
preview's origin, Health's row and command, and that with both switches off the listener stops and the hub's policy is
what it was. `preview_browser_check.py` drives the browser and the device preview in headless Chrome at a desk and on a
phone, with a plain terminal session that prints the dev server's address, a page inside the preview that tries to
reach the hub's API, and both switches turned off and on again live. Set `HUB_PREVIEW_PORT` with the other variables
when the instance's listener isn't on its port + 1.

The link-card guards are tested in `test_hub.py` without the internet: every kind of address the hub refuses, at the
first hop and after a redirect, against a small web server on loopback that the test lets through under one made-up
name only (an oversized page, a non-page, a slow page, a page that trickles, pictures that are too big, SVG or not what
they say).

## Known limits

- One Mac only, and macOS only (launchd, `sips`, `chflags`, `lsof` as macOS ships it).
- Terminal state on a phone browser is workable, but the Claude app through Remote Control is the better phone route.
- Worktrees are made with plain `git worktree add`, because `claude --worktree` didn't get the kit's memory link.
