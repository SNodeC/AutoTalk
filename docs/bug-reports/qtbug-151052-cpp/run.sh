#!/bin/sh
# Run inside: xvfb-run -a dbus-run-session -- ./run.sh /absolute/path/to/qtbug151052
set -eu
binary=$(realpath "$1")
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}" XDG_SESSION_TYPE=wayland QT_MEDIA_BACKEND=ffmpeg
ulimit -c 0
log=$(mktemp)
"$binary" --portal >"$log" 2>&1 &
portal=$!
trap 'kill -KILL "$portal" 2>/dev/null || :; wait "$portal" 2>/dev/null || :; cat "$log"; rm -f "$log"' EXIT
attempt=0
while ! grep -q '^ready$' "$log"; do
    kill -0 "$portal" || exit 2
    attempt=$((attempt+1))
    test "$attempt" -lt 100 || exit 2
    sleep 0.05
done
if test "${2-}" = --gdb; then
    gdb --batch -ex run -ex bt --args "$binary"
else
    "$binary"
fi
