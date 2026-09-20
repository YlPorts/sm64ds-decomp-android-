#!/usr/bin/env python3
"""Build and optionally execute the stage-7 native services and recovered-source probes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
from adapt_sources import load_manifest, transform, validate


def build_tests(cc, cxx, flags, output, runner):
    here=Path(__file__).resolve().parent; root=here.parents[1]
    output.mkdir(parents=True,exist_ok=True)
    manifest=load_manifest(); sources=[];commands=[]
    def run(cmd):
        commands.append(cmd)
        subprocess.run(cmd,check=True,timeout=60)
    units=[('src/func_ov002_020e8c34.c','c'),('src/func_ov002_020e8dd8.c','c'),('src/func_ov014_0211150c.c','c'),
           ('src/RotatingFirebar_Spawn.cpp','c++'),('src/func_02056e98.c','c'),('src/func_020393d4.c','c')]
    common=[*flags,'-O2','-fno-strict-aliasing','-fwrapv','-Werror=return-type','-I'+str(root/'include'),'-I'+str(here)]
    for i,(rel,lang) in enumerate(units):
        source=root/rel
        if rel in manifest['probe_sha256']:
            validate(source.read_bytes(),manifest['probe_sha256'][rel],rel)
        if rel in manifest['sources']:
            rule=manifest['sources'][rel];validate(source.read_bytes(),rule['sha256'],rel)
            source=output/Path(rel).name;source.write_text(transform((root/rel).read_text(),rule))
        obj=output/f'{i}.o'
        run([cxx if lang=='c++' else cc,'-x',lang,'-std=c++17' if lang=='c++' else '-std=c11',*common,'-c',str(source),'-o',str(obj)])
        sources.append(str(obj))
    validate((root/'port/tools/hostgen.py').read_bytes(),manifest['hostgen_sha256'],'hostgen.py')
    spec=importlib.util.spec_from_file_location('hg',root/'port/tools/hostgen.py');hg=importlib.util.module_from_spec(spec);spec.loader.exec_module(hg)
    generated,_=hg.emit(root/'src/func_0205a290.c',output/'host-src',root,True)
    validate(generated.read_bytes(),manifest['generated_sha256']['src/func_0205a290.c'],'DMA generated input')
    source=output/'dma_native.cpp';source.write_text(transform(generated.read_text(),manifest['sources']['src/func_0205a290.c']))
    logic=output/'source_tests';services=output/'service_tests';tag=output/'tag_tests'
    run([cxx,'-std=c++17',*common,'-I'+str(root/'port/ntr/include'),*sources,str(source),str(here/'source-tests/logic.cpp'),'-o',str(logic)])
    run([cxx,'-std=c++17',*common,str(here/'source-tests/services.cpp'),'-ldl','-o',str(services)])
    rel='port/hal/instance_tag.h';rule=manifest['sources'][rel];validate((root/rel).read_bytes(),rule['sha256'],rel)
    header=output/'instance_tag_native.h';header.write_text(transform((root/rel).read_text(),rule))
    tag_src=output/'tag.cpp';tag_src.write_text('#include "instance_tag_native.h"\n#include <stdio.h>\nint main(){puts(port_instance_tag());}\n')
    run([cxx,'-std=c++17',*common,str(tag_src),'-o',str(tag)])
    (output/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    if runner:
        for exe in [logic,services]: subprocess.run([*runner,str(exe)],check=True,timeout=30)
        cases=[(None,''),('',''),('Ab-12_x','.Ab-12_x'),('../:!*',''),(' A/b.c?Z ','.AbcZ'),('x'*15,'.'+'x'*15),('x'*63,'.'+'x'*15),('x'*64,'')]
        for value,expected in cases:
            env=dict(os.environ);env.pop('SM64DS_INSTANCE',None)
            if value is not None:env['SM64DS_INSTANCE']=value
            proc=subprocess.run([*runner,str(tag)],check=True,text=True,stdout=subprocess.PIPE,env=env,timeout=10)
            if proc.stdout.strip()!=expected: raise RuntimeError('Instance sanitiser mismatch: '+repr(value))
        print('PASS: 8 instance-tag process cases',flush=True)
    else:print('COMPILED AND LINKED ONLY: no Android device execution claimed',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cc',required=True);ap.add_argument('--cxx',required=True)
    ap.add_argument('--flags',default='');ap.add_argument('--runner',default='')
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();build_tests(a.cc,a.cxx,shlex.split(a.flags),a.output.resolve(),shlex.split(a.runner))
