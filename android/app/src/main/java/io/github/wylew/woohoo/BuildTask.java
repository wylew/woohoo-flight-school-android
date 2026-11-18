package io.github.wylew.woohoo;

import android.content.Context;
import android.content.res.AssetManager;
import android.net.Uri;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.util.Arrays;
import java.util.Properties;

/**
 * The on-phone build, the same stages as tools/pipeline.py build:
 *   1 copy   the chosen dump into the app's cache (Python reads files, not content:// URIs)
 *   2 verify container, title, encryption, code hash (tools/pipeline.py verify)
 *   3 extract code.bin, exheader.bin, romfs.bin (tools/cia.py)
 *   4 recompile  recomp/arm2c.py -> generated C
 *   5 compile    libtcc -> AArch64 objects, loaded by the game at start
 * Then the dump copy and the generated C are deleted. Runs on a background thread.
 */
final class BuildTask implements Runnable {
    interface Listener {
        void onLog(String line);
        void onStage(int stage, int of, String name);
        void onProgress(int done, int total);
        void onFinished(boolean ok, String message);
    }

    /** Chaquopy calls log(String) on this from Python. */
    public static final class PyLogger {
        private final Listener l;
        PyLogger(Listener l) { this.l = l; }
        public void log(String s) { l.onLog(s); }
    }

    static final int STAGES = 5;
    private final Context ctx;
    private final Uri rom;
    private final Listener l;
    private final Paths p;

    BuildTask(Context ctx, Uri rom, Listener l) {
        this.ctx = ctx.getApplicationContext(); this.rom = rom; this.l = l; this.p = new Paths(ctx);
    }

    @Override public void run() {
        long t0 = System.currentTimeMillis();
        File romCopy = new File(ctx.getCacheDir(), "rom.bin");
        try (PrintWriter buildLog = new PrintWriter(p.buildLog)) {
            Listener log = tee(buildLog);
            log.onStage(1, STAGES, "Copying the dump");
            copyUri(rom, romCopy);
            log.onLog(String.format("copied %.0f MB", romCopy.length() / 1e6));

            if (!Python.isStarted()) Python.start(new AndroidPlatform(ctx));
            PyObject py = Python.getInstance().getModule("pwr_android");
            PyLogger pyLog = new PyLogger(log);

            log.onStage(2, STAGES, "Checking the dump");
            String problems = py.callAttr("verify", romCopy.getAbsolutePath(), pyLog).toString();
            if (!problems.isEmpty()) throw new BuildError(problems);
            String sha = py.callAttr("code_sha256", romCopy.getAbsolutePath()).toString();

            log.onStage(3, STAGES, "Extracting the game files");
            deleteTree(p.extracted);
            py.callAttr("extract", romCopy.getAbsolutePath(), p.extracted.getAbsolutePath(), pyLog);
            romCopy.delete();

            log.onStage(4, STAGES, "Translating the game code to C");
            copyAsset("extra_seeds.txt", p.seeds);
            deleteTree(p.gen);
            py.callAttr("recompile", p.extracted.getAbsolutePath(), p.gen.getAbsolutePath(), p.seeds.getAbsolutePath(), pyLog);

            log.onStage(5, STAGES, "Compiling the game code");
            deleteTree(p.tcc);
            copyAssetTree(ctx.getAssets(), "tcc", p.tcc);
            deleteTree(p.obj);
            if (!p.obj.mkdirs()) throw new IOException("cannot create " + p.obj);
            File[] srcs = p.gen.listFiles((d, n) -> n.endsWith(".c"));
            if (srcs == null || srcs.length == 0) throw new BuildError("the translator produced no C files");
            Arrays.sort(srcs);
            for (int i = 0; i < srcs.length; i++) {
                log.onProgress(i, srcs.length);
                File out = new File(p.obj, srcs[i].getName().replace(".c", ".o"));
                long t = System.currentTimeMillis();
                String err = NativeCompiler.compileFile(p.tcc.getAbsolutePath(), srcs[i].getAbsolutePath(), out.getAbsolutePath());
                if (err != null) throw new BuildError(srcs[i].getName() + ": " + err);
                log.onLog(String.format("%s: %.1f s", srcs[i].getName(), (System.currentTimeMillis() - t) / 1000.0));
            }
            log.onProgress(srcs.length, srcs.length);
            deleteTree(p.gen);

            Properties info = new Properties();
            info.setProperty("code_sha256", sha);
            info.setProperty("app_version", String.valueOf(BuildConfig.VERSION_CODE));
            info.setProperty("objects", String.valueOf(srcs.length));
            try (OutputStream o = new FileOutputStream(p.buildInfo)) { info.store(o, "Woohoo! Flight School build"); }
            p.save.mkdirs();
            String msg = String.format("Done in %d s.", (System.currentTimeMillis() - t0) / 1000);
            log.onLog(msg);
            l.onFinished(true, msg);
        } catch (Throwable e) {
            romCopy.delete();
            String msg = e instanceof BuildError ? e.getMessage() : e.toString();
            l.onLog("error: " + msg);
            l.onFinished(false, msg);
        }
    }

    /** the build is usable: objects present and made by this app version (the runtime and the TinyCC cpu.h must match) */
    static boolean isBuilt(Paths p) {
        if (!p.buildInfo.exists() || !new File(p.extracted, "romfs.bin").exists()) return false;
        Properties info = new Properties();
        try (InputStream in = new java.io.FileInputStream(p.buildInfo)) { info.load(in); } catch (IOException e) { return false; }
        return String.valueOf(BuildConfig.VERSION_CODE).equals(info.getProperty("app_version"));
    }

    private Listener tee(PrintWriter w) {
        return new Listener() {
            public void onLog(String line) { w.println(line); w.flush(); l.onLog(line); }
            public void onStage(int s, int of, String name) { onLog("[" + s + "/" + of + "] " + name); l.onStage(s, of, name); }
            public void onProgress(int d, int t) { l.onProgress(d, t); }
            public void onFinished(boolean ok, String m) { l.onFinished(ok, m); }
        };
    }

    private void copyUri(Uri uri, File dst) throws IOException {
        try (InputStream in = ctx.getContentResolver().openInputStream(uri); OutputStream out = new FileOutputStream(dst)) {
            if (in == null) throw new IOException("cannot open the chosen file");
            byte[] buf = new byte[1 << 20]; int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
    }

    private void copyAsset(String name, File dst) throws IOException {
        dst.getParentFile().mkdirs();
        try (InputStream in = ctx.getAssets().open(name); OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[65536]; int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
    }

    private void copyAssetTree(AssetManager am, String path, File dst) throws IOException {
        String[] kids = am.list(path);
        if (kids == null || kids.length == 0) { copyAsset(path, dst); return; }
        dst.mkdirs();
        for (String k : kids) copyAssetTree(am, path + "/" + k, new File(dst, k));
    }

    static void deleteTree(File f) {
        File[] kids = f.listFiles();
        if (kids != null) for (File k : kids) deleteTree(k);
        f.delete();
    }

    static final class BuildError extends Exception {
        BuildError(String m) { super(m); }
    }
}
