package io.github.wylew.woohoo;

/** libpwrcc: libtcc compiling the generated C on the phone (cpp/pwr_compile.c). */
final class NativeCompiler {
    static { System.loadLibrary("pwrcc"); }

    private NativeCompiler() {}

    /** Compiles one C file into an AArch64 object. Returns null on success, else the compiler's messages. */
    static native String compileFile(String tccDir, String src, String out);
}
