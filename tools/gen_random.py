#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The randomiser's model, from the corpus of sounds, into firmware/gen/cs1_random.h.

Every sound is a point in the patch's 107 dimensions (device units, 0..127). The model is the mean of each
category, the directions the corpus varies along together (a principal component analysis: K unit vectors), and
how far each category spreads along each of them. On the device a roll is a category's mean plus a random amount
along every direction, scaled by that category's spread and the AMOUNT knob, then rounded, clamped and put through
a few hard rules (cs1.c: roll()). So a rolled pad has a pad's envelopes, filter and effects drawn together, never
one setting alone.

   tools/gen_random.py [--shipped build/host/shipped.jsonl] [--arturia ...arturia_corpus.json] [--arminator ...arminator.json]

The shipped sounds come from tests/dump_sounds.c (device units, hand categories); the two libraries from their
readers (chart panels and sound records, mapped here as gen_presets.py / sound_load would). A library that is not
on this computer is skipped. Nothing of the libraries themselves is written: only means and directions."""
import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gen_presets as G  # noqa: E402  (its import regenerates the presets header, unchanged)

CATS = ["ALL", "PAD", "STRINGS", "BRASS", "KEYS", "BELLS", "BASS", "LEAD", "FX", "USER"]
K = 12

# ---- the patch layout, read from the source so it cannot drift
src = (ROOT / "firmware/src/cs1_voice.h").read_text()
def fields(block):
    out = []
    for line in block.splitlines():
        m = re.match(r"\s*uint8_t (.*?);", line)
        if m:
            out += [f.strip() for f in m.group(1).split(",")]
    return out
CHAN = fields(src[src.index("typedef struct {                  /* a channel"):src.index("} chan_patch_t;")])
GLOB = fields(src[src.index("typedef struct {\n    chan_patch_t ch[NCH];"):src.index("} patch_t;")])
FIELDS = [f"ch0.{f}" for f in CHAN] + [f"ch1.{f}" for f in CHAN] + GLOB
N = len(FIELDS)
EFFECT = {"rm_mod", "rm_spd", "rm_depth", "rm_a", "rm_d", "cho_mode", "cho_spd", "cho_depth", "dly_time", "dly_fb", "dly_mix",
          "dly_ping", "dly_damp", "rv_mix", "rv_size", "rv_damp", "rv_shim", "rv_shift", "dly_sync", "dly_tape", "ph_rate",
          "ph_depth", "ph_fb", "ph_mix", "drive", "eq_lo", "eq_hi", "drive_lv"}
GROUP = [0 if f.startswith("ch") else 2 if f in EFFECT else 1 for f in FIELDS]   # 0 the tones, 1 the globals, 2 the effects
# the categorical fields and their last value: rounded and clamped after a roll
CATEGORICAL = {"feet": 5, "wave": 2, "lfo_wave": 5, "cho_mode": 3, "dly_sync": 7, "gliss": 1, "dly_ping": 1, "unison": 1, "lfo_sync": 5}
CAT_MAX = [CATEGORICAL.get(f.split(".")[-1], 127) for f in FIELDS]

DEF = dict(lfo_spd=60, brill=64, reso=64, volume=100, detune=64, at_vco=30, rm_spd=64, rm_a=10, rm_d=60, cho_spd=30, cho_depth=60,
           aat_rise=60, aat_fall=40, dly_time=70, dly_fb=50, dly_damp=40, rv_size=80, rv_damp=50, rv_shift=12, mix=64, vintage=30,
           kb_bl=64, kb_bh=64, kb_ll=64, kb_lh=64, ph_rate=40, ph_depth=64, ph_fb=40, eq_lo=64, eq_hi=64, drive_lv=64)


def chan_from_chart(row, feet, level):
    (pulse, saw, speed, pwm, pw, noise, hpf, hres, lpf, lres, il, al, fa, fd, fr, vcflev, sine, va, vd, vs, vr, lvl, ib, il2, ab, al2) = row
    wave = 2 if (pulse and saw) else (1 if pulse else 0)
    return dict(feet=feet, wave=wave, pw=round(pw * 11.3), pwm=G.lv(pwm), pwm_spd=round(speed * 9.5), noise=G.lv(noise),
                sine=G.lv_sine(sine), vcf_lv=G.lv(vcflev), level=level, hp_cut=G.lv(hpf), hp_res=G.lv(hres), lp_cut=G.cut_lp(lpf),
                lp_res=G.lv(lres), f_il=64 + round((il - 5) * 9.6), f_al=64 + round((al - 5) * 9.6), f_a=G.t_att(fa), f_d=G.t_dec(fd),
                f_r=G.t_dec(fr), v_a=G.t_att(va), v_d=G.t_dec(vd), v_s=G.lv_sus(vs), v_r=G.t_dec(vr), it_brill=G.lv(ib),
                it_level=G.lv(il2), at_brill=G.lv(ab), at_level=G.lv(al2))


def patch_from(panels, s):
    """a library sound (two chart panels + a sound record) as device units, the way sound_load fills the patch"""
    feet = [(s.get("feet1", [0, 0])[c] - 1) if s.get("feet1", [0, 0])[c] else 1 for c in range(2)]
    level = [s.get("level", [0, 0])[c] or 110 for c in range(2)]
    ch = [chan_from_chart(panels[s["tone"][c]][1:], feet[c], level[c]) for c in range(2)]
    for c in range(2):
        for f in ("at_brill", "v_a", "v_r"):
            if s.get(f):
                ch[c][f] = s[f]
    vec = []
    for c in range(2):
        vec += [ch[c][f] for f in CHAN]
    for f in GLOB:
        v = s.get(f, 0)
        vec.append(v if v else DEF.get(f, 0))
    return [max(0, min(127, int(v))) for v in vec]


NAME_CAT = [("string", "STRINGS"), ("brass", "BRASS"), ("horn", "BRASS"), ("trump", "BRASS"), ("flute", "BRASS"), ("bell", "BELLS"),
            ("chime", "BELLS"), ("glock", "BELLS"), ("bass", "BASS"), ("lead", "LEAD"), ("solo", "LEAD"), ("pad", "PAD"), ("wash", "PAD"),
            ("atmo", "PAD"), ("choir", "PAD"), ("drone", "PAD"), ("organ", "KEYS"), ("piano", "KEYS"), ("keys", "KEYS"), ("clav", "KEYS"),
            ("pluck", "KEYS"), ("harp", "KEYS"), ("sfx", "FX"), ("fx", "FX"), ("noise", "FX"), ("siren", "FX"), ("pod", "FX"), ("street", "FX"),
            ("arp", "KEYS"), ("seq", "KEYS")]
def cat_of_name(name):
    n = name.lower()
    for key, cat in NAME_CAT:
        if key in n:
            return cat
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shipped", default=str(ROOT / "build/host/shipped.jsonl"))
    ap.add_argument("--arturia", default=os.path.expanduser("~/Documents/Projects/CS1/arturia_corpus.json"))
    ap.add_argument("--arminator", default=os.path.expanduser("~/Documents/Projects/CS1/arminator/arminator.json"))
    a = ap.parse_args()
    X, C, origin = [], [], []
    for line in open(a.shipped):
        r = json.loads(line)
        assert len(r["patch"]) == N, (len(r["patch"]), N)
        X.append(r["patch"]); C.append(r["cat"]); origin.append("shipped")
    for path, tag in ((a.arturia, "arturia"), (a.arminator, "arminator")):
        if not os.path.exists(path):
            print(f"  (no {tag} corpus at {path})", file=sys.stderr); continue
        d = json.load(open(path))
        for s in d["sounds"]:
            X.append(patch_from(d["panels"], s)); C.append(s.get("cat") or cat_of_name(s["name"])); origin.append(tag)
    X = np.array(X, float) / 127.0
    print(f"corpus: {len(X)} sounds ({', '.join(f'{origin.count(t)} {t}' for t in ('shipped', 'arturia', 'arminator'))}), {sum(1 for c in C if c)} with a category", file=sys.stderr)
    mu = X.mean(axis=0)
    U, S, Vt = np.linalg.svd(X - mu, full_matrices=False)
    comps = Vt[:K]
    var = (S ** 2) / (S ** 2).sum()
    print(f"the first {K} directions carry {var[:K].sum() * 100:.0f} % of the variance ({' '.join(f'{v * 100:.0f}' for v in var[:K])})", file=sys.stderr)
    proj = (X - mu) @ comps.T
    means, sigs = [], []
    for cat in CATS:
        sel = np.array([c == cat for c in C]) if cat not in ("ALL", "USER") else np.ones(len(X), bool)
        n = int(sel.sum())
        m = X[sel].mean(axis=0) if n >= 8 else mu
        sg = proj[sel].std(axis=0) if n >= 8 else proj.std(axis=0)
        means.append(m); sigs.append(sg)
        print(f"  {cat:8} {n:4} sounds, spread along the directions: {' '.join(f'{v:.2f}' for v in sg[:6])}", file=sys.stderr)
    out = ["/* SPDX-License-Identifier: GPL-3.0-only */",
           f"/* Generated by tools/gen_random.py from {len(X)} sounds: do not edit. The randomiser's model: a mean a category, {K} directions",
           " * the corpus varies along together (unit vectors, x127), and each category's spread along them (in 1/127 of the field's",
           " * range). A roll: mean + sum over k of z_k x spread_k x direction_k, z_k gaussian times AMOUNT. */",
           f"#define RND_N {N}u", f"#define RND_K {K}u", f"#define RND_NCAT {len(CATS)}u",
           "static const uint8_t RND_GROUP[RND_N] = {" + ", ".join(str(g) for g in GROUP) + "};   /* 0 a tone's, 1 global, 2 an effect's */",
           "static const uint8_t RND_MAX[RND_N] = {" + ", ".join(str(g) for g in CAT_MAX) + "};   /* the categorical fields' last value */",
           "static const uint8_t RND_MEAN[RND_NCAT][RND_N] = {"]
    for cat, m in zip(CATS, means):
        out.append("    {" + ", ".join(str(int(round(v * 127))) for v in m) + "},   /* " + cat + " */")
    out.append("};")
    out.append("static const int8_t RND_COMP[RND_K][RND_N] = {")
    for k in range(K):
        out.append("    {" + ", ".join(str(int(round(v * 127))) for v in comps[k]) + "},")
    out.append("};")
    out.append("static const uint8_t RND_SIG[RND_NCAT][RND_K] = {")
    for cat, sg in zip(CATS, sigs):
        out.append("    {" + ", ".join(str(min(255, int(round(v * 127)))) for v in sg) + "},   /* " + cat + " */")
    out.append("};")
    (ROOT / "firmware/gen/cs1_random.h").write_text("\n".join(out) + "\n")
    print(f"firmware/gen/cs1_random.h written: {sum(len(l) for l in out)} chars", file=sys.stderr)


if __name__ == "__main__":
    main()
