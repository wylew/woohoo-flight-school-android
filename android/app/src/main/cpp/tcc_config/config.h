/* TinyCC configuration for libtcc inside the Android app (normally written by tinycc's configure). The target (ARM64) and
 * TCC_IS_NATIVE follow from the NDK compiler. {B} is the lib path the app sets: <files>/tcc, extracted from the APK. */
#define TCC_VERSION "0.9.28rc"
#define CONFIG_TCC_BCHECK 0
#define CONFIG_TCC_BACKTRACE 0
#define CONFIG_TCC_SYSINCLUDEPATHS "{B}/include"
#define CONFIG_TCC_LIBPATHS "{B}"
#define CONFIG_TCC_CRTPREFIX "{B}"
