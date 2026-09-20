import importlib.util
from pathlib import Path
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('inventory', Path(__file__).with_name('compile_inventory.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class InventoryTests(unittest.TestCase):
    def test_pack(self):
        flags, warnings = m.source_options({'compileCommandFragments':[{'fragment':'/Zp4 /Oy-'}]})
        self.assertEqual(flags,['-fpack-struct=4','-fno-omit-frame-pointer'])
    def test_abi_not_claimed(self):
        flags, warnings = m.source_options({'compileCommandFragments':[{'fragment':'/vmg /vmm'}]})
        self.assertFalse(flags)
        self.assertEqual(len(warnings),2)
    def test_unknown_msvc_flag_is_not_ignored(self):
        with self.assertRaises(ValueError):
            m.source_options({'compileCommandFragments':[{'fragment':'/MadeUp'}]})
    def test_forced_include(self):
        flags, warnings = m.source_options({'compileCommandFragments':[{'fragment':'/FI/safe/header.h'}]})
        self.assertEqual(flags,['-include','/safe/header.h'])
    def test_missing_graph_fails(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError): m.load_units(Path(t),'walk_window')
if __name__ == '__main__': unittest.main()
