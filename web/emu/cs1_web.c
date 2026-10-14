/* SPDX-License-Identifier: GPL-3.0-only */
/* CS-1 in the browser: the firmware's app against the fake FM-1 (tests/fake_fm1.h) and the exports the
 * AudioWorklet calls (web_fm1.h), compiled to WebAssembly by web/emu/build.sh. Nothing of the firmware changes. */
#define DINGHY_WEB 1
#include "../../firmware/src/cs1.c"
