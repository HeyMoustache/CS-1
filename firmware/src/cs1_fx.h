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
/* ---- the reverb: a plate after Dattorro (1997), in fixed point. The input is diffused by four allpasses and fed to
 * two cross-coupled tanks, each a slowly modulated allpass, a delay, the damping low-pass, an allpass and a delay,
 * with the decay applied twice round; the output is Dattorro's seven taps a side. SIZE is the decay time (0.5 .. 25 s),
 * the input is scaled by the loss so a held chord sits at one level whatever the SIZE. Lengths are Dattorro's at
 * 29.8 kHz scaled to 44.1 kHz. */
#define RV_MOD 24                                   /* the tank allpasses wander +-24 frames (Dattorro's 16 at 29.8 kHz) */
#define RV_AP0_L 995u
#define RV_AP0_R 1345u
#define RV_D1_L 6590u
#define RV_D1_R 5505u
#define RV_AP1_L 2664u
#define RV_AP1_R 3931u
#define RV_D2_L 4681u
#define RV_D2_R 6241u
static int16_t rv_pre[1024] FM1_POOL;               /* the pre-delay: 20 ms */
static int16_t rv_in1[210] FM1_POOL, rv_in2[158] FM1_POOL, rv_in3[561] FM1_POOL, rv_in4[410] FM1_POOL;   /* input diffusion */
static int32_t rv_ap0l[RV_AP0_L + 64u] FM1_POOL, rv_ap0r[RV_AP0_R + 64u] FM1_POOL;   /* the tanks: 32 bits for the build-up */
static int32_t rv_d1l[RV_D1_L] FM1_POOL, rv_d1r[RV_D1_R] FM1_POOL;
static int32_t rv_ap1l[RV_AP1_L] FM1_POOL, rv_ap1r[RV_AP1_R] FM1_POOL;
static int32_t rv_d2l[RV_D2_L] FM1_POOL, rv_d2r[RV_D2_R] FM1_POOL;
#define SH_LEN 8192u                     /* the shimmer's grain: 186 ms, two heads half a grain apart */
static int16_t sh_line[SH_LEN] FM1_POOL;
static uint32_t rv_w, sh_w, sh_ph, rv_lfo[2];
static int32_t rv_bw, rv_lpl, rv_lpr, rv_fbl, rv_fbr;   /* the input bandwidth, the two dampers, the cross-feeds */
static int32_t rv_dcxl, rv_dcyl, rv_dcxr, rv_dcyr;   /* the output DC blockers' last input and output */
static int32_t sh_fb, sh_lp;                        /* the shimmer's last sample, low-passed, into the next input */
#if !defined(DINGHY_HOST) && !defined(DINGHY_WEB)
static uint32_t rv_hot;                             /* samples a line had to bend (the knee): a meter (tests/fake_fm1.h) */
#define dbg_meter(k, p, n) ((void)0)
#endif

static inline int32_t allpass16(int16_t *z, uint32_t len, uint32_t w, int32_t x, int32_t g)
{
    int32_t d = z[w % len], v = x + mulq15r(d, g);     /* the lattice form: unity gain at every frequency */
    z[w % len] = (int16_t)clamp(v, -32767, 32767);
    return d - mulq15r(v, g);
}
static inline int32_t allpass32(int32_t *z, uint32_t len, uint32_t w, int32_t x, int32_t g)
{
    int32_t d = z[w % len], v = x + mulq15r(d, g);
    z[w % len] = clamp(v, -(1 << 20), 1 << 20);
    return d - mulq15r(v, g);
}
/* the modulated allpass: its delay wanders RV_MOD either side of len, read between frames */
static inline int32_t allpass_mod(int32_t *z, uint32_t len, uint32_t w, int32_t x, int32_t g, uint32_t m16)
{
    uint32_t size = len + 64u, dl = len - RV_MOD + (m16 >> 4);
    int32_t a = z[(w - dl) % size], b = z[(w - dl - 1u) % size];
    int32_t d = a + (((b - a) * (int32_t)(m16 & 15u)) >> 4), v = x + mulq15r(d, g);
    z[w % size] = clamp(v, -(1 << 20), 1 << 20);
    return d - mulq15r(v, g);
}
static inline int32_t tap32(const int32_t *z, uint32_t len, uint32_t w, uint32_t back) { return z[(w - back) % len]; }

static void fx_reverb(int32_t *st, uint32_t n)
{
    uint32_t i;
    int32_t decay = PLATE_D[patch.rv_size], mix = patch.rv_mix * 258, damp = 32767 - patch.rv_damp * 150;
    int32_t shim = patch.rv_shim * 240;          /* 0 .. 0.93 of the loop's unity gain (below) */
    int32_t in_g;
    if (!mix && !shim) return;
    /* a sustained input builds up ~1 / (1 - decay) in the tanks: the input is scaled by the loss so a held chord sits
     * at the same level whatever the SIZE (a tail then starts quieter the longer it is to last) */
    in_g = clamp((32768 - decay) * 7, 0, 32767);
    shim = mulq15(shim, in_g);                        /* the shimmer's injection, scaled the same way */
    if (shim > 8500) shim = 8500;                     /* and never past 0.35: short tails would ring otherwise */
    for (i = 0; i < n; i++) {
        int32_t in = mulq15((st[2u * i] + st[2u * i + 1u]) >> 1, in_g), x, tl, tr, l, r;
        uint32_t ml, mr;
        if (shim) {
            sh_lp += (sh_fb - sh_lp) >> 2;               /* ~2.5 kHz: the octaves stack up softly */
            in += softclip(mulq15(sh_lp, shim));         /* and the loop can never run away: the feedback saturates */
        }
        rv_pre[rv_w & 1023u] = (int16_t)clamp(in, -32767, 32767);
        x = rv_pre[(rv_w - 882u) & 1023u];           /* 20 ms later */
        rv_bw += mulq15r(x - rv_bw, 26000);           /* the input bandwidth: ~9 kHz */
        x = allpass16(rv_in1, 210u, rv_w, rv_bw, 24576);   /* 0.75, 0.75, 0.625, 0.625 */
        x = allpass16(rv_in2, 158u, rv_w, x, 24576);
        x = allpass16(rv_in3, 561u, rv_w, x, 20480);
        x = allpass16(rv_in4, 410u, rv_w, x, 20480);
        /* the two tanks, each fed by the input plus the other's end */
        rv_lfo[0] += 97391u; rv_lfo[1] += 68173u;    /* 1.0 Hz and 0.7 Hz */
        ml = (uint32_t)(sine_i(rv_lfo[0]) + 32768) * (RV_MOD * 2u * 16u) >> 16;   /* 0 .. 2 RV_MOD, in 1/16 frames */
        mr = (uint32_t)(sine_i(rv_lfo[1]) + 32768) * (RV_MOD * 2u * 16u) >> 16;
        tl = allpass_mod(rv_ap0l, RV_AP0_L, rv_w, x + rv_fbr, -22938, ml);   /* -0.7 */
        tr = allpass_mod(rv_ap0r, RV_AP0_R, rv_w, x + rv_fbl, -22938, mr);
        rv_d1l[rv_w % RV_D1_L] = clamp(tl, -(1 << 20), 1 << 20);
        rv_d1r[rv_w % RV_D1_R] = clamp(tr, -(1 << 20), 1 << 20);
        tl = rv_d1l[(rv_w + 1u) % RV_D1_L];          /* the oldest frame: the delay's end */
        tr = rv_d1r[(rv_w + 1u) % RV_D1_R];
        rv_lpl += mulq15r(tl - rv_lpl, damp);         /* the damping, then the decay */
        rv_lpr += mulq15r(tr - rv_lpr, damp);
        tl = mulq15r(rv_lpl, decay);
        tr = mulq15r(rv_lpr, decay);
        tl = allpass32(rv_ap1l, RV_AP1_L, rv_w, tl, 16384);   /* 0.5 */
        tr = allpass32(rv_ap1r, RV_AP1_R, rv_w, tr, 16384);
        rv_d2l[rv_w % RV_D2_L] = clamp(tl, -(1 << 20), 1 << 20);
        rv_d2r[rv_w % RV_D2_R] = clamp(tr, -(1 << 20), 1 << 20);
        tl = rv_d2l[(rv_w + 1u) % RV_D2_L];
        tr = rv_d2r[(rv_w + 1u) % RV_D2_R];
        if (tl > 120000 || tl < -120000 || tr > 120000 || tr < -120000) rv_hot++;
        rv_fbl = mulq15r(tl, decay);                 /* into the other tank next frame */
        rv_fbr = mulq15r(tr, decay);
        /* Dattorro's taps (his figure's nodes, scaled): the left ear hears mostly the right tank and vice versa */
        l = tap32(rv_d1r, RV_D1_R, rv_w, 394u) + tap32(rv_d1r, RV_D1_R, rv_w, 4401u) - tap32(rv_ap1r, RV_AP1_R, rv_w, 2831u)
          + tap32(rv_d2r, RV_D2_R, rv_w, 2954u) - tap32(rv_d1l, RV_D1_L, rv_w, 2945u) - tap32(rv_ap1l, RV_AP1_L, rv_w, 277u)
          - tap32(rv_d2l, RV_D2_L, rv_w, 1578u);
        r = tap32(rv_d1l, RV_D1_L, rv_w, 522u) + tap32(rv_d1l, RV_D1_L, rv_w, 5368u) - tap32(rv_ap1l, RV_AP1_L, rv_w, 1817u)
          + tap32(rv_d2l, RV_D2_L, rv_w, 3956u) - tap32(rv_d1r, RV_D1_R, rv_w, 3124u) - tap32(rv_ap1r, RV_AP1_R, rv_w, 496u)
          - tap32(rv_d2r, RV_D2_R, rv_w, 179u);
        rv_w++;
        { int32_t l2 = (l * 3 + r) >> 3, r2 = (r * 3 + l) >> 3; l = l2; r = r2; }   /* 0.375, a quarter of each in the other: wide, mono-safe */
        { int32_t yl = ((l - rv_dcxl) << 6) + rv_dcyl - (rv_dcyl >> 10), yr = ((r - rv_dcxr) << 6) + rv_dcyr - (rv_dcyr >> 10);   /* DC blockers, ~7 Hz, state in 1/64 */
          rv_dcxl = l; rv_dcyl = yl; l = yl >> 6; rv_dcxr = r; rv_dcyr = yr; r = yr >> 6; }
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
