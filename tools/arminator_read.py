#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Arminator 2 patches (Krakli Software; presets by Armin Kujat) as CS-1 panels and sounds, for the randomiser's
corpus. The banks are read with the plugin itself under Wine (tests/vstdump.c), one .jsonl per bank: a first line
with the parameter names, then a line per program with the plugin's values and display strings.

   tools/arminator_read.py [--dir ~/Documents/Projects/CS1/arminator] > arminator.json

The output has the converter's shape (tools/arturia_convert.py): "panels", chart rows 0..10 for the two lines, and
"sounds" with the globals, two panels each. The names are the patches' own: this corpus is statistics, not shipped
sounds. Arminator's arpeggiator, key split, bit crusher and ribbon have no counterpart here and are dropped; its
per-line LFO becomes the sub oscillator (line A's, or B's if A's is unused), its per-line echo the delay."""
import argparse
import glob
import json
import os
import sys

DIR = os.path.expanduser("~/Documents/Projects/CS1/arminator")
LW = {"Sine": 0, "Triangle": 1, "Saw": 2, "Ramp": 3, "Pulse": 4}


def c127(x):
    return max(0, min(127, round(x)))


def cl(v, lo=0.0, hi=10.0):
    return max(lo, min(hi, v))


class Patch:
    def __init__(self, names, prog):
        self.by = {}
        for i, p in enumerate(names):
            self.by[p["name"].strip().replace("  ", " ")] = (prog["values"][i], prog["display"][i].strip())
        self.name = prog["name"]

    def num(self, key, default=0.0):       # the plugin's displayed number
        v = self.by.get(key)
        if not v:
            return default
        try:
            return float(v[1])
        except ValueError:
            return default

    def mode(self, key, default=""):
        v = self.by.get(key)
        return v[1] if v else default


def panel(p, ln):
    """one line as a chart row: pulse saw speed pwm pw noise hpf hres lpf lres il al fa fd fr vcflev sine va vd vs vr
    level ibrill ilevel abrill alevel (0..10)"""
    k = lambda s: f"Line {ln} {s}"
    saw_lv, pwm_lv, sine_lv = p.num(k("Saw Osc Level")), p.num(k("PWM Osc Level")), p.num(k("sine Osc Level"), p.num(k("Sine Osc Level")))
    saw_wave = p.mode(k("saw Osc Waveform"))
    pulse = pwm_lv > 0.3 or (saw_lv > 0.3 and saw_wave == "Square")
    saw = saw_lv > 0.3 and saw_wave != "Square" and saw_wave != "Sine"
    if saw_lv > 0.3 and saw_wave == "Sine":
        sine_lv = max(sine_lv, saw_lv)
    speed = cl((p.num(k("PWM Osc Rate"), -10) + 10) / 15 * 10)
    pwm = cl(p.num(k("PWM Osc PWM")))
    pw = cl(p.num(k("PWM Osc Width")) / 9 * 10, 0, 9.0)
    hpf, hres = cl(p.num(k("HPF Freq"))), cl(p.num(k("HPF Resonance")))
    lpf, lres = cl(p.num(k("LPF Freq"))), cl(p.num(k("LPF Resonance")))
    env, sus = cl(p.num(k("LPF Env Mod"))), cl(p.num(k("LPF Sustain")))
    lpf = cl(2.5 + lpf + env * sus / 10 * 0.5)             # a floor (Arminator's 0 is not closed), the part the sustain holds open as a higher cutoff
    al = cl(5 + env * (10 - sus) / 10 / 2)                 # the transient part, above the centre (5 = none)
    il = 5.0
    fa, fd, fr = cl(p.num(k("LPF Attack"))), cl(p.num(k("LPF Decay"))), cl(p.num(k("LPF Release")))
    vcflev = cl(p.num(k("Filter to Amp Level")) / 15 * 10) if (pulse or saw) else 0
    if p.num(k("LPF HPF Mix")) > 7:                         # 0 = the low-pass (nearly every patch), 10 = the high-pass alone
        lpf = 10.0
    va, vd, vs, vr = cl(p.num(k("Amp Attack"))), cl(p.num(k("Amp Decay"))), cl(p.num(k("Amp Sustain"))), cl(p.num(k("Amp Release")))
    level = cl(p.num(k("Amp Level")))
    ibrill = cl(p.num(k("LPF Velocity")) / 8 * 10)
    abrill = cl(p.by.get(k("LPF Aftertouch"), (0, ""))[0] * 10)   # (its display scale differs between the lines: the raw value)
    return [1 if pulse else 0, 1 if saw else 0, speed, pwm, pw, 0.0, hpf, hres, lpf, lres, il, al, fa, fd, fr,
            vcflev, cl(sine_lv), va, vd, vs, vr, level, ibrill, 0.0, abrill, 0.0]


def sound(p, name, t1, t2):
    s = {"name": name, "tone": [t1, t2]}
    feet = lambda o: {-2: 0, -1: 0, 0: 1, 1: 3, 2: 5}.get(int(round(o)), 1)   # 16' 8' 4' 2' (no fifths)
    s["feet1"] = [feet(p.num("Line A Octave")) + 1, feet(p.num("Line B Octave")) + 1]
    vol = p.num("Volume", 10) / 10
    s["level"] = [max(1, c127(110 * p.num("Line A Mixer Volume") / 10 * vol)), max(1, c127(110 * p.num("Line B Mxer Volume") / 10 * vol))]
    s["brill"] = s["reso"] = 64
    s["mix"] = 64
    s["detune"] = c127(64 + (p.num("Line B Fine Tune") - p.num("Line A Note Tune")) * 40)
    gl = -min(p.num("Line A Glide Amount"), p.num("Line B Glide Amount"))
    s["porta"] = c127(gl / 6 * 127)
    s["gliss"] = 1 if "Gliss" in p.mode("Line A Glide Type") and gl > 0 else 0
    s["pbend"] = 0
    # the sub oscillator: the line's LFO, routed by the mod wheel (pressure here) or direct
    lw = "A" if p.num("Line A LFO Mod Amount") >= p.num("Line B LFO Mod Amount") else "B"
    amt = p.num(f"Line {lw} LFO Mod Amount") / 10 * 127
    dest, route = p.mode(f"Line {lw} LFO Mod Destination"), p.mode(f"Line {lw} LFO Mod Route")
    to_vcf = "Freq" in dest
    s["lfo_spd"] = max(1, c127((p.num(f"Line {lw} LFO Rate", -10) + 10) / 15 * 127))
    s["lfo_wave"] = 5 if p.mode(f"Line {lw} LFO or Sample and Hold") == "SandH" else LW.get(p.mode(f"Line {lw} LFO Waveform"), 0)
    s["lfo_vco"] = s["lfo_vcf"] = s["at_vco"] = s["at_vcf"] = 0
    if route == "Direct":
        s["lfo_vcf" if to_vcf else "lfo_vco"] = c127(amt if to_vcf else amt * 0.5)
    elif route == "Mod Wheel":
        s["at_vcf" if to_vcf else "at_vco"] = c127(amt if to_vcf else amt * 0.5)
    vib = max(p.num("Line A Vibrato Amount"), p.num("Line B Vibrato Amount"))
    if vib > 0:
        s["lfo_vco"] = max(s["lfo_vco"], c127(vib / 0.2 * 40))
        if not s["lfo_vcf"] and not amt:
            s["lfo_spd"] = max(1, c127((p.num("Line A Vibrato Rate", -10) + 10) / 15 * 127))
    s["at_vco"] = max(s["at_vco"], 17)
    s["aat_delay"], s["aat_rise"], s["aat_level"] = 40, 60, 60
    # the CS-80's own chorus
    s["cho_mode"] = 1 if p.mode("ChorusOnOff") == "On" else 0
    s["cho_spd"] = max(1, c127((p.num("ChorusRate", -10) + 10) / 5 * 60))
    s["cho_depth"] = max(1, c127((p.num("ChorusDepth", 4) - 4) / 39 * 127))
    # the ring modulator
    rm = p.num("Ring Mod Mixer Volume")
    s["rm_mod"] = c127(rm / 10 * 127)
    s["rm_spd"] = max(1, c127(p.num("Ring Mod Pitch") / 9.55 * 127))
    s["rm_depth"] = c127(p.num("Ring Mod Pitch Envelope Mod") / 10 * 127)
    s["rm_d"] = max(1, c127(p.num("Ring Mod Decay") / 12 * 127))
    # the delay: the louder line's echo
    le = "A" if p.num("Line A Echo Mix") >= p.num("Line B Echo Mix") else "B"
    mix = p.num(f"Line {le} Echo Mix")
    if mix > 0.2:
        s["dly_mix"] = c127(mix / 10 * 127)
        s["dly_fb"] = max(1, c127(p.num(f"Line {le} Echo Repeat") / 7 * 127))
        beats = p.num(f"Line {le} Echo Clock Mode", 1)
        s["dly_sync"] = {0.25: 1, 0.5: 3, 1.0: 5, 2.0: 7}.get(round(beats * 4) / 4, 0)
        if not s["dly_sync"]:
            s["dly_time"] = c127(70 + (beats - 1) * 10)
    # the reverb
    rv = p.num("Reverb Mix", -5)
    if rv > -5:
        s["rv_mix"] = max(1, c127((rv + 5) / 6 * 110))
        s["rv_size"] = max(1, c127(40 + p.num("Reverb Size") / 10 * 87))
        s["rv_damp"] = max(1, c127(p.num("Reverb Damp") / 10 * 127))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    a = ap.parse_args()
    panels, sounds = [], []
    for path in sorted(glob.glob(os.path.join(a.dir, "*.jsonl"))):
        lines = open(path, encoding="utf-8").read().splitlines()
        names = json.loads(lines[0])["params"]
        bank = os.path.basename(path)[:-6]
        for line in lines[1:]:
            p = Patch(names, json.loads(line))
            if p.name.strip().lower() in ("default", "init", ""):
                continue
            i1 = len(panels); panels.append([f"{p.name[:9]} A"] + [round(v, 3) for v in panel(p, "A")])
            i2 = len(panels); panels.append([f"{p.name[:9]} B"] + [round(v, 3) for v in panel(p, "B")])
            s = sound(p, p.name, i1, i2)
            s["bank"] = bank
            sounds.append(s)
    print(f"{len(sounds)} patches from {a.dir}", file=sys.stderr)
    json.dump({"panels": panels, "sounds": sounds}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
