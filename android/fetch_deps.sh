#!/bin/sh
# Fetches the third-party sources the Android build compiles into android/third_party (git-ignored):
#   SDL2    window, input, audio, Vulkan surface; its Java glue (SDLActivity) is part of the app
#   tinycc  libtcc, which compiles the generated game code on the phone
set -e
cd "$(dirname "$0")"
mkdir -p third_party
SDL_VER=2.32.10
TCC_COMMIT=f830a1697e159056b75de40a60464bc43ee670a3   # tinycc mob, 2026-11-13
if [ ! -f third_party/SDL2/CMakeLists.txt ]; then
    curl -fL -o third_party/sdl.tar.gz "https://github.com/libsdl-org/SDL/releases/download/release-$SDL_VER/SDL2-$SDL_VER.tar.gz"
    tar xzf third_party/sdl.tar.gz -C third_party && rm third_party/sdl.tar.gz
    mv "third_party/SDL2-$SDL_VER" third_party/SDL2
fi
if [ ! -f third_party/tinycc/libtcc.c ]; then
    # repo.or.cz is the home of tinycc; GitHub's TinyCC/tinycc mirrors it. A few tries, as either can fail now and then.
    ok=
    for try in 1 2 3; do
        for url in https://repo.or.cz/tinycc.git https://github.com/TinyCC/tinycc.git; do
            rm -rf third_party/tinycc
            if git clone -q "$url" third_party/tinycc && git -C third_party/tinycc checkout -q "$TCC_COMMIT"; then ok=1; break 2; fi
            echo "tinycc: $url failed, retrying"; sleep 5
        done
    done
    [ -n "$ok" ] || { echo "tinycc: could not fetch $TCC_COMMIT"; exit 1; }
fi
echo "third_party ready: SDL2 $SDL_VER, tinycc $(git -C third_party/tinycc rev-parse --short HEAD)"
