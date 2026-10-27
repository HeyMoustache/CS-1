#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The editor link's patch map, from the firmware itself: the byte order of patch_t (firmware/src/cs1_voice.h) and
the knobs of the page table (firmware/src/cs1.c: name, range, how a value is shown, the page).

    python3 tools/gen_editor_map.py            -> docs/SYSEX.md (the protocol and the map), build/editor/cs1_map.json

Run it after a change to patch_t or the pages: the editor reads the JSON, people read the Markdown."""
import json, re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
VOICE = (SRC / "firmware/src/cs1_voice.h").read_text()
APP = (SRC / "firmware/src/cs1.c").read_text()


def fields(struct_end):
    """the uint8_t fields of the typedef that closes with '} struct_end;', in order (comments stripped)"""
    end = re.search(r"\}\s*" + struct_end + r";", VOICE).start()
    start = VOICE.rindex("typedef struct {", 0, end) + len("typedef struct {")
    body = re.sub(r"/\*.*?\*/", "", VOICE[start:end], flags=re.S)
    out = []
    for decl in re.findall(r"uint8_t([^;]*);", body):
        out += [f.strip() for f in decl.split(",") if f.strip()]
    return out


CH = fields("chan_patch_t")
GL = fields("patch_t")
assert len(CH) == 26, CH
NCH = 2

# the knobs: CH(field, "NAME", max, kind, ...) / GL(...) inside each page {"TITLE", {...}}
knobs = {}
pages = re.search(r"static const page_t PAGES\[NPAGE\] = \{(.*?)\n\};", APP, re.S).group(1)
for title, body in re.findall(r'\{"([^"]+)",\s*\{(.*?)\}\},', pages, re.S):
    for kind, f, name, mx, how in re.findall(r'\b(CH|GL)\((\w+), "([^"]+)", (\d+), (K_\w+)', body):
        knobs.setdefault((kind, f), {"name": name, "max": int(mx), "kind": how[2:].lower(), "page": title})

VALUES = {   # the named values (cs1.c N_FEET ...)
    "feet": ["16'", "8'", "5.3'", "4'", "2.7'", "2'"], "wave": ["SAW", "PULSE", "BOTH"],
    "lwave": ["SINE", "TRI", "SAW", "SAW DN", "SQR", "NOISE"], "onoff": ["OFF", "ON"],
    "cho": ["OFF", "CHORUS", "TREM", "FLANGE"], "div": ["FREE", "1/16", "1/8T", "1/8", "1/8D", "1/4", "1/4D", "1/2"],
    "ldiv": ["FREE", "1/4", "1/2", "1 BAR", "2 BAR", "4 BAR"],
}
# patch_valid's limits beyond the knobs' (the firmware refuses a patch past these)
VALID_MAX = {"feet": 5, "wave": 2, "lfo_wave": 5, "gliss": 1, "cho_mode": 3, "dly_ping": 1, "dly_sync": 7,
             "lfo_sync": 5, "rv_shift": 24}

params = []
for c in range(NCH):
    for i, f in enumerate(CH):
        k = knobs.get(("CH", f), {})
        params.append({"off": c * len(CH) + i, "field": f"ch[{c}].{f}", "channel": c + 1, "key": f, **k,
                       "max": k.get("max", VALID_MAX.get(f, 127))})
for i, f in enumerate(GL[GL.index("ch[NCH]") + 1:] if "ch[NCH]" in GL else GL):
    k = knobs.get(("GL", f), {})
    params.append({"off": NCH * len(CH) + i, "field": f, "channel": 0, "key": f, **k,
                   "max": k.get("max", VALID_MAX.get(f, 127))})
plen = len(params)

out = SRC / "build/editor"
out.mkdir(parents=True, exist_ok=True)
(out / "cs1_map.json").write_text(json.dumps({"patch_len": plen, "values": VALUES, "params": params}, indent=1))

rows = []
for p in params:
    shown = p.get("kind")
    rng = f"0..{p['max']}"
    if shown in VALUES:
        rng += " (" + ", ".join(f"{i} {v}" for i, v in enumerate(VALUES[shown][: p["max"] + 1])) + ")"
    elif shown == "bip":
        rng += " (64 = centre)"
    where = f"{p['page']} · {p['name']}" if "page" in p else "(no knob)"
    rows.append(f"| {p['off']} | `{p['field']}` | {where} | {rng} |")

doc = f"""# The editor link (SysEx)

The browser editor talks to CS-1 over SysEx, on USB (both ways) or the TRS jack (into the FM-1 only). The firmware's
side is `firmware/src/cs1_editor.h`; this page and the editor's map (`build/editor/cs1_map.json`) are generated from
the firmware by `tools/gen_editor_map.py`.

## Frames

Every frame is `F0 7D 43 53 31 <cmd> <data> F7`: `7D` is MIDI's non-commercial ID, `43 53 31` is "CS1". Every data
byte is 0..127, and the patch travels as its {plen} bytes, unchanged (every one is a knob's value).

| cmd | to the FM-1 | data | the FM-1 replies |
| --- | --- | --- | --- |
| `01` | HELLO | none | `41` protocol (1), patch length (2 bytes, low 7 bits first), user slots, sounds, tones, the version as ASCII |
| `02` | GET PANEL | none | `42` tone I, tone II, sound, the patch |
| `03` | SET PANEL | tone I, tone II, the patch | `7F 03` status |
| `04` | SET PARAM | offset (2 bytes, low 7 bits first), value | nothing, or `7F 04` status on an error |
| `05` | STORE | slot 0..31 | `7F 05` status (the panel into the slot: flash) |
| `06` | GET SLOT | slot | `46` slot, used (0/1), tone I, tone II, category, the patch (nothing after "used" when empty) |
| `07` | PUT SLOT | slot, tone I, tone II, category (0 = guess), the patch | `7F 07` status (straight into the bank, the panel stays) |
| `08` | LOAD | index (the sounds, then the user slots) | `7F 08` status |

Status: 0 done, 1 wrong length, 2 a value out of range, 3 a slot or index out of range, 4 the flash failed, 5 an
unknown command. A panel or parameter the firmware refuses leaves the panel as it was.

STORE and PUT SLOT erase the bank's flash sector (about 50 ms, the sound stalls): wait for the status before the next.
The FM-1 takes one frame at a time; an editor waits for each reply (or, for SET PARAM, sends no faster than the knob
moves). Over the TRS jack there is no reply: leave 50 ms between frames.

## The patch

{plen} bytes: channel I's 26, channel II's 26, then the globals. "Page · knob" is where it is on the FM-1.

| offset | field | page · knob | range |
| --- | --- | --- | --- |
""" + "\n".join(rows) + "\n"
(SRC / "docs/SYSEX.md").write_text(doc)
print(f"editor map: {plen} bytes, {sum('page' in p for p in params)} on knobs -> docs/SYSEX.md, build/editor/cs1_map.json")
