/* content.c — content-addressing kernels for the atn-ga brain network.
 *
 * This replaces the numpy code that used to live in atn-ga.py: per-chunk
 * MinHash / SimHash signatures plus the nearest-neighbour table a content
 * gene uses to gather topically-similar chunks. The GA calls
 *     atn --neighbors TERRITORY --nn-index index.tsv -o neighbors.bin
 * once per run (cached across cron ticks, like the old sigs.npy) and then
 * reads the table back as plain int32 rows — so the Python side needs no
 * numpy at all.
 *
 * neighbors.bin layout (native-endian int32):
 *     [0] n          number of chunks
 *     [1] rowcap     ints per row (n for exact, 401 for LSH)
 *     then n rows of `rowcap` ints: chunk i's neighbours ranked by signature
 *     similarity (most similar first; the seed itself ranks first), -1 padded.
 *
 * Tokenisation mirrors atn-ga.py's `[a-zà-ÿ0-9']+` over lower-cased text:
 * ASCII and the Latin-1 supplement are lower-cased per code point and the
 * class is matched on the resulting code point. It is a clean UTF-8 reimpl,
 * not bug-for-bug identical to Python's full-Unicode str.lower(), which is
 * irrelevant here — signatures only need to be deterministic and topical.
 */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- CRC-32 (IEEE, reflected) — matches Python's zlib.crc32 ------------- */
static uint32_t crc_table[256];
static void crc_init(void) {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++)
            c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : (c >> 1);
        crc_table[i] = c;
    }
}
/* crc32_update(crc32(a), b) == zlib.crc32(a+b); crc32(x)=crc32_update(0,x). */
static uint32_t crc32_update(uint32_t crc, const unsigned char *buf, size_t len) {
    crc ^= 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++)
        crc = crc_table[(crc ^ buf[i]) & 0xFF] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}
static uint32_t crc32_buf(const unsigned char *buf, size_t len) {
    return crc32_update(0, buf, len);
}

/* ---- signature constants (must match the old atn-ga.py) ---------------- */
#define SIG_BITS 128          /* SimHash width                              */
#define NH       32           /* MinHash hash count                         */
#define MIN_DF   2            /* drop hapax words                           */
#define LSH_THRESHOLD 2500    /* exact O(n^2) at or below this, else LSH    */
#define LSH_BANDS 16
#define LSH_CAP   400         /* neighbours kept per chunk under LSH        */

/* ---- tokeniser --------------------------------------------------------- */
/* Decode one UTF-8 code point at s (len bytes available). Returns the code
 * point and writes its byte length to *adv; on a malformed lead byte returns
 * the raw byte with *adv==1 (the caller treats unknown points as separators). */
static uint32_t utf8_decode(const unsigned char *s, size_t len, size_t *adv) {
    unsigned char c = s[0];
    if (c < 0x80) { *adv = 1; return c; }
    if ((c & 0xE0) == 0xC0 && len >= 2 && (s[1] & 0xC0) == 0x80) {
        *adv = 2; return ((uint32_t)(c & 0x1F) << 6) | (s[1] & 0x3F);
    }
    if ((c & 0xF0) == 0xE0 && len >= 3 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80) {
        *adv = 3; return ((uint32_t)(c & 0x0F) << 12) | ((uint32_t)(s[1] & 0x3F) << 6) | (s[2] & 0x3F);
    }
    if ((c & 0xF8) == 0xF0 && len >= 4 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80 && (s[3] & 0xC0) == 0x80) {
        *adv = 4; return ((uint32_t)(c & 0x07) << 18) | ((uint32_t)(s[1] & 0x3F) << 12) |
                         ((uint32_t)(s[2] & 0x3F) << 6) | (s[3] & 0x3F);
    }
    *adv = 1; return c;   /* malformed: skip one byte */
}

static uint32_t cp_lower(uint32_t cp) {
    if (cp >= 'A' && cp <= 'Z') return cp + 32;
    if (cp >= 0xC0 && cp <= 0xDE && cp != 0xD7) return cp + 0x20;  /* À-Þ -> à-þ */
    return cp;
}
static int cp_in_class(uint32_t cp) {            /* [a-z à-ÿ 0-9 '] */
    return (cp >= 'a' && cp <= 'z') || (cp >= 0xE0 && cp <= 0xFF) ||
           (cp >= '0' && cp <= '9') || cp == '\'';
}
/* CJK ideographs: Chinese (and shared Han) has no word spaces, so each
 * character is treated as its own one-character "word" for signatures. */
static int cp_is_cjk(uint32_t cp) {
    return cp >= 0x3400 && cp <= 0x9FFF;
}
/* append the UTF-8 encoding of code point cp (up to 3 bytes) to buf at *n */
static void cp_emit(unsigned char *buf, size_t *n, uint32_t cp) {
    if (cp < 0x80) {
        buf[(*n)++] = (unsigned char)cp;
    } else if (cp < 0x800) {
        buf[(*n)++] = 0xC0 | (cp >> 6); buf[(*n)++] = 0x80 | (cp & 0x3F);
    } else {
        buf[(*n)++] = 0xE0 | (cp >> 12);
        buf[(*n)++] = 0x80 | ((cp >> 6) & 0x3F);
        buf[(*n)++] = 0x80 | (cp & 0x3F);
    }
}

/* Tokenise [text,text+len); for each token call cb(word,wlen,udata). Latin
 * runs form words; each CJK character is its own token (no spaces in Chinese). */
typedef void (*tok_cb)(const unsigned char *word, size_t wlen, void *udata);
static void tokenize(const unsigned char *text, size_t len, tok_cb cb, void *udata) {
    unsigned char tok[1024];
    size_t tn = 0, i = 0;
    while (i < len) {
        size_t adv; uint32_t cp = cp_lower(utf8_decode(text + i, len - i, &adv));
        if (cp_is_cjk(cp)) {
            if (tn) { cb(tok, tn, udata); tn = 0; }       /* flush pending Latin word */
            unsigned char c[4]; size_t cn = 0; cp_emit(c, &cn, cp); cb(c, cn, udata);
        } else if (cp_in_class(cp)) {
            if (tn < sizeof(tok) - 4) cp_emit(tok, &tn, cp);  /* clamp absurd tokens */
        } else if (tn) { cb(tok, tn, udata); tn = 0; }
        i += adv;
    }
    if (tn) cb(tok, tn, udata);
}

/* ---- vocabulary hash map (open addressing, keyed by token bytes) ------- */
typedef struct {
    char    *word;
    uint32_t wlen;
    uint32_t crc;        /* crc32 of the word (MinHash hash)           */
    uint32_t df;         /* #chunks containing it                      */
    int32_t  lastchunk;  /* dedup df to once per chunk                 */
    int32_t  tmpcount;   /* per-chunk term frequency (sig pass)        */
    int32_t  vid;        /* index among df-filtered "kept" words (-1)  */
    uint64_t sign0, sign1; /* SimHash hyperplane signs (kept words)    */
} Vocab;

typedef struct {
    Vocab   *e;
    int32_t *slot;      /* hash -> entry index, -1 empty */
    size_t   cap, mask, count;
} VMap;

static void vmap_init(VMap *v, size_t hint) {
    size_t cap = 1024;
    while (cap < hint * 2) cap <<= 1;
    v->cap = cap; v->mask = cap - 1; v->count = 0;
    v->slot = malloc(cap * sizeof(int32_t));
    for (size_t i = 0; i < cap; i++) v->slot[i] = -1;
    v->e = malloc((cap / 2 + 16) * sizeof(Vocab));
}
static void vmap_grow(VMap *v) {
    size_t ncap = v->cap << 1;
    int32_t *ns = malloc(ncap * sizeof(int32_t));
    for (size_t i = 0; i < ncap; i++) ns[i] = -1;
    size_t nmask = ncap - 1;
    for (size_t i = 0; i < v->count; i++) {
        size_t h = v->e[i].crc & nmask;
        while (ns[h] != -1) h = (h + 1) & nmask;
        ns[h] = (int32_t)i;
    }
    free(v->slot); v->slot = ns; v->cap = ncap; v->mask = nmask;
    v->e = realloc(v->e, (ncap / 2 + 16) * sizeof(Vocab));
}
/* find or insert; returns entry index. */
static int32_t vmap_intern(VMap *v, const unsigned char *w, size_t wlen, uint32_t crc) {
    size_t h = crc & v->mask;
    while (v->slot[h] != -1) {
        Vocab *e = &v->e[v->slot[h]];
        if (e->crc == crc && e->wlen == wlen && memcmp(e->word, w, wlen) == 0)
            return v->slot[h];
        h = (h + 1) & v->mask;
    }
    if ((v->count + 1) * 2 > v->cap) { vmap_grow(v); return vmap_intern(v, w, wlen, crc); }
    int32_t id = (int32_t)v->count++;
    Vocab *e = &v->e[id];
    e->word = malloc(wlen); memcpy(e->word, w, wlen);
    e->wlen = (uint32_t)wlen; e->crc = crc; e->df = 0;
    e->lastchunk = -1; e->tmpcount = 0; e->vid = -1; e->sign0 = e->sign1 = 0;
    v->slot[h] = id;
    return id;
}

/* ---- pass 1: document frequencies -------------------------------------- */
typedef struct { VMap *v; int32_t chunk; } DfCtx;
static void df_cb(const unsigned char *w, size_t wlen, void *u) {
    DfCtx *c = u;
    int32_t id = vmap_intern(c->v, w, wlen, crc32_buf(w, wlen));
    Vocab *e = &c->v->e[id];
    if (e->lastchunk != c->chunk) { e->df++; e->lastchunk = c->chunk; }  /* once per chunk */
}

/* pass 2: accumulate a chunk's df-filtered ("kept") words + term frequencies. */
typedef struct { VMap *v; int32_t *touched; size_t ntouch, nkept; } SigCtx;
static void sig_cb(const unsigned char *w, size_t wlen, void *u) {
    SigCtx *c = u;
    int32_t id = vmap_intern(c->v, w, wlen, crc32_buf(w, wlen));
    Vocab *e = &c->v->e[id];
    if (e->vid >= 0) {                          /* survived the df filter */
        if (e->tmpcount == 0) { c->touched[c->ntouch++] = id; c->nkept++; }
        e->tmpcount++;
    }
}

/* SimHash hyperplane signs for a kept word: two crc32s per 64-bit half,
 * salted by the half index (mirrors atn-ga.py's _word_bits). */
static void word_signs(const unsigned char *w, size_t wlen, uint64_t *s0, uint64_t *s1) {
    unsigned char p0 = 0x00, p1 = 0x01, mid = 0x01;
    uint32_t a0 = crc32_update(crc32_update(0, &p0, 1), w, wlen);
    uint32_t b0 = crc32_update(crc32_update(crc32_update(0, &p0, 1), &mid, 1), w, wlen);
    uint32_t a1 = crc32_update(crc32_update(0, &p1, 1), w, wlen);
    uint32_t b1 = crc32_update(crc32_update(crc32_update(0, &p1, 1), &mid, 1), w, wlen);
    *s0 = (uint64_t)a0 | ((uint64_t)b0 << 32);
    *s1 = (uint64_t)a1 | ((uint64_t)b1 << 32);
}

/* ---- similarity = number of matching signature slots ------------------- */
static int mh_match(const uint64_t *mh, size_t i, size_t j) {
    const uint64_t *a = mh + i * NH, *b = mh + j * NH;
    int m = 0;
    for (int s = 0; s < NH; s++) m += (a[s] == b[s]);
    return m;
}
static int sh_match(const unsigned char *sh, size_t i, size_t j) {
    const unsigned char *a = sh + i * SIG_BITS, *b = sh + j * SIG_BITS;
    int m = 0;
    for (int k = 0; k < SIG_BITS; k++) m += (a[k] == b[k]);
    return m;
}

/* ---- ranking helpers --------------------------------------------------- */
static const int *g_score;   /* match counts, for qsort (single-threaded) */
static int cmp_cand(const void *pa, const void *pb) {
    int a = *(const int *)pa, b = *(const int *)pb;
    if (g_score[a] != g_score[b]) return g_score[b] - g_score[a];  /* sim desc */
    return a - b;                                                   /* id asc  */
}

/* one (band-keyed bucket, chunk) entry, sorted to form LSH buckets */
typedef struct { uint64_t key; int32_t chunk; } BandEntry;
static int cmp_band(const void *pa, const void *pb) {
    const BandEntry *a = pa, *b = pb;
    return a->key < b->key ? -1 : a->key > b->key ? 1 : a->chunk - b->chunk;
}

int content_build_neighbors(const char *territory, const char *index,
                            const char *outpath, const char *sigkind, double df_max) {
    crc_init();
    int simhash = sigkind && strcmp(sigkind, "simhash") == 0;

    /* slurp the territory */
    FILE *tf = fopen(territory, "rb");
    if (!tf) { fprintf(stderr, "atn: %s: cannot open\n", territory); return 1; }
    fseek(tf, 0, SEEK_END); long tsz = ftell(tf); fseek(tf, 0, SEEK_SET);
    unsigned char *terr = malloc(tsz > 0 ? (size_t)tsz : 1);
    if (fread(terr, 1, (size_t)tsz, tf) != (size_t)tsz) { fprintf(stderr, "atn: read failed\n"); fclose(tf); return 1; }
    fclose(tf);

    /* read the chunk index: cid <tab> off <tab> len */
    FILE *xf = fopen(index, "r");
    if (!xf) { fprintf(stderr, "atn: %s: cannot open\n", index); free(terr); return 1; }
    size_t cap = 1024, n = 0;
    long *off = malloc(cap * sizeof(long)), *clen = malloc(cap * sizeof(long));
    long cid, o, l;
    while (fscanf(xf, "%ld\t%ld\t%ld\n", &cid, &o, &l) == 3) {
        if (n == cap) { cap <<= 1; off = realloc(off, cap * sizeof(long)); clen = realloc(clen, cap * sizeof(long)); }
        off[n] = o; clen[n] = l; n++;
    }
    fclose(xf);
    if (n == 0) { fprintf(stderr, "atn: empty index\n"); free(terr); free(off); free(clen); return 1; }

    /* pass 1: document frequencies */
    VMap V; vmap_init(&V, 1 << 16);
    DfCtx dc = { &V, 0 };
    for (size_t i = 0; i < n; i++) {
        dc.chunk = (int32_t)i;
        tokenize(terr + off[i], (size_t)clen[i], df_cb, &dc);
    }

    /* df filter + per-word idf/signs for kept words */
    double hi = df_max < 1.0 ? df_max * (double)n : (double)n + 1.0;
    int32_t nkept = 0;
    for (size_t i = 0; i < V.count; i++) {
        Vocab *e = &V.e[i];
        if (e->df >= MIN_DF && (double)e->df <= hi) e->vid = nkept++;
    }
    (void)nkept;
    /* idf needs only n & df (computed on the fly in pass 2); precompute the
       SimHash hyperplane signs once for each kept word. */
    if (simhash)
        for (size_t i = 0; i < V.count; i++)
            if (V.e[i].vid >= 0)
                word_signs((const unsigned char *)V.e[i].word, V.e[i].wlen, &V.e[i].sign0, &V.e[i].sign1);

    /* signature storage */
    int width = simhash ? SIG_BITS : NH;     /* "slots" compared for similarity */
    uint64_t *mh = NULL; unsigned char *sh = NULL;
    uint64_t mult[NH];
    if (simhash) {
        sh = calloc(n * SIG_BITS, 1);
    } else {
        mh = malloc(n * NH * sizeof(uint64_t));
        for (size_t i = 0; i < n * NH; i++) mh[i] = UINT64_MAX;
        for (int i = 0; i < NH; i++) mult[i] = 0x9E3779B97F4A7C15ULL * (uint64_t)(2 * i + 1);
    }

    /* pass 2: build each chunk's signature (re-tokenise) */
    /* reusable per-chunk scratch for SimHash accumulation */
    double *acc = simhash ? malloc(SIG_BITS * sizeof(double)) : NULL;
    int32_t *touched = malloc(V.count * sizeof(int32_t));   /* worst case */
    for (size_t i = 0; i < n; i++) {
        /* gather this chunk's df-filtered words + term frequencies */
        SigCtx sc = { &V, touched, 0, 0 };
        tokenize(terr + off[i], (size_t)clen[i], sig_cb, &sc);
        size_t ntouch = sc.ntouch, nkept_words = sc.nkept;

        if (simhash) {
            for (int k = 0; k < SIG_BITS; k++) acc[k] = 0.0;
            for (size_t t = 0; t < ntouch; t++) {
                Vocab *e = &V.e[touched[t]];
                double idf = log((double)n / (double)e->df);
                double wt = (1.0 + log((double)e->tmpcount)) * idf;
                for (int k = 0; k < SIG_BITS; k++) {
                    uint64_t col = (k < 64) ? e->sign0 : e->sign1;
                    int bit = (int)((col >> (k & 63)) & 1);
                    acc[k] += wt * (2 * bit - 1);
                }
            }
            unsigned char *row = sh + i * SIG_BITS;
            for (int k = 0; k < SIG_BITS; k++) row[k] = acc[k] > 0.0 ? 1 : 0;
        } else if (nkept_words >= 4) {                   /* MinHash needs >=4 words */
            uint64_t *row = mh + i * NH;
            for (size_t t = 0; t < ntouch; t++) {
                uint64_t h = V.e[touched[t]].crc;        /* crc32 as the base hash */
                for (int s = 0; s < NH; s++) {
                    uint64_t m = h * mult[s];
                    m ^= m >> 29;
                    if (m < row[s]) row[s] = m;
                }
            }
        }
        for (size_t t = 0; t < ntouch; t++) V.e[touched[t]].tmpcount = 0;  /* reset */
    }

    /* ---- build the neighbour table ---- */
    int exact = (n <= LSH_THRESHOLD);
    int rowcap = exact ? (int)n : (LSH_CAP + 1);
    int32_t *table = malloc(n * (size_t)rowcap * sizeof(int32_t));
    int *score = malloc(n * sizeof(int));            /* match count vs the query i */
    g_score = score;

    if (exact) {
        int *order = malloc(n * sizeof(int));
        for (size_t i = 0; i < n; i++) {
            for (size_t j = 0; j < n; j++)
                score[j] = simhash ? sh_match(sh, i, j) : mh_match(mh, i, j);
            for (size_t j = 0; j < n; j++) order[j] = (int)j;
            qsort(order, n, sizeof(int), cmp_cand);
            /* keep only chunks that share SOME vocabulary (match > 0): a gather
             * must never spill into unrelated chunks just to fill a large span. */
            int32_t *row = table + i * (size_t)rowcap;
            int k = 0;
            for (size_t j = 0; j < n; j++)
                if (score[order[j]] > 0) row[k++] = order[j];
            while (k < rowcap) row[k++] = -1;
        }
        free(order);
    } else {
        /* banded LSH: group chunks sharing a band's slots, gather co-members
         * as candidates, then rank candidates by full-signature similarity. */
        int R = width / LSH_BANDS; if (R < 1) R = 1;
        /* one (band-key, chunk) entry per (chunk, band); sorted -> buckets. */
        size_t ne = n * (size_t)LSH_BANDS;
        BandEntry *ent = malloc(ne * sizeof(*ent));
        size_t ei = 0;
        for (size_t i = 0; i < n; i++)
            for (int b = 0; b < LSH_BANDS; b++) {
                uint64_t k = 1469598103934665603ULL ^ ((uint64_t)b + 1);  /* FNV-ish seed */
                for (int r = 0; r < R; r++) {
                    uint64_t slot = simhash ? (uint64_t)sh[i * SIG_BITS + b * R + r]
                                            : mh[i * NH + b * R + r];
                    k = (k ^ slot) * 1099511628211ULL;
                }
                ent[ei].key = k; ent[ei].chunk = (int32_t)i; ei++;
            }
        qsort(ent, ne, sizeof(*ent), cmp_band);

        int32_t *visited = malloc(n * sizeof(int32_t));
        for (size_t i = 0; i < n; i++) visited[i] = -1;
        int *cand = malloc(n * sizeof(int));         /* candidate scratch (capped) */
        const int MAXC = 4000;

        /* For each chunk, recompute its band keys and binary-search the sorted
         * entries to collect co-bucket members, then rank by full similarity. */
        for (size_t i = 0; i < n; i++) {
            int nc = 0;
            visited[i] = (int32_t)i;                 /* exclude self from candidates */
            for (int b = 0; b < LSH_BANDS && nc < MAXC; b++) {
                uint64_t k = 1469598103934665603ULL ^ ((uint64_t)b + 1);
                for (int r = 0; r < R; r++) {
                    uint64_t slot = simhash ? (uint64_t)sh[i * SIG_BITS + b * R + r]
                                            : mh[i * NH + b * R + r];
                    k = (k ^ slot) * 1099511628211ULL;
                }
                /* binary search the first entry with this key */
                size_t lo = 0, hiB = ne;
                while (lo < hiB) { size_t mid = (lo + hiB) >> 1; if (ent[mid].key < k) lo = mid + 1; else hiB = mid; }
                for (size_t e = lo; e < ne && ent[e].key == k && nc < MAXC; e++) {
                    int32_t m = ent[e].chunk;
                    if (visited[m] != (int32_t)i) { visited[m] = (int32_t)i; cand[nc++] = m; }
                }
            }
            for (int c = 0; c < nc; c++) score[cand[c]] = simhash ? sh_match(sh, i, cand[c]) : mh_match(mh, i, cand[c]);
            qsort(cand, nc, sizeof(int), cmp_cand);
            int32_t *row = table + i * (size_t)rowcap;
            row[0] = (int32_t)i;                     /* seed first (matches Python) */
            int k = 1;                               /* keep only positive-similarity neighbours */
            for (int c = 0; c < nc && k <= LSH_CAP; c++)
                if (score[cand[c]] > 0) row[k++] = cand[c];
            while (k <= LSH_CAP) row[k++] = -1;
        }
        free(ent); free(visited); free(cand);
    }

    /* write neighbors.bin */
    FILE *of = fopen(outpath, "wb");
    if (!of) { fprintf(stderr, "atn: %s: cannot write\n", outpath); return 1; }
    int32_t hdr[2] = { (int32_t)n, rowcap };
    fwrite(hdr, sizeof(int32_t), 2, of);
    fwrite(table, sizeof(int32_t), n * (size_t)rowcap, of);
    fclose(of);

    fprintf(stderr, "atn: neighbors %s over %zu chunks (%s, %s)\n",
            sigkind ? sigkind : "minhash", n, exact ? "exact" : "LSH",
            outpath);

    free(terr); free(off); free(clen); free(table); free(score);
    free(mh); free(sh); free(acc); free(touched);
    for (size_t i = 0; i < V.count; i++) free(V.e[i].word);
    free(V.e); free(V.slot);
    return 0;
}
