import unittest
from native_signatures import transform, strip_compile_io, expanded_command
from isolate_signatures import referenced_units


class SignatureValidationTests(unittest.TestCase):
    def declaration(self, result='bool', offset=0):
        return {'kind': 'CXXMethodDecl', 'mangledName': '_ZNK12WithMeshClsn10IsOnGroundEv',
                'type': {'qualType': result + ' () const'},
                'range': {'begin': {'offset': offset}}, 'inner': []}

    def test_unknown_return_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unreviewed return'):
            transform(b'int declaration;', self.declaration('double'))

    def test_bad_offset_rejected(self):
        with self.assertRaisesRegex(ValueError, 'offset outside'):
            transform(b'x', self.declaration(offset=8))

    def test_unexpanded_macro_rejected(self):
        node = self.declaration()
        node['range']['begin'] = {'spellingLoc': {'offset': 0}}
        with self.assertRaisesRegex(ValueError, 'expanded declaration'):
            transform(b'x', node)

    def test_recompile_does_not_reinclude_untagged_headers(self):
        cmd = ['clang++', '-include', 'compat.h', '-Iheaders', '-x', 'c++',
               '-O2', '-c', 'original.cpp', '-o', 'old.o']
        self.assertEqual(expanded_command(cmd, 'tagged.ii'),
                         ['clang++', '-Iheaders', '-O2', '-x', 'c++-cpp-output', 'tagged.ii'])

    def test_multiple_inputs_rejected(self):
        with self.assertRaises(ValueError):
            strip_compile_io(['clang++', '-c', 'a.cpp', '-c', 'b.cpp', '-o', 'a.o'])

    def test_undefined_callers_are_selected_too(self):
        text = ('/out/00002.o: _ZNK12WithMeshClsn10IsOnGroundEv U 0 0\n'
                '/out/00003.o: _ZNK12WithMeshClsn10IsOnGroundEv T 0 40\n'
                '/out/00004.o: unrelated T 0 40\n')
        self.assertEqual(referenced_units(text), {2, 3})


if __name__ == '__main__':
    unittest.main()
