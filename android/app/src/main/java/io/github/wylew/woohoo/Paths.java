package io.github.wylew.woohoo;

import android.content.Context;

import java.io.File;

/** Where the app keeps things, all in its private storage. The game files come from the player's dump and never leave it. */
final class Paths {
    final File game, extracted, gen, obj, tcc, seeds, buildInfo, profile, save, settings, log, buildLog;

    Paths(Context c) {
        File files = c.getFilesDir();
        game = new File(files, "game");
        extracted = new File(game, "extracted");   // code.bin, exheader.bin, romfs.bin
        gen = new File(game, "gen");               // generated C (deleted after compiling)
        obj = new File(game, "obj");               // compiled game code, loaded at start
        buildInfo = new File(game, "build.properties");
        tcc = new File(files, "tcc");              // TinyCC headers + the TinyCC cpu.h (from the APK assets)
        seeds = new File(files, "extra_seeds.txt");
        profile = new File(files, "profile");
        save = new File(profile, "save");
        settings = new File(profile, "settings.json");
        log = new File(profile, "pwr.log");
        buildLog = new File(files, "build.log");
    }
}
