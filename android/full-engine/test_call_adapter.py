import json
from pathlib import Path
import tempfile
import unittest
from adapt_calls import adapt, masked, prepare

class CallAdapterTests(unittest.TestCase):
    def test_receiver_only_preserved(self):
        s,n=adapt('int __fastcall tick(void *s) { return body(s); }')
        self.assertIn('tick(void *s)',s);self.assertEqual(n['thunks'],1)
    def test_dummy_removed_not_real_argument(self):
        s,n=adapt('int __fastcall tick(void *s, void *, int a, int b) { return body(s,a,b); }')
        self.assertIn('tick(void *s, int a, int b)',s)
    def test_discarded_named_dummy(self):
        s,n=adapt('int __fastcall tick(void *s, void *dead_edx) { (void)dead_edx; return 2; }')
        self.assertIn('(void)nullptr;',s);self.assertNotIn('void *dead_edx',s)
    def test_live_second_argument_rejected(self):
        with self.assertRaises(ValueError):adapt('int __fastcall f(void*s, int a) {return a;}')
    def test_live_edx_rejected(self):
        with self.assertRaises(ValueError):adapt('int __fastcall f(void*s, void *edx) {return edx!=0;}')
    def test_literal_and_comment_untouched(self):
        s='// __fastcall f(void *, void *)\nconst char *x="__fastcall";'
        self.assertEqual(adapt(s)[0],s)
    def test_typedef_and_invocation(self):
        s,n=adapt('typedef int(__fastcall *Fn)(void*,void*,int); int call(void*s,void**v){return ((Fn)v[2])(s,0,71);}')
        self.assertIn('*Fn)(void*,int)',s);self.assertIn('(s,71)',s);self.assertEqual(n['explicit_calls'],1)
    def test_nested_cast_and_invocation(self):
        s,n=adapt('void f(void*s, int a){((void(__fastcall *)(void*,void*,int))((void***)s)[0][4])(s,0,a);}')
        self.assertIn('(s,a)',s);self.assertEqual(n['explicit_calls'],1)
    def test_local_pointer(self):
        s,n=adapt('int(__fastcall*m)(void*,void*)=(int(__fastcall*)(void*,void*))v[1]; int r=m(c,0);')
        self.assertIn('m(c)',s);self.assertNotIn('__fastcall',s)
    def test_direct_thunk_call(self):
        s,n=adapt('int __fastcall f(void*s,void*,int a); int g(void*s){return f(s,0,22);}')
        self.assertIn('f(s,22)',s)
    def test_nonconstant_dummy_call_rejected(self):
        with self.assertRaises(ValueError):adapt('int __fastcall f(void*s,void*,int a); int g(void*s,int d){return f(s,d,22);}')
    def test_macro_declarations_have_independent_arities(self):
        s,n=adapt('#define A(N) int __fastcall f_##N(void*s,void*) {return 0;}\n#define B(N) int __fastcall f_##N(void*s,void*,int a) {return a;}')
        self.assertNotIn('__fastcall',s);self.assertEqual(n['thunks'],2)
    def test_trap_forwarder(self):
        s,n=adapt('int __fastcall st_trap(void*,void*);\n#define T(n) int __fastcall f##n(void*s,void*d){return st_trap(s,d);}')
        self.assertIn('st_trap(s)',s)
    def test_sret_is_native_aggregate(self):
        s,n=adapt('void *__fastcall port_actor_s30_base(void *self,void*,void*out){body(out,self);return out;}')
        self.assertRegex(s,r'Sm64dsAbiVec3\s+port_actor_s30_base\(void \*self\)')
        self.assertIn('return sm64ds_result;',s);self.assertEqual(n['sret'],1)
    def test_sret_contract_change_rejected(self):
        with self.assertRaises(ValueError):adapt('void *__fastcall whomp_s30(void*s,void*,int out){return 0;}')
    def test_cdecl_plain_signature_retained(self):
        s,n=adapt('typedef int(__cdecl*Fn)(void*,int);')
        self.assertIn('*Fn)(void*,int)',s);self.assertEqual(n['cdecl'],1)
    def test_allowlist_is_sha256(self):
        manifest=json.loads(Path(__file__).with_name('call_abi_inputs.json').read_text())
        self.assertEqual(set(manifest['trees']),{'port','src','include'})
        self.assertGreater(len(manifest['generated_sha256']),10)
        self.assertTrue(all(len(x)==64 and all(c in '0123456789abcdef' for c in x) for x in manifest['generated_sha256']))

if __name__=='__main__':unittest.main()
