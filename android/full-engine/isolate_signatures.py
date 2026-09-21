#!/usr/bin/env python3
"""Third-pass C++ signature isolation over the unchanged full engine inventory.

No unit is removed, and no duplicate-symbol tolerance or weak alias is used.
The existing failed Windows frontend stays failed and is reported as such.
"""
from __future__ import annotations
import argparse
from collections import Counter
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from native_signatures import SYMBOLS, transform, strip_compile_io, expanded_command
from isolate_symbols import read_definitions


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_checked(command: list[str], *, output: Path | None = None) -> bytes:
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors='replace')[-8000:])
    if output:
        output.write_bytes(proc.stdout)
    return proc.stdout


def referenced_units(text: str) -> set[int]:
    return {int(m[1]) for line in text.splitlines()
            if (m := re.match(r'^.*[/\\](\d+)\.o:\s+(\S+)\s+', line)) and m[2] in SYMBOLS}


def retention(before: Path, after: Path, evidence: dict[int, list[dict]]) -> dict:
    old, new = read_definitions(before), read_definitions(after)
    missing = []; renamed = 0; unchanged = 0
    for index, definitions in old.items():
        allowed = {(x['symbol'], x['tag']) for x in evidence.get(index, [])}
        for symbol, kind in definitions:
            if (symbol, kind) in new.get(index, set()):
                unchanged += 1
                continue
            # Destructor D1/D2/D0 variants inherit the same declaration's tag.
            candidates = {tag for s, tag in allowed if s == symbol or
                          (s in ('_ZN5ActorD1Ev', '_ZN5ActorD2Ev') and symbol in
                           ('_ZN5ActorD0Ev', '_ZN5ActorD1Ev', '_ZN5ActorD2Ev'))}
            matches = []
            for ns, nk in new.get(index, set()):
                if nk != kind:
                    continue
                for tag in candidates:
                    marker = 'B' + str(len(tag)) + tag
                    if marker in ns and ns.replace(marker, '', 1) == symbol:
                        matches.append(ns)
            if len(set(matches)) == 1:
                renamed += 1
            else:
                missing.append({'index': index, 'symbol': symbol, 'type': kind,
                                'candidates': sorted(set(matches))})
    return {'passed': not missing, 'unchanged': unchanged, 'tagged': renamed,
            'missing': missing, 'scope': 'Every original strong provider retained in its own object'}


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
    audit = json.loads((base / 'link-audit/report.json').read_text())
    if not set(audit['strong_duplicates']).issubset(SYMBOLS):
        raise ValueError('The native duplicate census contains an unreviewed symbol')
    for p in ('objects', 'errors', 'preprocessed', 'tagged', 'signatures'):
        (out / p).mkdir(parents=True, exist_ok=True)
    llvm = args.ndk.resolve() / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    rsp = out / 'all-symbols.rsp'
    rsp.write_text('\n'.join(json.dumps(str(p)) for p in sorted((base / 'objects').glob('*.o'))))
    nm = run_checked([str(llvm / 'llvm-nm'), '-g', '-A', '--format=posix', '@' + str(rsp)])
    affected = referenced_units(nm.decode())
    print(f'Checking {len(affected)} caller/provider units, preserving all {first["total"]} units', flush=True)

    def one(row: dict) -> tuple[dict, list[dict]]:
        row = dict(row)
        index = row['index']; target = out / 'objects' / f'{index:05d}.o'
        target.unlink(missing_ok=True)
        if row['status'] != 'compiled':
            return row, []
        try:
            if digest(Path(row['source'])) != row['source_sha256']:
                raise ValueError('Changed input source: ' + row['source'])
            if index not in affected:
                os.link(base / 'objects' / target.name, target)
                row['command'] = row['command'].copy()
                row['command'][row['command'].index('-o') + 1] = str(target)
                return row, []
            if row['command'][row['command'].index('-x') + 1] != 'c++':
                raise ValueError('Native C++ signature referenced without C++ type information')
            pp = out / 'preprocessed' / f'{index:05d}.ii'
            expanded = run_checked(strip_compile_io(row['command']) + ['-E', '-P', row['source']], output=pp)
            command = expanded_command(row['command'], str(pp))
            ast = json.loads(run_checked(command + ['-Xclang', '-ast-dump=json', '-fsyntax-only']))
            converted, evidence = transform(expanded, ast)
            if not evidence:
                raise ValueError('Referenced native signatures missing from the AST')
            adapted = out / 'tagged' / pp.name
            adapted.write_bytes(converted)
            command = expanded_command(row['command'], str(adapted))
            source = command.pop()
            command += ['-c', source, '-o', str(target)]
            run_checked(command)
            (out / 'signatures' / f'{index:05d}.json').write_text(json.dumps(evidence, indent=2))
            row.update(source=str(adapted), source_sha256=digest(adapted), command=command,
                       object_bytes=target.stat().st_size, status='compiled', returncode=0,
                       signature_input_sha256=hashlib.sha256(expanded).hexdigest())
            return row, evidence
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            target.unlink(missing_ok=True)
            row.update(status='failed', returncode=1, first_error=str(error)[:800])
            (out / 'errors' / f'{index:05d}.txt').write_text(str(error))
            return row, []

    rows = []; evidence = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for row, entries in pool.map(one, first['results']):
            rows.append(row)
            if entries:
                evidence[row['index']] = entries
    report = {**first, 'scope': 'Full native inventory with reviewed C++ signature tags; NOT gameplay',
              'counts': dict(Counter(r['status'] for r in rows)), 'results': rows}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    subprocess.run([sys.executable, str(Path(__file__).with_name('link_inventory.py')),
                    '--build', str(args.build), '--report', str(out), '--ndk', str(args.ndk)], check=False)
    providers = retention(base / 'link-audit/defined-symbols.txt', out / 'link-audit/defined-symbols.txt', evidence)
    (out / 'signature-retention.json').write_text(json.dumps(providers, indent=2))
    final = json.loads((out / 'link-audit/report.json').read_text())
    summary = {'selected_units': first['total'], 'affected_units': len(affected),
               'counts': report['counts'], 'provider_retention': providers['passed'],
               'duplicates_before': audit['strong_duplicate_symbol_groups'],
               'duplicates_after': final['strong_duplicate_symbol_groups'],
               'undefined_symbols': len(final['undefined_symbols']),
               'link_returncode': final['link_returncode'], 'gameplay': 'NOT RUN'}
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return int(not providers['passed'] or final['link_returncode'] != 0 or
               any(r['status'] != 'compiled' for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
