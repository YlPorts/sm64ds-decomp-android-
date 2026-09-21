#!/usr/bin/env python3
"""Replace LINK-ONLY resources in a verified inventory with ROM-clean tables.

Run prepare_rom.py first. Nintendo bytes stay in build/assets and extracted;
the compiled tables contain zero initializers and relocation code only.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(cmd):
    p = subprocess.run(list(map(str, cmd)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(p.stdout.decode(errors='replace'))
    return p.stdout


def verify_packed_layout(llvm, sources, executable, output):
    """Check the generator's ROM-relative offsets in the final ELF as well."""
    names = {}
    for line in run([llvm/'llvm-nm', '--defined-only', '--format=posix', executable]).decode().splitlines():
        fields = line.split()
        if len(fields) >= 3:
            names[fields[0]] = int(fields[2], 16)
    checked, errors = 0, []
    for source in sources.glob('ov*_syms.c'):
        body = source.read_text()
        base = re.search(r'const u8 \*base = (\w+);', body)
        if not base:
            continue
        base = base[1]
        for symbol, delta in re.findall(r'if \((\w+) - base != (\d+)\)', body):
            checked += 1
            actual = names[symbol] - names[base] if symbol in names and base in names else None
            if actual != int(delta):
                errors.append(dict(source=source.name, symbol=symbol, expected=int(delta), actual=actual))
    if not checked:
        raise ValueError('No packed ROM offsets were checked')
    output.write_text(json.dumps(dict(checked=checked, errors=errors), indent=2)+'\n')
    if errors:
        raise ValueError(f'{len(errors)} packed ROM offsets differ: {output}')
    print(f'Packed ROM offsets: {checked} checked, zero mismatches', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--build', type=Path, required=True)
    ap.add_argument('--ndk', type=Path, required=True)
    ap.add_argument('--jobs', type=int, default=4)
    args = ap.parse_args()
    base, out = args.baseline.resolve(), args.output.resolve()
    if base == out or out.is_relative_to(base):
        raise ValueError('Output must be separate from baseline')
    audit = json.loads((base/'link-audit/report.json').read_text())
    if audit['link_returncode'] or audit['uncompiled_units'] or audit['strong_duplicate_symbol_groups']:
        raise ValueError('Baseline must have a complete, unambiguous link')
    report = json.loads((base/'report.json').read_text())
    real = ROOT/'build/port/host-src'
    assets = ROOT/'build/assets'
    env = dict(os.environ)
    env.pop('SM64DS_LINK_ONLY', None)
    for script, params in [
        ('romblob_verify.py', [ROOT, ROOT/'build/port', assets/'romdata.manifest', assets/'romdata.bin']),
        ('romblob_recipe.py', [assets/'romdata.manifest', assets/'romdata.recipe.tsv']),
    ]:
        subprocess.run([sys.executable, str(ROOT/'port/tools'/script), *map(str, params)],
                       env=env, check=True)
    # The cross-overlay fixups also depend on the actual extracted images.
    subprocess.run([sys.executable, str(ROOT/'port/tools/ovdata.py'), '--cross',
                    str(real/'ov_cross.c'), *map(str, sorted(real.glob('ov*.c.map')))],
                   env=env, check=True)
    (out/'objects').mkdir(parents=True, exist_ok=True)
    (out/'sources').mkdir(exist_ok=True)
    llvm = args.ndk.resolve()/'toolchains/llvm/prebuilt/linux-x86_64/bin'
    def one(old):
        row = dict(old)
        target = out/'objects'/f"{row['index']:05d}.o"
        target.unlink(missing_ok=True)
        source = Path(row['source'])
        candidate = real/Path(row['original_source']).name
        changed = False
        if row['generated'] and candidate.exists():
            body = candidate.read_text()
            changed = True
            if 'LINK-ONLY' in body:
                raise ValueError('Synthetic runtime source: '+str(candidate))
            # MSVC keeps explicitly placed internal padding; Clang otherwise
            # discards these unreferenced arrays even at -O0. Their bytes make
            # the packed symbol offsets, and must survive before the linker.
            body = '#undef SM64DS_DECLSPEC_allocate\n#define SM64DS_DECLSPEC_allocate(s) __attribute__((section(s),used))\n'+body
            body = re.sub(r'^#pragma data_seg\("\.dsstate\$mmm"\)', '#pragma clang section data=".sm64ds_state_data"',body,flags=re.M)
            body = re.sub(r'^#pragma bss_seg\("\.dsstate\$mmm"\)', '#pragma clang section bss=".sm64ds_state_bss"',body,flags=re.M)
            body = body.replace('#pragma data_seg()', '#pragma clang section data=""').replace('#pragma bss_seg()', '#pragma clang section bss=""')
            source = out/'sources'/candidate.name
            source.write_text(body)
        elif source.name == 'native_scene_main.cpp':
            changed = True
        elif Path(row['original_source']).name in ('func_ov007_020c3550.c', 'func_ov007_020c99d8.c'):
            # The cartridge returns the allocated OBJ descriptor in r0 across
            # both epilogues (ov007 020c3570..020c3594 and 020c9a1c..020c9a28).
            # A void definition / falling off an int function loses that value
            # under Clang; keep it explicit in the native generated copies.
            body = source.read_text()
            if Path(row['original_source']).name == 'func_ov007_020c3550.c':
                before = 'void func_ov007_020c3550(int a, int b, int c, int d)'
                if body.count(before) != 1 or body.count('  *(unsigned char*)(p+0xa) = 0;') != 1:
                    raise ValueError('OBJ descriptor constructor source changed')
                body = body.replace(before, 'int func_ov007_020c3550(int a, int b, int c, int d)')
                body = body.replace('  *(unsigned char*)(p+0xa) = 0;', '  *(unsigned char*)(p+0xa) = 0;\n  return (int)p;')
            else:
                before = 'extern void func_ov007_020c3550(int a, int b, int c, int d);'
                call = '    func_ov007_020c3550((int)((char *)ip + 0xc), b, c, d);'
                if body.count(before) != 1 or body.count(call) != 1:
                    raise ValueError('OBJ descriptor loader source changed')
                body = body.replace(before, before.replace('extern void ', 'extern int ')).replace(call, call.replace('    func_', '    return func_'))
            source = out/'sources'/f"{row['index']:05d}.c"
            source.write_text(body)
            changed = True
        elif Path(row['original_source']).name == 'func_0205d568.c':
            # FS_OpenFileFast receives FSFileID by value (archive pointer,
            # file index). ARM EABI passes both words in r1/r2; reading past
            # the address of a local parameter is not a varargs implementation.
            body = source.read_text()
            before = 'int func_0205d568(Node *node, int b, ...)'
            read = '        int c = *(int *)((char *)&b + 4);'
            if body.count(before) != 1 or body.count(read) != 1:
                raise ValueError('FS_OpenFileFast source changed')
            body = body.replace(before, 'int func_0205d568(Node *node, int b, int c)').replace(read, '')
            source = out/'sources'/f"{row['index']:05d}.c"
            source.write_text(body)
            changed = True
        if Path(row['original_source']).name in ('actor_vtables.cpp', 'stage_globals.cpp'):
            body = source.read_text()
            kind = 'u' if Path(row['original_source']).name == 'stage_globals.cpp' else ''
            helper = 'sm64ds_unsigned_quotient' if kind else 'sm64ds_signed_quotient'
            pattern = r'(int __aeabi_idiv\(int n, int d\)\s*\{)[^}]+}' if not kind else r'(unsigned int __aeabi_uidiv\(unsigned int n, unsigned int d\)\s*\{)[^}]+}'
            params = 'n, d'
            body, count = re.subn(pattern, lambda m:m[1]+' return '+helper+'('+params+'); }', body)
            if count != 1: raise ValueError('Divide helper source changed: '+str(source))
            source = out/'sources'/f"{row['index']:05d}.cpp"
            source.write_text('#include "'+str(HERE/'native_division.h')+'"\n'+body)
            changed = True
        command = row['command'].copy()
        command.insert(1, '-I'+str(ROOT/'port/hal'))
        command[0] = str(llvm/Path(command[0]).name)
        command[command.index('-o')+1] = str(target)
        if changed:
            command[command.index('-c')+1] = str(source)
            if source.name == 'native_scene_main.cpp':
                command.insert(1, '-DSM64DS_NATIVE_REAL_RESOURCES')
            run(command)
            rename = base/'renames'/f"{row['index']:05d}.txt"
            if rename.exists():
                run([llvm/'llvm-objcopy', '--redefine-syms='+str(rename), target])
        else:
            if row['generated'] and 'LINK-ONLY-BUILD-NOT-A-GAME' in source.read_text():
                raise ValueError('Missing real resource replacement: '+str(source))
            os.link(base/'objects'/target.name, target)
        row.update(source=str(source), command=command,
                   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   object_bytes=target.stat().st_size)
        if changed:
            row['abi_review'] = ['Recompiled with verified real-ROM recipe; zeroed runtime tables']
        return row, changed
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(one, report['results']))
    source = HERE/'native_early_memory.cpp'
    index = max(r['index'] for r,c in results)+1
    obj = out/'objects'/f'{index:05d}.o'
    command = [str(llvm/'armv7a-linux-androideabi23-clang++'), '-std=c++17', '-fPIC',
               '-I'+str(ROOT/'port/ntr/include'), '-c', str(source), '-o', str(obj)]
    run(command)
    results.append((dict(index=index, target='walk_window', generated=False, source=str(source),
                        original_source=str(source), command=command, status='compiled', returncode=0,
                        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                        object_bytes=obj.stat().st_size), True))
    report.update(results=[r for r,c in results], resource_mode='real-ROM recipe; ROM-clean zero-initialized tables')
    report.update(total=len(results), counts={'compiled':len(results)})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Recompiled', sum(c for r,c in results), 'runtime units', flush=True)
    subprocess.run([sys.executable, str(HERE/'link_inventory.py'), '--build', str(args.build),
                    '--report', str(out), '--ndk', str(args.ndk)], check=True)
    verify_packed_layout(llvm, out/'sources', out/'link-audit/engine-link-diagnostic',
                         out/'packed-layout.json')


if __name__ == '__main__':
    main()
