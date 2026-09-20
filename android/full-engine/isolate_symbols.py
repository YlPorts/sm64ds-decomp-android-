#!/usr/bin/env python3
"""Replay the native inventory with separate names for explicit Itanium-looking identifiers.

This is a two-pass integration tool, NOT a finished port. It keeps every selected
unit and every function body. Only source-language tokens are renamed; compiler
emitted C++ names are untouched. Failed units, remaining duplicate symbols and
link errors are never hidden. Source copies from the first pass must still exist.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

PREFIX = 'sm64ds_cabi'
IDENTIFIER = re.compile(r'_Z[A-Za-z0-9_]+\Z')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collision_names(audit: dict) -> list[str]:
    groups = audit['strong_duplicates']
    if audit['strong_duplicate_symbol_groups'] != len(groups):
        raise ValueError('Inconsistent first-pass symbol census')
    names = []
    for name, providers in groups.items():
        if not IDENTIFIER.fullmatch(name):
            raise ValueError('Unreviewed symbol spelling: ' + name)
        if len(providers) < 2 or len({p['index'] for p in providers}) < 2:
            raise ValueError('Not an inter-unit duplicate: ' + name)
        names.append(name)
    return sorted(names)


def header_text(names: list[str]) -> str:
    if len(set(names)) != len(names) or any(not IDENTIFIER.fullmatch(s) for s in names):
        raise ValueError('Invalid or repeated symbol token')
    return ('/* Generated from the actual first-pass strong-symbol census.\n'
            ' * Separate literal recovered identifiers from native C++ mangling.\n'
            ' * No function body, conversion, vtable entry or destructor is removed. */\n'
            '#pragma once\n' + ''.join(f'#define {s} {PREFIX}{s}\n' for s in sorted(names)))


def replay_command(row: dict, header: Path, output: Path) -> list[str]:
    cmd = row.get('command')
    if not isinstance(cmd, list) or not cmd or any(not isinstance(x, str) for x in cmd):
        raise ValueError('Missing original compile command')
    if cmd.count('-c') != 1 or cmd.count('-o') != 1:
        raise ValueError('Expected exactly one input and output')
    if cmd[cmd.index('-c') + 1] != row['source']:
        raise ValueError('Compile source does not match recorded source')
    source = Path(row['source'])
    if digest(source) != row['source_sha256']:
        raise ValueError('Source changed since first pass: ' + str(source))
    cmd = cmd.copy()
    cmd[cmd.index('-o') + 1] = str(output)
    cmd[1:1] = ['-include', str(header)]
    return cmd


def renamed_symbol(symbol: str, names: set[str]) -> str | None:
    if symbol in names:
        return PREFIX + symbol
    # A few recovered free functions were declared with C++ linkage, i.e.
    # their literal _ZN... identifier is encoded once MORE by the compiler.
    # Update that unqualified source-name's length; never guess nested names.
    m = re.match(r'^_Z([1-9][0-9]*)(.*)$', symbol)
    if m:
        n = int(m[1]); token, suffix = m[2][:n], m[2][n:]
        if len(token) == n and token in names:
            return '_Z' + str(n + len(PREFIX)) + PREFIX + token + suffix
    return None


def read_definitions(path: Path) -> dict[int, set[tuple[str, str]]]:
    by_unit = defaultdict(set)
    for line in path.read_text().splitlines():
        match = re.match(r'^.*?[/\\]([0-9]+)\.o:\s+(\S+)\s+([A-Za-z?])\s+', line)
        if not match:
            continue
        ident, symbol, typ = match.groups()
        if typ.isupper() and typ not in ('U', 'W', 'V', 'C'):
            by_unit[int(ident)].add((symbol, typ))
    if not by_unit:
        raise ValueError('No strong definitions in llvm-nm output: ' + str(path))
    return dict(by_unit)


def provider_audit(before: dict, after: dict, names: set[str]) -> dict:
    totals = Counter(); missing = []; introduced_aliases = []
    for index, definitions in before.items():
        target = after.get(index, set())
        for symbol, typ in sorted(definitions):
            renamed = renamed_symbol(symbol, names)
            if (symbol, typ) in target:
                totals['unchanged'] += 1
            elif renamed and (renamed, typ) in target:
                totals['renamed_literal' if symbol in names else 'renamed_cpp_free_identifier'] += 1
            else:
                missing.append({'index': index, 'symbol': symbol, 'type': typ})
    for index, definitions in after.items():
        old = before.get(index, set())
        for symbol, typ in definitions:
            if symbol.startswith(PREFIX):
                original = symbol[len(PREFIX):]
                if original not in names or (original, typ) not in old:
                    introduced_aliases.append({'index': index, 'symbol': symbol, 'type': typ})
    return {'scope': 'Every first-pass strong definition must survive in the SAME object, with the SAME symbol type',
            'before_definitions': sum(map(len, before.values())), 'counts': dict(totals),
            'missing_providers': missing, 'unexpected_prefixed_definitions': introduced_aliases,
            'passed': not missing and not introduced_aliases,
            'semantic_execution': 'Not established by symbol retention alone'}


def verify(folder: Path, baseline: Path, names: set[str]) -> dict:
    result = provider_audit(read_definitions(baseline/'link-audit/defined-symbols.txt'),
                            read_definitions(folder/'link-audit/defined-symbols.txt'), names)
    (folder/'provider-retention.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def run(args: argparse.Namespace) -> int:
    baseline, out = args.baseline.resolve(), args.output.resolve()
    if baseline == out or baseline in out.parents:
        raise ValueError('Use an independent output directory, not the first-pass folder')
    first = json.loads((baseline/'report.json').read_text())
    audit = json.loads((baseline/'link-audit/report.json').read_text())
    if first['total'] != len(first['results']) or len({r['index'] for r in first['results']}) != first['total']:
        raise ValueError('Repeated or missing unit identifiers')
    names = collision_names(audit)
    out.mkdir(parents=True, exist_ok=True)
    header = out/'native_symbol_isolation.h'
    manifest = {'scope': 'Diagnostic two-pass symbol separation, NOT gameplay',
                'baseline_report_sha256': digest(baseline/'report.json'),
                'baseline_census_sha256': digest(baseline/'link-audit/report.json'),
                'prefix': PREFIX, 'symbols': names, 'selected_units': first['total']}
    if args.audit_only:
        if not header.is_file():
            raise ValueError('Missing second-pass header')
        # Experimental and production headers may have different comments, but
        # the complete macro map must be identical and contain no extra macros.
        found = re.findall(r'^#define\s+(\S+)\s+(\S+)\s*$', header.read_text(), re.M)
        if sorted(found) != [(n, PREFIX+n) for n in names]:
            raise ValueError('Header differs from the first-pass census')
    else:
        header.write_text(header_text(names))
    manifest['header_sha256'] = digest(header)
    (out/'symbol-isolation.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if not args.audit_only:
        (out/'objects').mkdir(exist_ok=True); (out/'errors').mkdir(exist_ok=True)
        def one(row: dict) -> dict:
            result = dict(row); obj = out/'objects'/f"{row['index']:05d}.o"
            obj.unlink(missing_ok=True)  # Never count an old object after a failed command.
            result.pop('object_bytes', None)
            try:
                cmd = replay_command(row, header, obj)
                result['command'] = cmd
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
                text = proc.stdout.decode('utf-8', errors='replace')
                result.update(status='compiled' if proc.returncode == 0 and obj.is_file() else 'failed',
                              returncode=proc.returncode,
                              first_error=next((s for s in text.splitlines() if 'error:' in s), '')[:800])
                if obj.is_file(): result['object_bytes'] = obj.stat().st_size
                (out/'errors'/f"{row['index']:05d}.txt").write_text(text)
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                result.update(status='blocked', first_error=str(exc), returncode=None)
            return result
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            for row in pool.map(one, first['results']):
                results.append(row)
                if len(results) % 500 == 0:
                    print(f'Replayed {len(results)}/{first["total"]} original units', flush=True)
        second = {**first, 'scope': 'Same selected native units, explicit-identifier separation; NOT gameplay',
                  'symbol_isolation_header': str(header), 'results': results,
                  'counts': {s: sum(r['status'] == s for r in results) for s in ('compiled','failed','blocked')}}
        (out/'report.json').write_text(json.dumps(second, indent=2) + '\n')
    second = json.loads((out/'report.json').read_text())
    identity = lambda rows: {(r['index'],r['target'],r['original_source']) for r in rows}
    if identity(first['results']) != identity(second['results']):
        raise ValueError('Second pass changed the selected source set')
    proc = subprocess.run([sys.executable, str(Path(__file__).with_name('link_inventory.py')),
                           '--build',str(args.build.resolve()),'--report',str(out),
                           '--ndk',str(args.ndk.resolve())], timeout=240)
    if proc.returncode not in (0, 1): raise RuntimeError('Link auditor did not complete')
    retained = verify(out, baseline, set(names))
    link = json.loads((out/'link-audit/report.json').read_text())
    summary = {'scope': 'Full selected-set native compile/link diagnostic; NOT gameplay',
               'selected_units': second['total'], 'compile_counts': second['counts'],
               'before_strong_duplicate_groups': audit['strong_duplicate_symbol_groups'],
               'after_strong_duplicate_groups': link['strong_duplicate_symbol_groups'],
               'provider_retention_passed': retained['passed'],
               'link_returncode': link['link_returncode'],
               'undefined_linker_diagnostics': len(link['undefined_symbols']),
               'undefined_diagnostics_complete': link['strong_duplicate_symbol_groups'] == 0,
               'game_execution': 'NOT RUN', 'physical_android_device': 'NOT RUN'}
    (out/'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    return 1 if not retained['passed'] or proc.returncode or second['counts']['failed'] or second['counts']['blocked'] else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--audit-only', action='store_true', help='Verify already-replayed objects against the same census')
    return run(p.parse_args())


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        sys.exit('Native symbol isolation failed: ' + str(exc))
