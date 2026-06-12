/* fleet.c — recursive directory/filesystem scan with aggregate statistics. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define FLEET_READ_CAP (16u * 1024 * 1024)  /* bytes read per file for metrics */
#define TOPN 8

typedef struct { char *name; uint64_t count; } typecount;
typedef struct { char *path; double key; } topentry;

typedef struct {
    uint64_t files, dirs, errors, unreadable;
    uint64_t total_bytes;          /* true sizes from stat                 */
    uint64_t text, binary, empty;
    uint64_t high_entropy;         /* entropy > 7.5                        */
    double   entropy_sum; uint64_t entropy_n;
    uint64_t anomaly_files, sig_files, embedded_files;
    uint64_t ent_bucket[8];        /* 0-1,1-2,...,7-8 bits                 */

    typecount *types; size_t ntypes, captypes;
    topentry big[TOPN];   int nbig;
    topentry ent[TOPN];   int nent;
    /* a few notable findings to print verbatim */
    char *sig_examples[TOPN]; int nsig;
} agg;

/* ---- helpers ---- */
static void bump_type(agg *a, const char *name) {
    for (size_t i = 0; i < a->ntypes; i++)
        if (strcmp(a->types[i].name, name) == 0) { a->types[i].count++; return; }
    if (a->ntypes == a->captypes) {
        a->captypes = a->captypes ? a->captypes*2 : 32;
        a->types = realloc(a->types, a->captypes*sizeof(typecount));
    }
    a->types[a->ntypes].name = strdup(name);
    a->types[a->ntypes].count = 1;
    a->ntypes++;
}

/* keep a descending top-N by key */
static void top_offer(topentry *arr, int *n, const char *path, double key) {
    if (*n < TOPN) {
        arr[*n].path = strdup(path); arr[*n].key = key; (*n)++;
    } else {
        int worst = 0; for (int i = 1; i < *n; i++) if (arr[i].key < arr[worst].key) worst = i;
        if (key > arr[worst].key) { free(arr[worst].path); arr[worst].path = strdup(path); arr[worst].key = key; }
        else return;
    }
    /* simple insertion sort to keep descending */
    for (int i = 1; i < *n; i++) {
        topentry t = arr[i]; int j = i-1;
        while (j >= 0 && arr[j].key < t.key) { arr[j+1] = arr[j]; j--; }
        arr[j+1] = t;
    }
}

static int type_cmp(const void *x, const void *y) {
    const typecount *a = x, *b = y;
    if (a->count < b->count) return 1;
    if (a->count > b->count) return -1;
    return 0;
}

/* ---- per-file metric computation ---- */
static void analyze_file(const char *path, uint64_t true_size, agg *a,
                         const struct stat *st, const options *o) {
    bool sections = options_any_section(o);
    bool verbose = o->verbose;

    FILE *f = fopen(path, "rb");
    if (!f) { a->unreadable++; return; }

    unsigned char *buf; size_t got;
    if (sections) {
        /* Need the whole file to run real per-file sections. */
        blob whole;
        if (!read_stream(f, &whole)) { fclose(f); a->unreadable++; return; }
        fclose(f);
        buf = whole.data; got = whole.len;
    } else {
        buf = malloc(FLEET_READ_CAP);
        if (!buf) { fclose(f); a->unreadable++; return; }
        got = fread(buf, 1, FLEET_READ_CAP, f);
        fclose(f);
    }

    a->files++;
    a->total_bytes += true_size;
    blob b = { buf, got };

    /* Per-file detail: print the requested sections under a divider. */
    if (sections) {
        printf("\n\033[2m%s\033[0m\n", "────────────────────────────────────────");
        run_sections(path, st, &b, o);
    }

    if (got == 0) { a->empty++; bump_type(a, "(empty)"); free(buf);
        if (verbose && !sections) printf("  %10" PRIu64 "  ent —     (empty)              %s\n", true_size, path);
        top_offer(a->big, &a->nbig, path, (double)true_size); return; }

    /* type */
    const char *mime = NULL;
    const char *type = guess_type(&b, &mime);

    /* entropy + text/binary */
    histogram h; hist_build(&b, &h);
    double H = hist_entropy(&h);
    a->entropy_sum += H; a->entropy_n++;
    int bucket = (int)H; if (bucket > 7) bucket = 7; if (bucket < 0) bucket = 0;
    a->ent_bucket[bucket]++;
    if (H > 7.5) a->high_entropy++;

    uint64_t print = 0, nul = h.freq[0];
    for (int i = 0; i < 256; i++)
        if (isprint(i)||i=='\t'||i=='\n'||i=='\r') print += h.freq[i];
    bool text = nul == 0 && (double)print/(double)got >= 0.95;
    if (text) a->text++; else a->binary++;
    if (!type) type = text ? "text / ASCII" : "data (unrecognized)";
    bump_type(a, type);

    /* quick anomaly: trailing data after PNG IEND / missing JPEG EOI / no ZIP EOCD */
    bool anomaly = false;
    if (got >= 8 && memcmp(buf, "\x89PNG\r\n\x1a\n", 8) == 0) {
        static const unsigned char iend[4] = {'I','E','N','D'};
        const unsigned char *p = find_bytes(buf, got, iend, 4, 0);
        if (!p) anomaly = true;
        else if ((size_t)(p - buf) + 8 < got) anomaly = true;
    } else if (got >= 3 && memcmp(buf, "\xff\xd8\xff", 3) == 0) {
        if (true_size <= got && !(got>=2 && buf[got-2]==0xff && buf[got-1]==0xd9)) anomaly = true;
    }
    if (anomaly) a->anomaly_files++;

    /* signatures: EICAR + a couple of packer markers */
    static const char *eicar = "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!";
    bool sig = false; const char *what = NULL;
    if (find_bytes(buf, got, (const unsigned char*)eicar, strlen(eicar), 0)) { sig=true; what="EICAR"; }
    else if (find_bytes(buf, got, (const unsigned char*)"UPX!", 4, 0)) { sig=true; what="UPX-packed"; }
    if (sig) {
        a->sig_files++;
        if (a->nsig < TOPN) {
            char line[1100]; snprintf(line, sizeof(line), "%-12s %s", what, path);
            a->sig_examples[a->nsig++] = strdup(line);
        }
    }

    /* embedded signature past header (cheap: look for a few magics at offset>0) */
    static const unsigned char png[]={0x89,'P','N','G'}, pk[]={'P','K',3,4}, gz[]={0x1f,0x8b};
    bool emb = find_bytes(buf, got, png, 4, 1) || find_bytes(buf, got, pk, 4, 1) ||
               (got > 64 && find_bytes(buf, got, gz, 2, 64));
    if (emb) a->embedded_files++;

    if (verbose && !sections)
        printf("  %10" PRIu64 "  ent %.2f  %-28.28s %s\n", true_size, H, type, path);

    top_offer(a->big, &a->nbig, path, (double)true_size);
    top_offer(a->ent, &a->nent, path, H);

    free(buf);
}

/* ---- recursive walk (no symlink following; skips pseudo-filesystems) ---- */
static bool skip_dir(const char *path) {
    /* avoid pseudo / virtual filesystems when scanning from root */
    return strcmp(path,"/proc")==0 || strcmp(path,"/sys")==0 ||
           strcmp(path,"/dev")==0  || strcmp(path,"/run")==0;
}

static void walk(const char *path, agg *a, int depth, const options *o) {
    DIR *d = opendir(path);
    if (!d) { a->errors++; return; }
    a->dirs++;
    struct dirent *de;
    char child[4096];
    while ((de = readdir(d))) {
        if (strcmp(de->d_name, ".") == 0 || strcmp(de->d_name, "..") == 0) continue;
        int nw = snprintf(child, sizeof(child), "%s/%s",
                          strcmp(path,"/")==0 ? "" : path, de->d_name);
        if (nw <= 0 || (size_t)nw >= sizeof(child)) continue;

        struct stat st;
        if (lstat(child, &st) != 0) { a->errors++; continue; }
        if (S_ISLNK(st.st_mode)) continue;              /* never follow symlinks */
        if (S_ISDIR(st.st_mode)) {
            if (!skip_dir(child) && depth < 64) walk(child, a, depth + 1, o);
        } else if (S_ISREG(st.st_mode)) {
            analyze_file(child, (uint64_t)st.st_size, a, &st, o);
        }
    }
    closedir(d);
}

/* ================================================================ */
/* Filesystem-as-corpus: build ONE byte-model over the whole tree,   */
/* then measure each file's surprisal under it. Files that fit the   */
/* corpus score low bits/byte; alien files (encrypted, wrong type,   */
/* foreign language) score high — a content-grounded outlier finder. */
/* This is "attention to the files in the filesystem" meeting the    */
/* GPT model: the corpus is the context, each file a continuation.   */
/* ================================================================ */

#define CORPUS_CAP   (4u << 20)   /* total bytes per half fed to a model */
#define CORPUS_PREF  (8u << 10)   /* bytes kept per file             */
#define CORPUS_FILES 6000         /* max files tracked               */

typedef struct { char *path; unsigned char *data; size_t len; double bpb; int half; } cfile;
typedef struct {
    unsigned char *corp[2]; size_t clen[2], ccap[2];   /* two folds */
    cfile *f; size_t nf; size_t cap;
    uint64_t seen, skipped;
} corpus_acc;

static void corpus_take(corpus_acc *c, const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) { c->skipped++; return; }
    unsigned char *buf = malloc(CORPUS_PREF);
    if (!buf) { fclose(fp); c->skipped++; return; }
    size_t got = fread(buf, 1, CORPUS_PREF, fp);
    fclose(fp);
    c->seen++;
    if (got == 0) { free(buf); return; }

    int h = (int)(c->nf & 1);            /* alternate folds */
    if (c->clen[h] < CORPUS_CAP) {
        size_t room = CORPUS_CAP - c->clen[h], take = got < room ? got : room;
        if (c->clen[h] + take > c->ccap[h]) {
            while (c->ccap[h] < c->clen[h] + take) c->ccap[h] = c->ccap[h] ? c->ccap[h]*2 : (1u<<20);
            c->corp[h] = realloc(c->corp[h], c->ccap[h]);
        }
        memcpy(c->corp[h] + c->clen[h], buf, take); c->clen[h] += take;
    }
    if (c->nf < CORPUS_FILES) {
        if (c->nf == c->cap) { c->cap = c->cap ? c->cap*2 : 256; c->f = realloc(c->f, c->cap*sizeof(cfile)); }
        c->f[c->nf].path = strdup(path);
        c->f[c->nf].data = buf;
        c->f[c->nf].len = got;
        c->f[c->nf].bpb = 0;
        c->f[c->nf].half = h;
        c->nf++;
    } else free(buf);
}

static void corpus_walk(const char *path, corpus_acc *c, int depth) {
    DIR *d = opendir(path); if (!d) return;
    struct dirent *de; char child[4096];
    while ((de = readdir(d))) {
        if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, "..")) continue;
        int nw = snprintf(child, sizeof(child), "%s/%s", strcmp(path,"/")==0?"":path, de->d_name);
        if (nw <= 0 || (size_t)nw >= sizeof(child)) continue;
        struct stat st;
        if (lstat(child, &st) != 0) continue;
        if (S_ISLNK(st.st_mode)) continue;
        if (S_ISDIR(st.st_mode)) { if (!skip_dir(child) && depth < 64) corpus_walk(child, c, depth+1); }
        else if (S_ISREG(st.st_mode) && c->nf < CORPUS_FILES) corpus_take(c, child);
    }
    closedir(d);
}

static int cfile_cmp(const void *x, const void *y) {
    double a = ((const cfile*)x)->bpb, b = ((const cfile*)y)->bpb;
    return a < b ? -1 : a > b ? 1 : 0;
}

int scan_corpus(const char *root, const options *o) {
    corpus_acc c; memset(&c, 0, sizeof(c));
    fprintf(stderr, "atn: building corpus model from %s ...\n", root);

    struct stat st;
    if (stat(root, &st) != 0) { fprintf(stderr, "atn: %s: %s\n", root, strerror(errno)); return 1; }
    if (S_ISDIR(st.st_mode)) corpus_walk(root, &c, 0);
    else corpus_take(&c, root);

    if (c.clen[0] + c.clen[1] < 64 || c.nf == 0) {
        printf("\n== corpus: %s ==\n  (not enough data)\n", root);
        for (size_t i=0;i<c.nf;i++){free(c.f[i].path);free(c.f[i].data);}
        free(c.f); free(c.corp[0]); free(c.corp[1]); return 1; }

    /* Two folds: score each file with the model built from the OTHER fold,
     * so a file is never scored by a model that memorised it. */
    blob cb0 = { c.corp[0], c.clen[0] }, cb1 = { c.corp[1], c.clen[1] };
    void *MA = lm_build(&cb0);     /* fold 0 */
    void *MB = lm_build(&cb1);     /* fold 1 */

    double sum = 0; size_t scored = 0;
    for (size_t i = 0; i < c.nf; i++) {
        blob fb = { c.f[i].data, c.f[i].len };
        c.f[i].bpb = lm_score_bpb(c.f[i].half ? MA : MB, &fb);  /* held out */
        sum += c.f[i].bpb; scored++;
    }

    char sz[64]; human_size(c.clen[0] + c.clen[1], sz, sizeof(sz));
    printf("\n\033[1m== filesystem as GPT corpus: %s ==\033[0m\n", root);
    printf("  corpus      %s from %zu files (%" PRIu64 " seen, %" PRIu64 " unreadable)\n",
           sz, c.nf, c.seen, c.skipped);
    printf("  model       unlearned n-gram (orders 3+6, backoff), 2-fold held-out\n");
    printf("  mean held-out surprisal  %.3f bits/byte\n", scored ? sum/(double)scored : 0);

    qsort(c.f, c.nf, sizeof(cfile), cfile_cmp);
    printf("  most typical (lowest surprisal — most like the rest of the tree):\n");
    for (size_t i = 0; i < c.nf && i < 6; i++)
        printf("    %6.2f bpb  %s\n", c.f[i].bpb, c.f[i].path);
    printf("  most surprising (highest surprisal — the outliers):\n");
    for (size_t i = 0; i < 6 && i < c.nf; i++) {
        size_t idx = c.nf - 1 - i;
        printf("    %6.2f bpb  %s\n", c.f[idx].bpb, c.f[idx].path);
    }

    printf("  generation in the style of this directory:\n");
    lm_sample(MA, &cb0, o->temp > 0 ? o->temp : 0.7, o->gen > 0 ? o->gen : 200);

    lm_free_model(MA); lm_free_model(MB);
    for (size_t i = 0; i < c.nf; i++) { free(c.f[i].path); free(c.f[i].data); }
    free(c.f); free(c.corp[0]); free(c.corp[1]);
    return 0;
}

int scan_tree(const char *root, const options *o) {
    struct stat st;
    if (stat(root, &st) != 0) {
        fprintf(stderr, "atn: %s: %s\n", root, strerror(errno));
        return 1;
    }

    agg a; memset(&a, 0, sizeof(a));
    bool sections = options_any_section(o);

    fprintf(stderr, "atn: scanning %s ...\n", root);
    if (o->verbose && !sections)
        printf("        size  entropy  type                         path\n");
    if (S_ISDIR(st.st_mode)) walk(root, &a, 0, o);
    else analyze_file(root, (uint64_t)st.st_size, &a, &st, o);

    /* ---- report ---- */
    char sz[64]; human_size(a.total_bytes, sz, sizeof(sz));
    printf("\n\033[1m== filesystem scan: %s ==\033[0m\n", root);
    printf("  files       %" PRIu64 "   (%" PRIu64 " dirs, %" PRIu64
           " unreadable, %" PRIu64 " walk errors)\n",
           a.files, a.dirs, a.unreadable, a.errors);
    printf("  total size  %s\n", sz);
    printf("  composition %" PRIu64 " text, %" PRIu64 " binary, %" PRIu64 " empty\n",
           a.text, a.binary, a.empty);
    if (a.entropy_n)
        printf("  mean entropy %.3f bits/byte\n", a.entropy_sum / (double)a.entropy_n);
    printf("  high-entropy %" PRIu64 " files >7.5 bits (compressed/encrypted/packed)\n",
           a.high_entropy);

    printf("  entropy distribution:\n");
    uint64_t emax = 1; for (int i = 0; i < 8; i++) if (a.ent_bucket[i] > emax) emax = a.ent_bucket[i];
    for (int i = 0; i < 8; i++) {
        int bar = (int)(40.0 * (double)a.ent_bucket[i] / (double)emax + 0.5);
        printf("    %d-%d bits  %6" PRIu64 "  ", i, i+1, a.ent_bucket[i]);
        for (int k = 0; k < bar; k++) putchar('#');
        putchar('\n');
    }

    if (a.ntypes) {
        qsort(a.types, a.ntypes, sizeof(typecount), type_cmp);
        printf("  top types:\n");
        for (size_t i = 0; i < a.ntypes && i < 12; i++)
            printf("    %6" PRIu64 "  %s\n", a.types[i].count, a.types[i].name);
    }

    printf("  flagged:\n");
    printf("    anomalies (truncation/trailing): %" PRIu64 " files\n", a.anomaly_files);
    printf("    embedded signatures:             %" PRIu64 " files\n", a.embedded_files);
    printf("    known signatures (EICAR/packer): %" PRIu64 " files\n", a.sig_files);
    for (int i = 0; i < a.nsig; i++) printf("        %s\n", a.sig_examples[i]);

    if (a.nbig) {
        printf("  largest files:\n");
        for (int i = 0; i < a.nbig; i++) {
            char s[64]; human_size((uint64_t)a.big[i].key, s, sizeof(s));
            printf("    %-22s %s\n", s, a.big[i].path);
        }
    }
    if (a.nent) {
        printf("  highest entropy:\n");
        for (int i = 0; i < a.nent; i++)
            printf("    %.4f  %s\n", a.ent[i].key, a.ent[i].path);
    }

    /* cleanup */
    for (size_t i = 0; i < a.ntypes; i++) free(a.types[i].name);
    free(a.types);
    for (int i = 0; i < a.nbig; i++) free(a.big[i].path);
    for (int i = 0; i < a.nent; i++) free(a.ent[i].path);
    for (int i = 0; i < a.nsig; i++) free(a.sig_examples[i]);
    return 0;
}
