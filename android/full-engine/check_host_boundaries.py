#!/usr/bin/env python3
"""Build native memory/scene/actor boundary probes; execution is opt-in."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
from adapt_sources import validate
from adapt_host_boundaries import transform


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cxx', default='g++')
    ap.add_argument('--flags', default='')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--runner', default='')
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for path, rule in json.loads((here/'host_portability.json').read_text())['sources'].items():
        raw = (root/path).read_bytes()
        validate(raw, rule['sha256'], path)
        native = transform((root/path).read_text(), rule['native_boundary'])
        (out/('native_'+rule['native_boundary']+'.inc')).write_text(native)
    # The probes use only weak data enrollment, not the complete game's layout.
    compat = out/'probe_compat.h'
    compat.write_text('#define SM64DS_PROBE_selectany __attribute__((weak))\n'
                      '#define __declspec(x) SM64DS_PROBE_##x\n')
    records = []
    for name in ('memory', 'rollback', 'oam', 'actor'):
        exe = out/(name+'_probe')
        cmd = [args.cxx, *shlex.split(args.flags), '-std=c++17', '-O2', '-g',
               '-fno-strict-aliasing', '-fwrapv', '-ffunction-sections', '-fdata-sections',
               '-Wl,--gc-sections', '-include', str(compat), '-I'+str(out), '-I'+str(here),
               '-I'+str(root/'port/hal'), '-I'+str(root/'port/ntr/include'),
               str(here/'host-tests'/f'{name}.cpp'), '-ldl', '-o', str(exe)]
        run = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out/(name+'-build.log')).write_text(run.stdout)
        if run.returncode:
            raise RuntimeError(name+' did not compile:\n'+run.stdout[-10000:])
        entry = {'test': name, 'command': cmd, 'execution': 'NOT RUN'}
        if args.runner:
            runner = [] if args.runner == 'native' else shlex.split(args.runner)
            env = dict(os.environ)
            for key in ('SM64DS_FAULTS_FATAL', 'SM64DS_NO_OAM_CHECK', 'SM64DS_ERROR_DIR', 'SM64DS_T3_WATCH'):
                env.pop(key, None)
            run = subprocess.run([*runner, str(exe)], env=env, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=45)
            (out/(name+'-run.log')).write_text(run.stdout)
            print(run.stdout, end='')
            if run.returncode:
                raise RuntimeError(name+' execution failed: '+str(run.returncode))
            entry['execution'] = 'PASS'
            if name == 'actor':
                for arg in ('hardware', 'fatal'):
                    fail = subprocess.run([*runner, str(exe), arg], env=env, text=True,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                    (out/('actor-'+arg+'.log')).write_text(fail.stdout)
                    # Native runner returns -SIGNAL; QEMU shells may use 128+SIGNAL.
                    expected = (-11, 139) if arg == 'hardware' else (-6, 134)
                    if fail.returncode not in expected:
                        raise RuntimeError('Unexpected '+arg+' fault result: '+str(fail.returncode))
                print('PASS: actual memory fault and forced-fatal decline terminate separate processes')
        records.append(entry)
    (out/'report.json').write_text(json.dumps({'scope':'Native boundary probes; not game, ROM or Android device validation','results':records},indent=2)+'\n')
    if not args.runner:
        print('COMPILED AND LINKED ONLY: native host boundary probes, no execution claimed')

if __name__ == '__main__':
    main()
