#!/usr/bin/env python3
"""Generate a native copy of the pinned scheduler; never edit upstream sources."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

EXPECTED_BLOB = '24f17b5dd989f6f5c344874c5ae64aa77e41c666'

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def rewrite(text: str) -> str:
    if text.count('#include <windows.h>') != 1:
        raise ValueError('Expected exactly one Windows include')
    if '#if defined(_WIN32)' not in text:
        raise ValueError('Missing expected platform guards')
    header = '''#include "win_fiber_compat.h"
#include "sm64ds_scheduler.h"
#include <cerrno>
#include <sys/syscall.h>
#include <unistd.h>
static_assert(sizeof(void *) == 4, "The original scheduler requires a 32-bit ABI");
static unsigned long sm64ds_host_thread_id() {
    return static_cast<unsigned long>(syscall(SYS_gettid));
}'''
    text = text.replace('#include <windows.h>', header)
    text = text.replace('#if defined(_WIN32)', '#if defined(SM64DS_NATIVE_FIBERS)')
    substitutions = {
        'GetCurrentThreadId()': 'sm64ds_host_thread_id()',
        'GetLastError()': 'errno',
        'ERROR_ALREADY_FIBER': 'EALREADY',
        'GetCurrentFiber()': 'sm64ds::platform::current_fiber()',
    }
    for old, new in substitutions.items():
        if old not in text:
            raise ValueError(f'Missing expected scheduler dependency: {old}')
        text = text.replace(old, new)
    boot = 'ThreadBoot() {\n        thread_boot();\n        thread_proof();\n    }'
    if text.count(boot) != 1:
        raise ValueError('Missing expected eager Windows scheduler bootstrap')
    # Android loads JNI libraries on a different thread from the game worker.
    # Do not bind ownership to the dynamic loader's thread.
    text = text.replace(boot, 'ThreadBoot() = default;')
    text = text.replace('#pragma init_seg(lib)', '// Explicit native initialization replaces MSVC init_seg.')
    text += """
extern "C" bool sm64ds_native_scheduler_init() {
    if (g_booted) {
        if (g_owner_tid == sm64ds_host_thread_id()) return true;
        errno = EPERM;
        return false;
    }
    thread_boot();
    thread_proof();
    return true;
}
"""
    return ('// Generated from pinned port/hal/boot2_thread.cpp. Do not edit.\n'
            '// Native platform adaptation only; 32-bit layouts are preserved.\n' + text)

def add_lifetimes(text: str) -> str:
    """Patch native lifetime ownership, using reviewed, unique upstream anchors."""
    def once(old: str, new: str) -> None:
        nonlocal text
        count = text.count(old)
        if count != 1:
            raise ValueError(f'Lifetime anchor changed ({count}): {old[:72]!r}')
        text = text.replace(old, new, 1)

    once('    bool created;       // came in through func_02058200, not the boot seat',
         '    bool created;       // came in through func_02058200, not the boot seat\n'
         '    bool retired;       // original exit unlinked it; collect from another stack')
    once('FiberSlot *slot_of(RomThread *t) {',
         'unsigned native_reap_completed();\n'
         'unsigned long long native_reaped_total = 0;\n\n'
         'FiberSlot *slot_of(RomThread *t) {')
    once('            s.created = false;',
         '            s.created = false;\n            s.retired = false;')
    once('void CALLBACK thread_trampoline(void *p) {',
         'void CALLBACK thread_trampoline(void *p) {\n    native_reap_completed();')
    once('int ARMSaveContext(void *ctx) {\n    thread_boot();',
         'int ARMSaveContext(void *ctx) {\n'
         '    if (g_booted && g_owner_tid != sm64ds_host_thread_id()) {\n'
         '        ++g_stat.wrong_thread; errno = EPERM; return 1;\n'
         '    }\n    thread_boot();')
    once('void ARMRestoreContext(void *ctx) {\n    thread_boot();',
         'void ARMRestoreContext(void *ctx) {\n'
         '    // Check ownership BEFORE adopting a record or reading its stack.\n'
         '    if (g_booted && g_owner_tid != sm64ds_host_thread_id()) {\n'
         '        ++g_stat.wrong_thread; errno = EPERM; return;\n'
         '    }\n    thread_boot();\n'
         '    if (!ctx) { ++g_stat.rejected; errno = EINVAL; return; }\n'
         '    native_reap_completed();')
    once('    SwitchToFiber(ts->fiber);',
         '    // Snapshot retirement while the original record is still alive.\n'
         '    // Never inspect a caller-owned record later from the collector: the\n'
         '    // joiner may already have destroyed/reused it when we regain control.\n'
         '    if (FiberSlot *old = slot_of(from)) {\n'
         '        if (old->created && from->state == 2 && from->id < 16 &&\n'
         '            data_020a6148[from->id] != static_cast<int>(reinterpret_cast<intptr_t>(from)))\n'
         '            old->retired = true;\n'
         '    }\n    SwitchToFiber(ts->fiber);')
    once('    ++g_stat.resumes;\n    trace("resume %u", from ? from->id : 0u);',
         '    ++g_stat.resumes;\n'
         '    native_reap_completed();\n'
         '    trace("resume %u", from ? from->id : 0u);')
    once('    else if (lo == 0 || hi == 0 || hi <= lo)',
         '    else if (lo == 0 || hi == 0 || hi <= lo || hi - lo < 8 || ((lo | hi) & 3u))')
    # Keep all original scheduling and exit functions; only native stack ownership changes.
    return text + '\n#include "scheduler_lifecycle.inc"\n'

def adapt(source: Path, output: Path) -> None:
    data = source.read_bytes()
    digest = git_blob(data)
    if digest != EXPECTED_BLOB:
        raise ValueError(f'Upstream scheduler changed: {digest}; review before adapting')
    result = add_lifetimes(rewrite(data.decode('utf-8')))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        adapt(args.source, args.output)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f'Cannot adapt scheduler: {exc}\n')
