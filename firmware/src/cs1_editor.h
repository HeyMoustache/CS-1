/* SPDX-License-Identifier: GPL-3.0-only */
/* The editor link: a computer (the browser editor) reads and writes the panel and the user presets over SysEx,
 * on USB or the TRS jack. Included by cs1.c (it uses the panel, the bank and the screen's flags); the platform
 * hands over the frames whose first byte is 0x7D (sysex_get / sysex_done) and sends ours (sysex_send).
 *
 * Every frame:   F0 7D 43 53 31 <cmd> <data ..> F7          (7D: the non-commercial ID; "CS1")
 * Every byte of data is 0..127, the patch's bytes as they are (every one of them is a knob's 0..127).
 *
 *   to the FM-1                                            the FM-1 replies (on USB; TRS is in only)
 *   01 HELLO                                               41 proto, len lo, len hi, nuser, nsound, nslot, version ..
 *   02 GET PANEL                                           42 tone I, tone II, sound, patch ..
 *   03 SET PANEL   tone I, tone II, patch ..               7F 03 status
 *   04 SET PARAM   off lo, off hi, value                   (nothing; 7F 04 status on an error)
 *   05 STORE       slot                                    7F 05 status   (the panel into user slot 0..31: flash)
 *   06 GET SLOT    slot                                    46 slot, used, tone I, tone II, cat, patch .. (unused: no patch)
 *   07 PUT SLOT    slot, tone I, tone II, cat, patch ..    7F 07 status   (straight into the bank: flash; the panel stays)
 *   08 LOAD        index                                   7F 08 status   (as program change: a sound, then the slots)
 *
 * status: 0 done, 1 wrong length, 2 a value out of range, 3 a slot or index out of range, 4 the flash failed,
 * 5 an unknown command. "off" is the byte's offset in patch_t (cs1_voice.h): the channels' 26 bytes each, then the
 * globals in order. docs/SYSEX.md has the whole map. */
#define ED_PROTO 1u
#define ED_HDR 5u                                       /* 7D 43 53 31 cmd */
#define ED_PLEN ((uint32_t)sizeof(patch_t))
enum { ED_OK = 0, ED_LEN, ED_RANGE, ED_INDEX, ED_FLASH, ED_CMD };

static void ed_reply(uint32_t cmd, const uint8_t *d, uint32_t n)
{
    static uint8_t f[ED_HDR + 8u + 160u];
    uint32_t i;
    if (n > 160u) return;
    f[0] = 0xF0; f[1] = 0x7D; f[2] = 0x43; f[3] = 0x53; f[4] = 0x31; f[5] = (uint8_t)cmd;
    for (i = 0; i < n; i++) f[6 + i] = d[i] & 0x7Fu;
    f[6 + n] = 0xF7;
    sysex_send(f, 7u + n);
}
static void ed_status(uint32_t cmd, uint32_t st) { uint8_t d[2] = {(uint8_t)cmd, (uint8_t)st}; ed_reply(0x7F, d, 2); }

static void ed_panel_changed(uint32_t whole)          /* the panel moved under the editor's hand: kept, and redrawn once */
{
    set.patch = patch;
    changed();
    tones_drawn = ~0u;
    if (whole) content_dirty = 1u;
    else midi_redraw |= 15u;
}

static void ed_frame(const uint8_t *p, uint32_t n)
{
    static uint8_t out[160];
    const uint8_t *d = p + ED_HDR;
    uint32_t cmd, dn, i;
    if (n < ED_HDR || p[0] != 0x7Du || p[1] != 0x43u || p[2] != 0x53u || p[3] != 0x31u) return;   /* not ours */
    cmd = p[4];
    dn = n - ED_HDR;
    for (i = 0; i < dn; i++) if (d[i] > 127u) return;  /* (a status byte inside: a broken frame) */
    last_midi_ms = fm1_ms;                              /* a flash save waits for the editor to go quiet, as for MIDI */
    switch (cmd) {
    case 0x01: {                                        /* HELLO: who we are, the patch's size */
        static const char V[] = APP_VER;
        uint32_t k = 0;
        out[k++] = ED_PROTO;
        out[k++] = (uint8_t)(ED_PLEN & 0x7Fu); out[k++] = (uint8_t)(ED_PLEN >> 7);
        out[k++] = (uint8_t)NUSER; out[k++] = (uint8_t)NSOUND; out[k++] = (uint8_t)NTONE;
        for (i = 0; V[i] && i < 16u; i++) out[k++] = (uint8_t)V[i];
        ed_reply(0x41, out, k);
        return;
    }
    case 0x02:                                          /* GET PANEL */
        out[0] = set.tone[0]; out[1] = set.tone[1]; out[2] = set.sound;
        memcpy(out + 3, &patch, ED_PLEN);
        ed_reply(0x42, out, 3u + ED_PLEN);
        return;
    case 0x03: {                                        /* SET PANEL: the whole panel, at once */
        patch_t np;
        if (dn != 2u + ED_PLEN) { ed_status(cmd, ED_LEN); return; }
        memcpy(&np, d + 2, ED_PLEN);
        if (!patch_valid(&np)) { ed_status(cmd, ED_RANGE); return; }
        patch = np;
        set.tone[0] = (uint8_t)(d[0] % NTONE);
        set.tone[1] = (uint8_t)(d[1] % NTONE);
        ed_panel_changed(1);
        say("FROM EDITOR");
        ed_status(cmd, ED_OK);
        return;
    }
    case 0x04: {                                        /* SET PARAM: one byte of the panel (a knob in the editor) */
        patch_t np = patch;
        uint32_t off;
        if (dn != 3u) { ed_status(cmd, ED_LEN); return; }
        off = d[0] | (uint32_t)d[1] << 7;
        if (off >= ED_PLEN) { ed_status(cmd, ED_INDEX); return; }
        ((uint8_t *)&np)[off] = d[2];
        if (!patch_valid(&np)) { ed_status(cmd, ED_RANGE); return; }
        if (((uint8_t *)&patch)[off] == d[2]) return;
        ((uint8_t *)&patch)[off] = d[2];
        ed_panel_changed(0);
        return;
    }
    case 0x05:                                          /* STORE: the panel into a user slot */
        if (dn != 1u) { ed_status(cmd, ED_LEN); return; }
        if (d[0] >= NUSER) { ed_status(cmd, ED_INDEX); return; }
        slot_store(d[0]);
        changed(); content_dirty = 1u;
        say("SAVED");
        ed_status(cmd, ED_OK);
        return;
    case 0x06: {                                        /* GET SLOT */
        const slot_t *sl;
        uint32_t used;
        if (dn != 1u) { ed_status(cmd, ED_LEN); return; }
        if (d[0] >= NUSER) { ed_status(cmd, ED_INDEX); return; }
        sl = slot_at(d[0]);
        used = slot_used(d[0]) != 0;
        out[0] = d[0]; out[1] = (uint8_t)used;
        if (!used) { ed_reply(0x46, out, 2); return; }
        out[2] = sl->tone[0] % NTONE; out[3] = sl->tone[1] % NTONE; out[4] = sl->cat < NCAT ? sl->cat : 0;
        memcpy(out + 5, &sl->patch, ED_PLEN);
        if (!sl->layout) { patch_t *q = (patch_t *)(out + 5); q->drive = 0; q->drive_lv = 64; q->eq_lo = q->eq_hi = 64; }   /* (an older slot, as slot_load reads it) */
        ed_reply(0x46, out, 5u + ED_PLEN);
        return;
    }
    case 0x07: {                                        /* PUT SLOT: straight into the bank */
        slot_t *sl;
        patch_t np;
        if (dn != 4u + ED_PLEN) { ed_status(cmd, ED_LEN); return; }
        if (d[0] >= NUSER) { ed_status(cmd, ED_INDEX); return; }
        memcpy(&np, d + 4, ED_PLEN);
        if (!patch_valid(&np)) { ed_status(cmd, ED_RANGE); return; }
        sl = slot_at(d[0]);
        sl->magic = SLOT_MAGIC;
        sl->tone[0] = (uint8_t)(d[1] % NTONE); sl->tone[1] = (uint8_t)(d[2] % NTONE);
        sl->layout = 1;
        sl->cat = (uint8_t)(d[3] && d[3] < C_USER ? d[3] : classify(&np));
        sl->patch = np;
        if (bank_save(bank.raw, sizeof bank.raw)) { ed_status(cmd, ED_FLASH); return; }
        if (set.sound == NSOUND + d[0]) loaded = np;    /* (the slot showing: its star against the new contents) */
        tones_drawn = ~0u;
        ed_status(cmd, ED_OK);
        return;
    }
    case 0x08: {                                        /* LOAD: a sound or a slot, as program change does */
        char nb[8];
        if (dn != 1u) { ed_status(cmd, ED_LEN); return; }
        if (d[0] >= NSOUND + NUSER || (d[0] >= NSOUND && !slot_used(d[0] - NSOUND))) { ed_status(cmd, ED_INDEX); return; }
        sound_or_slot_load(d[0]);
        set.sound = d[0];
        ed_panel_changed(1);
        say(sound_name(d[0], nb));
        ed_status(cmd, ED_OK);
        return;
    }
    default:
        ed_status(cmd, ED_CMD);
        return;
    }
}

static void editor_service(void)                      /* main loop: the frames the platform has kept for us */
{
    const uint8_t *p;
    uint32_t n, k;
    for (k = 0; k < 8u && sysex_get(&p, &n); k++) {
        ed_frame(p, n);
        sysex_done();
    }
}
