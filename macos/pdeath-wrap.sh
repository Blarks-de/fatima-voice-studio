#!/bin/sh
# Runs "$@", killing it if the process whose PID is $FVS_WATCH_PPID disappears. macOS has no pdeathsig (the
# kernel feature linux/compat.py uses via setpriv), so this polls instead. "exec" below replaces this shell
# with the wrapped command, keeping the same PID, so the app's subprocess.Popen still sees the real process.
ppid="$FVS_WATCH_PPID"
# >/dev/null 2>&1 closes the watcher's own copies of stdout/stderr: without it, forking inherits the wrapped
# command's piped stdout/stderr, and the watcher holds that pipe open for as long as $ppid lives -- the real
# process can exit, but a caller reading via subprocess.PIPE (engine.py's pump thread) never sees EOF and hangs.
( while kill -0 "$ppid" 2>/dev/null; do sleep 1; done; kill -9 "$$" 2>/dev/null ) >/dev/null 2>&1 &
exec "$@"
