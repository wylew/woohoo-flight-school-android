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
    git clone https://repo.or.cz/tinycc.git third_party/tinycc
    git -C third_party/tinycc checkout -q "$TCC_COMMIT"
fi
echo "third_party ready: SDL2 $SDL_VER, tinycc $(git -C third_party/tinycc rev-parse --short HEAD)"
