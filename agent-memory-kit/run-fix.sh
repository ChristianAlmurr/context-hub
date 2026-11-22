#!/bin/sh
# The fixer: what the person approved under "Needs you", put right by Claude, one need at a time, each in a git worktree
# of its own. launchd and Context Hub both start it here, so a failure is never silent.
#   sh agent-memory-kit/run-fix.sh <repo>                 fix what is approved now
#   sh agent-memory-kit/run-fix.sh <repo> --if-approved   the daily job, two hours before the dream: with nothing approved it
#                                                                 stops there, exit 0: no Claude, no alert, and the last log stays as it was
# <repo> is any repository of the store; the needs say which repository each fix is in (scripts/needs.py).
# The store is found as run-dream.sh finds it: through the repo's memory/ link, else its agent-memory.store key.
# It always runs the kit's own scripts, never a repo's copy: scripts/fix.py does the run, fixer.md is what Claude is told.
# It takes the store's run lock, the one run-dream.sh takes, so a fixer and a dream never run together in one store.
# Claude is started with --restricted, its sandbox and the narrowest permissions (scripts/fix.py, settings()), it can write
# no memory (AGENT_MEMORY_PROPOSE_ONLY, as in a dream), and its login is the dream's: ~/.config/agent-memory/oauth-token.
# Log: ~/.local/state/agent-memory/fix-<store>.log. A run that goes wrong alerts through the store's notify.sh.
if_approved=
case $# in
  1) ;;
  2) [ "$2" = --if-approved ] || { echo "unknown option: $2" >&2; exit 2; }; if_approved=1 ;;
  *) echo "usage: run-fix.sh <repo> [--if-approved]" >&2; exit 2 ;;
esac
cd "$1" || exit 2
kit=$(cd "$(dirname "$0")" && pwd -P)
if [ -L memory ] || [ -d memory ]; then
  mem=$(cd memory && pwd -P) || exit 2
else
  mem=$("$kit/bin/amk" where) || exit 2
fi
AGENT_MEMORY_DIR=$mem; export AGENT_MEMORY_DIR
store=$(basename "$mem")
state=$HOME/.local/state/agent-memory
mkdir -p "$state"
log=$state/fix-$store.log
fix() { python3 "$kit/scripts/fix.py" "$@"; }
fail() {
  [ -x "$mem/notify.sh" ] && "$mem/notify.sh" "Fixer failed: $store" "$1"
  echo "fixer failed: $1" >&2
  exit 1
}
count=$(fix count 2>&1) || fail "The fixer could not read what is approved, so nothing was started: $count"
if [ "$count" = 0 ]; then
  echo "nothing approved for the fixer in $store"
  exit 0
fi
# The lock belongs to this open file, so it lasts until this script ends, however it ends.
exec 9>>"$state/$store.run.lock"
other=$(python3 "$kit/scripts/dream_try.py" lock "$$ fixer")  # "fixer" in the lock's file: a dream turned away says the fixer has it
case $? in
  0) ;;
  7) if [ -n "$if_approved" ]; then echo "$other The fixer waits for the next run."; exit 0; fi
     echo "$other Nothing was started." >&2; exit 4 ;;
  *) echo "couldn't take the lock $state/$store.run.lock, so nothing was started" >&2; exit 1 ;;
esac
# A person's dream in a session holds no lock: it owns the store's batch while it shows signs of life. The fixer doesn't
# work beside it either. Asked as a run of its own (AGENT_MEMORY_DREAM_RUN), so the lock this script holds is not counted.
other=$(AGENT_MEMORY_DREAM_RUN="fixer-$$" python3 "$kit/scripts/dream_try.py" running 2>&1)
case $? in
  0) ;;
  4) if [ -n "$if_approved" ]; then echo "$other The fixer waits for the next run."; exit 0; fi
     echo "$other Nothing was started." >&2; exit 4 ;;
  *) fail "It could not be told whether a dream is running, so nothing was started: $other" ;;
esac
token=$HOME/.config/agent-memory/oauth-token
[ -r "$token" ] && CLAUDE_CODE_OAUTH_TOKEN=$(cat "$token") && export CLAUDE_CODE_OAUTH_TOKEN
# Claude doesn't get the lock's file: something it leaves running must not hold the lock after this run.
{ date; fix run 9>&-; echo "exit: $?"; } >"$log" 2>&1
code=$(tail -1 "$log")
case $code in
  "exit: 0") tail -2 "$log" | head -1 ;;
  "exit: 1") tail -2 "$log" | head -1; exit 1 ;;  # fix.py has sent the alert itself, with what went wrong
  *) fail "The fixer's run stopped before its end. Log: $log" ;;
esac
