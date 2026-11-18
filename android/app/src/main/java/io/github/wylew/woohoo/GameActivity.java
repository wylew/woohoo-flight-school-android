package io.github.wylew.woohoo;

import android.os.Bundle;
import android.system.ErrnoException;
import android.system.Os;
import android.util.Log;
import android.widget.RelativeLayout;

import org.libsdl.app.SDLActivity;

/** The game: SDL2 runs SDL_main in libmain.so (recomp/runtime/main.c), with the on-screen controls on top. */
public class GameActivity extends SDLActivity {
    static final String EXTRA_CONTROLS = "controls";

    static native void nativeButton(int pos, boolean down);
    static native void nativeStick(int x, int y);
    static native void nativeSwapScreen();

    private Paths paths;

    @Override protected String[] getLibraries() { return new String[] { "SDL2", "main" }; }

    @Override protected String[] getArguments() {
        return new String[] { "--objs=" + paths.obj.getAbsolutePath(), paths.extracted.getAbsolutePath() };
    }

    @Override protected void onCreate(Bundle b) {
        paths = new Paths(this);
        paths.save.mkdirs();
        try {   // read by the runtime (main.c, fs.c) and by SDL (hints fall back to environment variables)
            Os.setenv("PWR_SAVE_DIR", paths.save.getAbsolutePath(), true);
            Os.setenv("PWR_SETTINGS", paths.settings.getAbsolutePath(), true);
            Os.setenv("PWR_LOG", paths.log.getAbsolutePath(), true);
            Os.setenv("PWR_TCC_DIR", paths.tcc.getAbsolutePath(), true);
            Os.setenv("PWR_CWD", paths.profile.getAbsolutePath(), true);
            Os.setenv("SDL_IOS_ORIENTATIONS", "LandscapeLeft LandscapeRight", true);
        } catch (ErrnoException e) {
            Log.e("woohoo", "setenv", e);
        }
        super.onCreate(b);
        if (mLayout != null && getIntent().getBooleanExtra(EXTRA_CONTROLS, true)) {
            mLayout.addView(new TouchControls(this), new RelativeLayout.LayoutParams(
                    RelativeLayout.LayoutParams.MATCH_PARENT, RelativeLayout.LayoutParams.MATCH_PARENT));
        }
    }
}
