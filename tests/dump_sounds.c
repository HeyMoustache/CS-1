/* SPDX-License-Identifier: GPL-3.0-only */
/* Every shipped sound's patch in device units, as JSON lines: the randomiser's corpus (tools/gen_random.py).
 *   cc -O1 -Wno-unused-function -DDINGHY_HOST -Ifirmware/src -Ifirmware/gen -o build/host/dump_sounds tests/dump_sounds.c */
#include <stdio.h>
#define main host_main
#include "cs1.c"
#undef main
int main(void)
{
    uint32_t i, k;
    patch = INIT_PATCH;
    for (i = 0; i < NSOUND; i++) {
        const uint8_t *b = (const uint8_t *)&patch;
        sound_load(i);
        printf("{\"name\":\"%s\",\"cat\":\"%s\",\"patch\":[", SOUNDS[i].name, N_CAT[SOUNDS[i].cat]);
        for (k = 0; k < sizeof patch; k++) printf("%s%u", k ? "," : "", b[k]);
        printf("]}\n");
    }
    return 0;
}
