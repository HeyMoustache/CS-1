#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The editor link (firmware/src/cs1_editor.h) on the host build: a script of SysEx frames in, the replies out.

    python3 tests/editor_test.py [build/host/cs1]

Two runs: the first reads the patch's size and the panel, the second (with frames built from what the first said)
sets the panel, one parameter, stores and reads slots, loads, and checks every reply and the errors."""
import subprocess, sys, os, tempfile

EXE = sys.argv[1] if len(sys.argv) > 1 else "build/host/cs1"
HDR = [0xF0, 0x7D, 0x43, 0x53, 0x31]
fails = 0


def check(what, ok):
    global fails
    print(f"editor: {what:<70} {'ok' if ok else 'FAIL'}")
    if not ok:
        fails += 1


def frame(cmd, *data):
    return HDR + [cmd] + [d & 0x7F for d in data] + [0xF7]


def run(events, end_ms):
    """events: [(t, frame or ('midi', st, d1, d2))] -> [(t, bytes)] of SysEx out, the bank saves seen, all output"""
    lines = []
    for t, ev in events:
        if ev[0] == "midi":
            lines.append(f"{t} midi {ev[1]} {ev[2]} {ev[3]}")
        else:
            lines.append(f"{t} sysex " + " ".join(f"{b:02X}" for b in ev))
    lines.append(f"{end_ms} end")
    with tempfile.TemporaryDirectory() as d:
        sc = os.path.join(d, "script.txt")
        open(sc, "w").write("\n".join(lines) + "\n")
        out = subprocess.run([EXE, os.path.join(d, "run"), sc], capture_output=True, text=True, check=True).stdout
    replies = []
    for ln in out.splitlines():
        if "SysEx out" in ln:
            t = int(ln.split()[0])
            replies.append((t, [int(x, 16) for x in ln.split("SysEx out")[1].split()]))
    return replies, out


def body(r):
    """a reply's command and data, or None when it is not ours"""
    if r[:5] != HDR or r[-1] != 0xF7:
        return None
    return r[5], r[6:-1]


# ---- the first run: who it is, the panel
rep, _ = run([(100, frame(0x01)), (120, frame(0x02))], 300)
check("HELLO and GET PANEL each answered", len(rep) == 2)
cmd, d = body(rep[0][1])
check("HELLO's reply is 41, protocol 1", cmd == 0x41 and d[0] == 1)
plen = d[1] | d[2] << 7
nuser, nsound, ntone = d[3], d[4], d[5]
version = bytes(d[6:]).decode()
print(f"editor: patch {plen} bytes, {nuser} user slots, {nsound} sounds, {ntone} tones, version {version}")
check("the patch is 26 bytes a channel plus the globals (100 .. 124)", 100 <= plen <= 124)
check("32 user slots, 52+ sounds, 22+ tones", nuser == 32 and nsound >= 52 and ntone >= 22)
cmd, d = body(rep[1][1])
check("GET PANEL's reply is 42 with tones, sound and the patch", cmd == 0x42 and len(d) == 3 + plen)
tones, panel = d[0:2], d[3:]
check("every byte of the panel is 0..127", all(0 <= b <= 127 for b in panel))

# offsets (cs1_voice.h): a channel is 26 bytes; ch[0].lp_cut = 11, ch[0].feet = 0; the globals at 52: lfo_spd, lfo_wave,
# lfo_vco, lfo_vcf, lfo_vca, brill (57)
LP_CUT0, FEET0, BRILL = 11, 0, 57
new = list(panel)
new[LP_CUT0] = 33
new[BRILL] = 99
bad = list(panel)
bad[FEET0] = 9                                     # feet 0..5: out of range
slot_patch = list(panel)
slot_patch[52 + 26 + 0] ^= 1                       # something different to tell the slot by (ch[1] untouched; a global)
slot_patch[BRILL] = 12

ev = [
    (100, frame(0x03, 3, 14, *new)),               # SET PANEL
    (150, frame(0x02)),
    (200, frame(0x04, LP_CUT0, 0, 77)),            # SET PARAM: no reply when it works
    (250, frame(0x02)),
    (300, frame(0x04, FEET0, 0, 9)),               # SET PARAM out of range
    (350, frame(0x04, plen & 0x7F, plen >> 7, 1)), # SET PARAM past the end
    (400, frame(0x03, 1, 2, *bad)),                # SET PANEL out of range
    (450, frame(0x03, 1, 2, *new[:-1])),           # SET PANEL a byte short
    (500, frame(0x05, 3)),                         # STORE slot 3
    (600, frame(0x06, 3)),                         # GET SLOT 3
    (650, frame(0x06, 4)),                         # GET SLOT 4: empty
    (700, frame(0x07, 5, 2, 4, 3, *slot_patch)),   # PUT SLOT 5 (category 3: BRASS)
    (800, frame(0x06, 5)),
    (850, frame(0x08, nsound + 5)),                # LOAD slot 5 onto the panel
    (900, frame(0x02)),
    (950, frame(0x08, nsound + 6)),                # LOAD an empty slot
    (1000, frame(0x08, 0)),                        # LOAD the first sound
    (1050, frame(0x02)),
    (1100, frame(0x05, 40)),                       # STORE out of range
    (1150, frame(0x09)),                           # unknown
    (1200, [0xF0, 0x7D, 0x01, 0x02, 0xF7]),        # another 7D frame, not "CS1": silence
    (1250, ("midi", 0x90, 60, 100)),               # it still plays
    (1300, frame(0x04, BRILL, 0, 20)),             # a parameter while a note sounds
    (1700, ("midi", 0x80, 60, 0)),
]
rep, out = run(ev, 9000)
at = {}
for t, r in rep:
    at.setdefault(t, []).append(body(r))


def one(t):
    v = at.get(t, [])
    return v[0] if len(v) == 1 else None


def status(t, cmd):
    r = one(t)
    return r and r[0] == 0x7F and r[1][0] == cmd and r[1][1]


check("SET PANEL acknowledged", status(100, 0x03) == 0 and one(100)[1] == [3, 0])
r = one(150)
check("the panel now reads back as sent, with its tones", r and r[1][:2] == [3, 14] and r[1][3:] == new)
check("SET PARAM that works says nothing", 200 not in at)
r = one(250)
check("the parameter landed (LPF of channel I = 77)", r and r[1][3 + LP_CUT0] == 77)
check("a parameter out of range: status 2", status(300, 0x04) == 2)
check("a parameter past the patch: status 3", status(350, 0x04) == 3)
check("a panel out of range: status 2", status(400, 0x03) == 2)
check("a panel a byte short: status 1", status(450, 0x03) == 1)
check("STORE slot 3: done", status(500, 0x05) == 0)
r = one(600)
expect = list(new); expect[LP_CUT0] = 77
check("GET SLOT 3: used, the panel as stored", r and r[0] == 0x46 and r[1][:2] == [3, 1] and r[1][5:] == expect)
r = one(650)
check("GET SLOT 4: empty", r and r[0] == 0x46 and r[1] == [4, 0])
check("PUT SLOT 5: done", status(700, 0x07) == 0)
r = one(800)
check("GET SLOT 5: tones 2 / 4, BRASS, the patch sent", r and r[1][:5] == [5, 1, 2, 4, 3] and r[1][5:] == slot_patch)
check("LOAD slot 5: done", status(850, 0x08) == 0)
r = one(900)
check("the panel is slot 5 now (sound index points at it)", r and r[1][:3] == [2, 4, nsound + 5] and r[1][3:] == slot_patch)
check("LOAD an empty slot: status 3", status(950, 0x08) == 3)
check("LOAD sound 0: done", status(1000, 0x08) == 0)
r = one(1050)
check("the panel is sound 0 again, as at power-on", r and r[1][2] == 0 and r[1][3:] == panel)
check("STORE slot 40: status 3", status(1100, 0x05) == 3)
check("an unknown command: status 5", status(1150, 0x09) == 5)
check("someone else's 7D frame: no answer", 1200 not in at)
saves = out.count("user bank saved")
check("the bank went to flash twice (STORE, PUT SLOT)", saves == 2)
check("nothing else answered", sum(len(v) for v in at.values()) == 19)
check("the settings were kept after the edits", "settings saved" in out)

print("editor:", "all ok" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
