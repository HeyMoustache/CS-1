#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Turn CS-80 V presets (the files on this computer) into CS-1 sounds.

   tools/arturia_convert.py [--list tools/converted.txt] [--dir PRESETS] > tools/converted.json

The list holds lines "Arturia preset name = OUR NAME". Each preset becomes two panels (chart values 0..10, the same
form as the manual's charts in gen_presets.py, so they go through the calibrated mapping) and a sound (the lower
panel, the performance side and the effects). The upper panel is stored as the sliders read, 0..1; every lower-panel
slider is stored flipped (the plugin's own parameter definitions say so: 1 is the top of the travel, which is zero).
Effects: the three FX slots map onto ours by type (reverb, the delays, the choruses, the phaser); the rest are
skipped. The output names are ours; the presets themselves stay on this computer."""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from arturia_read import read  # noqa: E402

PRESETS = "/Library/Arturia/Presets/CS-80 V4/Factory/Factory"
FX_TYPES = ["None", "Reverb", "Delay", "Tape Echo", "PS Delay", "Chorus", "Chorus JUN-6", "Flanger", "Phaser",
            "Compressor", "Multiband", "BitCrusher", "Multi Filter", "Param EQ", "Stereo Pan", "Distortion",
            "BL-20 Flanger", "Super Unison"]
DIVS_BARS = [None, 1 / 16, 1 / 12, 1 / 8, 3 / 16, 1 / 4, 3 / 8, 1 / 2]      # our delay SYNC divisions, in bars


def c127(x):
    return max(0, min(127, round(x)))


def panel(p, n):
    """channel n (1, 2) as a chart row: name later, then pulse saw speed pwm pw noise hpf hres lpf lres il al fa fd fr
    vcflev sine va vd vs vr level ibrill ilevel abrill alevel (0..10)"""
    g = lambda k, d=0.0: p.get(k, d)
    sq, saw, tri = g(f"VCO{n}_SquareOn"), g(f"VCO{n}_SawOn"), g(f"VCO{n}_TriOn")
    if tri and not sq and not saw:
        saw = 1                                   # no triangle here: a sawtooth (the filter softens it)
    wave_on = bool(sq or saw)
    # the plugin's pulse width runs to 100 % (silent); ours stops at 95 %: past 90 % on the slider the pulse fades out
    pwv = g(f"VCO{n}_PW")
    fade = 1.0 if (saw or pwv <= 0.9) else max(0.0, (1.0 - pwv) / 0.1)
    hp_on, lp_on = g(f"VCF{n}_HpfOn", 1), g(f"VCF{n}_LpfOn", 1)
    t = lambda k: 10 * g(k)
    return [1 if sq else 0, 1 if saw else 0,
            t(f"Cs80LFO{n}_RateUnSynced"), t(f"VCO{n}_PWM"), min(9.0, 10 * pwv), t(f"VCO{n}_NoiseLevel"),
            t(f"VCF{n}_HpfCutoffFreq") if hp_on else 0, t(f"VCF{n}_HpfResonance") if hp_on else 0,
            t(f"VCF{n}_LpfCutoffFreq") if lp_on else 10, t(f"VCF{n}_LpfResonance") if lp_on else 0,
            t(f"VcfEnv{n}_InitialLevel"), t(f"VcfEnv{n}_AttackLevel"), t(f"VcfEnv{n}_Attack"), t(f"VcfEnv{n}_Decay"),
            t(f"VcfEnv{n}_Release"),
            t(f"VCA{n}_VcfLevel") * fade if wave_on else 0, sine_chart(g(f"VCA{n}_SineLevel")),
            t(f"VcaEnv{n}_Attack"), t(f"VcaEnv{n}_Decay"), t(f"VcaEnv{n}_Sustain"), t(f"VcaEnv{n}_Release"),
            t(f"VCA{n}_VcaLevel"),
            t(f"VCF{n}_InitialBrilliance"), t(f"VCA{n}_InitialLevel"),
            t(f"ModulationsHandler_ModAfterTouchCutoffVcf{n}"), t(f"ModulationsHandler_ModAfterTouchVcaLevel{n}")]


def sine_chart(v):
    """the plugin's sine slider is linear, and at full ~8 dB under ours (Glass Pipes' take: two pure sines); our chart
    sine goes through a 0.4-power curve (calibrated on the manual's tones), so the chart value that lands on 0.4 v linear"""
    return 10 * (0.4 * max(0.0, v)) ** 2.5


def flip(p, k, d=1.0):
    return 1.0 - p.get(k, d)


def sound(p, name, t1, t2):
    g = lambda k, d=0.0: p.get(k, d)
    s = {"name": name, "tone": [t1, t2]}
    feet = lambda v: max(0, min(5, round((1 - v) * 5)))          # 1.0 = 16' .. 0 = 2', fifths between
    s["feet1"] = [feet(g("Feet1", 0.8)) + 1, feet(g("Feet2", 0.8)) + 1]
    # the LEVEL slider never reaches silence in the plugin (Dry Bass plays with both at 0): -9 dB .. full
    s["level"] = [max(1, c127(110 * (0.35 + 0.65 * g("VCA1_VcaLevel", 1)))), max(1, c127(110 * (0.35 + 0.65 * g("VCA2_VcaLevel", 1))))]
    s["brill"] = max(1, c127(64 + (1 - 2 * g("Brilliance", 0.5)) * 63))
    s["reso"] = max(1, c127(64 + flip(p, "Resonance") * 63))
    s["detune"] = max(1, c127(64 + (1 - 2 * g("Detune", 0.5)) * 63))
    s["mix"] = max(1, c127((1 - g("Mix", 1.0)) * 127))           # 1 = channel I only (the top of the lever)
    gl = g("GlideTime")
    s["porta"] = c127(127 * math.sqrt(gl)) if gl > 0.001 else 0
    s["gliss"] = 1 if g("PortaGlissSwitch") >= 0.5 else 0
    s["pbend"] = c127(flip(p, "InitialPitchBend") * 127)
    s["at_vco"] = max(1, c127(flip(p, "ModulationsHandler_ModAfterTouchSubOscVco") * 127 * 0.6))
    s["at_vcf"] = c127(flip(p, "ModulationsHandler_ModAfterTouchSubOscVcf") * 127)
    wf = max(0, min(5, round((1 - g("SubOsc_Waveform", 1)) * 5)))  # the function lever, top = sine
    s["lfo_wave"] = [0, 1, 2, 3, 4, 4][wf]
    s["lfo_spd"] = max(1, c127(127 * g("SubOsc_RateUnSynced", 0.5)))
    s["lfo_vco"] = c127(flip(p, "ModulationsHandler_ModSubOscVcoCoarse") * 127)
    s["lfo_vcf"] = c127(flip(p, "ModulationsHandler_ModSubOscVcfCutoff") * 127)
    # the CS-80's own chorus / tremolo
    if g("Cs80Chorus_Tremolo") >= 0.5:
        s["cho_mode"] = 2
    elif g("Cs80Chorus_Chorus") >= 0.5:
        s["cho_mode"] = 1
    else:
        s["cho_mode"] = 0
    s["cho_spd"] = max(1, c127(127 * g("Cs80Chorus_Speed", 0.25)))
    s["cho_depth"] = max(1, c127(127 * g("Cs80Chorus_Depth", 0.45)))
    s["rm_mod"] = c127(flip(p, "RingMod_Amount") * 127)
    s["rm_spd"] = max(1, c127(flip(p, "RingMod_Speed") * 127))
    s["rm_depth"] = c127(flip(p, "RingMod_Depth") * 127)
    s["rm_d"] = max(1, c127(flip(p, "RingMod_Decay") * 127))
    # a pressure curve so the touch-led sounds move under a sequencer too
    s["aat_delay"], s["aat_rise"], s["aat_level"] = 40, 60, 80
    # the effects, by slot type, in slot order (a later slot of the same kind wins)
    skipped = []
    if g("FX_Enable", 1) >= 0.5:
        for k in (1, 2, 3):
            ty = FX_TYPES[max(0, min(len(FX_TYPES) - 1, round(16 * g(f"FX{k}_ModuleType"))))]
            if g(f"FX{k}_Bypass", 1) < 0.5 or ty == "None":
                continue
            wet = g(f"FX{k}_Dry_Wet", 0.3)
            pre = f"FX{k}_"
            if ty == "Reverb":
                s["rv_mix"] = max(1, c127(127 * min(1.0, wet * 1.6)))
                s["rv_size"] = max(1, c127(40 + 87 * g(pre + "Reverb_Decay", 0.5)))
                s["rv_damp"] = max(1, c127(127 * g(pre + "Reverb_Damping", 0.5)))
            elif ty in ("Delay", "Tape Echo", "PS Delay"):
                key = {"Delay": "Delay", "Tape Echo": "TapeEcho", "PS Delay": "OctaverDelay"}[ty]
                s["dly_mix"] = max(1, c127(127 * min(1.0, wet * 1.3)))
                s["dly_fb"] = max(1, c127(127 * g(pre + key + "_Feedback", 0.4)))
                bars = g(pre + key + "_DelayTimeSynced", 0.375)
                if g(pre + "Delay_MidiSync", 0) >= 0.5 or g(pre + key + "_RateType", 0) >= 0.5 or ty == "PS Delay":
                    best = min(range(1, 8), key=lambda i: abs(math.log(DIVS_BARS[i] / max(bars, 1e-3))))
                    s["dly_sync"] = best
                else:
                    ms = 2 + 1998 * g(pre + key + "_DelayTimeMs", 0.3) ** 3
                    s["dly_time"] = max(1, c127(127 * math.log(max(ms, 10) / 10) / math.log(110)))
                s["dly_ping"] = 1 if g(pre + key + "_StereoMode", 0) >= 0.5 else 0
                if ty == "Tape Echo":
                    s["dly_tape"] = 70
                if ty == "PS Delay":                      # the pitch-shifted repeats: our shimmer at the interval
                    mode = g(pre + "OctaverDelay_Mode", 0.5)
                    s["rv_shift"] = 7 if abs(mode - 0.5) < 0.2 else 12
                    s["rv_shim"] = max(1, c127(127 * g(pre + "OctaverDelay_Feedback", 0.25) * 2))
            elif ty in ("Chorus", "Chorus JUN-6", "Flanger", "BL-20 Flanger"):
                if not s["cho_mode"]:
                    s["cho_mode"] = 3 if "Flanger" in ty else 1
                    s["cho_spd"] = max(1, c127(127 * (g(pre + "Juno6Chorus_RateHz", 0.25) if ty == "Chorus JUN-6" else g(pre + "Chorus_Freq", 0.25))))
                    s["cho_depth"] = max(1, c127(127 * min(1.0, 0.3 + wet)))
            elif ty == "Phaser":
                s["ph_mix"] = max(1, c127(127 * min(1.0, wet * 1.5)))
                s["ph_rate"] = max(1, c127(127 * g(pre + "Phaser_Rate", 0.3)))
                s["ph_depth"] = max(1, c127(127 * g(pre + "Phaser_Depth", 0.5)))
                s["ph_fb"] = max(1, c127(127 * g(pre + "Phaser_Feedback", 0.3)))
            else:
                skipped.append(ty)
    return s, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default=os.path.join(os.path.dirname(__file__), "converted.txt"))
    ap.add_argument("--dir", default=PRESETS)
    ap.add_argument("--all", action="store_true", help="every preset in --dir under its own name: a corpus for the randomiser, not sounds to ship")
    a = ap.parse_args()
    panels, sounds = [], []
    if a.all:
        entries = [(n, n) for n in sorted(os.listdir(a.dir)) if not n.startswith(".")]
    else:
        entries = []
        for line in open(a.list, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                entries.append(tuple(x.strip() for x in line.split("=", 1)))
    for src, ours in entries:
        meta, p = read(os.path.join(a.dir, src))
        short = ours[:9]
        i1 = len(panels); panels.append([f"{short} I"] + [round(v, 3) for v in panel(p, 1)])
        i2 = len(panels); panels.append([f"{short} II"] + [round(v, 3) for v in panel(p, 2)])
        s, skipped = sound(p, ours, i1, i2)
        sounds.append(s)
        print(f"{src:28} -> {ours:14} {meta.get('type', ''):10} skipped FX: {', '.join(skipped) or '-'}", file=sys.stderr)
    json.dump({"panels": panels, "sounds": sounds}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
