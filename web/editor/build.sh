#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# The CS-1 Programmer as one self-contained page:  web/editor/build.sh  ->  build/editor/cs1-editor.html
# It compiles the firmware to WebAssembly (emcc when present, else clang --target=wasm32 with web/editor/wasm/), reads
# the editor's data out of the firmware (tools/dump_editor_data.c) and puts both, with the worklet, into editor.html.
set -e
cd "$(dirname "$0")/../.."
VERSION="${APP_VER:-$(cat VERSION 2>/dev/null || echo dev)}"
CC="${CC:-cc}"
mkdir -p build/editor build/host
if command -v emcc >/dev/null 2>&1; then
    emcc -O2 -ffp-contract=off -std=gnu99 -Wall -Wno-unused-function "-DAPP_VER=\"$VERSION\"" -Ifirmware/src -Ifirmware/gen \
        --no-entry -sSTANDALONE_WASM -sSTACK_SIZE=1048576 -sINITIAL_MEMORY=16777216 -sFILESYSTEM=0 \
        -o build/editor/cs1.wasm web/emu/cs1_web.c
else
    clang --target=wasm32 -O2 -ffp-contract=off -std=gnu99 -ffreestanding -nostdlib -Wall -Wno-unused-function \
        "-DAPP_VER=\"$VERSION\"" -Iweb/editor/wasm -Ifirmware/src -Ifirmware/gen \
        -Wl,--no-entry -Wl,--export-dynamic -Wl,-z,stack-size=1048576 -Wl,--initial-memory=16777216 \
        -o build/editor/cs1.wasm web/emu/cs1_web.c web/editor/wasm/rt.c
fi
$CC -O1 -Wno-unused-function -DDINGHY_HOST "-DAPP_VER=\"$VERSION\"" -Ifirmware/src -Ifirmware/gen \
    -o build/host/dump_editor_data tools/dump_editor_data.c
build/host/dump_editor_data > build/editor/cs1_data.json
python3 - <<'PYEOF'
import base64, json
from pathlib import Path
b = Path("build/editor")
page = Path("web/editor/editor.html").read_text()
data = json.dumps(json.loads((b / "cs1_data.json").read_text()), separators=(",", ":"))
wasm = base64.b64encode((b / "cs1.wasm").read_bytes()).decode()
worklet = json.dumps(Path("web/editor/worklet.js").read_text())
for key, val in (("/*@DATA@*/null", data), ("/*@WASM@*/", wasm), ("/*@WORKLET@*/\"\"", worklet)):
    assert page.count(key) == 1, key
    page = page.replace(key, val)
(b / "cs1-editor.html").write_text(page)
print(f"editor: build/editor/cs1-editor.html ({len(page) // 1024} KiB)")
PYEOF
