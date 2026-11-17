"""Your dump -> an Android APK of Woohoo! Flight School, for your own phone.

usage:
  python3 tools/android/build_apk.py sdk                     download the Android SDK pieces this needs (first run only)
  python3 tools/android/build_apk.py build <rom> [--no-shaderc] [--jobs N]
  python3 tools/android/build_apk.py install [--apk PATH]    adb install to the connected phone
  python3 tools/android/build_apk.py devices
  common: --home DIR   work folder (default $PWR_ANDROID_HOME, else ~/.local/share/pwr-android)

Stages of build (each prints "[n/7] <stage>"):
  1 sdk        Android command-line tools, platform 35, build-tools 35, NDK r27c in <home>/sdk (once, ~2.5 GB)
  2 verify     the same checks as the desktop build (tools/pipeline.py): title, not encrypted, code hash
  3 extract    code.bin, exheader.bin, romfs.bin -> <home>/game/extracted/
  4 recompile  recomp/arm2c.py -> <home>/game/gen/*.c
  5 libraries  SDL2 (release-2.32.10, from GitHub) for arm64 Android; libshaderc from the NDK's sources (optional: the
               game then translates vertex shaders for the GPU instead of interpreting them, which is faster)
  6 compile    recomp/ with the NDK toolchain -> libmain.so (runtime + recompiled game), 16 KB page aligned
  7 package    SDL's Java classes (javac + d8), the manifest and icon (aapt2), the libraries and the game's files as
               uncompressed assets, zipalign, apksigner with a personal key kept in <home>/personal.keystore
               -> <home>/out/WoohooFlightSchool.apk

The APK holds code translated from your dump and the game's files: it is for your own devices only. Don't share it.
No Gradle: the APK is assembled with the SDK's own tools, so nothing else is downloaded at build time.
"""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys, time, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import cia, pipeline  # noqa: E402
from pipeline import PipelineError  # noqa: E402

CMDLINE_TOOLS = 'https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip'
PLATFORM = 'android-35'
BUILD_TOOLS = '35.0.0'
NDK = '27.2.12479018'          # r27c
MIN_SDK, TARGET_SDK = 29, 34   # Android 10+; 34 keeps the classic full-screen window behaviour
SDL_TAG = 'release-2.32.10'
SDL_GIT = 'https://github.com/libsdl-org/SDL'
ABI = 'arm64-v8a'
PACKAGE = 'io.github.wylew.woohoo'
APK_NAME = 'WoohooFlightSchool.apk'


def default_home():
    if os.environ.get('PWR_ANDROID_HOME'): return os.environ['PWR_ANDROID_HOME']
    return os.path.join(os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')), 'pwr-android')


def _run(cmd, log, cwd=None, env=None, input_text=None):
    log('$ ' + ' '.join(f'"{c}"' if ' ' in c else c for c in cmd))
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    if input_text is not None:
        try: p.stdin.write(input_text); p.stdin.close()
        except BrokenPipeError: pass
    last = ''
    for line in p.stdout:
        line = line.rstrip('\n').split('\r')[-1]   # sdkmanager redraws its progress bar with \r
        if line and line != last: log(line); last = line
    if p.wait(): raise PipelineError(f'{os.path.basename(cmd[0])} failed with exit code {p.returncode}')


class Sdk:
    def __init__(self, home):
        self.root = os.path.join(home, 'sdk')
        self.sdkmanager = os.path.join(self.root, 'cmdline-tools', 'latest', 'bin', 'sdkmanager')
        self.ndk = os.path.join(self.root, 'ndk', NDK)
        self.bt = os.path.join(self.root, 'build-tools', BUILD_TOOLS)
        self.android_jar = os.path.join(self.root, 'platforms', PLATFORM, 'android.jar')
        self.adb = os.path.join(self.root, 'platform-tools', 'adb')
        self.toolchain = os.path.join(self.ndk, 'build', 'cmake', 'android.toolchain.cmake')
        self.glslc = os.path.join(self.ndk, 'shader-tools', 'linux-x86_64', 'glslc')

    def ready(self):
        return all(os.path.exists(p) for p in (self.sdkmanager, self.toolchain, self.glslc, self.android_jar, self.adb,
                                               os.path.join(self.bt, 'd8'), os.path.join(self.bt, 'aapt2')))

    def env(self):
        e = dict(os.environ, ANDROID_HOME=self.root, ANDROID_SDK_ROOT=self.root)
        return e


def check(log=print):
    """missing host tools: [(tool, hint)]"""
    need = [('java', 'a JDK 17+ (java-21-openjdk-devel)'), ('javac', 'a JDK 17+ (java-21-openjdk-devel)'),
            ('keytool', 'a JDK 17+'), ('cmake', 'CMake 3.16+'), ('ninja', 'Ninja (ninja-build)'), ('git', 'git'), ('unzip', 'unzip')]
    missing = [(t, h) for t, h in need if not shutil.which(t)]
    for t, h in missing: log(f'missing: {t} - install {h}')
    return missing


def setup_sdk(home, log=print):
    sdk = Sdk(home)
    if sdk.ready():
        log(f'  Android SDK ready in {sdk.root}'); return sdk
    if check(log): raise PipelineError('host tools missing (see above); the Bazzite script sets them up in a distrobox')
    os.makedirs(sdk.root, exist_ok=True)
    if not os.path.exists(sdk.sdkmanager):
        z = os.path.join(sdk.root, 'cmdline-tools.zip')
        log(f'  downloading {CMDLINE_TOOLS}')
        urllib.request.urlretrieve(CMDLINE_TOOLS, z)
        tmp = os.path.join(sdk.root, 'cmdline-tools-tmp'); shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(z) as zf: zf.extractall(tmp)
        dst = os.path.join(sdk.root, 'cmdline-tools', 'latest'); shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(os.path.join(tmp, 'cmdline-tools'), dst); shutil.rmtree(tmp); os.remove(z)
        for f in glob.glob(os.path.join(dst, 'bin', '*')): os.chmod(f, 0o755)
    log('  accepting the Android SDK licences (the same ones Android Studio shows)')
    _run([sdk.sdkmanager, f'--sdk_root={sdk.root}', '--licenses'], log, env=sdk.env(), input_text='y\n' * 50)
    log('  installing platform-tools, platform, build-tools and the NDK (about 2.5 GB, once)')
    _run([sdk.sdkmanager, f'--sdk_root={sdk.root}', 'platform-tools', f'platforms;{PLATFORM}', f'build-tools;{BUILD_TOOLS}', f'ndk;{NDK}'],
         log, env=sdk.env())
    if not sdk.ready(): raise PipelineError('the SDK install finished but some tools are missing')
    return sdk


# ---------------------------------------------------------------- libraries
def build_sdl(home, sdk, jobs, log):
    deps = os.path.join(home, 'deps'); src = os.path.join(deps, 'SDL'); out = os.path.join(deps, 'sdl2-android')
    if os.path.exists(os.path.join(out, 'lib', 'libSDL2.so')) and os.path.exists(os.path.join(out, 'TAG')) and \
            open(os.path.join(out, 'TAG')).read().strip() == SDL_TAG:
        log(f'  SDL2 {SDL_TAG}: built before, kept'); return src, out
    shutil.rmtree(src, ignore_errors=True); shutil.rmtree(out, ignore_errors=True); os.makedirs(deps, exist_ok=True)
    _run(['git', 'clone', '--depth', '1', '--branch', SDL_TAG, SDL_GIT, src], log)
    bd = os.path.join(deps, 'build-sdl')
    shutil.rmtree(bd, ignore_errors=True)
    _run(['cmake', '-S', src, '-B', bd, '-G', 'Ninja', f'-DCMAKE_TOOLCHAIN_FILE={sdk.toolchain}', f'-DANDROID_ABI={ABI}',
          f'-DANDROID_PLATFORM=android-{MIN_SDK}', '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={out}',
          '-DSDL_SHARED=ON', '-DSDL_STATIC=OFF', '-DSDL_TEST=OFF', '-DSDL_TESTS=OFF',   # HIDAPI stays on: SDLActivity calls into it at start-up (the runtime turns its joystick use off)
          '-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384'], log)
    _run(['cmake', '--build', bd, '-j', str(jobs)], log)
    _run(['cmake', '--install', bd], log)
    if not os.path.exists(os.path.join(out, 'lib', 'libSDL2.so')): raise PipelineError('SDL2 built, but no libSDL2.so')
    open(os.path.join(out, 'TAG'), 'w').write(SDL_TAG + '\n')
    return src, out


def build_shaderc(home, sdk, jobs, log):
    """libshaderc_shared.so for the phone, from the NDK's copy of shaderc; None when unavailable (not fatal)"""
    out = os.path.join(home, 'deps', 'shaderc-android', 'libshaderc_shared.so')
    if os.path.exists(out): log('  libshaderc: built before, kept'); return out
    nsrc = os.path.join(sdk.ndk, 'sources', 'third_party', 'shaderc')
    if not os.path.isdir(nsrc):
        log('  libshaderc: this NDK has no shaderc sources; vertex shaders will use the GPU interpreter'); return None
    work = os.path.join(home, 'deps', 'shaderc-src')
    try:
        if not os.path.isdir(work): shutil.copytree(os.path.join(sdk.ndk, 'sources', 'third_party'), work, symlinks=True)
        log('  libshaderc: compiling the NDK\'s shaderc (10-20 minutes, once)')
        _run([os.path.join(sdk.ndk, 'ndk-build'), 'NDK_PROJECT_PATH=.', 'APP_BUILD_SCRIPT=Android.mk', 'APP_STL=c++_static',
              f'APP_ABI={ABI}', f'APP_PLATFORM=android-{MIN_SDK}', 'libshaderc_combined', f'-j{jobs}'],
             log, cwd=os.path.join(work, 'shaderc'))
        libs = [l for l in glob.glob(os.path.join(work, 'shaderc', 'libs', '**', 'libshaderc*.a'), recursive=True) if ABI in l]   # libs/<stl>/<abi>/libshaderc.a
        if not libs: raise PipelineError('no libshaderc archive after ndk-build')
        cxx = os.path.join(sdk.ndk, 'toolchains', 'llvm', 'prebuilt', 'linux-x86_64', 'bin', f'aarch64-linux-android{MIN_SDK}-clang++')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        _run([cxx, '-shared', '-o', out + '.tmp', '-Wl,--whole-archive', libs[0], '-Wl,--no-whole-archive',
              '-static-libstdc++', '-Wl,-z,max-page-size=16384', '-Wl,-soname,libshaderc_shared.so', '-s'], log)
        os.replace(out + '.tmp', out)
        return out
    except (PipelineError, OSError) as e:
        log(f'  libshaderc: skipped ({e}); vertex shaders will use the GPU interpreter'); return None


# ---------------------------------------------------------------- build
def build(rom, home=None, jobs=None, shaderc=True, log=print):
    home = home or default_home(); t0 = time.time(); jobs = jobs or os.cpu_count() or 4
    game = os.path.join(home, 'game'); ex = os.path.join(game, 'extracted'); gen = os.path.join(game, 'gen')
    log('[1/7] sdk'); sdk = setup_sdk(home, log)
    log('[2/7] verify'); v = pipeline.verify(rom, log)
    if not v['ok']: raise PipelineError('the ROM did not pass verification')
    log('[3/7] extract')
    have = os.path.join(ex, 'code.bin')
    if os.path.exists(have) and os.path.exists(os.path.join(ex, 'romfs.bin')) and \
            hashlib.sha256(open(have, 'rb').read()).hexdigest() == v['code_sha256']:
        log(f'  {ex}: already extracted from this title, kept')
    else:
        cia.extract(rom, ex, runtime_only=True, log=lambda m: log('  ' + m))
    log('[4/7] recompile')
    _run([sys.executable, os.path.join(REPO, 'recomp', 'arm2c.py'), os.path.join(ex, 'code.bin'), os.path.join(ex, 'exheader.bin'), gen], log)
    log('[5/7] libraries')
    sdl_src, sdl = build_sdl(home, sdk, jobs, log)
    sc = build_shaderc(home, sdk, jobs, log) if shaderc else None
    log('[6/7] compile')
    bd = os.path.join(game, 'build-android')
    cfg = ['cmake', '-S', os.path.join(REPO, 'recomp'), '-B', bd, f'-DCMAKE_TOOLCHAIN_FILE={sdk.toolchain}',
           f'-DANDROID_ABI={ABI}', f'-DANDROID_PLATFORM=android-{MIN_SDK}', '-DCMAKE_BUILD_TYPE=Release',
           f'-DGEN_DIR={gen}', f'-DSDL2_ANDROID_DIR={sdl}', f'-DGLSLC={sdk.glslc}']
    if not os.path.exists(os.path.join(bd, 'CMakeCache.txt')): cfg += ['-G', 'Ninja']
    _run(cfg, log)
    _run(['cmake', '--build', bd, '-j', str(jobs), '--target', 'main'], log)
    libmain = os.path.join(bd, 'libmain.so')
    if not os.path.exists(libmain): raise PipelineError(f'no libmain.so in {bd}')
    log('[7/7] package')
    apk = package(home, sdk, sdl_src, [os.path.join(sdl, 'lib', 'libSDL2.so'), libmain] + ([sc] if sc else []), ex, log)
    json.dump(dict(title=v['title'], code_sha256=v['code_sha256'], rom=v['rom'], apk=apk, built=time.strftime('%Y-%m-%d %H:%M:%S'),
                   shaderc=bool(sc)), open(os.path.join(home, 'manifest.json'), 'w'), indent=2)
    log(f'done in {time.time() - t0:.0f} s: {apk} ({os.path.getsize(apk) >> 20} MB)')
    log('This APK contains code translated from your dump: install it on your own devices only.')
    return apk


def _keystore(home, log):
    ks = os.path.join(home, 'personal.keystore')
    if not os.path.exists(ks):   # the same key every build, so a new APK installs over the old one and keeps the saves
        _run(['keytool', '-genkeypair', '-keystore', ks, '-alias', 'pwr', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
              '-storepass', 'android', '-keypass', 'android', '-dname', 'CN=Woohoo Flight School personal build'], log)
    return ks


def package(home, sdk, sdl_src, libs, extracted, log):
    work = os.path.join(home, 'apk'); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    out = os.path.join(home, 'out'); os.makedirs(out, exist_ok=True)
    # SDL's Java side (SDLActivity and friends), from the same SDL checkout as libSDL2.so
    java = os.path.join(sdl_src, 'android-project', 'app', 'src', 'main', 'java')
    srcs = sorted(glob.glob(os.path.join(java, '**', '*.java'), recursive=True))
    if not srcs: raise PipelineError(f'no SDL Java sources in {java}')
    classes = os.path.join(work, 'classes'); os.makedirs(classes)
    _run(['javac', '--release', '11', '-nowarn', '-Xlint:none', '-encoding', 'UTF-8', '-classpath', sdk.android_jar, '-d', classes] + srcs, log)
    dex = os.path.join(work, 'dex'); os.makedirs(dex)
    _run([os.path.join(sdk.bt, 'd8'), '--release', '--min-api', str(MIN_SDK), '--lib', sdk.android_jar, '--output', dex]
         + sorted(glob.glob(os.path.join(classes, '**', '*.class'), recursive=True)), log)
    # resources: the launcher icon
    res = os.path.join(work, 'res'); icon_dir = os.path.join(res, 'mipmap-xxxhdpi'); os.makedirs(icon_dir)
    shutil.copy2(os.path.join(REPO, 'launcher', 'assets', 'icon@2x.png'), os.path.join(icon_dir, 'ic_launcher.png'))
    flat = os.path.join(work, 'res.zip')
    _run([os.path.join(sdk.bt, 'aapt2'), 'compile', '--dir', res, '-o', flat], log)
    base = os.path.join(work, 'base.apk')
    _run([os.path.join(sdk.bt, 'aapt2'), 'link', '-o', base, '-I', sdk.android_jar, '--manifest', os.path.join(HERE, 'AndroidManifest.xml'),
          '--min-sdk-version', str(MIN_SDK), '--target-sdk-version', str(TARGET_SDK),
          '--version-code', str(int(time.time()) // 60), '--version-name', time.strftime('%Y.%m.%d'), flat], log)
    # everything else: libraries and the game's files uncompressed (mapped / read in place), dex compressed
    unsigned = os.path.join(work, 'unsigned.apk'); shutil.copy2(base, unsigned)
    with zipfile.ZipFile(unsigned, 'a', allowZip64=True) as z:
        z.write(os.path.join(dex, 'classes.dex'), 'classes.dex', compress_type=zipfile.ZIP_DEFLATED)
        for lib in libs: z.write(lib, f'lib/{ABI}/{os.path.basename(lib)}', compress_type=zipfile.ZIP_STORED)
        for name in ('code.bin', 'exheader.bin', 'romfs.bin'):
            log(f'  adding {name} ({os.path.getsize(os.path.join(extracted, name)) >> 20} MB)')
            z.write(os.path.join(extracted, name), f'assets/{name}', compress_type=zipfile.ZIP_STORED)
        z.write(os.path.join(HERE, 'settings_android.json'), 'assets/settings.json', compress_type=zipfile.ZIP_DEFLATED)
    aligned = os.path.join(work, 'aligned.apk')
    _run([os.path.join(sdk.bt, 'zipalign'), '-f', '-P', '16', '4', unsigned, aligned], log)
    apk = os.path.join(out, APK_NAME)
    _run([os.path.join(sdk.bt, 'apksigner'), 'sign', '--ks', _keystore(home, log), '--ks-key-alias', 'pwr', '--ks-pass', 'pass:android',
          '--key-pass', 'pass:android', '--out', apk, aligned], log)
    for f in (unsigned, aligned, base): os.remove(f)
    return apk


# ---------------------------------------------------------------- phone
def devices(home=None, log=print):
    sdk = Sdk(home or default_home())
    if not os.path.exists(sdk.adb): return []
    r = subprocess.run([sdk.adb, 'devices', '-l'], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines()[1:] if l.strip()]


def adb(home, args, log=print, input_text=None):
    sdk = Sdk(home or default_home())
    if not os.path.exists(sdk.adb): raise PipelineError('adb is not installed yet: build once first (it sets up the SDK)')
    _run([sdk.adb] + args, log, input_text=input_text)


def install(home=None, apk=None, log=print):
    home = home or default_home(); apk = apk or os.path.join(home, 'out', APK_NAME)
    if not os.path.exists(apk): raise PipelineError(f'no APK at {apk}: build first')
    ready = [d for d in devices(home) if ' device ' in d + ' ']
    if not ready: raise PipelineError('no phone connected: plug it in with USB debugging on, or pair it over Wi-Fi')
    if len(ready) > 1: log(f'  several devices connected; installing to the first: {ready[0]}')
    adb(home, ['-s', ready[0].split()[0], 'install', '-r', apk], log)
    log('installed. The first start copies the game\'s files into the app (a few seconds), then boots.')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--home', default=None)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('sdk'); sp.add_parser('devices')
    b = sp.add_parser('build'); b.add_argument('rom'); b.add_argument('--jobs', type=int); b.add_argument('--no-shaderc', action='store_true')
    i = sp.add_parser('install'); i.add_argument('--apk')
    a = ap.parse_args(argv)
    home = a.home or default_home()
    try:
        if a.cmd == 'sdk': setup_sdk(home)
        elif a.cmd == 'devices': print('\n'.join(devices(home)) or 'no devices')
        elif a.cmd == 'build': build(a.rom, home, a.jobs, not a.no_shaderc)
        elif a.cmd == 'install': install(home, a.apk)
    except PipelineError as e:
        print(f'error: {e}', file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
