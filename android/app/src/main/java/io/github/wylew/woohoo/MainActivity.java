package io.github.wylew.woohoo;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileWriter;
import java.io.RandomAccessFile;
import java.io.IOException;

/**
 * Setup and launcher: pick your own Pilotwings Resort (USA) dump, build the game on the phone, play.
 * Settings shown here go to the profile's settings.json, which the runtime reads at start (main.c settings_file).
 */
public class MainActivity extends Activity implements BuildTask.Listener {
    private static final int PICK_ROM = 1;
    private Paths paths;
    private TextView status, log;
    private ScrollView logScroll;
    private ProgressBar progress;
    private Button pick, play;
    private CheckBox controls, fps, hires, linear;
    private boolean building;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        paths = new Paths(this);
        int pad = dp(16);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(18, 32, 52));

        TextView title = new TextView(this);
        title.setText("Woohoo! Flight School");
        title.setTextColor(Color.WHITE); title.setTextSize(24); title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);
        TextView sub = new TextView(this);
        sub.setText("Beta. Builds Pilotwings Resort (USA) from your own decrypted dump (.3ds / .cci / .cia / .cxi), on this phone. "
                + "The app contains no game code or data.");
        sub.setTextColor(Color.rgb(170, 190, 215)); sub.setPadding(0, dp(4), 0, dp(12));
        root.addView(sub);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        pick = new Button(this); pick.setText("Choose dump and build");
        pick.setOnClickListener(v -> chooseRom());
        play = new Button(this); play.setText("PLAY");
        play.setOnClickListener(v -> play());
        buttons.addView(pick, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        buttons.addView(play, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        root.addView(buttons);
        LinearLayout logButtons = new LinearLayout(this);
        logButtons.setOrientation(LinearLayout.HORIZONTAL);
        Button showLog = new Button(this); showLog.setText("Show game log");
        showLog.setOnClickListener(v -> showGameLog());
        Button shareLog = new Button(this); shareLog.setText("Share game log");
        shareLog.setOnClickListener(v -> shareGameLog());
        logButtons.addView(showLog, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        logButtons.addView(shareLog, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        root.addView(logButtons);

        SharedPreferences prefs = getSharedPreferences("settings", MODE_PRIVATE);
        controls = check("On-screen controls", prefs.getBoolean("controls", true));
        hires = check("2x 3D resolution (needs a fast GPU)", prefs.getBoolean("hires", false));
        linear = check("Smooth scaling (linear filter)", prefs.getBoolean("linear", true));
        fps = check("Frame counter", prefs.getBoolean("fps", false));
        for (CheckBox c : new CheckBox[] { controls, hires, linear, fps }) root.addView(c);

        status = new TextView(this);
        status.setTextColor(Color.WHITE); status.setPadding(0, dp(12), 0, dp(4));
        root.addView(status);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setVisibility(View.GONE);
        root.addView(progress);

        log = new TextView(this);
        log.setTextColor(Color.rgb(200, 210, 225)); log.setTypeface(Typeface.MONOSPACE); log.setTextSize(11);
        logScroll = new ScrollView(this);
        logScroll.addView(log);
        root.addView(logScroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));

        TextView help = new TextView(this);
        help.setText("In game: the ⇅ button swaps between the top and the touch screen. A gamepad works too.");
        help.setTextColor(Color.rgb(140, 160, 185)); help.setTextSize(12); help.setGravity(Gravity.CENTER);
        root.addView(help);
        setContentView(root);
        refresh();
        devLaunch(getIntent());
    }

    @Override protected void onNewIntent(Intent i) { super.onNewIntent(i); devLaunch(i); }

    /** For testing over USB: adb shell am start -n io.github.wylew.woohoo/.MainActivity --ez play true [--es env "PWR_X=1;PWR_Y=2"]
     *  starts the game straight away, with extra runtime environment variables (PWR_* only). */
    private void devLaunch(Intent in) {
        if (in == null || !in.getBooleanExtra("play", false) || !BuildTask.isBuilt(paths)) return;
        in.removeExtra("play");
        saveSettings();
        Intent i = new Intent(this, GameActivity.class);
        i.putExtra(GameActivity.EXTRA_CONTROLS, controls.isChecked());
        if (in.getStringExtra("env") != null) i.putExtra(GameActivity.EXTRA_ENV, in.getStringExtra("env"));
        startActivity(i);
    }

    private CheckBox check(String label, boolean on) {
        CheckBox c = new CheckBox(this);
        c.setText(label); c.setTextColor(Color.WHITE); c.setChecked(on);
        c.setOnCheckedChangeListener((v, s) -> saveSettings());
        return c;
    }

    private void refresh() {
        boolean built = BuildTask.isBuilt(paths);
        play.setEnabled(built && !building);
        pick.setEnabled(!building);
        pick.setText(built ? "Rebuild from a dump" : "Choose dump and build");
        if (!building) status.setText(built ? "Ready to play." : "Step 1: choose your dump. Building takes a few minutes.");
    }

    private void chooseRom() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        startActivityForResult(i, PICK_ROM);
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != PICK_ROM || res != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        building = true; log.setText("");
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        progress.setVisibility(View.VISIBLE); progress.setIndeterminate(true);
        refresh();
        new Thread(new BuildTask(this, uri, this), "build").start();
    }

    private void play() {
        saveSettings();
        Intent i = new Intent(this, GameActivity.class);
        i.putExtra(GameActivity.EXTRA_CONTROLS, controls.isChecked());
        startActivity(i);
    }

    /** the runtime's flat settings.json (keys as video_option in recomp/runtime/video.c) */
    private void saveSettings() {
        getSharedPreferences("settings", MODE_PRIVATE).edit()
                .putBoolean("controls", controls.isChecked()).putBoolean("hires", hires.isChecked())
                .putBoolean("linear", linear.isChecked()).putBoolean("fps", fps.isChecked()).apply();
        paths.profile.mkdirs();
        try (FileWriter w = new FileWriter(paths.settings)) {
            w.write("{\n  \"fullscreen\": \"borderless\",\n  \"layout\": \"single\",\n  \"auto_gameplay\": \"top\",\n  \"aspect\": \"keep\",\n"
                    + "  \"filter\": \"" + (linear.isChecked() ? "linear" : "nearest") + "\",\n"
                    + "  \"resolution\": " + (hires.isChecked() ? 2 : 1) + ",\n"
                    + "  \"show_fps\": " + fps.isChecked() + ",\n  \"select_layout\": true\n}\n");
        } catch (IOException e) {
            Toast.makeText(this, "cannot save settings: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    /** the end of a text file (the game log grows by a stats line every few seconds) */
    private static String tail(File f, int max) {
        if (!f.exists()) return "";
        try (RandomAccessFile r = new RandomAccessFile(f, "r")) {
            long len = r.length(), from = Math.max(0, len - max);
            byte[] b = new byte[(int) (len - from)];
            r.seek(from); r.readFully(b);
            return (from > 0 ? "[…]\n" : "") + new String(b, java.nio.charset.StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "cannot read " + f + ": " + e.getMessage();
        }
    }

    private String gameLog(int max) {
        File prev = new File(paths.log.getPath() + ".1");
        String cur = tail(paths.log, max);
        if (cur.isEmpty() && !prev.exists()) return "No game log yet: press PLAY first.";
        StringBuilder sb = new StringBuilder();
        sb.append("Device: ").append(android.os.Build.MANUFACTURER).append(' ').append(android.os.Build.MODEL)
          .append(", Android ").append(android.os.Build.VERSION.RELEASE).append(", ").append(android.os.Build.HARDWARE)
          .append(", app ").append(BuildConfig.VERSION_NAME).append(" (").append(BuildConfig.VERSION_CODE).append(")\n\n");
        sb.append("== last run (pwr.log)\n").append(cur);
        if (prev.exists()) sb.append("\n\n== run before (pwr.log.1)\n").append(tail(prev, max / 4));
        return sb.toString();
    }

    private void showGameLog() {
        if (building) return;
        log.setText(gameLog(64 * 1024));
        log.setTextIsSelectable(true);
        status.setText("Game log (newest at the bottom):");
        logScroll.post(() -> logScroll.fullScroll(View.FOCUS_DOWN));
    }

    private void shareGameLog() {
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("text/plain");
        i.putExtra(Intent.EXTRA_SUBJECT, "Woohoo! Flight School game log");
        i.putExtra(Intent.EXTRA_TEXT, gameLog(200 * 1024));
        startActivity(Intent.createChooser(i, "Share game log"));
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density + 0.5f); }

    // ---- BuildTask.Listener (background thread)
    @Override public void onLog(String line) {
        runOnUiThread(() -> { log.append(line + "\n"); logScroll.post(() -> logScroll.fullScroll(View.FOCUS_DOWN)); });
    }
    @Override public void onStage(int stage, int of, String name) {
        runOnUiThread(() -> { status.setText("Step " + stage + " of " + of + ": " + name + "…"); progress.setIndeterminate(true); });
    }
    @Override public void onProgress(int done, int total) {
        runOnUiThread(() -> { progress.setIndeterminate(false); progress.setMax(total); progress.setProgress(done); });
    }
    @Override public void onFinished(boolean ok, String message) {
        runOnUiThread(() -> {
            building = false;
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            progress.setVisibility(View.GONE);
            refresh();
            status.setText(ok ? "Built. " + message + " Press PLAY." : "Build failed: " + message);
            if (ok) saveSettings();
        });
    }
}
