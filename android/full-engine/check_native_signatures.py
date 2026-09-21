#!/usr/bin/env python3
"""Execute signature routing and real IsOnGround flag conversion probes.

The object layouts besides the original flags reader are test fixtures, not a
running game. This checks caller routing, not engine gameplay or virtual tables.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
from native_signatures import transform

FIXTURES = {
    'ground_bool.cpp': '''
extern "C" int ground_original(const void*);
struct WithMeshClsn { bool IsOnGround() const; };
bool WithMeshClsn::IsOnGround() const { return ground_original(this) != 0; }
''',
    'ground_int.cpp': '''
extern "C" int ground_original(const void*);
typedef signed int s32;
struct WithMeshClsn { s32 IsOnGround() const; };
s32 WithMeshClsn::IsOnGround() const { return ground_original(this); }
''',
    'ground_bool_caller.cpp': '''
struct WithMeshClsn { bool IsOnGround() const; };
extern "C" int call_bool(const void*p) { return ((const WithMeshClsn*)p)->IsOnGround(); }
''',
    'ground_int_caller.cpp': '''
struct WithMeshClsn { int IsOnGround() const; };
extern "C" int call_int(const void*p) { return ((const WithMeshClsn*)p)->IsOnGround(); }
''',
    'static_scene.cpp': '''
struct FaderBrightness {};
extern "C" int marks[8];
struct Scene { static void SetFaders(FaderBrightness*); };
void Scene::SetFaders(FaderBrightness*) { marks[0] += 3; }
extern "C" void call_static() { Scene::SetFaders(0); }
''',
    'member_scene.cpp': '''
struct FaderBrightness {};
extern "C" int marks[8];
struct Scene { int value; void SetFaders(FaderBrightness*); };
void Scene::SetFaders(FaderBrightness*) { marks[1] += value; }
extern "C" void call_member() { Scene s{7}; s.SetFaders(0); }
''',
    'gx_namespace.cpp': '''
extern "C" int marks[8];
namespace GX { void LoadTex(const void*, unsigned, unsigned); }
void GX::LoadTex(const void*, unsigned x, unsigned y) { marks[2] += x + y; }
extern "C" void call_gx_namespace() { GX::LoadTex(0, 2, 3); }
''',
    'gx_class.cpp': '''
extern "C" int marks[8];
struct GX { static void LoadTex(const void*, unsigned, unsigned); };
void GX::LoadTex(const void*, unsigned x, unsigned y) { marks[3] += x * y; }
extern "C" void call_gx_class() { GX::LoadTex(0, 2, 3); }
''',
    'actor_virtual.cpp': '''
extern "C" int marks[8];
struct Actor { virtual ~Actor(); };
Actor::~Actor() { ++marks[4]; }
extern "C" void call_virtual() { Actor a; }
''',
    'actor_nonvirtual.cpp': '''
extern "C" int marks[8];
struct Actor { ~Actor(); };
Actor::~Actor() { ++marks[5]; }
extern "C" void call_nonvirtual() { Actor a; }
''',
    'enable_struct.cpp': '''
extern "C" int marks[8];
struct Actor;
struct MeshColliderBase { void Enable(Actor*); };
void MeshColliderBase::Enable(Actor*) { marks[6] += 11; }
extern "C" void call_enable_struct() { MeshColliderBase b; b.Enable(0); }
''',
    'enable_class.cpp': '''
extern "C" int marks[8];
class Actor;
struct MeshColliderBase { void Enable(Actor*); };
void MeshColliderBase::Enable(Actor*) { marks[7] += 13; }
extern "C" void call_enable_class() { MeshColliderBase b; b.Enable(0); }
''',
    'main.cpp': '''
extern "C" {
int marks[8] = {};
int call_bool(const void*); int call_int(const void*);
void call_static(); void call_member();
void call_gx_namespace(); void call_gx_class();
void call_virtual(); void call_nonvirtual();
void call_enable_struct(); void call_enable_class();
}
int main() {
    unsigned int object[5] = {};
    if (call_bool(object) != 0 || call_int(object) != 0) return 1;
    object[4] = 16;
    if (call_bool(object) != 1 || call_int(object) != 16) return 2;
    object[4] = 0xffffffef;
    if (call_bool(object) != 0 || call_int(object) != 0) return 3;
    call_static(); call_member(); call_gx_namespace(); call_gx_class();
    call_virtual(); call_nonvirtual(); call_enable_struct(); call_enable_class();
    const int expected[8] = {3, 7, 5, 6, 1, 1, 11, 13};
    for (int i=0; i<8; ++i) if (marks[i] != expected[i]) return 10+i;
    return 0;
}
''',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clang', required=True)
    p.add_argument('--cxx', default='g++')
    p.add_argument('--cc', default='gcc')
    p.add_argument('--flags', default='')
    p.add_argument('--runner', default='native')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    flags = shlex.split(a.flags)
    commands = []
    def run(cmd, name, success=True):
        commands.append(cmd)
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        (out / (name + '.log')).write_bytes(r.stdout + r.stderr)
        if success and r.returncode:
            raise RuntimeError((r.stdout + r.stderr).decode(errors='replace'))
        return r
    originals = []; tagged = []
    for name, source in FIXTURES.items():
        src = out / name; src.write_text(source)
        obj = out / (name + '.o'); tagged_obj = out / (name + '.tagged.o')
        run([a.cxx, '-std=c++17', '-O0', *flags, '-c', str(src), '-o', str(obj)], name)
        pp = run([a.clang, '-E', '-P', str(src)], name + '.pp').stdout
        pp_file = out / (name + '.ii'); pp_file.write_bytes(pp)
        ast = json.loads(run([a.clang, '-Xclang', '-ast-dump=json', '-fsyntax-only', str(pp_file)], name + '.ast').stdout)
        converted, evidence = transform(pp, ast)
        pp_file.write_bytes(converted)
        run([a.cxx, '-std=c++17', '-O0', *flags, '-c', str(pp_file), '-o', str(tagged_obj)], name + '.tagged')
        originals.append(str(obj)); tagged.append(str(tagged_obj))
    original = out / 'ground-original.o'
    run([a.cc, *flags, '-I', str(root / 'include'),
         '-D_ZNK12WithMeshClsn10IsOnGroundEv=ground_original',
         '-c', str(root / 'src/_ZNK12WithMeshClsn10IsOnGroundEv.c'), '-o', str(original)], 'original')
    negative = run([a.cxx, *flags, *originals, str(original), '-o', str(out / 'must-not-link')], 'negative-link', False)
    if negative.returncode == 0 or not any(s in negative.stderr for s in (b'multiple definition', b'duplicate symbol')):
        raise RuntimeError('Baseline must fail due to native signature collisions')
    exe = out / 'signature-tests'
    run([a.cxx, *flags, *tagged, str(original), '-o', str(exe)], 'tagged-link')
    status = 'COMPILED AND LINKED ONLY'
    if a.runner:
        run([*([] if a.runner == 'native' else shlex.split(a.runner)), str(exe)], 'execution')
        status = 'PASS'
    report = {'scope': '14 routing assertions, including actual recovered IsOnGround body; not gameplay',
              'baseline_duplicate_failure': True, 'tagged_link': True, 'execution': status,
              'commands': commands}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(status)


if __name__ == '__main__':
    main()
