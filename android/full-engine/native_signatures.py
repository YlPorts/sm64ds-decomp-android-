"""Separate reviewed C++ shadow signatures using Clang AST locations.

MSVC encodes return types and class/struct distinctions that Itanium omits.
Source-level ABI tags preserve each body AND route callers to the variant their
declaration describes. Only generated, preprocessed copies are modified.
"""
from __future__ import annotations
import re

# Explicitly reviewed collisions. Never infer new engine signatures from names.
RETURNS = {
    '_Z14ApproachLinearRsss': {'void', 'int'},
    '_ZN12MeshCollider8LoadFileER13SharedFilePtr': {'char*', 'KCL_File*'},
    '_ZN14BlendModelAnim7SetAnimER8BCA_Fileiiit': {'void', 'int'},
    '_ZN16MeshColliderBase6EnableEP5Actor': {'void', 'int'},
    '_ZN16MeshColliderBase7DisableEv': {'void', 'int'},
    '_ZN16MeshColliderBase9IsEnabledEv': {'bool', 'int'},
    '_ZN18MovingMeshCollider7SetFileEP8KCL_FileRK9Matrix4x3isR10CLPS_Block': {'void', 'int'},
    '_ZN18NestedHeapIterator4NextEP13HeapAllocator': {'unsignedchar*', 'HeapAllocator*', 'int'},
    '_ZN8Particle6System9NewSimpleEjiii': {'void', 'void*', 'System*', 'Particle::System*'},
    '_ZN8Platform13IsClsnInRangeEii': {'bool', 'int'},
    '_ZN9ModelBase7SetFileEP8BMD_Fileii': {'void', 'int'},
    '_ZNK12WithMeshClsn10IsOnGroundEv': {'bool', 'int'},
    '_ZNK12WithMeshClsn13JustHitGroundEv': {'bool', 'int'},
    '_ZNK7PathPtr7GetNodeER7Vector3j': {'void', 'int'},
    '_ZN13RaycastGround12SetObjAndPosERK7Vector3P5Actor': {'void', 'int'},
    '_ZN3OAM6RenderEbP7OamAttriiiiP9Matrix2x2': {'void', 'int'},
    '_ZNK7PathPtr8NumNodesEv': {'unsignedint', 'int'},
    '_ZN5Scene9SetFadersEP15FaderBrightness': {'void'},
    '_ZN2GX7LoadTexEPKvjj': {'void'},
}
DTORS = {'_ZN5ActorD0Ev', '_ZN5ActorD1Ev', '_ZN5ActorD2Ev'}
SYMBOLS = set(RETURNS) | DTORS


def declarations(ast: dict):
    if ast.get('kind') in ('FunctionDecl', 'CXXMethodDecl', 'CXXDestructorDecl'):
        yield ast
    for child in ast.get('inner', []):
        yield from declarations(child)


def records(ast: dict):
    if ast.get('kind') == 'CXXRecordDecl' and ast.get('name') == 'Actor':
        yield ast
    for child in ast.get('inner', []):
        yield from records(child)


def typedefs(ast: dict):
    if ast.get('kind') == 'TypedefDecl' and ast.get('name'):
        yield ast['name'], ast.get('type', {}).get('desugaredQualType', ast.get('type', {}).get('qualType', ''))
    for child in ast.get('inner', []):
        yield from typedefs(child)


def tag_for(node: dict, actor_kind: str | None, virtual_dtor: bool,
            static_methods: set[str], aliases: dict[str, str]) -> str:
    symbol = node['mangledName']
    if symbol in DTORS:
        return 'sm64ds_virtual' if virtual_dtor else 'sm64ds_nonvirtual'
    result = re.sub(r'\s+', '', node['type']['qualType'].split('(', 1)[0])
    if result in aliases:
        result = re.sub(r'\s+', '', aliases[result])
    if result == 'signedint':
        result = 'int'
    if result not in RETURNS[symbol]:
        raise ValueError(f'Unreviewed return type for {symbol}: {result}')
    if result == 'Particle::System*':
        result = 'System*'
    tag = 'sm64ds_ret_' + result.replace('*', '_ptr')
    if symbol == '_ZN5Scene9SetFadersEP15FaderBrightness':
        tag += '_static' if symbol in static_methods else '_member'
    if symbol == '_ZN2GX7LoadTexEPKvjj':
        tag += '_namespace' if node['kind'] == 'FunctionDecl' else '_class'
    if symbol == '_ZN16MeshColliderBase6EnableEP5Actor' and result == 'void':
        if actor_kind not in ('class', 'struct'):
            raise ValueError('Enable requires an unambiguous Actor class/struct declaration')
        tag += '_' + actor_kind
    return tag


def transform(source: bytes, ast: dict) -> tuple[bytes, list[dict]]:
    decls = [n for n in declarations(ast) if n.get('mangledName') in SYMBOLS]
    actor_kinds = {n['tagUsed'] for n in records(ast) if n.get('tagUsed')}
    actor_kind = next(iter(actor_kinds)) if len(actor_kinds) == 1 else None
    virtual_dtor = any(n.get('virtual') for n in decls if n['mangledName'] in DTORS)
    static_methods = {n['mangledName'] for n in decls if n.get('storageClass') == 'static'}
    aliases = dict(typedefs(ast))
    edits = {}; audit = []
    for n in decls:
        if n.get('isImplicit'):
            continue
        begin = n['range']['begin']
        if 'offset' not in begin or 'spellingLoc' in begin or 'expansionLoc' in begin:
            raise ValueError('Expected an expanded declaration in preprocessed input')
        pos = begin['offset']
        if not 0 <= pos < len(source):
            raise ValueError('Declaration offset outside source')
        tag = tag_for(n, actor_kind, virtual_dtor, static_methods, aliases)
        value = f'__attribute__((abi_tag("{tag}"))) '.encode()
        if pos in edits and edits[pos] != value:
            raise ValueError('Overlapping signature attributes')
        edits[pos] = value
        audit.append({'symbol': n['mangledName'], 'type': n['type']['qualType'],
                      'tag': tag, 'offset': pos,
                      'definition': any(x['kind'] == 'CompoundStmt' for x in n.get('inner', []))})
    for pos, value in sorted(edits.items(), reverse=True):
        source = source[:pos] + value + source[pos:]
    return source, audit


def strip_compile_io(command: list[str]) -> list[str]:
    cmd = command.copy()
    for option in ('-o', '-c'):
        if cmd.count(option) != 1:
            raise ValueError('Expected a single compile input/output')
        i = cmd.index(option)
        del cmd[i:i + 2]
    return cmd


def expanded_command(command: list[str], source: str) -> list[str]:
    cmd = strip_compile_io(command)
    # The preprocessor has already applied include files and macro definitions.
    # Keeping -include here would reintroduce untagged declarations.
    for option in ('-include', '-x'):
        while option in cmd:
            i = cmd.index(option)
            del cmd[i:i + 2]
    return cmd + ['-x', 'c++-cpp-output', source]
