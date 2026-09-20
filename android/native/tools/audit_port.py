#!/usr/bin/env python3
"""Inventory native-port blockers. Counts are occurrences, NOT game completion."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

RULES = {
    'windows_headers': r'#\s*include\s*[<"](?:windows|mmsystem|intrin|d3d\w*|xaudio\w*)\.h[>"]',
    'windows_fibers': r'\b(?:ConvertThreadToFiber(?:Ex)?|ConvertFiberToThread|CreateFiber(?:Ex)?|SwitchToFiber|DeleteFiber|GetCurrentFiber|IsThreadAFiber)\b',
    'windows_memory': r'\b(?:VirtualAlloc|VirtualFree|VirtualProtect|AddVectoredExceptionHandler)\b',
    'windows_timing_io': r'\b(?:QueryPerformanceCounter|QueryPerformanceFrequency|GetTickCount(?:64)?|CreateFile[AW]?|ReadFile|WriteFile|Sleep|timeGetTime|waveOut\w+)\b',
    'structured_exceptions': r'\b(?:__try|__except|__finally|EXCEPTION_POINTERS|GetExceptionCode)\b',
    'msvc_alias_linkage': r'#\s*pragma\s+comment\s*\(\s*linker|\b__declspec\s*\(|\b__thiscall\b',
    'assembly_and_intrinsics': r'\b(?:__asm|_Interlocked\w*|_mm_\w*)\b|\basm\s+void\b',
    'pointer_layout_checks': r'sizeof\s*\(\s*void\s*\*\s*\)\s*(?:==|!=)\s*4',
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    report = {'scope': 'Text inventory; comments can match; no execution or gameplay validation.',
              'base': 'port/link100@9bb3c454f9d67ee25ea9d08735e1f3943bbd6225',
              'files_scanned': 0, 'categories': {k: [] for k in RULES}}
    for folder in ('port', 'include', 'src'):
        for file in sorted((root / folder).rglob('*')):
            if file.suffix.lower() not in ('.h', '.hpp', '.c', '.cpp', '.cc', '.cmake', '.txt'):
                continue
            if not file.is_file():
                continue
            report['files_scanned'] += 1
            for number, line in enumerate(file.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                for name, pattern in RULES.items():
                    if re.search(pattern, line):
                        report['categories'][name].append({'path': file.relative_to(root).as_posix(),
                                                          'line': number, 'text': line.strip()[:240]})
    report['counts'] = {key: len(value) for key, value in report['categories'].items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'files_scanned': report['files_scanned'], 'counts': report['counts']}, indent=2))


if __name__ == '__main__':
    main()
