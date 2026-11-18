/* Android: load the game code that the phone compiled (NativeCompiler -> <files>/game/obj, TinyCC objects) into
 * memory with libtcc, link it against the runtime, and hand its function table to runtime.c (PWR_DYNAMIC_GAME).
 * Nothing of the game is in the APK: the objects come from the player's own dump, translated and compiled on the phone. */
#include "cpu.h"
#include "table.h"
#include "libtcc.h"
#include <dirent.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const FnEntry *g_dyn_fn_table;
extern unsigned g_dyn_fn_count;

/* runtime functions the generated code calls (see the declarations at the top of the generated funcs.h, and arm2c.py HOOKS) */
void rt_trace_fn(CPU *c, uint32_t fn, int ret);
void rt_log_printf(CPU *c);
void gsp_gx_enqueue_hook(CPU *c);
void freelook_pre(CPU *c);
void freelook_post(CPU *c);
void setting_pre(CPU *c);
void setting_post(CPU *c);
uint32_t rt_cas32(uint32_t *p, uint32_t expect, uint32_t v);
uint32_t rt_cas16(uint16_t *p, uint32_t expect, uint32_t v);
uint32_t rt_cas8(uint8_t *p, uint32_t expect, uint32_t v);
uint32_t rt_clz(uint32_t v);
uint32_t rt_bswap32(uint32_t v);
void rt_dmb(void);

static void tcc_err(void *opaque, const char *msg) { (void)opaque; fprintf(stderr, "tcc: %s\n", msg); }

static int cmp_str(const void *a, const void *b) { return strcmp(*(char *const *)a, *(char *const *)b); }

int pwr_game_load(const char *obj_dir) {
    TCCState *s = tcc_new();   /* kept for the life of the process: it owns the loaded code */
    if (!s) return -1;
    tcc_set_error_func(s, NULL, tcc_err);
    const char *tcc_dir = getenv("PWR_TCC_DIR");
    if (tcc_dir && *tcc_dir) tcc_set_lib_path(s, tcc_dir);
    tcc_set_options(s, "-nostdlib");   /* no crt, no libtcc1.a: everything the code needs is added below or in libc */
    tcc_set_output_type(s, TCC_OUTPUT_MEMORY);

    DIR *d = opendir(obj_dir);
    if (!d) { fprintf(stderr, "load: cannot open %s\n", obj_dir); return -1; }
    char *names[512]; int n = 0; struct dirent *e;
    while ((e = readdir(d)) && n < 512) {
        size_t l = strlen(e->d_name);
        if (l > 2 && !strcmp(e->d_name + l - 2, ".o")) names[n++] = strdup(e->d_name);
    }
    closedir(d);
    if (!n) { fprintf(stderr, "load: no objects in %s\n", obj_dir); return -1; }
    qsort(names, (size_t)n, sizeof *names, cmp_str);
    for (int i = 0; i < n; i++) {
        char p[4096]; snprintf(p, sizeof p, "%s/%s", obj_dir, names[i]); free(names[i]);
        if (tcc_add_file(s, p) < 0) { fprintf(stderr, "load: %s rejected\n", p); return -1; }
    }

#define SYM(x) tcc_add_symbol(s, #x, (const void *)&x)
    SYM(g_mem);
    SYM(rt_svc); SYM(rt_call_indirect); SYM(rt_unimpl); SYM(rt_bkpt); SYM(rt_ret_mismatch); SYM(rt_nan);
    SYM(rt_trace_fn); SYM(rt_log_printf); SYM(gsp_gx_enqueue_hook);
    SYM(freelook_pre); SYM(freelook_post); SYM(setting_pre); SYM(setting_post);
    SYM(rt_cas32); SYM(rt_cas16); SYM(rt_cas8); SYM(rt_clz); SYM(rt_bswap32); SYM(rt_dmb);
    SYM(memcpy); SYM(memset); SYM(memmove); SYM(fabsf); SYM(sqrtf); SYM(sqrt); SYM(nearbyint);
#undef SYM

    if (tcc_relocate(s) < 0) { fprintf(stderr, "load: linking the game code failed\n"); return -1; }
    const FnEntry *table = tcc_get_symbol(s, "g_fn_table");
    const unsigned *count = tcc_get_symbol(s, "g_fn_count");
    if (!table || !count) { fprintf(stderr, "load: no function table in the game code\n"); return -1; }
    g_dyn_fn_table = table; g_dyn_fn_count = *count;
    fprintf(stderr, "load: %d objects, %u functions\n", n, g_dyn_fn_count);
    return 0;
}
