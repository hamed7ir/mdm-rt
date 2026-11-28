# MDM RT: CMake toolchain for x64 Windows with llvm-rt 2.4's clang-cl and lld, for btls-sys's BoringSSL (build.py:
# CMAKE_TOOLCHAIN_FILE_x86_64_pc_windows_msvc). x64 builds as the host, but without a toolchain file CMake looks for
# MSVC's rc.exe (its compiler check links a manifest), which only a Visual Studio prompt puts on PATH: here every
# tool is named, as in arm32-clang-cl.cmake. BoringSSL keeps its x64 assembly here (NASM, on build.py's PATH).
# With a toolchain file btls-sys skips its own CMake settings: the static CRT is set below.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR AMD64)
set(CMAKE_SYSTEM_VERSION 10.0)

set(_RT "F:/cr/rt24-cr/bin")
set(_VCTOOLS "D:/Program Files/vs22buildtools/VC/Tools/MSVC/14.44.35207")
set(_WINSDK "D:/Windows Kits/10")
set(_SDK "10.0.26100.0")

set(CMAKE_C_COMPILER   "${_RT}/clang-cl.exe")
set(CMAKE_CXX_COMPILER "${_RT}/clang-cl.exe")
set(CMAKE_AR           "${_RT}/llvm-lib.exe")
set(CMAKE_LINKER       "${_RT}/lld-link.exe")
set(CMAKE_RC_COMPILER  "${_RT}/llvm-rc.exe")
set(CMAKE_MT           "${_RT}/llvm-mt.exe")

set(_PIN "--target=x86_64-pc-windows-msvc -vctoolsdir \"${_VCTOOLS}\" -winsdkdir \"${_WINSDK}\" -winsdkversion ${_SDK}")
set(CMAKE_C_FLAGS_INIT   "${_PIN}")
set(CMAKE_CXX_FLAGS_INIT "${_PIN}")

set(_LIBPATHS "/libpath:\"${_VCTOOLS}/lib/x64\" /libpath:\"${_WINSDK}/Lib/${_SDK}/ucrt/x64\" /libpath:\"${_WINSDK}/Lib/${_SDK}/um/x64\"")
set(CMAKE_EXE_LINKER_FLAGS_INIT    "${_LIBPATHS}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_LIBPATHS}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_LIBPATHS}")

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
cmake_policy(SET CMP0091 NEW)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
