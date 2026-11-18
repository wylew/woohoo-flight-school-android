/* Names the runtime's threads (Linux and Android) so that the CPU stats in main.c and tools like top can tell them apart. */
#pragma once
#include <pthread.h>
#ifdef __linux__
int pthread_setname_np(pthread_t, const char *);
#define THREAD_NAME(th, name) pthread_setname_np(th, name)
#else
#define THREAD_NAME(th, name) ((void)0)
#endif
