/* MDM RT: qjs.exe, a small runner for QuickJS-ng (https://github.com/quickjs-ng/quickjs, MIT), built from its
 * amalgamation (quickjs-amalgam.c, quickjs.h, quickjs-libc.h).
 *
 * yt-dlp needs a JavaScript runtime to solve YouTube's challenges, and the ones it knows (Deno, Node.js, Bun,
 * QuickJS) have no 32-bit Arm Windows build, so MDM RT's ARM32 build ships this one and tells yt-dlp about it
 * (`--js-runtimes quickjs:<path>`). yt-dlp uses exactly two things of `qjs` (yt_dlp/utils/_jsruntime.py,
 * yt_dlp/extractor/youtube/jsc/_builtin/quickjs.py), and this program does them as the real qjs does:
 *   qjs --help              prints "QuickJS-ng version <v>" first (exit code 1, as qjs)
 *   qjs --script <file>     runs <file> as a classic script, with qjs's helpers (console.log, print, scriptArgs,
 *                           std and os as globals not; yt-dlp's solver needs console.log only), then the job loop;
 *                           an uncaught exception goes to stderr with exit code 1
 * A plain `qjs <file>` runs the file the same way. Nothing else of qjs (REPL, modules, -e) is here.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "quickjs.h"
#include "quickjs-libc.h"

static int usage(void)
{
    printf("QuickJS-ng version %s\n"
           "usage: qjs [--script] file [args]\n"
           "MDM RT's runner: runs a script file with console.log, print and scriptArgs.\n",
           JS_GetVersion());
    return 1;
}

int main(int argc, char **argv)
{
    int i = 1;
    if (i < argc && (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")))
        return usage();
    if (i < argc && !strcmp(argv[i], "--script"))
        i++;
    if (i >= argc)
        return usage();
    const char *file = argv[i];

    JSRuntime *rt = JS_NewRuntime();
    if (!rt) {
        fprintf(stderr, "qjs: cannot allocate the JS runtime\n");
        return 2;
    }
    js_std_init_handlers(rt);
    JSContext *ctx = JS_NewContext(rt);
    if (!ctx) {
        fprintf(stderr, "qjs: cannot allocate the JS context\n");
        return 2;
    }
    js_std_add_helpers(ctx, argc - i, argv + i);

    size_t len = 0;
    uint8_t *buf = js_load_file(ctx, &len, file);
    if (!buf) {
        fprintf(stderr, "qjs: cannot read %s\n", file);
        return 1;
    }
    int ret = 0;
    JSValue val = JS_Eval(ctx, (const char *)buf, len, file, JS_EVAL_TYPE_GLOBAL);
    js_free(ctx, buf);
    if (JS_IsException(val)) {
        js_std_dump_error(ctx);
        ret = 1;
    }
    JS_FreeValue(ctx, val);
    if (!ret && js_std_loop(ctx))      /* nonzero: an unhandled exception in a job or promise */
        ret = 1;
    js_std_free_handlers(rt);
    JS_FreeContext(ctx);
    JS_FreeRuntime(rt);
    return ret;
}
