"""Retire reviewed Windows ABI forwarding definitions, not recovered methods.

Each listed face is receiver-only and forwards to the exact same Itanium symbol
that the native C++ provider already exports. No alias, stub or weak fallback is
invented. Methods needing argument conversion, different return types, vtables,
destructors and reverse faces are deliberately outside this first allowlist.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from adapt_calls import masked

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def manifest() -> dict:
    return json.loads((HERE/'native_faces.json').read_text())


def key(path: str) -> str:
    p = Path(path)
    if '/host-src/src/' in p.as_posix():
        return 'generated:' + p.name
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def elide(text: str, faces: list[dict]) -> str:
    code = masked(text)
    edits = []
    for face in faces:
        symbol, result = face['symbol'], face['result']
        found = list(re.finditer(r'\b'+re.escape(result)+r'\s+'+re.escape(symbol)+
                                r'\s*\(([^;{}]*)\)\s*\{([^{}]*)\}', code))
        if len(found) != 1:
            raise ValueError('Changed native face definition: ' + symbol)
        m = found[0]
        args, body = m.groups()
        fw = re.fullmatch(r'\s*(return\s+)?\(\((const\s+)?(\w+)\s*\*\)self\)->\3::(\w+)\(\);\s*', body)
        if not fw or args.strip() not in ('void *self', 'const void *self'):
            raise ValueError('Face is not a receiver-only qualified forward: ' + symbol)
        const = bool(fw[2])
        cls, method = fw[3], fw[4]
        expected = '_ZN'+('K' if const else '')+str(len(cls))+cls+str(len(method))+method+'Ev'
        if expected != symbol or const != args.strip().startswith('const'):
            raise ValueError('Face target or receiver differs: ' + symbol)
        if bool(fw[1]) != (result != 'void'):
            raise ValueError('Face changes its return convention: ' + symbol)
        start = m.start()
        # Include a per-declaration extern "C", but not enclosing linkage blocks.
        linkage = re.search(r'extern\s+"C"\s*$', text[:start])
        if linkage and code[linkage.start():start].strip() == 'extern':
            start = linkage.start()
        edits.append((start, m.end(), '// Native ABI: retained original provider for '+symbol+'.\n'))
    for a,b,value in sorted(edits, reverse=True):
        text = text[:a]+value+text[b:]
    return text


def prepare(units: list[dict], output: Path) -> list[dict]:
    rules = manifest()
    selected = [u for u in units if key(u.get('original_source',u['source'])) == rules['face_source']]
    if not selected:
        return units
    available = [key(u.get('original_source',u['source'])) for u in units]
    result = []
    for u in units:
        if u not in selected or u.get('adaptation_error'):
            result.append(u)
            continue
        item = deepcopy(u)
        item.setdefault('original_source',u['source'])
        try:
            original = ROOT/rules['face_source']
            if hashlib.sha256(original.read_bytes()).hexdigest() != rules['face_sha256']:
                raise ValueError('Unreviewed original method faces')
            for face in rules['faces']:
                provider = key(str(ROOT/face['provider']))
                if available.count(provider) != 1:
                    raise ValueError('Native provider absent or ambiguous: '+face['symbol'])
            converted = elide(Path(u['source']).read_text(), rules['faces'])
            target = output.resolve()/'native-faces'/'method_faces.cpp'
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(converted)
            item['source'] = str(target)
            item['adaptation'] = item.get('adaptation','')+'; redundant native-ABI faces retired with providers retained'
            item['group'].setdefault('includes',[]).append({'path':str(original.parent)})
            (target.parent/'report.json').write_text(json.dumps(rules,indent=2)+'\n')
        except (ValueError,OSError) as exc:
            item['adaptation_error'] = str(exc)
        result.append(item)
    return result
