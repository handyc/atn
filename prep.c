/*
 * prep.c — fast, training-free corpus preparation for (later) LLM training.
 *
 * Reads text line-by-line (one document/article/turn per line) from stdin or
 * files and emits a cleaned, de-duplicated, quality-filtered corpus to stdout.
 * No model is trained — this is pure data prep, the standard front of an LLM
 * pipeline, and it streams in O(total) time:
 *
 *   - clean:    collapse whitespace, drop control chars
 *   - filter:   drop too-short / OCR-garbage / low-alpha / repetitive lines
 *   - exact:    drop case/punctuation-normalised duplicates
 *   - near:     drop near-duplicates via MinHash + LSH (reworded wire stories)
 *
 * Deterministic (fixed-seed hashing). Stats go to stderr.
 *
 *   atn --prep file1 file2 ... > clean.txt
 *   cat corpus.txt | atn --prep > clean.txt
 *
 * Env: PREP_MINLEN=40, PREP_MINALPHA=0.55, PREP_NEAR=1 (0 disables near-dedup).
 */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- growable open-addressing uint64 set ---- */
typedef struct { uint64_t *k; char *used; size_t cap, n; } u64set;

static void set_init(u64set *s) {
    s->cap = 1u << 16; s->n = 0;
    s->k = malloc(s->cap * sizeof(uint64_t));
    s->used = calloc(s->cap, 1);
}
static void set_grow(u64set *s) {
    size_t oc = s->cap; uint64_t *ok = s->k; char *ou = s->used;
    s->cap *= 2; s->k = malloc(s->cap * sizeof(uint64_t)); s->used = calloc(s->cap, 1); s->n = 0;
    for (size_t i = 0; i < oc; i++) if (ou[i]) {
        uint64_t key = ok[i]; size_t j = (key * 0x9E3779B97F4A7C15ull) & (s->cap - 1);
        while (s->used[j]) j = (j + 1) & (s->cap - 1);
        s->used[j] = 1; s->k[j] = key; s->n++;
    }
    free(ok); free(ou);
}
static bool set_has(const u64set *s, uint64_t key) {
    size_t i = (key * 0x9E3779B97F4A7C15ull) & (s->cap - 1);
    while (s->used[i]) { if (s->k[i] == key) return true; i = (i + 1) & (s->cap - 1); }
    return false;
}
static void set_put(u64set *s, uint64_t key) {
    if ((s->n + 1) * 10 >= s->cap * 7) set_grow(s);
    size_t i = (key * 0x9E3779B97F4A7C15ull) & (s->cap - 1);
    while (s->used[i]) { if (s->k[i] == key) return; i = (i + 1) & (s->cap - 1); }
    s->used[i] = 1; s->k[i] = key; s->n++;
}

static uint64_t fnv(const unsigned char *d, size_t n, uint64_t h) {
    for (size_t i = 0; i < n; i++) { h ^= d[i]; h *= 1099511628211ull; }
    return h;
}

/* ---- one document at a time ---- */
typedef struct {
    size_t minlen;
    double minalpha;
    int near;
    /* MinHash / LSH */
    u64set exact, lsh;
    uint64_t kept, dropped_short, dropped_garbage, dropped_exact, dropped_near, total;
} prep;

#define K_SHINGLE 4          /* words per shingle               */
#define MINH      12         /* number of MinHash values        */
#define LSH_R     2          /* rows per band                   */
#define LSH_B     (MINH/LSH_R)
static const uint64_t MIX_A[MINH] = {
    0x100000001b3ull,0x9E3779B97F4A7C15ull,0xC2B2AE3D27D4EB4Full,0x165667B19E3779F9ull,
    0xD6E8FEB86659FD93ull,0xA0761D6478BD642Full,0xE7037ED1A0B428DBull,0x8EBC6AF09C88C6E3ull,
    0x589965CC75374CC3ull,0x1D8E4E27C47D124Full,0xEB44ACCAB455D165ull,0x2545F4914F6CDD1Dull };

/* clean: collapse whitespace, keep printable; returns new length (in place) */
static size_t clean_line(char *s, size_t n) {
    size_t w = 0; int sp = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        if (c == '\t' || c == '\r' || c == '\n' || c == ' ') { if (!sp && w) { s[w++] = ' '; sp = 1; } }
        else if (c >= 32 && c < 127) { s[w++] = (char)c; sp = 0; }
        else if (c >= 128) { s[w++] = (char)c; sp = 0; }   /* keep UTF-8 bytes */
        /* drop other control chars */
    }
    while (w && s[w-1] == ' ') w--;
    return w;
}

/* quality: false => drop. checks length, alpha ratio, repetitiveness */
static bool quality_ok(const char *s, size_t n, const prep *p) {
    if (n < p->minlen) return false;
    size_t alpha = 0; int distinct[256]; memset(distinct, 0, sizeof(distinct));
    size_t nd = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        if (isalpha(c) || c == ' ') alpha++;
        if (!distinct[c]) { distinct[c] = 1; nd++; }
    }
    if ((double)alpha / (double)n < p->minalpha) return false;   /* OCR garbage */
    if (nd < 8) return false;                                     /* too repetitive */
    return true;
}

/* normalised fingerprint hash: lowercase, alnum-only, single spaces */
static uint64_t fingerprint(const char *s, size_t n) {
    uint64_t h = 1469598103934665603ull; int sp = 1;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        if (isalnum(c)) { c = (unsigned char)tolower(c); h ^= c; h *= 1099511628211ull; sp = 0; }
        else if (!sp) { h ^= ' '; h *= 1099511628211ull; sp = 1; }
    }
    return h;
}

/* near-dup test via MinHash+LSH. returns true if near-duplicate of a kept doc;
 * otherwise registers the doc and returns false. */
static bool near_dup(prep *p, const char *s, size_t n) {
    /* hash words */
    uint64_t wh[4096]; size_t nw = 0;
    size_t i = 0;
    while (i < n && nw < 4096) {
        while (i < n && !isalnum((unsigned char)s[i])) i++;
        size_t st = i;
        while (i < n && isalnum((unsigned char)s[i])) i++;
        if (i > st) {
            uint64_t h = 1469598103934665603ull;
            for (size_t j = st; j < i; j++) { h ^= (unsigned char)tolower((unsigned char)s[j]); h *= 1099511628211ull; }
            wh[nw++] = h;
        }
    }
    if (nw < K_SHINGLE) return false;   /* too short to shingle; let exact handle it */

    uint64_t mins[MINH];
    for (int h = 0; h < MINH; h++) mins[h] = ~0ull;
    for (size_t k = 0; k + K_SHINGLE <= nw; k++) {
        uint64_t sh = 1469598103934665603ull;
        for (int j = 0; j < K_SHINGLE; j++) { sh ^= wh[k+j]; sh *= 1099511628211ull; }
        for (int h = 0; h < MINH; h++) {
            uint64_t v = sh * MIX_A[h]; v ^= v >> 29;
            if (v < mins[h]) mins[h] = v;
        }
    }
    /* LSH bands */
    uint64_t band[LSH_B];
    for (int b = 0; b < LSH_B; b++)
        band[b] = fnv((const unsigned char *)&mins[b*LSH_R], LSH_R * sizeof(uint64_t), (uint64_t)(b+1) * 1099511628211ull);

    bool dup = false;
    for (int b = 0; b < LSH_B; b++) if (set_has(&p->lsh, band[b])) { dup = true; break; }
    if (!dup) for (int b = 0; b < LSH_B; b++) set_put(&p->lsh, band[b]);
    return dup;
}

static void prep_line(prep *p, char *line, size_t n) {
    p->total++;
    size_t len = clean_line(line, n);
    if (len == 0) { p->dropped_short++; return; }
    if (!quality_ok(line, len, p)) {
        if (len < p->minlen) p->dropped_short++; else p->dropped_garbage++;
        return;
    }
    uint64_t fp = fingerprint(line, len);
    if (set_has(&p->exact, fp)) { p->dropped_exact++; return; }
    if (p->near && near_dup(p, line, len)) { p->dropped_near++; return; }
    set_put(&p->exact, fp);
    fwrite(line, 1, len, stdout); putchar('\n');
    p->kept++;
}

static void prep_stream(prep *p, FILE *f) {
    char *line = NULL; size_t cap = 0; ssize_t r;
    while ((r = getline(&line, &cap, f)) != -1) {
        size_t n = (size_t)r;
        while (n && (line[n-1] == '\n' || line[n-1] == '\r')) n--;
        prep_line(p, line, n);
    }
    free(line);
}

int prep_run(int argc, char **argv) {
    prep p; memset(&p, 0, sizeof(p));
    p.minlen   = (size_t)(getenv("PREP_MINLEN")   ? atoi(getenv("PREP_MINLEN"))   : 40);
    p.minalpha = getenv("PREP_MINALPHA") ? atof(getenv("PREP_MINALPHA")) : 0.55;
    p.near     = getenv("PREP_NEAR") ? atoi(getenv("PREP_NEAR")) : 1;
    set_init(&p.exact); set_init(&p.lsh);

    if (argc == 0) prep_stream(&p, stdin);
    else for (int i = 0; i < argc; i++) {
        FILE *f = fopen(argv[i], "rb");
        if (!f) { fprintf(stderr, "atn: prep: %s: cannot open\n", argv[i]); continue; }
        prep_stream(&p, f); fclose(f);
    }

    fprintf(stderr, "atn: prep %" PRIu64 " -> %" PRIu64 " lines "
            "(dropped: %" PRIu64 " short, %" PRIu64 " garbage, %" PRIu64 " exact-dup, %" PRIu64 " near-dup)\n",
            p.total, p.kept, p.dropped_short, p.dropped_garbage, p.dropped_exact, p.dropped_near);
    free(p.exact.k); free(p.exact.used); free(p.lsh.k); free(p.lsh.used);
    return 0;
}
