"""Checked source adapter for the pinned x86 method-thunk seam, not all C++ ABI.

Only reviewed inputs are accepted by prepare(). Scalar thunks lose their dead
EDX parameter AND explicit thunk callers lose the corresponding dummy argument.
The two Vector3 sret seats become real 12-byte aggregate-returning functions so
Clang, not handwritten register shuffling, implements the ARM result ABI.
Comments/literals are not edited. Original src/ and port/ are never written.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

SRET = {'port_actor_s30_base', 'whomp_s30'}
OPAQUE = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
DECL = re.compile(r'\s*([A-Za-z_]\w*(?:\s*##\s*\w+)*)\s*(\()')
POINTER = re.compile(r'\s*\*\s*([A-Za-z_]\w*)?\s*\)\s*(\()')
DUMMY = re.compile(r'void\s*\*\s*(dead_edx|edx|e|d|dead|dummy)?\s*\Z')


def masked(text: str) -> str:
    return OPAQUE.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), text)


def close_at(code: str, pos: int) -> int:
    opening = code[pos]
    closing = {'(': ')', '{': '}', '[': ']'}[opening]
    depth = 1
    for end in range(pos + 1, len(code)):
        if code[end] == opening:
            depth += 1
        elif code[end] == closing:
            depth -= 1
            if depth == 0:
                return end
    raise ValueError('Unbalanced ' + opening + ' in reviewed ABI seam')


def arguments(code: str, pos: int) -> tuple[int, list[tuple[int, int]]]:
    end = close_at(code, pos)
    starts, items, i = pos + 1, [], pos + 1
    while i < end:
        c = code[i]
        if c in '([{':
            i = close_at(code, i) + 1
            continue
        if c == ',':
            items.append((starts, i)); starts = i + 1
        i += 1
    if code[starts:end].strip():
        items.append((starts, end))
    return end, items


def adapt(text: str) -> tuple[str, dict]:
    """All-or-nothing transform; caller must additionally enforce input hashes."""
    # Strip a UTF-8 signature before generated headers/comments precede it.
    text = text.removeprefix("\ufeff")
    code = masked(text)
    edits: dict[tuple[int, int], str] = {}
    protected: list[tuple[int, int]] = []
    symbols: dict[str, tuple[int, bool]] = {}
    pointer_occurrences: list[tuple[int, int, int]] = []
    forwarded_dummies = set()
    stats = dict(thunks=0, pointer_types=0, explicit_calls=0, cdecl=0, sret=0)

    def edit(start: int, end: int, replacement: str) -> None:
        key = (start, end)
        if key in edits and edits[key] != replacement:
            raise ValueError('Conflicting ABI rewrites')
        edits[key] = replacement

    for m in re.finditer(r'\b__cdecl\b', code):
        edit(m.start(), m.end(), ''); stats['cdecl'] += 1

    for m in re.finditer(r'\b__fastcall\b', code):
        decl = DECL.match(code, m.end())
        pointer = POINTER.match(code, m.end())
        if decl:
            name = re.sub(r'\s+', '', decl[1]); pos = decl.start(2)
        elif pointer:
            name = pointer[1] or ''; pos = pointer.start(2)
        else:
            raise ValueError('Unrecognised __fastcall declarator at line ' + str(code.count('\n', 0, m.start()) + 1))
        end, spans = arguments(code, pos)
        params = [code[a:b].strip() for a, b in spans]
        if not params or not re.fullmatch(r'(?:const\s+)?[A-Za-z_]\w*\s*\*\s*\w*', params[0]):
            raise ValueError('Thunk receiver is not a reviewed void pointer: ' + name)
        if len(params) > 1 and not DUMMY.fullmatch(params[1]):
            raise ValueError('Second parameter is not a reviewed dead-EDX word: ' + name)
        if any('...' in p for p in params):
            raise ValueError('Variadic thunk is not supported')
        edit(m.start(), m.end(), '')
        protected.append((m.start(), end + 1))
        is_sret = name in SRET
        if name:
            shape = (len(params), is_sret)
            if '##' not in name and name in symbols and symbols[name] != shape:
                raise ValueError('Conflicting declarations for ' + name)
            if '##' not in name:
                symbols[name] = shape
        if decl:
            stats['thunks'] += 1
        else:
            stats['pointer_types'] += 1
            pointer_occurrences.append((m.start(), end, len(params)))
        if len(params) == 1:
            continue
        dummy = DUMMY.fullmatch(params[1])[1]
        body_pos = end + 1
        while body_pos < len(code) and (code[body_pos].isspace() or code[body_pos] == '\\'):
            body_pos += 1
        body_end = close_at(code, body_pos) if decl and body_pos < len(code) and code[body_pos] == '{' else None
        if is_sret:
            if len(params) != 3 or not re.fullmatch(r'void\s*\*\s*out', params[2]):
                raise ValueError('Changed aggregate-return contract: ' + name)
            rtype = re.search(r'void\s*\*\s*$', code[:m.start()])
            if not rtype:
                raise ValueError('Changed aggregate thunk return type: ' + name)
            edit(rtype.start(), rtype.end(), 'Sm64dsAbiVec3 ')
            edit(spans[0][1], end, '')
            if body_end is not None:
                body = code[body_pos + 1:body_end]
                returns = list(re.finditer(r'\breturn\s+out\s*;', body))
                if len(returns) != 1:
                    raise ValueError('Changed sret body: ' + name)
                r = returns[0]; base = body_pos + 1
                edit(base + r.start(), base + r.end(), 'return sm64ds_result;')
                edit(base, base, '\n    Sm64dsAbiVec3 sm64ds_result{}; void *out = &sm64ds_result;\n')
            stats['sret'] += 1
        else:
            edit(spans[0][1], spans[1][1], '')
        if dummy and body_end is not None:
            body = code[body_pos + 1:body_end]; base = body_pos + 1
            for use in re.finditer(r'\b' + dummy + r'\b', body):
                before, after = body[:use.start()], body[use.end():]
                discarded = re.search(r'\(\s*void\s*\)\s*$', before) and re.match(r'\s*;', after)
                forwarded = (dummy == 'd' and re.search(r'\b(?:st_trap|ps_trap)\(\s*s\s*,\s*$', before) and re.match(r'\s*\)', after))
                if not discarded and not forwarded:
                    raise ValueError('EDX word has non-discarded semantics in ' + name)
                if forwarded:
                    forwarded_dummies.add(base + use.start())
                if discarded:
                    edit(base + use.start(), base + use.end(), 'nullptr')

    stack, pairs = [], []
    for i, c in enumerate(code):
        if c == '(':
            stack.append(i)
        elif c == ')' and stack:
            pairs.append((stack.pop(), i))

    def call(pos: int, arity: int, sret: bool = False) -> bool:
        end, spans = arguments(code, pos)
        if len(spans) != arity:
            return False
        if arity == 1:
            return True
        dummy = code[spans[1][0]:spans[1][1]].strip()
        if dummy not in ('0', 'nullptr', 'NULL') and not (dummy == 'd' and any(spans[1][0] <= p < spans[1][1] for p in forwarded_dummies)):
            return False
        if sret:
            raise ValueError('Explicit aggregate-result call needs a reviewed native caller')
        key = (spans[0][1], spans[1][1])
        if key not in edits:
            edit(*key, ''); stats['explicit_calls'] += 1
        return True

    def enclosing_call(start: int, after: int, arity: int) -> bool:
        for left, right in sorted((p for p in pairs if p[0] < start and p[1] > after), key=lambda p:p[1] - p[0]):
            match = re.match(r'\s*(\()', code[right + 1:])
            if match and call(right + 1 + match.start(1), arity):
                return True
        return False

    for start, end, arity in pointer_occurrences:
        ptr = POINTER.match(code, start + len('__fastcall'))
        if not ptr[1] and not enclosing_call(start, end, arity):
            if not any(s[0] == arity for n, s in symbols.items() if n in ('m', 'fn')):
                raise ValueError('Anonymous thunk cast has no reviewed dummy invocation')

    for name, (arity, sret) in symbols.items():
        if '##' in name:
            continue
        for m in re.finditer(r'\b' + re.escape(name) + r'\b', code):
            if any(a <= m.start() < b for a, b in protected):
                continue
            following = re.match(r'\s*(\()', code[m.end():])
            if following:
                if not call(m.end() + following.start(1), arity, sret):
                    raise ValueError('Changed explicit thunk call: ' + name)
            else:
                enclosing_call(m.start(), m.end(), arity)

    ordered = sorted((a,b,v) for (a,b),v in edits.items())
    for (_, last, _), (start, _, _) in zip(ordered, ordered[1:]):
        if last > start:
            raise ValueError('Overlapping ABI transformations')
    result = text
    for a, b, value in reversed(ordered):
        result = result[:a] + value + result[b:]
    if stats['sret']:
        result = '#include "sm64ds_call_abi.h"\n' + result
    return result, stats


def verified_blobs(root: Path, manifest: dict) -> dict[str, str]:
    """Pin the entire reviewed original snapshot; never trust HEAD's name alone."""
    for path, expected in manifest['trees'].items():
        actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD:' + path], text=True).strip()
        if actual != expected:
            raise ValueError('Unreviewed original source tree: ' + path)
    raw = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', '-z', 'HEAD', '--', *manifest['trees']])
    blobs = {}
    for entry in raw.split(b'\0'):
        if entry:
            meta, path = entry.split(b'\t', 1)
            blobs[path.decode()] = meta.decode().split()[2]
    return blobs


def accepted(path: Path, root: Path, blobs: dict, generated: dict) -> bool:
    data = path.read_bytes()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = ''
    if rel in blobs:
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        return blob == blobs[rel]
    return hashlib.sha256(data).hexdigest() in generated


def rewrite_forced_headers(group: dict, headers: dict[str, Path]) -> dict:
    """Keep per-file flags, replacing only reviewed force-include paths."""
    group = deepcopy(group)
    for fragment in group.get('compileCommandFragments', []):
        for source, target in headers.items():
            fragment['fragment'] = fragment['fragment'].replace(source, str(target))
    return group


def prepare(units: list[dict], output: Path) -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(Path(__file__).with_name('call_abi_inputs.json').read_text())
    blobs = verified_blobs(root, manifest)
    dst = output / 'call-abi'
    dst.mkdir(parents=True, exist_ok=True)
    headers, header_stats = {}, {}
    for rel in ('port/hal/dtor_faces_cpp.h', 'port/unmatched/MgSmartball_HostAbi.h'):
        header = root / rel
        if not accepted(header, root, blobs, {}):
            raise ValueError('Unreviewed call bridge header: ' + rel)
        target = dst / header.name
        converted, stats = adapt(header.read_text())
        target.write_text(converted)
        headers[str(header)] = target
        header_stats[rel] = stats
    records, result, cache = [], [], {}
    for unit in units:
        p = Path(unit['source'])
        if not p.is_file():
            result.append(unit); continue
        text = p.read_text()
        has_header = any('"' + target.name + '"' in text for target in headers.values())
        forced_header = any(source in frag['fragment'] for source in headers
                            for frag in unit['group'].get('compileCommandFragments', []))
        if not re.search(r'\b__(?:fastcall|cdecl)\b', masked(text)) and not has_header and not forced_header:
            result.append(unit); continue
        item = deepcopy(unit)
        item.setdefault('original_source', str(p))
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            if not accepted(p, root, blobs, manifest['generated_sha256']):
                raise ValueError('Unreviewed call-ABI input: ' + str(p))
            if str(p) not in cache:
                converted, stats = adapt(text)
                for target in headers.values():
                    converted = converted.replace('"' + target.name + '"', json.dumps(str(target)))
                target = dst / (digest[:16] + '_' + p.name)
                target.write_text('// GENERATED ARM call adaptation. Upstream comments describe the x86 baseline.\n' + converted)
                cache[str(p)] = (target, stats)
                records.append({'source':str(p), 'sha256':digest, 'output':str(target), **stats})
            target, stats = cache[str(p)]
            item['source'] = str(target)
            item['adaptation'] = 'reviewed native calls: drop EDX word at both ends; aggregate returns use compiler ABI'
            group = rewrite_forced_headers(item['group'], headers)
            group.setdefault('includes', []).extend([{'path':str(p.parent)}, {'path':str(Path(__file__).parent)}])
            item['group'] = group
        except ValueError as exc:
            item['adaptation_error'] = str(exc)
            records.append({'source':str(p), 'error':str(exc)})
        result.append(item)
    (output / 'call-abi-report.json').write_text(json.dumps({'headers':header_stats, 'sources':records},indent=2))
    return result
