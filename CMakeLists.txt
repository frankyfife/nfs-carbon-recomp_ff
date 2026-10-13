# nfscarbon - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(nfscarbon LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Cross-compiling (Android): codegen runs at build time, so it must execute on
# the host. Point the imported rexglue target at a native build.
if(ANDROID AND REXGLUE_HOST_REXGLUE_TOOL)
    set_target_properties(rex::rexglue PROPERTIES
        IMPORTED_LOCATION "${REXGLUE_HOST_REXGLUE_TOOL}"
        IMPORTED_LOCATION_RELEASE "${REXGLUE_HOST_REXGLUE_TOOL}"
    )
endif()

# Sources
set(NFSCARBON_SOURCES
    src/main.cpp
    src/dispatch_tolerance.cpp
    # carbon_60fps (experimental, off): lifts the game's 30 fps frame limiter (docs/60fps.md).
    src/frame_rate_hook.cpp
)

if(WIN32)
    list(APPEND NFSCARBON_SOURCES src/crash_diag.cpp)
endif()

if(ANDROID)
    # JNI bridge for the on-screen touch gamepad overlay.
    list(APPEND NFSCARBON_SOURCES src/touch_bridge.cpp)
    # CPU core pinning watchdog for the command processor and main guest thread.
    list(APPEND NFSCARBON_SOURCES src/thread_affinity.cpp)
    # Futex sleep instead of a busy spin while D3D waits for ring space.
    list(APPEND NFSCARBON_SOURCES src/ring_wait_hook.cpp)
    # Retail render mode 2 (one tile, no MSAA) for the scene: removes the tiling/MSAA redraws.
    list(APPEND NFSCARBON_SOURCES src/render_mode_hook.cpp)
    # Stereo AAudio output instead of the SDL 5.1 stream.
    list(APPEND NFSCARBON_SOURCES src/android_aaudio.cpp)
    # Downloaded Adreno ICD drivers (turnip) through libadrenotools; arm64 only.
    if(ANDROID_ABI STREQUAL "arm64-v8a")
        list(APPEND NFSCARBON_SOURCES src/turnip_driver.cpp)
    endif()
endif()

if(WIN32)
    add_executable(nfscarbon WIN32 ${NFSCARBON_SOURCES})
    target_link_libraries(nfscarbon PRIVATE dbghelp)
elseif(ANDROID)
    # SDLActivity loads the game as a shared library.
    add_library(nfscarbon SHARED ${NFSCARBON_SOURCES})
    target_link_libraries(nfscarbon PRIVATE aaudio)
else()
    add_executable(nfscarbon ${NFSCARBON_SOURCES})
endif()

if(WIN32)
    target_link_options(nfscarbon PRIVATE "LINKER:/force:multiple")
endif()

rexglue_setup_target(nfscarbon GPU_PLUGINS xenos)

# The frame limiter function for carbon_60fps once it is found
# (tools/find_60fps.py; 8 hex digits, e.g. 8236ABCD), else only data patches.
set(NFSCARBON_FPS_LIMITER_FUNC "" CACHE STRING
    "Address of Carbon's SetFPSLimiter(float fps) for the carbon_60fps hook (docs/60fps.md)")
if(NFSCARBON_FPS_LIMITER_FUNC)
    target_compile_definitions(nfscarbon PRIVATE NFSCARBON_FPS_LIMITER_FUNC=${NFSCARBON_FPS_LIMITER_FUNC})
endif()

# Native Direct3D 12 renderer next to the Xenos emulation (--native_renderer),
# ported from NFSMW-Recompiled_ff (GPL-3.0, see src/native and
# docs/native-d3d12-port.md). It compiles the SDK's Xenos shader translator in
# from the SDK source tree (the GPU plugin does not export it); its cvars stay
# local (src/native/sdk_cvars_local.h) so the plugin's own settings keep working.
set(NFSCARBON_SDK_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../reference/rexglue-sdk" CACHE PATH
    "rexglue-sdk source tree, for the native Direct3D 12 renderer")
option(NFSCARBON_NATIVE_D3D12 "Build the native Direct3D 12 renderer (Windows)" ON)
if(WIN32 AND NFSCARBON_NATIVE_D3D12 AND
   EXISTS "${NFSCARBON_SDK_SOURCE_DIR}/src/graphics/pipeline/shader/dxbc_translator.cpp")
    set(SDK_GPU "${NFSCARBON_SDK_SOURCE_DIR}/src/graphics")
    set(NATIVE_SDK_SOURCES
        ${SDK_GPU}/flags.cpp
        ${SDK_GPU}/registers.cpp
        ${SDK_GPU}/register_file.cpp
        ${SDK_GPU}/format/ucode.cpp
        ${SDK_GPU}/util/draw.cpp
        ${SDK_GPU}/pipeline/shader/shader.cpp
        ${SDK_GPU}/pipeline/shader/translator.cpp
        ${SDK_GPU}/pipeline/shader/translator_disasm.cpp
        ${SDK_GPU}/pipeline/shader/dxbc.cpp
        ${SDK_GPU}/pipeline/shader/dxbc_translator.cpp
        ${SDK_GPU}/pipeline/shader/dxbc_translator_alu.cpp
        ${SDK_GPU}/pipeline/shader/dxbc_translator_fetch.cpp
        ${SDK_GPU}/pipeline/shader/dxbc_translator_memexport.cpp
        ${SDK_GPU}/pipeline/shader/dxbc_translator_om.cpp
    )
    target_sources(nfscarbon PRIVATE
        src/native/parallel.cpp
        src/native/renderer.cpp
        src/native/sdk_globals.cpp
        ${NATIVE_SDK_SOURCES}
        ${NFSCARBON_SDK_SOURCE_DIR}/thirdparty/dxbc/DXBCChecksum.cpp
    )
    set_source_files_properties(${NATIVE_SDK_SOURCES} PROPERTIES
        COMPILE_OPTIONS "-include;${CMAKE_CURRENT_SOURCE_DIR}/src/native/sdk_cvars_local.h;-Wno-unused-variable"
        SKIP_PRECOMPILE_HEADERS ON)
    set_source_files_properties(src/native/parallel.cpp src/native/renderer.cpp PROPERTIES
        COMPILE_OPTIONS "-gline-tables-only")
    set_source_files_properties(${NFSCARBON_SDK_SOURCE_DIR}/thirdparty/dxbc/DXBCChecksum.cpp PROPERTIES
        COMPILE_OPTIONS "-w" SKIP_PRECOMPILE_HEADERS ON)
    target_include_directories(nfscarbon PRIVATE
        src/native ${NFSCARBON_SDK_SOURCE_DIR} ${NFSCARBON_SDK_SOURCE_DIR}/thirdparty/renderdoc)
    target_link_libraries(nfscarbon PRIVATE d3d12 dxgi dxguid d3dcompiler windowscodecs ole32)
    message(STATUS "Native D3D12 renderer: on (SDK source ${NFSCARBON_SDK_SOURCE_DIR})")
else()
    message(STATUS "Native D3D12 renderer: off")
endif()

if(ANDROID AND ANDROID_ABI STREQUAL "arm64-v8a")
    # libadrenotools (BSD-2-Clause). Its hook libraries (libhook_impl.so, libmain_hook.so,
    # libfile_redirect_hook.so, libgsl_alloc_hook.so) must be copied into jniLibs/arm64-v8a.
    add_subdirectory(third_party/libadrenotools)
    target_link_libraries(nfscarbon PRIVATE adrenotools log)
    add_dependencies(nfscarbon main_hook file_redirect_hook gsl_alloc_hook hook_impl)
endif()

# Native Vulkan renderer plugin (gpu_plugin = "carbon"), see renderer/.
option(NFSCARBON_BUILD_CARBON_GPU "Build the rexgpu-carbon native renderer plugin" ON)
if(NFSCARBON_BUILD_CARBON_GPU)
    add_subdirectory(renderer)
    add_dependencies(nfscarbon rexgpu-carbon)
endif()

if(ANDROID)
    # The NDK defaults to per-function sections; with ~72k recompiled functions
    # that overflows ELF's 16-bit section count and breaks strip/dlopen. Merge
    # them back into one .text/.data per object.
    target_compile_options(nfscarbon PRIVATE -fno-function-sections -fno-data-sections)
    # Bind guest-to-guest calls inside the library directly. Otherwise every
    # call to an exported sub_XXXXXXXX goes through the PLT (~19.8k slots).
    # Hooks still win: the static linker picks strong definitions first.
    target_link_options(nfscarbon PRIVATE "LINKER:-Bsymbolic-functions")
    if(TARGET nfscarbon_recomp)
        target_compile_options(nfscarbon_recomp PRIVATE
            -fno-function-sections -fno-data-sections)
    endif()
    # Every phone this targets has ARMv8.2 (LSE atomics for the guest's
    # reservation loads/stores, among others).
    if(ANDROID_ABI STREQUAL "arm64-v8a")
        foreach(target nfscarbon nfscarbon_recomp)
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE -march=armv8.2-a)
            endif()
        endforeach()
    endif()
    # ThinLTO over the game code and the app. With tools/direct_calls.py applied,
    # calls between unhooked game functions go to __imp__sub_X and can be inlined
    # across files.
    option(NFSCARBON_ANDROID_LTO "ThinLTO over the game code (Android, Release)" ON)
    if(NFSCARBON_ANDROID_LTO AND CMAKE_BUILD_TYPE STREQUAL "Release")
        foreach(target nfscarbon nfscarbon_recomp)
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE -flto=thin)
            endif()
        endforeach()
        cmake_host_system_information(RESULT NFSCARBON_CORES QUERY NUMBER_OF_LOGICAL_CORES)
        target_link_options(nfscarbon PRIVATE -flto=thin "LINKER:--thinlto-jobs=${NFSCARBON_CORES}"
                            "LINKER:--thinlto-cache-dir=${CMAKE_BINARY_DIR}/thinlto-cache")
    endif()
endif()
