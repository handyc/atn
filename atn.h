/*
 * atn — look very closely at files.
 *
 * Shared declarations. Each analysis module prints its own section; main.c
 * orchestrates which run based on the parsed options.
 */
#ifndef ATN_H
#define ATN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>

#define ATN_VERSION "2.0.0"

/* A whole file slurped into memory. */
typedef struct {
    unsigned char *data;
    size_t len;
} blob;

/* Which sections to print, plus their tunables. */
typedef struct {
    bool basic;       /* metadata + type (default on)            */
    bool stats;       /* -S deep statistical metrics             */
    bool emap;        /* -E windowed entropy map                 */
    bool similar;     /* -C self-similarity / periodicity        */
    bool structure;   /* -T type-specific structural breakdown   */
    bool patterns;    /* -P opcode / routine pattern scan        */
    bool malware;     /* -M signature scan (EICAR, packers, ...) */
    bool anomalies;   /* -K anomaly / error checks               */
    bool embedded;    /* -F carve embedded file signatures       */
    bool disasm;      /* -D linear disassembly                   */
    bool attn;        /* -Z hand-wired attention head            */
    bool compress;    /* -X model-driven compression round-trip  */
    bool feedback;    /* -B predictive feedback / context mixing */
    bool hex;         /* -x hex dump                             */
    bool strings;     /* -s string extraction                    */
    bool quiet;       /* -q suppress section headers/basic       */
    bool recursive;   /* -R aggregate scan of a directory tree   */
    bool corpus;      /* --corpus treat a tree as a GPT corpus   */
    bool verbose;     /* -v per-file line in recursive mode      */

    long   hex_limit; /* -n bytes shown by hex dump (0 = all)    */
    size_t min_str;   /* -m minimum string length                */
    size_t window;    /* -w window size for -E / -C              */
    int    bits;      /* --bits 32|64 for -D (0 = auto-detect)   */
    double temp;      /* --temp generation temperature           */
    int    gen;       /* --gen number of bytes to generate       */
    const char *grep; /* -g custom hex/ascii pattern             */
    const char *sigfile; /* --sigs extra signature file          */
    const char *yarafile; /* --yara rule file                    */
} options;

/* Recursively scan a directory tree, run metrics on every file, and print
 * an aggregate report. Returns 0 on success. */
int scan_tree(const char *root, const options *o);

/* True if any per-file analysis section (not just the aggregate) is requested. */
bool options_any_section(const options *o);

/* Run all requested per-file sections on an in-memory blob. */
void run_sections(const char *label, const struct stat *st,
                  const blob *b, const options *o);

/* Slurp an open stream fully into a blob (grows as needed). */
bool read_stream(FILE *fp, blob *out);

/* ---- byte-frequency table shared by several modules ---- */
typedef struct {
    uint64_t freq[256];
    uint64_t total;
} histogram;

void   hist_build(const blob *b, histogram *h);
double hist_entropy(const histogram *h); /* Shannon bits/byte 0..8 */

/* ---- modules (each prints a section) ---- */
void report_basic(const char *label, const struct stat *st, const blob *b);
const char *guess_type(const blob *b, const char **mime);

void stats_report(const blob *b);
void entropy_map(const blob *b, size_t window);
void similarity_report(const blob *b, size_t window);
void structure_report(const blob *b);
void pattern_scan(const blob *b);
void malware_scan(const blob *b, const char *sigfile);
void anomaly_scan(const char *label, const blob *b);
void embedded_scan(const blob *b);
void hex_dump(const blob *b, long limit);
void extract_strings(const blob *b, size_t minlen);
void grep_pattern(const blob *b, const char *pat);
void yara_scan(const blob *b, const char *rulefile);
void attention_report(const blob *b, size_t window, double temp, int gen);
void lm_report(const blob *b, double temp, int gen);
void compress_report(const blob *b);
void feedback_report(const blob *b);
int  lm_compress_file(const blob *b, const char *outpath);
int  lm_decompress_file(const blob *in, const char *outpath);

/* minimal learning chat (gpt.c): learns from what you type, persists a brain */
void chat_session(const char *brainpath, double temp);
/* one-shot: one line of stdin -> one line of reply, then exit (cron-friendly) */
void chat_once(const char *brainpath, double temp, bool learn);
/* score: per stdin line, print surprisal (bits/byte) under the brain + the line */
void score_query(const char *brainpath);
/* tune the per-map entry cap to 1<<bits (more = higher fidelity, more RAM) */
void lm_set_map_cap(int bits);
/* autotrain (gpt.c): ingest every text file under a directory into the brain */
void autotrain(const char *dir, const char *brainpath, bool strip_html);

/* context-mixing coder (cm.c) */
void cm_report(const blob *b);
int  cm_compress_file(const blob *b, const char *outpath);
int  cm_decompress_file(const blob *in, const char *outpath);
int  cm_is_stream(const blob *in);

/* Model API for the filesystem-corpus mode. */
void  *lm_build(const blob *corpus);
double lm_score_bpb(void *model, const blob *b);
void   lm_sample(void *model, const blob *seed, double temp, int gen);
void   lm_free_model(void *model);

/* Scan a tree as a text corpus: build one model, score every file's surprisal,
 * flag outliers, and generate in the directory's style. */
int scan_corpus(const char *root, const options *o);

/* ---- small shared helpers (util.c) ---- */
void section(const char *title);                 /* "== title ==" header */
void human_size(uint64_t n, char *out, size_t outlen);
void sparkline(const double *vals, size_t n, char *out, size_t outlen);
/* Boyer-Moore-ish memmem; returns pointer or NULL. */
const unsigned char *find_bytes(const unsigned char *hay, size_t haylen,
                                const unsigned char *needle, size_t nlen,
                                size_t from);
/* Parse "CD21", "cd 21", "\xCD\x21", or fall back to literal ASCII.
 * Writes up to *outlen bytes, updates *outlen. Returns true on success. */
bool parse_pattern(const char *spec, unsigned char *out, size_t *outlen);

#endif /* ATN_H */
