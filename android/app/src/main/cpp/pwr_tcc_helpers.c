/* Helpers for the generated code compiled by libtcc (assets/tcc/pwr/cpu.h): the GCC builtins TinyCC lacks. */
#include <stdint.h>

uint32_t rt_cas32(uint32_t *p, uint32_t expect, uint32_t v) {
    return __atomic_compare_exchange_n(p, &expect, v, 0, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
}
uint32_t rt_cas16(uint16_t *p, uint32_t expect, uint32_t v) {
    uint16_t e = (uint16_t)expect;
    return __atomic_compare_exchange_n(p, &e, (uint16_t)v, 0, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
}
uint32_t rt_cas8(uint8_t *p, uint32_t expect, uint32_t v) {
    uint8_t e = (uint8_t)expect;
    return __atomic_compare_exchange_n(p, &e, (uint8_t)v, 0, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
}
uint32_t rt_clz(uint32_t v) { return v ? (uint32_t)__builtin_clz(v) : 32; }
uint32_t rt_bswap32(uint32_t v) { return __builtin_bswap32(v); }
void rt_dmb(void) { __atomic_thread_fence(__ATOMIC_SEQ_CST); }
