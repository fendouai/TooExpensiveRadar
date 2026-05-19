#!/bin/bash
# Start the Too Expensive Radar API server
# WeasyPrint requires pango library path on macOS
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH}"
cd "$(dirname "$0")"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
