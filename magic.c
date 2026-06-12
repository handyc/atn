/* magic.c — type identification and embedded-signature carving. */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <stdio.h>
#include <string.h>

#define SIG(...) ((const unsigned char[]){__VA_ARGS__})

typedef struct {
    const char *name;
    const char *mime;
    unsigned char sig[16];  /* stored inline so the table can be static */
    size_t siglen;
    size_t offset;        /* where the signature must appear        */
    bool   carve;         /* include in embedded-file scanning      */
} magic;

/* The table is shared by guess_type (offset 0/anchored) and embedded_scan
 * (carve == true entries searched at any offset). Signature bytes are copied
 * in by value so the pointers never dangle. */
static const magic *magic_table(size_t *count) {
    static magic t[64];
    size_t n = 0;
#define ADD(NM, MM, S, OFF, CARVE) \
    do { t[n].name=(NM); t[n].mime=(MM); \
         memcpy(t[n].sig, (S), sizeof(S)); \
         t[n].siglen=sizeof(S); t[n].offset=(OFF); t[n].carve=(CARVE); n++; } while (0)

    ADD("ELF executable/object", "application/x-elf",
        SIG(0x7f,'E','L','F'), 0, true);
    ADD("PE/COFF executable (DOS MZ)", "application/x-dosexec",
        SIG('M','Z'), 0, false);
    ADD("PNG image", "image/png",
        SIG(0x89,'P','N','G',0x0d,0x0a,0x1a,0x0a), 0, true);
    ADD("JPEG image", "image/jpeg",
        SIG(0xff,0xd8,0xff), 0, true);
    ADD("GIF image", "image/gif",
        SIG('G','I','F','8'), 0, true);
    ADD("BMP image", "image/bmp",
        SIG('B','M'), 0, false);
    ADD("TIFF image (LE)", "image/tiff",
        SIG('I','I',0x2a,0x00), 0, true);
    ADD("TIFF image (BE)", "image/tiff",
        SIG('M','M',0x00,0x2a), 0, true);
    ADD("PDF document", "application/pdf",
        SIG('%','P','D','F'), 0, true);
    ADD("PostScript", "application/postscript",
        SIG('%','!','P','S'), 0, false);
    ADD("ZIP archive (or docx/xlsx/jar/apk)", "application/zip",
        SIG('P','K',0x03,0x04), 0, true);
    ADD("ZIP archive (empty)", "application/zip",
        SIG('P','K',0x05,0x06), 0, false);
    ADD("gzip compressed", "application/gzip",
        SIG(0x1f,0x8b), 0, true);
    ADD("bzip2 compressed", "application/x-bzip2",
        SIG('B','Z','h'), 0, true);
    ADD("xz compressed", "application/x-xz",
        SIG(0xfd,'7','z','X','Z',0x00), 0, true);
    ADD("zstd compressed", "application/zstd",
        SIG(0x28,0xb5,0x2f,0xfd), 0, true);
    ADD("lz4 frame", "application/x-lz4",
        SIG(0x04,0x22,0x4d,0x18), 0, true);
    ADD("7-zip archive", "application/x-7z-compressed",
        SIG('7','z',0xbc,0xaf,0x27,0x1c), 0, true);
    ADD("RAR archive (v5)", "application/x-rar",
        SIG('R','a','r','!',0x1a,0x07,0x01,0x00), 0, true);
    ADD("RAR archive (v4)", "application/x-rar",
        SIG('R','a','r','!',0x1a,0x07,0x00), 0, true);
    ADD("cpio archive", "application/x-cpio",
        SIG('0','7','0','7','0'), 0, false);
    ADD("Debian package", "application/vnd.debian.binary-package",
        SIG('!','<','a','r','c','h','>'), 0, false);
    ADD("tar archive", "application/x-tar",
        SIG('u','s','t','a','r'), 257, false);
    ADD("Mach-O (64-bit LE)", "application/x-mach-binary",
        SIG(0xcf,0xfa,0xed,0xfe), 0, true);
    ADD("Mach-O (32-bit LE)", "application/x-mach-binary",
        SIG(0xce,0xfa,0xed,0xfe), 0, true);
    ADD("Mach-O universal (fat)", "application/x-mach-binary",
        SIG(0xca,0xfe,0xba,0xbe), 0, false);
    ADD("Java class", "application/java-vm",
        SIG(0xca,0xfe,0xba,0xbe), 0, false);  /* same magic as fat Mach-O */
    ADD("WebAssembly module", "application/wasm",
        SIG(0x00,'a','s','m'), 0, true);
    ADD("Ogg media", "application/ogg",
        SIG('O','g','g','S'), 0, true);
    ADD("FLAC audio", "audio/flac",
        SIG('f','L','a','C'), 0, true);
    ADD("MP3 audio (ID3)", "audio/mpeg",
        SIG('I','D','3'), 0, true);
    ADD("Matroska/WebM", "video/x-matroska",
        SIG(0x1a,0x45,0xdf,0xa3), 0, true);
    ADD("MP4/QuickTime (ftyp)", "video/mp4",
        SIG('f','t','y','p'), 4, false);
    ADD("RIFF (WAV/AVI/WebP)", "application/octet-stream",
        SIG('R','I','F','F'), 0, false);
    ADD("SQLite 3 database", "application/vnd.sqlite3",
        SIG('S','Q','L','i','t','e',' ','f'), 0, true);
    ADD("Git pack index", "application/octet-stream",
        SIG(0xff,'t','O','c'), 0, false);
    ADD("ICO icon", "image/x-icon",
        SIG(0x00,0x00,0x01,0x00), 0, false);
    ADD("Windows shortcut (.lnk)", "application/x-ms-shortcut",
        SIG('L',0x00,0x00,0x00,0x01,0x14,0x02,0x00), 0, false);
    ADD("Shebang script", "text/x-script",
        SIG('#','!'), 0, false);
    ADD("UTF-8 BOM text", "text/plain",
        SIG(0xef,0xbb,0xbf), 0, false);
    ADD("UTF-16 LE BOM text", "text/plain",
        SIG(0xff,0xfe), 0, false);
    ADD("UTF-16 BE BOM text", "text/plain",
        SIG(0xfe,0xff), 0, false);

#undef ADD
    *count = n;
    return t;
}

/* RIFF disambiguation: bytes 8..11 hold the form type. */
static const char *riff_subtype(const blob *b) {
    if (b->len < 12) return "RIFF container";
    if (memcmp(b->data + 8, "WAVE", 4) == 0) return "WAV audio";
    if (memcmp(b->data + 8, "AVI ", 4) == 0) return "AVI video";
    if (memcmp(b->data + 8, "WEBP", 4) == 0) return "WebP image";
    return "RIFF container";
}

const char *guess_type(const blob *b, const char **mime) {
    size_t count;
    const magic *t = magic_table(&count);
    for (size_t i = 0; i < count; i++) {
        const magic *m = &t[i];
        if (b->len >= m->offset + m->siglen &&
            memcmp(b->data + m->offset, m->sig, m->siglen) == 0) {
            if (strcmp(m->name, "RIFF (WAV/AVI/WebP)") == 0) {
                if (mime) *mime = m->mime;
                return riff_subtype(b);
            }
            if (mime) *mime = m->mime;
            return m->name;
        }
    }
    if (mime) *mime = NULL;
    return NULL;
}

void embedded_scan(const blob *b) {
    section("embedded signatures");
    size_t count;
    const magic *t = magic_table(&count);

    int hits = 0;
    /* Start at offset 1 so we don't re-report the file's own header. */
    for (size_t i = 0; i < count; i++) {
        const magic *m = &t[i];
        if (!m->carve) continue;
        size_t from = 1;
        const unsigned char *p;
        int per_sig = 0;
        while ((p = find_bytes(b->data, b->len, m->sig, m->siglen, from))) {
            size_t off = (size_t)(p - b->data);
            printf("  0x%08zx  %s\n", off, m->name);
            hits++;
            per_sig++;
            from = off + 1;
            if (per_sig >= 8) { printf("  ...           (more %s hits suppressed)\n", m->name); break; }
        }
    }
    if (hits == 0)
        printf("  none found past the file header\n");
    else
        printf("  (%d signature hit(s); a hit is a magic match, not a guarantee)\n", hits);
}
