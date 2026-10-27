/* SPDX-License-Identifier: GPL-3.0-only */
/* A stand-in for hal/fm1_uart.h on a computer (tests/trs_sysex_test.c): no UART, the test feeds the ring */
#pragma once
#include <stdint.h>
static void fm1_uart1_midi_init(volatile uint8_t *ring, uint32_t len) { (void)ring; (void)len; }
static uint32_t fm1_uart1_rx_take(void) { return 0; }
