# MDM RT: CMake toolchain for Windows ARM32 (thumbv7, IMAGE_FILE_MACHINE_ARMNT) with llvm-rt 2.4's clang-cl and lld,
# for the C/C++ libraries cargo's build scripts build with CMake: btls-sys's BoringSSL (the engine's browser-like
# connection, wreq). build.py gives it to them as CMAKE_TOOLCHAIN_FILE_thumbv7a_pc_windows_msvc.
# From hamed7ir/adb-rt's cross/arm32-clang-cl.cmake and the tgcalls ARM32 build's tc/arm32-rt21.cmake:
#  - -vctoolsdir/-winsdkdir/-winsdkversion pin the MSVC toolset and SDK headers (14.44: the last toolset with ARM32);
#    import libraries from SDK 10.0.19041.0, the last with ARM32 ones.
#  - static CRT (/MT), as the Rust side links it (+crt-static).
#  - OPENSSL_NO_ASM: BoringSSL has no Windows ARM32 assembly. btls-sys sets it itself only when it isn't given a
#    toolchain file, as it skips all its own settings then.
#  - executables link too (CMake's compiler checks), with the ARM32 libraries.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_SYSTEM_VERSION 10.0)

set(_RT "F:/cr/rt24-cr/bin")
set(_VCTOOLS "D:/Program Files/vs22buildtools/VC/Tools/MSVC/14.44.35207")
set(_WINSDK "D:/Windows Kits/10")
set(_SDKINC "10.0.26100.0")
set(_SDKLIB "10.0.19041.0")

set(CMAKE_C_COMPILER   "${_RT}/clang-cl.exe")
set(CMAKE_CXX_COMPILER "${_RT}/clang-cl.exe")
set(CMAKE_ASM_COMPILER "${_RT}/clang.exe")
set(CMAKE_AR           "${_RT}/llvm-lib.exe")
set(CMAKE_LINKER       "${_RT}/lld-link.exe")
set(CMAKE_RC_COMPILER  "${_RT}/llvm-rc.exe")
set(CMAKE_MT           "${_RT}/llvm-mt.exe")

set(_PIN "--target=thumbv7-windows-msvc -vctoolsdir \"${_VCTOOLS}\" -winsdkdir \"${_WINSDK}\" -winsdkversion ${_SDKINC}")
set(CMAKE_C_FLAGS_INIT   "${_PIN}")
set(CMAKE_CXX_FLAGS_INIT "${_PIN}")
set(CMAKE_ASM_FLAGS_INIT "--target=thumbv7-windows-msvc")

set(_LIBPATHS "/libpath:\"${_VCTOOLS}/lib/arm\" /libpath:\"${_WINSDK}/Lib/${_SDKLIB}/ucrt/arm\" /libpath:\"${_WINSDK}/Lib/${_SDKLIB}/um/arm\"")
set(CMAKE_EXE_LINKER_FLAGS_INIT    "${_LIBPATHS}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_LIBPATHS}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_LIBPATHS}")

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
cmake_policy(SET CMP0091 NEW)
set(OPENSSL_NO_ASM ON CACHE BOOL "BoringSSL: no assembly (none for Windows ARM32)" FORCE)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
