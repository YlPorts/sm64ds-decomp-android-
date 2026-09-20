import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from adapt_native_faces import manifest, elide, prepare, ROOT
from adapt_calls import masked

class NativeFacesTests(unittest.TestCase):
    def setUp(self):
        self.rules=manifest();self.text=(ROOT/self.rules['face_source']).read_text()
    def test_source_identity_and_allowlist(self):
        self.assertEqual(hashlib.sha256(self.text.encode()).hexdigest(),self.rules['face_sha256'])
        self.assertEqual(len(self.rules['faces']),64)
        self.assertEqual(len({f['symbol'] for f in self.rules['faces']}),64)
    def test_only_reviewed_definitions_are_retired(self):
        output=elide(self.text,self.rules['faces'])
        for f in self.rules['faces']:
            self.assertNotRegex(masked(output),re.escape(f['symbol'])+r'\s*\([^;{}]*\)\s*\{')
        # Different target, boolean conversion and return-type mismatch are NOT elided.
        for symbol in ('_ZN4Heap7_SizeofEPv','_ZN9ActorBase14BeforeBehaviorEv','_ZN6Player17St_PunchKick_InitEv','_ZTV18TextureTransformer'):
            self.assertIn(symbol,output)
        self.assertIn('int Player::St_GroundPound_Main()',output)
    def test_other_code_and_comments_preserved(self):
        output=elide(self.text,self.rules['faces'])
        self.assertTrue(output.startswith(self.text[:self.text.index('void _ZN5Actor24KillAndTrackInDeathTableEv')]))
        self.assertIn('C-linkage forwarder faces are LOAD-BEARING PLUMBING',output)
        self.assertTrue(output.endswith(self.text[self.text.rindex('#pragma comment'):]))
    def test_changed_target_receiver_result_rejected(self):
        face=next(f for f in self.rules['faces'] if 'CylinderClsn5Clear' in f['symbol'])
        for old,new in [('CylinderClsn::Clear();','CylinderClsn::Update();'),('void *self)\n{ ((CylinderClsn *)self)->CylinderClsn::Clear();','void *other)\n{ ((CylinderClsn *)self)->CylinderClsn::Clear();'),('CylinderClsn::Clear();','CylinderClsn::Clear(); other();')]:
            with self.assertRaises(ValueError):elide(self.text.replace(old,new),[face])
        with self.assertRaises(ValueError):elide(self.text,[{**face,'result':'int'}])
    def test_deleted_or_duplicated_definition_rejected(self):
        f=next(f for f in self.rules['faces'] if 'CylinderClsn5Clear' in f['symbol'])
        code='void '+f['symbol']+'(void *self) { ((CylinderClsn *)self)->CylinderClsn::Clear(); }'
        with self.assertRaises(ValueError):elide('',[f])
        with self.assertRaises(ValueError):elide(code+'\n'+code,[f])
    def units(self):
        return [{'source':str(ROOT/r),'target':'port_slice_shared','generated':False,'group':{'includes':[]}} for r in [self.rules['face_source']]+[f['provider'] for f in self.rules['faces']]]
    def test_units_and_providers_preserved(self):
        units=self.units()
        with tempfile.TemporaryDirectory() as d:
            result=prepare(units,Path(d))
            self.assertEqual(len(units),len(result));self.assertNotIn('adaptation_error',result[0])
            self.assertEqual(result[1:],units[1:])
            self.assertEqual(result[0]['original_source'],units[0]['source'])
    def test_missing_or_ambiguous_provider_rejected(self):
        units=self.units()
        for changed in (units[:-1],units+[units[-1]]):
            with tempfile.TemporaryDirectory() as d:
                result=prepare(changed,Path(d))
                self.assertIn('adaptation_error',result[0])
                self.assertEqual(len(result),len(changed))
    def test_unrelated_selection_unmodified(self):
        units=self.units()[1:]
        with tempfile.TemporaryDirectory() as d:self.assertIs(prepare(units,Path(d)),units)

if __name__=='__main__':unittest.main()
