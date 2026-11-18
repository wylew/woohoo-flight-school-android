# Woohoo! Flight School for Android (beta)

The same port on a phone: one 3DS screen at a time, on-screen controls, and the game built **on the phone** from your own
dump. The APK contains the translator, the runtime, SDL2 and a C compiler (libtcc), but no game code or data.

## Install and play

1. Download `WoohooFlightSchool-android-beta.apk` from the
   [android-beta pre-release](https://github.com/wylew/woohoo-flight-school-android/releases/tag/android-beta) and install
   it (allow installs from your browser or file manager).
2. Copy your decrypted **Pilotwings Resort (USA)** dump (`.3ds`, `.cci`, `.cia` or `.cxi`) to the phone.
3. Open the app, tap **Choose dump and build** and pick the dump. The app checks it, extracts the game files, translates
   the game code to C (`recomp/arm2c.py`, run by an embedded Python) and compiles it with libtcc. That takes a few
   minutes. The dump copy and the generated C are deleted afterwards; about 100 MB of game files stay in the app's storage.
4. Tap **PLAY**.

Needs an arm64 phone with Vulkan and Android 7 or newer. Phones with Vulkan 1.3 get the hardware renderer; older ones fall
back to the slower software renderer.

## Screen and controls

- One screen fills the display. **⇅** swaps between the top screen and the touch screen; when flying starts, the top
  screen comes back by itself. Touch the touch screen directly when it is shown.
- Circle pad bottom left, D-pad above it, A/B/X/Y bottom right, L and R in the top corners, Select and Start at the
  bottom. **◐** hides the controls (tap it again to bring them back). A Bluetooth or USB gamepad works as on the PC.
- Settings (resolution, filter, frame counter, on-screen controls) are on the start screen.
- **Show game log** and **Share game log** on the start screen show or send the game's log (`files/profile/pwr.log`, plus
  `pwr.log.1` from the run before) with the phone model. Please attach it to reports. The build's log is `files/build.log`.

## How it differs from the PC build

| | PC | Android |
|---|---|---|
| Translator | `recomp/arm2c.py` | the same, through Chaquopy |
| C compiler | GCC/Clang, `-O2`, statically linked | libtcc on the phone, objects loaded into memory at start (`app/src/main/cpp/pwr_game_load.c`) |
| `cpu.h` | `recomp/runtime/cpu.h` | `app/src/main/assets/tcc/pwr/cpu.h`: same CPU struct, macros instead of inlines, runtime calls instead of GCC builtins |
| Screens | layouts incl. stacked/side/large | default `single` (new in `video.c`, also on the PC: `--layout=single`) |
| Vertex shaders | translated to SPIR-V with libshaderc | the same: the APK carries libshaderc (`build_shaderc.sh`) |

TinyCC does not optimize, so the game code runs slower than a GCC build; a modern phone should still have room.

## Building the APK

The `android-beta` branch is built by GitHub Actions (`.github/workflows/android-apk.yml`), which attaches the APK to the
pre-release. To build it yourself:

```bash
android/fetch_deps.sh                      # SDL2 2.32.10 and tinycc sources into android/third_party
android/build_shaderc.sh                   # libshaderc for arm64 into app/src/main/jniLibs (needs the NDK)
gradle -p android assembleRelease          # Gradle 9.9 (JDK 17-25); or open android/ in Android Studio
```

Needs the Android SDK with NDK `28.2.13676358`, CMake `3.31.6` and platform 36. Accept their licences yourself first
(`sdkmanager --licenses`). Output: `android/app/build/outputs/apk/release/app-release.apk` (signed with the public beta key `app/beta.keystore`, for sideloading).
