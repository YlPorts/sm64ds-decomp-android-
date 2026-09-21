#!/usr/bin/env python3
"""Resolve the retained native inventory using reviewed existing providers.

Undefined references alone are renamed. Definitions are never renamed, removed,
weakened, or satisfied by an empty function. The Windows executable is replaced
by a finite native scene entry; all selected engine objects remain in the link.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from native_signatures import expanded_command, strip_compile_io
from native_virtual_calls import SYMBOLS as VIRTUALS, transform as virtual_calls
from isolate_symbols import read_definitions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(command: list[str]) -> bytes:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-10000:])
    return result.stdout


def validate_manifest(manifest: dict, root: Path = ROOT) -> dict[str, str]:
    for rel, sha in manifest['source_sha256'].items():
        path = (root / rel).resolve()
        if not path.is_relative_to(root) or digest(path) != sha:
            raise ValueError('Changed linkage evidence: ' + rel)
    result = {}
    for source, row in manifest['bindings'].items():
        target = row['target']
        if source == target or any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', s)
                                   for s in (source, target)):
            raise ValueError('Invalid linkage binding: ' + source)
        if not row['upstream']:
            raise ValueError('Missing upstream binding evidence: ' + source)
        for evidence in row['upstream']:
            path = evidence['path']
            if path not in manifest['source_sha256']:
                raise ValueError('Unpinned alias evidence: ' + path)
            line = (root / path).read_text().splitlines()[evidence['line'] - 1]
            if '/alternatename:' + evidence['from'] + '=' + evidence['to'] + '"' not in line:
                raise ValueError('Alias evidence no longer matches: ' + source)
        result[source] = target
    return result


def symbols(text: str) -> dict[int, dict[str, str]]:
    result = defaultdict(dict)
    for line in text.splitlines():
        match = re.match(r'^.*[/\\](\d+)\.o:\s+(\S+)\s+([A-Za-z?])(?:\s|$)', line)
        if match:
            result[int(match[1])][match[2]] = match[3]
    if not result:
        raise ValueError('Empty object symbol inventory')
    return dict(result)


def fader_source(source: bytes) -> bytes:
    old = b'virtual ~HalFaderWipe() {}'
    if source.count(old) != 1:
        raise ValueError('Changed HalFaderWipe destructor')
    # MSVC needs an explicit second destructor slot. ARM Itanium already emits
    # two for a virtual destructor, so leaving the declaration unchanged would
    # shift every method after it by one. Keep the original destructor body and
    # the explicit ROM deleting-destructor method in their original slot order.
    source = b'extern "C" void *_ZN9FaderWipeD1Ev(void *);\n' + source.replace(
        old, b'~HalFaderWipe() {}\n'
             b'    virtual void DtorComplete() { _ZN9FaderWipeD1Ev(this); }')
    # ROM names its vtable at the first function, whereas ELF names the two-word
    # header. Define the address point in the SAME object as the native table.
    source += b'''\nstatic_assert(sizeof(void*) == 4, "Fader address point is ARM32");
__asm__(".global _ZTV9FaderWipe\\n"
        ".type _ZTV9FaderWipe, %object\\n"
        ".set _ZTV9FaderWipe, _ZTV12HalFaderWipe + 8\\n"
        ".size _ZTV9FaderWipe, 40\\n");
'''
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    base, out = args.baseline.resolve(), args.output.resolve()
    if base == out or base in out.parents:
        raise ValueError('Use a separate output directory')
    first = json.loads((base / 'report.json').read_text())
    old_audit = json.loads((base / 'link-audit/report.json').read_text())
    if old_audit['strong_duplicate_symbol_groups']:
        raise ValueError('Resolve duplicate signatures before linkage')
    for rel, sha in json.loads((HERE / 'linkage_sources.json').read_text()).items():
        if digest(ROOT / rel) != sha:
            raise ValueError('Unreviewed linkage source: ' + rel)
    aliases = validate_manifest(json.loads((HERE / 'linkage_aliases.json').read_text()))
    for directory in ('objects', 'sources', 'renames', 'errors'):
        (out / directory).mkdir(parents=True, exist_ok=True)
    llvm = args.ndk.resolve() / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    rsp = out / 'symbols.rsp'
    rsp.write_text('\n'.join(json.dumps(str(p)) for p in sorted((base / 'objects').glob('*.o'))))
    nm = checked([str(llvm / 'llvm-nm'), '-g', '-A', '--format=posix', '@' + str(rsp)])
    inventory = symbols(nm.decode())
    defined = {s for unit in inventory.values() for s, t in unit.items() if t not in ('U', 'w', 'v')}
    if aliases.keys() & defined:
        raise ValueError('An alias now has its own definition; review instead of overriding it')
    if set(aliases.values()) - defined:
        raise ValueError('Missing real alias providers: ' + str(sorted(set(aliases.values()) - defined)))
    isolation = Path(first['symbol_isolation_header'])
    extra_flags = ['-std=c++17', '-O1', '-fPIC', '-fno-strict-aliasing', '-fwrapv',
                   '-ffunction-sections', '-fdata-sections', '-I' + str(ROOT / 'include'),
                   '-I' + str(ROOT / 'port'), '-I' + str(ROOT / 'port/ntr/include'),
                   '-I' + str(ROOT / 'android/native/include'),
                   '-include', str(HERE / 'elf_compat.h'), '-include', str(isolation)]

    def compile_extra(source: Path, target: Path) -> list[str]:
        command = [str(llvm / 'armv7a-linux-androideabi23-clang++')]
        if source.suffix == '.S':
            command += ['-fPIC']
        else:
            command += extra_flags
        command += ['-c', str(source), '-o', str(target)]
        checked(command)
        return command

    def one(original: dict) -> tuple[dict, dict]:
        row = dict(original)
        index = row['index']
        target = out / 'objects' / f'{index:05d}.o'
        target.unlink(missing_ok=True)
        row.pop('object_bytes', None)
        evidence = {'index': index, 'renamed_references': {}, 'virtual_calls': []}
        try:
            if digest(Path(row['source'])) != row['source_sha256']:
                raise ValueError('Changed baseline source: ' + row['source'])
            original_path = Path(row['original_source']).resolve()
            rel = original_path.relative_to(ROOT).as_posix() if original_path.is_relative_to(ROOT) else ''
            if rel == 'port/tests/walk_window.cpp':
                source = HERE / 'native_scene_main.cpp'
                command = compile_extra(source, target)
                row.update(source=str(source), source_sha256=digest(source), command=command,
                           adaptation='Native finite scene runner replaces the Windows frontend')
            elif row['status'] != 'compiled':
                return row, evidence
            elif rel == 'port/hal/fader_wipes.cpp' or VIRTUALS & inventory.get(index, {}).keys():
                source = Path(row['source'])
                expanded = (source.read_bytes() if source.suffix == '.ii' else
                            checked(strip_compile_io(row['command']) + ['-E', '-P', str(source)]))
                pp = out / 'sources' / f'{index:05d}.ii'
                pp.write_bytes(expanded)
                if rel == 'port/hal/fader_wipes.cpp':
                    adapted = fader_source(expanded)
                    evidence['fader_address_point'] = '_ZTV12HalFaderWipe + 8; reviewed 10 ROM slots'
                else:
                    ast = json.loads(checked(expanded_command(row['command'], str(pp)) +
                                             ['-Xclang', '-ast-dump=json', '-fsyntax-only']))
                    adapted, evidence['virtual_calls'] = virtual_calls(expanded, ast)
                    if not evidence['virtual_calls']:
                        raise ValueError('Unresolved dummy method has no reviewed virtual call')
                pp.write_bytes(adapted)
                command = expanded_command(row['command'], str(pp))
                source_arg = command.pop()
                command += ['-c', source_arg, '-o', str(target)]
                checked(command)
                row.update(source=str(pp), source_sha256=digest(pp), command=command)
            else:
                os.link(base / 'objects' / target.name, target)
                row['command'] = row['command'].copy()
                row['command'][row['command'].index('-o') + 1] = str(target)
            # Never run objcopy in-place over the hardlink to the baseline.
            rename = {s: aliases[s] for s, t in inventory.get(index, {}).items()
                      if t == 'U' and s in aliases}
            if rename:
                mapping = out / 'renames' / f'{index:05d}.txt'
                mapping.write_text(''.join(f'{s} {t}\n' for s, t in sorted(rename.items())))
                temp = target.with_suffix('.new.o')
                checked([str(llvm / 'llvm-objcopy'), '--redefine-syms=' + str(mapping), str(target), str(temp)])
                temp.replace(target)
                evidence['renamed_references'] = rename
            row.update(status='compiled', returncode=0, first_error='', object_bytes=target.stat().st_size)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            target.unlink(missing_ok=True)
            row.update(status='failed', returncode=1, first_error=str(error)[:800])
            (out / 'errors' / f'{index:05d}.txt').write_text(str(error))
        return row, evidence

    rows, evidence = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for row, record in pool.map(one, first['results']):
            rows.append(row)
            if record['renamed_references'] or record['virtual_calls'] or record.get('fader_address_point'):
                evidence.append(record)
    for source in (HERE / 'smartball_native.cpp', HERE / 'native_controls.cpp',
                   ROOT / 'android/native/src/fiber.cpp', ROOT / 'android/native/src/context.S'):
        index = max(r['index'] for r in rows) + 1
        target = out / 'objects' / f'{index:05d}.o'
        target.unlink(missing_ok=True)
        command = compile_extra(source, target)
        rows.append({'index': index, 'target': 'walk_window', 'source': str(source),
                     'original_source': str(source), 'source_sha256': digest(source),
                     'generated': False, 'command': command, 'status': 'compiled',
                     'returncode': 0, 'object_bytes': target.stat().st_size})
    report = {**first, 'scope': 'Complete retained engine link with native scene frontend; NOT gameplay',
              'total': len(rows), 'counts': dict(Counter(r['status'] for r in rows)), 'results': rows}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    (out / 'linkage-evidence.json').write_text(json.dumps(evidence, indent=2))
    subprocess.run([sys.executable, str(HERE / 'link_inventory.py'), '--build', str(args.build),
                    '--report', str(out), '--ndk', str(args.ndk)], check=False)
    old = read_definitions(base / 'link-audit/defined-symbols.txt')
    new = read_definitions(out / 'link-audit/defined-symbols.txt')
    missing = [{'index': i, 'symbol': s, 'type': t} for i, values in old.items()
               for s, t in values - new.get(i, set())]
    retained = {'passed': not missing, 'original_strong_definitions': sum(map(len, old.values())),
                'missing': missing, 'scope': 'Same definition, symbol type and object for every original strong provider'}
    (out / 'provider-retention.json').write_text(json.dumps(retained, indent=2))
    audit = json.loads((out / 'link-audit/report.json').read_text())
    summary = {'baseline_units': first['total'], 'native_backend_units_added': 4,
               'selected_units': len(rows), 'compile_counts': report['counts'],
               'translated_aliases': len(aliases), 'provider_retention': retained['passed'],
               'strong_duplicate_groups': audit['strong_duplicate_symbol_groups'],
               'undefined_before': len(old_audit['undefined_symbols']),
               'undefined_after': len(audit['undefined_symbols']), 'link_returncode': audit['link_returncode'],
               'resource_mode': first['resource_mode'], 'gameplay': 'NOT RUN', 'android_device': 'NOT RUN'}
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    return int(bool(missing or audit['link_returncode'] or audit['strong_duplicate_symbol_groups'] or
                    any(r['status'] != 'compiled' for r in rows)))


if __name__ == '__main__':
    raise SystemExit(main())
