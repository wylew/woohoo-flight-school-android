/* Guest CPU model, TinyCC edition (Android): the same interface as recomp/runtime/cpu.h, for the generated code that the
 * phone compiles with libtcc. TinyCC does not inline, has no system headers here and lacks some GCC builtins, so:
 *   - integer types are declared directly (no <stdint.h>);
 *   - the hot accessors (guest memory, VFP registers) are macros on plain pointers (AArch64 allows unaligned access);
 *   - CAS, CLZ and barriers call the runtime (android/app/src/main/cpp/pwr_game_load.c exports them to libtcc).
 * The CPU struct must stay identical to recomp/runtime/cpu.h: the runtime (compiled by clang) shares it. */
#ifndef PWR_CPU_H
#define PWR_CPU_H

typedef unsigned char uint8_t;   typedef signed char int8_t;
typedef unsigned short uint16_t; typedef short int16_t;
typedef unsigned int uint32_t;   typedef int int32_t;
typedef unsigned long long uint64_t; typedef long long int64_t;
typedef unsigned long size_t;
#ifndef NULL
#define NULL ((void *)0)
#endif

typedef struct CPU {
    uint32_t r[16];
    uint32_t n, z, cf, v, q;
    uint32_t ge;
    uint32_t s[32];
    uint32_t fpscr;
    uint32_t tls;
    uint32_t excl_addr, excl_val;
    int excl_valid;
} CPU;

typedef void (*GuestFn)(CPU *c);

extern uint8_t *g_mem;

void rt_svc(CPU *c, uint32_t num, uint32_t pc);
void rt_call_indirect(CPU *c, uint32_t target, uint32_t pc);
void rt_unimpl(CPU *c, uint32_t pc, uint32_t insn);
void rt_bkpt(CPU *c, uint32_t pc);
void rt_ret_mismatch(CPU *c, uint32_t pc, uint32_t got, uint32_t want);
void rt_nan(CPU *c, uint32_t pc);

/* helpers the runtime provides in place of GCC builtins */
uint32_t rt_cas32(uint32_t *p, uint32_t expect, uint32_t v);   /* 1 if *p held expect and now holds v */
uint32_t rt_cas16(uint16_t *p, uint32_t expect, uint32_t v);
uint32_t rt_cas8(uint8_t *p, uint32_t expect, uint32_t v);
uint32_t rt_clz(uint32_t v);                                   /* v != 0 */
uint32_t rt_bswap32(uint32_t v);
void rt_dmb(void);
float fabsf(float); float sqrtf(float); double sqrt(double); double nearbyint(double);
void *memcpy(void *, const void *, size_t);

#undef __builtin_fabsf
#undef __builtin_sqrtf
#undef __builtin_sqrt
#undef __builtin_bswap32
#undef __builtin_clz
#undef __builtin_nearbyint
#undef __sync_synchronize
#define __builtin_fabsf(x) fabsf(x)
#define __builtin_sqrtf(x) sqrtf(x)
#define __builtin_sqrt(x) sqrt(x)
#define __builtin_bswap32(x) rt_bswap32(x)
#define __builtin_clz(x) rt_clz(x)
#define __builtin_nearbyint(x) nearbyint(x)
#define __sync_synchronize() rt_dmb()

/* ---- memory ---- */
#define WATCH(a, v, n) do { } while (0)
#define rd8(a)  ((uint32_t)g_mem[(uint32_t)(a)])
#define rd16(a) ((uint32_t)*(uint16_t *)(g_mem + (uint32_t)(a)))
#define rd32(a) (*(uint32_t *)(g_mem + (uint32_t)(a)))
#define wr8(a, v)  (g_mem[(uint32_t)(a)] = (uint8_t)(v))
#define wr16(a, v) (*(uint16_t *)(g_mem + (uint32_t)(a)) = (uint16_t)(v))
#define wr32(a, v) (*(uint32_t *)(g_mem + (uint32_t)(a)) = (uint32_t)(v))

/* ---- flags / ALU helpers ---- */
static inline void set_nz(CPU *c, uint32_t r) { c->n = r >> 31; c->z = r == 0; }
static inline uint32_t adc_flags(CPU *c, uint32_t a, uint32_t b, uint32_t cin) {
    uint64_t w = (uint64_t)a + b + cin; uint32_t r = (uint32_t)w;
    c->n = r >> 31; c->z = r == 0; c->cf = (uint32_t)(w >> 32); c->v = ((~(a ^ b)) & (a ^ r)) >> 31;
    return r;
}
static inline uint32_t sbc_flags(CPU *c, uint32_t a, uint32_t b, uint32_t cin) {
    uint32_t nb = ~b; uint64_t w = (uint64_t)a + nb + cin; uint32_t r = (uint32_t)w;
    c->n = r >> 31; c->z = r == 0; c->cf = (uint32_t)(w >> 32); c->v = ((~(a ^ nb)) & (a ^ r)) >> 31;
    return r;
}

static inline uint32_t ror32(uint32_t v, uint32_t s) { s &= 31; return s ? (v >> s) | (v << (32 - s)) : v; }

static inline uint32_t lsl_rs(uint32_t v, uint32_t s, uint32_t *co) {
    s &= 0xff; if (!s) return v;
    if (s < 32) { *co = (v >> (32 - s)) & 1; return v << s; }
    *co = s == 32 ? (v & 1) : 0; return 0;
}
static inline uint32_t lsr_rs(uint32_t v, uint32_t s, uint32_t *co) {
    s &= 0xff; if (!s) return v;
    if (s < 32) { *co = (v >> (s - 1)) & 1; return v >> s; }
    *co = s == 32 ? (v >> 31) : 0; return 0;
}
static inline uint32_t asr_rs(uint32_t v, uint32_t s, uint32_t *co) {
    s &= 0xff; if (!s) return v;
    if (s < 32) { *co = ((int32_t)v >> (s - 1)) & 1; return (uint32_t)((int32_t)v >> s); }
    *co = v >> 31; return (uint32_t)((int32_t)v >> 31);
}
static inline uint32_t ror_rs(uint32_t v, uint32_t s, uint32_t *co) {
    s &= 0xff; if (!s) return v;
    s &= 31; if (!s) { *co = v >> 31; return v; }
    uint32_t r = ror32(v, s); *co = r >> 31; return r;
}

static inline uint32_t clz32(uint32_t v) { return v ? rt_clz(v) : 32; }

static inline int32_t sat_s(int64_t v, int bits, CPU *c) {
    int64_t hi = ((int64_t)1 << (bits - 1)) - 1, lo = -((int64_t)1 << (bits - 1));
    if (v > hi) { c->q = 1; return (int32_t)hi; }
    if (v < lo) { c->q = 1; return (int32_t)lo; }
    return (int32_t)v;
}
static inline uint32_t sat_u(int64_t v, int bits, CPU *c) {
    int64_t hi = ((int64_t)1 << bits) - 1;
    if (v > hi) { c->q = 1; return (uint32_t)hi; }
    if (v < 0) { c->q = 1; return 0; }
    return (uint32_t)v;
}

/* ---- exclusive access ---- */
static inline uint32_t ldrex32(CPU *c, uint32_t a) { uint32_t v = rd32(a); c->excl_addr = a; c->excl_val = v; c->excl_valid = 1; return v; }
static inline uint32_t strex32(CPU *c, uint32_t a, uint32_t v) {
    if (!c->excl_valid || c->excl_addr != a) return 1;
    c->excl_valid = 0;
    return rt_cas32((uint32_t *)(g_mem + a), c->excl_val, v) ? 0 : 1;
}
static inline uint32_t ldrexb(CPU *c, uint32_t a) { uint32_t v = rd8(a); c->excl_addr = a; c->excl_val = v; c->excl_valid = 1; return v; }
static inline uint32_t strexb(CPU *c, uint32_t a, uint32_t v) {
    if (!c->excl_valid || c->excl_addr != a) return 1;
    c->excl_valid = 0;
    return rt_cas8(g_mem + a, c->excl_val & 0xff, v) ? 0 : 1;
}
static inline uint32_t ldrexh(CPU *c, uint32_t a) { uint32_t v = rd16(a); c->excl_addr = a; c->excl_val = v; c->excl_valid = 1; return v; }
static inline uint32_t strexh(CPU *c, uint32_t a, uint32_t v) {
    if (!c->excl_valid || c->excl_addr != a) return 1;
    c->excl_valid = 0;
    return rt_cas16((uint16_t *)(g_mem + a), c->excl_val & 0xffff, v) ? 0 : 1;
}

/* ---- VFP ---- */
#define fS(c, i) (*(float *)&(c)->s[(i)])
#define sS(c, i, f) (*(float *)&(c)->s[(i)] = (float)(f))
#define fD(c, i) (*(double *)&(c)->s[2 * (i)])
#define sD(c, i, d) (*(double *)&(c)->s[2 * (i)] = (double)(d))
static inline void vfp_cmp(CPU *c, double a, double b) {
    uint32_t f = (a != a || b != b) ? 0x3u : a == b ? 0x6u : a < b ? 0x8u : 0x2u;
    c->fpscr = (c->fpscr & 0x0fffffffu) | (f << 28);
}
static inline int32_t  vcvt_s32(double x) { if (x != x) return 0; if (x >= 2147483647.0) return 2147483647; if (x <= -2147483648.0) return (-2147483647 - 1); return (int32_t)x; }
static inline uint32_t vcvt_u32(double x) { if (x != x || x <= 0) return 0; if (x >= 4294967295.0) return 4294967295u; return (uint32_t)x; }
static inline int32_t  vcvtr_s32(double x) { return vcvt_s32(nearbyint(x)); }
static inline uint32_t vcvtr_u32(double x) { return vcvt_u32(nearbyint(x)); }

#endif
