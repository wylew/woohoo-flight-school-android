/* Android: the Vulkan 1.3 core commands the renderer calls directly, resolved with vkGetDeviceProcAddr after the device is
   created (android.c, vk_android_load). Included after <vulkan/vulkan.h>; does nothing on other systems. */
#pragma once
#include <vulkan/vulkan.h>
#ifdef __ANDROID__
#define VK_ANDROID_DEVICE_FUNCS(X) \
    X(vkCmdBeginRendering) X(vkCmdEndRendering) X(vkCmdSetCullMode) X(vkCmdSetFrontFace) \
    X(vkCmdSetDepthTestEnable) X(vkCmdSetDepthWriteEnable) X(vkCmdSetDepthCompareOp) \
    X(vkCmdSetStencilTestEnable) X(vkCmdSetStencilOp)
#define X(n) extern PFN_##n pfn_##n;
VK_ANDROID_DEVICE_FUNCS(X)
#undef X
#define vkCmdBeginRendering pfn_vkCmdBeginRendering
#define vkCmdEndRendering pfn_vkCmdEndRendering
#define vkCmdSetCullMode pfn_vkCmdSetCullMode
#define vkCmdSetFrontFace pfn_vkCmdSetFrontFace
#define vkCmdSetDepthTestEnable pfn_vkCmdSetDepthTestEnable
#define vkCmdSetDepthWriteEnable pfn_vkCmdSetDepthWriteEnable
#define vkCmdSetDepthCompareOp pfn_vkCmdSetDepthCompareOp
#define vkCmdSetStencilTestEnable pfn_vkCmdSetStencilTestEnable
#define vkCmdSetStencilOp pfn_vkCmdSetStencilOp
int vk_android_load(VkDevice dev);
#endif
