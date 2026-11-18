# Native part of the Android app (arm64-v8a):
#   libSDL2.so   SDL2 from source (android/third_party/SDL2, fetched by android/fetch_deps.sh)
#   libpwrcc.so  libtcc + JNI: compiles the generated C on the phone (setup screen)
#   libmain.so   the runtime (recomp/runtime, PWR_DYNAMIC_GAME) + the loader for the compiled game code; SDLActivity's "main"
# No game code is built here: the APK holds only the translator, runtime and compiler.
cmake_minimum_required(VERSION 3.22)
project(woohoo_android C CXX)   # CXX: SDL2's Android HIDAPI
set(CMAKE_C_STANDARD 11)

get_filename_component(REPO ${CMAKE_CURRENT_SOURCE_DIR}/../../../../.. ABSOLUTE)
set(TP ${REPO}/android/third_party)
set(RT ${REPO}/recomp/runtime)
if(NOT EXISTS ${TP}/SDL2/CMakeLists.txt OR NOT EXISTS ${TP}/tinycc/libtcc.c)
  message(FATAL_ERROR "run android/fetch_deps.sh first (SDL2 and tinycc sources in android/third_party)")
endif()

# ---- SDL2
set(SDL_SHARED ON CACHE BOOL "" FORCE)
set(SDL_STATIC OFF CACHE BOOL "" FORCE)
set(SDL_TEST OFF CACHE BOOL "" FORCE)
add_subdirectory(${TP}/SDL2 SDL2-build)
# the runtime includes <SDL2/SDL.h>: SDL's public headers under an SDL2/ folder
file(GLOB SDL_PUBLIC_HEADERS ${TP}/SDL2/include/*.h)
file(COPY ${SDL_PUBLIC_HEADERS} DESTINATION ${CMAKE_BINARY_DIR}/sdlinc/SDL2)

# ---- libtcc (one translation unit, native AArch64)
add_library(tcc STATIC ${TP}/tinycc/libtcc.c)
target_include_directories(tcc PUBLIC ${TP}/tinycc PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tcc_config)
target_compile_definitions(tcc PRIVATE ONE_SOURCE=1)
target_compile_options(tcc PRIVATE -w -fPIC)
target_link_libraries(tcc PUBLIC dl m)

add_library(pwrcc SHARED pwr_compile.c)
target_link_libraries(pwrcc tcc log)

# ---- shaders (glslc from the NDK)
if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Windows")
  set(NDK_HOST windows-x86_64)
elseif(CMAKE_HOST_SYSTEM_NAME STREQUAL "Darwin")
  set(NDK_HOST darwin-x86_64)
else()
  set(NDK_HOST linux-x86_64)
endif()
find_program(GLSLC glslc HINTS ${ANDROID_NDK}/shader-tools/${NDK_HOST} REQUIRED)
set(SHADER_INCS)
foreach(sh pica.vert pica_vs.vert pica.frag present.vert present.frag fsr_easu.frag fsr_rcas.frag)
  add_custom_command(OUTPUT ${CMAKE_BINARY_DIR}/shaders/${sh}.inc
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/shaders
    COMMAND ${GLSLC} --target-env=vulkan1.3 -O -mfmt=c -o ${CMAKE_BINARY_DIR}/shaders/${sh}.inc ${RT}/shaders/${sh}
    DEPENDS ${RT}/shaders/${sh})
  list(APPEND SHADER_INCS ${CMAKE_BINARY_DIR}/shaders/${sh}.inc)
endforeach()
add_custom_command(OUTPUT ${CMAKE_BINARY_DIR}/shaders/pica_nd.frag.inc
  COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/shaders
  COMMAND ${GLSLC} --target-env=vulkan1.3 -O -DNO_FRAG_DEPTH -mfmt=c -o ${CMAKE_BINARY_DIR}/shaders/pica_nd.frag.inc ${RT}/shaders/pica.frag
  DEPENDS ${RT}/shaders/pica.frag)
list(APPEND SHADER_INCS ${CMAKE_BINARY_DIR}/shaders/pica_nd.frag.inc)

# ---- the runtime: SDLActivity loads libmain.so and calls SDL_main (main.c)
set(RUNTIME_SOURCES main.c kernel.c services.c fs.c gsp.c pica.c video.c dsp.c pica_sw.c input.c pica_vk.c pica_vsgen.c mii.c
    freelook.c drawdist.c runtime.c)
list(TRANSFORM RUNTIME_SOURCES PREPEND ${RT}/)
add_library(main SHARED ${RUNTIME_SOURCES} ${SHADER_INCS} pwr_game_load.c pwr_tcc_helpers.c pwr_jni.c vk_shim.c)
target_compile_definitions(main PRIVATE PWR_DYNAMIC_GAME)
target_include_directories(main PRIVATE ${RT} ${CMAKE_BINARY_DIR}/shaders ${CMAKE_BINARY_DIR}/sdlinc)
target_compile_options(main PRIVATE -O2 -Wno-unused-parameter)
target_link_libraries(main SDL2 tcc vulkan android log m dl)
