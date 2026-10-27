# The editor link (SysEx)

The browser editor talks to CS-1 over SysEx, on USB (both ways) or the TRS jack (into the FM-1 only). The firmware's
side is `firmware/src/cs1_editor.h`; this page and the editor's map (`build/editor/cs1_map.json`) are generated from
the firmware by `tools/gen_editor_map.py`.

## Frames

Every frame is `F0 7D 43 53 31 <cmd> <data> F7`: `7D` is MIDI's non-commercial ID, `43 53 31` is "CS1". Every data
byte is 0..127, and the patch travels as its 107 bytes, unchanged (every one is a knob's value).

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

107 bytes: channel I's 26, channel II's 26, then the globals. "Page · knob" is where it is on the FM-1.

| offset | field | page · knob | range |
| --- | --- | --- | --- |
| 0 | `ch[0].feet` | VCO · FEET | 0..5 (0 16', 1 8', 2 5.3', 3 4', 4 2.7', 5 2') |
| 1 | `ch[0].wave` | VCO · WAVE | 0..2 (0 SAW, 1 PULSE, 2 BOTH) |
| 2 | `ch[0].pw` | VCO · PW | 0..127 |
| 3 | `ch[0].pwm` | VCO · PWM | 0..127 |
| 4 | `ch[0].pwm_spd` | VCO 2 · SPEED | 0..127 |
| 5 | `ch[0].noise` | VCO 2 · NOISE | 0..127 |
| 6 | `ch[0].sine` | VCA · SINE | 0..127 |
| 7 | `ch[0].vcf_lv` | VCA · VCF | 0..127 |
| 8 | `ch[0].level` | VCA · LEVEL | 0..127 |
| 9 | `ch[0].hp_cut` | VCF · HPF | 0..127 |
| 10 | `ch[0].hp_res` | VCF · RES.H | 0..127 |
| 11 | `ch[0].lp_cut` | VCF · LPF | 0..127 |
| 12 | `ch[0].lp_res` | VCF · RES.L | 0..127 |
| 13 | `ch[0].f_il` | VCF EG · IL | 0..127 (64 = centre) |
| 14 | `ch[0].f_al` | VCF EG · AL | 0..127 (64 = centre) |
| 15 | `ch[0].f_a` | VCF EG · A | 0..127 |
| 16 | `ch[0].f_d` | VCF EG · D | 0..127 |
| 17 | `ch[0].f_r` | VCA · VCF R | 0..127 |
| 18 | `ch[0].v_a` | VCA EG · A | 0..127 |
| 19 | `ch[0].v_d` | VCA EG · D | 0..127 |
| 20 | `ch[0].v_s` | VCA EG · S | 0..127 |
| 21 | `ch[0].v_r` | VCA EG · R | 0..127 |
| 22 | `ch[0].it_brill` | TOUCH · I.BRIL | 0..127 |
| 23 | `ch[0].it_level` | TOUCH · I.LEV | 0..127 |
| 24 | `ch[0].at_brill` | TOUCH · A.BRIL | 0..127 |
| 25 | `ch[0].at_level` | TOUCH · A.LEV | 0..127 |
| 26 | `ch[1].feet` | VCO · FEET | 0..5 (0 16', 1 8', 2 5.3', 3 4', 4 2.7', 5 2') |
| 27 | `ch[1].wave` | VCO · WAVE | 0..2 (0 SAW, 1 PULSE, 2 BOTH) |
| 28 | `ch[1].pw` | VCO · PW | 0..127 |
| 29 | `ch[1].pwm` | VCO · PWM | 0..127 |
| 30 | `ch[1].pwm_spd` | VCO 2 · SPEED | 0..127 |
| 31 | `ch[1].noise` | VCO 2 · NOISE | 0..127 |
| 32 | `ch[1].sine` | VCA · SINE | 0..127 |
| 33 | `ch[1].vcf_lv` | VCA · VCF | 0..127 |
| 34 | `ch[1].level` | VCA · LEVEL | 0..127 |
| 35 | `ch[1].hp_cut` | VCF · HPF | 0..127 |
| 36 | `ch[1].hp_res` | VCF · RES.H | 0..127 |
| 37 | `ch[1].lp_cut` | VCF · LPF | 0..127 |
| 38 | `ch[1].lp_res` | VCF · RES.L | 0..127 |
| 39 | `ch[1].f_il` | VCF EG · IL | 0..127 (64 = centre) |
| 40 | `ch[1].f_al` | VCF EG · AL | 0..127 (64 = centre) |
| 41 | `ch[1].f_a` | VCF EG · A | 0..127 |
| 42 | `ch[1].f_d` | VCF EG · D | 0..127 |
| 43 | `ch[1].f_r` | VCA · VCF R | 0..127 |
| 44 | `ch[1].v_a` | VCA EG · A | 0..127 |
| 45 | `ch[1].v_d` | VCA EG · D | 0..127 |
| 46 | `ch[1].v_s` | VCA EG · S | 0..127 |
| 47 | `ch[1].v_r` | VCA EG · R | 0..127 |
| 48 | `ch[1].it_brill` | TOUCH · I.BRIL | 0..127 |
| 49 | `ch[1].it_level` | TOUCH · I.LEV | 0..127 |
| 50 | `ch[1].at_brill` | TOUCH · A.BRIL | 0..127 |
| 51 | `ch[1].at_level` | TOUCH · A.LEV | 0..127 |
| 52 | `lfo_spd` | SUB OSC · SPEED | 0..127 |
| 53 | `lfo_wave` | SUB OSC · FUNC | 0..5 (0 SINE, 1 TRI, 2 SAW, 3 SAW DN, 4 SQR, 5 NOISE) |
| 54 | `lfo_vco` | SUB OSC · VCO | 0..127 |
| 55 | `lfo_vcf` | SUB OSC · VCF | 0..127 |
| 56 | `lfo_vca` | SUB OSC 2 · VCA | 0..127 |
| 57 | `brill` | TONES · BRILL | 0..127 (64 = centre) |
| 58 | `reso` | TONES · RESO | 0..127 (64 = centre) |
| 59 | `volume` | TONES · VOLUME | 0..127 |
| 60 | `detune` | PERFORM · DETUNE | 0..127 (64 = centre) |
| 61 | `porta` | PERFORM · PORTA | 0..127 |
| 62 | `gliss` | PERFORM · GLISS | 0..1 (0 OFF, 1 ON) |
| 63 | `pbend` | TOUCH RESP · P.BEND | 0..127 |
| 64 | `at_spd` | TOUCH RESP · SPEED | 0..127 |
| 65 | `at_vco` | TOUCH RESP · VCO | 0..127 |
| 66 | `at_vcf` | TOUCH RESP · VCF | 0..127 |
| 67 | `rm_mod` | RING MOD · MOD | 0..127 |
| 68 | `rm_spd` | RING MOD · SPEED | 0..127 |
| 69 | `rm_depth` | RING MOD · DEPTH | 0..127 |
| 70 | `rm_a` | (no knob) | 0..127 |
| 71 | `rm_d` | RING MOD · DECAY | 0..127 |
| 72 | `cho_mode` | CHORUS · MODE | 0..3 (0 OFF, 1 CHORUS, 2 TREM, 3 FLANGE) |
| 73 | `cho_spd` | CHORUS · SPEED | 0..127 |
| 74 | `cho_depth` | CHORUS · DEPTH | 0..127 |
| 75 | `aat_delay` | AUTO AT · DELAY | 0..127 |
| 76 | `aat_rise` | AUTO AT · RISE | 0..127 |
| 77 | `aat_level` | AUTO AT · LEVEL | 0..127 |
| 78 | `aat_fall` | AUTO AT · FALL | 0..127 |
| 79 | `dly_time` | DELAY · TIME | 0..127 |
| 80 | `dly_fb` | DELAY · FEEDBK | 0..127 |
| 81 | `dly_mix` | DELAY · MIX | 0..127 |
| 82 | `dly_ping` | DELAY 2 · PING | 0..1 (0 OFF, 1 ON) |
| 83 | `dly_damp` | DELAY 2 · DAMP | 0..127 |
| 84 | `rv_mix` | REVERB · MIX | 0..127 |
| 85 | `rv_size` | REVERB · SIZE | 0..127 |
| 86 | `rv_damp` | REVERB · DAMP | 0..127 |
| 87 | `rv_shim` | SHIMMER · SHIMMR | 0..127 |
| 88 | `rv_shift` | SHIMMER · SHIFT | 0..24 |
| 89 | `mix` | TONES · MIX | 0..127 |
| 90 | `vintage` | PERFORM · VINTAG | 0..127 |
| 91 | `dly_sync` | DELAY · SYNC | 0..7 (0 FREE, 1 1/16, 2 1/8T, 3 1/8, 4 1/8D, 5 1/4, 6 1/4D, 7 1/2) |
| 92 | `lfo_sync` | SUB OSC 2 · SYNC | 0..5 (0 FREE, 1 1/4, 2 1/2, 3 1 BAR, 4 2 BAR, 5 4 BAR) |
| 93 | `kb_bl` | KEYBOARD · BRIL.LO | 0..127 (64 = centre) |
| 94 | `kb_bh` | KEYBOARD · BRIL.HI | 0..127 (64 = centre) |
| 95 | `kb_ll` | KEYBOARD · LEV.LO | 0..127 (64 = centre) |
| 96 | `kb_lh` | KEYBOARD · LEV.HI | 0..127 (64 = centre) |
| 97 | `dly_tape` | DELAY 2 · TAPE | 0..127 |
| 98 | `ph_rate` | PHASER · RATE | 0..127 |
| 99 | `ph_depth` | PHASER · DEPTH | 0..127 |
| 100 | `ph_fb` | PHASER · FEEDBK | 0..127 |
| 101 | `ph_mix` | PHASER · MIX | 0..127 |
| 102 | `unison` | MODES · UNISON | 0..127 |
| 103 | `drive` | DRIVE · DRIVE | 0..127 |
| 104 | `eq_lo` | DRIVE · LOW | 0..127 (64 = centre) |
| 105 | `eq_hi` | DRIVE · HIGH | 0..127 (64 = centre) |
| 106 | `drive_lv` | DRIVE · LEVEL | 0..127 |
