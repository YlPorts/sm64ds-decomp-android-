"""Fail-closed checks for the pinned stage-7 transformations."""
import copy
import tempfile
import unittest
from pathlib import Path
from adapt_sources import transform, validate, load_manifest, prepare
from adapt_calls import adapt, masked

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = load_manifest()

class SourcePortabilityTests(unittest.TestCase):
    def test_all_upstream_inputs_are_pinned(self):
        for rel, rule in MANIFEST['sources'].items():
            with self.subTest(source=rel):
                validate((ROOT / rel).read_bytes(), rule['sha256'], rel)
                transform((ROOT / rel).read_text(), rule)

    def test_every_exact_anchor_rejects_deletion_and_duplication(self):
        for rel, rule in MANIFEST['sources'].items():
            source = (ROOT / rel).read_text()
            for edit in rule.get('edits', []):
                with self.subTest(source=rel, anchor=edit['old'][:40]):
                    bad = source.replace(edit['old'], '', 1)
                    with self.assertRaises(ValueError): transform(bad, rule)
                    with self.assertRaises(ValueError): transform(source + '\n' + edit['old'], rule)

    def test_modified_input_rejected(self):
        for rel, rule in MANIFEST['sources'].items():
            with self.assertRaises(ValueError): validate((ROOT / rel).read_bytes() + b' ', rule['sha256'], rel)

    def test_tokens_leave_comments_and_literals_unchanged(self):
        text='// Sleep GetTickCount\nconst char*s="Sleep GetTickCount";\nGetTickCount(); ::Sleep(1);'
        out=transform(text, {'code_tokens':{'GetTickCount':'ticks', 'Sleep':'sleep_ms'}})
        self.assertIn('// Sleep GetTickCount',out)
        self.assertIn('"Sleep GetTickCount"',out)
        self.assertIn('ticks(); ::sleep_ms(1);',out)

    def test_callback_addresses_are_not_invoked_or_reordered(self):
        rel='src/RotatingFirebar_Spawn.cpp'; out=transform((ROOT/rel).read_text(),MANIFEST['sources'][rel])
        self.assertIn('8, 0x3c, reinterpret_cast<void*>(&_ZN19CylinderClsnWithPosC1Ev), reinterpret_cast<void*>(&_ZN19CylinderClsnWithPosD1Ev)',out)

    def test_player_early_branch_does_not_evaluate_other_path(self):
        rel='src/_ZN6Player17St_HoldLight_MainEv.cpp';out=transform((ROOT/rel).read_text(),MANIFEST['sources'][rel])
        self.assertLess(out.index('int var_r4;'),out.index('goto end;'))
        self.assertGreater(out.index('var_r4 = 0;'),out.index('goto end;'))
        self.assertEqual(out.count('Player_AdvanceAnims(((char*)this));'),1)

    def test_king_receiver_load_stays_after_early_exits(self):
        rel='src/func_ov078_02124cf4.cpp';out=transform((ROOT/rel).read_text(),MANIFEST['sources'][rel])
        self.assertLess(out.index('unsigned char* other;'),out.index('goto done;'))
        self.assertGreater(out.index('other = *'),out.index('goto done;'))

    def test_no_fabricated_return_values(self):
        for rel in ('src/func_ov002_020e8c34.c','src/func_ov002_020e8dd8.c','src/func_ov014_0211150c.c'):
            out=transform((ROOT/rel).read_text(),MANIFEST['sources'][rel])
            self.assertNotIn('return 0;',out)
            self.assertNotIn('return 1;',out)
            self.assertIn('void '+Path(rel).stem+'(',out)

    def test_existing_call_adaptation_composes(self):
        for rel,rule in MANIFEST['sources'].items():
            text=(ROOT/rel).read_text()
            if '__fastcall' in masked(text) or '__cdecl' in masked(text):
                converted,_=adapt(text)
                with self.subTest(source=rel): transform(converted,rule)

    def test_original_selection_preserved_and_error_reported(self):
        rel='src/func_0200d8c8.c'
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/'bad.c';bad.write_text('no expected source here')
            unit={'source':str(bad),'original_source':str(ROOT/rel),'group':{},'target':'game','generated':False}
            unchanged={'source':'not-present.c','group':{},'target':'game','generated':False}
            out=prepare([unit,unchanged],Path(tmp))
            self.assertEqual(len(out),2)
            self.assertIn('adaptation_error',out[0])
            self.assertEqual(out[1],unchanged)

if __name__=='__main__':unittest.main()
