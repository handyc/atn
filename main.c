/* main.c — CLI parsing and orchestration. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"
#include "disasm.h"

#include <errno.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

bool options_any_section(const options *o) {
    return o->stats || o->emap || o->similar || o->structure || o->embedded ||
           o->patterns || o->disasm || o->attn || o->compress || o->feedback ||
           o->malware || o->yarafile || o->anomalies || o->grep || o->hex || o->strings;
}

void run_sections(const char *label, const struct stat *st,
                  const blob *b, const options *o) {
    if (o->basic && !o->quiet) report_basic(label, st, b);
    if (o->stats)     stats_report(b);
    if (o->emap)      entropy_map(b, o->window);
    if (o->similar)   similarity_report(b, o->window);
    if (o->attn)      attention_report(b, o->window, o->temp, o->gen);
    if (o->feedback)  feedback_report(b);
    if (o->compress)  cm_report(b);
    if (o->structure) structure_report(b);
    if (o->embedded)  embedded_scan(b);
    if (o->patterns)  pattern_scan(b);
    if (o->disasm)    disasm_report(b, o->bits ? o->bits : detect_bits(b));
    if (o->malware)   malware_scan(b, o->sigfile);
    if (o->yarafile)  yara_scan(b, o->yarafile);
    if (o->anomalies) anomaly_scan(label, b);
    if (o->grep)      grep_pattern(b, o->grep);
    if (o->hex)       hex_dump(b, o->hex_limit);
    if (o->strings)   extract_strings(b, o->min_str);
}

static void usage(FILE *o) {
    fprintf(o,
"atn " ATN_VERSION " — look very closely at files\n\n"
"Usage: atn [sections] [tunables] FILE...   ('-' = stdin)\n\n"
"Sections (default: basic report only):\n"
"  -A    everything below\n"
"  -S    deep statistics (entropy, chi-square, serial corr., monte-carlo, noise)\n"
"  -E    windowed entropy map (find compressed/encrypted/embedded regions)\n"
"  -C    self-similarity: periodicity + most-repeated chunks\n"
"  -T    type-specific structure (PNG/JPEG/GIF/BMP/WAV/gzip/ELF/ZIP)\n"
"  -F    carve embedded file signatures at any offset\n"
"  -P    routine/opcode patterns (INT 21h, syscalls, NOP sleds, prologues...)\n"
"  -M    signature scan (EICAR test file, packers; --sigs for more)\n"
"  -K    anomaly & error checks (truncation, trailing data, bad UTF-8...)\n"
"  -D    linear x86/x86-64 disassembly (ELF .text or whole file)\n"
"  -Z    hand-wired attention head: causal self-attention map + induction\n"
"        next-byte predictor (a deterministic, unlearned echo of GPT attention)\n"
"  -B    predictive feedback loop: online context-mixing whose weights are\n"
"        updated by prediction error, plus a model-based surprisal map\n"
"  -X    model-driven arithmetic compression with a lossless round-trip check\n"
"  --compress FILE [-o OUT]    write a real .atnz compressed file\n"
"  --decompress FILE [-o OUT]  restore an .atnz file (stdout if no -o)\n"
"  -c        chat: a minimal terminal chat that learns from what you type\n"
"            (persists a 'brain' next to the atn binary; --brain FILE to override)\n"
"  --train DIR  ingest every text file under DIR into the brain (then -c to chat)\n"
"               (add -q to skip the learnability pass: ~2-3x faster training;\n"
"               UTF-8 text is accepted, including non-Latin scripts e.g. Chinese)\n"
"  --strip-html with --train, strip HTML tags/entities (clean prose corpora)\n"
"  --ask        one-shot: read one line from stdin, print one reply, exit\n"
"               (cron-friendly; --no-learn to query a corpus read-only)\n"
"  --score      per stdin line, print surprisal (bits/byte) under the brain\n"
"               (low = fits the corpus; high = novel/off-topic)\n"
"  --score-bytes per stdin line, print space-separated PER-BYTE surprisal (bits)\n"
"  --orders CSV  context orders for the model, e.g. 2,4,7 (each 1-7, up to 6)\n"
"  --prep [files] clean + dedup (exact + near-dup) + quality-filter text for LLM\n"
"               training; streams to stdout, no model trained (~100s of MB/s)\n"
"  --neighbors TERRITORY --nn-index INDEX.tsv -o OUT.bin\n"
"               build the atn-ga content nearest-neighbour table (MinHash/SimHash\n"
"               signatures + exact/LSH ranking); used by atn-ga.py --locus content\n"
"  --map-bits N  per-map entry cap = 2^N (default 22; higher = more fidelity on\n"
"               big/diverse corpora, more RAM). Use the same N for train+query.\n"
"  -x    hex + ASCII dump\n"
"  -s    extract printable strings\n\n"
"Filesystem scan:\n"
"  -R DIR    recursively scan a directory tree and print aggregate statistics\n"
"            (point it at / for the whole filesystem). Combine with any section\n"
"            flags above to also run those analyses per file, e.g. -R -P -K DIR\n"
"  -v        with -R (and no section flags), print one summary line per file\n"
"  --corpus DIR  build one byte language-model over the whole tree, then rank\n"
"            every file by surprisal under it (outlier finder) + generate\n\n"
"Tunables:\n"
"  -w N      window size for -E/-C (default 256)\n"
"  -n N      bytes shown by hex dump (0 = all, default 256)\n"
"  -m N      minimum string length for -s (default 4)\n"
"  --bits N  force 32 or 64 for -D / -P (default: auto-detect)\n"
"  -g PAT    search for a pattern: 'CD21', 'cd 21', '\\xCD\\x21', or ASCII\n"
"  --sigs F  load extra 'name:hexpattern' signatures for -M\n"
"  --yara F  scan with a (subset) YARA rule file\n"
"  -q        quiet: drop the basic report (keep requested sections)\n"
"  -h, -V    help, version\n");
}

static int inspect(const char *path, const options *o) {
    struct stat st;
    bool is_stdin = strcmp(path, "-") == 0;
    const char *label = is_stdin ? "<stdin>" : path;

    if (!is_stdin) {
        if (stat(path, &st) != 0) {
            fprintf(stderr, "atn: %s: %s\n", path, strerror(errno));
            return 1;
        }
        if (S_ISDIR(st.st_mode)) {
            fprintf(stderr, "atn: %s: is a directory\n", path);
            return 1;
        }
    } else memset(&st, 0, sizeof(st));

    FILE *fp = is_stdin ? stdin : fopen(path, "rb");
    if (!fp) { fprintf(stderr, "atn: %s: %s\n", path, strerror(errno)); return 1; }

    blob b;
    if (!read_stream(fp, &b)) {
        fprintf(stderr, "atn: %s: read failed\n", path);
        if (!is_stdin) fclose(fp);
        return 1;
    }
    if (!is_stdin) fclose(fp);

    run_sections(label, &st, &b, o);

    free(b.data);
    return 0;
}

int main(int argc, char **argv) {
    options o; memset(&o, 0, sizeof(o));
    o.basic = true;
    o.hex_limit = 256; o.min_str = 4; o.window = 256;
    o.temp = 0.7; o.gen = 200;

    static struct option longopts[] = {
        {"sigs", required_argument, 0, 1000},
        {"yara", required_argument, 0, 1001},
        {"bits", required_argument, 0, 1002},
        {"temp", required_argument, 0, 1003},
        {"gen",  required_argument, 0, 1004},
        {"corpus", no_argument,     0, 1005},
        {"compress", no_argument,   0, 1006},
        {"decompress", no_argument, 0, 1007},
        {"brain", required_argument,0, 1008},
        {"train", required_argument,0, 1009},
        {"strip-html", no_argument, 0, 1010},
        {"ask", no_argument,        0, 1011},
        {"no-learn", no_argument,   0, 1012},
        {"score", no_argument,      0, 1013},
        {"map-bits", required_argument, 0, 1014},
        {"score-bytes", no_argument, 0, 1016},
        {"orders", required_argument, 0, 1017},
        {"prep", no_argument,       0, 1015},
        {"neighbors", no_argument,  0, 1018},
        {"nn-index", required_argument, 0, 1019},
        {"nn-sig", required_argument, 0, 1020},
        {"nn-dfmax", required_argument, 0, 1021},
        {"attn", no_argument,       0, 'Z'},
        {"help", no_argument, 0, 'h'},
        {0,0,0,0}
    };

    bool do_compress = false, do_decompress = false, do_chat = false;
    bool do_ask = false, strip_html = false, no_learn = false, do_score = false, do_score_bytes = false;
    bool do_prep = false, do_neighbors = false;
    const char *outfile = NULL, *brainfile = NULL, *traindir = NULL;
    const char *nn_index = NULL, *nn_sig = "minhash";
    double nn_dfmax = 0.5;
    int opt;
    while ((opt = getopt_long(argc, argv, "ASECTFPMKDZBXxsRvcw:n:m:g:o:qhV", longopts, NULL)) != -1) {
        switch (opt) {
            case 'A': o.stats=o.emap=o.similar=o.attn=o.feedback=o.structure=o.embedded=
                      o.patterns=o.disasm=o.malware=o.anomalies=o.hex=o.strings=true; break;
            case 'S': o.stats = true; break;
            case 'E': o.emap = true; break;
            case 'C': o.similar = true; break;
            case 'T': o.structure = true; break;
            case 'F': o.embedded = true; break;
            case 'P': o.patterns = true; break;
            case 'M': o.malware = true; break;
            case 'K': o.anomalies = true; break;
            case 'D': o.disasm = true; break;
            case 'Z': o.attn = true; break;
            case 'B': o.feedback = true; break;
            case 'X': o.compress = true; break;
            case 'x': o.hex = true; break;
            case 's': o.strings = true; break;
            case 'R': o.recursive = true; break;
            case 'v': o.verbose = true; break;
            case 'w': o.window = (size_t)strtoul(optarg, NULL, 10); break;
            case 'n': o.hex_limit = strtol(optarg, NULL, 10); break;
            case 'm': o.min_str = (size_t)strtoul(optarg, NULL, 10); break;
            case 'g': o.grep = optarg; break;
            case 'q': o.quiet = true; break;
            case 1000: o.sigfile = optarg; o.malware = true; break;
            case 1001: o.yarafile = optarg; break;
            case 1002: o.bits = atoi(optarg); break;
            case 1003: o.temp = atof(optarg); break;
            case 1004: o.gen = atoi(optarg); break;
            case 1005: o.corpus = true; break;
            case 1006: do_compress = true; break;
            case 1007: do_decompress = true; break;
            case 1008: brainfile = optarg; break;
            case 1009: traindir = optarg; break;
            case 1010: strip_html = true; break;
            case 1011: do_ask = true; break;
            case 1012: no_learn = true; break;
            case 1013: do_score = true; break;
            case 1014: lm_set_map_cap(atoi(optarg)); break;
            case 1016: do_score_bytes = true; break;
            case 1017: lm_set_orders(optarg); break;
            case 1015: do_prep = true; break;
            case 1018: do_neighbors = true; break;
            case 1019: nn_index = optarg; break;
            case 1020: nn_sig = optarg; break;
            case 1021: nn_dfmax = atof(optarg); break;
            case 'c': do_chat = true; break;
            case 'o': outfile = optarg; break;
            case 'h': usage(stdout); return 0;
            case 'V': printf("atn " ATN_VERSION "\n"); return 0;
            default: usage(stderr); return 2;
        }
    }
    if (o.min_str == 0) o.min_str = 1;
    if (o.window == 0) o.window = 256;

    /* Chat / train / one-shot ask: the brain sits next to the atn binary by
     * default (override with --brain). --train ingests first; --ask is one
     * stdin line -> one reply line -> exit; -c is the interactive loop. */
    if (do_chat || traindir || do_ask || do_score || do_score_bytes) {
        char def[4096];
        const char *bp = brainfile;
        if (!bp) {
            char exe[4000];
            ssize_t r = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
            char *slash = NULL;
            if (r > 0) { exe[r] = '\0'; slash = strrchr(exe, '/'); }
            if (slash) { *slash = '\0'; snprintf(def, sizeof(def), "%s/atn.brain", exe); }
            else snprintf(def, sizeof(def), "atn.brain");   /* fallback: cwd */
            bp = def;
        }
        if (traindir) autotrain(traindir, bp, strip_html, o.quiet);
        if (do_score)      score_query(bp);
        else if (do_score_bytes) score_query_bytes(bp);
        else if (do_ask)   chat_once(bp, o.temp, !no_learn);
        else if (do_chat)  chat_session(bp, o.temp);
        return 0;
    }

    /* Content neighbour table for the atn-ga brain network: read the chunk index
     * over a territory file, build signatures, write the binary table to -o. */
    if (do_neighbors) {
        if (optind == argc || !nn_index || !outfile) {
            fprintf(stderr, "atn: --neighbors needs TERRITORY --nn-index FILE -o OUT\n");
            return 2;
        }
        return content_build_neighbors(argv[optind], nn_index, outfile, nn_sig, nn_dfmax);
    }

    /* Corpus prep: clean + dedup + quality-filter text (files or stdin) -> stdout. */
    if (do_prep) return prep_run(argc - optind, argv + optind);

    if (optind == argc) { usage(stderr); return 2; }

    /* Real on-disk (de)compression: read the file, transform, write -o/stdout. */
    if (do_compress || do_decompress) {
        const char *path = argv[optind];
        FILE *fp = fopen(path, "rb");
        if (!fp) { fprintf(stderr, "atn: %s: %s\n", path, strerror(errno)); return 1; }
        blob b;
        if (!read_stream(fp, &b)) { fprintf(stderr, "atn: %s: read failed\n", path); fclose(fp); return 1; }
        fclose(fp);
        int rc;
        if (do_compress) {
            char def[4096];
            if (!outfile) { snprintf(def, sizeof(def), "%s.atcm", path); outfile = def; }
            rc = cm_compress_file(&b, outfile);
        } else {
            /* auto-detect: context-mixing (ATCM) or the older byte-model (ATNZ) */
            rc = cm_is_stream(&b) ? cm_decompress_file(&b, outfile)
                                  : lm_decompress_file(&b, outfile);
        }
        free(b.data);
        return rc;
    }

    /* Filesystem-as-corpus: build one model over the tree, score files. */
    if (o.corpus) {
        int rc = 0;
        for (int i = optind; i < argc; i++) rc |= scan_corpus(argv[i], &o);
        return rc;
    }

    /* Recursive filesystem scan: aggregate stats over each given root. */
    if (o.recursive) {
        int rc = 0;
        for (int i = optind; i < argc; i++) rc |= scan_tree(argv[i], &o);
        return rc;
    }

    int rc = 0, first = 1;
    for (int i = optind; i < argc; i++) {
        if (!first) printf("\n%s\n", "────────────────────────────────────────");
        first = 0;
        rc |= inspect(argv[i], &o);
    }
    return rc;
}
