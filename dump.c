/* dump.c — basic report, hex dump, string extraction. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static const char *mode_string(mode_t m, char *buf) {
    const char *rwx = "rwxrwxrwx";
    buf[0] = S_ISDIR(m) ? 'd' : S_ISLNK(m) ? 'l' : S_ISCHR(m) ? 'c'
           : S_ISBLK(m) ? 'b' : S_ISFIFO(m) ? 'p' : S_ISSOCK(m) ? 's' : '-';
    for (int i = 0; i < 9; i++)
        buf[i + 1] = (m & (1 << (8 - i))) ? rwx[i] : '-';
    buf[10] = '\0';
    return buf;
}

void report_basic(const char *label, const struct stat *st, const blob *b) {
    char sz[64], modebuf[11], tbuf[64];
    human_size(b->len, sz, sizeof(sz));

    printf("\033[1m%s\033[0m\n", label);
    printf("  size       %s\n", sz);
    if (st->st_mode) {
        printf("  mode       %s (%04o)   uid %u  gid %u\n",
               mode_string(st->st_mode, modebuf),
               (unsigned)(st->st_mode & 07777),
               (unsigned)st->st_uid, (unsigned)st->st_gid);
        printf("  inode      %ju   links %ju\n",
               (uintmax_t)st->st_ino, (uintmax_t)st->st_nlink);
        struct tm tm; time_t mt = st->st_mtime; localtime_r(&mt, &tm);
        strftime(tbuf, sizeof(tbuf), "%Y-%m-%d %H:%M:%S", &tm);
        printf("  modified   %s\n", tbuf);
    }

    const char *mime = NULL;
    const char *type = guess_type(b, &mime);
    if (b->len == 0) { printf("  type       (empty file)\n"); return; }

    histogram h; hist_build(b, &h);
    uint64_t print = 0, nul = h.freq[0], high = 0;
    for (int i = 0; i < 256; i++) {
        if (isprint(i)||i=='\t'||i=='\n'||i=='\r') print += h.freq[i];
        if (i >= 0x80) high += h.freq[i];
    }
    bool text = nul == 0 && (double)print/(double)b->len >= 0.95;
    if (!type) type = text ? "text / ASCII" : "data (unrecognized)";

    printf("  type       %s%s%s\n", type,
           mime ? "  ·  " : "", mime ? mime : "");
    printf("  class      %s  (%.1f%% printable, %"PRIu64" NUL, %"PRIu64" high-bit)\n",
           text ? "text" : "binary",
           100.0 * (double)print / (double)b->len, nul, high);
    printf("  entropy    %.3f bits/byte\n", hist_entropy(&h));
}

void hex_dump(const blob *b, long limit) {
    section("hex dump");
    size_t n = b->len;
    bool truncated = false;
    if (limit > 0 && (size_t)limit < n) { n = (size_t)limit; truncated = true; }

    for (size_t off = 0; off < n; off += 16) {
        printf("  %08zx  ", off);
        for (size_t i = 0; i < 16; i++) {
            if (off + i < n) printf("%02x ", b->data[off + i]);
            else printf("   ");
            if (i == 7) putchar(' ');
        }
        printf(" |");
        for (size_t i = 0; i < 16 && off + i < n; i++) {
            unsigned char c = b->data[off + i];
            putchar(isprint(c) ? c : '.');
        }
        printf("|\n");
    }
    if (truncated)
        printf("  ... %zu of %zu bytes shown (use -n 0 for all)\n", n, b->len);
}

void extract_strings(const blob *b, size_t minlen) {
    section("strings");
    size_t start = 0, run = 0; int found = 0;
    for (size_t i = 0; i <= b->len; i++) {
        unsigned char c = (i < b->len) ? b->data[i] : 0;
        bool ok = (i < b->len) && (isprint(c) || c == '\t');
        if (ok) { if (run == 0) start = i; run++; }
        else {
            if (run >= minlen) {
                printf("  0x%08zx  %.*s\n", start, (int)run, b->data + start);
                found++;
            }
            run = 0;
        }
    }
    if (!found) printf("  (no strings >= %zu chars)\n", minlen);
}
