/* SPDX-License-Identifier: GPL-3.0-only */
/* CS-1's effects after the voice: a stereo delay and a reverb with a shimmer, where the CS-80 had a studio's
 * outboard. Fixed point, the lines in the pool (int16), the controls read from the patch a byte at a time.
 *   delay    one line, the input the sum of both sides; TIME, FEEDBK (with a one-pole damping in the loop),
 *            MIX; PING puts the right side on a tap at half the time
 *   reverb   a feedback delay network of eight lines (a Householder matrix: every line feeds every other),
 *            two all-pass diffusers on the way in and a 20 ms pre-delay; SIZE is the decay, DAMP a one-pole
 *            low-pass in every line, MIX; SHIMMER feeds the reverb's own output back in an octave up (a two-head
 *            granular pitch shifter), the way a shimmer pedal does */

/* ---- the delay */
#define DLY_LEN 49152u                   /* 1.1 s */
static int16_t dly_line[DLY_LEN] FM1_POOL;
static uint32_t dly_w;
static int32_t dly_lp;
static void fx_delay(int32_t *st, uint32_t n)       /* st: L R L R ..., in place */
{
    uint32_t i, time = patch.dly_sync ? sync_dly : DLY_TIME[patch.dly_time], half = time >> 1;
    int32_t fb = patch.dly_fb * 250, mix = patch.dly_mix * 258, damp = 32767 - patch.dly_damp * 230;
    if (!mix) {                                     /* off: the line keeps filling, so turning MIX up finds a tail */
        for (i = 0; i < n; i++) { dly_line[dly_w % DLY_LEN] = (int16_t)clamp((st[2u * i] + st[2u * i + 1u]) >> 1, -32767, 32767); dly_w++; }
        return;
    }
    for (i = 0; i < n; i++) {
        int32_t in = (st[2u * i] + st[2u * i + 1u]) >> 1;
        int32_t tap = dly_line[(dly_w - time) % DLY_LEN];
        int32_t tap2 = patch.dly_ping ? dly_line[(dly_w - half) % DLY_LEN] : tap;
        dly_lp += mulq15(tap - dly_lp, damp);       /* the loop's damping */
        dly_line[dly_w % DLY_LEN] = (int16_t)clamp(in + mulq15(dly_lp, fb), -32767, 32767);
        dly_w++;
        st[2u * i] += mulq15(tap, mix);
        st[2u * i + 1u] += mulq15(tap2, mix);
    }
}

/* ---- the reverb */
#define RV_N 8u
static const uint16_t RV_LEN[RV_N] = {1307, 1637, 1811, 1931, 2221, 2503, 2707, 2999};   /* ~30 .. 68 ms, primes */
#define RV_SUM (1307u + 1637u + 1811u + 1931u + 2221u + 2503u + 2707u + 2999u)
static int32_t rv_line[RV_SUM] FM1_POOL;            /* 32 bits: a held chord in a long tail builds up well past 16 */
static int16_t rv_pre[1024] FM1_POOL;               /* the pre-delay: 20 ms */
static int16_t rv_ap1[149] FM1_POOL, rv_ap2[379] FM1_POOL;   /* the input diffusers */
#define SH_LEN 8192u                     /* the shimmer's grain: 186 ms, two heads half a grain apart */
static int16_t sh_line[SH_LEN] FM1_POOL;
static uint32_t rv_w, rv_apw, sh_w, sh_ph;
static int32_t rv_lp[RV_N];
static int32_t sh_fb, sh_lp;                        /* the shimmer's last sample, low-passed, into the next input */
#if !defined(DINGHY_HOST) && !defined(DINGHY_WEB)
static uint32_t rv_hot;                             /* samples a line had to bend (the knee): a meter (tests/fake_fm1.h) */
#define dbg_meter(k, p, n) ((void)0)
#endif

static inline int32_t allpass(int16_t *z, uint32_t len, uint32_t w, int32_t x)
{
    int32_t d = z[w % len], y = d - (x >> 1);        /* g = 0.5 */
    z[w % len] = (int16_t)clamp(x + (d >> 1), -32767, 32767);
    return y;
}
static void fx_reverb(int32_t *st, uint32_t n)
{
    uint32_t i, k, off[RV_N];
    int32_t g[RV_N], gref = REV_G[patch.rv_size], mix = patch.rv_mix * 258, damp = 32767 - patch.rv_damp * 150;
    int32_t shim = patch.rv_shim * 240;          /* 0 .. 0.93 of the loop's unity gain (below) */
    int32_t in_g;
    if (!mix && !shim) return;
    /* a sustained input builds up ~1 / (1 - g) in the lines: the input is scaled by the loss (1 - g) so a held chord
     * sits at the same level in the lines whatever the SIZE (a tail then starts quieter the longer it is to last) */
    in_g = clamp((32768 - gref) * 3, 0, 32767);
    /* the shimmer's injection, scaled the same way: the loop's gain is what SHIMMER says, and the tail always dies */
    shim = mulq15(shim, clamp((32768 - gref) * 3, 0, 32767));
    if (shim > 8500) shim = 8500;                     /* and never past 0.35: short tails would ring otherwise */
    for (k = 0, i = 0; k < RV_N; k++) {              /* each line's feedback for its length: the same decay time */
        off[k] = i; i += RV_LEN[k];
        g[k] = clamp(32768 - ((32768 - gref) * (int32_t)RV_LEN[k]) / 2000, 0, 32700);
    }
    for (i = 0; i < n; i++) {
        int32_t in = mulq15((st[2u * i] + st[2u * i + 1u]) >> 1, in_g), f[RV_N], sum = 0, l = 0, r = 0, x;
        if (shim) {
            sh_lp += (sh_fb - sh_lp) >> 2;               /* ~2.5 kHz: the octaves stack up softly */
            in += softclip(mulq15(sh_lp, shim));         /* and the loop can never run away: the feedback saturates */
        }
        rv_pre[rv_w & 1023u] = (int16_t)clamp(in, -32767, 32767);
        x = rv_pre[(rv_w - 882u) & 1023u];           /* 20 ms later */
        x = allpass(rv_ap1, 149, rv_apw, x);
        x = allpass(rv_ap2, 379, rv_apw, x);
        rv_apw++;
        for (k = 0; k < RV_N; k++) {                 /* read, damp, sum */
            int32_t v = rv_line[off[k] + (rv_w % RV_LEN[k])];
            rv_lp[k] += mulq15(v - rv_lp[k], damp);
            f[k] = rv_lp[k];
            sum += f[k];
        }
        sum >>= 2;                                   /* Householder: y = f - (2 / 8) sum */
        for (k = 0; k < RV_N; k++) {
            int32_t y = f[k] - sum, w = x + mulq15(y, g[k]);
            if (w > 120000 || w < -120000) rv_hot++;
            rv_line[off[k] + (rv_w % RV_LEN[k])] = clamp(w, -(1 << 20), 1 << 20);
            if (k & 1u) r += f[k]; else l += f[k];
        }
        rv_w++;
        l >>= 1; r >>= 1;                            /* four lines each: twice a line's level */
        l = soft_knee(l, 20000); r = soft_knee(r, 20000);   /* a loud wash bends rather than slams the master knee */
        if (shim) {                                  /* the shimmer: the output an octave up, back to the input */
            int32_t m = (l + r) >> 1, a, b, wa;
            uint32_t da = sh_ph, db = (sh_ph + SH_LEN / 2u) & (SH_LEN - 1u);   /* two heads, half a grain apart */
            sh_line[sh_w & (SH_LEN - 1u)] = (int16_t)clamp(m, -32767, 32767);
            a = sh_line[(sh_w - da) & (SH_LEN - 1u)];
            b = sh_line[(sh_w - db) & (SH_LEN - 1u)];
            wa = (32767 - sine_i((da << 19) + 0x40000000u)) >> 1;   /* a raised cosine over the grain: the two sum to one */
            sh_fb = mulq15(a, wa) + mulq15(b, 32767 - wa);
            sh_ph = (sh_ph + SH_LEN - 1u) & (SH_LEN - 1u);   /* the heads run ahead by a frame a frame: an octave up */
            sh_w++;
        }
        st[2u * i] += mulq15(l, mix);
        st[2u * i + 1u] += mulq15(r, mix);
    }
}
