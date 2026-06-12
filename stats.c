/* stats.c — macro-level numeric metrics, entropy map, self-similarity. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ---------------------------------------------------------------- */
/* Deep statistics                                                  */
/* ---------------------------------------------------------------- */

void stats_report(const blob *b) {
    section("statistics");
    if (b->len == 0) { printf("  (empty file)\n"); return; }

    histogram h;
    hist_build(b, &h);
    const double n = (double)b->len;

    /* Mean, variance, median, min/max from the histogram. */
    double sum = 0;
    for (int i = 0; i < 256; i++) sum += (double)i * (double)h.freq[i];
    double mean = sum / n;

    double var = 0;
    for (int i = 0; i < 256; i++)
        var += (double)h.freq[i] * (i - mean) * (i - mean);
    var /= n;
    double sd = sqrt(var);

    int vmin = 0; while (vmin < 256 && h.freq[vmin] == 0) vmin++;
    int vmax = 255; while (vmax > 0 && h.freq[vmax] == 0) vmax--;
    uint64_t acc = 0, half = b->len / 2; int median = 0;
    for (int i = 0; i < 256; i++) { acc += h.freq[i]; if (acc > half) { median = i; break; } }
    int distinct = 0; for (int i = 0; i < 256; i++) if (h.freq[i]) distinct++;

    double H = hist_entropy(&h);

    /* Chi-square vs. a uniform distribution (expected n/256 per value). */
    double expv = n / 256.0, chi2 = 0;
    for (int i = 0; i < 256; i++) {
        double d = (double)h.freq[i] - expv;
        chi2 += d * d / expv;
    }
    /* df = 255; mean of chi-square is df, sd is sqrt(2*df) ~= 22.6. */
    double chi_z = (chi2 - 255.0) / sqrt(2.0 * 255.0);

    /* Serial correlation coefficient (ent's algorithm, with wrap-around). */
    double t1 = 0, t2 = 0, t3 = 0, last = 0, u0 = 0;
    bool first = true;
    for (size_t i = 0; i < b->len; i++) {
        double a = b->data[i];
        if (first) { first = false; u0 = a; }
        else t1 += last * a;
        t2 += a;
        t3 += a * a;
        last = a;
    }
    t1 += last * u0;
    double scc_den = n * t3 - t2 * t2;
    double scc = scc_den == 0 ? 0 : (n * t1 - t2 * t2) / scc_den;

    /* Monte-Carlo pi: 6 bytes per point (3 per coordinate). */
    double incirc = pow(pow(256.0, 3.0) - 1.0, 2.0);
    uint64_t mtries = 0, mhits = 0;
    for (size_t i = 0; i + 6 <= b->len; i += 6) {
        double x = 0, y = 0;
        for (int k = 0; k < 3; k++) x = x * 256 + b->data[i + k];
        for (int k = 0; k < 3; k++) y = y * 256 + b->data[i + 3 + k];
        mtries++;
        if (x * x + y * y <= incirc) mhits++;
    }
    double mpi = mtries ? 4.0 * (double)mhits / (double)mtries : 0;

    /* Noise / smoothness: mean absolute delta between consecutive bytes. */
    double mad = 0;
    for (size_t i = 1; i < b->len; i++)
        mad += fabs((double)b->data[i] - (double)b->data[i - 1]);
    if (b->len > 1) mad /= (double)(b->len - 1);

    /* RLE redundancy: fraction of bytes removable by run-length coding. */
    uint64_t runs = 0; size_t i2 = 0;
    while (i2 < b->len) { unsigned char c = b->data[i2]; runs++; while (i2 < b->len && b->data[i2] == c) i2++; }
    double rle_save = 1.0 - (double)runs / n; /* rough */

    /* Printable share. */
    uint64_t print = 0;
    for (int i = 0; i < 256; i++)
        if (isprint(i) || i=='\t' || i=='\n' || i=='\r') print += h.freq[i];

    printf("  bytes        %" PRIu64 "   distinct values %d/256\n", b->len, distinct);
    printf("  mean byte    %.3f   median %d   std-dev %.3f\n", mean, median, sd);
    printf("  range        min 0x%02x  max 0x%02x\n", vmin, vmax);
    printf("  entropy      %.4f bits/byte  (%.1f%% of max)\n", H, 100.0 * H / 8.0);
    printf("  est. compr.  ~%.1f%% of original if entropy-coded\n", 100.0 * H / 8.0);
    printf("  RLE redund.  %.1f%% (long runs of equal bytes)\n", 100.0 * rle_save);
    printf("  chi-square   %.1f  (z=%+.1f vs uniform; near 0 = random-like)\n", chi2, chi_z);
    printf("  serial corr. %+.4f  (0 = independent, ±1 = predictable)\n", scc);
    printf("  monte-carlo  pi=%.5f  error %.3f%%  (%"PRIu64" pts; near 0 = random)\n",
           mpi, mtries ? 100.0 * fabs(mpi - M_PI) / M_PI : 0.0, mtries);
    printf("  noise (mad)  %.2f  (mean |delta| of adjacent bytes; high = busy)\n", mad);
    printf("  printable    %.1f%%\n", 100.0 * (double)print / n);

    const char *verdict =
        H > 7.9 && fabs(chi_z) < 3 ? "looks random / encrypted / well-compressed"
      : H > 7.0 ? "high-entropy: compressed or media payload likely"
      : H > 4.5 ? "structured binary"
      : H > 2.0 ? "low-entropy / textual or repetitive"
      :           "very repetitive / sparse";
    printf("  read         %s\n", verdict);
}

/* ---------------------------------------------------------------- */
/* Windowed entropy map (binwalk-style)                             */
/* ---------------------------------------------------------------- */

void entropy_map(const blob *b, size_t window) {
    section("entropy map");
    if (b->len == 0) { printf("  (empty file)\n"); return; }
    if (window < 16) window = 16;

    size_t nwin = (b->len + window - 1) / window;
    double *ent = malloc(nwin * sizeof(double));
    if (!ent) { printf("  (out of memory)\n"); return; }

    for (size_t w = 0; w < nwin; w++) {
        size_t start = w * window;
        size_t end = start + window; if (end > b->len) end = b->len;
        uint64_t f[256] = {0};
        for (size_t i = start; i < end; i++) f[b->data[i]]++;
        double len = (double)(end - start), H = 0;
        for (int i = 0; i < 256; i++)
            if (f[i]) { double p = f[i] / len; H -= p * log2(p); }
        ent[w] = H / 8.0; /* normalize 0..1 */
    }

    /* Print a sparkline, chunked so very large files stay readable. */
    printf("  window %zu bytes, %zu windows (each glyph = one window):\n", window, nwin);
    char line[4096];
    size_t per_row = 100;
    for (size_t off = 0; off < nwin; off += per_row) {
        size_t cnt = nwin - off; if (cnt > per_row) cnt = per_row;
        sparkline(ent + off, cnt, line, sizeof(line));
        printf("  0x%08zx  %s\n", off * window, line);
    }

    /* Flag notable regions: high-entropy plateaus and sharp transitions. */
    int flagged = 0;
    for (size_t w = 0; w < nwin; w++) {
        bool hi = ent[w] > 0.95;
        bool edge = w > 0 && fabs(ent[w] - ent[w-1]) > 0.30;
        if (hi && (w == 0 || ent[w-1] <= 0.95)) {
            printf("    0x%08zx  high-entropy region begins (%.2f) — "
                   "compressed/encrypted/embedded\n", w * window, ent[w]*8);
            if (++flagged >= 12) break;
        } else if (edge) {
            printf("    0x%08zx  entropy %s (%.2f -> %.2f) — possible boundary\n",
                   w * window, ent[w] > ent[w-1] ? "rises" : "drops",
                   ent[w-1]*8, ent[w]*8);
            if (++flagged >= 12) break;
        }
    }
    if (flagged == 0) printf("    (no sharp entropy transitions)\n");
    free(ent);
}

/* ---------------------------------------------------------------- */
/* Self-similarity / periodicity / repeated n-grams                 */
/* ---------------------------------------------------------------- */

/* Match fraction at a given period: how often data[i] == data[i+p]. */
static double period_match(const unsigned char *d, size_t n, size_t p) {
    if (p == 0 || p >= n) return 0;
    size_t cmp = n - p, same = 0;
    /* Sample to keep it cheap on large inputs. */
    size_t stride = cmp > 200000 ? cmp / 200000 : 1;
    size_t checked = 0;
    for (size_t i = 0; i < cmp; i += stride) { if (d[i] == d[i+p]) same++; checked++; }
    return checked ? (double)same / (double)checked : 0;
}

void similarity_report(const blob *b, size_t window) {
    section("self-similarity");
    if (b->len < 8) { printf("  (too small)\n"); return; }
    (void)window;

    /* 1) Periodicity sweep: find periods where the file repeats itself. */
    size_t maxp = b->len / 2; if (maxp > 65536) maxp = 65536;
    double best = 0; size_t bestp = 0;
    /* Track the top few independent peaks. */
    struct { size_t p; double m; } top[5] = {{0,0}};
    for (size_t p = 1; p <= maxp; p++) {
        double m = period_match(b->data, b->len, p);
        if (m > best) { best = m; bestp = p; }
        if (m > 0.30) {
            /* keep highest peaks, avoiding near-duplicates/multiples */
            for (int k = 0; k < 5; k++) {
                if (m > top[k].m) {
                    for (int j = 4; j > k; j--) top[j] = top[j-1];
                    top[k].p = p; top[k].m = m; break;
                }
            }
        }
    }
    printf("  strongest period: %zu bytes (%.1f%% of bytes repeat at that stride)\n",
           bestp, best * 100);
    if (best > 0.30) {
        printf("  candidate record/block sizes:\n");
        for (int k = 0; k < 5 && top[k].p; k++)
            printf("    %6zu bytes  %.1f%% match\n", top[k].p, top[k].m * 100);
    } else {
        printf("  no strong periodicity (file does not repeat at a fixed stride)\n");
    }

    /* 2) Repeated 8-grams via a hash table: find the most common chunks. */
    if (b->len >= 8) {
        size_t cap = 1; while (cap < b->len * 2 && cap < (1u<<22)) cap <<= 1;
        uint64_t *keys = calloc(cap, sizeof(uint64_t));
        uint32_t *cnts = calloc(cap, sizeof(uint32_t));
        size_t  *offs = calloc(cap, sizeof(size_t));
        if (keys && cnts && offs) {
            size_t stride = (b->len > 4000000) ? 4 : 1; /* sample huge files */
            for (size_t i = 0; i + 8 <= b->len; i += stride) {
                uint64_t k = 0;
                memcpy(&k, b->data + i, 8);
                if (k == 0) continue; /* skip null padding, too common */
                size_t slot = (k * 1099511628211ull) & (cap - 1);
                while (cnts[slot] && keys[slot] != k) slot = (slot + 1) & (cap - 1);
                if (!cnts[slot]) { keys[slot] = k; offs[slot] = i; }
                cnts[slot]++;
            }
            /* find top 5 counts */
            struct { uint64_t k; uint32_t c; size_t o; } tk[5] = {{0,0,0}};
            for (size_t s = 0; s < cap; s++) {
                if (cnts[s] < 2) continue;
                for (int r = 0; r < 5; r++) {
                    if (cnts[s] > tk[r].c) {
                        for (int j = 4; j > r; j--) tk[j] = tk[j-1];
                        tk[r].k = keys[s]; tk[r].c = cnts[s]; tk[r].o = offs[s]; break;
                    }
                }
            }
            if (tk[0].c >= 2) {
                printf("  most repeated 8-byte chunks:\n");
                for (int r = 0; r < 5 && tk[r].c >= 2; r++) {
                    unsigned char bytes[8]; memcpy(bytes, &tk[r].k, 8);
                    printf("    x%u  ", tk[r].c);
                    for (int j = 0; j < 8; j++) printf("%02x ", bytes[j]);
                    printf(" |");
                    for (int j = 0; j < 8; j++) putchar(isprint(bytes[j]) ? bytes[j] : '.');
                    printf("|  first @ 0x%zx\n", tk[r].o);
                }
            } else {
                printf("  no 8-byte chunk repeats (high diversity)\n");
            }
        }
        free(keys); free(cnts); free(offs);
    }
}
