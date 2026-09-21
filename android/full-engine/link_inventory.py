#!/usr/bin/env python3
"""Audit real NDK object symbols and attempt an explicitly incomplete engine link.

Uncompiled units remain in the report. No entry point, missing symbol, vtable or
ROM table is invented to make linking pass. Static and object-library grouping
comes from CMake. Dead-code removal is disabled so missing main cannot conceal
unresolved engine references. This is a wider diagnostic than a final app link.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess


def target_types(build: Path) -> dict[str, str]:
    reply = build/'.cmake/api/v1/reply'
    index = json.loads(sorted(reply.glob('index-*.json'))[-1].read_text())
    model = json.loads((reply/next(x['jsonFile'] for x in index['objects'] if x['kind']=='codemodel')).read_text())
    config = next((x for x in model['configurations'] if x['name']=='Release'),model['configurations'][0])
    return {t['name']:json.loads((reply/t['jsonFile']).read_text())['type'] for t in config['targets']}


def quoted(path: Path) -> str:
    return json.dumps(str(path))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--ndk',type=Path,required=True)
    args = ap.parse_args()
    folder = args.report.resolve()
    data = json.loads((folder/'report.json').read_text())
    llvm = args.ndk.resolve()/'toolchains/llvm/prebuilt/linux-x86_64/bin'
    kinds = target_types(args.build.resolve())
    out = folder/'link-audit';out.mkdir(exist_ok=True)
    groups = defaultdict(list); sources = {};missing = []
    for r in data['results']:
        if r['status']!='compiled':
            missing.append({'index':r['index'],'target':r['target'],'source':r['original_source'],'status':r['status']})
            continue
        obj = folder/'objects'/f"{r['index']:05d}.o"
        if not obj.is_file(): raise ValueError('Missing compiled object: '+str(obj))
        groups[r['target']].append(obj)
        sources[str(obj)] = {'index':r['index'],'target':r['target'],'source':r['original_source']}
    all_objects = [o for v in groups.values() for o in v]
    rsp = out/'symbols.rsp';rsp.write_text('\n'.join(quoted(p) for p in all_objects)+'\n')
    nm = subprocess.run([str(llvm/'llvm-nm'),'-g','--defined-only','--print-file-name','--format=posix','@'+str(rsp)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if nm.returncode: raise RuntimeError(nm.stderr)
    (out/'defined-symbols.txt').write_text(nm.stdout)
    definitions = defaultdict(list)
    for line in nm.stdout.splitlines():
        # llvm-nm -A -P: /path/to/object.o: symbol TYPE value size
        match = re.match(r'^(.*?\.o):\s+(\S+)\s+([A-Za-z?])\s+',line)
        if not match: continue
        obj,symbol,typ = match.groups()
        if typ.isupper() and typ not in ('U','W','V','C'):
            definitions[symbol].append({**sources[obj],'type':typ})
    duplicates = {k:v for k,v in definitions.items() if len(v)>1}
    direct,archives = [],[]
    for target,objects in sorted(groups.items()):
        kind = kinds.get(target)
        if kind in ('OBJECT_LIBRARY','EXECUTABLE'):
            direct.extend(objects)
        elif kind=='STATIC_LIBRARY':
            archive = out/('lib'+target+'.a')
            ar_rsp = out/(target+'.rsp');ar_rsp.write_text('\n'.join(quoted(p) for p in objects)+'\n')
            subprocess.run([str(llvm/'llvm-ar'),'rcs',str(archive),'@'+str(ar_rsp)],check=True,timeout=60)
            archives.append(archive)
        else: raise ValueError('Unreviewed link target kind: '+str((target,kind)))
    link_rsp = out/'link.rsp'
    args_list = [quoted(p) for p in direct]
    args_list += ['-Wl,--start-group',*[quoted(p) for p in archives],'-Wl,--end-group']
    link_rsp.write_text('\n'.join(args_list)+'\n')
    cmd = [str(llvm/'armv7a-linux-androideabi23-clang++'),'-static-libstdc++','-pthread',
           '@'+str(link_rsp),'-ldl','-llog','-landroid','-latomic',
           '-Wl,--no-undefined','-Wl,--no-gc-sections','-Wl,--error-limit=0',
           '-Wl,-T,'+str(Path(__file__).with_name('state_sections.ld').resolve()),
           '-Wl,-Map,'+str(out/'engine.map'),'-o',str(out/'engine-link-diagnostic')]
    proc = subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    (out/'link.log').write_text(proc.stdout)
    undefined = sorted(set(re.findall(r'undefined symbol: (.+)',proc.stdout)))
    duplicate_errors = sorted(set(re.findall(r'duplicate symbol: (.+)',proc.stdout)))
    complete = not missing and not duplicates and proc.returncode == 0
    summary = {'scope': ('Complete retained engine/native-frontend link; gameplay and Android app integration NOT verified'
                         if complete else 'Object-symbol census and retained-reference diagnostic; NOT a complete game/app link'),
               'resource_mode':data['resource_mode'],'selected_units':data['total'],
               'compiled_objects':len(all_objects),'uncompiled_units':missing,
               'target_kinds':{t:kinds[t] for t in groups},
               'strong_duplicate_symbol_groups':len(duplicates),
               'strong_duplicates':duplicates,'link_command':cmd,'link_returncode':proc.returncode,
               'undefined_symbols':undefined,'duplicate_link_errors':duplicate_errors,
               'native_game_execution':'NOT RUN','android_device_execution':'NOT RUN'}
    (out/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('LINK DIAGNOSTIC:',len(all_objects),'compiled objects;',len(missing),'uncompiled units;',
          len(duplicates),'multiply defined strong symbol groups;',len(undefined),'undefined linker diagnostics;',
          'exit',proc.returncode,'-- NOT gameplay')
    return 1 if missing or proc.returncode else 0

if __name__=='__main__':
    raise SystemExit(main())
