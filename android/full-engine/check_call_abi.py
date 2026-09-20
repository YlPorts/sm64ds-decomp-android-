#!/usr/bin/env python3
"""Compile/optionally run 32-bit ABI probes from pinned real and synthetic sources."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
from adapt_calls import adapt, masked, close_at


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compiler',required=True)
    ap.add_argument('--flags',default='')
    ap.add_argument('--runner',default='')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--objects-only',action='store_true')
    args=ap.parse_args()
    here=Path(__file__).resolve().parent;root=here.parents[1]
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((here/'call_abi_inputs.json').read_text())['probe_sha256']
    for rel,digest in manifest.items():
        if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=digest:raise ValueError('Unreviewed probe source: '+rel)
    p=root/'port/hal/actor_slot30_seat.cpp'
    seat=out/'actor_slot30_native.cpp';seat.write_text(adapt(p.read_text())[0])
    p=root/'port/hal/actor_classes_wf_enemy.cpp';text=p.read_text()
    c=masked(text);m=re.search(r'static void\s*\*__fastcall whomp_s30\(',c)
    if not m:raise ValueError('Missing reviewed Whomp seat')
    end=close_at(c,c.index('{',m.start()))
    thunk=adapt(text[m.start():end+1])[0]
    w=out/'whomp_slot30_native.cpp'
    w.write_text('extern "C" void func_ov079_02123d4c(int*,char*);\n'+thunk+'\nextern "C" void *whomp_test_seat(){return (void*)whomp_s30;}\n')
    legacy=out/'native_thunks.cpp';legacy.write_text(adapt((here/'call-tests/legacy_thunks.cpp').read_text())[0])
    spec=importlib.util.spec_from_file_location('hostgen',root/'port/tools/hostgen.py')
    hg=importlib.util.module_from_spec(spec);spec.loader.exec_module(hg)
    generated,_=hg.emit(root/'src/func_02016ff4.cpp',out/'host-src',root,True)
    model=out/'model_caller_native.cpp';model.write_text(adapt(generated.read_text())[0])
    sources=[legacy,here/'call-tests/native_caller.cpp',here/'call-tests/runner.cpp',seat,w,
             root/'src/_ZN5Actor25OnAimedAtWithEggReturnVecEv.cpp',root/'src/func_ov079_02123d4c.cpp',model]
    exe=out/'sm64ds_call_abi_tests'
    cmd=[args.compiler,*shlex.split(args.flags),'-std=c++17','-O2','-fno-strict-aliasing','-fwrapv','-fno-rtti','-fno-exceptions',
         '-Werror=ignored-attributes','-include','stddef.h','-I'+str(here),'-I'+str(root/'port/ntr/include'),*map(str,sources),'-o',str(exe)]
    (out/'command.json').write_text(json.dumps(cmd,indent=2))
    if args.objects_only:
        prefix=cmd[:cmd.index(str(sources[0]))]
        for i,source in enumerate(sources):
            subprocess.run([*prefix,'-c',str(source),'-o',str(out/f'probe_{i}.o')],check=True)
        print(f'COMPILED {len(sources)} objects only; no link or execution claimed')
        return
    subprocess.run(cmd,check=True)
    if args.runner:
        subprocess.run([*shlex.split(args.runner),str(exe)],check=True,timeout=30)
    else:print('COMPILED ONLY: '+str(exe)+'; no execution claimed')

if __name__=='__main__':main()
