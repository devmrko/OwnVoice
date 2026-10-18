#!/bin/sh
set -eu
ownvoice_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ownvoice_root"
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo 'FFmpeg is required. macOS: brew install ffmpeg; Ubuntu/Debian: sudo apt install ffmpeg' >&2
    exit 1
fi
# --setup-only prepares dependencies without starting the server or downloading models.
"$ownvoice_root/uvw" sync --locked --extra tts --python 3.12
if [ "${1:-}" = '--setup-only' ]; then exit 0; fi
exec "$ownvoice_root/uvw" run --no-sync ownvoice start "$@"
