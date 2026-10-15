#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Even out the converted sounds' loudness by measurement: render a chord on each (the host build), and scale its two
channel levels so the chord's held level sits at TARGET dBFS (the plugin's own levels do not carry over: its LEVEL
slider never reaches silence and each preset has its own output volume). Writes the levels into tools/converted.json.
   tests/run_host.sh (once), then tools/level_converted.py; run gen_presets.py after."""
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from compare_wav import read_wav  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = -18.0
FS = 44100


def held_db(i, note):
    with tempfile.TemporaryDirectory() as d:
        s = os.path.join(d, "s.txt")
        open(s, "w").write(f"50 btn 11\n100 midi 0xC0 {i} 0\n500 midi 0x90 {note} 100\n520 midi 0x90 {note + 4} 100\n"
                           f"540 midi 0x90 {note + 7} 100\n2500 midi 0x80 {note} 0\n2500 midi 0x80 {note + 4} 0\n"
                           f"2500 midi 0x80 {note + 7} 0\n3000 end\n")
        subprocess.run([os.path.join(ROOT, "build/host/cs1"), os.path.join(d, "o"), s], capture_output=True, check=True)
        x, _, _, _ = read_wav(os.path.join(d, "o.wav"))
    m = x.mean(axis=1)
    seg = m[int(0.6 * FS):int(2.4 * FS)]
    return 10 * math.log10(float((seg ** 2).mean()) + 1e-12)


def main():
    path = os.path.join(ROOT, "tools/converted.json")
    d = json.load(open(path))
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 51      # the index of the first converted sound
    for k, s in enumerate(d["sounds"]):
        note = 48 if "BASS" in s["name"] else 60
        db = held_db(first + k, note)
        gain = 10 ** ((TARGET - db) / 20)
        lv = [max(8, min(127, round(v * gain))) for v in s["level"]]
        rest = gain * min(s["level"][0] / max(lv[0], 1), s["level"][1] / max(lv[1], 1))   # what the levels could not take
        if rest > 1.05:                                 # into the panels' own VCF and sine levels (chart 0..10)
            for t in s["tone"]:
                pn = d["panels"][t]
                pn[16] = round(min(10.0, pn[16] * rest), 3)              # VCF LEVEL (linear)
                pn[17] = round(min(10.0, pn[17] * rest ** 2.5), 3)       # SINE (a 0.4-power curve)
        print(f"{s['name']:15} held {db:6.1f} dBFS -> levels {s['level']} -> {lv}" + (f", panels x{rest:.2f}" if rest > 1.05 else ""), file=sys.stderr)
        s["level"] = lv
    json.dump(d, open(path, "w"), indent=1)
    open(path, "a").write("\n")


if __name__ == "__main__":
    main()
