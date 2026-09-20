#!/usr/bin/env python3
"""Build 5 original providers and their original bridge units with isolated names.

This is a narrow 32-bit probe. A test-only Animation destructor, Player storage,
Sound boundary and linker GC isolate the functions under examination. The full
engine audit independently DISABLES GC. No game scenario is run by this script.
"""
import argparse, hashlib, json, shlex, subprocess
from pathlib import Path
from isolate_symbols import header_text
SOURCES=['port/hal/anim_bridge.cpp','src/_ZN9Animation8SetFlagsEi.cpp',
 'src/_ZNK9Animation13GetFrameCountEv.cpp','port/unmatched/Klepto_PathPtrFaces.cpp',
 'src/_ZN7PathPtrC1Ev.c','port/hal/reverse_bridges.cpp',
 'src/_ZN6Player7IsStateERNS_5StateE.c','port/hal/bob_enemy_shadow_faces.cpp',
 'src/_ZN5Sound13Func_02048eb4Ev.cpp']
# This is the same full first-pass collision map used by the full engine replay;
# it must be passed explicitly so the probes cannot silently test another map.
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--cc',required=True);p.add_argument('--cxx',required=True)
 p.add_argument('--flags',default='');p.add_argument('--runner',default='')
 p.add_argument('--header',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();here=Path(__file__).resolve().parent;root=here.parent.parent
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 commands=[];objects=[];hashes={}
 sources=[root/s for s in SOURCES]+[here/'isolation-tests'/s for s in ['original_animation.cpp','original_main.cpp']]
 for i,src in enumerate(sources):
  obj=out/f'{i:02d}.o';objects.append(str(obj));hashes[str(src.relative_to(root))]=hashlib.sha256(src.read_bytes()).hexdigest()
  cmd=[a.cc if src.suffix=='.c' else a.cxx,*shlex.split(a.flags),'-std=c11' if src.suffix=='.c' else '-std=c++17',
   '-O2','-fno-strict-aliasing','-ffunction-sections','-fdata-sections','-include',str(a.header.resolve()),
   '-I'+str(root/'include'),'-I'+str(root/'port'),'-c',str(src),'-o',str(obj)]
  commands.append(cmd);r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
  (out/f'{i:02d}-compile.log').write_text(r.stdout)
  if r.returncode:raise RuntimeError(r.stdout)
 exe=out/'original-isolation-probe';cmd=[a.cxx,*shlex.split(a.flags),*objects,'-Wl,--gc-sections','-o',str(exe)]
 commands.append(cmd);r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
 (out/'link.log').write_text(r.stdout)
 if r.returncode:raise RuntimeError(r.stdout)
 execution='COMPILED AND LINKED ONLY'
 if a.runner:
  cmd=[*([] if a.runner=='native' else shlex.split(a.runner)),str(exe)];commands.append(cmd)
  r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
  (out/'run.log').write_text(r.stdout)
  if r.returncode:raise RuntimeError(r.stdout)
  print(r.stdout,end='');execution='PASS'
 (out/'report.json').write_text(json.dumps({'scope':__doc__,'execution':execution,'source_sha256':hashes,
  'header_sha256':hashlib.sha256(a.header.read_bytes()).hexdigest(),'commands':commands},indent=2)+'\n')
 print(execution)
if __name__=='__main__':main()
