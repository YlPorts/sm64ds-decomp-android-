#!/usr/bin/env python3
"""Compile native audio/UDP boundaries and optionally execute them, not a game.

Audio mixer/device are labelled fixtures. UDP uses two real processes with the
complete upstream packet engine. Sources are pinned by source_portability.json.
No --runner means compilation/linking only (in particular Android NDK).
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import shlex
import subprocess
from adapt_calls import adapt, close_at, masked
from adapt_sources import transform, load_manifest, validate


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cxx',required=True)
    p.add_argument('--flags',default='')
    p.add_argument('--runner',default=None,help='Use "native" for current host or a command prefix')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[2]
    here=Path(__file__).resolve().parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    rules=load_manifest()['sources']
    def converted(rel: str) -> str:
        source=root/rel;data=source.read_bytes();validate(data,rules[rel]['sha256'],rel)
        text=data.decode('utf-8-sig')
        if '__cdecl' in masked(text):text=adapt(text)[0]
        return transform(text,rules[rel])
    (out/'native_comms_under_test.cpp').write_text(converted('port/hal/comms_loopback.cpp'))
    # Extract the exact installer bodies after adaptation. Their dependencies
    # are tiny explicit filter fixtures, not complete resource-loader execution.
    stage=converted('port/hal/stage_geom.cpp')
    start=stage.index('void  geom_install(void)');brace=stage.index('{',start)
    body=stage[start:close_at(masked(stage),brace)+1]
    mods=converted('port/hal/fs_mods.cpp')
    start=mods.index('struct InstallHooks {');brace=mods.index('{',start)
    installer=mods[start:close_at(masked(mods),brace)+1]+' g_install;\n'
    (out/'install_stage.cpp').write_text('''#include <cstdio>
extern "C" {extern unsigned (*port_fs_mod_filter)(unsigned,unsigned char**,unsigned);}
unsigned (*g_prev_filter)(unsigned,unsigned char**,unsigned);int g_chained;
unsigned geom_filter(unsigned id,unsigned char **p,unsigned n){return g_prev_filter(id,p,n)+1;}
'''+body+'\nextern "C" {void (*port_stage_geom_ctor)(void)=geom_install;}\n')
    (out/'install_mods.cpp').write_text('''extern "C" {unsigned (*port_fs_mod_filter)(unsigned,unsigned char**,unsigned)=nullptr;void *port_fs_mod_map=nullptr;extern void (*port_stage_geom_ctor)(void);}
unsigned mod_filter(unsigned,unsigned char**,unsigned n){return n*2;}
void *mod_map=nullptr;
'''+installer)
    (out/'install_main.cpp').write_text('''#include <cstdio>
extern "C" {extern unsigned (*port_fs_mod_filter)(unsigned,unsigned char**,unsigned);extern void (*port_stage_geom_ctor)(void);}
extern int g_chained;
int main(){if(!g_chained||port_fs_mod_filter(0,nullptr,7)!=15)return 1;port_stage_geom_ctor();if(port_fs_mod_filter(0,nullptr,7)!=15)return 2;puts("native filter initialization: chain and idempotency PASS");}
''')
    flags=shlex.split(a.flags)
    base=[a.cxx,*flags,'-std=c++17','-O2','-pthread','-ffunction-sections','-fdata-sections',
          '-Wl,--gc-sections','-I'+str(here),'-I'+str(root/'port'),'-I'+str(root/'port/hal'),
          '-I'+str(root/'port/hal/sdat'),'-I'+str(out)]
    commands=[]
    def build(name: str, sources: list[Path], extra: list[str]=[]) -> Path:
        exe=out/name;cmd=base+extra+list(map(str,sources))+['-ldl','-o',str(exe)]
        commands.append(cmd)
        run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (out/(name+'.build.log')).write_text(run.stdout)
        if run.returncode:raise RuntimeError(name+' did not build:\n'+run.stdout[-8000:])
        return exe
    audio=build('audio_tests',[here/'out_android.cpp',here/'platform-tests/audio.cpp'],['-DSM64DS_AUDIO_TEST'])
    network=build('network_tests',[here/'platform-tests/network.cpp'])
    init_files=[out/'install_stage.cpp',out/'install_mods.cpp',out/'install_main.cpp']
    init=build('init_tests',init_files)
    reverse=build('init_reverse_tests',list(reversed(init_files)))
    if a.runner is not None:
        prefix=[] if a.runner=='native' else shlex.split(a.runner)
        logs=[]
        def execute(exe: Path,args: list[str]=[]) -> None:
            run=subprocess.run(prefix+[str(exe)]+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=15)
            logs.append(run.stdout);print(run.stdout,end='',flush=True)
            if run.returncode:raise RuntimeError(f'{exe.name} exit={run.returncode}')
        execute(audio,[str(out/'fixture.wav')]);execute(network);execute(init);execute(reverse)
        # Opt-in loopback tests, never bind to external interfaces or contact a relay.
        port=random.randrange(25000,50000)
        peers=[]
        try:
            for role in ('parent','child'):
                peers.append(subprocess.Popen(prefix+[str(network),role,str(port)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True))
            for child in peers:
                text=child.communicate(timeout=12)[0];logs.append(text);print(text,end='',flush=True)
                if child.returncode:raise RuntimeError(f'UDP peer exited {child.returncode}')
        finally:
            for child in peers:
                if child.poll() is None:child.kill();child.wait()
            (out/'execution.log').write_text(''.join(logs))
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print('Native platform boundaries: '+('EXECUTED; audio device simulated, UDP real' if a.runner is not None else 'COMPILED AND LINKED ONLY; no device execution'))

if __name__=='__main__':main()
