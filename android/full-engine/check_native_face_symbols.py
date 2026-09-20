#!/usr/bin/env python3
"""Verify native face retirement against the actual compiled-object census."""
import argparse
import json
from pathlib import Path
import re
from adapt_native_faces import manifest


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,required=True);args=ap.parse_args()
    out=args.report.resolve();rules=manifest()
    compiled=json.loads((out/'report.json').read_text())['results']
    faces=[r for r in compiled if r['original_source'].endswith('/'+rules['face_source'])]
    if len(faces)!=1 or faces[0]['status']!='compiled':raise ValueError('Adapted face unit did not compile')
    sources={f"{r['index']:05d}.o":r['original_source'] for r in compiled if r['status']=='compiled'}
    symbols={f['symbol']:[] for f in rules['faces']}
    for line in (out/'link-audit/defined-symbols.txt').read_text().splitlines():
        m=re.match(r'^(.*?\.o):\s+(\S+)\s+([A-Za-z?])\s+',line)
        if m and m[2] in symbols and m[3].isupper() and m[3] not in ('U','W','V','C'):
            symbols[m[2]].append(sources[Path(m[1]).name])
    records=[]
    for f in rules['faces']:
        providers=symbols[f['symbol']];expected=f['provider']
        if '/host-src/src/' in expected:
            passed=len(providers)==1 and '/host-src/src/' in providers[0] and Path(providers[0]).name==Path(expected).name
        else:passed=len(providers)==1 and providers[0].endswith('/'+expected)
        records.append({'symbol':f['symbol'],'expected':expected,'actual':providers,'passed':passed})
    (out/'link-audit/native-face-providers.json').write_text(json.dumps({'scope':'Preservation of original native providers, not full link or gameplay','checks':records},indent=2)+'\n')
    print('NATIVE FACE PROVIDERS:',sum(r['passed'] for r in records),'/',len(records),'uniquely retained')
    return 0 if all(r['passed'] for r in records) else 1

if __name__=='__main__':raise SystemExit(main())
