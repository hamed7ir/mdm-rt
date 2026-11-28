# MDM RT: CMake toolchain for 32-bit x86 Windows with llvm-rt 2.4's clang-cl and lld: the x86 test build of the
# ARM32 path, for btls-sys's BoringSSL (build.py: CMAKE_TOOLCHAIN_FILE_i686_pc_windows_msvc). As arm32-clang-cl.cmake;
# BoringSSL without its assembly here too (the same as on ARM32; btls-sys does so when it cross-compiles itself).
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86)
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

set(_PIN "--target=i686-pc-windows-msvc -vctoolsdir \"${_VCTOOLS}\" -winsdkdir \"${_WINSDK}\" -winsdkversion ${_SDKINC}")
set(CMAKE_C_FLAGS_INIT   "${_PIN}")
set(CMAKE_CXX_FLAGS_INIT "${_PIN}")
set(CMAKE_ASM_FLAGS_INIT "--target=i686-pc-windows-msvc")

set(_LIBPATHS "/libpath:\"${_VCTOOLS}/lib/x86\" /libpath:\"${_WINSDK}/Lib/${_SDKLIB}/ucrt/x86\" /libpath:\"${_WINSDK}/Lib/${_SDKLIB}/um/x86\"")
set(CMAKE_EXE_LINKER_FLAGS_INIT    "${_LIBPATHS}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_LIBPATHS}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_LIBPATHS}")

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
cmake_policy(SET CMP0091 NEW)
set(OPENSSL_NO_ASM ON CACHE BOOL "BoringSSL: no assembly" FORCE)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
