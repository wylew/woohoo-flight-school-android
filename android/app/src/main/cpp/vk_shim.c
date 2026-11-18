/* Android: the NDK's libvulkan.so (API 24) exports only Vulkan 1.0 commands. The runtime calls these newer ones directly
 * (dynamic rendering, extended dynamic state, features2); here they are resolved at run time through vkGetInstanceProcAddr
 * on the instance video.c created (vkshim_set_instance). Only used when the device has Vulkan 1.3 (video.c checks). */
#include <vulkan/vulkan.h>

static VkInstance shim_inst;
void vkshim_set_instance(VkInstance inst) { shim_inst = inst; }

VKAPI_ATTR void VKAPI_CALL vkCmdBeginRendering(VkCommandBuffer commandBuffer, const VkRenderingInfo* pRenderingInfo) {
    static PFN_vkCmdBeginRendering p; if (!p) p = (PFN_vkCmdBeginRendering)vkGetInstanceProcAddr(shim_inst, "vkCmdBeginRendering"); p(commandBuffer, pRenderingInfo);
}
VKAPI_ATTR void VKAPI_CALL vkCmdEndRendering(VkCommandBuffer commandBuffer) {
    static PFN_vkCmdEndRendering p; if (!p) p = (PFN_vkCmdEndRendering)vkGetInstanceProcAddr(shim_inst, "vkCmdEndRendering"); p(commandBuffer);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetCullMode(VkCommandBuffer commandBuffer, VkCullModeFlags cullMode) {
    static PFN_vkCmdSetCullMode p; if (!p) p = (PFN_vkCmdSetCullMode)vkGetInstanceProcAddr(shim_inst, "vkCmdSetCullMode"); p(commandBuffer, cullMode);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetDepthCompareOp(VkCommandBuffer commandBuffer, VkCompareOp depthCompareOp) {
    static PFN_vkCmdSetDepthCompareOp p; if (!p) p = (PFN_vkCmdSetDepthCompareOp)vkGetInstanceProcAddr(shim_inst, "vkCmdSetDepthCompareOp"); p(commandBuffer, depthCompareOp);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetDepthTestEnable(VkCommandBuffer commandBuffer, VkBool32 depthTestEnable) {
    static PFN_vkCmdSetDepthTestEnable p; if (!p) p = (PFN_vkCmdSetDepthTestEnable)vkGetInstanceProcAddr(shim_inst, "vkCmdSetDepthTestEnable"); p(commandBuffer, depthTestEnable);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetDepthWriteEnable(VkCommandBuffer commandBuffer, VkBool32 depthWriteEnable) {
    static PFN_vkCmdSetDepthWriteEnable p; if (!p) p = (PFN_vkCmdSetDepthWriteEnable)vkGetInstanceProcAddr(shim_inst, "vkCmdSetDepthWriteEnable"); p(commandBuffer, depthWriteEnable);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetFrontFace(VkCommandBuffer commandBuffer, VkFrontFace frontFace) {
    static PFN_vkCmdSetFrontFace p; if (!p) p = (PFN_vkCmdSetFrontFace)vkGetInstanceProcAddr(shim_inst, "vkCmdSetFrontFace"); p(commandBuffer, frontFace);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetStencilOp(VkCommandBuffer commandBuffer, VkStencilFaceFlags faceMask, VkStencilOp failOp, VkStencilOp passOp, VkStencilOp depthFailOp, VkCompareOp compareOp) {
    static PFN_vkCmdSetStencilOp p; if (!p) p = (PFN_vkCmdSetStencilOp)vkGetInstanceProcAddr(shim_inst, "vkCmdSetStencilOp"); p(commandBuffer, faceMask, failOp, passOp, depthFailOp, compareOp);
}
VKAPI_ATTR void VKAPI_CALL vkCmdSetStencilTestEnable(VkCommandBuffer commandBuffer, VkBool32 stencilTestEnable) {
    static PFN_vkCmdSetStencilTestEnable p; if (!p) p = (PFN_vkCmdSetStencilTestEnable)vkGetInstanceProcAddr(shim_inst, "vkCmdSetStencilTestEnable"); p(commandBuffer, stencilTestEnable);
}
VKAPI_ATTR void VKAPI_CALL vkGetPhysicalDeviceFeatures2(VkPhysicalDevice physicalDevice, VkPhysicalDeviceFeatures2* pFeatures) {
    static PFN_vkGetPhysicalDeviceFeatures2 p; if (!p) p = (PFN_vkGetPhysicalDeviceFeatures2)vkGetInstanceProcAddr(shim_inst, "vkGetPhysicalDeviceFeatures2"); p(physicalDevice, pFeatures);
}
