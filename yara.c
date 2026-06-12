/*
 * yara.c — a practical subset of the YARA rule language.
 *
 * Supported:
 *   rule NAME { meta: ... strings: ... condition: ... }
 *   text strings:  $a = "abc"   with modifiers nocase, wide, ascii, fullword
 *   hex strings:   $a = { DE AD ?? BE [2-4] EF }   wildcards ?? and jumps [n-m]
 *   condition:     and / or / not / parentheses,
 *                  $a , !$a (via not),
 *                  #a <op> N   (match count),
 *                  all|any|<N> of them,
 *                  all|any|<N> of ($a*) ,
 *                  filesize <op> N   (supports KB/MB suffixes)
 *
 * Not supported (skipped with a note): regex strings (/.../), string offsets
 * ($a at X, $a in (a..b)), uint8/16/32 reads, entrypoint, modules. Rules using
 * those still load; unsupported terms evaluate to false.
 */
#define _POSIX_C_SOURCE 200809L

#include "atn.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

/* ---- hex pattern token program ---- */
typedef enum { HT_BYTE, HT_MASK, HT_JUMP } htype;
typedef struct {
    htype type;
    unsigned char val;   /* HT_BYTE: byte; HT_MASK: value bits under mask */
    unsigned char mask;  /* HT_MASK: which bits are fixed (0xF0/0x0F/0x00) */
    int jmin, jmax;      /* HT_JUMP: jmax < 0 means unbounded               */
} htok;

typedef struct {
    char id[64];
    int  kind;           /* 0 = text, 1 = hex */
    unsigned char *bytes; size_t blen;     /* text */
    bool nocase, wide;
    htok *prog; size_t nprog;              /* hex */
    uint64_t count; size_t first; bool matched;
} ystr;

typedef struct {
    char name[128];
    ystr strings[64]; int nstr;
    char cond[2048];
} yrule;

/* ---------------------------------------------------------------- */
/* Parsing                                                          */
/* ---------------------------------------------------------------- */

static int hexv(int c){
    if(c>='0'&&c<='9')return c-'0';
    if(c>='a'&&c<='f')return c-'a'+10;
    if(c>='A'&&c<='F')return c-'A'+10;
    return -1;
}

/* Compile a hex body like "DE AD ?? BE [2-4] EF" into a token program. */
static bool compile_hex(const char *s, ystr *out) {
    htok *prog = NULL; size_t cap = 0, n = 0;
    while (*s) {
        if (isspace((unsigned char)*s)) { s++; continue; }
        if (n + 1 >= cap) { cap = cap ? cap*2 : 16; prog = realloc(prog, cap*sizeof(htok)); }
        if (*s == '[') {                       /* jump [n], [n-m], [n-] */
            s++; int lo = 0, hi = 0; bool havehi = false;
            while (isdigit((unsigned char)*s)) lo = lo*10 + (*s++ - '0');
            if (*s == '-') { s++; if (isdigit((unsigned char)*s)) { hi = 0; havehi = true;
                while (isdigit((unsigned char)*s)) hi = hi*10 + (*s++ - '0'); } else { hi = -1; havehi = true; } }
            else hi = lo, havehi = true;
            if (*s == ']') s++;
            prog[n].type = HT_JUMP; prog[n].jmin = lo; prog[n].jmax = havehi ? hi : lo; n++;
            continue;
        }
        int c1 = *s, c2 = *(s+1);
        if (c2 == 0) { free(prog); return false; }
        bool w1 = (c1=='?'), w2 = (c2=='?');
        s += 2;
        if (w1 && w2) { prog[n].type=HT_MASK; prog[n].val=0; prog[n].mask=0x00; n++; }
        else if (!w1 && !w2) { int hi=hexv(c1),lo=hexv(c2); if(hi<0||lo<0){free(prog);return false;}
            prog[n].type=HT_BYTE; prog[n].val=(unsigned char)(hi*16+lo); n++; }
        else if (w1) { int lo=hexv(c2); if(lo<0){free(prog);return false;}
            prog[n].type=HT_MASK; prog[n].val=(unsigned char)lo; prog[n].mask=0x0F; n++; }
        else { int hi=hexv(c1); if(hi<0){free(prog);return false;}
            prog[n].type=HT_MASK; prog[n].val=(unsigned char)(hi<<4); prog[n].mask=0xF0; n++; }
    }
    out->prog = prog; out->nprog = n; out->kind = 1;
    return n > 0;
}

/* Recursive hex matcher: does prog[idx..] match data at pos? */
static bool hmatch(const htok *prog, size_t np, size_t idx,
                   const unsigned char *d, size_t pos, size_t end) {
    for (; idx < np; idx++) {
        const htok *t = &prog[idx];
        if (t->type == HT_BYTE) {
            if (pos >= end || d[pos] != t->val) return false;
            pos++;
        } else if (t->type == HT_MASK) {
            if (pos >= end || (d[pos] & t->mask) != (t->val & t->mask)) return false;
            pos++;
        } else { /* JUMP */
            int lo = t->jmin, hi = t->jmax;
            for (int k = lo; hi < 0 ? (pos + (size_t)k <= end) : (k <= hi); k++) {
                if (pos + (size_t)k > end) break;
                if (hmatch(prog, np, idx+1, d, pos + (size_t)k, end)) return true;
            }
            return false;
        }
    }
    return true;
}

static char *slurp(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb"); if (!f) return NULL;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    if (n < 0) { fclose(f); return NULL; }
    char *buf = malloc((size_t)n + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t got = fread(buf, 1, (size_t)n, f); fclose(f);
    buf[got] = 0; *len = got; return buf;
}

/* Extremely small tokenizing parser, sufficient for the supported subset. */
static const char *skip_ws(const char *p){ while(*p && isspace((unsigned char)*p))p++; return p; }

static int parse_rules(char *text, yrule **out) {
    yrule *rules = NULL; int nr = 0, cap = 0;
    char *p = text;
    while ((p = strstr(p, "rule"))) {
        /* ensure token boundary */
        if (p != text && (isalnum((unsigned char)p[-1]) || p[-1]=='_')) { p += 4; continue; }
        const char *q = p + 4;
        if (!isspace((unsigned char)*q)) { p += 4; continue; }
        q = skip_ws(q);
        if (nr == cap) { cap = cap ? cap*2 : 8; rules = realloc(rules, cap*sizeof(yrule)); }
        yrule *r = &rules[nr]; memset(r, 0, sizeof(*r));
        int ni = 0; while (*q && (isalnum((unsigned char)*q)||*q=='_') && ni < 127) r->name[ni++]=*q++;
        r->name[ni]=0;
        char *brace = strchr(q, '{'); if (!brace) break;
        /* find matching close brace */
        char *body = brace + 1; int depth = 1; char *e = body;
        while (*e && depth) { if(*e=='{')depth++; else if(*e=='}')depth--; if(depth)e++; }
        /* parse strings: section */
        char saved = *e; *e = 0;
        char *strsec = strstr(body, "strings:");
        char *condsec = strstr(body, "condition:");
        if (strsec) {
            char *sp = strsec + 8;
            char *send = condsec ? condsec : e;
            while (sp < send) {
                sp = (char*)skip_ws(sp);
                if (*sp != '$') { if (sp<send) sp++; continue; }
                ystr st; memset(&st, 0, sizeof(st));
                sp++; int idn=0; while ((isalnum((unsigned char)*sp)||*sp=='_') && idn<63) st.id[idn++]=*sp++;
                st.id[idn]=0;
                sp = (char*)skip_ws(sp); if (*sp=='=') sp++; sp=(char*)skip_ws(sp);
                if (*sp == '"') {                  /* text string */
                    sp++; unsigned char buf[1024]; size_t bl=0;
                    while (*sp && *sp!='"' && bl<sizeof(buf)) {
                        if (*sp=='\\' && sp[1]) {
                            sp++; char c=*sp;
                            if (c=='n') buf[bl++]='\n';
                            else if (c=='t') buf[bl++]='\t';
                            else if (c=='r') buf[bl++]='\r';
                            else if (c=='x' && hexv(sp[1])>=0 && hexv(sp[2])>=0) {
                                buf[bl++] = (unsigned char)(hexv(sp[1])*16 + hexv(sp[2])); sp+=2;
                            } else buf[bl++] = (unsigned char)c;
                        } else buf[bl++] = (unsigned char)*sp;
                        sp++;
                    }
                    if (*sp=='"') sp++;
                    st.kind=0; st.bytes=malloc(bl?bl:1); memcpy(st.bytes,buf,bl); st.blen=bl;
                    /* modifiers until newline */
                    char *eol = strpbrk(sp, "\n"); char *ms = sp; char *me = eol?eol:send;
                    char mtmp[128]; size_t ml = (size_t)(me-ms); if(ml>127)ml=127; memcpy(mtmp,ms,ml); mtmp[ml]=0;
                    if (strstr(mtmp,"nocase")) st.nocase=true;
                    if (strstr(mtmp,"wide")) st.wide=true;
                    sp = me;
                } else if (*sp == '{') {           /* hex string */
                    char *hend = strchr(sp,'}'); if(!hend){break;}
                    *hend=0; compile_hex(sp+1,&st); *hend='}'; sp=hend+1;
                } else if (*sp == '/') {           /* regex — unsupported */
                    char *re = strchr(sp+1,'/'); sp = re?re+1:send;
                    st.kind=2; /* mark unsupported */
                } else { sp++; continue; }
                if (r->nstr < 64) r->strings[r->nstr++] = st;
            }
        }
        if (condsec) {
            char *cs = condsec + 10; size_t cl=0;
            while (*cs && cl < sizeof(r->cond)-1) r->cond[cl++]=*cs++;
            r->cond[cl]=0;
        }
        *e = saved;
        nr++;
        p = e + 1;
    }
    *out = rules; return nr;
}

/* ---------------------------------------------------------------- */
/* Matching                                                         */
/* ---------------------------------------------------------------- */

static void match_string(ystr *st, const blob *b) {
    st->count = 0; st->first = 0; st->matched = false;
    if (st->kind == 2) return;                 /* unsupported regex */
    if (st->kind == 1) {                       /* hex */
        for (size_t i = 0; i < b->len; i++) {
            if (hmatch(st->prog, st->nprog, 0, b->data, i, b->len)) {
                if (!st->matched) { st->first = i; st->matched = true; }
                st->count++;
            }
        }
        return;
    }
    /* text (optionally nocase / wide) */
    if (st->blen == 0) return;
    if (!st->wide) {
        for (size_t i = 0; i + st->blen <= b->len; i++) {
            bool ok = true;
            for (size_t j = 0; j < st->blen; j++) {
                unsigned char a = b->data[i+j], c = st->bytes[j];
                if (st->nocase) { a = (unsigned char)tolower(a); c = (unsigned char)tolower(c); }
                if (a != c) { ok = false; break; }
            }
            if (ok) { if(!st->matched){st->first=i;st->matched=true;} st->count++; }
        }
    } else {
        size_t wlen = st->blen * 2;
        for (size_t i = 0; i + wlen <= b->len; i++) {
            bool ok = true;
            for (size_t j = 0; j < st->blen; j++) {
                unsigned char a = b->data[i+2*j], z = b->data[i+2*j+1], c = st->bytes[j];
                if (st->nocase) { a=(unsigned char)tolower(a); c=(unsigned char)tolower(c); }
                if (a != c || z != 0) { ok = false; break; }
            }
            if (ok) { if(!st->matched){st->first=i;st->matched=true;} st->count++; }
        }
    }
}

/* ---- condition evaluation: tiny recursive-descent over tokens ---- */
typedef struct { yrule *r; const blob *b; const char *p; } cstate;

static ystr *find_str(yrule *r, const char *id, size_t idlen) {
    for (int i = 0; i < r->nstr; i++)
        if (strlen(r->strings[i].id)==idlen && strncmp(r->strings[i].id,id,idlen)==0)
            return &r->strings[i];
    return NULL;
}

static long long read_num(const char **p) {
    const char *s = skip_ws(*p); long long v = 0;
    while (isdigit((unsigned char)*s)) v = v*10 + (*s++ - '0');
    if (*s=='K'||*s=='k'){v*=1024;s++;} else if(*s=='M'||*s=='m'){v*=1024*1024;s++;}
    *p = s; return v;
}

static bool cmp_apply(long long a, const char *op, long long b) {
    if (!strncmp(op,"==",2)) return a==b;
    if (!strncmp(op,"!=",2)) return a!=b;
    if (!strncmp(op,">=",2)) return a>=b;
    if (!strncmp(op,"<=",2)) return a<=b;
    if (op[0]=='>') return a>b;
    if (op[0]=='<') return a<b;
    return false;
}

static bool eval_or(cstate *c);

/* count matched strings in "them" or a ($a*) set */
static int count_set(cstate *c, int *total) {
    const char *p = skip_ws(c->p);
    int matched = 0, tot = 0;
    if (!strncmp(p,"them",4)) {
        c->p = p+4;
        for (int i=0;i<c->r->nstr;i++){ tot++; if(c->r->strings[i].matched)matched++; }
    } else if (*p=='(') {
        c->p = p+1;
        for (;;) {
            const char *q = skip_ws(c->p);
            if (*q=='$') {
                q++; const char *id=q; while(isalnum((unsigned char)*q)||*q=='_')q++;
                size_t idl=(size_t)(q-id); bool wild=false;
                if(*q=='*'){wild=true;q++;}
                for (int i=0;i<c->r->nstr;i++){
                    bool hit = wild ? strncmp(c->r->strings[i].id,id,idl)==0
                                    : (strlen(c->r->strings[i].id)==idl && strncmp(c->r->strings[i].id,id,idl)==0);
                    if(hit){tot++; if(c->r->strings[i].matched)matched++;}
                }
            }
            q = skip_ws(q);
            if (*q==',') { c->p=q+1; continue; }
            if (*q==')') { c->p=q+1; break; }
            c->p=q; break;
        }
    }
    *total = tot; return matched;
}

static bool eval_primary(cstate *c) {
    const char *p = skip_ws(c->p);
    if (*p=='(') { c->p=p+1; bool v=eval_or(c); c->p=skip_ws(c->p); if(*c->p==')')c->p++; return v; }
    if (!strncmp(p,"not",3) && !isalnum((unsigned char)p[3])) { c->p=p+3; return !eval_primary(c); }

    /* quantifier of <set> */
    int quant = -1; const char *after = p;
    if (!strncmp(p,"all",3) && !isalnum((unsigned char)p[3])) { quant=-2; after=p+3; }
    else if (!strncmp(p,"any",3) && !isalnum((unsigned char)p[3])) { quant=-3; after=p+3; }
    else if (isdigit((unsigned char)*p)) { const char *t=p; long long v=read_num(&t);
        const char *u=skip_ws(t); if(!strncmp(u,"of",2)){quant=(int)v; after=t;} }
    if (quant != -1) {
        const char *u = skip_ws(after);
        if (!strncmp(u,"of",2)) {
            c->p = skip_ws(u+2); int total=0; int m=count_set(c,&total);
            if (quant==-2) return total>0 && m==total;
            if (quant==-3) return m>=1;
            return m>=quant;
        }
    }

    if (*p=='#') {                       /* #id <op> N */
        p++; const char *id=p; while(isalnum((unsigned char)*p)||*p=='_')p++;
        size_t idl=(size_t)(p-id); ystr *s=find_str(c->r,id,idl);
        p=skip_ws(p); char op[3]={p[0],p[1],0}; const char *aop=p;
        if(p[0]=='>'||p[0]=='<'||p[0]=='='||p[0]=='!') p += (p[1]=='=')?2:1;
        long long n=read_num(&p); c->p=p;
        return s ? cmp_apply((long long)s->count, aop, n) : false;
        (void)op;
    }
    if (!strncmp(p,"filesize",8)) {
        p=skip_ws(p+8); const char *aop=p;
        if(p[0]=='>'||p[0]=='<'||p[0]=='='||p[0]=='!') p += (p[1]=='=')?2:1;
        long long n=read_num(&p); c->p=p;
        return cmp_apply((long long)c->b->len, aop, n);
    }
    if (*p=='$') {                       /* bare $id present? */
        p++; const char *id=p; while(isalnum((unsigned char)*p)||*p=='_')p++;
        size_t idl=(size_t)(p-id); c->p=p;
        if (idl==0) {                    /* "$" alone or "$*" -> any string */
            for(int i=0;i<c->r->nstr;i++) if(c->r->strings[i].matched) return true;
            return false;
        }
        ystr *s=find_str(c->r,id,idl);
        return s ? s->matched : false;
    }
    /* unknown term: consume a token, treat as false */
    while (*c->p && !isspace((unsigned char)*c->p) && *c->p!=')' ) c->p++;
    return false;
}

static bool eval_and(cstate *c) {
    bool v = eval_primary(c);
    for (;;) { const char *p=skip_ws(c->p);
        if(!strncmp(p,"and",3) && !isalnum((unsigned char)p[3])){ c->p=p+3; bool r=eval_primary(c); v=v&&r; }
        else break; }
    return v;
}
static bool eval_or(cstate *c) {
    bool v = eval_and(c);
    for (;;) { const char *p=skip_ws(c->p);
        if(!strncmp(p,"or",2) && !isalnum((unsigned char)p[2])){ c->p=p+2; bool r=eval_and(c); v=v||r; }
        else break; }
    return v;
}

void yara_scan(const blob *b, const char *rulefile) {
    section("yara");
    if (!rulefile) { printf("  (no rule file; pass --yara FILE)\n"); return; }
    size_t tlen; char *text = slurp(rulefile, &tlen);
    if (!text) { printf("  could not read rules: %s\n", rulefile); return; }

    yrule *rules = NULL; int nr = parse_rules(text, &rules);
    if (nr == 0) { printf("  no rules parsed from %s\n", rulefile); free(text); return; }

    int fired = 0;
    for (int i = 0; i < nr; i++) {
        yrule *r = &rules[i];
        bool any_regex = false;
        for (int j = 0; j < r->nstr; j++) {
            match_string(&r->strings[j], b);
            if (r->strings[j].kind == 2) any_regex = true;
        }
        cstate c = { r, b, r->cond };
        bool hit = r->nstr ? eval_or(&c) : false;
        if (hit) {
            fired++;
            printf("  \033[1mMATCH\033[0m  %s\n", r->name);
            for (int j = 0; j < r->nstr; j++) if (r->strings[j].matched)
                printf("           $%s x%" PRIu64 "  first @ 0x%zx\n",
                       r->strings[j].id, r->strings[j].count, r->strings[j].first);
        }
        if (any_regex)
            printf("           (note: rule '%s' has regex strings, not evaluated)\n", r->name);
        /* free */
        for (int j = 0; j < r->nstr; j++) { free(r->strings[j].bytes); free(r->strings[j].prog); }
    }
    printf("  %d rule(s) checked, %d matched\n", nr, fired);
    free(rules); free(text);
}
