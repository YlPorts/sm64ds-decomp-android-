#!/usr/bin/env python3
"""Exercise actual link conflicts before/after explicit-identifier isolation.

Fixtures are synthetic and intentionally not game objects. Their purpose is to
prove a native method and a recovered literal spelling remain distinct, including
converting wrappers that must NOT be removed. Baseline failure is required.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
from isolate_symbols import header_text

NAMES=['_ZN5Mixer5ApplyEi','_ZN5Mixer6VectorEi','_ZN6RecordC1Ev','_ZN7CleanupD1Ev','_ZTV4Face']

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--cc',default='cc');p.add_argument('--cxx',default='c++')
 p.add_argument('--flags',default='');p.add_argument('--runner',default='')
 p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 fixtures=Path(__file__).resolve().parent/'isolation-tests'
 header=out/'isolated.h';header.write_text(header_text(NAMES))
 commands=[]
 def run(cmd,log):
  commands.append(cmd);s=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
  (out/log).write_text(s.stdout);return s
 def compile_set(isolate):
  tag='isolated' if isolate else 'baseline';objects=[]
  for source in ['caller.c','methods.cpp','bridges.cpp','main.cpp']:
   obj=out/(tag+'-'+source+'.o');c=source.endswith('.c')
   cmd=[a.cc if c else a.cxx,'-std=c11' if c else '-std=c++17','-O2','-fno-strict-aliasing',*shlex.split(a.flags)]
   if isolate:cmd+=['-include',str(header)]
   cmd+=['-I',str(fixtures),'-c',str(fixtures/source),'-o',str(obj)]
   r=run(cmd,tag+'-'+source+'.log')
   if r.returncode:raise RuntimeError(r.stdout)
   objects.append(str(obj))
  return objects
 failed=run([a.cxx,*shlex.split(a.flags),*compile_set(False),'-o',str(out/'must-not-link')],'baseline-link.log')
 if not failed.returncode or not any(x in failed.stdout for x in ['multiple definition','duplicate symbol']):
  raise RuntimeError('Baseline did not fail with the required duplicate-symbol diagnostic')
 exe=out/'isolation-tests'
 linked=run([a.cxx,*shlex.split(a.flags),*compile_set(True),'-o',str(exe)],'isolated-link.log')
 if linked.returncode:raise RuntimeError(linked.stdout)
 status='COMPILED AND LINKED ONLY'
 if a.runner:
  ran=run([*([] if a.runner=='native' else shlex.split(a.runner)),str(exe)],'run.log')
  if ran.returncode:raise RuntimeError(ran.stdout)
  print(ran.stdout,end='');status='PASS'
 report={'scope':'Synthetic cross-language/name/return-conversion probe, NOT game execution',
         'baseline_duplicate_link_failure_verified':True,'isolated_link_passed':True,
         'execution':status,'commands':commands}
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(status)
if __name__=='__main__':main()
