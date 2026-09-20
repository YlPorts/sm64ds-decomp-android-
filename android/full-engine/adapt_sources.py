"""Pinned source portability, applied after the earlier checked ABI adapters.

This is not a generic C++ fixer or Windows shim. Every upstream input is pinned,
unknown source changes fail closed, and no translation unit is dropped.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from adapt_calls import masked


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(text: str, rule: dict) -> str:
    text = text.removeprefix('\ufeff')
    for edit in rule.get('edits', []):
        count = text.count(edit['old'])
        if count != edit['count']:
            raise ValueError(f"Portability anchor expected {edit['count']}, found {count}: {edit['old'][:70]}")
        text = text.replace(edit['old'], edit['new'])
    tokens = rule.get('code_tokens', {})
    if tokens:
        code = masked(text)
        changes = [(m.start(), m.end(), tokens[m[0]]) for m in
                   re.finditer(r'\b(?:' + '|'.join(map(re.escape, tokens)) + r')\b', code)]
        for a, b, value in reversed(changes):
            text = text[:a] + value + text[b:]
    return rule.get('prefix', '') + text


def load_manifest() -> dict:
    result = json.loads(Path(__file__).with_name('source_portability.json').read_text())
    for filename in ('platform_portability.json', 'input_portability.json'):
        extra = json.loads(Path(__file__).with_name(filename).read_text())['sources']
        if result['sources'].keys() & extra.keys():
            raise ValueError('Duplicate native platform source rule')
        result['sources'].update(extra)
    return result


def validate(data: bytes, digest: str, name: str) -> None:
    if sha256(data) != digest:
        raise ValueError('Unreviewed source portability input: ' + name)


def prepare(units: list[dict], output: Path) -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    manifest = load_manifest()
    rules = manifest['sources']
    dest = output.resolve() / 'source-ports'
    dest.mkdir(parents=True, exist_ok=True)
    headers = {}
    for rel, rule in rules.items():
        if not rel.endswith('.h'):
            continue
        source = root / rel
        validate(source.read_bytes(), rule['sha256'], rel)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(transform(source.read_text(), rule))
        headers[rel] = target
    result, records = [], []
    for unit in units:
        if unit.get('adaptation_error'):
            result.append(unit)
            continue
        original = Path(unit.get('original_source', unit['source']))
        try:
            rel = original.relative_to(root).as_posix()
        except ValueError:
            rel = ''
        is_hostgen = False
        if rel not in rules and '/host-src/src/' in original.as_posix():
            candidates = [k for k in manifest['generated_sha256'] if Path(k).stem == original.stem]
            if len(candidates) == 1:
                rel = candidates[0]
                is_hostgen = True
        if rel not in rules or rel.endswith('.h'):
            result.append(unit)
            continue
        item = deepcopy(unit)
        item.setdefault('original_source', unit['source'])
        try:
            rule = rules[rel]
            validate((root / rel).read_bytes(), rule['sha256'], rel)
            if is_hostgen:
                validate((root / 'port/tools/hostgen.py').read_bytes(), manifest['hostgen_sha256'], 'hostgen.py')
                validate(original.read_bytes(), manifest['generated_sha256'][rel], str(original))
            text = Path(unit['source']).read_text()
            if 'replacement' in rule:
                replacement = (root / rule['replacement']).resolve()
                if not replacement.is_relative_to(Path(__file__).resolve().parent) or replacement.suffix != '.cpp':
                    raise ValueError('Replacement must be a native .cpp inside android/full-engine')
                converted = replacement.read_text()
            else:
                converted = transform(text, rule)
            for header in rule.get('redirect_headers', []):
                old = '"' + Path(header).name + '"'
                if converted.count(old) != 1:
                    raise ValueError('Changed header reference in ' + rel)
                converted = converted.replace(old, json.dumps(str(headers[header])))
            key = sha256((rel + '\0' + unit['source']).encode())[:16]
            target = dest / (key + '_' + Path(unit['source']).name)
            target.write_text('// Generated native source portability; upstream files remain unchanged.\n' + converted)
            item['source'] = str(target)
            item['adaptation'] = item.get('adaptation', '') + '; pinned source/POSIX boundary adaptation'
            item['group'].setdefault('includes', []).extend([
                {'path': str(Path(__file__).resolve().parent)},
                {'path': str((root / rel).parent)},
            ])
            records.append({'source': rel, 'original_source': str(original), 'output': str(target),
                            'input_sha256': sha256(text.encode()), 'output_sha256': sha256(target.read_bytes()),
                            'edits': len(rule.get('edits', [])), 'generated_input': is_hostgen})
        except (ValueError, OSError) as error:
            item['adaptation_error'] = str(error)
            records.append({'source': rel, 'error': str(error)})
        result.append(item)
    (output / 'source-portability-report.json').write_text(json.dumps(records, indent=2) + '\n')
    return result
