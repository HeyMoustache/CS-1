/* SPDX-License-Identifier: GPL-3.0-only */
/* vstdump: a tiny VST2 host that loads a plugin, loads a bank (.fxb) into it, and prints every program's name and
 * parameter values with the parameter names, as JSON lines. Built as a 32-bit Windows program for Wine:
 *   i686-w64-mingw32-gcc -O1 -o vstdump.exe vstdump.c
 *   wine vstdump.exe plugin.dll bank.fxb > out.jsonl
 * No SDK: the AEffect layout and the opcodes are the well-known VST 2.4 ones. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct AEffect AEffect;
typedef intptr_t (__cdecl *audioMasterCallback)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
typedef intptr_t (__cdecl *dispatcherProc)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
typedef void (__cdecl *processProc)(AEffect *, float **, float **, int32_t);
typedef void (__cdecl *setParameterProc)(AEffect *, int32_t, float);
typedef float (__cdecl *getParameterProc)(AEffect *, int32_t);
struct AEffect {
    int32_t magic;                 /* 'VstP' */
    dispatcherProc dispatcher;
    processProc process;
    setParameterProc setParameter;
    getParameterProc getParameter;
    int32_t numPrograms, numParams, numInputs, numOutputs, flags;
    intptr_t resvd1, resvd2;
    int32_t initialDelay, realQualities, offQualities;
    float ioRatio;
    void *object, *user;
    int32_t uniqueID, version;
    processProc processReplacing;
};
typedef AEffect *(__cdecl *mainProc)(audioMasterCallback);

enum { effOpen = 0, effClose = 1, effSetProgram = 2, effGetProgram = 3, effSetProgramName = 4, effGetProgramName = 5,
       effGetParamLabel = 6, effGetParamDisplay = 7, effGetParamName = 8, effSetSampleRate = 10, effSetBlockSize = 11,
       effMainsChanged = 12, effGetChunk = 23, effSetChunk = 24, effGetProgramNameIndexed = 29, effGetEffectName = 45 };
enum { audioMasterAutomate = 0, audioMasterVersion = 1, audioMasterCurrentId = 2, audioMasterIdle = 3,
       audioMasterGetSampleRate = 16, audioMasterGetBlockSize = 17, audioMasterGetCurrentProcessLevel = 23,
       audioMasterGetVendorString = 32, audioMasterGetProductString = 33, audioMasterGetVendorVersion = 34,
       audioMasterCanDo = 37, audioMasterGetLanguage = 38 };

static intptr_t __cdecl host(AEffect *e, int32_t op, int32_t idx, intptr_t val, void *ptr, float f)
{
    (void)e; (void)idx; (void)val; (void)f;
    switch (op) {
    case audioMasterVersion: return 2400;
    case audioMasterCurrentId: return 0;
    case audioMasterGetSampleRate: return 44100;
    case audioMasterGetBlockSize: return 256;
    case audioMasterGetCurrentProcessLevel: return 0;
    case audioMasterGetLanguage: return 1;
    case audioMasterGetVendorString: strcpy((char *)ptr, "vstdump"); return 1;
    case audioMasterGetProductString: strcpy((char *)ptr, "vstdump"); return 1;
    case audioMasterGetVendorVersion: return 1;
    case audioMasterCanDo: return 0;
    default: return 0;
    }
}

static void json_str(const char *s)
{
    putchar('"');
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') { putchar('\\'); putchar(c); }
        else if (c < 32 || c > 126) printf("\\u%04x", c);
        else putchar(c);
    }
    putchar('"');
}

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "vstdump plugin.dll bank.fxb\n"); return 2; }
    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 1; }
    mainProc entry = (mainProc)GetProcAddress(h, "VSTPluginMain");
    if (!entry) entry = (mainProc)GetProcAddress(h, "main");
    if (!entry) { fprintf(stderr, "no VST entry point\n"); return 1; }
    AEffect *e = entry(host);
    if (!e || e->magic != 0x56737450) { fprintf(stderr, "no AEffect (%p)\n", (void *)e); return 1; }
    e->dispatcher(e, effOpen, 0, 0, 0, 0);
    e->dispatcher(e, effSetSampleRate, 0, 0, 0, 44100.f);
    e->dispatcher(e, effSetBlockSize, 0, 256, 0, 0);
    e->dispatcher(e, effMainsChanged, 0, 1, 0, 0);
    char name[256] = {0};
    e->dispatcher(e, effGetEffectName, 0, 0, name, 0);
    fprintf(stderr, "plugin '%s': %d programs, %d params, flags %#x, id %#x\n", name, e->numPrograms, e->numParams, e->flags, e->uniqueID);

    /* the bank: a VST2 .fxb; a chunk bank (FBCh) goes in with effSetChunk, a parameter bank (FxBk) by its values */
    FILE *fb = fopen(argv[2], "rb");
    if (!fb) { fprintf(stderr, "cannot open %s\n", argv[2]); return 1; }
    fseek(fb, 0, SEEK_END); long n = ftell(fb); fseek(fb, 0, SEEK_SET);
    unsigned char *bank = malloc((size_t)n); fread(bank, 1, (size_t)n, fb); fclose(fb);
    if (n < 160 || memcmp(bank, "CcnK", 4) != 0) { fprintf(stderr, "not a .fxb\n"); return 1; }
    if (memcmp(bank + 8, "FBCh", 4) == 0) {
        uint32_t csz = (uint32_t)bank[156] << 24 | (uint32_t)bank[157] << 16 | (uint32_t)bank[158] << 8 | bank[159];
        intptr_t r = e->dispatcher(e, effSetChunk, 0, (intptr_t)csz, bank + 160, 0);
        fprintf(stderr, "setChunk(bank, %u B) -> %ld\n", csz, (long)r);
    } else { fprintf(stderr, "not a chunk bank: %.4s\n", bank + 8); return 1; }

    /* the parameter names once */
    printf("{\"params\":[");
    for (int32_t i = 0; i < e->numParams; i++) {
        char pn[256] = {0}, lb[256] = {0};
        e->dispatcher(e, effGetParamName, i, 0, pn, 0);
        e->dispatcher(e, effGetParamLabel, i, 0, lb, 0);
        if (i) putchar(',');
        printf("{\"i\":%d,\"name\":", i); json_str(pn); printf(",\"label\":"); json_str(lb); putchar('}');
    }
    printf("]}\n");
    /* every program: its name, its values, and the plugin's own display text for each */
    for (int32_t p = 0; p < e->numPrograms; p++) {
        char pn[256] = {0};
        e->dispatcher(e, effSetProgram, 0, p, 0, 0);
        e->dispatcher(e, effGetProgramName, 0, 0, pn, 0);
        printf("{\"program\":%d,\"name\":", p); json_str(pn); printf(",\"values\":[");
        for (int32_t i = 0; i < e->numParams; i++) printf("%s%.6g", i ? "," : "", e->getParameter(e, i));
        printf("],\"display\":[");
        for (int32_t i = 0; i < e->numParams; i++) {
            char d[256] = {0};
            e->dispatcher(e, effGetParamDisplay, i, 0, d, 0);
            if (i) putchar(',');
            json_str(d);
        }
        printf("]}\n");
    }
    e->dispatcher(e, effMainsChanged, 0, 0, 0, 0);
    e->dispatcher(e, effClose, 0, 0, 0, 0);
    return 0;
}
