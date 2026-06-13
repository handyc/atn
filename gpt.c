/*
 * gpt.c — the "fake transformer" language model over file bytes.
 *
 * A deterministic, unlearned n-gram-with-backoff byte model that plays the
 * role a trained transformer would: it gives a probability distribution over
 * the next byte given the preceding context. From that one capability we get
 *   - cross-entropy / bits-per-byte (a real measure that the model "works"),
 *   - temperature sampling generation (escapes the greedy loop, mixes context),
 * and later it drives arithmetic-coding compression. Nothing is trained; the
 * "weights" are just observed counts, and a fixed-seed PRNG keeps sampling
 * reproducible so the same file always yields the same output.
 */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <dirent.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define MODEL_CAP (64u << 20)   /* model is built from up to this many bytes */
#define MAP_CAP   (1u << 22)    /* max entries per hash map (caps RAM ~300MB) */
#define MAP_PROBE 128           /* bounded linear probing: never scan more than */
                                /* this many slots, so a saturated map (diverse  */
                                /* corpus) degrades gracefully instead of going  */
                                /* O(cap) per lookup. Excess n-grams are dropped. */

/* ---- deterministic PRNG (xorshift64) ---- */
static uint64_t rng_state = 0x9E3779B97F4A7C15ull;
static void   rng_seed(uint64_t s) { rng_state = s ? s : 0x9E3779B97F4A7C15ull; }
static uint64_t rng_u64(void) {
    uint64_t x = rng_state; x ^= x << 13; x ^= x >> 7; x ^= x << 17; rng_state = x; return x;
}
static double rng_unit(void) { return (double)(rng_u64() >> 11) / (double)(1ull << 53); }

/* ---- open-addressing uint64 -> uint32 count map ---- */
typedef struct { uint64_t *k; uint32_t *v; char *used; size_t cap; } u64map;

static size_t g_map_cap = MAP_CAP;     /* runtime-tunable via --map-bits */
void lm_set_map_cap(int bits) {
    if (bits < 16) bits = 16;
    if (bits > 27) bits = 27;
    g_map_cap = (size_t)1 << bits;
}

/* maxcap = 0 uses the tunable global cap; otherwise a hard cap (load uses the
 * exact entry count so a saved brain always reloads in full). */
static bool map_init_cap(u64map *m, size_t want, size_t maxcap) {
    size_t lim = maxcap ? maxcap : g_map_cap;
    size_t cap = 1; while (cap < want * 2 && cap < lim) cap <<= 1;
    if (cap < 16) cap = 16;
    m->k = malloc(cap * sizeof(uint64_t));
    m->v = calloc(cap, sizeof(uint32_t));
    m->used = calloc(cap, 1);
    m->cap = cap;
    if (!m->k || !m->v || !m->used) { free(m->k); free(m->v); free(m->used); m->cap = 0; return false; }
    return true;
}
static bool map_init(u64map *m, size_t want) { return map_init_cap(m, want, 0); }
static void map_free(u64map *m) { free(m->k); free(m->v); free(m->used); m->cap = 0; }
static void map_add(u64map *m, uint64_t key) {
    if (!m->cap) return;
    size_t s = (key * 1099511628211ull) & (m->cap - 1), pr = 0;
    while (m->used[s] && pr < MAP_PROBE) { if (m->k[s] == key) { m->v[s]++; return; } s = (s+1)&(m->cap-1); pr++; }
    if (!m->used[s]) { m->used[s] = 1; m->k[s] = key; m->v[s] = 1; }
}
static uint32_t map_get(const u64map *m, uint64_t key) {
    if (!m->cap) return 0;
    size_t s = (key * 1099511628211ull) & (m->cap - 1), pr = 0;
    while (m->used[s] && pr < MAP_PROBE) { if (m->k[s] == key) return m->v[s]; s = (s+1)&(m->cap-1); pr++; }
    return 0;
}
/* Insert a key with a given count (used when restoring saved weights). */
static void map_put(u64map *m, uint64_t key, uint32_t val) {
    if (!m->cap) return;
    size_t s = (key * 1099511628211ull) & (m->cap - 1), pr = 0;
    while (m->used[s] && pr < MAP_PROBE) { if (m->k[s] == key) { m->v[s] = val; return; } s = (s+1)&(m->cap-1); pr++; }
    if (!m->used[s]) { m->used[s] = 1; m->k[s] = key; m->v[s] = val; }
}

/* ---- the model: unigram + a couple of higher orders with backoff ---- */
#define NORD 3
typedef struct {
    uint32_t uni[256]; uint64_t uni_total;
    int orders[NORD];           /* context lengths, low -> high  */
    u64map cnt[NORD];           /* (ctx<<8 | nextbyte) -> count */
    u64map tot[NORD];           /* ctx -> total count           */
    size_t n;                   /* bytes used to build          */
} model;

/* Single place to choose the context orders (low -> high). */
static void model_set_orders(model *M) {
    /* Max order is 7: the count key packs (ctx<<8)|byte into 64 bits. */
    M->orders[0] = 2; M->orders[1] = 4; M->orders[2] = 7;
}

static uint64_t pack_ctx(const unsigned char *d, size_t pos, int m) {
    uint64_t c = 0; for (int k = 0; k < m; k++) c = (c << 8) | d[pos - m + k]; return c;
}

/* Build the model from b, sizing the hash maps for at least `reserve` entries
 * (headroom so an online chat can keep adding n-grams without dropping any). */
static void model_build_reserve(model *M, const blob *b, size_t reserve) {
    memset(M, 0, sizeof(*M));
    model_set_orders(M);
    size_t n = b->len; if (n > MODEL_CAP) n = MODEL_CAP;
    M->n = n;
    size_t want = n > reserve ? n : reserve;
    for (int o = 0; o < NORD; o++) { map_init(&M->cnt[o], want); map_init(&M->tot[o], want); }
    for (size_t t = 0; t < n; t++) {
        unsigned char x = b->data[t];
        M->uni[x]++; M->uni_total++;
        for (int o = 0; o < NORD; o++) {
            int m = M->orders[o];
            if (t >= (size_t)m) {
                uint64_t ctx = pack_ctx(b->data, t, m);
                map_add(&M->cnt[o], (ctx << 8) | x);
                map_add(&M->tot[o], ctx);
            }
        }
    }
}
static void model_build(model *M, const blob *b) { model_build_reserve(M, b, 0); }
static void model_free(model *M) {
    for (int o = 0; o < NORD; o++) { map_free(&M->cnt[o]); map_free(&M->tot[o]); }
}

/* Probability of byte `nb` given the context ending at d[pos-1] (pos bytes
 * of history available). Interpolated backoff: uniform <- unigram <- orders. */
static double model_prob(const model *M, const unsigned char *d, size_t pos, unsigned char nb) {
    const double LAMBDA = 0.7;
    double p = 1.0 / 256.0;                                   /* uniform floor */
    double puni = (M->uni_total ? (double)M->uni[nb] / (double)M->uni_total : 1.0/256.0);
    p = 0.5 * puni + 0.5 * p;                                 /* unigram */
    for (int o = 0; o < NORD; o++) {                         /* low -> high order */
        int m = M->orders[o];
        if (pos < (size_t)m) continue;
        uint64_t ctx = pack_ctx(d, pos, m);
        uint32_t total = map_get(&M->tot[o], ctx);
        if (!total) continue;
        uint32_t c = map_get(&M->cnt[o], (ctx << 8) | nb);
        double porder = (double)c / (double)total;
        p = LAMBDA * porder + (1.0 - LAMBDA) * p;
    }
    return p;
}

/* Incrementally fold byte at position t into the model. */
static void model_observe(model *M, const unsigned char *d, size_t t) {
    unsigned char x = d[t];
    M->uni[x]++; M->uni_total++;
    for (int o = 0; o < NORD; o++) {
        int m = M->orders[o];
        if (t >= (size_t)m) {
            uint64_t ctx = pack_ctx(d, t, m);
            map_add(&M->cnt[o], (ctx << 8) | x);
            map_add(&M->tot[o], ctx);
        }
    }
}

/* ---------------------------------------------------------------- */
/* Cross-entropy / bits-per-byte — ONLINE (prequential), the honest  */
/* measure: each byte is predicted from only the preceding bytes,    */
/* then folded in. This equals an adaptive arithmetic coder's size,  */
/* and (correctly) does NOT compress random data.                    */
/* ---------------------------------------------------------------- */

static double model_bpb_online(const blob *b) {
    size_t n = b->len; if (n > MODEL_CAP) n = MODEL_CAP;
    if (n == 0) return 0;
    model M; memset(&M, 0, sizeof(M));
    model_set_orders(&M);
    for (int o = 0; o < NORD; o++) { map_init(&M.cnt[o], n); map_init(&M.tot[o], n); }

    double bits = 0;
    for (size_t t = 0; t < n; t++) {
        bits += -log2(model_prob(&M, b->data, t, b->data[t]));  /* predict from past */
        model_observe(&M, b->data, t);                          /* then learn */
    }
    model_free(&M);
    return bits / (double)n;
}

/* ---------------------------------------------------------------- */
/* Temperature-sampled autoregressive generation                    */
/* ---------------------------------------------------------------- */

static void model_generate(const model *M, const blob *b, double temp, int gen) {
    if (b->len < 8) { printf("    (too small to generate)\n"); return; }
    if (temp < 0.01) temp = 0.01;
    rng_seed(0xA77E27107ull ^ (uint64_t)b->len);   /* fixed but content-tied */

    /* history buffer: seed with the file's final bytes */
    int hist = M->orders[NORD-1];                  /* longest context needed */
    unsigned char ctx[8];
    for (int k = 0; k < hist; k++) ctx[k] = b->data[b->len - hist + k];

    printf("    temperature %.2f, seed = file's last %d bytes: \"", temp, hist);
    for (int k = 0; k < hist; k++) putchar(isprint(ctx[k]) ? ctx[k] : '.');
    printf("\"\n");

    char out[512]; int outn = 0;
    double p[256];
    for (int step = 0; step < gen && outn < (int)sizeof(out) - 1; step++) {
        double sum = 0;
        for (int b2 = 0; b2 < 256; b2++) {
            double pr = model_prob(M, ctx, (size_t)hist, (unsigned char)b2);
            pr = pow(pr, 1.0 / temp);              /* temperature */
            p[b2] = pr; sum += pr;
        }
        double r = rng_unit() * sum, acc = 0; int pick = 255;
        for (int b2 = 0; b2 < 256; b2++) { acc += p[b2]; if (r <= acc) { pick = b2; break; } }
        out[outn++] = (char)pick;
        memmove(ctx, ctx + 1, hist - 1); ctx[hist-1] = (unsigned char)pick;
    }
    out[outn] = 0;
    printf("    generated %d bytes:\n      \"", outn);
    for (int i = 0; i < outn; i++) putchar(isprint((unsigned char)out[i]) ? out[i] : '.');
    printf("\"\n");
}

/* ---------------------------------------------------------------- */
/* Full next-byte distribution at a position (same math as model_prob */
/* but computed once for all 256 symbols).                           */
/* ---------------------------------------------------------------- */

static void model_dist(const model *M, const unsigned char *d, size_t pos, double *p) {
    const double LAMBDA = 0.7;
    double uni = 1.0 / 256.0;
    for (int i = 0; i < 256; i++) {
        double pu = M->uni_total ? (double)M->uni[i] / (double)M->uni_total : uni;
        p[i] = 0.5 * pu + 0.5 * uni;
    }
    for (int o = 0; o < NORD; o++) {
        int m = M->orders[o];
        if (pos < (size_t)m) continue;
        uint64_t ctx = pack_ctx(d, pos, m);
        uint32_t total = map_get(&M->tot[o], ctx);
        if (!total) continue;
        for (int i = 0; i < 256; i++) {
            uint32_t c = map_get(&M->cnt[o], (ctx << 8) | (unsigned)i);
            double porder = (double)c / (double)total;
            p[i] = LAMBDA * porder + (1.0 - LAMBDA) * p[i];
        }
    }
}

/* ---------------------------------------------------------------- */
/* Range coder (Subbotin carryless) + model-driven (de)compression   */
/* ---------------------------------------------------------------- */

#define RC_TOP (1u << 24)
#define RC_BOT (1u << 16)
#define CTOT   (1u << 16)        /* total of quantised frequencies   */
#define COMPRESS_CAP (1u << 18)  /* compress up to 256 KiB (demo)     */

typedef struct { uint32_t low, range; unsigned char *buf; size_t n, cap; } renc;
static void renc_put(renc *e, unsigned char c) {
    if (e->n == e->cap) { e->cap = e->cap ? e->cap * 2 : 4096; e->buf = realloc(e->buf, e->cap); }
    e->buf[e->n++] = c;
}
static void renc_encode(renc *e, uint32_t cum, uint32_t freq, uint32_t tot) {
    e->range /= tot;
    e->low += cum * e->range;
    e->range *= freq;
    while ((e->low ^ (e->low + e->range)) < RC_TOP ||
           (e->range < RC_BOT && ((e->range = (0u - e->low) & (RC_BOT - 1)), 1))) {
        renc_put(e, (unsigned char)(e->low >> 24)); e->low <<= 8; e->range <<= 8;
    }
}
static void renc_flush(renc *e) { for (int i = 0; i < 4; i++) { renc_put(e, (unsigned char)(e->low >> 24)); e->low <<= 8; } }

typedef struct { uint32_t low, range, code; const unsigned char *buf; size_t n, pos; } rdec;
static unsigned char rdec_get(rdec *d) { return d->pos < d->n ? d->buf[d->pos++] : 0; }
static void rdec_init(rdec *d, const unsigned char *buf, size_t n) {
    d->buf = buf; d->n = n; d->pos = 0; d->low = 0; d->range = 0xFFFFFFFFu; d->code = 0;
    for (int i = 0; i < 4; i++) d->code = (d->code << 8) | rdec_get(d);
}
static uint32_t rdec_getfreq(rdec *d, uint32_t tot) { d->range /= tot; return (d->code - d->low) / d->range; }
static void rdec_decode(rdec *d, uint32_t cum, uint32_t freq) {
    d->low += cum * d->range; d->range *= freq;
    while ((d->low ^ (d->low + d->range)) < RC_TOP ||
           (d->range < RC_BOT && ((d->range = (0u - d->low) & (RC_BOT - 1)), 1))) {
        d->code = (d->code << 8) | rdec_get(d); d->low <<= 8; d->range <<= 8;
    }
}

/* Quantise a probability distribution into integer freqs summing to CTOT. */
static void quantise(const double *p, uint32_t *freq) {
    uint32_t sum = 0; int imax = 0; double pmax = -1;
    for (int i = 0; i < 256; i++) {
        uint32_t q = (uint32_t)(p[i] * (double)(CTOT - 256));
        freq[i] = 1 + q; sum += freq[i];
        if (p[i] > pmax) { pmax = p[i]; imax = i; }
    }
    if (sum < CTOT) freq[imax] += CTOT - sum;
    else if (sum > CTOT) {
        uint32_t over = sum - CTOT;
        freq[imax] = freq[imax] > over + 1 ? freq[imax] - over : 1;  /* keep >=1 */
    }
}

static void fresh_model(model *M, size_t n) {
    memset(M, 0, sizeof(*M));
    model_set_orders(M);
    for (int o = 0; o < NORD; o++) { map_init(&M->cnt[o], n); map_init(&M->tot[o], n); }
}

/* ================================================================ */
/* Predictive feedback loop: online context mixing.                  */
/*                                                                    */
/* Several "expert" predictors (unigram + each context order) each   */
/* propose a next-byte distribution. They are blended in log space    */
/* (a log-linear / max-entropy mix), and the blend weights are        */
/* updated every byte by gradient descent on the prediction error —   */
/* the model's surprise feeds back to re-weight which context length   */
/* it trusts. That error->weight->prediction loop is, deterministically*/
/* and online, the same shape as the gradient feedback that trains a   */
/* transformer. It also predicts better than fixed backoff.           */
/* ================================================================ */

#define NEXP (NORD + 1)               /* nested backoffs: ≤unigram .. ≤full */
#define FEEDBACK_CAP (1u << 19)       /* 512 KiB                          */

/* Backoff probability of nb using only the first `nord` context orders. */
static double model_prob_upto(const model *M, const unsigned char *d, size_t pos,
                              unsigned char nb, int nord) {
    const double LAMBDA = 0.7;
    double p = 1.0 / 256.0;
    double puni = M->uni_total ? (double)M->uni[nb] / (double)M->uni_total : 1.0/256.0;
    p = 0.5 * puni + 0.5 * p;
    for (int o = 0; o < nord; o++) {
        int m = M->orders[o];
        if (pos < (size_t)m) continue;
        uint64_t ctx = pack_ctx(d, pos, m);
        uint32_t tot = map_get(&M->tot[o], ctx);
        if (!tot) continue;
        uint32_t c = map_get(&M->cnt[o], (ctx << 8) | nb);
        p = LAMBDA * ((double)c / (double)tot) + (1.0 - LAMBDA) * p;
    }
    return p;
}

void feedback_report(const blob *b) {
    section("predictive feedback loop (online Bayesian model mixing)");
    size_t n = b->len; bool capped = false;
    if (n > FEEDBACK_CAP) { n = FEEDBACK_CAP; capped = true; }
    if (n < 64) { printf("  (too small)\n"); return; }
    if (capped) printf("  (first %u KiB)\n", FEEDBACK_CAP >> 10);

    model M; fresh_model(&M, n);
    /* NEXP nested experts: expert e uses backoff over the first e orders
     * (e = 0 is unigram only, e = NORD is the full model). */
    double w[NEXP]; for (int e = 0; e < NEXP; e++) w[e] = 1.0 / NEXP;
    const double gamma = 0.003;        /* fixed-share: keep some adaptivity */
    double mixed_bits = 0, base_bits = 0;

    const int NW = 64; double winbits[64]; size_t wincnt[64];
    for (int i = 0; i < NW; i++) { winbits[i] = 0; wincnt[i] = 0; }
    double wsnap[NEXP]; for (int e = 0; e < NEXP; e++) wsnap[e] = w[e];

    for (size_t t = 0; t < n; t++) {
        unsigned char act = b->data[t];
        double pe[NEXP], mixed = 0;
        for (int e = 0; e < NEXP; e++) { pe[e] = model_prob_upto(&M, b->data, t, act, e); mixed += w[e] * pe[e]; }
        if (mixed < 1e-300) mixed = 1e-300;
        double lb = -log2(mixed);
        mixed_bits += lb;
        base_bits  += -log2(pe[NORD]);                 /* full backoff = expert NORD */
        int wi = (int)(t * NW / n); winbits[wi] += lb; wincnt[wi]++;

        /* Bayesian feedback: posterior ∝ prior × likelihood of the actual byte */
        double Z = 0; for (int e = 0; e < NEXP; e++) { w[e] *= pe[e]; Z += w[e]; }
        if (Z > 0) for (int e = 0; e < NEXP; e++) w[e] /= Z;
        for (int e = 0; e < NEXP; e++) w[e] = (1.0 - gamma) * w[e] + gamma / NEXP;

        model_observe(&M, b->data, t);
    }
    for (int e = 0; e < NEXP; e++) wsnap[e] = w[e];

    double mbpb = mixed_bits / (double)n, bbpb = base_bits / (double)n;
    printf("  experts: nested backoffs (unigram");
    for (int o = 0; o < NORD; o++) printf(", ≤order-%d", M.orders[o]);
    printf("), Bayesian mix\n");
    printf("  bits/byte   mixed %.3f   vs fixed-backoff %.3f   (%+.1f%% from feedback)\n",
           mbpb, bbpb, bbpb > 0 ? 100.0 * (bbpb - mbpb) / bbpb : 0);

    printf("  posterior weights learned from prediction error (start -> end):\n");
    static char nb[NEXP][14];
    snprintf(nb[0], 14, "unigram");
    for (int o = 0; o < NORD; o++) snprintf(nb[o+1], 14, "<=order-%d", M.orders[o]);
    for (int e = 0; e < NEXP; e++)
        printf("    %-11s %5.2f -> %5.2f\n", nb[e], 1.0/NEXP, wsnap[e]);

    /* surprisal map */
    double norm[64];
    for (int i = 0; i < NW; i++) norm[i] = wincnt[i] ? (winbits[i]/(double)wincnt[i])/8.0 : 0;
    char spark[512]; sparkline(norm, NW, spark, sizeof(spark));
    printf("  surprisal map (model bits/byte per window; tall = info-dense/anomalous):\n");
    printf("    %s\n", spark);
    /* top hot spots */
    int top[3] = {-1,-1,-1};
    for (int i = 0; i < NW; i++) {
        double v = norm[i];
        for (int r = 0; r < 3; r++) {
            if (top[r] < 0 || v > norm[top[r]]) {
                for (int j = 2; j > r; j--) top[j] = top[j-1];
                top[r] = i; break;
            }
        }
    }
    printf("  hottest regions:");
    for (int r = 0; r < 3; r++) if (top[r] >= 0)
        printf(" 0x%zx(%.1f)", (size_t)top[r] * n / NW, norm[top[r]] * 8);
    printf("\n");
    printf("  -> the surprise (prediction error) feeds back into the mixing weights\n");
    printf("     every byte: a deterministic, online echo of a transformer's gradient loop.\n");
    model_free(&M);
}

/* Encode n bytes with the online model; returns malloc'd buffer, sets *outn. */
static unsigned char *model_encode(const unsigned char *d, size_t n, size_t *outn) {
    double p[256]; uint32_t freq[256];
    model M; fresh_model(&M, n);
    renc e; e.low = 0; e.range = 0xFFFFFFFFu; e.buf = NULL; e.n = 0; e.cap = 0;
    for (size_t t = 0; t < n; t++) {
        model_dist(&M, d, t, p);
        quantise(p, freq);
        unsigned char s = d[t];
        uint32_t cum = 0; for (int i = 0; i < s; i++) cum += freq[i];
        renc_encode(&e, cum, freq[s], CTOT);
        model_observe(&M, d, t);
    }
    renc_flush(&e);
    model_free(&M);
    *outn = e.n;
    return e.buf;
}

/* Decode n bytes from a coded stream into out (caller-allocated, n bytes). */
static void model_decode(const unsigned char *coded, size_t cn, unsigned char *out, size_t n) {
    double p[256]; uint32_t freq[256];
    model M; fresh_model(&M, n);
    rdec d; rdec_init(&d, coded, cn);
    for (size_t t = 0; t < n; t++) {
        model_dist(&M, out, t, p);          /* out[0..t-1] already decoded */
        quantise(p, freq);
        uint32_t f = rdec_getfreq(&d, CTOT);
        uint32_t cum = 0; int s = 0;
        while (s < 256 && cum + freq[s] <= f) { cum += freq[s]; s++; }
        if (s == 256) s = 255;
        rdec_decode(&d, cum, freq[s]);
        out[t] = (unsigned char)s;
        model_observe(&M, out, t);
    }
    model_free(&M);
}

void compress_report(const blob *b) {
    section("compression (model-driven arithmetic coding)");
    size_t n = b->len; bool capped = false;
    if (n > COMPRESS_CAP) { n = COMPRESS_CAP; capped = true; }
    if (n < 16) { printf("  (too small)\n"); return; }
    if (capped) printf("  (first %u KiB)\n", COMPRESS_CAP >> 10);

    size_t csize;
    unsigned char *enc = model_encode(b->data, n, &csize);
    unsigned char *dec = malloc(n);
    bool lossless = false;
    if (enc && dec) { model_decode(enc, csize, dec, n); lossless = memcmp(dec, b->data, n) == 0; }

    double ratio = csize ? (double)n / (double)csize : 0;
    double bpb = csize ? 8.0 * (double)csize / (double)n : 0;
    printf("  original    %zu bytes\n", n);
    printf("  compressed  %zu bytes  (%.3f bits/byte, %.2fx smaller)\n", csize, bpb, ratio);
    printf("  round-trip  %s\n", lossless ? "LOSSLESS (decoded == original)" : "!! MISMATCH");
    free(enc); free(dec);
}

/* ---- real on-disk compressor ----
 * .atnz = "ATNZ2\n"(6) | NORD(1) | orders[NORD] | u64 len | coded stream
 * The order config is embedded and validated so a future change to
 * model_set_orders() can't silently mis-decode an old file.
 */
#define ATNZ_MAGIC "ATNZ2\n"
#define ATNZ_CAP (64u << 20)
#define ATNZ_HDR (6 + 1 + NORD + 8)

int lm_compress_file(const blob *b, const char *outpath) {
    if (b->len > ATNZ_CAP) { fprintf(stderr, "atn: file too large to compress (>64 MiB)\n"); return 1; }
    size_t n = b->len, csize;
    unsigned char *enc = model_encode(b->data, n, &csize);
    if (!enc) { fprintf(stderr, "atn: compress: out of memory\n"); return 1; }

    model ref; memset(&ref, 0, sizeof(ref)); model_set_orders(&ref);
    unsigned char hdr[ATNZ_HDR]; size_t h = 0;
    memcpy(hdr, ATNZ_MAGIC, 6); h = 6;
    hdr[h++] = (unsigned char)NORD;
    for (int o = 0; o < NORD; o++) hdr[h++] = (unsigned char)ref.orders[o];
    for (int i = 0; i < 8; i++) hdr[h++] = (unsigned char)((uint64_t)n >> (8 * i));

    FILE *f = fopen(outpath, "wb");
    if (!f) { fprintf(stderr, "atn: %s: cannot write\n", outpath); free(enc); return 1; }
    fwrite(hdr, 1, sizeof(hdr), f);
    fwrite(enc, 1, csize, f);
    fclose(f);
    free(enc);
    double bpb = n ? 8.0 * (double)(csize + sizeof(hdr)) / (double)n : 0;
    fprintf(stderr, "atn: compressed -> %s  (%zu -> %zu bytes, %.3f bits/byte)\n",
            outpath, n, csize + sizeof(hdr), bpb);
    return 0;
}

int lm_decompress_file(const blob *in, const char *outpath) {
    if (in->len < ATNZ_HDR || memcmp(in->data, ATNZ_MAGIC, 6) != 0) {
        fprintf(stderr, "atn: not an .atnz (v2) stream\n"); return 1;
    }
    size_t h = 6;
    int nord = in->data[h++];
    model ref; memset(&ref, 0, sizeof(ref)); model_set_orders(&ref);
    if (nord != NORD) { fprintf(stderr, "atn: incompatible model (order count)\n"); return 1; }
    for (int o = 0; o < NORD; o++) if (in->data[h++] != (unsigned char)ref.orders[o]) {
        fprintf(stderr, "atn: incompatible model (orders differ from this build)\n"); return 1;
    }
    uint64_t n = 0; for (int i = 0; i < 8; i++) n |= (uint64_t)in->data[h++] << (8 * i);
    if (n > ATNZ_CAP) { fprintf(stderr, "atn: implausible length in header\n"); return 1; }

    unsigned char *out = malloc(n ? n : 1);
    if (!out) { fprintf(stderr, "atn: decompress: out of memory\n"); return 1; }
    model_decode(in->data + ATNZ_HDR, in->len - ATNZ_HDR, out, n);
    FILE *f = outpath ? fopen(outpath, "wb") : stdout;
    if (!f) { fprintf(stderr, "atn: %s: cannot write\n", outpath); free(out); return 1; }
    fwrite(out, 1, n, f);
    if (outpath) fclose(f);
    free(out);
    if (outpath) fprintf(stderr, "atn: decompressed -> %s (%" PRIu64 " bytes)\n", outpath, n);
    return 0;
}

/* ---------------------------------------------------------------- */
/* Public entry: the language-model part of the -Z section           */
/* ---------------------------------------------------------------- */

/* ---------------------------------------------------------------- */
/* Chat mode: the model learns from what you type (the reality port), */
/* persists the conversation as its "brain", and replies by sampling. */
/* ---------------------------------------------------------------- */

/* Generate up to maxout printable bytes, seeded by the tail of `seed`;
 * stops at a newline. Non-printable samples are skipped to keep the
 * terminal clean. Returns the number of bytes written to out. */
static int gen_text(const model *M, const unsigned char *seed, size_t seedlen,
                    double temp, char *out, int maxout) {
    if (temp < 0.05) temp = 0.05;
    int hist = M->orders[NORD-1];
    unsigned char ctx[8];
    memset(ctx, 0, sizeof(ctx));
    size_t take = seedlen < (size_t)hist ? seedlen : (size_t)hist;
    for (size_t k = 0; k < take; k++) ctx[hist - take + k] = seed[seedlen - take + k];

    int n = 0;
    double p[256];
    for (int step = 0; step < maxout * 6 && n < maxout; step++) {
        double sum = 0;
        for (int b = 0; b < 256; b++) {
            double pr = pow(model_prob(M, ctx, (size_t)hist, (unsigned char)b), 1.0 / temp);
            p[b] = pr; sum += pr;
        }
        double r = rng_unit() * sum, acc = 0; int pick = 255;
        for (int b = 0; b < 256; b++) { acc += p[b]; if (r <= acc) { pick = b; break; } }
        memmove(ctx, ctx + 1, hist - 1); ctx[hist-1] = (unsigned char)pick;
        if (pick == '\n') { if (n > 0) break; else continue; }  /* skip leading blanks */
        if (isprint(pick) || pick == '\t') out[n++] = (char)pick;
    }
    return n;
}

/* ---- saved weights: the trained n-gram tables, as a binary cache ----
 * NOTE: for this model the "weights" are just counts derived from the
 * transcript, so this file is a fast-load / consolidated-memory artifact,
 * not independent information. It stores the transcript length it was built
 * from, so a stale cache is detected and the model is rebuilt instead.
 * Host-endian binary (a local cache, not a portable format). */
#define WMAGIC "ATNW1\n"

static void save_weights(const model *M, uint64_t tlen, const char *path) {
    FILE *f = fopen(path, "wb"); if (!f) return;
    fwrite(WMAGIC, 1, 6, f);
    uint8_t nord = NORD; fwrite(&nord, 1, 1, f);
    for (int o = 0; o < NORD; o++) { uint8_t m = (uint8_t)M->orders[o]; fwrite(&m, 1, 1, f); }
    fwrite(&tlen, 8, 1, f);
    fwrite(&M->uni_total, 8, 1, f);
    fwrite(M->uni, 4, 256, f);
    for (int o = 0; o < NORD; o++) {
        for (int pass = 0; pass < 2; pass++) {
            const u64map *mp = pass ? &M->tot[o] : &M->cnt[o];
            uint64_t live = 0;
            for (size_t s = 0; s < mp->cap; s++) if (mp->used[s]) live++;
            fwrite(&live, 8, 1, f);
            for (size_t s = 0; s < mp->cap; s++) if (mp->used[s]) {
                fwrite(&mp->k[s], 8, 1, f); fwrite(&mp->v[s], 4, 1, f);
            }
        }
    }
    fclose(f);
}

/* Load weights iff they exist and match the current transcript length. */
static bool load_weights(model *M, uint64_t expect_tlen, const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) return false;
    char mg[6]; uint8_t nord;
    if (fread(mg, 1, 6, f) != 6 || memcmp(mg, WMAGIC, 6) || fread(&nord, 1, 1, f) != 1 || nord != NORD) {
        fclose(f); return false;
    }
    memset(M, 0, sizeof(*M));
    for (int o = 0; o < NORD; o++) { uint8_t m; if (fread(&m, 1, 1, f) != 1) { fclose(f); return false; } M->orders[o] = m; }
    uint64_t tlen;
    if (fread(&tlen, 8, 1, f) != 1 || tlen != expect_tlen) { fclose(f); return false; }  /* stale -> rebuild */
    if (fread(&M->uni_total, 8, 1, f) != 1 || fread(M->uni, 4, 256, f) != 256) { fclose(f); return false; }
    for (int o = 0; o < NORD; o++) {
        for (int pass = 0; pass < 2; pass++) {
            uint64_t live;
            if (fread(&live, 8, 1, f) != 1) { model_free(M); fclose(f); return false; }
            u64map *mp = pass ? &M->tot[o] : &M->cnt[o];
            map_init_cap(mp, live ? live : 16, (size_t)1 << 27);  /* hold all saved */
            for (uint64_t i = 0; i < live; i++) {
                uint64_t k; uint32_t v;
                if (fread(&k, 8, 1, f) != 1 || fread(&v, 4, 1, f) != 1) { model_free(M); fclose(f); return false; }
                map_put(mp, k, v);
            }
        }
    }
    fclose(f);
    return true;
}

/* ---- autotrain: ingest a whole directory of text into the brain ---- */

static bool is_texty(const unsigned char *d, size_t n) {
    if (n == 0) return false;
    size_t check = n < 8192 ? n : 8192, printable = 0, nul = 0;
    for (size_t i = 0; i < check; i++) {
        unsigned char c = d[i];
        if (c == 0) nul++;
        if (isprint(c) || c == '\n' || c == '\r' || c == '\t') printable++;
    }
    return nul == 0 && (double)printable / (double)check > 0.90;
}

static bool skip_name(const char *path) {
    size_t L = strlen(path);
    const char *exts[] = { ".brain", ".weights", ".atcm", ".atnz", ".o", NULL };
    for (int i = 0; exts[i]; i++) {
        size_t e = strlen(exts[i]);
        if (L >= e && strcmp(path + L - e, exts[i]) == 0) return true;
    }
    return false;
}

/* ---- optional HTML -> text cleaner (for --strip-html) ---- */
static size_t find_ci(const unsigned char *d, size_t n, size_t from, const char *pat) {
    size_t pl = strlen(pat);
    for (size_t i = from; i + pl <= n; i++) {
        size_t k = 0;
        for (; k < pl; k++) if (tolower(d[i+k]) != tolower((unsigned char)pat[k])) break;
        if (k == pl) return i;
    }
    return n;
}
/* Decode an HTML entity at s (len avail). Writes ASCII into out; returns input
 * bytes consumed, or 0 if s is not a well-formed entity. */
static int decode_entity(const unsigned char *s, size_t avail, char *out) {
    if (avail < 3 || s[0] != '&') return 0;
    size_t semi = 0;
    for (size_t k = 1; k < avail && k < 12; k++) {
        if (s[k] == ';') { semi = k; break; }
        if (!isalnum(s[k]) && s[k] != '#') break;
    }
    if (!semi) return 0;
    if (s[1] == '#') {
        long c = (s[2]=='x'||s[2]=='X') ? strtol((const char*)s+3,NULL,16) : strtol((const char*)s+2,NULL,10);
        const char *r = " ";
        char tmp[2];
        if (c==8216||c==8217||c==39) r="'";
        else if (c==8220||c==8221||c==34) r="\"";
        else if (c==8211) r="-";
        else if (c==8212) r="--";
        else if (c==8230) r="...";
        else if (c==160) r=" ";
        else if (c>=32 && c<127) { tmp[0]=(char)c; tmp[1]=0; r=tmp; }
        strcpy(out, r); return (int)(semi + 1);
    }
    char name[12]; size_t nl = semi - 1;
    if (nl == 0 || nl >= sizeof(name)) return 0;
    memcpy(name, s+1, nl); name[nl] = 0;
    static const struct { const char *n, *r; } E[] = {
        {"amp","&"},{"lt","<"},{"gt",">"},{"quot","\""},{"apos","'"},{"nbsp"," "},
        {"mdash","--"},{"ndash","-"},{"rsquo","'"},{"lsquo","'"},{"rdquo","\""},
        {"ldquo","\""},{"hellip","..."},{"copy","(c)"},{"deg"," deg "},{NULL,NULL}
    };
    for (int i = 0; E[i].n; i++) if (!strcmp(name, E[i].n)) { strcpy(out, E[i].r); return (int)(semi+1); }
    out[0] = 0; return (int)(semi + 1);   /* unknown named entity -> drop */
}
static unsigned char *html_to_text(const unsigned char *d, size_t n, size_t *outlen) {
    unsigned char *out = malloc(n + 1);
    if (!out) { *outlen = 0; return NULL; }
    size_t o = 0, i = 0;
    while (i < n) {
        unsigned char c = d[i];
        if (c == '<') {
            if (i+7 <= n && strncasecmp((const char*)d+i, "<script", 7) == 0) {
                size_t e = find_ci(d, n, i, "</script>"); i = e < n ? e + 9 : n;
            } else if (i+6 <= n && strncasecmp((const char*)d+i, "<style", 6) == 0) {
                size_t e = find_ci(d, n, i, "</style>"); i = e < n ? e + 8 : n;
            } else {
                size_t j = i + 1; while (j < n && d[j] != '>') j++; i = j < n ? j + 1 : n;
            }
            if (o > 0 && out[o-1] != ' ' && out[o-1] != '\n') out[o++] = ' ';
        } else if (c == '&') {
            char rep[8]; int adv = decode_entity(d+i, n-i, rep);
            if (adv > 0) { for (char *p = rep; *p; p++) out[o++] = (unsigned char)*p; i += adv; }
            else { out[o++] = '&'; i++; }
        } else { out[o++] = c; i++; }
    }
    /* collapse: spaces->1, drop space before newline, cap blank-line runs at 1 */
    size_t w = 0; int nl = 0; bool sp = false;
    for (size_t r = 0; r < o; r++) {
        unsigned char c = out[r];
        if (c == '\r') continue;
        if (c == ' ' || c == '\t') { if (sp || (w && out[w-1] == '\n')) continue; out[w++] = ' '; sp = true; }
        else if (c == '\n') { if (w && out[w-1] == ' ') w--; nl++; if (nl <= 2) out[w++] = '\n'; sp = false; }
        else { out[w++] = c; sp = false; nl = 0; }
    }
    out[w] = 0; *outlen = w;
    return out;
}

/* Append one file's text to the brain (texty check + optional HTML strip).
 * Returns bytes written. */
static size_t ingest_file(FILE *bw, const unsigned char *d, size_t n, bool strip) {
    if (!is_texty(d, n)) return 0;
    if (strip) {
        size_t cl; unsigned char *c = html_to_text(d, n, &cl);
        if (!c) return 0;
        fwrite(c, 1, cl, bw);
        if (cl && c[cl-1] != '\n') fputc('\n', bw);
        free(c);
        return cl;
    }
    fwrite(d, 1, n, bw);
    if (n && d[n-1] != '\n') fputc('\n', bw);
    return n;
}

static void train_walk(const char *path, FILE *bw, uint64_t *files, uint64_t *bytes, int depth, bool strip) {
    DIR *dp = opendir(path);
    if (!dp) return;
    struct dirent *de;
    char child[4096];
    while ((de = readdir(dp))) {
        if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, "..")) continue;
        int nw = snprintf(child, sizeof(child), "%s/%s", strcmp(path, "/") ? path : "", de->d_name);
        if (nw <= 0 || (size_t)nw >= sizeof(child)) continue;
        struct stat st;
        if (lstat(child, &st) != 0 || S_ISLNK(st.st_mode)) continue;
        if (S_ISDIR(st.st_mode)) { if (depth < 64) train_walk(child, bw, files, bytes, depth + 1, strip); continue; }
        if (!S_ISREG(st.st_mode) || skip_name(child)) continue;

        FILE *f = fopen(child, "rb");
        if (!f) continue;
        blob b;
        if (read_stream(f, &b)) {
            size_t w = ingest_file(bw, b.data, b.len, strip);
            if (w) { (*files)++; *bytes += w; printf("  + %-50s %zu bytes\n", child, w); }
            free(b.data);
        }
        fclose(f);
    }
    closedir(dp);
}

void autotrain(const char *dir, const char *brainpath, bool strip_html, bool quiet) {
    FILE *bw = fopen(brainpath, "ab");
    if (!bw) { fprintf(stderr, "atn: cannot open brain %s\n", brainpath); return; }

    fprintf(stderr, "atn: training on %s -> %s%s\n", dir, brainpath, strip_html ? " (stripping HTML)" : "");
    uint64_t files = 0, bytes = 0;
    struct stat st;
    if (stat(dir, &st) == 0 && S_ISREG(st.st_mode)) {
        FILE *f = fopen(dir, "rb");
        if (f) { blob b; if (read_stream(f, &b)) {
            size_t w = ingest_file(bw, b.data, b.len, strip_html);
            if (w) { files = 1; bytes = w; printf("  + %-50s %zu bytes\n", dir, w); }
            free(b.data); } fclose(f); }
    } else {
        train_walk(dir, bw, &files, &bytes, 0, strip_html);
    }
    fclose(bw);

    /* Rebuild the model from the whole brain, refresh weights, report learnability. */
    FILE *bf = fopen(brainpath, "rb");
    if (bf) {
        blob brain;
        if (read_stream(bf, &brain)) {
            model M; model_build_reserve(&M, &brain, brain.len);
            char wpath[4200]; snprintf(wpath, sizeof(wpath), "%s.weights", brainpath);
            save_weights(&M, (uint64_t)brain.len, wpath);
            model_free(&M);
            printf("atn: ingested %" PRIu64 " files, %" PRIu64 " bytes; brain now %zu bytes",
                   files, bytes, brain.len);
            if (brain.len > MODEL_CAP) printf(" (model uses first %u MiB)", MODEL_CAP >> 20);
            printf("\n");
            if (!quiet) {       /* the learnability pass is a second full O(n) pass; skip with -q */
                double bpb = model_bpb_online(&brain);
                histogram h; hist_build(&brain, &h); double e0 = hist_entropy(&h);
                printf("atn: learnability %.3f bits/byte under the model (order-0 entropy %.3f; "
                       "lower = more predictable corpus)\n", bpb, e0);
            }
            free(brain.data);
        }
        fclose(bf);
    }
    bool dflt = strstr(brainpath, "atn.brain") != NULL;
    printf("atn: done. query it:  echo \"hi\" | atn --ask%s%s    (or chat:  atn -c%s%s)\n",
           dflt ? "" : " --brain ", dflt ? "" : brainpath,
           dflt ? "" : " --brain ", dflt ? "" : brainpath);
}

void chat_session(const char *brainpath, double temp) {
    if (temp <= 0) temp = 0.7;
    /* Load the brain: a plain-text transcript of everything ever said TO it.
     * (We train on the human's words — the reality term — not our own output,
     * which would just feed back on itself.) */
    unsigned char *T = NULL; size_t Tn = 0, Tcap = 1 << 16;
    T = malloc(Tcap);
    if (!T) { fprintf(stderr, "atn: chat: out of memory\n"); return; }
    FILE *bf = fopen(brainpath, "rb");
    if (bf) {
        size_t got;
        while ((got = fread(T + Tn, 1, Tcap - Tn, bf)) > 0) {
            Tn += got;
            if (Tn == Tcap) { Tcap *= 2; unsigned char *nt = realloc(T, Tcap); if (!nt) break; T = nt; }
        }
        fclose(bf);
    }

    /* Weights file sits beside the brain (e.g. atn.brain -> atn.brain.weights).
     * Use it if it matches the transcript; otherwise rebuild from the text. */
    char wpath[4200];
    snprintf(wpath, sizeof(wpath), "%s.weights", brainpath);
    model M;
    if (!load_weights(&M, (uint64_t)Tn, wpath)) {
        blob b0 = { T, Tn }; model_build_reserve(&M, &b0, 1u << 18);  /* headroom */
    }
    rng_seed(0xC0FFEEull ^ (uint64_t)Tn ^ ((uint64_t)Tn << 21));

    /* Persist incrementally (append each line as it arrives) so an abrupt
     * exit — Ctrl-C, a kill, a crash — never loses what you taught it. */
    FILE *bw = fopen(brainpath, "ab");

    char reply[256];
    int rn = gen_text(&M, T, Tn, temp, reply, Tn ? 120 : 24);
    fputs("atn: ", stdout);
    fwrite(reply, 1, rn, stdout);
    if (rn == 0) fputs("(untrained — teach me by typing)", stdout);
    fputs("\n", stdout);

    char line[8192];
    for (;;) {
        fputs("> ", stdout); fflush(stdout);
        if (!fgets(line, sizeof(line), stdin)) break;       /* Ctrl-D exits */
        if (strcmp(line, "/q\n") == 0 || strcmp(line, "/quit\n") == 0) break;

        /* Ingest: append to the transcript and train on each new byte. */
        size_t len = strlen(line);
        for (size_t i = 0; i < len; i++) {
            if (Tn == Tcap) { Tcap *= 2; unsigned char *nt = realloc(T, Tcap); if (!nt) break; T = nt; }
            T[Tn] = (unsigned char)line[i];
            model_observe(&M, T, Tn);
            Tn++;
        }
        if (bw) { fwrite(line, 1, len, bw); fflush(bw); }   /* save immediately */
        /* Reply: sample a continuation from what it has learned. */
        rn = gen_text(&M, T, Tn, temp, reply, 160);
        fputs("atn: ", stdout);
        if (rn > 0) fwrite(reply, 1, rn, stdout); else fputc('.', stdout);
        fputs("\n", stdout);
    }

    if (bw) fclose(bw);     /* transcript already persisted incrementally */
    save_weights(&M, (uint64_t)Tn, wpath);   /* consolidate the trained tables */
    model_free(&M);
    free(T);
    fputs("\n", stdout);
}

/* Ask mode: for EACH line on stdin, print one reply line. One piped line is a
 * single one-shot turn (cron / spare-cycle use); many piped lines are answered
 * in a batch with the brain loaded just once, so N queries cost one load plus
 * N cheap generations. By default it learns from the input (the conversation
 * accumulates and persists); learn=false queries a corpus read-only. */
void chat_once(const char *brainpath, double temp, bool learn) {
    if (temp <= 0) temp = 0.7;

    unsigned char *T = NULL; size_t Tn = 0, Tcap = 1 << 16;
    T = malloc(Tcap); if (!T) return;
    FILE *bf = fopen(brainpath, "rb");
    if (bf) {
        size_t got;
        while ((got = fread(T + Tn, 1, Tcap - Tn, bf)) > 0) {
            Tn += got;
            if (Tn == Tcap) { Tcap *= 2; unsigned char *nt = realloc(T, Tcap); if (!nt) break; T = nt; }
        }
        fclose(bf);
    }

    char wpath[4200]; snprintf(wpath, sizeof(wpath), "%s.weights", brainpath);
    model M;
    if (!load_weights(&M, (uint64_t)Tn, wpath)) {       /* load once */
        blob b0 = { T, Tn }; model_build_reserve(&M, &b0, 1u << 18);
    }
    rng_seed(0xC0FFEEull ^ (uint64_t)Tn ^ ((uint64_t)Tn << 17));

    FILE *bw = learn ? fopen(brainpath, "ab") : NULL;
    char line[8192], reply[256];
    bool dirty = false;
    while (fgets(line, sizeof(line), stdin)) {          /* one reply per line */
        size_t len = strlen(line);
        for (size_t i = 0; i < len; i++) {
            if (Tn == Tcap) { Tcap *= 2; unsigned char *nt = realloc(T, Tcap); if (!nt) break; T = nt; }
            T[Tn] = (unsigned char)line[i];
            if (learn) model_observe(&M, T, Tn);        /* train (or just seed) */
            Tn++;
        }
        if (bw) { fwrite(line, 1, len, bw); fflush(bw); dirty = true; }

        int rn = gen_text(&M, T, Tn, temp, reply, 200);
        fwrite(reply, 1, rn, stdout); fputc('\n', stdout);
        fflush(stdout);
    }

    if (bw) fclose(bw);
    if (learn && dirty) save_weights(&M, (uint64_t)Tn, wpath);  /* save once */
    model_free(&M); free(T);
}

/* Score mode: for each stdin line, print its surprisal (bits/byte) under the
 * brain, then the line. Low = the line fits the corpus's statistics ("typical
 * of this corpus"); high = novel / off-topic / foreign. Read-only. This is the
 * "does this belong to today's news / how surprising is it" signal. */
void score_query(const char *brainpath) {
    unsigned char *T = NULL; size_t Tn = 0, Tcap = 1 << 16;
    T = malloc(Tcap); if (!T) return;
    FILE *bf = fopen(brainpath, "rb");
    if (bf) {
        size_t got;
        while ((got = fread(T + Tn, 1, Tcap - Tn, bf)) > 0) {
            Tn += got;
            if (Tn == Tcap) { Tcap *= 2; unsigned char *nt = realloc(T, Tcap); if (!nt) break; T = nt; }
        }
        fclose(bf);
    }
    char wpath[4200]; snprintf(wpath, sizeof(wpath), "%s.weights", brainpath);
    model M;
    if (!load_weights(&M, (uint64_t)Tn, wpath)) {
        blob b0 = { T, Tn }; model_build_reserve(&M, &b0, 1u << 18);
    }
    char line[8192];
    while (fgets(line, sizeof(line), stdin)) {
        size_t len = strlen(line);
        while (len && (line[len-1] == '\n' || line[len-1] == '\r')) len--;
        if (len == 0) { putchar('\n'); continue; }
        double bits = 0;
        for (size_t i = 0; i < len; i++)
            bits += -log2(model_prob(&M, (const unsigned char*)line, i, (unsigned char)line[i]));
        printf("%6.3f\t%.*s\n", bits / (double)len, (int)len, line);
        fflush(stdout);
    }
    model_free(&M); free(T);
}

/* ---------------------------------------------------------------- */
/* Public model API (used by the filesystem-corpus mode in fleet.c)  */
/* ---------------------------------------------------------------- */

void *lm_build(const blob *corpus) {
    model *M = malloc(sizeof(model));
    if (!M) return NULL;
    model_build(M, corpus);
    return M;
}
/* Static cross-entropy of b under a fixed (already-built) model. */
double lm_score_bpb(void *handle, const blob *b) {
    model *M = handle; if (!M) return 0;
    size_t n = b->len; if (n > MODEL_CAP) n = MODEL_CAP;
    if (n == 0) return 0;
    double bits = 0;
    for (size_t t = 0; t < n; t++)
        bits += -log2(model_prob(M, b->data, t, b->data[t]));
    return bits / (double)n;
}
void lm_sample(void *handle, const blob *seed, double temp, int gen) {
    if (handle) model_generate((model *)handle, seed, temp, gen);
}
void lm_free_model(void *handle) {
    if (handle) { model_free((model *)handle); free(handle); }
}

void lm_report(const blob *b, double temp, int gen) {
    double bpb = model_bpb_online(b);               /* honest prequential bpb */
    double order0 = 0;
    { histogram h; hist_build(b, &h); order0 = hist_entropy(&h); }

    printf("  language model (unlearned n-gram, orders 3+6 w/ backoff, online):\n");
    printf("    cross-entropy   %.3f bits/byte   (order-0 entropy %.3f)\n", bpb, order0);
    printf("    would compress  %.2fx vs raw 8-bit  (~%.0f%% smaller, adaptive-coder size)\n",
           bpb > 0 ? 8.0 / bpb : 0.0, 100.0 * (1.0 - bpb / 8.0));
    if (bpb < order0 - 0.1)
        printf("    -> beats order-0 entropy: the model learns structure as it reads (it works).\n");
    else
        printf("    -> ~order-0: little sequential structure to exploit (e.g. random/encrypted).\n");

    /* Generation uses a model built from the whole file (memorising the file's
     * style is fine here — we *want* it to sound like the file). */
    model M; model_build(&M, b);
    printf("  autoregressive generation (temperature sampling, deterministic PRNG):\n");
    model_generate(&M, b, temp, gen);
    model_free(&M);
}
