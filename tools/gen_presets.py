#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The CS-80's 22 preset tones, as the owner's manual's charts show them (pages 32-34, "Using the programmable
panels to duplicate the preset patches"), mapped onto CS-1's parameters.
   tools/gen_presets.py  ->  firmware/gen/cs1_presets.h

The chart values are the sliders' positions on their 0..10 scales, read off the scans (tools in the project's
history: an image pass, then by eye where it missed). Yamaha's own note: the panels only approximate the presets.
Every number here is to within about half a unit.

  pulse, saw   the VCO's switches (the chart's black half at the bottom = ON)
  speed pwm pw noise          PWM speed 0..10, PWM depth 0..10, pulse width 50..90 % as 0..10, noise 0..10
  hpf hres lpf lres           the filters: LOW..HIGH as 0..10
  il al fa fd fr              VCF envelope: IL 0..-5 as 0..10, AL 0..+5 as 0..10, A D R SHORT..LONG as 0..10
  vcflev sine va vd vs vr level   VCA: the filtered signal, the sine, A D S R, the level
  ibrill ilevel abrill alevel     touch response: initial (velocity) and after (pressure) brilliance and level

The mapping, with the assumptions it makes (tune these against recordings, not the chart data):
  - 0..10 is 0..127 for levels, the HPF cutoff, resonances, depths and the touch sliders.
  - The LPF slider was calibrated against a CS-80 emulation (Arturia CS-80 V, dry, C3): 1.5 rests at about 680 Hz,
    2.5 at 660 Hz (under +9 dB of resonance), 4.0 and 6.0 above a fixed roll-off near 2.3 kHz. The sine slider's
    0.5 lifts the fundamental by 4 dB there, so the chart's sine is placed on a 0.4-power curve (0.5 -> 38, 8 -> 116). So the scale is flat at the bottom and steep in the middle: interpolated through 0 -> MIDI 66, 1.5 -> 76.5,
    2.5 -> 78.5, 4.0 -> 98.5, 6.0 -> 116, 10 -> open, at C3. The filters track the keyboard 1:1.
  - PW 0..10 is 50..90 %; CS-1's PW parameter runs 50..95 %, so 0..10 -> 0..113.
  - PWM speed 0..10 is 0.1 Hz .. ~9 Hz on CS-1's exponential 0.1..40 Hz rate scale.
  - IL and AL are bipolar sliders drawn 0..10 with 5 at the centre; the full travel (-5, +5) is 48 semitones
    (4 octaves) of filter sweep. CS-1 stores them around 64, a unit a semitone: 0 -> 64 - 48, 5 -> 64, 10 -> 64 + 48.
    (Measured: the CS-80 V's brass barely sweeps at the onset, its bass starts bright and falls.)
  - Envelope times: the CS-80's attack is 1 ms .. 1 s (the manual's spec), placed on CS-1's exponential 1 ms .. 12 s
    knob. Decay and release follow the CS-80 V's curve, measured as the time to -40 dB: 2 -> 40 ms, 4.5 -> 1.5 s,
    7 -> 3.3 s, 10 -> 10 s (interpolated in log time). Sustain is a square law: 3 sits 21 dB below the peak.
  - Feet: the charts carry no feet setting (a performance control): every tone is 8'.
"""
import math
from pathlib import Path

# name, pulse, saw, speed pwm pw noise, hpf hres lpf lres, il al fa fd fr, vcflev sine va vd vs vr level, ibrill ilevel abrill alevel
TONES = [
    ("STRING 1",       0, 1,  1.0, 0.5, 0.5, 0,   4.5, 8.5, 6.0, 8.0,   7.0, 6.0, 6.0, 4.0, 2.5,   9.5, 0,   5.5, 9.5, 6.0, 2.5, 9.5,   4.5, 9.5, 0, 0),
    ("STRING 2",       0, 1,  1.5, 1.0, 1.0, 1.0, 5.0, 1.0, 10,  0.5,   0.5, 0.5, 0.5, 0.5, 0.5,   10,  0.5, 0.5, 10,  10,  2.0, 10,    0, 1.5, 0, 9.5),
    ("STRING 3",       0, 1,  0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 10,  0,     0, 0, 0, 0, 0,             9.5, 0,   7.0, 6.5, 9.0, 3.0, 9.5,   0, 4.0, 0, 8.5),
    ("STRING 4",       0, 1,  0.5, 0.5, 0.5, 0.5, 3.5, 0,   6.0, 0,     4.0, 4.0, 4.0, 6.0, 2.0,   9.5, 0,   4.5, 6.0, 9.0, 2.5, 9.5,   2.0, 0, 5.5, 9.0),
    ("BRASS 1",        0, 1,  0, 0, 0, 0,         0, 0, 4.0, 4.5,       7.0, 7.5, 8.0, 7.0, 2.5,   10,  0.5, 5.5, 10,  10,  2.0, 10,    2.0, 10,  5.5, 7.0),
    ("BRASS 2",        0, 1,  0, 0, 0, 0,         0, 0, 6.0, 2.5,       8.0, 5.5, 8.0, 6.0, 3.5,   10,  0,   7.0, 6.0, 8.0, 1.5, 10,    3.5, 0, 6.0, 10),
    ("FLUTE",          0, 1,  0, 0, 0, 0,         0, 0, 4.0, 10,        0, 0, 0, 0, 0,             9.5, 0,   6.0, 9.5, 9.5, 2.0, 9.5,   2.0, 7.0, 2.0, 9.5),
    ("BRASS 3",        0, 1,  0, 0, 0, 0,         0, 0, 4.0, 7.0,       6.0, 7.0, 4.0, 4.5, 2.5,   10,  0.5, 4.5, 6.0, 5.5, 2.5, 10,    3.0, 6.0, 4.5, 10),
    ("ELECTRIC PIANO", 1, 0,  0, 0, 4.0, 0,       0, 0, 3.0, 2.0,       6.0, 6.0, 0, 6.0, 2.0,     9.5, 0,   0, 4.0, 4.0, 4.0, 7.5,     3.0, 9.5, 0, 0),
    ("BASS",           1, 1,  0, 0, 6.5, 0,       0, 8.5, 2.5, 8.5,     3.0, 7.5, 0, 4.0, 2.5,     9.5, 0,   2.5, 7.0, 0, 0, 9.5,       7.5, 3.5, 0, 0),
    ("CLAVICHORD 1",   1, 0,  0, 0, 7.0, 0,       4.0, 5.0, 4.0, 4.0,   4.0, 4.5, 0, 8.0, 2.0,     9.5, 0,   0, 5.5, 4.0, 0, 7.5,       2.5, 9.5, 0, 0),
    ("CLAVICHORD 2",   1, 1,  0, 0, 9.5, 0,       2.0, 0, 1.5, 2.0,     0.5, 10,  0.5, 6.0, 4.5,   6.0, 0,   0.5, 4.5, 3.0, 2.0, 9.5,   4.0, 10,  0.5, 0.5),
    ("HARPSICHORD 1",  1, 0,  0, 0, 7.0, 0,       5.0, 2.0, 7.0, 2.0,   0, 0, 0, 0, 0,             9.5, 0,   0, 5.5, 2.0, 2.0, 9.5,     0, 9.5, 0, 0),
    ("HARPSICHORD 2",  1, 0,  0, 0, 7.0, 0,       6.0, 0, 7.0, 0,       0, 0, 0, 0, 0.5,           10,  0,   0.5, 6.0, 0.5, 0.5, 10,    0.5, 0.5, 0.5, 0.5),
    ("ORGAN 1",        0, 1,  0.5, 0.5, 0.5, 0,   3.5, 10,  3.5, 10,    0, 0, 0, 0, 0,             10,  0,   0, 0, 10,  0, 10,          0, 0, 0, 0),
    ("ORGAN 2",        1, 0,  0.5, 0.5, 0.5, 0,   0, 0, 4.0, 9.5,       0, 0, 0, 0, 0,             9.5, 0,   0, 3.0, 3.5, 0, 9.5,       0, 0, 0, 0),
    ("GUITAR 1",       1, 0,  0.5, 0.5, 6.5, 0,   4.0, 4.0, 5.0, 5.0,   4.0, 4.0, 1.0, 4.0, 3.0,   7.0, 0,   0, 5.0, 3.0, 3.0, 10,      3.0, 10,  1.5, 9.5),
    ("GUITAR 2",       0, 1,  0.5, 0.5, 2.5, 0,   2.5, 6.0, 3.0, 5.5,   7.0, 8.0, 0, 7.0, 2.0,     10,  0,   0, 6.0, 2.0, 2.0, 9.5,     2.0, 9.5, 0, 9.5),
    ("FUNKY 1",        1, 1,  5.0, 2.0, 7.0, 0,   3.0, 10,  1.0, 10,    10,  8.0, 0, 2.0, 4.0,     9.5, 0,   1.5, 3.0, 9.5, 0, 9.5,     10,  10,  10,  10),
    ("FUNKY 2",        0, 1,  0, 0, 0, 0,         4.0, 4.0, 5.0, 7.0,   8.0, 8.0, 4.0, 4.0, 0,     10,  0,   2.0, 5.5, 4.0, 0, 9.5,     4.0, 0, 0, 0),
    ("FUNKY 3",        1, 0,  7.0, 2.0, 6.0, 0,   4.0, 10,  2.5, 10,    10,  10,  10,  8.0, 3.5,   9.0, 8.0, 0, 5.0, 10,  2.0, 9.5,    9.5, 9.5, 5.0, 9.5),
    ("FUNKY 4",        0, 1,  0.5, 0.5, 0.5, 0.5, 4.0, 10,  4.0, 10,    10,  9.5, 3.0, 3.0, 2.0,   9.5, 9.5, 0, 6.0, 8.0, 0, 9.5,      9.5, 9.5, 5.5, 9.5),
]
# the CS-80's two rows of tone selectors: channel I's row, then channel II's
ROW_I = ["STRING 1", "STRING 3", "BRASS 1", "FLUTE", "ELECTRIC PIANO", "CLAVICHORD 1", "HARPSICHORD 1", "ORGAN 1", "GUITAR 1", "FUNKY 1", "FUNKY 3"]
ROW_II = ["STRING 2", "STRING 4", "BRASS 2", "BRASS 3", "BASS", "CLAVICHORD 2", "HARPSICHORD 2", "ORGAN 2", "GUITAR 2", "FUNKY 2", "FUNKY 4"]
# the buttons' colours on the panel: 0 yellow (strings, piano, bass, clavs, harpsichords, guitars), 1 red (brass),
# 2 white (flute, organs), 3 green (funky)
COLOR = {"STRING": 0, "BRASS": 1, "FLUTE": 2, "ELECTRIC": 0, "BASS": 0, "CLAVICHORD": 0, "HARPSICHORD": 0, "ORGAN": 2, "GUITAR": 0, "FUNKY": 3}

LN_RANGE = math.log(12000)       # CS-1's time knobs: 1 ms * 12000^(i/127)

def lv(v):                       # a 0..10 level, cutoff, depth -> 0..127
    return round(min(10, max(0, v)) * 12.7)
def lv_sine(v):                  # the sine slider: a 0.4-power curve, 0.5 -> 38 of 127
    return round(127 * (min(10, max(0, v)) / 10) ** 0.4)
LPF_PTS = [(0, 66), (1.5, 76.5), (2.5, 78.5), (4.0, 98.5), (6.0, 116), (10, 150)]   # chart -> MIDI at C3, measured on the CS-80 V
def cut_lp(v):                   # a 0..10 LPF slider -> the knob (MIDI 16 + knob * 15/16 at C3)
    v = min(10, max(0, v))
    for (v0, m0), (v1, m1) in zip(LPF_PTS, LPF_PTS[1:]):
        if v <= v1:
            midi = m0 + (m1 - m0) * (v - v0) / (v1 - v0)
            return round(min(127, max(0, (midi - 16) * 16 / 15)))
def t_att(v):                    # a 0..10 attack slider: 1 ms .. 1 s
    return round(127 * (v / 10 * math.log(1000)) / LN_RANGE)
DEC_PTS = [(0, 10), (2, 40), (4.5, 1500), (7, 3300), (10, 10000)]   # chart -> ms to -40 dB, measured on the CS-80 V
def t_dec(v):                    # a 0..10 decay / release slider -> the knob (1 ms .. 12 s exponential)
    v = min(10, max(0, v))
    for (v0, t0), (v1, t1) in zip(DEC_PTS, DEC_PTS[1:]):
        if v <= v1:
            ms = math.exp(math.log(t0) + (math.log(t1) - math.log(t0)) * (v - v0) / (v1 - v0))
            return round(127 * math.log(ms) / LN_RANGE)
def lv_sus(v):                   # the sustain slider: a square law (3 -> 21 dB down), as the CS-80 V has it
    return round(127 * (min(10, max(0, v)) / 10) ** 2)

out = ["/* SPDX-License-Identifier: GPL-3.0-only */",
       "/* Generated by tools/gen_presets.py from the CS-80 owner's manual's preset charts: do not edit. */",
       f"#define NTONE {len(TONES)}u",
       "static const char *const TONE_NAMES[NTONE] = {" + ", ".join(f'"{t[0]}"' for t in TONES) + "};",
       "/* chan_patch_t: feet wave pw pwm pwm_spd noise sine vcf_lv level hp_cut hp_res lp_cut lp_res",
       " *               f_il f_al f_a f_d f_r v_a v_d v_s v_r it_brill it_level at_brill at_level */",
       "static const chan_patch_t TONES[NTONE] = {"]
for (name, pulse, saw, speed, pwm, pw, noise, hpf, hres, lpf, lres, il, al, fa, fd, fr, vcflev, sine, va, vd, vs, vr, level, ibrill, ilevel, abrill, alevel) in TONES:
    wave = 2 if (pulse and saw) else (1 if pulse else 0)
    vals = [1, wave, round(pw * 11.3), lv(pwm), round(speed * 9.5), lv(noise), lv_sine(sine), lv(vcflev), lv(level),
            lv(hpf), lv(hres), cut_lp(lpf), lv(lres),
            64 + round((il - 5) * 9.6), 64 + round((al - 5) * 9.6), t_att(fa), t_dec(fd), t_dec(fr),
            t_att(va), t_dec(vd), lv_sus(vs), t_dec(vr),
            lv(ibrill), lv(ilevel), lv(abrill), lv(alevel)]
    out.append("    {" + ", ".join(str(v) for v in vals) + "},   /* " + name + " */")
out.append("};")
def row(names):
    return "{" + ", ".join(str([t[0] for t in TONES].index(n)) for n in names) + "}"
out.append(f"static const uint8_t TONE_ROW[2][11] = {{{row(ROW_I)}, {row(ROW_II)}}};   /* the CS-80's two rows of buttons */")
out.append("static const uint8_t TONE_COLOR[NTONE] = {" + ", ".join(str(COLOR[t[0].split()[0]]) for t in TONES) + "};   /* 0 yellow 1 red 2 white 3 green */")
Path(__file__).resolve().parents[1].joinpath("firmware/gen/cs1_presets.h").write_text("\n".join(out) + "\n")
print("firmware/gen/cs1_presets.h written")
