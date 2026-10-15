#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read a CS-80 V preset file (a Boost text archive: "<len> <name> <value>" pairs after a header) into a dict.
   tools/arturia_read.py PRESET [filter]   prints the parameters (those whose name contains filter)."""
import re
import sys


def read(path):
    raw = open(path, "rb").read().decode("latin-1")
    meta = {}
    m = re.search(r"\d+ OriginalPresetName (\d+) ", raw)
    if m:
        meta["name"] = raw[m.end():m.end() + int(m.group(1))]
    m = re.search(r"\d+ Type (\d+) ", raw)
    if m:
        meta["type"] = raw[m.end():m.end() + int(m.group(1))]
    start = raw.find("AfterTouchCurve_LastActivePointIndex")
    if start < 0:
        raise SystemExit(f"{path}: no parameter list")
    i = raw.rfind(" ", 0, start - 1) + 1       # back to the length that precedes the first name
    params = {}
    n = len(raw)
    while i < n:
        m = re.match(r"(\d+) ", raw[i:])
        if not m:
            break
        ln = int(m.group(1))
        j = i + m.end()
        name = raw[j:j + ln]
        if not name or not re.match(r"[A-Za-z]", name) or len(name) != ln:
            break
        k = j + ln
        if k >= n or raw[k] != " ":
            break
        mv = re.match(r" (-?[0-9.eE+-]+)(?= |$)", raw[k:])
        if not mv:
            break
        params[name] = float(mv.group(1))
        i = k + mv.end() + 1
    return meta, params


if __name__ == "__main__":
    meta, p = read(sys.argv[1])
    flt = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    print(meta, len(p), "parameters")
    for k in sorted(p):
        if flt in k.lower():
            print(f"  {k:44} {p[k]:.4f}")
