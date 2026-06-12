/* disasm.c — x86 / x86-64 length disassembler and linear sweep. */
#define _POSIX_C_SOURCE 200809L

#include "disasm.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Per-opcode flags. */
#define F_MODRM 0x01
#define F_IB    0x02   /* imm8                                  */
#define F_IW    0x04   /* imm16                                 */
#define F_IZ    0x08   /* imm16 if opsize else imm32            */
#define F_IV    0x10   /* imm16/32/64 (B8-BF mov, rex.w => 64)  */
#define F_MOFF  0x20   /* moffs, size = address size            */

static uint8_t op1[256];
static uint8_t op2[256];
static bool tables_ready = false;

static void init_tables(void) {
    if (tables_ready) return;
    memset(op1, 0, sizeof(op1));
    memset(op2, 0, sizeof(op2));

    /* One-byte map. Arithmetic groups 00..3D share a layout. */
    const int arith[] = {0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38};
    for (size_t g = 0; g < sizeof(arith)/sizeof(arith[0]); g++) {
        int base = arith[g];
        op1[base+0] = F_MODRM; op1[base+1] = F_MODRM;
        op1[base+2] = F_MODRM; op1[base+3] = F_MODRM;
        op1[base+4] = F_IB;    op1[base+5] = F_IZ;
    }
    op1[0x62] = F_MODRM;   /* BOUND / (EVEX in 64-bit, not handled) */
    op1[0x63] = F_MODRM;   /* ARPL / MOVSXD                          */
    op1[0x68] = F_IZ;      op1[0x69] = F_MODRM|F_IZ;
    op1[0x6A] = F_IB;      op1[0x6B] = F_MODRM|F_IB;
    for (int i = 0x70; i <= 0x7F; i++) op1[i] = F_IB;     /* Jcc rel8 */
    op1[0x80] = F_MODRM|F_IB; op1[0x81] = F_MODRM|F_IZ;
    op1[0x82] = F_MODRM|F_IB; op1[0x83] = F_MODRM|F_IB;
    for (int i = 0x84; i <= 0x8F; i++) op1[i] = F_MODRM;  /* test/xchg/mov/lea/pop */
    op1[0x9A] = 0;  /* far ptr — handled specially */
    for (int i = 0xA0; i <= 0xA3; i++) op1[i] = F_MOFF;   /* mov moffs */
    op1[0xA8] = F_IB; op1[0xA9] = F_IZ;                   /* test al/eax */
    for (int i = 0xB0; i <= 0xB7; i++) op1[i] = F_IB;     /* mov r8, ib */
    for (int i = 0xB8; i <= 0xBF; i++) op1[i] = F_IV;     /* mov r, iv  */
    op1[0xC0] = F_MODRM|F_IB; op1[0xC1] = F_MODRM|F_IB;
    op1[0xC2] = F_IW;                                     /* ret imm16  */
    op1[0xC4] = F_MODRM; op1[0xC5] = F_MODRM;             /* les/lds (VEX in 64-bit) */
    op1[0xC6] = F_MODRM|F_IB; op1[0xC7] = F_MODRM|F_IZ;
    op1[0xC8] = 0;  /* ENTER iw,ib — handled specially */
    op1[0xCA] = F_IW;                                     /* retf imm16 */
    op1[0xCD] = F_IB;                                     /* int n      */
    op1[0xD0] = F_MODRM; op1[0xD1] = F_MODRM;
    op1[0xD2] = F_MODRM; op1[0xD3] = F_MODRM;
    op1[0xD4] = F_IB; op1[0xD5] = F_IB;                   /* aam/aad    */
    for (int i = 0xD8; i <= 0xDF; i++) op1[i] = F_MODRM;  /* x87        */
    for (int i = 0xE0; i <= 0xE3; i++) op1[i] = F_IB;     /* loop/jcxz  */
    op1[0xE4] = F_IB; op1[0xE5] = F_IB; op1[0xE6] = F_IB; op1[0xE7] = F_IB;
    op1[0xE8] = F_IZ; op1[0xE9] = F_IZ; op1[0xEB] = F_IB; /* call/jmp rel */
    op1[0xF6] = F_MODRM; op1[0xF7] = F_MODRM;             /* grp3 (+imm if reg<2) */
    op1[0xFE] = F_MODRM; op1[0xFF] = F_MODRM;

    /* Two-byte map (0F xx): assume ModRM, then carve exceptions. */
    for (int i = 0; i < 256; i++) op2[i] = F_MODRM;
    int nomodrm[] = {0x05,0x06,0x07,0x08,0x09,0x0B,0x0E,0x30,0x31,0x32,0x33,
                     0x34,0x35,0x77,0xA0,0xA1,0xA2,0xA8,0xA9,0xAA};
    for (size_t i = 0; i < sizeof(nomodrm)/sizeof(nomodrm[0]); i++) op2[nomodrm[i]] = 0;
    for (int i = 0xC8; i <= 0xCF; i++) op2[i] = 0;        /* bswap      */
    for (int i = 0x80; i <= 0x8F; i++) op2[i] = F_IZ;     /* jcc rel32  */
    int imm8_2[] = {0x70,0x71,0x72,0x73,0xA4,0xAC,0xBA,0xC2,0xC4,0xC5,0xC6};
    for (size_t i = 0; i < sizeof(imm8_2)/sizeof(imm8_2[0]); i++)
        op2[imm8_2[i]] = F_MODRM|F_IB;

    tables_ready = true;
}

static bool is_prefix(unsigned char c) {
    switch (c) {
        case 0xF0: case 0xF2: case 0xF3:
        case 0x2E: case 0x36: case 0x3E: case 0x26: case 0x64: case 0x65:
        case 0x66: case 0x67: return true;
        default: return false;
    }
}

/* Best-effort mnemonic for display (subset; NULL if unknown). */
static const char *mnemonic_of(int opl, const unsigned char *op, unsigned char modrm) {
    if (opl == 1) {
        switch (op[0]) {
            case 0xCC: return "int3";
            case 0xCD: return "int";
            case 0xCE: return "into";
            case 0xF1: return "int1";
            case 0xC3: return "ret";
            case 0xC2: return "ret";
            case 0xCB: return "retf";
            case 0xC9: return "leave";
            case 0xC8: return "enter";
            case 0x90: return "nop";
            case 0xE8: return "call";
            case 0xE9: case 0xEB: return "jmp";
            case 0xF4: return "hlt";
            case 0xFA: return "cli";
            case 0xFB: return "sti";
            case 0xFC: return "cld";
            case 0xFD: return "std";
            case 0x9C: return "pushf";
            case 0x9D: return "popf";
            case 0xCF: return "iret";
            case 0x8D: return "lea";
            case 0xE6: case 0xE7: case 0xEE: case 0xEF: return "out";
            case 0xE4: case 0xE5: case 0xEC: case 0xED: return "in";
        }
        if (op[0] >= 0x50 && op[0] <= 0x57) return "push";
        if (op[0] >= 0x58 && op[0] <= 0x5F) return "pop";
        if (op[0] >= 0x70 && op[0] <= 0x7F) return "jcc";
        if (op[0] >= 0xB8 && op[0] <= 0xBF) return "mov";
        if (op[0] >= 0x88 && op[0] <= 0x8B) return "mov";
        switch (op[0] & 0xF8) { default: break; }
        switch (op[0]) {
            case 0x00: case 0x01: case 0x02: case 0x03: case 0x04: case 0x05: return "add";
            case 0x28: case 0x29: case 0x2A: case 0x2B: case 0x2C: case 0x2D: return "sub";
            case 0x30: case 0x31: case 0x32: case 0x33: case 0x34: case 0x35: return "xor";
            case 0x38: case 0x39: case 0x3A: case 0x3B: case 0x3C: case 0x3D: return "cmp";
            case 0x84: case 0x85: return "test";
        }
        if (op[0] == 0xFF) {
            int reg = (modrm >> 3) & 7;
            if (reg == 2 || reg == 3) return "call";
            if (reg == 4 || reg == 5) return "jmp";
            if (reg == 6) return "push";
        }
    } else if (opl == 2) {
        switch (op[1]) {
            case 0x05: return "syscall";
            case 0x07: return "sysret";
            case 0x34: return "sysenter";
            case 0x35: return "sysexit";
            case 0x31: return "rdtsc";
            case 0xA2: return "cpuid";
            case 0x0B: return "ud2";
            case 0x1F: return "nop";
        }
        if (op[1] >= 0x80 && op[1] <= 0x8F) return "jcc";
        if (op[1] >= 0x90 && op[1] <= 0x9F) return "setcc";
        if (op[1] == 0xAF) return "imul";
        if (op[1] == 0xB6 || op[1] == 0xB7) return "movzx";
        if (op[1] == 0xBE || op[1] == 0xBF) return "movsx";
    }
    return NULL;
}

size_t x86_decode(const unsigned char *p, size_t avail, bool bits64, insn *out) {
    init_tables();
    memset(out, 0, sizeof(*out));
    out->imm8 = -1;

    size_t i = 0;
    bool op66 = false, ad67 = false;
    int rex = 0;

    /* Legacy prefixes. */
    int guard = 0;
    while (i < avail && is_prefix(p[i])) {
        if (p[i] == 0x66) op66 = true;
        if (p[i] == 0x67) ad67 = true;
        i++;
        if (++guard > 14) return 0;
    }
    /* REX (64-bit only), immediately before the opcode. */
    if (bits64 && i < avail && (p[i] & 0xF0) == 0x40) {
        rex = p[i];
        out->rex_w = (rex & 0x08) != 0;
        i++;
    }
    if (i >= avail) return 0;

    bool addr16 = (!bits64 && ad67);
    int addrsize = bits64 ? (ad67 ? 4 : 8) : (ad67 ? 2 : 4);

    uint8_t flags;
    unsigned char b0 = p[i];
    out->opcode[0] = b0;

    bool far_ptr = false;
    bool enter = false;

    if (b0 == 0x0F) {
        i++;
        if (i >= avail) return 0;
        unsigned char b1 = p[i];
        out->opcode[1] = b1;
        if (b1 == 0x38) {
            i++; if (i >= avail) return 0;
            out->opcode[2] = p[i]; out->opcode_len = 3; flags = F_MODRM; i++;
        } else if (b1 == 0x3A) {
            i++; if (i >= avail) return 0;
            out->opcode[2] = p[i]; out->opcode_len = 3; flags = F_MODRM|F_IB; i++;
        } else if (b1 == 0x0F) {           /* 3DNow!: modrm then imm8 suffix */
            out->opcode_len = 2; flags = F_MODRM|F_IB; i++;
        } else {
            out->opcode_len = 2; flags = op2[b1]; i++;
        }
    } else {
        out->opcode_len = 1; flags = op1[b0]; i++;
        if (b0 == 0x9A || b0 == 0xEA) { if (bits64) return 0; far_ptr = true; }
        if (b0 == 0xC8) enter = true;
    }

    /* ModRM + SIB + displacement. */
    if (flags & F_MODRM) {
        if (i >= avail) return 0;
        unsigned char modrm = p[i]; i++;
        out->has_modrm = true; out->modrm = modrm;
        int mod = modrm >> 6, rm = modrm & 7;

        /* grp3 F6/F7: immediate present only for reg field 0 or 1 (test). */
        if (out->opcode_len == 1 && (b0 == 0xF6 || b0 == 0xF7)) {
            int reg = (modrm >> 3) & 7;
            if (reg == 0 || reg == 1) flags |= (b0 == 0xF6) ? F_IB : F_IZ;
        }

        if (!addr16) {
            int disp = 0;
            if (mod != 3 && rm == 4) {            /* SIB */
                if (i >= avail) return 0;
                unsigned char sib = p[i]; i++;
                int base = sib & 7;
                if (mod == 0 && base == 5) disp = 4;
                else disp = (mod == 1) ? 1 : (mod == 2) ? 4 : 0;
            } else {
                if (mod == 0 && rm == 5) disp = 4; /* disp32 / RIP-rel */
                else disp = (mod == 1) ? 1 : (mod == 2) ? 4 : 0;
            }
            i += disp;
        } else {                                   /* 16-bit addressing */
            int disp = 0;
            if (mod == 0 && rm == 6) disp = 2;
            else disp = (mod == 1) ? 1 : (mod == 2) ? 2 : 0;
            i += disp;
        }
    }

    /* Immediates. */
    size_t imm = 0;
    unsigned char first_imm_byte = 0;
    bool have_imm = false;
    if (flags & F_IB) { imm += 1; }
    if (flags & F_IW) { imm += 2; }
    if (flags & F_IZ) { imm += op66 ? 2 : 4; }
    if (flags & F_IV) { imm += op66 ? 2 : (out->rex_w ? 8 : 4); }
    if (flags & F_MOFF) { imm += addrsize; }
    if (enter) imm += 3;                            /* iw + ib */
    if (far_ptr) imm += (op66 ? 2 : 4) + 2;

    if (imm > 0) {
        if (i < avail) { first_imm_byte = p[i]; have_imm = true; }
        i += imm;
    }
    (void)have_imm;
    if (b0 == 0xCD && i <= avail) out->imm8 = first_imm_byte; /* INT n */

    if (i > avail) return 0;                        /* truncated */

    out->len = i;
    out->mnemonic = mnemonic_of(out->opcode_len, out->opcode, out->modrm);
    return i;
}

/* ---------------------------------------------------------------- */
/* ELF helpers                                                      */
/* ---------------------------------------------------------------- */

static uint16_t r16(const unsigned char *p) { return (uint16_t)(p[0] | p[1]<<8); }
static uint32_t r32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static uint64_t r64(const unsigned char *p) {
    return (uint64_t)r32(p) | ((uint64_t)r32(p+4) << 32);
}

int detect_bits(const blob *b) {
    if (b->len >= 5 && memcmp(b->data, "\x7f""ELF", 4) == 0)
        return b->data[4] == 2 ? 64 : 32;
    if (b->len >= 0x40 && b->data[0]=='M' && b->data[1]=='Z') {
        uint32_t peoff = r32(b->data + 0x3c);
        if (peoff + 6 <= b->len && memcmp(b->data + peoff, "PE\0\0", 4) == 0) {
            uint16_t mach = r16(b->data + peoff + 4);
            return (mach == 0x8664 || mach == 0xAA64) ? 64 : 32;
        }
    }
    return 64; /* default */
}

bool elf_text_range(const blob *b, size_t *start, size_t *size, uint64_t *vaddr) {
    if (b->len < 64 || memcmp(b->data, "\x7f""ELF", 4) != 0) return false;
    bool is64 = b->data[4] == 2;
    if (!is64) {  /* 32-bit ELF section walk */
        uint32_t shoff = r32(b->data + 0x20);
        uint16_t shentsize = r16(b->data + 0x2e);
        uint16_t shnum = r16(b->data + 0x30);
        uint16_t shstrndx = r16(b->data + 0x32);
        if (shoff == 0 || (size_t)shoff + (size_t)shnum*shentsize > b->len) return false;
        const unsigned char *sh = b->data + shoff;
        uint32_t stroff = r32(sh + (size_t)shstrndx*shentsize + 0x10);
        for (int i = 0; i < shnum; i++) {
            const unsigned char *e = sh + (size_t)i*shentsize;
            uint32_t name = r32(e), addr = r32(e+0x0c), off = r32(e+0x10), sz = r32(e+0x14);
            if (stroff + name < b->len &&
                strcmp((const char*)b->data + stroff + name, ".text") == 0) {
                *start = off; *size = sz; if (vaddr) *vaddr = addr; return true;
            }
        }
        return false;
    }
    uint64_t shoff = r64(b->data + 0x28);
    uint16_t shentsize = r16(b->data + 0x3a);
    uint16_t shnum = r16(b->data + 0x3c);
    uint16_t shstrndx = r16(b->data + 0x3e);
    if (shoff == 0 || shoff + (uint64_t)shnum*shentsize > b->len) return false;
    const unsigned char *sh = b->data + shoff;
    uint64_t stroff = r64(sh + (size_t)shstrndx*shentsize + 0x18);
    for (int i = 0; i < shnum; i++) {
        const unsigned char *e = sh + (size_t)i*shentsize;
        uint32_t name = r32(e);
        uint64_t addr = r64(e+0x10), off = r64(e+0x18), sz = r64(e+0x20);
        if (stroff + name < b->len &&
            strcmp((const char*)b->data + stroff + name, ".text") == 0) {
            *start = off; *size = sz; if (vaddr) *vaddr = addr; return true;
        }
    }
    return false;
}

bool *instruction_starts(const blob *b, size_t start, size_t size, bool bits64) {
    bool *marks = calloc(b->len + 1, 1);
    if (!marks) return NULL;
    size_t end = start + size; if (end > b->len) end = b->len;
    size_t i = start;
    while (i < end) {
        insn in;
        size_t l = x86_decode(b->data + i, end - i, bits64, &in);
        if (l == 0) { i++; continue; }   /* resync on bad byte */
        marks[i] = true;
        i += l;
    }
    return marks;
}

void disasm_report(const blob *b, int bits) {
    section("disassembly (linear sweep)");
    bool bits64 = bits == 64;
    size_t start = 0, size = b->len; uint64_t vaddr = 0;
    bool have_text = elf_text_range(b, &start, &size, &vaddr);
    if (have_text)
        printf("  ELF .text: file 0x%zx, vaddr 0x%" PRIx64 ", %zu bytes (%d-bit)\n",
               start, vaddr, size, bits);
    else
        printf("  whole file as %d-bit code (no ELF .text found)\n", bits);

    size_t end = start + size; if (end > b->len) end = b->len;
    size_t i = start; int count = 0; const int LIMIT = 400;
    while (i < end && count < LIMIT) {
        insn in;
        size_t l = x86_decode(b->data + i, end - i, bits64, &in);
        printf("  0x%08zx  ", i);
        size_t shown = l ? l : 1;
        for (size_t k = 0; k < 8; k++) {
            if (k < shown && i + k < end) printf("%02x ", b->data[i+k]);
            else printf("   ");
        }
        if (l == 0) printf(" (bad)\n");
        else {
            printf(" %s", in.mnemonic ? in.mnemonic : "?");
            if (in.opcode[0] == 0xCD && in.imm8 >= 0) printf(" 0x%02x", in.imm8);
            printf("\n");
        }
        i += l ? l : 1;
        count++;
    }
    if (i < end) printf("  ... stopped after %d instructions (0x%zx of 0x%zx)\n",
                        LIMIT, i, end);
}
