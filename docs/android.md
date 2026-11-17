# Android (experimental)

Builds an APK of Woohoo! Flight School from your own dump, for your own phone. The phone runs the same recompiled code as
the PC build, compiled for arm64 with the Android NDK, with the same Vulkan renderer.

> **Status:** first pass, not yet tested on a phone. Expect to send `pwr.log` back and forth for the first runs.
> The APK contains code translated from your dump and the game's files. Don't share it.

## Build on Bazzite (one click)

```bash
git clone https://github.com/wylew/woohoo-flight-school-android
cd woohoo-flight-school-android
./android-builder.sh --install     # adds "Woohoo! Flight School (Android builder)" to the app menu and opens it
```

After that, start it from the app menu. What happens:

1. **First run only:** a distrobox container `wfs-android` (Fedora 41) is created with Python/Tk, a JDK, CMake, Ninja and
   git. Bazzite's system stays untouched. A terminal window shows the progress and later the build log.
2. The builder window opens. **Pick your dump**: it is checked right away (title, encryption, code hash).
3. **Build APK.** The first build downloads the Android SDK and NDK into `~/.local/share/pwr-android/sdk` (about 2.5 GB)
   and, with "Faster vertex shaders" ticked, compiles a shader compiler for the phone (10–20 minutes, once). Later builds
   take a few minutes.
4. **Install.** Turn on *Developer options → USB debugging* on the phone and plug it in (or use *Pair over Wi-Fi*), then
   **Install APK**. Or copy `~/.local/share/pwr-android/out/WoohooFlightSchool.apk` to the phone any way you like and open it.

Every build is signed with the same personal key (`~/.local/share/pwr-android/personal.keystore`), so a new APK installs
over the old one and keeps your saves.

Without the window: `python3 tools/android/build_apk.py build "My Dump.cia"`, then `python3 tools/android/build_apk.py install`
(inside the container: `distrobox enter wfs-android`). Any Linux with a JDK 17+, CMake, Ninja, git and Python works too.

## What the phone needs

- Android 10 or newer, arm64.
- Vulkan 1.3 with dynamic rendering and push descriptors: most Snapdragon 8-series / Tensor / recent Dimensity phones
  from about 2021 on. Without it the game falls back to the software renderer, which will be too slow.
- A gamepad (Bluetooth or USB) for flying. Touch works on the bottom screen (menus, the sign-up signature).
  There are no on-screen buttons yet.

## Playing

| | |
|---|---|
| Back button | settings overlay (layouts, filters, 3D resolution...; change with the gamepad's D-pad, close with Back or B) |
| Gamepad Back/Select | next screen layout (or 3DS Select, set in the overlay) |
| Touch | the bottom screen, wherever the layout puts it |

Defaults for a phone: the *large* layout (big top screen, small bottom screen), sharp bilinear scaling, 1x 3D
resolution, frame counter on. Settings and saves live in the app's private storage; uninstalling deletes them.

**The log:** `Android/data/io.github.wylew.woohoo/files/pwr.log` on the phone (the run before is `pwr.log.1`). The
builder's **Get phone log** button pulls it over adb into the `out` folder; `adb logcat -s pwr` shows it live.

## How it fits together

| Piece | Where |
|---|---|
| Runtime changes | `recomp/runtime/android.c` (logging to logcat + `pwr.log`, game files copied from the APK's assets into internal storage on first start, paths, SDL hints), `vk_android.h` (Vulkan 1.3 commands resolved at run time), `video.c` (compositor rotation, surface lost and rebuilt when the app goes to the background, Back button), `main.c` (SDL_main entry) |
| Build | `recomp/CMakeLists.txt` `if(ANDROID)`: `libmain.so`, 16 KB page aligned, game code compiled with `-ffp-contract=off` (no fused multiply-add, as on the 3DS) |
| APK | `tools/android/build_apk.py`: SDL 2.32.10 for Android, optional libshaderc from the NDK's sources, javac + d8 for SDL's Java classes, aapt2, zipalign, apksigner. No Gradle. |
| One click | `android-builder.sh` (distrobox + app-menu entry), `launcher/android_launcher.py` (the window) |

## Known gaps / next steps

- On-screen touch controls (circle pad, A/B/X/Y, L/R).
- First-start copy of the game's files (a few hundred MB) shows a black screen for a few seconds.
- Performance on phone GPUs is unknown: the renderer copies render targets back to guest memory after every command
  list, which tile-based mobile GPUs dislike. Start at 1x 3D resolution.
- Phase 2: a shareable APK with no game code in it, which asks for the dump and builds the game on the phone.
