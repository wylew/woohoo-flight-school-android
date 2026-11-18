/* libpwrcc: compiles the generated C (arm2c.py output, made on the phone from the player's dump) into AArch64 objects
 * with libtcc. Called by BuildTask.java, one file per call so the app can show progress. */
#include <jni.h>
#include <stdio.h>
#include <string.h>
#include "libtcc.h"

typedef struct { char buf[4096]; size_t len; } ErrBuf;

static void on_error(void *opaque, const char *msg) {
    ErrBuf *e = opaque;
    int n = snprintf(e->buf + e->len, sizeof e->buf - e->len, "%s\n", msg);
    if (n > 0) e->len += (size_t)n < sizeof e->buf - e->len ? (size_t)n : sizeof e->buf - e->len - 1;
}

/* tccDir: TinyCC's include/ (tccdefs.h, stddef.h, ...) and pwr/ (the TinyCC cpu.h and table.h) extracted from the APK
   assets. Returns NULL on success, else the compiler's messages. */
JNIEXPORT jstring JNICALL Java_io_github_wylew_woohoo_NativeCompiler_compileFile(JNIEnv *env, jclass cls, jstring jtcc,
                                                                                  jstring jsrc, jstring jout) {
    (void)cls;
    const char *tcc_dir = (*env)->GetStringUTFChars(env, jtcc, NULL);
    const char *src = (*env)->GetStringUTFChars(env, jsrc, NULL);
    const char *out = (*env)->GetStringUTFChars(env, jout, NULL);
    ErrBuf err = { { 0 }, 0 };
    int ok = 0;
    TCCState *s = tcc_new();
    if (s) {
        char inc[4096];
        tcc_set_error_func(s, &err, on_error);
        tcc_set_lib_path(s, tcc_dir);   /* {B}/include = TinyCC's own headers */
        tcc_set_options(s, "-nostdlib -w");
        snprintf(inc, sizeof inc, "%s/pwr", tcc_dir); tcc_add_include_path(s, inc);
        snprintf(inc, sizeof inc, "%s/include", tcc_dir); tcc_add_sysinclude_path(s, inc);
        tcc_set_output_type(s, TCC_OUTPUT_OBJ);
        ok = tcc_add_file(s, src) >= 0 && tcc_output_file(s, out) >= 0;
        tcc_delete(s);
    } else snprintf(err.buf, sizeof err.buf, "tcc_new failed");
    (*env)->ReleaseStringUTFChars(env, jtcc, tcc_dir);
    (*env)->ReleaseStringUTFChars(env, jsrc, src);
    (*env)->ReleaseStringUTFChars(env, jout, out);
    if (ok) return NULL;
    if (!err.len && !err.buf[0]) snprintf(err.buf, sizeof err.buf, "compile failed");
    return (*env)->NewStringUTF(env, err.buf);
}
