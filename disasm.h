/*
 * disasm.h — compact x86 / x86-64 length-decoding disassembler.
 *
 * This is a "length disassembler engine": it walks the standard (non-VEX)
 * x86 instruction encoding and returns the exact byte length of each
 * instruction, plus enough opcode info to name common instructions and to
 * tell whether a given offset is a real instruction boundary.
 *
 * Limitations (documented, by design): VEX/EVEX (AVX) prefixes C4/C5/62 are
 * not decoded and will cause a linear sweep through AVX code to desync.
 */
#ifndef ATN_DISASM_H
#define ATN_DISASM_H

#include "atn.h"

typedef struct {
    size_t len;            /* total instruction length, 0 if invalid/truncated */
    int    opcode_len;     /* 1, 2, or 3                                        */
    unsigned char opcode[3];
    bool   has_modrm;
    unsigned char modrm;
    bool   rex_w;
    int    imm8;           /* value of a trailing imm8 (e.g. INT n), or -1     */
    const char *mnemonic;  /* best-effort; NULL if unknown                     */
} insn;

/* Decode one instruction at p (avail bytes available). Returns length. */
size_t x86_decode(const unsigned char *p, size_t avail, bool bits64, insn *out);

/* True if the file's code is 64-bit (from ELF/PE header; default 64). */
int detect_bits(const blob *b);

/* If this is an ELF, set start/size to the executable section to sweep.
 * Returns true if a code range was found; else caller sweeps the whole file. */
bool elf_text_range(const blob *b, size_t *start, size_t *size, uint64_t *vaddr);

/* -D section: linear disassembly. */
void disasm_report(const blob *b, int bits);

/* Build a boolean array (caller frees) marking instruction-start offsets from
 * a linear sweep of [start,start+size). Returns NULL on allocation failure. */
bool *instruction_starts(const blob *b, size_t start, size_t size, bool bits64);

#endif /* ATN_DISASM_H */
