#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Run firmware/src/cs1.c on this computer (tests/host.c): build/host/cs1.wav and the screens as PNG.
# Also the audio worker's unit tests (the second core's hand-off, on a host thread).
set -e
cd "$(dirname "$0")/.."
mkdir -p build/host
CC="${CC:-cc}"
$CC -O2 -Wall -Wno-unused-function -DDINGHY_HOST -DAPP_VER="\"${APP_VER:-dev}\"" -Ifirmware/src -Ifirmware/gen -o build/host/cs1 firmware/src/cs1.c
$CC -O2 -Wall -o build/host/audio_worker_test tests/audio_worker_test.c
build/host/audio_worker_test
$CC -O2 -Wall -pthread -o build/host/audio_worker_thread_test tests/audio_worker_thread_test.c
build/host/audio_worker_thread_test
$CC -O2 -Wall -Wno-unused-function -o build/host/sense_test tests/sense_test.c
build/host/sense_test
build/host/cs1 build/host/cs1
python3 - <<'PYEOF'
from pathlib import Path
from PIL import Image
for p in sorted(Path("build/host").glob("cs1-*.ppm")):
    Image.open(p).resize((480, 480), Image.NEAREST).save(p.with_suffix(".png"))
    p.unlink()
    print("screen ->", p.with_suffix(".png"))
PYEOF
