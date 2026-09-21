import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from native_virtual_calls import transform
from resolve_linkage import fader_source, symbols, validate_manifest


class LinkageTests(unittest.TestCase):
    def test_reviewed_upstream_evidence(self):
        path = Path(__file__).with_name('linkage_aliases.json')
        aliases = validate_manifest(json.loads(path.read_text()))
        self.assertEqual(len(aliases), 452)
        self.assertFalse(aliases.keys() & set(aliases.values()))

    def test_changed_or_unpinned_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'bridge.cpp'
            source.write_text('#pragma comment(linker, "/alternatename:_old=_real")\n')
            manifest = {'source_sha256': {'bridge.cpp': hashlib.sha256(source.read_bytes()).hexdigest()},
                        'bindings': {'old': {'target': 'real', 'upstream': [
                            {'path': 'bridge.cpp', 'line': 1, 'from': '_old', 'to': '_real'}]}}}
            self.assertEqual(validate_manifest(manifest, root), {'old': 'real'})
            for change in ('target', 'evidence', 'hash', 'unpinned'):
                bad = copy.deepcopy(manifest)
                if change == 'target': bad['bindings']['old']['target'] = 'real;evil'
                if change == 'evidence': bad['bindings']['old']['upstream'][0]['to'] = '_other'
                if change == 'hash': bad['source_sha256']['bridge.cpp'] = '0' * 64
                if change == 'unpinned': bad['source_sha256'] = {}
                with self.subTest(change=change), self.assertRaises(ValueError):
                    validate_manifest(bad, root)

    def test_symbol_types_remain_distinct(self):
        table = symbols('/tmp/00123.o: old U 0 0\n/tmp/00123.o: real T 0 8\n'
                        '/tmp/00456.o: optional w 0 0\n/tmp/00456.o: table V 0 40\n')
        self.assertEqual(table[123], {'old': 'U', 'real': 'T'})
        self.assertEqual(table[456], {'optional': 'w', 'table': 'V'})

    def test_changed_fader_destructor_is_rejected(self):
        with self.assertRaises(ValueError): fader_source(b'virtual ~HalFaderWipe() { changed(); }')

    @staticmethod
    def call_ast(qualified=False, virtual=True):
        source = b'p.member.' + (b'Base::' if qualified else b'') + b'M(0)'
        def loc(offset, size=1): return {'offset': offset, 'tokLen': size}
        member_end = source.index(b'M')
        return source, {'inner': [
            {'id': 'method', 'kind': 'CXXMethodDecl', 'mangledName': '_ZN4Base1MEPv', 'virtual': virtual},
            {'kind': 'CXXMemberCallExpr', 'inner': [
                {'kind': 'MemberExpr', 'name': 'M', 'referencedMemberDecl': 'method', 'isArrow': False,
                 'range': {'begin': loc(0), 'end': loc(member_end)}, 'inner': [
                     {'kind': 'MemberExpr', 'range': {'begin': loc(0), 'end': loc(2, 6)}}]}]}]}

    def test_virtual_receiver_keeps_expression_and_arguments(self):
        source, ast = self.call_ast()
        converted, evidence = transform(source, ast)
        self.assertTrue(converted.endswith(b'sm64ds_dynamic_receiver(&(p.member))->M(0)'))
        self.assertEqual(evidence[0]['receiver'], 'p.member')

    def test_qualified_and_nonvirtual_calls_fail_closed(self):
        for kwargs in ({'qualified': True}, {'virtual': False}):
            source, ast = self.call_ast(**kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): transform(source, ast)

    def test_unreviewed_calls_are_untouched(self):
        source, ast = self.call_ast()
        ast['inner'][0]['mangledName'] = '_ZN4Real1MEPv'
        self.assertEqual(transform(source, ast), (source, []))


if __name__ == '__main__':
    unittest.main()
