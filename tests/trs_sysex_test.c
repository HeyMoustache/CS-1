/* SPDX-License-Identifier: GPL-3.0-only */
/* The TRS jack's SysEx collection (firmware/src/midi_uart.c, for the editor link) on a computer: bytes as the jack
 * delivers them, with notes before and clock bytes inside the frame; a second frame while the first is unread is
 * dropped, a status byte inside a frame cancels it, an overlong frame is not kept.
 *   cc -O1 -Itests/stub_hal -Ifirmware/src -o build/host/trs_sysex_test tests/trs_sysex_test.c */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#define MQ 256u
#define RING_PUBLISH() __asm__ volatile("" ::: "memory")
static uint32_t midi_in_q[MQ];
static volatile uint32_t mi_w, mi_r;
#include "midi_uart.c"

static int fails;
static void check(const char *what, int ok) { printf("trs: %-66s %s\n", what, ok ? "ok" : "FAIL"); if (!ok) fails++; }
static void feed(const uint8_t *b, uint32_t n) { uint32_t i; for (i = 0; i < n; i++) um_byte(b[i]); }

int main(void)
{
    static const uint8_t note[] = {0x90, 60, 100};
    static const uint8_t f1[] = {0xF0, 0x7D, 0x43, 0xF8, 0x53, 0x31, 0x01, 0xF8, 0xF7};   /* clock inside */
    static const uint8_t f2[] = {0xF0, 0x7D, 0x43, 0x53, 0x31, 0x02, 0xF7};
    static const uint8_t cut[] = {0xF0, 0x7D, 0x43, 0x90, 61, 90};                       /* a note cuts it */
    static uint8_t big[700];
    uint32_t i;
    feed(note, sizeof note);
    check("a note before the frame reaches the queue", mi_w == 1u && (midi_in_q[0] >> 8 & 0xFFu) == 0x90u);
    feed(f1, sizeof f1);
    check("the frame is kept, the clock bytes in it are not part of it",
          um_sx_ready && um_sx_len == 5u && !memcmp(um_sx, "\x7D\x43\x53\x31\x01", 5));
    check("the two clock bytes still went to the queue", mi_w == 3u);
    feed(f2, sizeof f2);
    check("a second frame while the first is unread is dropped", um_sx_len == 5u && um_sx[4] == 0x01);
    um_sx_ready = 0;                                   /* the main loop took it */
    feed(f2, sizeof f2);
    check("the next frame after that is kept", um_sx_ready && um_sx_len == 5u && um_sx[4] == 0x02);
    um_sx_ready = 0;
    feed(cut, sizeof cut);
    check("a status byte inside cancels the frame; the note after it plays", !um_sx_ready && mi_w == 4u);
    big[0] = 0xF0; for (i = 1; i < sizeof big - 1u; i++) big[i] = 0x7D; big[sizeof big - 1u] = 0xF7;
    feed(big, sizeof big);
    check("a frame longer than the buffer is not kept", !um_sx_ready);
    feed(f2, sizeof f2);
    check("and the one after it is", um_sx_ready && um_sx[4] == 0x02);
    feed(note, sizeof note);
    check("running status survives: a note after SysEx needs its status again", mi_w == 5u);
    printf("trs: %s\n", fails ? "FAILED" : "all ok");
    return fails != 0;
}
