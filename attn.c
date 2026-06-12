/*
 * attn.c — a deterministic, *unlearned* "attention head" over file bytes.
 *
 * This is the self-similarity / autocorrelation idea pushed until it looks
 * like transformer attention. Two related things are computed:
 *
 *  1) Soft self-attention: each byte position becomes a token; we give it a
 *     fixed content embedding plus a sinusoidal positional encoding (straight
 *     out of "Attention Is All You Need"), then run scaled dot-product
 *     attention with a causal mask and softmax — exactly the transformer
 *     operation, except the Q/K/V projections are hand-built constants rather
 *     than learned weights. We report the attention map and its statistics.
 *
 *  2) Induction head: the mechanism behind in-context learning. For each
 *     position it finds earlier positions whose preceding context matches the
 *     current context and predicts the byte that followed them — i.e. it does
 *     GPT's actual job, next-token (next-byte) prediction, with a hard top-1
 *     attention over exact context matches. The prediction accuracy is a real
 *     number you can compare across files (and against the 1/256 baseline).
 *
 * Nothing here is trained; it stays in atn's deterministic spirit.
 */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define D 32                       /* model dimension                    */
#define INDUCTION_CAP (8u << 20)   /* cap induction scan at 8 MiB         */

static void bchar(unsigned char c, char *out) {
    if (isprint(c) && c != ' ') sprintf(out, "'%c'", c);
    else sprintf(out, "0x%02x", c);
}

/* ---------------------------------------------------------------- */
/* Soft scaled-dot-product self-attention (causal)                  */
/* ---------------------------------------------------------------- */

static void build_embed_table(double tbl[256][D]) {
    for (int v = 0; v < 256; v++) {
        double norm = 0;
        for (int k = 0; k < D; k++) {
            /* deterministic hash -> value in [-1, 1] (a fixed "embedding") */
            uint32_t h = (uint32_t)v * 2654435761u ^ ((uint32_t)k * 40503u + 0x9e3779b9u);
            h ^= h >> 13; h *= 0x85ebca6bu; h ^= h >> 16;
            double val = ((double)(h % 4001) / 2000.0) - 1.0;
            tbl[v][k] = val; norm += val * val;
        }
        norm = sqrt(norm); if (norm < 1e-9) norm = 1;
        for (int k = 0; k < D; k++) tbl[v][k] /= norm;
    }
}

static void soft_attention(const blob *b, size_t AW) {
    static double tbl[256][D];
    build_embed_table(tbl);

    double (*e)[D] = malloc(AW * sizeof(*e));
    double *w = malloc(AW * sizeof(double));
    const int GRID = 24;
    double *grid = calloc((size_t)GRID * GRID, sizeof(double));
    if (!e || !w || !grid) { free(e); free(w); free(grid); printf("  (out of memory)\n"); return; }

    /* token embedding = content[byte] + sinusoidal positional encoding */
    for (size_t i = 0; i < AW; i++) {
        unsigned char x = b->data[i];
        for (int k = 0; k < D; k++) {
            double denom = pow(10000.0, (double)(k & ~1) / D);
            double pe = (k % 2 == 0) ? sin((double)i / denom) : cos((double)i / denom);
            e[i][k] = tbl[x][k] + 0.5 * pe;
        }
    }

    double sum_dist = 0, sum_ent = 0, best_peak = -1;
    size_t best_i = 0, best_j = 0;

    for (size_t i = 0; i < AW; i++) {
        double mx = -1e30;
        for (size_t j = 0; j <= i; j++) {
            double dot = 0; for (int k = 0; k < D; k++) dot += e[i][k] * e[j][k];
            dot /= sqrt((double)D);            /* scaled dot product */
            w[j] = dot; if (dot > mx) mx = dot;
        }
        double s = 0;
        for (size_t j = 0; j <= i; j++) { w[j] = exp(w[j] - mx); s += w[j]; }
        double inv = 1.0 / s, dist = 0, ent = 0, peake = 0; size_t peakej = 0;
        for (size_t j = 0; j <= i; j++) {
            double p = w[j] * inv;
            dist += p * (double)(i - j);
            if (p > 1e-12) ent -= p * log2(p);
            if (j < i && p > peake) { peake = p; peakej = j; }  /* strongest non-self */
            int gi = (int)(i * GRID / AW), gj = (int)(j * GRID / AW);
            grid[(size_t)gi * GRID + gj] += p;
        }
        sum_dist += dist; sum_ent += ent;
        /* Highlight the strongest attend-back (ignoring self-attention). */
        if (i > AW / 8 && peake > best_peak) {
            best_peak = peake; best_i = i; best_j = peakej;
        }
    }

    double gmax = 0;
    for (size_t c = 0; c < (size_t)GRID * GRID; c++) if (grid[c] > gmax) gmax = grid[c];

    printf("  soft self-attention: %zu tokens, dim %d, sinusoidal positions, causal softmax\n", AW, D);
    printf("    mean attention distance  %.1f bytes  (how far back each token looks)\n", sum_dist / (double)AW);
    printf("    mean attention entropy   %.2f bits   (low = peaked/decisive, high = diffuse)\n", sum_ent / (double)AW);
    if (best_peak > 0) {
        char qc[8], kc[8];
        bchar(b->data[best_i], qc); bchar(b->data[best_j], kc);
        printf("    most peaked token: pos %zu (%s) attends to pos %zu (%s), lag %zu, weight %.2f\n",
               best_i, qc, best_j, kc, best_i - best_j, best_peak);
    }
    printf("    attention map (row = query pos, col = key pos; causal lower-triangle):\n");
    const char *sh = " .:-=+*#%@"; int nsh = 9;
    for (int gi = 0; gi < GRID; gi++) {
        printf("      ");
        for (int gj = 0; gj < GRID; gj++) {
            double v = gmax > 0 ? grid[(size_t)gi * GRID + gj] / gmax : 0;
            int idx = (int)(v * (nsh - 1) + 0.5); if (idx < 0) idx = 0; if (idx >= nsh) idx = nsh - 1;
            putchar(sh[idx]);
        }
        putchar('\n');
    }
    free(e); free(w); free(grid);
}

/* ---------------------------------------------------------------- */
/* Stacked attention: feed the output back in, layer after layer    */
/* ---------------------------------------------------------------- */

static void layernorm(double *v) {
    double mean = 0; for (int k = 0; k < D; k++) mean += v[k]; mean /= D;
    double var = 0; for (int k = 0; k < D; k++) { double d = v[k] - mean; var += d*d; } var /= D;
    double inv = 1.0 / sqrt(var + 1e-6);
    for (int k = 0; k < D; k++) v[k] = (v[k] - mean) * inv;
}

static void iterate_attention(const blob *b, size_t AW, int L) {
    static double tbl[256][D];
    build_embed_table(tbl);

    double (*e)[D] = malloc(AW * sizeof(*e));
    double (*o)[D] = malloc(AW * sizeof(*o));
    double *w = malloc(AW * sizeof(double));
    if (!e || !o || !w) { free(e); free(o); free(w); printf("  (out of memory)\n"); return; }

    for (size_t i = 0; i < AW; i++) {
        unsigned char x = b->data[i];
        for (int k = 0; k < D; k++) {
            double denom = pow(10000.0, (double)(k & ~1) / D);
            double pe = (k % 2 == 0) ? sin((double)i / denom) : cos((double)i / denom);
            e[i][k] = tbl[x][k] + 0.5 * pe;
        }
    }

    printf("  stacked attention layers (each layer's output is fed back as input):\n");
    printf("    %-7s %-11s %-13s %-9s\n", "layer", "attn dist", "attn entropy", "delta");
    for (int layer = 1; layer <= L; layer++) {
        double sdist = 0, sent = 0;
        for (size_t i = 0; i < AW; i++) {
            double mx = -1e30;
            for (size_t j = 0; j <= i; j++) {
                double dot = 0; for (int k = 0; k < D; k++) dot += e[i][k] * e[j][k];
                dot /= sqrt((double)D); w[j] = dot; if (dot > mx) mx = dot;
            }
            double s = 0; for (size_t j = 0; j <= i; j++) { w[j] = exp(w[j] - mx); s += w[j]; }
            double inv = 1.0 / s, dist = 0, ent = 0;
            for (int k = 0; k < D; k++) o[i][k] = 0;
            for (size_t j = 0; j <= i; j++) {
                double p = w[j] * inv; dist += p * (double)(i - j);
                if (p > 1e-12) ent -= p * log2(p);
                for (int k = 0; k < D; k++) o[i][k] += p * e[j][k];   /* attention output */
            }
            sdist += dist; sent += ent;
        }
        double delta = 0;
        for (size_t i = 0; i < AW; i++) {
            double tmp[D], d2 = 0;
            for (int k = 0; k < D; k++) tmp[k] = e[i][k] + o[i][k];   /* residual add */
            layernorm(tmp);
            for (int k = 0; k < D; k++) { double dd = tmp[k] - e[i][k]; d2 += dd*dd; e[i][k] = tmp[k]; }
            delta += sqrt(d2);
        }
        printf("    %-7d %-11.1f %-13.2f %-9.3f\n", layer, sdist/(double)AW, sent/(double)AW, delta/(double)AW);
    }
    printf("    (delta = how much the representation still moves; it settles as it iterates)\n");
    free(e); free(o); free(w);
}

/* ---------------------------------------------------------------- */
/* Induction head: hard top-1 attention -> next-byte prediction     */
/* ---------------------------------------------------------------- */

typedef struct { size_t off; uint64_t ctx; unsigned char pred, actual; } sample;

/* ---------------------------------------------------------------- */
/* The 2-layer induction CIRCUIT, weights set by construction.       */
/* This is the actual mechanism (Elhage/Olsson et al.) by which a    */
/* 2-layer attention-only transformer does in-context learning:      */
/*   layer 0 = a previous-token head: each position copies the token */
/*             at t-1 into its residual stream.                      */
/*   layer 1 = an induction head: query = current token, key = the   */
/*             previous-token info written by layer 0, so it attends  */
/*             to positions preceded by the current token, and its    */
/*             OV circuit copies the token THERE -> predicts the byte */
/*             that followed the last time this byte appeared.        */
/* No learning: the QK/OV "weights" are fixed by construction.        */
/* ---------------------------------------------------------------- */
static void induction_circuit(const blob *b, size_t window) {
    printf("  2-layer induction circuit (prev-token head -> induction head, by construction):\n");
    size_t W = b->len; if (W > window) W = window; if (W > 512) W = 512;
    if (W < 4) { printf("    (too small)\n"); return; }

    const unsigned char *d = b->data;
    /* layer 0 writes prev[t] = d[t-1]; we just read d[t-1] directly. */

    const int G = 16;
    double *g0 = calloc((size_t)G*G, sizeof(double));   /* prev-token attn  */
    double *g1 = calloc((size_t)G*G, sizeof(double));   /* induction attn   */
    if (!g0 || !g1) { free(g0); free(g1); printf("    (out of memory)\n"); return; }

    uint64_t correct = 0, cov = 0;
    int ex_i = -1, ex_pred = 0, ex_match = 0;
    for (size_t i = 2; i < W; i++) {
        unsigned char cur = d[i-1];                 /* query = current token */
        g0[(i*G/W)*G + ((i-1)*G/W)] += 1.0;         /* layer-0: attends t-1  */

        /* layer-1 induction: attend to j in [1,i-1] with d[j-1]==cur (key) */
        int votes[256]; memset(votes, 0, sizeof(votes));
        int nmatch = 0, best = -1, bestc = 0;
        for (size_t j = 1; j < i; j++) {
            if (d[j-1] == cur) {                    /* key matches query     */
                unsigned char follow = d[j];        /* OV copies token here  */
                votes[follow]++; nmatch++;
                if (votes[follow] > bestc) { bestc = votes[follow]; best = follow; }
                g1[(i*G/W)*G + (j*G/W)] += 1.0;
            }
        }
        if (nmatch) {
            cov++;
            if ((unsigned char)best == d[i]) {
                correct++;
                if (ex_i < 0 && isprint(d[i]) && isprint(cur)) { ex_i = (int)i; ex_pred = best; ex_match = nmatch; }
            }
        }
    }

    double acc = cov ? 100.0 * (double)correct / (double)cov : 0;
    printf("    next-byte accuracy over %zu bytes: %.1f%% when the byte recurred"
           "  (vs 0.39%% chance)\n", W, acc);
    if (ex_i >= 0) {
        char qc[8], pc[8]; bchar(d[ex_i-1], qc); bchar((unsigned char)ex_pred, pc);
        printf("    e.g. @0x%x: query %s -> %d earlier match(es) -> predicts %s (correct)\n",
               ex_i, qc, ex_match, pc);
    }

    /* render the two attention patterns side by side */
    double m0 = 0, m1 = 0;
    for (size_t c = 0; c < (size_t)G*G; c++) { if (g0[c] > m0) m0 = g0[c]; if (g1[c] > m1) m1 = g1[c]; }
    const char *sh = " .:-=+*#%@"; int ns = 9;
    printf("    layer-0 prev-token head      layer-1 induction head\n");
    for (int r = 0; r < G; r++) {
        printf("    ");
        for (int c = 0; c < G; c++) { double v = m0 ? g0[(size_t)r*G+c]/m0 : 0; putchar(sh[(int)(v*(ns-1)+0.5)]); }
        printf("     ");
        for (int c = 0; c < G; c++) { double v = m1 ? g1[(size_t)r*G+c]/m1 : 0; putchar(sh[(int)(v*(ns-1)+0.5)]); }
        putchar('\n');
    }
    printf("    (layer 0 is the sub-diagonal 'look back one'; layer 1 attends to where\n"
           "     the current byte occurred before — induction = in-context copying.)\n");
    free(g0); free(g1);
}

static void induction(const blob *b) {
    size_t n = b->len; if (n > INDUCTION_CAP) n = INDUCTION_CAP;

    printf("  induction head (hard top-1 attention over exact prior contexts):\n");
    if (n < 4) { printf("    (too small)\n"); return; }
    if (b->len > INDUCTION_CAP)
        printf("    (measured over the first %u MiB)\n", INDUCTION_CAP >> 20);
    printf("    %-7s %-10s %-15s %-9s\n", "order", "coverage", "acc(covered)", "overall");

    int orders[] = {1, 3, 8};
    sample samples[3]; int nsamp = 0;

    for (size_t oi = 0; oi < sizeof(orders)/sizeof(orders[0]); oi++) {
        int m = orders[oi];
        if (n <= (size_t)m + 1) continue;
        size_t cap = 1; while (cap < n * 2 && cap < (1u << 22)) cap <<= 1;
        uint64_t *keys = malloc(cap * sizeof(uint64_t));
        unsigned char *nb = malloc(cap);
        char *used = calloc(cap, 1);
        if (!keys || !nb || !used) { free(keys); free(nb); free(used); printf("    (out of memory)\n"); break; }

        uint64_t correct = 0, total = 0, cov = 0;
        bool last_order = (oi == sizeof(orders)/sizeof(orders[0]) - 1);

        for (size_t t = (size_t)m; t < n; t++) {
            uint64_t ctx = 0;
            for (int k = 0; k < m; k++) ctx = (ctx << 8) | b->data[t - m + k];
            unsigned char actual = b->data[t];

            size_t slot = (ctx * 1099511628211ull) & (cap - 1);
            bool found = false; size_t probes = 0;
            while (used[slot] && probes < cap) {
                if (keys[slot] == ctx) { found = true; break; }
                slot = (slot + 1) & (cap - 1); probes++;
            }
            total++;
            if (found) {
                cov++;
                if (nb[slot] == actual) {
                    correct++;
                    if (last_order && nsamp < 3 && m >= 4 && isprint(actual)) {
                        samples[nsamp].off = t; samples[nsamp].ctx = ctx;
                        samples[nsamp].pred = nb[slot]; samples[nsamp].actual = actual; nsamp++;
                    }
                }
                nb[slot] = actual;                 /* attend to most-recent */
            } else if (!used[slot]) {
                used[slot] = 1; keys[slot] = ctx; nb[slot] = actual;
            }
        }
        double coverage = 100.0 * (double)cov / (double)total;
        double accov = cov ? 100.0 * (double)correct / (double)cov : 0;
        double overall = 100.0 * (double)correct / (double)total;
        printf("    m=%-5d %7.1f%%  %12.1f%%   %7.1f%%\n", m, coverage, accov, overall);
        free(keys); free(nb); free(used);
    }
    printf("    random baseline (1/256) = 0.39%%\n");
    for (int i = 0; i < nsamp; i++) {
        char pc[8]; bchar(samples[i].pred, pc);
        unsigned char ctxb[8]; int m = 8;
        for (int k = 0; k < m; k++) ctxb[k] = (unsigned char)(samples[i].ctx >> (8*(m-1-k)));
        printf("    e.g. @0x%zx context \"", samples[i].off);
        for (int k = 0; k < m; k++) putchar(isprint(ctxb[k]) ? ctxb[k] : '.');
        printf("\" -> predicted %s  (correct)\n", pc);
    }
}

/* ---------------------------------------------------------------- */
/* Generation by the attention softmax itself (no n-gram tables):    */
/* keys = context embeddings of source positions, values = the byte  */
/* that followed; the query attends over them and we sample the      */
/* attention-weighted next-byte distribution. This is fuzzy (partial */
/* context) matching — what real attention does — not table lookup.  */
/* ---------------------------------------------------------------- */

static uint64_t arng = 0x243F6A8885A308D3ull;
static double arng_unit(void) { uint64_t x=arng; x^=x<<13; x^=x>>7; x^=x<<17; arng=x; return (double)(x>>11)/(double)(1ull<<53); }

#define CK 6        /* context length for the attention key */

static void ctx_embed(const double tbl[256][D], const unsigned char *c, double *out) {
    for (int k = 0; k < D; k++) out[k] = 0;
    double decay = 1.0, norm = 0;
    for (int r = 0; r < CK; r++) {                 /* most recent byte = c[CK-1] */
        unsigned char by = c[CK - 1 - r];
        for (int k = 0; k < D; k++) out[k] += decay * tbl[by][k];
        decay *= 0.7;
    }
    for (int k = 0; k < D; k++) norm += out[k]*out[k];
    norm = sqrt(norm); if (norm < 1e-9) norm = 1;
    for (int k = 0; k < D; k++) out[k] /= norm;
}

static void soft_attn_generate(const blob *b, double temp, int gen) {
    printf("  generation by the attention softmax itself (fuzzy context, no tables):\n");
    if (b->len < CK + 2) { printf("    (too small)\n"); return; }
    if (temp < 0.05) temp = 0.05;
    arng = 0x243F6A8885A308D3ull ^ (uint64_t)b->len;

    static double tbl[256][D]; build_embed_table(tbl);

    /* sample up to MEMSZ source positions evenly across the file */
    const size_t MEMSZ = 8192;
    size_t avail = b->len - 1 - (CK - 1);
    size_t stride = avail > MEMSZ ? avail / MEMSZ : 1;
    size_t cnt = 0;
    for (size_t j = CK - 1; j + 1 < b->len; j += stride) cnt++;
    if (cnt == 0) { printf("    (too small)\n"); return; }

    double (*K)[D] = malloc(cnt * sizeof(*K));
    unsigned char *V = malloc(cnt);
    double *logit = malloc(cnt * sizeof(double));
    if (!K || !V || !logit) { free(K); free(V); free(logit); printf("    (out of memory)\n"); return; }
    size_t idx = 0;
    for (size_t j = CK - 1; j + 1 < b->len && idx < cnt; j += stride, idx++) {
        ctx_embed(tbl, b->data + (j - (CK - 1)), K[idx]);
        V[idx] = b->data[j + 1];
    }

    unsigned char ctx[CK];
    for (int k = 0; k < CK; k++) ctx[k] = b->data[b->len - CK + k];

    char out[400]; int outn = 0;
    double q[D], dist[256];
    int glen = gen > (int)sizeof(out) - 1 ? (int)sizeof(out) - 1 : gen;
    for (int step = 0; step < glen; step++) {
        ctx_embed(tbl, ctx, q);
        double mx = -1e30;
        for (size_t j = 0; j < cnt; j++) {
            double dot = 0; for (int k = 0; k < D; k++) dot += q[k]*K[j][k];
            dot /= sqrt((double)D) * temp;
            logit[j] = dot; if (dot > mx) mx = dot;
        }
        double s = 0; for (size_t j = 0; j < cnt; j++) { logit[j] = exp(logit[j]-mx); s += logit[j]; }
        for (int i = 0; i < 256; i++) dist[i] = 0;
        for (size_t j = 0; j < cnt; j++) dist[V[j]] += logit[j];
        double r = arng_unit() * s, acc = 0; int pick = V[cnt-1];
        for (int i = 0; i < 256; i++) { acc += dist[i]; if (r <= acc) { pick = i; break; } }
        out[outn++] = (char)pick;
        memmove(ctx, ctx + 1, CK - 1); ctx[CK-1] = (unsigned char)pick;
    }
    out[outn] = 0;
    printf("    generated %d bytes (attention-weighted over %zu key positions):\n      \"", outn, cnt);
    for (int i = 0; i < outn; i++) putchar(isprint((unsigned char)out[i]) ? out[i] : '.');
    printf("\"\n");
    free(K); free(V); free(logit);
}

void attention_report(const blob *b, size_t window, double temp, int gen) {
    section("attention (hand-wired, unlearned)");
    if (b->len < 8) { printf("  (too small)\n"); return; }

    size_t AW = window; if (AW < 16) AW = 16; if (AW > 1024) AW = 1024;
    if (AW > b->len) AW = b->len;

    soft_attention(b, AW);          /* one attention layer + the map        */
    printf("\n");
    iterate_attention(b, AW, 4);    /* feed the output back in, repeat       */
    printf("\n");
    induction(b);                   /* next-byte prediction (GPT's job)      */
    printf("\n");
    induction_circuit(b, AW);       /* the 2-layer circuit, by construction  */
    printf("\n");
    lm_report(b, temp, gen);        /* bits/byte + temperature generation    */
    printf("\n");
    soft_attn_generate(b, temp, gen); /* generation via the attention softmax */
    printf("    interpretation: the byte sweep is embedded, run through attention,\n"
           "    and the output is fed back layer after layer; the induction head then\n"
           "    predicts — and autoregressively generates — the next byte by copying\n"
           "    from matching prior context. It is the transformer loop, unlearned.\n");
}
