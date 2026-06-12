/* structure.c — type-specific structural breakdowns. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static uint32_t be32(const unsigned char *p) {
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3];
}
static uint32_t le32(const unsigned char *p) {
    return (uint32_t)p[3]<<24 | (uint32_t)p[2]<<16 | (uint32_t)p[1]<<8 | p[0];
}
static uint16_t le16(const unsigned char *p) { return (uint16_t)(p[0] | p[1]<<8); }
static uint16_t be16(const unsigned char *p) { return (uint16_t)(p[1] | p[0]<<8); }

/* ---- PNG ---- */
static void png_struct(const blob *b) {
    printf("  PNG chunks:\n");
    size_t off = 8;
    bool seen_iend = false;
    while (off + 8 <= b->len) {
        uint32_t len = be32(b->data + off);
        char type[5] = {0};
        memcpy(type, b->data + off + 4, 4);
        printf("    0x%08zx  %-4s  %u bytes\n", off, type, len);
        if (strcmp(type, "IHDR") == 0 && off + 8 + 13 <= b->len) {
            const unsigned char *p = b->data + off + 8;
            printf("              %ux%u, %d-bit, color-type %d\n",
                   be32(p), be32(p+4), p[8], p[9]);
        }
        if (strcmp(type, "IEND") == 0) { seen_iend = true; off += 12; break; }
        off += 12 + (size_t)len; /* len + type + data + crc */
        if (len > b->len) break;
    }
    if (!seen_iend) printf("    !! no IEND chunk — file is truncated or corrupt\n");
    else if (off < b->len)
        printf("    note: %zu bytes of trailing data after IEND (0x%zx)\n",
               b->len - off, off);
}

/* ---- JPEG ---- */
static void jpeg_struct(const blob *b) {
    printf("  JPEG segments:\n");
    size_t off = 2;
    bool eoi = false;
    while (off + 2 <= b->len) {
        if (b->data[off] != 0xff) { off++; continue; }
        unsigned char marker = b->data[off + 1];
        if (marker == 0xd9) { printf("    0x%08zx  FFD9 EOI\n", off); eoi = true; off += 2; break; }
        if (marker == 0xd8 || (marker >= 0xd0 && marker <= 0xd7)) { off += 2; continue; }
        if (off + 4 > b->len) break;
        uint16_t seglen = be16(b->data + off + 2);
        const char *name =
            (marker >= 0xc0 && marker <= 0xc3) ? "SOFn (frame)" :
            marker == 0xc4 ? "DHT" : marker == 0xda ? "SOS (scan)" :
            marker == 0xdb ? "DQT" : marker == 0xe0 ? "APP0/JFIF" :
            marker == 0xe1 ? "APP1/EXIF" : marker == 0xfe ? "COM" : "segment";
        printf("    0x%08zx  FF%02X  %-12s %u bytes\n", off, marker, name, seglen);
        if (marker >= 0xc0 && marker <= 0xc3 && off + 9 <= b->len) {
            const unsigned char *p = b->data + off + 5;
            printf("              %ux%u, %d components\n", be16(p+2), be16(p), p[4]);
        }
        if (marker == 0xda) { printf("    ... entropy-coded scan data follows\n"); break; }
        off += 2 + seglen;
    }
    if (!eoi) printf("    !! no EOI (FFD9) marker — possibly truncated\n");
}

/* ---- GIF ---- */
static void gif_struct(const blob *b) {
    if (b->len < 13) { printf("  GIF header too short\n"); return; }
    char ver[4] = {0}; memcpy(ver, b->data + 3, 3);
    printf("  GIF8%s: %ux%u, %s\n", ver, le16(b->data+6), le16(b->data+8),
           (b->data[10] & 0x80) ? "global color table" : "no global color table");
}

/* ---- BMP ---- */
static void bmp_struct(const blob *b) {
    if (b->len < 26) { printf("  BMP header too short\n"); return; }
    printf("  BMP: file size %u bytes, pixel data @ 0x%x\n",
           le32(b->data+2), le32(b->data+10));
    printf("       %dx%d, %u bpp\n", (int32_t)le32(b->data+18),
           (int32_t)le32(b->data+22), le16(b->data+28));
}

/* ---- WAV / RIFF ---- */
static void wav_struct(const blob *b) {
    printf("  RIFF size %u, form '%.4s'\n", le32(b->data+4), b->data+8);
    size_t off = 12;
    while (off + 8 <= b->len) {
        char id[5] = {0}; memcpy(id, b->data + off, 4);
        uint32_t sz = le32(b->data + off + 4);
        printf("    0x%08zx  '%-4s'  %u bytes\n", off, id, sz);
        if (strcmp(id, "fmt ") == 0 && off + 8 + 16 <= b->len) {
            const unsigned char *p = b->data + off + 8;
            printf("              format %u, %u ch, %u Hz, %u-bit\n",
                   le16(p), le16(p+2), le32(p+4), le16(p+14));
        }
        off += 8 + sz + (sz & 1);
    }
}

/* ---- gzip ---- */
static void gzip_struct(const blob *b) {
    if (b->len < 10) { printf("  gzip header too short\n"); return; }
    unsigned char flg = b->data[3];
    uint32_t mtime = le32(b->data + 4);
    printf("  gzip: method %s, mtime %u\n",
           b->data[2] == 8 ? "deflate" : "?", mtime);
    if (flg & 0x08) { /* FNAME */
        size_t p = 10;
        if (flg & 0x04) { if (p+2<=b->len) p += 2 + le16(b->data+p); } /* FEXTRA */
        if (p < b->len) printf("       original name: %.*s\n",
                               (int)(b->len - p), b->data + p);
    }
    if (b->len >= 8)
        printf("       uncompressed size (mod 4G): %u bytes\n",
               le32(b->data + b->len - 4));
}

/* ---- ELF ---- */
static void elf_struct(const blob *b) {
    if (b->len < 20) { printf("  ELF header too short\n"); return; }
    const unsigned char *e = b->data;
    int is64 = e[4] == 2;
    int le = e[5] == 1;
    uint16_t type = le ? le16(e+16) : be16(e+16);
    uint16_t mach = le ? le16(e+18) : be16(e+18);
    const char *types[] = {"none","relocatable","executable","shared-object","core"};
    const char *tn = type < 5 ? types[type] : "?";
    const char *mn =
        mach==0x3e?"x86-64":mach==0x03?"x86":mach==0xb7?"AArch64":
        mach==0x28?"ARM":mach==0xf3?"RISC-V":mach==0x08?"MIPS":
        mach==0x15?"PPC64":"machine?";
    printf("  ELF %d-bit %s-endian, %s, %s\n", is64?64:32, le?"little":"big", tn, mn);
    if (is64 && b->len >= 64) {
        uint64_t entry = 0; memcpy(&entry, e+24, 8);
        uint16_t phnum = le16(e+56), shnum = le16(e+60);
        printf("      entry 0x%" PRIx64 ", %u program headers, %u sections\n",
               entry, phnum, shnum);
    }
}

/* ---- ZIP ---- */
static void zip_struct(const blob *b) {
    /* Find End Of Central Directory (PK\5\6), scanning backwards. */
    static const unsigned char eocd[4] = {'P','K',0x05,0x06};
    size_t pos = 0; bool found = false;
    if (b->len >= 22) {
        for (size_t i = b->len - 22 + 1; i-- > 0; ) {
            if (memcmp(b->data + i, eocd, 4) == 0) { pos = i; found = true; break; }
            if (b->len - i > 65557) break; /* max comment size guard */
        }
    }
    if (!found) { printf("  ZIP: no End-Of-Central-Directory — truncated/streamed\n"); return; }
    uint16_t nent = le16(b->data + pos + 10);
    uint32_t cdoff = le32(b->data + pos + 16);
    printf("  ZIP: %u entries, central dir @ 0x%x\n", nent, cdoff);

    size_t off = cdoff; int shown = 0;
    static const unsigned char cdh[4] = {'P','K',0x01,0x02};
    while (off + 46 <= b->len && memcmp(b->data + off, cdh, 4) == 0) {
        uint16_t method = le16(b->data + off + 10);
        uint32_t csz = le32(b->data + off + 20), usz = le32(b->data + off + 24);
        uint16_t nlen = le16(b->data + off + 28);
        uint16_t elen = le16(b->data + off + 30);
        uint16_t clen = le16(b->data + off + 32);
        if (shown < 20 && off + 46 + nlen <= b->len) {
            printf("    %-30.*s %s %u->%u\n", nlen, b->data + off + 46,
                   method == 0 ? "stored " : method == 8 ? "deflate" : "method?",
                   usz, csz);
        }
        shown++;
        off += 46 + nlen + elen + clen;
    }
    if (shown > 20) printf("    ... and %d more entries\n", shown - 20);
}

/* ---- PE / COFF (Windows executables) ---- */
static void pe_struct(const blob *b) {
    if (b->len < 0x40) { printf("  PE: too short\n"); return; }
    uint32_t peoff = le32(b->data + 0x3c);
    if (peoff + 24 > b->len || memcmp(b->data + peoff, "PE\0\0", 4) != 0) {
        printf("  MZ header but no PE signature (likely a DOS executable)\n");
        return;
    }
    const unsigned char *coff = b->data + peoff + 4;
    uint16_t mach = le16(coff), nsec = le16(coff + 2);
    uint16_t optsz = le16(coff + 16), chars = le16(coff + 18);
    const char *mn = mach==0x8664?"x86-64":mach==0x14c?"x86":mach==0xaa64?"ARM64":
                     mach==0x1c0?"ARM":"machine?";
    printf("  PE: %s, %u sections, %s\n", mn, nsec,
           (chars & 0x2000) ? "DLL" : (chars & 0x0002) ? "executable" : "object");

    const unsigned char *end = b->data + b->len;
    const unsigned char *opt = coff + 20;
    if (opt + 2 <= end) {
        uint16_t magic = le16(opt);
        bool plus = magic == 0x20b;
        printf("      format %s, entry RVA 0x%x\n", plus?"PE32+":"PE32",
               (opt + 20 <= end) ? le32(opt + 16) : 0);
        if (opt + 70 <= end) {
            uint16_t subsys = le16(opt + 68);
            printf("      subsystem %s\n",
                   subsys==2?"GUI":subsys==3?"console":subsys==1?"native":"?");
        }
    }
    const unsigned char *sec = opt + optsz;
    printf("  sections:\n");
    for (int i = 0; i < nsec && sec + 40 <= b->data + b->len; i++, sec += 40) {
        char nm[9] = {0}; memcpy(nm, sec, 8);
        uint32_t vsz = le32(sec + 8), rsz = le32(sec + 16), flags = le32(sec + 36);
        printf("    %-8s vsize %-8u rawsize %-8u %s%s%s\n", nm, vsz, rsz,
               (flags & 0x20000000) ? "X" : "-",
               (flags & 0x40000000) ? "R" : "-",
               (flags & 0x80000000) ? "W" : "-");
    }
}

/* ---- MP4 / ISO-BMFF (recursive box walk) ---- */
static void mp4_boxes(const blob *b, size_t off, size_t end, int depth) {
    while (off + 8 <= end) {
        uint32_t size = (uint32_t)b->data[off]<<24 | (uint32_t)b->data[off+1]<<16 |
                        (uint32_t)b->data[off+2]<<8 | b->data[off+3];
        char type[5] = {0}; memcpy(type, b->data + off + 4, 4);
        size_t boxlen = size, hdr = 8;
        if (size == 1) { /* 64-bit largesize */
            if (off + 16 > end) break;
            uint64_t big = 0; for (int k = 0; k < 8; k++) big = big<<8 | b->data[off+8+k];
            boxlen = (size_t)big; hdr = 16;
        } else if (size == 0) boxlen = end - off;
        if (boxlen < hdr || off + boxlen > end) {
            printf("  %*s0x%08zx  %-4s  (bad size %u)\n", depth*2, "", off, type, size);
            break;
        }
        printf("  %*s0x%08zx  %-4s  %zu bytes\n", depth*2, "", off, type, boxlen);
        /* Recurse into known container boxes. */
        if (depth < 4 && (!strcmp(type,"moov")||!strcmp(type,"trak")||!strcmp(type,"mdia")||
            !strcmp(type,"minf")||!strcmp(type,"stbl")||!strcmp(type,"udta")||
            !strcmp(type,"moof")||!strcmp(type,"traf")||!strcmp(type,"edts")))
            mp4_boxes(b, off + hdr, off + boxlen, depth + 1);
        off += boxlen;
    }
}
static void mp4_struct(const blob *b) {
    char brand[5] = {0}; if (b->len >= 12) memcpy(brand, b->data + 8, 4);
    printf("  ISO-BMFF (MP4/MOV), major brand '%s'\n", brand);
    printf("  boxes:\n");
    mp4_boxes(b, 0, b->len, 1);
}

/* ---- PDF (object / xref / trailer survey) ---- */
static void pdf_struct(const blob *b) {
    char ver[8] = {0};
    size_t vn = 0; for (size_t i = 5; i < b->len && i < 12 && b->data[i] != '\n' && b->data[i] != '\r'; i++) ver[vn++] = b->data[i];
    printf("  PDF version %s\n", ver);

    static const unsigned char obj[] = {' ','o','b','j'};
    static const unsigned char strm[] = {'s','t','r','e','a','m'};
    static const unsigned char xref[] = {'x','r','e','f'};
    static const unsigned char eof[] = {'%','%','E','O','F'};

    size_t nobj = 0, nstream = 0, from = 0; const unsigned char *p;
    while ((p = find_bytes(b->data, b->len, obj, 4, from))) { nobj++; from = (size_t)(p - b->data) + 1; }
    from = 0;
    while ((p = find_bytes(b->data, b->len, strm, 6, from))) { nstream++; from = (size_t)(p - b->data) + 1; }
    int nxref = 0; from = 0;
    while ((p = find_bytes(b->data, b->len, xref, 4, from))) { nxref++; from = (size_t)(p - b->data) + 1; }
    int neof = 0; from = 0;
    while ((p = find_bytes(b->data, b->len, eof, 5, from))) { neof++; from = (size_t)(p - b->data) + 1; }

    printf("  %zu indirect objects, %zu streams, %d xref section(s), %d %%%%EOF marker(s)\n",
           nobj, nstream, nxref, neof);
    if (neof > 1) printf("  note: %d EOF markers — incrementally updated (or appended) PDF\n", neof);

    /* Flag content that often indicates active/suspicious PDFs. */
    struct { const char *s; const char *what; } flags[] = {
        {"/JavaScript","JavaScript"},{"/JS","JS action"},{"/OpenAction","auto-run OpenAction"},
        {"/AA","additional actions"},{"/Launch","Launch action"},{"/EmbeddedFile","embedded file"},
        {"/RichMedia","rich media"},{"/AcroForm","form"},
    };
    for (size_t i = 0; i < sizeof(flags)/sizeof(flags[0]); i++)
        if (find_bytes(b->data, b->len, (const unsigned char*)flags[i].s, strlen(flags[i].s), 0))
            printf("  ?  contains %s (%s)\n", flags[i].s, flags[i].what);
}

void structure_report(const blob *b) {
    section("structure");
    if (b->len < 4) { printf("  (too small to parse)\n"); return; }
    const unsigned char *d = b->data;

    if (b->len >= 8 && memcmp(d, "\x89PNG\r\n\x1a\n", 8) == 0) png_struct(b);
    else if (memcmp(d, "\xff\xd8\xff", 3) == 0) jpeg_struct(b);
    else if (memcmp(d, "GIF8", 4) == 0) gif_struct(b);
    else if (memcmp(d, "BM", 2) == 0 && b->len >= 26) bmp_struct(b);
    else if (memcmp(d, "RIFF", 4) == 0) wav_struct(b);
    else if (d[0]==0x1f && d[1]==0x8b) gzip_struct(b);
    else if (memcmp(d, "\x7f""ELF", 4) == 0) elf_struct(b);
    else if (memcmp(d, "PK\x03\x04", 4) == 0 || memcmp(d, "PK\x05\x06", 4) == 0)
        zip_struct(b);
    else if (memcmp(d, "MZ", 2) == 0) pe_struct(b);
    else if (memcmp(d, "%PDF", 4) == 0) pdf_struct(b);
    else if (b->len >= 8 && memcmp(d + 4, "ftyp", 4) == 0) mp4_struct(b);
    else printf("  no structural parser for this type yet\n");
}
