#!/usr/bin/env python3
"""Link the verified ROM-clean engine into the Android Activity's JNI library."""
import argparse
import concurrent.futures
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'android/full-engine'))
from link_inventory import target_types, quoted
from build_runtime import verify_packed_layout

def run(command):
    proc=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if proc.returncode:raise RuntimeError(proc.stdout.decode(errors='replace'))
    return proc.stdout

def validate_dynamic(llvm,library):
    # Nothing may rely on an unpackaged C++ runtime or replace Android's own
    # allocation/ABI symbols while a dependency's constructors are running.
    dynamic=run([llvm/'llvm-readelf','-d',library]).decode()
    needed=set(re.findall(r'Shared library: \[(.+?)\]',dynamic))
    allowed={'libc.so','libm.so','libdl.so','liblog.so','libandroid.so'}
    if needed-allowed:raise ValueError('Unexpected Android dependencies: '+repr(needed-allowed))
    exports=run([llvm/'llvm-nm','-D','--defined-only','--format=posix',library]).decode()
    names=[line.split()[0] for line in exports.splitlines() if line.strip()]
    if not names or any(not n.startswith(('Java_org_ylports_sm64ds_nativeport_EngineBridge_',
                                         'Java_org_ylports_sm64ds_controls_NativeBridge_')) for n in names):
        raise ValueError('Only the reviewed JNI surface may be exported')
    return dict(needed=sorted(needed),exports=names)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--ndk',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=json.loads((args.runtime/'report.json').read_text())
    if not report['resource_mode'].startswith('real-ROM recipe;'):raise ValueError('Requires real resources')
    audit=json.loads((args.runtime/'link-audit/report.json').read_text())
    if audit['link_returncode'] or audit['uncompiled_units']:raise ValueError('Runtime audit failed')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    llvm=args.ndk.resolve()/'toolchains/llvm/prebuilt/linux-x86_64/bin'
    aliases=json.loads((ROOT/'android/full-engine/linkage_aliases.json').read_text())
    aliases=aliases['bindings']
    def compile_row(row):
        obj=args.runtime.resolve()/'objects'/f"{row['index']:05d}.o"
        cmd=row['command'].copy()
        if '-fPIE' in cmd or Path(row['source']).name=='native_scene_main.cpp':
            obj=out/f"{row['index']:05d}.o"
            cmd[0]=str(llvm/Path(cmd[0]).name)
            cmd=[('-fPIC' if x=='-fPIE' else x) for x in cmd]
            cmd[cmd.index('-o')+1]=str(obj)
            if Path(row['source']).name=='native_scene_main.cpp':cmd.insert(1,'-DSM64DS_NATIVE_SHARED')
            run(cmd)
            unresolved=run([llvm/'llvm-nm','-u','--format=posix',obj]).decode()
            symbols=[line.split()[0] for line in unresolved.splitlines() if line.split()]
            rename={s:aliases[s]['target'] for s in symbols if s in aliases}
            if rename:
                mapping=obj.with_suffix('.aliases');mapping.write_text(''.join(s+' '+t+'\n' for s,t in rename.items()))
                run([llvm/'llvm-objcopy','--redefine-syms='+str(mapping),obj])
        return row['target'],obj
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:objects=list(pool.map(compile_row,report['results']))
    flags=['-std=c++17','-fPIC','-O2','-DNTR_WIDE_RT',
           '-I'+str(ROOT/'port'),'-I'+str(ROOT/'port/ntr/include'),'-I'+str(ROOT/'android/full-engine')]
    for source in [HERE/'native/engine_host.cpp',ROOT/'android/touch-ui/native/bridge.cpp']:
        obj=out/(source.stem+'.o');run([llvm/'armv7a-linux-androideabi23-clang++',*flags,'-c',source,'-o',obj]);objects.append(('walk_window',obj))
    groups={}
    for target,obj in objects:groups.setdefault(target,[]).append(obj)
    kinds=target_types(args.build.resolve());direct=[];archives=[]
    for target,objs in groups.items():
        if kinds[target]=='STATIC_LIBRARY':
            archive=out/('lib'+target+'.a');rsp=out/(target+'.rsp');rsp.write_text('\n'.join(quoted(p) for p in objs))
            run([llvm/'llvm-ar','rcs',archive,'@'+str(rsp)]);archives.append(archive)
        else:direct.extend(objs)
    rsp=out/'link.rsp';rsp.write_text('\n'.join([*[quoted(p) for p in direct],'-Wl,--start-group',*[quoted(p) for p in archives],'-Wl,--end-group']))
    library=out/'libsm64ds_engine.so'
    command=[llvm/'armv7a-linux-androideabi23-clang++','-shared','-static-libstdc++','-pthread','@'+str(rsp),
             '-ldl','-llog','-landroid','-latomic','-Wl,--no-undefined','-Wl,--no-gc-sections','-Wl,--error-limit=0',
             '-Wl,-z,max-page-size=16384','-Wl,-soname,libsm64ds_engine.so',
             '-Wl,--version-script='+str(HERE/'native/exports.map'),
             '-Wl,-T,'+str(ROOT/'android/full-engine/state_sections.ld'),'-Wl,-Map,'+str(out/'engine.map'),'-o',library]
    run(command)
    verify_packed_layout(llvm, args.runtime/'sources', library, out/'packed-layout.json')
    bootstrap=out/'libsm64ds_bootstrap.so'
    run([llvm/'armv7a-linux-androideabi23-clang++','-shared','-static-libstdc++','-fPIC','-O2',HERE/'native/bootstrap.cpp',
         '-Wl,--no-undefined','-Wl,-z,max-page-size=16384','-Wl,-soname,libsm64ds_bootstrap.so',
         '-Wl,--version-script='+str(HERE/'native/exports.map'),'-o',bootstrap])
    dynamic={p.name:validate_dynamic(llvm,p) for p in (library,bootstrap)}
    (out/'report.json').write_text(json.dumps({'objects':len(objects),'resource_mode':report['resource_mode'],
        'link_command':list(map(str,command)),'library_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),
        'dynamic_libraries':dynamic,'execution':'separate runtime validation required'},indent=2)+'\n')
    print(library)
if __name__=='__main__':main()
