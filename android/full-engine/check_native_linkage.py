#!/usr/bin/env python3
"""Execute linkage, real render dispatch, fader-slot and controller probes.

These exercise adapters and original bodies, not a running game. ARM32 probes
also use the original object layouts; host probes cover data/function aliases
and all controller slots. An empty --runner means compile/link only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shlex
import subprocess

from native_virtual_calls import transform as virtual_calls
from native_signatures import transform as signature_tags
from resolve_linkage import fader_source, validate_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', required=True)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--cc', default='gcc')
    parser.add_argument('--objcopy', default='objcopy')
    parser.add_argument('--flags', default='')
    parser.add_argument('--runner', default='native')
    parser.add_argument('--arm-layout', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    flags = shlex.split(args.flags)
    common = ['-O2', '-fno-strict-aliasing', '-ffunction-sections', '-fdata-sections',
              '-I' + str(root / 'include'), '-I' + str(root / 'port'),
              '-I' + str(root / 'port/ntr/include')]
    commands, results = [], []

    def run(command: list[str], name: str, expect_success: bool = True):
        commands.append(command)
        result = subprocess.run(command, capture_output=True, timeout=90)
        (out / (name + '.log')).write_bytes(result.stdout + result.stderr)
        if expect_success and result.returncode:
            raise RuntimeError(name + ': ' + (result.stdout + result.stderr).decode(errors='replace')[-8000:])
        return result

    def compile_source(source: Path, name: str, extra: list[str] | None = None) -> Path:
        obj = out / (name + '.o')
        c = source.suffix == '.c'
        run([args.cc if c else args.cxx, *flags, '-std=c11' if c else '-std=c++17',
             *common, *(extra or []), '-c', str(source), '-o', str(obj)], name + '-compile')
        return obj

    def adapt(source: Path, name: str, transform) -> Path:
        pp = out / (name + '.ii')
        expanded = run([args.cxx, *flags, '-std=c++17', *common, '-E', '-P', str(source)], name + '-preprocess').stdout
        pp.write_bytes(expanded)
        ast_flags = ['--target=armv7a-linux-gnueabihf'] if args.arm_layout else []
        command = [args.clang, *ast_flags, '-x', 'c++-cpp-output', '-std=c++17',
                   '-Xclang', '-ast-dump=json', '-fsyntax-only', str(pp)]
        ast = json.loads(run(command, name + '-ast').stdout)
        converted, evidence = transform(expanded, ast)
        if not evidence:
            raise ValueError('No adapted expressions in ' + str(source))
        pp.write_bytes(converted)
        (out / (name + '-evidence.json')).write_text(json.dumps(evidence, indent=2))
        return compile_source(pp, name)

    def executable(name: str, objects: list[Path]) -> None:
        exe = out / name
        run([args.cxx, *flags, '-Wl,--gc-sections', *map(str, objects), '-o', str(exe)], name + '-link')
        result = {'test': name, 'compile_link': 'PASS', 'execution': 'NOT RUN'}
        if args.runner:
            runner = [] if args.runner == 'native' else shlex.split(args.runner)
            run([*runner, str(exe)], name + '-run')
            result['execution'] = 'PASS'
        results.append(result)

    aliases = validate_manifest(json.loads((here / 'linkage_aliases.json').read_text()))
    caller = out / 'alias-caller.cpp'
    caller.write_text('''#include <cassert>
extern "C" int WithMeshClsn_IsOnGround(const void*);
extern "C" int IceSheet_ModelFile[];
extern "C" int data_ov018_02113c84[];
int main() {
  unsigned object[5] = {};
  assert(WithMeshClsn_IsOnGround(object)==0);
  object[4]=16;assert(WithMeshClsn_IsOnGround(object)==16);
  object[4]=0xffffffef;assert(WithMeshClsn_IsOnGround(object)==0);
  IceSheet_ModelFile[1]=12345;
  assert(IceSheet_ModelFile==data_ov018_02113c84 && data_ov018_02113c84[1]==12345);
}
''')
    data = out / 'alias-data.cpp'; data.write_text('extern "C" { int data_ov018_02113c84[2] = {}; }\n')
    caller_obj = compile_source(caller, 'alias-caller')
    ground_obj = compile_source(root / 'src/_ZNK12WithMeshClsn10IsOnGroundEv.c', 'ground',
                                ['-D_ZNK12WithMeshClsn10IsOnGroundEv=sm64ds_cabi_ZNK12WithMeshClsn10IsOnGroundEv'])
    data_obj = compile_source(data, 'alias-data')
    negative = run([args.cxx, *flags, str(caller_obj), str(ground_obj), str(data_obj),
                    '-o', str(out / 'unadapted-alias')], 'unadapted-link', False)
    if negative.returncode == 0 or b'WithMeshClsn_IsOnGround' not in negative.stderr:
        raise ValueError('Unadapted alias negative control did not fail as expected')
    mapping = out / 'alias-map.txt'
    mapping.write_text(''.join(s + ' ' + aliases[s] + '\n' for s in ('WithMeshClsn_IsOnGround', 'IceSheet_ModelFile')))
    adapted = out / 'alias-caller-adapted.o'
    run([args.objcopy, '--redefine-syms=' + str(mapping), str(caller_obj), str(adapted)], 'alias-objcopy')
    executable('aliases', [adapted, ground_obj, data_obj])
    executable('controls', [compile_source(here / 'native_controls.cpp', 'controls'),
                            compile_source(here / 'linkage-tests/controls.cpp', 'controls-main')])

    if args.arm_layout:
        objects = [adapt(root / ('src/' + filename), 'render-' + str(i), virtual_calls)
                   for i, filename in enumerate(('_ZN10BulletBill6RenderEv.cpp', '_ZN10FlameChomp6RenderEv.cpp',
                                                 '_ZN11BabyPenguin6RenderEv.cpp', '_ZN9Butterfly6RenderEv.cpp'))]
        executable('render', objects + [compile_source(here / 'linkage-tests/render.cpp', 'render-main')])
        next_obj = adapt(root / 'src/_ZN18NestedHeapIterator4NextEP13HeapAllocator.cpp', 'next-provider', signature_tags)
        next_source = out / 'next-caller.cpp'
        missing = '_ZN18NestedHeapIterator4NextB28sm64ds_ret_HeapAllocator_ptrEP13HeapAllocator'
        next_source.write_text('''#include <cassert>
#include <cstring>
extern "C" void *next_ptr(void*,void*) asm("''' + missing + '''");
int main() {
  static_assert(sizeof(void*)==4);
  alignas(4) unsigned char iterator[12]{}, node[32]{};
  int sentinel=42;void *expected=&sentinel;
  std::memcpy(iterator,&expected,4);
  assert(next_ptr(iterator,nullptr)==expected);
  unsigned short offset=12;std::memcpy(iterator+10,&offset,2);
  std::memcpy(node+16,&expected,4);assert(next_ptr(iterator,node)==expected);
  std::memset(node+16,0,4);assert(next_ptr(iterator,node)==nullptr);
}
''')
        next_call = compile_source(next_source, 'next-caller')
        next_map = out / 'next-map.txt'; next_map.write_text(missing + ' ' + aliases[missing] + '\n')
        next_adapted = out / 'next-adapted.o'
        run([args.objcopy, '--redefine-syms=' + str(next_map), str(next_call), str(next_adapted)], 'next-objcopy')
        executable('next-pointer', [next_obj, next_adapted])
        smart_objects = [compile_source(root / ('src/func_ov006_' + addr + '.c'), 'smart-' + addr)
                         for addr in ('02114724', '02114720', '02114738')]
        executable('smartball', smart_objects + [compile_source(here / 'smartball_native.cpp', 'smart-native'),
                                                compile_source(here / 'linkage-tests/smartball.cpp', 'smart-main')])
        original = (root / 'port/hal/fader_wipes.cpp').read_bytes()
        start = original.index(b'struct HalFaderWipe {')
        end = original.index(b'\n};', start) + 3
        fader = out / 'fader.cpp'
        fader.write_bytes((here / 'linkage-tests/fader_prefix.cpp').read_bytes() + b'\n' +
                          fader_source(original[start:end]) + b'\n' +
                          (here / 'linkage-tests/fader_main.cpp').read_bytes())
        executable('fader', [compile_source(fader, 'fader')])
    (out / 'report.json').write_text(json.dumps({'scope': 'Native linkage probes; NOT gameplay',
        'arm32_original_layouts': args.arm_layout, 'negative_control': 'PASS',
        'results': results, 'commands': commands}, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
