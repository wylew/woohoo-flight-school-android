/* JNI for GameActivity's on-screen controls (TouchControls.java) -> the runtime's input (input.c) and screen swap (video.c). */
#include <jni.h>
#include "input.h"

void video_swap_screen(void);

/* pos: input.h's positional buttons, 0=B(south) 1=A(east) 2=Y(west) 3=X(north) 4=L 5=R 6=Select 7=Start 8..11=D-pad U/D/L/R */
JNIEXPORT void JNICALL Java_io_github_wylew_woohoo_GameActivity_nativeButton(JNIEnv *env, jclass cls, jint pos, jboolean down) {
    (void)env; (void)cls; input_pad_button(pos, down);
}

/* circle pad, -32768..32767, y up positive */
JNIEXPORT void JNICALL Java_io_github_wylew_woohoo_GameActivity_nativeStick(JNIEnv *env, jclass cls, jint x, jint y) {
    (void)env; (void)cls; input_pad_stick(x, y);
}

JNIEXPORT void JNICALL Java_io_github_wylew_woohoo_GameActivity_nativeSwapScreen(JNIEnv *env, jclass cls) {
    (void)env; (void)cls; video_swap_screen();
}
