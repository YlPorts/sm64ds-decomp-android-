"""Keep recovered sub-object render calls virtual on the native compiler.

The matching sources model embedded runtime objects with local shadow classes.
Clang can infer the shadow member's exact type and devirtualize its call to an
undefined dummy method. Hide only that receiver's static provenance, retaining
the compiler's virtual dispatch, receiver adjustment and argument conversions.
This operates on generated copies; the byte-matching sources are untouched.
"""
from __future__ import annotations

SYMBOLS = {
    '_ZN3Foo2M5Ei', '_ZN3Sub1mEP3Arg', '_ZN3Sub2m5EP5Thing',
    '_ZN3Sub7method5Ei', '_ZN4Base1MEPv', '_ZN4Base1mEi',
    '_ZN4Base5vfuncEi', '_ZN5Base21mEPv',
}

PREAMBLE = b'''// Native dynamic receiver: no replacement method or vtable.
template<class T> static inline T *sm64ds_dynamic_receiver(T *receiver) {
    __asm__ __volatile__("" : "+r"(receiver) : : "memory");
    return receiver;
}
'''


def nodes(node: dict):
    yield node
    for child in node.get('inner', []):
        yield from nodes(child)


def span(node: dict) -> tuple[int, int]:
    first, last = node['range']['begin'], node['range']['end']
    if 'offset' not in first or 'offset' not in last:
        raise ValueError('Virtual-call adaptation requires preprocessed locations')
    return first['offset'], last['offset'] + last['tokLen']


def transform(source: bytes, ast: dict) -> tuple[bytes, list[dict]]:
    declarations = {n['id']: n for n in nodes(ast)
                    if n.get('mangledName') in SYMBOLS}
    edits = []
    evidence = []
    for call in nodes(ast):
        if call.get('kind') != 'CXXMemberCallExpr' or not call.get('inner'):
            continue
        member = call['inner'][0]
        decl = declarations.get(member.get('referencedMemberDecl'))
        if not decl:
            continue
        if member['kind'] != 'MemberExpr' or not decl.get('virtual'):
            raise ValueError('Reviewed render method is no longer virtual')
        receiver, = member['inner']
        a, b = span(receiver)
        c, d = span(member)
        if c != a or not 0 <= a < b < d <= len(source):
            raise ValueError('Unexpected virtual receiver expression')
        suffix = source[b:d]
        operator = b'->' if member['isArrow'] else b'.'
        if suffix.strip() != operator + member['name'].encode():
            raise ValueError('Qualified or changed render call: ' + suffix.decode())
        expression = source[a:b]
        if not member['isArrow']:
            expression = b'&(' + expression + b')'
        replacement = (b'sm64ds_dynamic_receiver(' + expression + b')->' +
                       member['name'].encode())
        edits.append((a, d, replacement))
        evidence.append({'symbol': decl['mangledName'], 'offset': a,
                         'receiver': source[a:b].decode(), 'method': member['name']})
    last = len(source)
    for a, b, replacement in sorted(edits, reverse=True):
        if b > last:
            raise ValueError('Overlapping virtual render calls')
        source = source[:a] + replacement + source[b:]
        last = a
    return (PREAMBLE + source if edits else source), evidence
