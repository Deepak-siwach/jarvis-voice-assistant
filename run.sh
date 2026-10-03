#!/bin/bash
# Robust launcher for J.A.R.V.I.S. Voice Assistant & Arc Reactor HUD on MacBook Air M5

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

# Prefer local virtual environment if present
if [ -x ".venv/bin/python3" ]; then
    exec .venv/bin/python3 jarvis.py "$@"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    exec /opt/homebrew/bin/python3 jarvis.py "$@"
else
    exec python3 jarvis.py "$@"
fi
