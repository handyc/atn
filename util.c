/* util.c — shared helpers and the byte histogram. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

bool read_stream(FILE *fp, blob *out) {
    size_t cap = 1 << 16, len = 0;
    unsigned char *buf = malloc(cap);
    if (!buf) return false;
    for (;;) {
        if (len == cap) {
            size_t ncap = cap * 2;
            unsigned char *nb = realloc(buf, ncap);
            if (!nb) { free(buf); return false; }
            buf = nb; cap = ncap;
        }
        size_t got = fread(buf + len, 1, cap - len, fp);
        len += got;
        if (got == 0) { if (ferror(fp)) { free(buf); return false; } break; }
    }
    out->data = buf; out->len = len;
    return true;
}

void hist_build(const blob *b, histogram *h) {
    memset(h, 0, sizeof(*h));
    for (size_t i = 0; i < b->len; i++) h->freq[b->data[i]]++;
    h->total = b->len;
}

double hist_entropy(const histogram *h) {
    if (h->total == 0) return 0.0;
    double H = 0.0;
    for (int i = 0; i < 256; i++) {
        if (h->freq[i]) {
            double p = (double)h->freq[i] / (double)h->total;
            H -= p * log2(p);
        }
    }
    return H;
}

void section(const char *title) {
    printf("\n\033[1m== %s ==\033[0m\n", title);
}

void human_size(uint64_t n, char *out, size_t outlen) {
    static const char *u[] = {"B", "KiB", "MiB", "GiB", "TiB", "PiB"};
    double v = (double)n;
    int i = 0;
    while (v >= 1024.0 && i < 5) { v /= 1024.0; i++; }
    if (i == 0) snprintf(out, outlen, "%" PRIu64 " %s", n, u[i]);
    else        snprintf(out, outlen, "%.1f %s (%" PRIu64 " bytes)", v, u[i], n);
}

/* Map 0..1 values onto the eight block glyphs, UTF-8 encoded into out. */
void sparkline(const double *vals, size_t n, char *out, size_t outlen) {
    static const char *blocks[8] = {
        "▁","▂","▃","▄","▅","▆","▇","█"
    };
    size_t pos = 0;
    for (size_t i = 0; i < n; i++) {
        double v = vals[i];
        if (v < 0) v = 0;
        if (v > 1) v = 1;
        int idx = (int)(v * 7.999);
        const char *g = blocks[idx];
        size_t glen = strlen(g);
        if (pos + glen + 1 >= outlen) break;
        memcpy(out + pos, g, glen);
        pos += glen;
    }
    out[pos] = '\0';
}

const unsigned char *find_bytes(const unsigned char *hay, size_t haylen,
                                const unsigned char *needle, size_t nlen,
                                size_t from) {
    if (nlen == 0 || from >= haylen || nlen > haylen - from) return NULL;
    const unsigned char first = needle[0];
    for (size_t i = from; i + nlen <= haylen; i++) {
        if (hay[i] == first && memcmp(hay + i, needle, nlen) == 0)
            return hay + i;
    }
    return NULL;
}

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool parse_pattern(const char *spec, unsigned char *out, size_t *outlen) {
    size_t cap = *outlen, n = 0;

    /* Form 1: \xNN\xNN... */
    if (strncmp(spec, "\\x", 2) == 0) {
        const char *p = spec;
        while (*p) {
            if (p[0] == '\\' && p[1] == 'x') {
                int hi = hexval(p[2]), lo = hexval(p[3]);
                if (hi < 0 || lo < 0 || n >= cap) return false;
                out[n++] = (unsigned char)(hi * 16 + lo);
                p += 4;
            } else return false;
        }
        *outlen = n;
        return n > 0;
    }

    /* Form 2: pure hex (with optional spaces), e.g. "CD21" or "cd 21". */
    bool all_hex = true;
    for (const char *p = spec; *p; p++)
        if (!isxdigit((unsigned char)*p) && *p != ' ') { all_hex = false; break; }
    if (all_hex) {
        int hi = -1;
        for (const char *p = spec; *p; p++) {
            if (*p == ' ') continue;
            int v = hexval(*p);
            if (hi < 0) hi = v;
            else { if (n >= cap) return false; out[n++] = (unsigned char)(hi*16+v); hi = -1; }
        }
        if (hi >= 0) return false; /* odd number of nibbles */
        if (n > 0) { *outlen = n; return true; }
    }

    /* Form 3: literal ASCII. */
    size_t l = strlen(spec);
    if (l == 0 || l > cap) return false;
    memcpy(out, spec, l);
    *outlen = l;
    return true;
}
