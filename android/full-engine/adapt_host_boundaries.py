"""Reviewed native boundaries for the final engine-side Windows units.

Called only after adapt_sources has checked the original input SHA-256. The
original actor walk, snapshot/restore logic and scene dispatch remain in their
own translation units. Optional x86-only crash probes explicitly report that
no native measurement was made; ordinary hardware faults stay fatal on Android.
"""
from __future__ import annotations
import re
from adapt_calls import masked


def replace(text: str, old: str, new: str, count: int = 1) -> str:
    if text.count(old) != count:
        raise ValueError('Native boundary anchor changed: ' + old[:100])
    return text.replace(old, new)


def function(text: str, signature: str, replacement: str) -> str:
    if text.count(signature) != 1:
        raise ValueError('Native boundary function changed: ' + signature)
    start = text.index(signature)
    code = masked(text)
    opening = code.index('{', start)
    depth = 1
    end = opening + 1
    while depth and end < len(code):
        depth += (code[end] == '{') - (code[end] == '}')
        end += 1
    if depth:
        raise ValueError('Unbalanced native boundary function')
    return text[:start] + replacement + text[end:]


def transform(text: str, kind: str) -> str:
    text = replace(text, '#include <windows.h>',
        '#include "sm64ds_posix_debug.h"\n#include "sm64ds_posix_clock.h"\n'
        '#include "sm64ds_memory_delta.h"\n#include <ctime>')
    if kind == 'scene':
        # This entire block is an opt-in x86 DR0..DR7 diagnostic, not scene
        # execution. Refuse its use instead of faking instruction-level tracing.
        start = text.index('static unsigned t3w_addr[4];')
        stop = text.index('/* TITLE LANE DIAGNOSTIC, run mg12.', start)
        text = text[:start] + '''static void t3w_tick(int, const char *)
{
    static bool warned = false;
    if (!warned && std::getenv("SM64DS_T3_WATCH")) {
        warned = true;
        std::fprintf(stderr, "[t3watch] NOT AVAILABLE: x86 hardware watchpoints "
                     "are not installed by the Android engine. No trace recorded.\\n");
    }
}
static void t3w_report(void)
{
    t3w_tick(0, "report");
}

''' + text[stop:]
    elif kind == 'oam':
        text = function(text, 'int terminated(const void *p)', '''int terminated(const void *p)
{
    const auto *a = static_cast<const unsigned char *>(p);
    for (int i = 0; i < kMaxEntries; ++i) {
        const void *word = a + i * 8 + 6;
        // Startup runs on the engine owner thread; no concurrent unmapping.
        if (sm64ds_bad_read_span(word, sizeof(unsigned short))) return 0;
        unsigned short value;
        std::memcpy(&value, word, sizeof value);
        if (value == 0xffff) return 1;
    }
    return 0;
}''')
        text = function(text, 'extern "C" int hal_oam_walk_probe(void)', '''extern "C" int hal_oam_walk_probe(void)
{
    std::fprintf(stderr, "[oam] NOT RUN: the destructive Windows SEH walk probe "
                 "is not available inside Android. Template validation is active.\\n");
    return 2; // Explicitly not a passed probe. No deliberate SIGSEGV in the app.
}''')
    elif kind == 'actor':
        text = '#include <exception>\nstruct Sm64dsActorDecline {};\n' + text
        text = replace(text, 'RaiseException(EXCEPTION_ACCESS_VIOLATION, 0, 0, 0);',
                       'throw Sm64dsActorDecline{};', 2)
        text = replace(text, 'IsBadReadPtr(', 'sm64ds_bad_read_span(', 3)
        text = replace(text, 'SYSTEMTIME st;', 'std::tm st{};')
        text = replace(text, 'GetLocalTime(&st);',
                       'const std::time_t wall = std::time(nullptr);\n    localtime_r(&wall, &st);')
        text = replace(text, 'st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond,',
                       'unsigned(st.tm_year + 1900), unsigned(st.tm_mon + 1), unsigned(st.tm_mday),\n        unsigned(st.tm_hour), unsigned(st.tm_min), unsigned(st.tm_sec),')
        text = replace(text, '"%s\\\\quarantine.log"', '"%s/quarantine.log"')
        text = function(text, 'static int port_q_filter(EXCEPTION_POINTERS *ep, unsigned *code, unsigned *off)',
            '''/* Android does not resume through hardware faults. Explicit unsupported-actor
 * declines use C++ unwinding; SIGSEGV/SIGBUS remain fatal for Android's native
 * crash reporter. No synthetic Windows exception context is manufactured. */''')
        text = replace(text, '    __try {', '    try {')
        text = replace(text, '    } __except (port_q_filter(GetExceptionInformation(), &code, &off)) {',
            '''    } catch (const Sm64dsActorDecline &) {
        if (port_faults_fatal()) throw;
        code = 0xe0640001u; // Native explicit-decline diagnostic, NOT an OS fault.
        off = 0; // No instruction address is claimed for an intentional decline.''')
        # Production logger owns an absolute app path, provided before boot.
        text += '''\nextern "C" __attribute__((weak)) const char *port_crash_dir_get(void)
{
    const char *dir = std::getenv("SM64DS_ERROR_DIR");
    return dir && dir[0] == '/' ? dir : "";
}
'''
    elif kind == 'rollback':
        text = function(text, 'double now_ms()', '''double now_ms()
{
    return static_cast<double>(sm64ds_clock_ns(CLOCK_MONOTONIC)) / 1000000.0;
}''')
        text = function(text, 'char *big_alloc(size_t n)', '''char *big_alloc(size_t n)
{
    return static_cast<char *>(sm64ds_snapshot_alloc(n));
}''')
        text = function(text, 'void hw_watch_reset_all()', '''/* The byte-comparison backend has no kernel watch bits to reset. Its
 * baseline is R.shadow, refreshed by the existing snapshot/restore code. */''')
        # Delete only code calls (not comments), no fictitious ResetWriteWatch.
        text = replace(text, 'hw_watch_reset_all();', '', text.count('hw_watch_reset_all();'))
        start = text.index('    if (g_hw_n) {\n        g_ww_buf = (void **)malloc(')
        stop = text.index('    size_t total = 0;', start)
        text = text[:start] + '''    if (g_hw_n) {
        g_ww_buf = (void **)malloc(sizeof(void *) * (g_ww_pages + 1));
        if (!g_ww_buf) return false;
        g_ww = true; // Differential byte comparison, NOT Windows write-watch.
    }
''' + text[stop:]
        text = replace(text, '''        ULONG_PTR cnt = g_ww_pages + 1;
        DWORD gran = 0;
        const UINT rc = GetWriteWatch(WRITE_WATCH_FLAG_RESET, R.base, R.size,
                                      g_ww_buf, &cnt, &gran);''', '''        size_t cnt = g_ww_pages + 1;
        const int rc = sm64ds_changed_blocks(R.base, R.shadow, R.size,
                                              kPage, g_ww_buf, &cnt);''')
        text = replace(text, '(ULONG_PTR)kUndoPages', '(size_t)kUndoPages')
        text = replace(text, 'for (ULONG_PTR i = 0;', 'for (size_t i = 0;')
        text = replace(text, 'g_ww ? "write-watched, undo logs" : "NO write-watch, full copies"',
                       'g_ww ? "native byte-compared undo logs" : "full copies"')
        text = replace(text, 'Sleep((DWORD)g_pause_ms);', 'sm64ds_sleep_ms((uint32_t)g_pause_ms);')
        old = '''        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery((const void *)(size_t)v, &mbi, sizeof mbi) && mbi.State == MEM_COMMIT)
            snprintf(desc[k], sizeof desc[k], "host %s at %p+0x%zx (type 0x%x)",
                     (const char *)mbi.AllocationBase == (const char *)port_arena_base() ? "ARENA" : "memory",
                     mbi.AllocationBase, (size_t)(v - (size_t)mbi.AllocationBase), (unsigned)mbi.Type);
        else snprintf(desc[k], sizeof desc[k], "not a host address");'''
        text = replace(text, old, '''        snprintf(desc[k], sizeof desc[k], "%s",
                 sm64ds_bad_read_span((const void *)(size_t)v, 1)
                     ? "not currently readable" : "currently readable host address");''')
        # Fail before using any shadow or undo allocation. No silent nullptr copy.
        text = replace(text, 'bool ring_init()\n{', '''static void native_ring_release_storage()
{
    for (int i = 0; i < kSlots; ++i) {
        Slot &s = g_ring[i];
        sm64ds_snapshot_free(s.arena, g_arena_size);
        sm64ds_snapshot_free(s.ds, g_ds_size);
        sm64ds_snapshot_free(s.undo_data, (size_t)kUndoPages * kPage);
        sm64ds_snapshot_free(s.hw_full, port_hw_regions_size());
        free(s.undo);
        memset(&s, 0, sizeof s);
    }
    for (int i = 0; i < kHwRegions; ++i) {
        sm64ds_snapshot_free(g_hw[i].shadow, g_hw[i].size);
        memset(&g_hw[i], 0, sizeof g_hw[i]);
    }
    free(g_ww_buf); g_ww_buf = nullptr;
    g_hw_n = 0; g_ww = false; g_ww_pages = 0;
}
struct NativeRingAllocGuard {
    bool committed = false;
    ~NativeRingAllocGuard() { if (!committed) native_ring_release_storage(); }
};
bool ring_init()
{''')
        text = replace(text, '    g_hw_n = 0;\n    for (int i = 0;',
                       '    NativeRingAllocGuard allocation_guard;\n    g_hw_n = 0;\n    for (int i = 0;')
        text = replace(text, '    g_ring_ready = true;',
                       '    allocation_guard.committed = true;\n    g_ring_ready = true;')
        text = replace(text, '        g_hw[g_hw_n].shadow = big_alloc(sz);',
                       '        g_hw[g_hw_n].shadow = big_alloc(sz);\n        if (!g_hw[g_hw_n].shadow) return false;')
        text = replace(text, '        if (!s.arena || !s.ds) {',
                       '        if (!s.arena || !s.ds || (g_ww && (!s.undo || !s.undo_data)) ||\n            (!g_ww && g_hw_n && !s.hw_full)) {')
    else:
        raise ValueError('Unknown native host boundary: ' + kind)
    code = masked(text)
    if re.search(r'\b(__try|__except|GetWriteWatch|ResetWriteWatch|VirtualAlloc|VirtualQuery|EXCEPTION_POINTERS|CONTEXT)\b', code):
        raise ValueError('Unadapted Windows code remains in ' + kind)
    return text
