#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The reference page of the site, from the firmware itself: every page's four parameters as PAGES in
firmware/src/cs1.c lists them, with a line each from DESC below, and the sounds as SOUNDS lists them.
   tools/gen_docs.py > build/site/reference.html"""
import html
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "firmware" / "src" / "cs1.c"
s = SRC.read_text()

# ---- the pages
pages = []
block = s[s.index("static const page_t PAGES[NPAGE]"):s.index("};", s.index("static const page_t PAGES[NPAGE]"))]
for m in re.finditer(r'\{"([^"]+)",\s*\{(.*?)\}\},', block, re.S):
    title, body = m.group(1), m.group(2)
    params = []
    for pm in re.finditer(r'(CH|GL|ST)\((\w+), "([^"]+)", (\d+), (K_\w+), (C\w), "([^"]*)", "([^"]*)"\)|NONE', body):
        if pm.group(0) == "NONE":
            continue
        params.append({"scope": pm.group(1), "field": pm.group(2), "name": pm.group(3), "max": int(pm.group(4)),
                       "kind": pm.group(5), "color": pm.group(6), "hi": pm.group(7), "lo": pm.group(8)})
    pages.append((title, params))

CAP = {"CW": "w", "CG": "g", "CR": "r", "CK": "k", "CY": "y", "CS": "s"}
GROUP = {"TONES": "HOME", "VCO": "EDIT", "VCO 2": "EDIT", "VCF": "EDIT", "VCF EG": "EDIT", "VCA EG": "EDIT", "VCA": "EDIT", "TOUCH": "EDIT",
         "SUB OSC": "LFO", "SUB OSC 2": "LFO", "TOUCH RESP": "LFO", "AUTO AT": "LFO", "PERFORM": "ARP", "KEYBOARD": "ARP", "SUSTAIN": "ARP",
         "RING MOD": "FX", "CHORUS": "FX", "DELAY": "FX", "DELAY 2": "FX", "REVERB": "FX", "PHASER": "FX", "MAIN": "GLO", "MIDI": "GLO"}
PAGE_NOTE = {
    "TONES": "The HOME page: the two rows of tone buttons, the sound's name, and the lower panel's performance levers.",
    "VCO": "The oscillator of the channel being edited (SEL picks I or II). The CS-80's VCO section.",
    "VCO 2": "The rest of the VCO section and the two source levels of the VCA section: how much of the filtered signal and of the pure sine reaches the amplifier.",
    "VCF": "The channel's two filters in series: a high-pass into a low-pass, 12 dB an octave each, with their own resonance.",
    "VCF EG": "The filter envelope. It has no sustain: it starts at IL, reaches AL over the attack, falls back to the resting cutoff over the decay, and on release returns to IL over VCF R (VCA page).",
    "VCA EG": "The amplifier's envelope: attack, decay, sustain, release.",
    "VCA": "The filter envelope's release and the channel's level.",
    "TOUCH": "Touch response: how velocity (initial) and pressure (after) brighten and louden the channel. Pressure comes from aftertouch, the expression CC, or the auto after touch curve.",
    "SUB OSC": "The sub oscillator, the CS-80's LFO, for all voices: its function (shape), speed and how much goes to pitch and filter.",
    "SUB OSC 2": "The sub oscillator to the amplifier (tremolo), and its sync to MIDI clock.",
    "TOUCH RESP": "The performance touch levers: the initial pitch bend (a note starts below pitch and slides up, by velocity) and pressure into the sub oscillator's speed, pitch depth and filter depth.",
    "AUTO AT": "A pressure curve every note plays by itself, for when nothing sends aftertouch: a wait, a rise to a level, a fall after the key goes. SEQ switches it on and off.",
    "PERFORM": "Portamento and glissando, channel II's detune, and VINTAGE: each voice drifting a few cents of its own.",
    "KEYBOARD": "Keyboard control: brilliance and level tilted towards the low or the high end of the keyboard. Nothing at middle C, full effect three octaves out.",
    "SUSTAIN": "Mode I sustains every note on its own; mode II ends the sustain of the chord before when a new one is played.",
    "RING MOD": "The ring modulator on both channels' sum: a sine carrier, its rate pushed up by an attack / decay envelope at every note.",
    "CHORUS": "The ring modulator's envelope decay, and the chorus / tremolo: the CS-80's slow phasing tremolo between left and right (stereo here).",
    "DELAY": "A stereo delay, with SYNC overriding TIME in note divisions of the MIDI clock.",
    "DELAY 2": "The delay's ping-pong, the damping in its feedback, its sync, and TAPE: the character of a tape echo.",
    "PHASER": "A six-stage phaser, the right side a quarter turn behind the left. Not on the CS-80; of its era.",
    "REVERB": "A plate after Dattorro: diffused input, two cross-coupled tanks with slowly wandering allpasses, damping in the loop. With a shimmer: the output fed back an octave up.",
    "MAIN": "The lower panel's levers: brilliance and resonance offsets for every filter, TONE, the output level. TONE is an instrument setting rather than part of a sound.",
    "MIDI": "The channel listened to, which CC acts as pressure, program change on or off, and the learned CC bindings (turn down to clear).",
}
DESC = {
    ("TONES", "BRILL"): "Opens or closes every filter: a global cutoff offset.", ("TONES", "RESO"): "More or less resonance on every filter.",
    ("TONES", "MIX"): "The balance between channel I (left) and II (right); both at the middle.", ("TONES", "VOLUME"): "The output level before the master knob.",
    ("VCO", "FEET"): "The channel's octave: 16', 8' (concert pitch), 4', 2'.", ("VCO", "WAVE"): "Sawtooth, pulse, or both.",
    ("VCO", "PW"): "The pulse's width, 50 % (square) to 90 %.", ("VCO", "PWM"): "How far the pulse width is swept by the channel's own PWM oscillator.",
    ("VCO 2", "SPEED"): "The PWM oscillator's rate.", ("VCO 2", "NOISE"): "White noise mixed in before the filters.",
    ("VCO 2", "VCF"): "The filtered signal's level into the amplifier.", ("VCO 2", "SINE"): "The pure sine's level into the amplifier: it bypasses the filters, so it adds body the filter cannot take away.",
    ("VCF", "HPF"): "The high-pass filter's cutoff.", ("VCF", "RES.H"): "Its resonance.", ("VCF", "LPF"): "The low-pass filter's cutoff.", ("VCF", "RES.L"): "Its resonance. Neither filter self-oscillates, as on the CS-80.",
    ("VCF EG", "IL"): "Initial level: where the cutoff starts at a note, below (−) or above (+) its resting setting.", ("VCF EG", "AL"): "Attack level: where the attack takes it before the decay brings it back.",
    ("VCF EG", "A"): "Attack time, 1 ms to 12 s.", ("VCF EG", "D"): "Decay time.",
    ("VCA EG", "A"): "Attack time.", ("VCA EG", "D"): "Decay time.", ("VCA EG", "S"): "Sustain level.", ("VCA EG", "R"): "Release time.",
    ("VCA", "VCF R"): "The filter envelope's release: how long the cutoff takes to return to IL after the key goes.", ("VCA", "LEVEL"): "The channel's level.",
    ("TOUCH", "I.BRIL"): "Initial brilliance: velocity opens the filters.", ("TOUCH", "I.LEV"): "Initial level: velocity sets the loudness. At 0 velocity has no effect, as on the CS-80.",
    ("TOUCH", "A.BRIL"): "After brilliance: pressure opens the filters, up to three octaves.", ("TOUCH", "A.LEV"): "After level: the note sits 6 dB down until pressed, at full.",
    ("SUB OSC", "FUNC"): "The shape: sine, triangle, sawtooth, inverted sawtooth, square.", ("SUB OSC", "SPEED"): "Its rate, 0.1 to 40 Hz.",
    ("SUB OSC", "VCO"): "Vibrato depth, up to two semitones.", ("SUB OSC", "VCF"): "Filter sweep depth, up to two octaves.",
    ("SUB OSC 2", "VCA"): "Tremolo depth.", ("SUB OSC 2", "SYNC"): "The cycle locked to the clock: a quarter, a half, one, two or four bars. MIDI start restarts it.",
    ("TOUCH RESP", "P.BEND"): "Initial pitch bend: the note starts up to two semitones below and slides up, more with velocity.",
    ("TOUCH RESP", "SPEED"): "Pressure speeds the sub oscillator up.", ("TOUCH RESP", "VCO"): "Pressure adds vibrato.", ("TOUCH RESP", "VCF"): "Pressure adds filter sweep.",
    ("AUTO AT", "DELAY"): "How long after the note the curve starts, up to about four seconds.", ("AUTO AT", "RISE"): "How long it takes to reach its level.",
    ("AUTO AT", "LEVEL"): "The pressure it reaches; 0 switches the curve off.", ("AUTO AT", "FALL"): "How fast it dies away after the key goes.",
    ("PERFORM", "PORTA"): "Portamento time: about two seconds an octave at full. 0 is off.", ("PERFORM", "GLISS"): "Glissando: the glide in semitone steps.",
    ("PERFORM", "DETUNE"): "Channel II sharp or flat against I, about half a semitone each way.", ("PERFORM", "VINTAG"): "Vintage: each voice wanders to a new tuning offset every second or so, up to 12 cents.",
    ("KEYBOARD", "BRIL.LO"): "Brighter (+) or darker (−) towards the bottom of the keyboard.", ("KEYBOARD", "BRIL.HI"): "The same towards the top.",
    ("KEYBOARD", "LEV.LO"): "Louder or quieter towards the bottom (it can only cut).", ("KEYBOARD", "LEV.HI"): "The same towards the top.",
    ("SUSTAIN", "MODE"): "I or II.",
    ("RING MOD", "MOD"): "How much of the ring-modulated signal replaces the plain one.", ("RING MOD", "SPEED"): "The carrier's rate, 0.5 Hz to 2 kHz: slow is a tremolo, fast is bells.",
    ("RING MOD", "DEPTH"): "How far the envelope pushes the rate up.", ("RING MOD", "ATTACK"): "The envelope's attack.",
    ("CHORUS", "R.DECAY"): "The ring modulator envelope's decay.", ("CHORUS", "MODE"): "Off, chorus (slow and wide) or tremolo (faster, deeper in level).",
    ("CHORUS", "SPEED"): "Its rate.", ("CHORUS", "DEPTH"): "Its depth.",
    ("DELAY", "TIME"): "10 ms to 1.1 s, when SYNC is FREE.", ("DELAY", "FEEDBK"): "Repeats.", ("DELAY", "MIX"): "The delay's level; 0 is off.",
    ("DELAY", "SYNC"): "FREE, or a note division of the MIDI clock that overrides TIME.",
    ("DELAY 2", "PING"): "The right side on a tap at half the time.", ("DELAY 2", "DAMP"): "A low-pass in the feedback: repeats get darker.",
    ("DELAY 2", "SYNC"): "As on the DELAY page.", ("DELAY 2", "TAPE"): "A tape echo's character: the repeats wander a little (wow and flutter), darken each pass and saturate in the feedback. 0 is the clean delay.",
    ("PHASER", "RATE"): "The sweep's speed, 0.1 to 9 Hz.", ("PHASER", "DEPTH"): "How far the sweep travels, 100 Hz to 5 kHz at full.", ("PHASER", "FEEDBK"): "Feedback round the stages: sharper notches.", ("PHASER", "MIX"): "The phased signal added to the dry; 0 is off.",
    ("DELAY 2", "TEMPO"): "The tempo the clock gives, in brackets when no clock has arrived for two seconds (120 at power-on).",
    ("REVERB", "MIX"): "The reverb's level; 0 is off.", ("REVERB", "SIZE"): "The decay, half a second to about 25 s.",
    ("REVERB", "DAMP"): "Darkens the tail.", ("REVERB", "SHIMMR"): "Feeds the tail back an octave up: it climbs in octaves. Its loop never runs away.",
    ("MAIN", "BRILL"): "As on HOME.", ("MAIN", "RESO"): "As on HOME.", ("MAIN", "TONE"): "A gentle 12 dB per octave roll-off above the filters, as the instrument's output stage has it: off at 0, 2.4 kHz at 100 (the CS-80 V's, measured), 1.6 kHz at full. It takes the glass off the sawtooth; BRILL on HOME still opens the filters under it.", ("MAIN", "VOLUME"): "As on HOME.",
    ("MIDI", "CHAN"): "OMNI, or a channel 1 to 16.", ("MIDI", "EXPR"): "AT only, or a CC number that also acts as pressure (CC 1 by default).",
    ("MIDI", "PROG"): "Program change on or off.", ("MIDI", "LEARNS"): "How many CCs are bound to parameters; turn it down to 0 to clear them.",
}

# ---- the sounds
sounds = []
block = s[s.index("static const sound_t SOUNDS[] = {"):s.index("\n};", s.index("static const sound_t SOUNDS[] = {"))]
group = ""
for line in block.splitlines():
    g = re.match(r"\s*/\* ---- (.*?) \*/", line)
    if g: group = g.group(1)
    m = re.search(r'\.name = "([^"]+)", \.tone = \{T_(\w+), T_(\w+)\}', line)
    if m: sounds.append((group, m.group(1), m.group(2), m.group(3)))
TONE = {"STR1": "String 1", "STR2": "String 2", "STR3": "String 3", "STR4": "String 4", "BRS1": "Brass 1", "BRS2": "Brass 2", "BRS3": "Brass 3", "FLUTE": "Flute",
        "EPIANO": "Electric Piano", "BASS": "Bass", "CLAV1": "Clavichord 1", "CLAV2": "Clavichord 2", "HARP1": "Harpsichord 1", "HARP2": "Harpsichord 2",
        "ORG1": "Organ 1", "ORG2": "Organ 2", "GTR1": "Guitar 1", "GTR2": "Guitar 2", "FNK1": "Funky 1", "FNK2": "Funky 2", "FNK3": "Funky 3", "FNK4": "Funky 4"}
SOUND_NOTE = {
    "BLADE BRASS": "The Blade Runner brass from the presets: detuned, a slow swell, vibrato and brightness under pressure, chorus, a little glide.",
    "BR BLUES": "A high, bright, expressive lead for Blade Runner Blues: String 3 at 4' over Brass 3, pressure vibrato, a long synced ping-pong tail.",
    "BR FLUTE": "The Main Titles flute line: Flute over a quiet Organ 2 an octave down, long portamento for the glides.",
    "BR STRINGS": "The Blade Runner string pad: slow, chorused, a touch of shimmer.",
    "CHARIOTS": "Chariots of Fire brass with its echo, synced to dotted eighths.",
    "UNKNOWN MAN": "To the Unknown Man: a brass lead with deep pressure vibrato.",
    "BR BRASS 2": "Syntorial's documented recipe: two 50 % pulses an octave apart and 6 cents off, PWM at ~4 Hz, a 650 ms filter swell falling over 10 s.",
    "BRASS SWELL": "MusicTech's brass swell: two saws at 60 / 40, a third of the filter range over a second, tape-style delay (a 10 s reverb is set up; add MIX).",
    "BR BLUES 2": "Blade Runner Blues as a player set it on the Arturia: Brass 1 + 2 with the performance side up.",
    "END TITLES": "The End Titles' sequenced bass: two saws an octave apart under the filter envelope. Sequence it.",
    "CHIMES": "The manual's Bells & Gongs: Flute + Bass at 4' with the ring modulator fully in.",
    "AFRICA": "Africa: String 1 + String 4, channel I forward, brilliance down, resonance up, sparing chorus (Reverb Machine).",
    "AFRICA 2": "Syntorial's Africa: a saw into a half-closed filter, the amplitude decaying over 10 s.",
    "ROSANNA": "Rosanna's brass pad.",
    "HUMAN NATURE": "Human Nature: String 1 + Brass 2, resonance high, a long release on I, and the glide chromatic (GLISS), as Porcaro played it.",
    "BILLIE JEAN": "Billie Jean's chord vamp: the same pair without the glide.",
    "BILLIE KEYS": "Syntorial's Billie Jean keys: a narrow pulse with PWM at a quarter note and a short filter blip.",
    "BORN USA": "Born in the U.S.A.'s intro chords: bright brass over strings.",
    "XMAS BASS": "Wonderful Christmastime: the Bass preset alone, the sub oscillator's inverted saw into the filter at ~3 Hz, resonance up.",
    "WHO BASS": "The 1980 Doctor Who bass: Bass at 16' and 8', resonant, with an envelope snap.",
    "BABOOSHKA": "Babooshka's intro lead: a flute with glide and vibrato.",
    "DUCHESS": "Genesis' Duchess: strings with a slow glide.",
    "TURN IT ON": "Turn It On Again: a punchy brass line.",
    "TIME STRINGS": "ELO's Time: thick chorused strings, slow attack.",
    "VIENNA": "Ultravox: cold strings over brass, a synced echo.",
    "OXYGENE": "Jarre: a PWM string pad with a slow filter sweep and a wide chorus.",
    "ENO WASH": "Eno's wash: a dark pad with a very long attack and a huge, dark reverb with shimmer set up on the REVERB page (add MIX).",
    "WALKING": "Walking on a Dream: a saw with a PWM square through a bandpass, the chorus fast and deep.",
    "4001 PLUCK": "Squarepusher's 4001 pluck, as documented: both filters on, resonance up, a short filter decay, a long release.",
    "4001 STRINGS": "4001's strings: an octave apart, filters open, brilliance up, vibrato at 4 Hz.",
    "LONG BRASS": "Metric's slow brass: a long attack, the filter opening under pressure.",
    "SHRIEK LEAD": "Jesper Kyd's high, screaming lead: Funky 3 at 2'.",
    "SQUELCH BASS": "Dillinger's squelchy bass.",
    "TRUMPET": "The manual's trumpet: a saw with IL and AL fully apart.", "CLARINET": "The manual's clarinet: a 50 % square into a half-open filter.",
    "OBOE": "The manual's oboe: a 90 % pulse through a narrow bandpass.", "TIMPANI": "The manual's timpani: a noise mallet over a 16' drum.",
}

out = []
w = out.append
w('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">')
w('<title>CS-1 reference</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&family=Barlow+Semi+Condensed:wght@600;700&display=swap"><link rel="stylesheet" href="site.css"></head><body><main>')
w('<header><h1><a href="./">CS-1</a></h1><p>reference: every page, every sound</p><nav><a href="manual.html">Manual</a><a href="sound.html">Sound design</a><a href="emu/">Play it</a><a href="https://github.com/twochannels/CS-1">Source</a></nav></header>')
w('<p class="note">Generated from the firmware\'s own page table, so what is here is what the screen shows. The cap colour is the slider\'s on the screen, following the CS-80\'s panel; the legends are the slider\'s ends.</p>')
w('<h2 id="pages">The pages</h2><ul class="toc">')
for title, params in pages:
    w(f'<li><a href="#p-{html.escape(title).replace(" ", "-")}">{html.escape(title)}</a> <small>({GROUP.get(title, "")})</small></li>')
w('</ul>')
for title, params in pages:
    w(f'<h3 id="p-{html.escape(title).replace(" ", "-")}">{html.escape(title)} <small>· {GROUP.get(title, "")}</small></h3>')
    if title in PAGE_NOTE: w(f'<p>{html.escape(PAGE_NOTE[title])}</p>')
    w('<table><tr><th>Knob</th><th>Name</th><th>Range</th><th>What it does</th></tr>')
    for i, p in enumerate(params):
        rng = f'{p["lo"]} … {p["hi"]}' if p["hi"] or p["lo"] else {"K_FEET": "16' 8' 4' 2'", "K_WAVE": "SAW PULSE BOTH", "K_LWAVE": "SINE TRI SAW SAW DN SQR", "K_ONOFF": "OFF ON",
                                                                  "K_CHO": "OFF CHORUS TREM", "K_DIV": "FREE 1/16 … 1/2", "K_LDIV": "FREE 1/4 … 4 BAR", "K_SUS": "I II", "K_TEMPO": "(read-only)"}.get(p["kind"], "0 … 127")
        scope = {"CH": "channel", "GL": "global", "ST": "setting"}[p["scope"]]
        w(f'<tr><td class="k">KNOB {i + 1}</td><td class="k"><span class="cap {CAP[p["color"]]}"></span>{html.escape(p["name"])}</td><td>{html.escape(rng)}<br><small>{scope}</small></td><td>{html.escape(DESC.get((title, p["name"]), ""))}</td></tr>')
    w('</table>')
w('<h2 id="sounds">The sounds</h2><p>In PRESETS order, which is also the program change number. Each pairs a row I tone with a row II tone, as the instrument does. The classic ones are recipes after what is documented about the records, not transcriptions: a guide to the character.</p>')
w('<table><tr><th>#</th><th>Sound</th><th>Channel I</th><th>Channel II</th><th>Notes</th><th></th></tr>')
last = ""
for i, (group, name, t1, t2) in enumerate(sounds):
    if group != last:
        w(f'<tr><th colspan="6">{html.escape(group)}</th></tr>'); last = group
    w(f'<tr><td>{i}</td><td class="k">{html.escape(name)}</td><td>{TONE[t1]}</td><td>{TONE[t2]}</td><td>{html.escape(SOUND_NOTE.get(name, ""))}</td><td><a class="try" href="emu/?sound={i}">Try</a></td></tr>')
w('</table>')
w('<footer><small>CS-1 is GPL-3.0; M-VAVE and FM-1 are their owners\' marks, CS-80 is Yamaha\'s. CS-1 is affiliated with none of them.</small></footer></main></body></html>')
print("\n".join(out))
