#!/usr/bin/env python3
"""Compile/test native input and the full adapted sub-screen touch path.

No runner means compile and link only. Layout and missing game services in the
sub-screen test are explicitly fixtures; the production touch functions are
compiled unabridged. No Activity, Surface or physical device is exercised.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shlex
import subprocess
from adapt_sources import load_manifest, transform, validate

TEST_ACCESS = r'''
#ifdef SM64DS_INPUT_TEST
// Test-only access to the existing internal poller: no production replacement.
extern "C" void sm64ds_test_touch_config(int stacked,int x,int y,int divisor) {
    g_stacked=stacked;g_on=true;g_headless=false;g_nofocusgate=false;
    g_hwnd=reinterpret_cast<void*>(1);g_x0=x;g_y0=y;g_div=divisor;g_tp_n=0;
}
extern "C" void sm64ds_test_poll_touch() {poll_touch();}
#endif
'''

def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cxx',required=True);p.add_argument('--flags',default='')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--runner',help='native for current host, or an explicit runner prefix')
    p.add_argument('--android',action='store_true',help='Link real NDK input accessors with libandroid')
    a=p.parse_args();here=Path(__file__).resolve().parent;root=here.parents[1]
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    source=root/'port/hal/sub_screen.cpp';rule=load_manifest()['sources']['port/hal/sub_screen.cpp']
    validate(source.read_bytes(),rule['sha256'],str(source))
    adapted=out/'sub_screen_native_test.cpp'
    adapted.write_text(transform(source.read_text(),rule)+TEST_ACCESS)
    common=[a.cxx,*shlex.split(a.flags),'-std=c++17','-O2','-pthread',
            '-fno-strict-aliasing','-fwrapv','-ffunction-sections','-fdata-sections',
            '-Werror=ignored-attributes','-Wl,--gc-sections','-I'+str(here),
            '-I'+str(root/'port'),'-I'+str(root/'port/ntr/include')]
    commands=[];logs=[]
    try:
        for name,sources,flags in [
            ('input', [here/'pad_android.cpp',here/'input-tests/input.cpp'], []),
            ('touch', [adapted,here/'pad_android.cpp',here/'input-tests/touch.cpp'], ['-DSM64DS_INPUT_TEST']),
        ]:
            exe=out/name
            cmd=common+flags+list(map(str,sources))+(['-landroid'] if a.android else [])+['-o',str(exe)]
            commands.append(cmd)
            run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=40)
            (out/(name+'.build.log')).write_text(run.stdout)
            if run.returncode:raise RuntimeError(name+' build failed:\n'+run.stdout[-6000:])
            if a.runner is not None:
                prefix=[] if a.runner=='native' else shlex.split(a.runner)
                command=prefix+[str(exe)];commands.append(command)
                run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
                logs.append(run.stdout);print(run.stdout,end='',flush=True)
                if run.returncode:raise RuntimeError(name+' execution failed: '+str(run.returncode))
    finally:
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        if logs:(out/'execution.log').write_text(''.join(logs))
    print('Android input/touch: '+('EXECUTED with OS/layout fixtures; no Android device' if a.runner is not None else 'COMPILED AND LINKED ONLY; no execution'))

if __name__=='__main__':main()
