/* Android glue (built only for Android; SDL2's SDLActivity calls main() through SDL_main on its own thread).
 *
 * android_setup(), first thing in main():
 *  - stdout/stderr go to logcat (tag "pwr") and to <external files>/pwr.log, kept one run back as pwr.log.1 (the same
 *    file the desktop launcher writes; on the phone it is Android/data/<package>/files/pwr.log, readable over USB/adb);
 *  - the game's files (code.bin, exheader.bin, romfs.bin) travel inside the APK as assets and are copied once into the
 *    app's internal storage, where fs.c can fopen/fseek them like on the desktop (again only when the APK's copy changed);
 *  - the working directory becomes the internal storage folder (pipeline cache, vertex shader cache), saves go to
 *    <internal>/save ($PWR_SAVE_DIR) and settings to <internal>/settings.json ($PWR_SETTINGS, written by the F1 overlay,
 *    which the Back button opens); first run: settings for a phone (assets/settings.json from the APK build).
 *
 * vk_android_load(): Vulkan 1.3 core commands through vkGetDeviceProcAddr. The NDK's libvulkan.so only exports them on
 *    newer API levels; resolving them at run time keeps the APK installable from Android 10 (vk_android.h).
 */
#ifdef __ANDROID__
#include "vk_android.h"
#include <SDL2/SDL.h>
#include <android/log.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define X(n) PFN_##n pfn_##n;
VK_ANDROID_DEVICE_FUNCS(X)
#undef X

int vk_android_load(VkDevice dev) {
    int missing = 0;
#define X(n) if (!(pfn_##n = (PFN_##n)vkGetDeviceProcAddr(dev, #n))) { __android_log_print(ANDROID_LOG_ERROR, "pwr", "vulkan: no %s", #n); missing++; }
    VK_ANDROID_DEVICE_FUNCS(X)
#undef X
    return missing ? -1 : 0;
}

/* ---- logging: a pipe in place of fds 1 and 2, drained into logcat and pwr.log */
static int log_pipe[2]; static FILE *log_file;
static void *log_thread(void *arg) {
    (void)arg; char buf[2048]; size_t used = 0;
    for (;;) {
        ssize_t n = read(log_pipe[0], buf + used, sizeof buf - 1 - used);
        if (n <= 0) { if (n < 0 && errno == EINTR) continue; break; }
        used += (size_t)n;
        if (log_file) { fwrite(buf + used - n, 1, (size_t)n, log_file); fflush(log_file); }
        char *start = buf, *nl;   /* logcat wants whole lines */
        while ((nl = memchr(start, '\n', (size_t)(buf + used - start)))) { *nl = 0; __android_log_write(ANDROID_LOG_INFO, "pwr", start); start = nl + 1; }
        used = (size_t)(buf + used - start); memmove(buf, start, used);
        if (used == sizeof buf - 1) { buf[used] = 0; __android_log_write(ANDROID_LOG_INFO, "pwr", buf); used = 0; }
    }
    return NULL;
}

static void log_setup(const char *ext) {
    if (ext) {
        char p[1024], p1[1040]; snprintf(p, sizeof p, "%s/pwr.log", ext); snprintf(p1, sizeof p1, "%s.1", p);
        rename(p, p1); log_file = fopen(p, "w");
    }
    setvbuf(stdout, NULL, _IOLBF, 0); setvbuf(stderr, NULL, _IONBF, 0);
    if (pipe(log_pipe)) return;
    dup2(log_pipe[1], 1); dup2(log_pipe[1], 2);
    pthread_t t; pthread_create(&t, NULL, log_thread, NULL); pthread_detach(t);
}

/* ---- the game's files: asset -> internal storage, when missing or a different size than the APK's copy */
static int copy_asset(const char *name, const char *dir, int always) {
    char dst[1024]; snprintf(dst, sizeof dst, "%s/%s", dir, name);
    SDL_RWops *in = SDL_RWFromFile(name, "rb");   /* on Android, a relative path is read from the APK's assets */
    if (!in) { fprintf(stderr, "android: asset %s missing from the APK\n", name); return -1; }
    Sint64 size = SDL_RWsize(in);
    struct stat st;
    if (!always && !stat(dst, &st) && (Sint64)st.st_size == size) { SDL_RWclose(in); return 0; }
    if (always == 2 && !stat(dst, &st)) { SDL_RWclose(in); return 0; }   /* first-run defaults: never overwrite */
    char tmp[1040]; snprintf(tmp, sizeof tmp, "%s.part", dst);
    FILE *out = fopen(tmp, "wb");
    if (!out) { fprintf(stderr, "android: cannot write %s: %s\n", tmp, strerror(errno)); SDL_RWclose(in); return -1; }
    fprintf(stderr, "android: copying %s (%lld MB) to internal storage\n", name, (long long)(size >> 20));
    static char buf[1 << 20]; size_t n; Sint64 total = 0;
    while ((n = SDL_RWread(in, buf, 1, sizeof buf)) > 0) {
        if (fwrite(buf, 1, n, out) != n) { fprintf(stderr, "android: out of space writing %s\n", dst); fclose(out); remove(tmp); SDL_RWclose(in); return -1; }
        total += (Sint64)n;
    }
    SDL_RWclose(in); fclose(out);
    if (total != size) { fprintf(stderr, "android: short read of %s\n", name); remove(tmp); return -1; }
    return rename(tmp, dst) ? -1 : 0;
}

int android_setup(const char **data_dir) {
    const char *in = SDL_AndroidGetInternalStoragePath(), *ext = SDL_AndroidGetExternalStoragePath();
    log_setup(ext);
    if (!in) { fprintf(stderr, "android: no internal storage path\n"); return -1; }
    fprintf(stderr, "android: internal %s, external %s\n", in, ext ? ext : "(none)");
    static char game[1024], save[1024], settings[1024];
    snprintf(game, sizeof game, "%s/game", in); snprintf(save, sizeof save, "%s/save", in); snprintf(settings, sizeof settings, "%s/settings.json", in);
    mkdir(game, 0700); mkdir(save, 0700);
    if (copy_asset("code.bin", game, 0) || copy_asset("exheader.bin", game, 0) || copy_asset("romfs.bin", game, 0)) return -1;
    copy_asset("settings.json", in, 2);
    if (chdir(in)) fprintf(stderr, "android: chdir %s: %s\n", in, strerror(errno));
    setenv("PWR_SAVE_DIR", save, 1); setenv("PWR_SETTINGS", settings, 1);
    /* the Back button arrives as a key (it opens the settings overlay) instead of closing the activity; Android's own
       controller support instead of HIDAPI, which needs USB/Bluetooth permissions */
    SDL_SetHint(SDL_HINT_ANDROID_TRAP_BACK_BUTTON, "1");
    SDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI, "0");
    SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight");
    *data_dir = game;
    return 0;
}
#endif
