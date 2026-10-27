/* SPDX-License-Identifier: GPL-3.0-only */
/* string.h for the freestanding WebAssembly build (wasm/rt.c has the functions) */
#pragma once
typedef __SIZE_TYPE__ size_t;
void *memcpy(void *d, const void *s, size_t n);
void *memset(void *d, int c, size_t n);
void *memmove(void *d, const void *s, size_t n);
int memcmp(const void *a, const void *b, size_t n);
size_t strlen(const char *s);
