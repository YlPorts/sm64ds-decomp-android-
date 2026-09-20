#!/usr/bin/env python3
"""Build and optionally run a C-to-C++ probe using original recovered method bodies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shlex
import subprocess
from adapt_native_faces import elide, manifest, ROOT, HERE
import hashlib

SYMBOLS = '''_ZN12CylinderClsn5ClearEv _ZN12CylinderClsn6UpdateEv
_ZN12WithMeshClsn13SetGroundFlagEv _ZN12WithMeshClsn13SetLimMovFlagEv
_ZN12WithMeshClsn15ClearGroundFlagEv _ZN12WithMeshClsn15ClearLimMovFlagEv
_ZN12WithMeshClsn19ClearAllGroundFlagsEv _ZN5Timer10ResetTimerEv
_ZN5Timer10StartTimerEv _ZN5Timer9StopTimerEv _ZN5Timer7GetTimeEv'''.split()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cc',required=True);ap.add_argument('--cxx',required=True)
    ap.add_argument('--flags',default='');ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--runner',default='');args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    rules=manifest();src=ROOT/rules['face_source']
    if hashlib.sha256(src.read_bytes()).hexdigest()!=rules['face_sha256']:
        raise ValueError('Unreviewed native faces')
    faces=out/'method_faces.cpp';faces.write_text(elide(src.read_text(),rules['faces']))
    sources=[faces]+[ROOT/next(f['provider'] for f in rules['faces'] if f['symbol']==symbol) for symbol in SYMBOLS]
    sources.append(HERE/'face-tests/caller.c')
    objects=[];commands=[]
    for i,source in enumerate(sources):
        obj=out/f'{i}.o';objects.append(obj)
        cmd=[args.cc if source.suffix=='.c' else args.cxx,*shlex.split(args.flags),
             '-std=c11' if source.suffix=='.c' else '-std=c++17','-O2','-fno-strict-aliasing',
             '-ffunction-sections','-fdata-sections','-I'+str(ROOT/'include'),'-I'+str(ROOT/'port'),
             '-c',str(source),'-o',str(obj)]
        run=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        (out/f'{i}-build.log').write_text(run.stdout);commands.append(cmd)
        if run.returncode:raise RuntimeError(run.stdout[-6000:])
    exe=out/'native_face_probe'
    cmd=[args.cxx,*shlex.split(args.flags),*[str(p) for p in objects],'-Wl,--gc-sections','-o',str(exe)]
    run=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    (out/'link.log').write_text(run.stdout);commands.append(cmd)
    if run.returncode:raise RuntimeError(run.stdout[-6000:])
    status='COMPILED AND LINKED ONLY'
    if args.runner:
        cmd=[*([] if args.runner=='native' else shlex.split(args.runner)),str(exe)]
        run=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
        (out/'run.log').write_text(run.stdout);commands.append(cmd)
        if run.returncode:raise RuntimeError(run.stdout)
        print(run.stdout,end='');status='PASS'
    (out/'report.json').write_text(json.dumps({'scope':'11 original method providers, actual adapted face unit; narrow ABI probe, not full engine', 'execution':status,'commands':commands},indent=2)+'\n')
    print(status+'; Android physical-device execution not claimed')

if __name__=='__main__':main()
