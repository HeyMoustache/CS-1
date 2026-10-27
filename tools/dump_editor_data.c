/* SPDX-License-Identifier: GPL-3.0-only */
/* The browser editor's data, read out of the firmware itself as JSON (web/editor/build.sh puts it in the page):
 * the patch's size, every knob of every page (where it lives in the patch, its range, how it is shown, its cap
 * colour and legends), the named values, the tones (names, colours, the CS-80's two rows, their panels), the
 * categories and every factory sound (name, category, tones and its whole patch, as PRESETS loads it).
 *   cc -O1 -Wno-unused-function -DDINGHY_HOST -Ifirmware/src -Ifirmware/gen -o build/host/dump_editor_data tools/dump_editor_data.c
 *   build/host/dump_editor_data > build/editor/cs1_data.json */
#include <stdio.h>
#define main host_main
#include "../firmware/src/cs1.c"
#undef main

static void str(const char *s)
{
    putchar('"');
    for (; s && *s; s++) { if (*s == '"' || *s == '\\') putchar('\\'); putchar(*s); }
    putchar('"');
}
static void names(const char *const *n, uint32_t k)
{
    uint32_t i;
    putchar('[');
    for (i = 0; i < k; i++) { if (i) putchar(','); str(n[i]); }
    putchar(']');
}
static void bytes(const void *p, uint32_t n)
{
    const uint8_t *b = p;
    uint32_t i;
    putchar('[');
    for (i = 0; i < n; i++) printf("%s%u", i ? "," : "", b[i]);
    putchar(']');
}
static const char *const KIND[] = {"num", "bip", "feet", "wave", "lwave", "onoff", "cho", "mchan", "expr", "div", "ldiv",
                                   "tempo", "sus", "cent", "semi", "scope", "cat"};
static const char *const COLOR[] = {"white", "green", "red", "black", "yellow", "silver"};

int main(void)
{
    uint32_t i, k;
    printf("{\"version\":");
    str(APP_VER);
    printf(",\"patch_len\":%u,\"chan_len\":%u,\"nuser\":%u", (unsigned)sizeof(patch_t), (unsigned)sizeof(chan_patch_t), NUSER);
    printf(",\"pages\":[");
    for (i = 0; i < NPAGE; i++) {
        printf("%s{\"title\":", i ? "," : "");
        str(PAGES[i].title);
        printf(",\"knobs\":[");
        for (k = 0; k < 4u; k++) {
            const pdesc_t *d = &PAGES[i].p[k];
            if (k) putchar(',');
            if (!d->name) { printf("null"); continue; }
            printf("{\"name\":");
            str(d->name);
            /* scope: chan (an offset in a channel's panel), patch (in the globals), or not part of a sound */
            printf(",\"scope\":\"%s\",\"off\":%u,\"max\":%u,\"kind\":\"%s\",\"color\":\"%s\",\"hi\":",
                   d->global == 0 ? "chan" : d->global == 1 ? "patch" : d->global == 2 ? "setting" : "random",
                   d->off, d->max, KIND[d->kind], COLOR[d->color]);
            str(d->hi);
            printf(",\"lo\":");
            str(d->lo);
            putchar('}');
        }
        printf("]}");
    }
    printf("],\"values\":{\"feet\":");
    names(N_FEET, 6);
    printf(",\"wave\":");
    names(N_WAVE, 3);
    printf(",\"lwave\":");
    names(N_LWAVE, 6);
    printf(",\"onoff\":");
    names(N_ONOFF, 2);
    printf(",\"cho\":");
    names(N_CHO, 4);
    printf(",\"div\":");
    names(N_DIV, 8);
    printf(",\"ldiv\":");
    names(N_LDIV, 6);
    printf("},\"categories\":");
    names(N_CAT, NCAT);
    printf(",\"tones\":[");
    for (i = 0; i < NTONE; i++) {
        printf("%s{\"name\":", i ? "," : "");
        str(TONE_NAMES[i]);
        printf(",\"color\":%u,\"panel\":", TONE_COLOR[i]);
        bytes(&TONES[i], sizeof TONES[i]);
        putchar('}');
    }
    printf("],\"tone_rows\":[");
    bytes(TONE_ROW[0], 11);
    putchar(',');
    bytes(TONE_ROW[1], 11);
    printf("],\"sounds\":[");
    patch = INIT_PATCH;
    for (i = 0; i < NSOUND; i++) {
        sound_load(i);
        printf("%s{\"name\":", i ? "," : "");
        str(SOUNDS[i].name);
        printf(",\"cat\":%u,\"tones\":[%u,%u],\"patch\":", SOUNDS[i].cat, set.tone[0], set.tone[1]);
        bytes(&patch, sizeof patch);
        putchar('}');
    }
    printf("],\"init\":");
    patch = INIT_PATCH;
    sound_load(0);
    bytes(&patch, sizeof patch);
    printf("}\n");
    return 0;
}
