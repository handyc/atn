/* scan.c — opcode/routine patterns, signatures, anomalies, custom grep. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"
#include "disasm.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

/* ---------------------------------------------------------------- */
/* Opcode / routine pattern scan (heuristic byte matching)          */
/* ---------------------------------------------------------------- */

typedef struct {
    const char *name;
    const unsigned char *bytes;
    size_t len;
} bytepat;

#define BP(...) ((const unsigned char[]){__VA_ARGS__})

static void show_hits(const blob *b, const unsigned char *pat, size_t plen,
                      const char *name, const bool *instr) {
    size_t from = 0; int n = 0, verified = 0;
    const unsigned char *p;
    size_t first_offs[6]; int nf = 0;
    while ((p = find_bytes(b->data, b->len, pat, plen, from))) {
        size_t off = (size_t)(p - b->data);
        if (nf < 6) first_offs[nf++] = off;
        n++;
        if (instr && instr[off]) verified++;
        from = off + 1;
    }
    if (n == 0) return;
    printf("  %-26s x%-6d ", name, n);
    for (int i = 0; i < nf; i++) printf("0x%zx ", first_offs[i]);
    if (n > nf) printf("...");
    if (instr) printf("  [%d at instr boundary]", verified);
    printf("\n");
}

void pattern_scan(const blob *b) {
    section("routine / opcode patterns");

    /* Disassemble the code range once so we can verify which byte matches
     * fall on real instruction boundaries (vs. coincidental data). */
    int bits = detect_bits(b);
    size_t cstart = 0, csize = b->len; uint64_t cva = 0;
    bool have_text = elf_text_range(b, &cstart, &csize, &cva);
    bool *instr = instruction_starts(b, cstart, csize, bits == 64);
    if (instr)
        printf("  (verified against a %d-bit linear sweep of %s; "
               "'instr boundary' = real instruction)\n",
               bits, have_text ? "ELF .text" : "the whole file");
    else
        printf("  (heuristic: raw byte matches, not a disassembly)\n");

    const bytepat table[] = {
        { "INT 20h (DOS terminate)", BP(0xcd,0x20), 2 },
        { "INT 21h (DOS API call)",  BP(0xcd,0x21), 2 },
        { "INT 13h (BIOS disk)",     BP(0xcd,0x13), 2 },
        { "INT 10h (BIOS video)",    BP(0xcd,0x10), 2 },
        { "INT 16h (BIOS kbd)",      BP(0xcd,0x16), 2 },
        { "INT 80h (Linux syscall)", BP(0xcd,0x80), 2 },
        { "SYSCALL (x86-64)",        BP(0x0f,0x05), 2 },
        { "SYSENTER",                BP(0x0f,0x34), 2 },
        { "INT3 breakpoint",         BP(0xcc),      1 },
        { "JMP $ (EB FE loop)",      BP(0xeb,0xfe), 2 },
        { "x86 prologue (55 8B EC)", BP(0x55,0x8b,0xec), 3 },
        { "x64 prologue (55 48 89 E5)", BP(0x55,0x48,0x89,0xe5), 4 },
        { "GetPC (call $+5)",        BP(0xe8,0x00,0x00,0x00,0x00), 5 },
        { "xor eax,eax",             BP(0x31,0xc0), 2 },
        { "CPUID",                   BP(0x0f,0xa2), 2 },
        { "RDTSC",                   BP(0x0f,0x31), 2 },
        { "PE header (PE\\0\\0)",    BP('P','E',0x00,0x00), 4 },
    };
    int any = 0;
    for (size_t i = 0; i < sizeof(table)/sizeof(table[0]); i++) {
        const unsigned char *p = find_bytes(b->data, b->len, table[i].bytes, table[i].len, 0);
        if (p) { show_hits(b, table[i].bytes, table[i].len, table[i].name, instr); any = 1; }
    }

    /* NOP sled: run of >= 8 consecutive 0x90. */
    size_t i = 0; int sleds = 0;
    while (i < b->len) {
        if (b->data[i] == 0x90) {
            size_t j = i; while (j < b->len && b->data[j] == 0x90) j++;
            if (j - i >= 8) {
                if (sleds < 4)
                    printf("  %-26s %zu bytes @ 0x%zx\n", "NOP sled (0x90 run)", j - i, i);
                sleds++; any = 1;
            }
            i = j;
        } else i++;
    }
    if (sleds > 4) printf("  ... %d more NOP sleds\n", sleds - 4);

    if (!any) printf("  none of the tracked patterns were found\n");
    free(instr);
}

/* ---------------------------------------------------------------- */
/* Signature scan: EICAR, packers, and an optional external db      */
/* ---------------------------------------------------------------- */

void malware_scan(const blob *b, const char *sigfile) {
    section("signatures");
    int hits = 0;

    /* EICAR antivirus test string (safe, standard). */
    static const char *eicar =
        "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*";
    if (find_bytes(b->data, b->len, (const unsigned char *)eicar, strlen(eicar), 0)) {
        printf("  !! EICAR antivirus test file detected (benign test pattern)\n");
        hits++;
    }

    /* Packer / installer markers — presence suggests packed/obfuscated code. */
    struct { const char *sig; const char *what; } packers[] = {
        { "UPX!",        "UPX packer" },
        { "UPX0",        "UPX packer (section)" },
        { "ASPack",      "ASPack packer" },
        { "FSG!",        "FSG packer" },
        { "MEW",         "MEW packer" },
        { "PECompact2",  "PECompact packer" },
        { "Themida",     "Themida protector" },
        { ".themida",    "Themida protector" },
        { "VMProtect",   "VMProtect protector" },
        { "petite",      "Petite packer" },
        { "MPRESS",      "MPRESS packer" },
        { "Nullsoft",    "NSIS installer" },
        { "Inno",        "Inno Setup installer" },
    };
    for (size_t i = 0; i < sizeof(packers)/sizeof(packers[0]); i++) {
        const char *s = packers[i].sig;
        if (find_bytes(b->data, b->len, (const unsigned char *)s, strlen(s), 0)) {
            printf("  ?  %s marker ('%s')\n", packers[i].what, s);
            hits++;
        }
    }

    /* Optional external signatures: lines of "name:hexpattern". */
    if (sigfile) {
        FILE *f = fopen(sigfile, "r");
        if (!f) { printf("  (could not open sig file %s)\n", sigfile); }
        else {
            char line[1024]; int loaded = 0;
            while (fgets(line, sizeof(line), f)) {
                char *nl = strchr(line, '\n'); if (nl) *nl = 0;
                if (line[0] == '#' || line[0] == 0) continue;
                char *colon = strchr(line, ':');
                if (!colon) continue;
                *colon = 0;
                unsigned char pat[256]; size_t plen = sizeof(pat);
                if (!parse_pattern(colon + 1, pat, &plen)) continue;
                loaded++;
                if (find_bytes(b->data, b->len, pat, plen, 0)) {
                    printf("  !! custom signature matched: %s\n", line);
                    hits++;
                }
            }
            fclose(f);
            printf("  (%d external signature(s) checked)\n", loaded);
        }
    }

    if (hits == 0)
        printf("  no known signatures matched (note: not a substitute for a real AV)\n");
}

/* ---------------------------------------------------------------- */
/* Anomaly / error checks                                           */
/* ---------------------------------------------------------------- */

static const char *ext_of(const char *label) {
    const char *dot = strrchr(label, '.');
    return dot ? dot + 1 : NULL;
}

static bool utf8_valid(const blob *b, size_t *bad_off) {
    size_t i = 0;
    while (i < b->len) {
        unsigned char c = b->data[i];
        int extra = c < 0x80 ? 0 : (c >> 5) == 0x6 ? 1 :
                    (c >> 4) == 0xe ? 2 : (c >> 3) == 0x1e ? 3 : -1;
        if (extra < 0) { *bad_off = i; return false; }
        if (i + (size_t)extra >= b->len) { *bad_off = i; return false; }
        for (int k = 1; k <= extra; k++)
            if ((b->data[i+k] & 0xc0) != 0x80) { *bad_off = i; return false; }
        i += extra + 1;
    }
    return true;
}

void anomaly_scan(const char *label, const blob *b) {
    section("anomalies & errors");
    int issues = 0;
    const char *mime = NULL;
    const char *type = guess_type(b, &mime);

    /* Extension vs detected type. */
    const char *ext = ext_of(label);
    if (ext && type) {
        struct { const char *e; const char *needle; } map[] = {
            {"png","PNG"},{"jpg","JPEG"},{"jpeg","JPEG"},{"gif","GIF"},
            {"pdf","PDF"},{"zip","ZIP"},{"gz","gzip"},{"elf","ELF"},
            {"wav","WAV"},{"bmp","BMP"},{"7z","7-zip"},
        };
        for (size_t i = 0; i < sizeof(map)/sizeof(map[0]); i++) {
            if (strcasecmp(ext, map[i].e) == 0 && !strstr(type, map[i].needle)) {
                printf("  !! extension .%s but content looks like: %s\n", ext, type);
                issues++;
            }
        }
    }

    /* Per-type truncation / trailer checks. */
    if (b->len >= 8 && memcmp(b->data, "\x89PNG\r\n\x1a\n", 8) == 0) {
        static const unsigned char iend[4] = {'I','E','N','D'};
        const unsigned char *p = find_bytes(b->data, b->len, iend, 4, 0);
        if (!p) { printf("  !! PNG: no IEND chunk (truncated)\n"); issues++; }
        else {
            size_t end = (size_t)(p - b->data) + 8; /* IEND + crc */
            if (end < b->len) { printf("  ?  PNG: %zu trailing bytes after IEND (appended/stego?)\n", b->len - end); issues++; }
        }
    } else if (b->len >= 3 && memcmp(b->data, "\xff\xd8\xff", 3) == 0) {
        if (!(b->len >= 2 && b->data[b->len-2]==0xff && b->data[b->len-1]==0xd9)) {
            printf("  ?  JPEG: does not end with EOI (FFD9) — truncated or appended data\n"); issues++;
        }
    } else if (b->len >= 4 && memcmp(b->data, "PK\x03\x04", 4) == 0) {
        static const unsigned char eocd[4] = {'P','K',0x05,0x06};
        if (!find_bytes(b->data, b->len, eocd, 4, 0)) {
            printf("  !! ZIP: no End-Of-Central-Directory (truncated/streamed)\n"); issues++;
        }
    } else if (b->len >= 2 && b->data[0]==0x1f && b->data[1]==0x8b) {
        if (b->len < 18) { printf("  !! gzip: too short to contain footer\n"); issues++; }
    }

    /* Text-ish problems. */
    histogram h; hist_build(b, &h);
    uint64_t print = 0, nul = 0;
    for (int i = 0; i < 256; i++) {
        if (isprint(i)||i=='\t'||i=='\n'||i=='\r') print += h.freq[i];
        if (i == 0) nul = h.freq[i];
    }
    bool textish = b->len && (double)print/(double)b->len > 0.85 && nul == 0;
    if (textish) {
        size_t bad;
        if (!utf8_valid(b, &bad)) { printf("  ?  text: invalid UTF-8 at 0x%zx (latin-1 or binary?)\n", bad); issues++; }
        uint64_t lf=0,crlf=0,cr=0;
        for (size_t i=0;i<b->len;i++){
            if(b->data[i]=='\n'){ if(i&&b->data[i-1]=='\r')crlf++; else lf++; }
            else if(b->data[i]=='\r'&&(i+1>=b->len||b->data[i+1]!='\n'))cr++;
        }
        if ((lf&&crlf)||cr) { printf("  ?  text: mixed line endings (%"PRIu64" LF, %"PRIu64" CRLF, %"PRIu64" lone-CR)\n", lf,crlf,cr); issues++; }
        if (b->len && b->data[b->len-1] != '\n') { printf("  ?  text: no trailing newline\n"); issues++; }
    } else if (nul && (double)print/(double)(b->len?b->len:1) > 0.6) {
        printf("  ?  mostly text but contains %"PRIu64" NUL byte(s)\n", nul); issues++;
    }

    /* Large uniform padding region. */
    size_t bi=0, bestrun=0, bestoff=0;
    while (bi < b->len) { unsigned char c=b->data[bi]; size_t j=bi; while(j<b->len&&b->data[j]==c)j++; if(j-bi>bestrun){bestrun=j-bi;bestoff=bi;} bi=j; }
    if (bestrun > 256 && bestrun > b->len/20) {
        printf("  ?  large uniform run: %zu identical bytes (0x%02x) @ 0x%zx\n",
               bestrun, b->data[bestoff], bestoff); issues++;
    }

    if (issues == 0) printf("  no anomalies detected\n");
}

/* ---------------------------------------------------------------- */
/* Custom pattern grep                                              */
/* ---------------------------------------------------------------- */

void grep_pattern(const blob *b, const char *spec) {
    section("pattern search");
    unsigned char pat[256]; size_t plen = sizeof(pat);
    if (!parse_pattern(spec, pat, &plen)) {
        printf("  could not parse pattern '%s'\n", spec);
        return;
    }
    printf("  searching for %zu byte(s): ", plen);
    for (size_t i = 0; i < plen; i++) printf("%02x ", pat[i]);
    printf("\n");

    size_t from = 0; int n = 0;
    const unsigned char *p;
    while ((p = find_bytes(b->data, b->len, pat, plen, from))) {
        size_t off = (size_t)(p - b->data);
        if (n < 64) {
            /* a little context */
            size_t cs = off > 4 ? off - 4 : 0;
            size_t ce = off + plen + 4; if (ce > b->len) ce = b->len;
            printf("  0x%08zx  ", off);
            for (size_t i = cs; i < ce; i++) {
                if (i == off) printf("[");
                printf("%02x", b->data[i]);
                if (i == off + plen - 1) printf("]");
                printf(" ");
            }
            printf("\n");
        }
        n++;
        from = off + 1;
    }
    if (n == 0) printf("  not found\n");
    else if (n > 64) printf("  ... %d matches total (first 64 shown)\n", n);
    else printf("  %d match(es)\n", n);
}
