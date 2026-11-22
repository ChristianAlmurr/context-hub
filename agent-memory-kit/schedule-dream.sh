#!/bin/sh
# Turns a store's dreams on or off. A dream only proposes; each one costs money.
#   sh agent-memory-kit/schedule-dream.sh <repo>            put the store on the one scheduler (once per store)
#   sh agent-memory-kit/schedule-dream.sh <repo> --remove   take it off, and out of any job of its own
#   sh agent-memory-kit/schedule-dream.sh <repo> --hour 18  the way back: a daily job of the store's own, as before
# The scheduler is one launchd job for the machine, ai.agent-memory.scheduler, that runs `amk schedule run` every hour
# (scripts/scheduler.py): a store on it dreams when a dream is due and nobody has been at work in its repositories for a
# while, one store at a time, with the fixer first when the person approved something. The stores on it are listed in
# ~/.config/agent-memory/schedule.json. Putting a store on it takes out the daily jobs an older kit gave it
# (ai.agent-memory.dream.<store> and ai.agent-memory.fix.<store>) only once the scheduler's job is written, checked
# (plutil -lint) and seen loaded (launchctl print), so a mistake never leaves a store with no schedule. A scheduler job
# that is there but not loaded is loaded, whether or not its file changed. A working scheduler is only taken out of
# launchd for a new job that passed the lint; if the new one can't be loaded, the one before is put back and loaded
# again, the store keeps its own jobs, and it says so and exits 1. Running it again changes nothing.
# --remove takes the store off the scheduler and removes its own jobs; the scheduler's job goes when no store is left on it.
# --hour N (0 to 23, or auto) writes the older form instead and takes the store off the scheduler: a job that runs
# run-dream.sh --if-due every day at that hour, and the fixer's job, run-fix.sh --if-approved, two hours before it.
# With auto the store keeps the hour its own job has, and one without a job gets the first hour (evenings first)
# where neither its dream nor its fixer starts beside another store's. Running it over an old weekly job replaces it.
# A store shared by several repos needs one schedule: the run covers every repo in roots.txt.
set -eu
repo=$(cd "$1" && pwd); shift
hour=; remove=
while [ $# -gt 0 ]; do
  case $1 in
    --hour) [ $# -ge 2 ] || { echo "--hour needs a number from 0 to 23" >&2; exit 2; }; hour=$2; [ -n "$hour" ] || hour=-; shift 2 ;;
    --remove) remove=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
kit=$(cd "$(dirname "$0")" && pwd)
if [ -L "$repo/memory" ] || [ -d "$repo/memory" ]; then
  store=$(basename "$(cd "$repo/memory" && pwd -P)")
else
  store=$(basename "$(cd "$repo" && "$kit/bin/amk" where)")
fi
state=$HOME/.local/state/agent-memory
jobs=$HOME/Library/LaunchAgents
label=ai.agent-memory.dream.$store
plist=$jobs/$label.plist
fix_label=ai.agent-memory.fix.$store
fix_plist=$jobs/$fix_label.plist
sched_label=ai.agent-memory.scheduler
sched_plist=$jobs/$sched_label.plist
schedule() { python3 "$kit/scripts/scheduler.py" "$@"; }
# A path may hold & or <, which would end the value or break the file.
xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
# launchd has almost no PATH, so find claude now and pass its folder on.
claude=$(command -v claude || true)
[ -n "$remove" ] || [ -n "$claude" ] || { echo "claude is not on the PATH, so a job could not be told where it is; nothing was changed" >&2; exit 1; }
jobs_path=$(xml "$(dirname "${claude:-/usr/bin/claude}"):/usr/bin:/bin:/usr/sbin:/sbin")
# own_jobs_out: the store's own daily jobs, out of launchd and gone. Says which it took out.
own_jobs_out() {
  for one in "$label" "$fix_label"; do
    if [ -e "$jobs/$one.plist" ]; then
      launchctl bootout "gui/$(id -u)/$one" 2>/dev/null || true
      rm -f "$jobs/$one.plist"
      echo "removed $one, the store's own daily job"
    fi
  done
}
# scheduler_out <stores left on it>: the scheduler's job, out of launchd and gone, when no store is left on it.
scheduler_out() {
  if [ "$1" = 0 ] && [ -e "$sched_plist" ]; then
    launchctl bootout "gui/$(id -u)/$sched_label" 2>/dev/null || true
    rm -f "$sched_plist"
    echo "removed $sched_label: no store is left on it"
  fi
}
if [ -n "$remove" ]; then
  left=$(schedule drop "$store")
  own_jobs_out
  scheduler_out "$left"
  echo "off: $store dreams only when you start one"; exit 0
fi
mkdir -p "$jobs" "$state"
if [ -z "$hour" ]; then
  # The one scheduler. Its job is the same for every store, so it is only written when it is not there or not as it should be.
  # The run a check starts goes on after the check has ended (scheduler.py launch, in a session of its own); AbandonProcessGroup
  # tells launchd too not to end what the check left running.
  new=$(mktemp "$state/scheduler.plist.XXXXXX")
  cat >"$new" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$sched_label</string>
  <key>WorkingDirectory</key><string>$(xml "$HOME")</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$(xml "$kit/bin/amk")</string><string>schedule</string><string>run</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$jobs_path</string>
    <key>HOME</key><string>$(xml "$HOME")</string>
  </dict>
  <key>StartCalendarInterval</key><dict><key>Minute</key><integer>7</integer></dict>
  <key>AbandonProcessGroup</key><true/>
  <key>StandardOutPath</key><string>$(xml "$state/scheduler.log")</string>
  <key>StandardErrorPath</key><string>$(xml "$state/scheduler.log")</string>
</dict></plist>
EOF_PLIST
  if ! problem=$(plutil -lint "$new" 2>&1); then
    rm -f "$new"
    echo "The scheduler's job is not a valid plist, so nothing was changed: $problem" >&2
    exit 1
  fi
  # loaded: whether launchd has the scheduler's job now. Only asked, never changed.
  loaded() { launchctl print "gui/$(id -u)/$sched_label" >/dev/null 2>&1; }
  # unloaded <why>: the scheduler's job could not be loaded. The one before it, if there was one, is back in its place and in
  # launchd; the store is not put on the scheduler and keeps its own daily jobs.
  unloaded() {
    if [ -n "${old:-}" ]; then
      mv "$old" "$sched_plist"
      launchctl bootstrap "gui/$(id -u)" "$sched_plist" 2>/dev/null || true
      back="the job that was there before is back"; loaded || back="the job that was there before is back in its place, but launchd did not load it either"
    else
      rm -f "$sched_plist"; back="there was none before it"
    fi
    echo "The scheduler's job $sched_plist could not be loaded ($1), so $store was not put on it and keeps the jobs it had; $back. Run this again once launchctl works." >&2
    exit 1
  }
  old=
  if cmp -s "$new" "$sched_plist"; then
    rm -f "$new"
    if ! loaded; then  # the job's file is as it should be, but launchd doesn't have it: a bootstrap that failed before, or a logout
      problem=$(launchctl bootstrap "gui/$(id -u)" "$sched_plist" 2>&1) && loaded || {
        echo "The scheduler's job $sched_plist is there but could not be loaded (${problem:-launchd does not have it after it was loaded}), so $store was not put on it and keeps the jobs it had. Run this again once launchctl works." >&2
        exit 1; }
    fi
  else
    chmod 644 "$new"
    if [ -e "$sched_plist" ]; then
      old=$(mktemp "$state/scheduler.plist.before.XXXXXX")
      cp -p "$sched_plist" "$old"
    fi
    # Only now, with the new job checked and in hand, is a working scheduler taken out of launchd.
    if loaded; then launchctl bootout "gui/$(id -u)/$sched_label" 2>/dev/null || true; fi
    mv "$new" "$sched_plist"
    problem=$(launchctl bootstrap "gui/$(id -u)" "$sched_plist" 2>&1) || unloaded "$problem"
    loaded || unloaded "launchd does not have it after it was loaded"
    if [ -n "$old" ]; then rm -f "$old"; fi
  fi
  if ! schedule enroll "$store" "$repo"; then
    echo "$store could not be put on the scheduler, so it keeps the jobs it had" >&2
    exit 1
  fi
  own_jobs_out
  echo "on: $store is on $sched_label, which checks every hour and dreams when one is due and nobody has been at work in its repositories for 45 minutes, one store at a time, with the fixer first when you approved something; it logs to ~/.local/state/agent-memory/scheduler.log, a dream to ~/.local/state/agent-memory/dream-$store.log"
  exit 0
fi
# The way back: the store's own daily jobs, as an older kit wrote them.
[ "$hour" = - ] && hour=
# auto: the store keeps the hour its dream job has; a store without one gets the first hour where neither its
# dream nor its fixer (two hours before) starts beside another store's dream or fixer. Evenings first.
if [ "$hour" = auto ]; then
  hour=$(/usr/bin/python3 - "$jobs" "$store" <<'EOF_PY'
import glob, os, plistlib, sys
jobs, store = sys.argv[1], sys.argv[2]
def hour_of(path):
    try:
        with open(path, "rb") as f:
            h = plistlib.load(f)["StartCalendarInterval"]["Hour"]
        return h if isinstance(h, int) and 0 <= h <= 23 else None
    except Exception:
        return None
own = hour_of(os.path.join(jobs, f"ai.agent-memory.dream.{store}.plist"))
if own is not None:
    print(own); sys.exit()
busy = []
for kind in ("dream", "fix"):
    for path in glob.glob(os.path.join(jobs, f"ai.agent-memory.{kind}.*.plist")):
        if os.path.basename(path) != f"ai.agent-memory.{kind}.{store}.plist" and hour_of(path) is not None:
            busy.append(hour_of(path))
order = [18, 20, 22, 16, 14, 12, 10, 19, 21, 23, 17, 15, 13, 11] + [h for h in range(24) if not 10 <= h <= 23]
# the first free pair; when none is, the hour whose pair is least taken
print(min(order, key=lambda h: (busy.count(h) + busy.count((h + 22) % 24), order.index(h))))
EOF_PY
) || { echo "couldn't read the other stores' jobs to choose an hour; say one with --hour" >&2; exit 1; }
fi
case $hour in ''|*[!0-9]*|???*) echo "--hour is '$hour'; it has to be a whole number from 0 to 23" >&2; exit 2 ;; esac
hour=$(expr "$hour" + 0) || true  # 08 is 8; expr exits 1 when the answer is 0
[ "$hour" -le 23 ] || { echo "--hour is $hour; it has to be a whole number from 0 to 23" >&2; exit 2; }
fix_hour=$(( (hour + 22) % 24 ))
# job <file> <label> <hour> <script> <option> <log>: one job's plist
job() {
cat >"$1" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$(xml "$2")</string>
  <key>WorkingDirectory</key><string>$(xml "$repo")</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$(xml "$kit/$4")</string><string>$(xml "$repo")</string><string>$5</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$jobs_path</string>
    <key>HOME</key><string>$(xml "$HOME")</string>
  </dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$3</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$(xml "$state/$6")</string>
  <key>StandardErrorPath</key><string>$(xml "$state/$6")</string>
</dict></plist>
EOF_PLIST
}
new=$(mktemp "$state/$store.plist.XXXXXX")
fix_new=$(mktemp "$state/$store.fix-plist.XXXXXX")
job "$new" "$label" "$hour" run-dream.sh --if-due "launchd-$store.log"
job "$fix_new" "$fix_label" "$fix_hour" run-fix.sh --if-approved "launchd-fix-$store.log"
for one in "$new" "$fix_new"; do
  if ! problem=$(plutil -lint "$one" 2>&1); then
    rm -f "$new" "$fix_new"
    echo "The new jobs for $store are not valid plists, so nothing was changed: $problem" >&2
    exit 1
  fi
done
chmod 644 "$new" "$fix_new"
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/$fix_label" 2>/dev/null || true
mv "$new" "$plist"
mv "$fix_new" "$fix_plist"
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl bootstrap "gui/$(id -u)" "$fix_plist"
# Off the scheduler, so it never dreams from both.
left=$(schedule drop "$store")
scheduler_out "$left"
echo "on: $label, checks every day at $hour:00 and dreams when one is due; the daily check logs to ~/.local/state/agent-memory/launchd-$store.log, a dream to ~/.local/state/agent-memory/dream-$store.log"
echo "on: $fix_label, every day at $fix_hour:00 does what you approved for the fixer, and nothing when nothing is; it logs to ~/.local/state/agent-memory/fix-$store.log"
