#!/bin/sh
# Builds libshaderc_shared.so for arm64 Android into app/src/main/jniLibs (git-ignored). The runtime dlopens it
# (recomp/runtime/pica_vsgen.c) to translate the game's PICA vertex shaders to SPIR-V, as on the PC; without it they run
# through a GPU interpreter, which mobile GPUs handle poorly. Needs the NDK (ANDROID_NDK_HOME or $ANDROID_HOME/ndk/<ver>)
# and the SDK's CMake. Pinned to shaderc v2026.4 and the dependency revisions in its DEPS file.
set -e
cd "$(dirname "$0")"
NDK_VER=28.2.13676358
CMAKE_VER=3.31.6
SHADERC_COMMIT=b64fd42c4a2a9d501c47aca5d3571f7673a5e9cc        # v2026.4
GLSLANG_COMMIT=e1b562a8bed273a02f30b59b66a5d499793cede5
SPIRV_TOOLS_COMMIT=ef96ed763b43b59b33b31b362f09a02b729fa1c9
SPIRV_HEADERS_COMMIT=04fd3caa1e8267e4d95c806cad901181728e1006
OUT=app/src/main/jniLibs/arm64-v8a/libshaderc_shared.so
[ -f "$OUT" ] && { echo "shaderc: $OUT already built"; exit 0; }

NDK=${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/$NDK_VER}
CMAKE_DIR=$ANDROID_HOME/cmake/$CMAKE_VER/bin
fetch() {   # fetch <dir> <url> <commit>
    [ -d "$1/.git" ] && return
    git init -q "$1"
    for try in 1 2 3; do git -C "$1" fetch -q --depth 1 "$2" "$3" && break; echo "fetch $2 failed, retrying"; sleep 5; done
    git -C "$1" checkout -q FETCH_HEAD
}
S=third_party/shaderc
fetch $S https://github.com/google/shaderc.git $SHADERC_COMMIT
fetch $S/third_party/glslang https://github.com/KhronosGroup/glslang.git $GLSLANG_COMMIT
fetch $S/third_party/spirv-tools https://github.com/KhronosGroup/SPIRV-Tools.git $SPIRV_TOOLS_COMMIT
fetch $S/third_party/spirv-headers https://github.com/KhronosGroup/SPIRV-Headers.git $SPIRV_HEADERS_COMMIT

"$CMAKE_DIR/cmake" -S $S -B third_party/shaderc-build -G Ninja -DCMAKE_MAKE_PROGRAM="$CMAKE_DIR/ninja" \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 \
    -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release \
    -DSHADERC_SKIP_TESTS=ON -DSHADERC_SKIP_EXAMPLES=ON -DSHADERC_SKIP_EXECUTABLES=ON \
    -DSHADERC_SKIP_COPYRIGHT_CHECK=ON -DSHADERC_ENABLE_WERROR_COMPILE=OFF -DSHADERC_ENABLE_HLSL=OFF \
    -DSPIRV_SKIP_TESTS=ON -DSPIRV_SKIP_EXECUTABLES=ON -DSPIRV_WERROR=OFF -DENABLE_GLSLANG_BINARIES=OFF -DGLSLANG_TESTS=OFF \
    -DENABLE_OPT=ON   # no SHADERC_SKIP_INSTALL: it drops SPIRV-Tools' install rules, which glslang's (always on) need
"$CMAKE_DIR/ninja" -C third_party/shaderc-build shaderc_shared
mkdir -p "$(dirname $OUT)"
SO=$(find third_party/shaderc-build -name 'libshaderc_shared.so*' -type f | head -1)
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" --strip-unneeded -o "$OUT" "$SO"
ls -l "$OUT"
