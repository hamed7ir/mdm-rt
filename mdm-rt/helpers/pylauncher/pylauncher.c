/* MDM RT: the launcher of the Python helpers (yt-dlp.exe, ...), for Windows on 32-bit Arm.
 *
 * yt-dlp is Python, and Python has no 32-bit Arm Windows release. MDM RT ships Kodi RT's ARM32 CPython (python-rt,
 * python314.dll with its modules built in, the standard library in python314.zip) and yt-dlp's own zipapp
 * (`yt-dlp`, the platform-independent release file, as yt-dlp.pyz). <name>.exe, this program renamed, runs
 * <name>.pyz beside it with that Python, in this process (Py_Main), so it starts, prints and ends like the
 * official yt-dlp.exe and MDM drives it the same way (its job object, its pipes, its exit code).
 *
 *   python314.dll   beside this exe (python314._pth beside it sets sys.path: python314.zip and this folder)
 *   <name>.pyz      beside this exe, or the file MDMRT_<NAME>_PYZ names (MDMRT_YT_DLP_PYZ for yt-dlp): a newer
 *                   zipapp MDM downloaded and verified, run with the Python beside this exe
 *
 * Python runs in UTF-8 mode (-X utf8): text from yt-dlp and from the programs it starts (ffmpeg, qjs) is UTF-8.
 *
 *   cacert.pem      beside this exe: Mozilla's list of root certificates, which Python's ssl then trusts besides
 *                   Windows' store (SSL_CERT_FILE, unless already set). An old Windows' store lacks today's roots
 *                   until a program checking certificates the Windows way asks for them (Windows fetches them
 *                   then), and Python reads the store as it is: on a Surface 2's Windows 10 build 15035 yt-dlp's
 *                   YouTube look-ups failed with CERTIFICATE_VERIFY_FAILED. The official yt-dlp.exe brings
 *                   Mozilla's list too (certifi); this zipapp doesn't.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

typedef int (*PyMainFn)(int, wchar_t **);

static int fail(const wchar_t *what, const wchar_t *detail)
{
    fwprintf(stderr, L"%ls: %ls\n", what, detail);
    return 2;
}

int wmain(int argc, wchar_t **argv)
{
    static wchar_t exe[32768], dir[32768], name[512], dll[32768], pyz[32768], var[600], env[32768];
    DWORD n = GetModuleFileNameW(NULL, exe, ARRAYSIZE(exe));
    if (n == 0 || n >= ARRAYSIZE(exe))
        return fail(L"launcher", L"cannot find its own path");
    wcscpy_s(dir, ARRAYSIZE(dir), exe);
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (!slash)
        return fail(L"launcher", L"odd program path");
    *slash = 0;
    wcscpy_s(name, ARRAYSIZE(name), slash + 1);
    wchar_t *dot = wcsrchr(name, L'.');
    if (dot && !_wcsicmp(dot, L".exe"))
        *dot = 0;

    /* MDMRT_<NAME>_PYZ: the name upper-cased, '-' as '_' */
    swprintf_s(var, ARRAYSIZE(var), L"MDMRT_%ls_PYZ", name);
    for (wchar_t *p = var; *p; p++) {
        if (*p == L'-')
            *p = L'_';
        else if (*p >= L'a' && *p <= L'z')
            *p = (wchar_t)(*p - L'a' + L'A');
    }
    DWORD e = GetEnvironmentVariableW(var, env, ARRAYSIZE(env));
    if (e > 0 && e < ARRAYSIZE(env) && GetFileAttributesW(env) != INVALID_FILE_ATTRIBUTES)
        wcscpy_s(pyz, ARRAYSIZE(pyz), env);
    else
        swprintf_s(pyz, ARRAYSIZE(pyz), L"%ls\\%ls.pyz", dir, name);
    if (GetFileAttributesW(pyz) == INVALID_FILE_ATTRIBUTES)
        return fail(name, L"its .pyz file is missing beside the program");

    /* Mozilla's roots besides Windows' store (above): set before Python and its C runtime read the environment */
    static wchar_t certs[32768];
    if (GetEnvironmentVariableW(L"SSL_CERT_FILE", NULL, 0) == 0) {
        swprintf_s(certs, ARRAYSIZE(certs), L"%ls\\cacert.pem", dir);
        if (GetFileAttributesW(certs) != INVALID_FILE_ATTRIBUTES)
            SetEnvironmentVariableW(L"SSL_CERT_FILE", certs);
    }

    swprintf_s(dll, ARRAYSIZE(dll), L"%ls\\python314.dll", dir);
    HMODULE py = LoadLibraryExW(dll, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!py)
        return fail(name, L"python314.dll is missing beside the program");
    PyMainFn py_main = (PyMainFn)GetProcAddress(py, "Py_Main");
    if (!py_main)
        return fail(name, L"python314.dll has no Py_Main");

    /* python -X utf8 -B <pyz> <the arguments> */
    wchar_t **args = (wchar_t **)calloc((size_t)argc + 5, sizeof(wchar_t *));
    if (!args)
        return fail(name, L"out of memory");
    int k = 0;
    args[k++] = argv[0];
    args[k++] = L"-X";
    args[k++] = L"utf8";
    args[k++] = L"-B";
    args[k++] = pyz;
    for (int i = 1; i < argc; i++)
        args[k++] = argv[i];
    args[k] = NULL;
    return py_main(k, args);
}
