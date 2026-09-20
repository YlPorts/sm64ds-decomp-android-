import hashlib
from pathlib import Path
import tempfile
import unittest
from isolate_symbols import collision_names, header_text, renamed_symbol, replay_command, provider_audit, read_definitions

class IsolationTests(unittest.TestCase):
 def test_valid_census(self):
  self.assertEqual(collision_names({'strong_duplicate_symbol_groups':1,'strong_duplicates':{'_ZN1A1fEv':[{'index':1},{'index':2}]}}),['_ZN1A1fEv'])
 def test_census_count_mismatch(self):
  with self.assertRaises(ValueError):collision_names({'strong_duplicate_symbol_groups':2,'strong_duplicates':{}})
 def test_census_non_identifier(self):
  with self.assertRaises(ValueError):collision_names({'strong_duplicate_symbol_groups':1,'strong_duplicates':{'bad-name':[{'index':1},{'index':2}]}})
 def test_same_unit_not_collision(self):
  with self.assertRaises(ValueError):collision_names({'strong_duplicate_symbol_groups':1,'strong_duplicates':{'_Za':[{'index':1},{'index':1}]}})
 def test_header_preserves_map(self):
  self.assertIn('#define _ZN1A1fEv sm64ds_cabi_ZN1A1fEv',header_text(['_ZN1A1fEv']))
 def test_header_rejects_injection(self):
  with self.assertRaises(ValueError):header_text(['_Za\n#error injected'])
 def test_header_rejects_duplicate(self):
  with self.assertRaises(ValueError):header_text(['_Za','_Za'])
 def test_literal_rename(self):
  self.assertEqual(renamed_symbol('_ZN1A1fEv',{'_ZN1A1fEv'}),'sm64ds_cabi_ZN1A1fEv')
 def test_native_name_not_changed_by_name_alone(self):
  self.assertIsNone(renamed_symbol('_ZN1B1fEv',{'_ZN1A1fEv'}))
 def test_cpp_free_nested_spelling(self):
  self.assertEqual(renamed_symbol('_Z17_ZN6Player4HealEiP6Playeri',{'_ZN6Player4HealEi'}),'_Z28sm64ds_cabi_ZN6Player4HealEiP6Playeri')
 def test_never_guess_arbitrary_mangling(self):
  self.assertIsNone(renamed_symbol('_ZN4Test17_ZN6Player4HealEiEv',{'_ZN6Player4HealEi'}))
 def test_both_providers_survive(self):
  r=provider_audit({0:{('_Za','T')},1:{('_Za','T')}},{0:{('_Za','T')},1:{('sm64ds_cabi_Za','T')}},{'_Za'})
  self.assertTrue(r['passed']);self.assertEqual(r['before_definitions'],2)
 def test_wrong_object_is_rejected(self):
  self.assertFalse(provider_audit({0:{('_Za','T')}},{1:{('sm64ds_cabi_Za','T')}},{'_Za'})['passed'])
 def test_weak_substitution_is_rejected(self):
  self.assertFalse(provider_audit({0:{('_Za','T')}},{0:{('sm64ds_cabi_Za','W')}},{'_Za'})['passed'])
 def test_changed_type_is_rejected(self):
  self.assertFalse(provider_audit({0:{('_Za','T')}},{0:{('sm64ds_cabi_Za','D')}},{'_Za'})['passed'])
 def test_new_alias_not_counted(self):
  self.assertFalse(provider_audit({0:{('_Za','T')}},{0:{('_Za','T'),('sm64ds_cabi_Zb','T')}},{'_Za','_Zb'})['passed'])
 def row(self,p):
  return {'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
          'command':['cc','-x','c','-O2','-DMYFLAG=1','-c',str(p),'-o','old.o']}
 def test_replay_preserves_input_and_flags(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'in.c';p.write_text('int a;');row=self.row(p)
   cmd=replay_command(row,Path('map.h'),Path('new.o'))
   self.assertEqual(cmd,['cc','-include','map.h','-x','c','-O2','-DMYFLAG=1','-c',str(p),'-o','new.o'])
   self.assertEqual(row['command'][-1],'old.o')
 def test_changed_source_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'in.c';p.write_text('int a;');row=self.row(p);p.write_text('int b;')
   with self.assertRaises(ValueError):replay_command(row,Path('map.h'),Path('new.o'))
 def test_different_command_input_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'in.c';p.write_text('int a;');row=self.row(p);row['command'][-3]='other.c'
   with self.assertRaises(ValueError):replay_command(row,Path('map.h'),Path('new.o'))
 def test_nm_types_and_indices(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'nm.txt';p.write_text('/tmp/00312.o: _Za T 0 10\n/tmp/00312.o: weak W 10 3\n/tmp/00313.o: _ZTVb D 0 8\n')
   self.assertEqual(read_definitions(p),{312:{('_Za','T')},313:{('_ZTVb','D')}})

if __name__=='__main__':unittest.main()
