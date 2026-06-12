/*
 * cm.c — a bit-level CONTEXT-MIXING predictor + binary arithmetic coder.
 *
 * This is the feedback loop made load-bearing. Several context models each
 * predict the next *bit*; a logistic mixer combines them, and the mixer's
 * weights are trained ONLINE by gradient descent on the prediction error —
 * a one-layer neural network learning as it reads, which is exactly the
 * shape of the feedback that trains a transformer. The mixed probability
 * drives a binary arithmetic coder, so the same predictor compresses and
 * decompresses (in lockstep, losslessly). Deterministic, untrained.
 *
 * Lineage: this is a small lpaq/PAQ-style coder.
 */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- squash / stretch (logistic <-> logit), lpaq tables ---- */
static int squash(int d) {
    static const int t[33] = {1,2,3,6,10,16,27,45,73,120,194,310,488,747,1101,
        1546,2047,2549,2994,3348,3607,3785,3901,3975,4022,4050,4068,4079,4085,
        4089,4092,4093,4094};
    if (d >  2047) return 4095;
    if (d < -2047) return 0;
    int w = d & 127; d = (d >> 7) + 16;
    return (t[d]*(128-w) + t[d+1]*w + 64) >> 7;
}
static int STRETCH[4096];
static void init_stretch(void) {
    int pi = 0;
    for (int x = -2047; x <= 2047; x++) {
        int v = squash(x);
        for (int j = pi; j <= v; j++) STRETCH[j] = x;
        pi = v + 1;
    }
    for (int j = pi; j < 4096; j++) STRETCH[j] = 2047;
}

/* ---- the predictor ---- */
#define NM   7                 /* hashed context models               */
#define NIN  (NM + 1)          /* mixer inputs: + the match model      */
#define NSET 8                 /* mixer weight sets (by bit position)  */
#define TBITS 22
#define TSIZE (1u << TBITS)
#define TMASK (TSIZE - 1)

#define MINLEN 6               /* match-model context length          */
#define MHBITS 22
#define MHSIZE (1u << MHBITS)

static const int ORD[NM] = {0, 1, 2, 3, 4, 6, 8};

typedef struct {
    uint16_t *t[NM];           /* per-model bit probability, 16-bit     */
    uint8_t  *ct[NM];          /* per-slot visit count (adaptive rate)  */
    uint32_t base[NM];         /* per-byte context hash per model      */
    uint32_t idx[NM];          /* table index for the current bit      */
    int      st[NIN];          /* stretched prediction per mixer input  */
    int      wx[NSET][NIN];    /* mixer weights (online-trained)        */
    int      c0;               /* partial current byte (1..255)        */
    int      nbits;            /* bits seen in current byte (0..7)      */
    unsigned char hist[16];    /* recent finished bytes (hist[0]=last)  */
    int      pr;               /* final P(bit=1) used for coding, 12-bit */
    int      set;
    uint16_t *apm;             /* SSE: refine the mixed prob (16-bit)   */
    int      ai, ai2;          /* apm cells touched this bit            */
    /* match model (an induction head inside the compressor) */
    unsigned char *H;          /* full history of decoded/seen bytes    */
    size_t   Hn;               /* bytes in H                            */
    uint32_t *mhash;           /* context hash -> position after it      */
    size_t   mp;               /* predicted-byte index in H             */
    int      mlen;             /* current match length                  */
    uint16_t mmap[32];         /* P(match correct) by length bucket      */
    int      m_active, m_pbit, m_lenb;
} cm_t;
#define APMCTX 1024

static uint32_t hashb(const unsigned char *h, int k, int salt) {
    uint32_t x = (uint32_t)(salt + 1) * 0x9E3779B1u;
    for (int i = 0; i < k; i++) { x = (x + h[i] + 1) * 2654435761u; x ^= x >> 15; }
    return x;
}

static bool cm_init(cm_t *c, size_t n) {
    memset(c, 0, sizeof(*c));
    init_stretch();
    for (int i = 0; i < NM; i++) {
        c->t[i]  = malloc(TSIZE * sizeof(uint16_t));
        c->ct[i] = calloc(TSIZE, 1);
        if (!c->t[i] || !c->ct[i]) { for (int j = 0; j <= i; j++) { free(c->t[j]); free(c->ct[j]); } return false; }
        for (uint32_t k = 0; k < TSIZE; k++) c->t[i][k] = 32768;   /* p = 0.5 (16-bit) */
    }
    c->apm = malloc(APMCTX * 33 * sizeof(uint16_t));
    c->H = malloc(n ? n : 1);
    c->mhash = calloc(MHSIZE, sizeof(uint32_t));
    if (!c->apm || !c->H || !c->mhash) {
        for (int i = 0; i < NM; i++) { free(c->t[i]); free(c->ct[i]); }
        free(c->apm); free(c->H); free(c->mhash); return false;
    }
    for (int ctx = 0; ctx < APMCTX; ctx++)
        for (int j = 0; j < 33; j++) c->apm[ctx*33 + j] = (uint16_t)(squash((j-16)*128) * 16);
    for (int i = 0; i < 32; i++) c->mmap[i] = 32768;
    c->c0 = 1; c->nbits = 0;
    for (int i = 0; i < NM; i++) c->base[i] = hashb(c->hist, ORD[i], i);
    return true;
}
static void cm_free(cm_t *c) {
    for (int i = 0; i < NM; i++) { free(c->t[i]); free(c->ct[i]); }
    free(c->apm); free(c->H); free(c->mhash);
}

static uint32_t mhash_ctx(const unsigned char *H, size_t Hn) {
    uint32_t h = 0;
    for (int i = 0; i < MINLEN; i++) { h = (h * 2654435761u) + H[Hn - MINLEN + i] + 1; h ^= h >> 15; }
    return h & (MHSIZE - 1);
}

/* Predict P(next bit = 1), 12-bit (1..4094). */
static int cm_predict(cm_t *c) {
    c->set = c->nbits;
    for (int i = 0; i < NM; i++) {
        c->idx[i] = (c->base[i] * 0x2545F491u + (uint32_t)c->c0) & TMASK;
        int p = c->t[i][c->idx[i]];          /* 16-bit */
        c->st[i] = STRETCH[p >> 4];           /* stretch on 12-bit */
    }
    /* match model: if the current context recurred, predict the byte that
     * followed it last time — an induction head feeding the mixer. */
    c->m_active = 0; c->st[NM] = 0;
    if (c->mlen > 0 && c->mp < c->Hn) {
        unsigned char pbyte = c->H[c->mp];
        int expect = (1 << c->nbits) | (c->nbits ? (pbyte >> (8 - c->nbits)) : 0);
        if (expect == c->c0) {                /* bits so far match the prediction */
            int pbit = (pbyte >> (7 - c->nbits)) & 1;
            int lenb = c->mlen < 31 ? c->mlen : 31;
            int s = STRETCH[c->mmap[lenb] >> 4];
            c->st[NM] = pbit ? s : -s;
            c->m_active = 1; c->m_pbit = pbit; c->m_lenb = lenb;
        }
    }
    int64_t dot = 0;
    for (int i = 0; i < NIN; i++) dot += (int64_t)c->wx[c->set][i] * c->st[i];
    int d = (int)(dot >> 16);
    int pr = squash(d);

    /* SSE / APM: refine pr through an adaptive map indexed by (last byte,
     * partial byte) and the stretched probability bucket. */
    int ctx = ((c->hist[0] << 2) ^ c->c0) & (APMCTX - 1);
    int s = STRETCH[pr < 1 ? 1 : pr > 4094 ? 4094 : pr] + 2048;   /* 0..4095 */
    int w = s & 127; int j = s >> 7;
    c->ai = ctx*33 + j; c->ai2 = c->ai + 1;
    int refined = (c->apm[c->ai]*(128-w) + c->apm[c->ai2]*w) >> 11; /* ->12-bit */
    pr = (pr + 3*refined) >> 2;
    if (pr < 1) pr = 1;
    if (pr > 4094) pr = 4094;
    c->pr = pr;
    return pr;
}

/* Train on the actual bit, then advance the byte context. */
static void cm_update(cm_t *c, int bit) {
    int err = (bit ? 4095 : 0) - c->pr;             /* mixer error (12-bit)  */
    int t16 = bit ? 65535 : 0;                       /* counter target (16b)  */
    for (int i = 0; i < NIN; i++) {                  /* train the mixer       */
        int *w = &c->wx[c->set][i];
        *w += (c->st[i] * err) >> 10;
        if (*w >  (1 << 20)) *w =  (1 << 20);
        if (*w < -(1 << 20)) *w = -(1 << 20);
    }
    for (int i = 0; i < NM; i++) {                   /* adapt the bit models  */
        int n = c->ct[i][c->idx[i]];
        int rate = (n >> 1) + 1; if (rate > 7) rate = 7;
        uint16_t *p = &c->t[i][c->idx[i]];
        *p += (t16 - *p) >> rate;
        if (n < 30) c->ct[i][c->idx[i]] = (uint8_t)(n + 1);
    }
    /* calibrate the match model's confidence by match length */
    if (c->m_active) {
        int correct = (bit == c->m_pbit) ? 65535 : 0;
        c->mmap[c->m_lenb] += (correct - c->mmap[c->m_lenb]) >> 6;
    }
    /* train the SSE map */
    c->apm[c->ai]  += (t16 - c->apm[c->ai])  >> 6;
    c->apm[c->ai2] += (t16 - c->apm[c->ai2]) >> 6;

    c->c0 = (c->c0 << 1) | bit; c->nbits++;
    if (c->c0 >= 256) {                              /* byte finished         */
        unsigned char by = (unsigned char)(c->c0 & 0xff);
        c->H[c->Hn++] = by;
        for (int k = 15; k > 0; k--) c->hist[k] = c->hist[k-1];
        c->hist[0] = by;
        for (int i = 0; i < NM; i++) c->base[i] = hashb(c->hist, ORD[i], i);

        /* match model bookkeeping: extend if our prediction held, else relook */
        if (c->mlen > 0) {
            if (c->mp < c->Hn && c->H[c->mp] == by) { c->mp++; c->mlen++; }
            else c->mlen = 0;
        }
        if (c->Hn >= MINLEN) {
            uint32_t h = mhash_ctx(c->H, c->Hn);
            if (c->mlen == 0) {
                uint32_t cand = c->mhash[h];
                if (cand && cand < c->Hn) { c->mp = cand; c->mlen = 1; }
            }
            c->mhash[h] = (uint32_t)c->Hn;          /* next byte follows this ctx */
        }
        c->c0 = 1; c->nbits = 0;
    }
}

/* ---- binary arithmetic coder ---- */
typedef struct { uint32_t x1, x2; unsigned char *buf; size_t n, cap; } benc;
static void be_put(benc *e, unsigned char ch) {
    if (e->n == e->cap) { e->cap = e->cap ? e->cap*2 : 4096; e->buf = realloc(e->buf, e->cap); }
    e->buf[e->n++] = ch;
}
static void be_init(benc *e) { e->x1 = 0; e->x2 = 0xffffffffu; e->buf = NULL; e->n = 0; e->cap = 0; }
static void be_encode(benc *e, int bit, int p) {
    uint32_t range = e->x2 - e->x1;
    uint32_t xmid = e->x1 + (uint32_t)(((uint64_t)range * (uint32_t)p) >> 12);
    if (bit) e->x2 = xmid; else e->x1 = xmid + 1;
    while (((e->x1 ^ e->x2) & 0xff000000u) == 0) {
        be_put(e, (unsigned char)(e->x2 >> 24)); e->x1 <<= 8; e->x2 = (e->x2 << 8) | 0xff;
    }
}
static void be_flush(benc *e) { for (int i = 0; i < 4; i++) { be_put(e, (unsigned char)(e->x1 >> 24)); e->x1 <<= 8; } }

typedef struct { uint32_t x1, x2, x; const unsigned char *buf; size_t n, pos; } bdec;
static unsigned char bd_get(bdec *d) { return d->pos < d->n ? d->buf[d->pos++] : 0; }
static void bd_init(bdec *d, const unsigned char *buf, size_t n) {
    d->x1 = 0; d->x2 = 0xffffffffu; d->buf = buf; d->n = n; d->pos = 0; d->x = 0;
    for (int i = 0; i < 4; i++) d->x = (d->x << 8) | bd_get(d);
}
static int bd_decode(bdec *d, int p) {
    uint32_t range = d->x2 - d->x1;
    uint32_t xmid = d->x1 + (uint32_t)(((uint64_t)range * (uint32_t)p) >> 12);
    int bit = (d->x <= xmid);
    if (bit) d->x2 = xmid; else d->x1 = xmid + 1;
    while (((d->x1 ^ d->x2) & 0xff000000u) == 0) {
        d->x1 <<= 8; d->x2 = (d->x2 << 8) | 0xff; d->x = (d->x << 8) | bd_get(d);
    }
    return bit;
}

/* ---- encode / decode whole buffers ---- */
static unsigned char *cm_encode_buf(const unsigned char *d, size_t n, size_t *outn) {
    cm_t c; if (!cm_init(&c, n)) return NULL;
    benc e; be_init(&e);
    for (size_t t = 0; t < n; t++) {
        for (int b = 7; b >= 0; b--) {
            int bit = (d[t] >> b) & 1;
            int p = cm_predict(&c);
            be_encode(&e, bit, p);
            cm_update(&c, bit);
        }
    }
    be_flush(&e);
    cm_free(&c);
    *outn = e.n;
    return e.buf;
}
static bool cm_decode_buf(const unsigned char *coded, size_t cn, unsigned char *out, size_t n) {
    cm_t c; if (!cm_init(&c, n)) return false;
    bdec d; bd_init(&d, coded, cn);
    for (size_t t = 0; t < n; t++) {
        int byte = 0;
        for (int b = 7; b >= 0; b--) {
            int p = cm_predict(&c);
            int bit = bd_decode(&d, p);
            cm_update(&c, bit);
            byte = (byte << 1) | bit;
        }
        out[t] = (unsigned char)byte;
    }
    cm_free(&c);
    return true;
}

/* ---- public: report + file I/O ---- */
#define CM_CAP (16u << 20)
#define CMZ_MAGIC "ATCM1\n"
#define CMZ_HDR (6 + 8)

void cm_report(const blob *b) {
    section("compression (context-mixing, online-trained mixer)");
    size_t n = b->len; bool capped = false;
    if (n > CM_CAP) { n = CM_CAP; capped = true; }
    if (n < 16) { printf("  (too small)\n"); return; }
    if (capped) printf("  (first %u MiB)\n", CM_CAP >> 20);

    size_t csize;
    unsigned char *enc = cm_encode_buf(b->data, n, &csize);
    unsigned char *dec = malloc(n);
    bool ok = false;
    if (enc && dec) ok = cm_decode_buf(enc, csize, dec, n) && memcmp(dec, b->data, n) == 0;

    double bpb = csize ? 8.0 * (double)csize / (double)n : 0;
    printf("  %d context models (orders 0..8) + online logistic mixer + SSE\n", NM);
    printf("  original    %zu bytes\n", n);
    printf("  compressed  %zu bytes  (%.3f bits/byte, %.2fx smaller)\n",
           csize, bpb, csize ? (double)n/(double)csize : 0);
    printf("  round-trip  %s\n", ok ? "LOSSLESS (decoded == original)" : "!! MISMATCH");
    free(enc); free(dec);
}

int cm_compress_file(const blob *b, const char *outpath) {
    if (b->len > CM_CAP) { fprintf(stderr, "atn: file too large for cm (>16 MiB)\n"); return 1; }
    size_t n = b->len, csize;
    unsigned char *enc = cm_encode_buf(b->data, n, &csize);
    if (!enc) { fprintf(stderr, "atn: cm: out of memory\n"); return 1; }
    FILE *f = fopen(outpath, "wb");
    if (!f) { fprintf(stderr, "atn: %s: cannot write\n", outpath); free(enc); return 1; }
    unsigned char hdr[CMZ_HDR]; memcpy(hdr, CMZ_MAGIC, 6);
    for (int i = 0; i < 8; i++) hdr[6+i] = (unsigned char)((uint64_t)n >> (8*i));
    fwrite(hdr, 1, sizeof(hdr), f); fwrite(enc, 1, csize, f); fclose(f); free(enc);
    fprintf(stderr, "atn: compressed -> %s  (%zu -> %zu bytes, %.3f bits/byte)\n",
            outpath, n, csize + sizeof(hdr), n ? 8.0*(double)(csize+sizeof(hdr))/(double)n : 0);
    return 0;
}

/* Returns 1 if this looks like a cm stream (so the dispatcher can route). */
int cm_is_stream(const blob *in) {
    return in->len >= CMZ_HDR && memcmp(in->data, CMZ_MAGIC, 6) == 0;
}

int cm_decompress_file(const blob *in, const char *outpath) {
    if (!cm_is_stream(in)) { fprintf(stderr, "atn: not an ATCM stream\n"); return 1; }
    uint64_t n = 0; for (int i = 0; i < 8; i++) n |= (uint64_t)in->data[6+i] << (8*i);
    if (n > CM_CAP) { fprintf(stderr, "atn: implausible length\n"); return 1; }
    unsigned char *out = malloc(n ? n : 1);
    if (!out) { fprintf(stderr, "atn: cm: out of memory\n"); return 1; }
    if (!cm_decode_buf(in->data + CMZ_HDR, in->len - CMZ_HDR, out, n)) { free(out); return 1; }
    FILE *f = outpath ? fopen(outpath, "wb") : stdout;
    if (!f) { fprintf(stderr, "atn: %s: cannot write\n", outpath); free(out); return 1; }
    fwrite(out, 1, n, f); if (outpath) fclose(f); free(out);
    if (outpath) fprintf(stderr, "atn: decompressed -> %s (%" PRIu64 " bytes)\n", outpath, n);
    return 0;
}
