#!/usr/bin/env python3
"""Compile the resolved upstream game target with NDK; never claim gameplay.

CMake resolves source selection, per-file languages, definitions, includes and
custom generators. Every compiled unit is reported, including failures. Original
sources stay unchanged. Link-only resource generation is explicitly non-playable.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def load_units(build: Path, target: str) -> list[dict]:
    reply = build / '.cmake/api/v1/reply'
    indices = sorted(reply.glob('index-*.json'))
    if not indices:
        raise ValueError('No CMake File API index; request codemodel-v2 before configuring')
    index = json.loads(indices[-1].read_text())
    reference = next(o for o in index['objects'] if o['kind'] == 'codemodel')
    model = json.loads((reply / reference['jsonFile']).read_text())
    config = next((c for c in model['configurations'] if c['name'] == 'Release'), model['configurations'][0])
    targets = {t['id']: t for t in config['targets']}
    first = next(t['id'] for t in config['targets'] if t['name'] == target)
    source_root = Path(model['paths']['source'])
    build_root = Path(model['paths']['build'])
    todo, visited, units = [first], set(), []
    while todo:
        ident = todo.pop()
        if ident in visited:
            continue
        visited.add(ident)
        data = json.loads((reply / targets[ident]['jsonFile']).read_text())
        todo.extend(d['id'] for d in data.get('dependencies', []) if d['id'] in targets)
        for src in data.get('sources', []):
            if 'compileGroupIndex' not in src:
                continue
            group = {k: v for k, v in data['compileGroups'][src['compileGroupIndex']].items()
                     if k in ('language', 'defines', 'includes', 'compileCommandFragments')}
            path = Path(src['path'])
            if not path.is_absolute():
                path = (build_root if src.get('isGenerated') else source_root) / path
            units.append({'source': str(path.resolve()), 'target': data['name'],
                          'generated': bool(src.get('isGenerated')), 'group': group})
    if not units:
        raise ValueError('Resolved target contains no compilation units')
    return sorted(units, key=lambda u: (u['target'], u['source']))


def source_options(group: dict) -> tuple[list[str], list[str]]:
    """Translate only understood source-specific MSVC flags; reject the rest.

    NDK toolchain/optimisation flags are set explicitly by this compile-only
    diagnostic. Windows pointer-to-member flags are recorded, NOT equated with
    ARM C++ ABI compatibility. They are unresolved runtime integration work.
    """
    result, hazards = [], []
    for frag in group.get('compileCommandFragments', []):
        for flag in shlex.split(frag['fragment']):
            if flag == '/Oy-':
                result.append('-fno-omit-frame-pointer')
            elif flag in ('/vmg', '/vmm'):
                hazards.append('Unresolved MSVC member-pointer ABI: ' + flag)
            elif flag == '/Zp4':
                result.append('-fpack-struct=4')
            elif flag.startswith('/FI'):
                result += ['-include', flag[3:]]
            elif flag in ('-DWIN32', '-D_WIN32', '-D_WINDOWS'):
                hazards.append('Removed Windows platform define: ' + flag)
            elif flag.startswith('/'):
                raise ValueError('Untranslated compiler option: ' + flag)
            else:
                result.append(flag)
    return result, sorted(set(hazards))


def command_for(unit: dict, ndk: Path, output: Path, compat: Path) -> tuple[list[str], list[str]]:
    group = unit['group']
    lang = group['language']
    if lang not in ('C', 'CXX'):
        raise ValueError('Unsupported source language: ' + lang)
    compiler = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin' / (
        'armv7a-linux-androideabi23-clang++' if lang == 'CXX' else 'armv7a-linux-androideabi23-clang')
    if not compiler.is_file():
        raise ValueError('NDK compiler is missing: ' + str(compiler))
    flags, hazards = source_options(group)
    cmd = [str(compiler), '-x', 'c++' if lang == 'CXX' else 'c',
           '-std=c++17' if lang == 'CXX' else '-std=c11', '-O1', '-fPIC',
           '-fno-strict-aliasing', '-fwrapv', '-fno-omit-frame-pointer',
           '-ffunction-sections', '-fdata-sections', '-fms-extensions',
           '-ferror-limit=6', '-Werror=ignored-attributes', '-include', str(compat)]
    for define in group.get('defines', []):
        d = define['define']
        if d.split('=')[0] in ('WIN32', '_WIN32', '_WINDOWS'):
            hazards.append('Removed Windows platform define: ' + d)
            continue
        cmd.append('-D' + d)
    for inc in group.get('includes', []):
        cmd += ['-isystem' if inc.get('isSystem') else '-I', inc['path']]
    cmd += flags
    if unit['generated'] and Path(unit['source']).name.startswith(('ov', 'romdata')):
        cmd.append('-O0')
        hazards.append('Synthetic LINK-ONLY data setup compiled at O0; not release resource validation')
    cmd += ['-c', unit['source'], '-o', str(output)]
    return cmd, hazards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', default='walk_window')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'objects').mkdir(exist_ok=True)
    (out / 'errors').mkdir(exist_ok=True)
    units = load_units(build, args.target)
    from prepare_inputs import prepare
    units = prepare(units, out)
    (out / 'resolved-units.json').write_text(json.dumps(units, indent=2))
    generated = sorted({u['source'] for u in units if u['generated'] and not Path(u['source']).exists()})
    from generate_sources import generate
    generator_rc = generate(build, generated, out)
    from adapt_calls import prepare as prepare_calls
    units = prepare_calls(units, out)
    from adapt_sources import prepare as prepare_sources
    units = prepare_sources(units, out)
    (out / 'resolved-units.json').write_text(json.dumps(units, indent=2))
    print(f'Resolved {len(units)} translation units; generator exit={generator_rc}', flush=True)
    compat = Path(__file__).with_name('elf_compat.h').resolve()

    def compile_one(pair: tuple[int, dict]) -> dict:
        number, unit = pair
        result = {'index': number, **{k: unit[k] for k in ('source', 'target', 'generated')}}
        result['original_source'] = unit.get('original_source', unit['source'])
        obj = out / 'objects' / f'{number:05d}.o'
        source = Path(unit['source'])
        try:
            if unit.get('adaptation_error'):
                raise ValueError(unit['adaptation_error'])
            if not source.is_file():
                raise ValueError('Source was not generated')
            result['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            cmd, hazards = command_for(unit, args.ndk.resolve(), obj, compat)
            if unit.get('adaptation'):
                hazards.append(unit['adaptation'])
            result['command'], result['abi_review'] = cmd, hazards
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
            text = proc.stdout.decode('utf-8', errors='replace')
            result['status'] = 'compiled' if proc.returncode == 0 and obj.is_file() else 'failed'
            result['returncode'] = proc.returncode
            result['first_error'] = next((s for s in text.splitlines() if 'error:' in s), '')[:600]
            if result['status'] == 'compiled':
                result['object_bytes'] = obj.stat().st_size
            if text:
                (out / 'errors' / f'{number:05d}.txt').write_text(text)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            result['status'], result['first_error'] = 'blocked', str(exc)
        return result

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        pending = {pool.submit(compile_one, item): item[0] for item in enumerate(units)}
        for f in concurrent.futures.as_completed(pending):
            results.append(f.result())
            if len(results) % 500 == 0 or len(results) == len(units):
                print(f"{len(results)}/{len(units)} attempted; {sum(r['status']=='compiled' for r in results)} compiled", flush=True)
    results.sort(key=lambda r: r['index'])
    counts = {s: sum(r['status'] == s for r in results) for s in ('compiled', 'failed', 'blocked')}
    report = {'scope': 'NDK translation-unit compilation only; no complete link, executable, gameplay or device run',
              'resource_mode': 'upstream LINK-ONLY synthetic tables; deliberately not playable',
              'target': args.target, 'total': len(results), 'counts': counts,
              'generator_returncode': generator_rc, 'results': results}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    rows = ['# Full-engine NDK compilation', '', report['scope'], '',
            f"Target: `{args.target}`. Total {len(results)}. Counts: {counts}.",
            '', 'Generated resource tables are LINK-ONLY placeholders, not game data.',
            '', '## Remaining compilation errors', '']
    for r in results:
        if r['status'] != 'compiled':
            rows += [f"- `{r['source']}`: {r['first_error']}"]
    (out / 'REPORT.md').write_text('\n'.join(rows) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'results'}, indent=2), flush=True)
    return 1 if generator_rc or counts['failed'] or counts['blocked'] else 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        sys.exit(f'engine inventory error: {exc}')
