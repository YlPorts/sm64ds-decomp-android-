import importlib.util
from pathlib import Path
import tempfile
import unittest
SPEC = importlib.util.spec_from_file_location('adapt', Path(__file__).parents[1] / 'tools/adapt_ntr.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

class NtrAdapterTests(unittest.TestCase):
    def runtime(self):
        return '#include "../hal/dsstate_seg.h"\nDSSTATE_BEGIN\nint data_020a6460[8];\nstruct { unsigned handler, active, arg; } data_020a60c4[8];\nDSSTATE_END\n'
    def test_runtime_enrolls_both_globals(self):
        text = mod.adapt_text('runtime.cpp', self.runtime())
        self.assertEqual(text.count('SM64DS_CAPTURED'), 2)
        self.assertNotIn('DSSTATE_BEGIN', text)
    def test_missing_definition_rejected(self):
        with self.assertRaises(ValueError):
            mod.adapt_text('runtime.cpp', self.runtime().replace('data_020a6460[8]', 'different[8]'))
    def test_duplicate_block_rejected(self):
        with self.assertRaises(ValueError):
            mod.adapt_text('runtime.cpp', self.runtime() + '\nDSSTATE_BEGIN\n')
    def test_io_buffer_uses_path_limit(self):
        self.assertIn('char namebuf[PATH_MAX];', mod.adapt_text('io.cpp', 'char namebuf[MAX_PATH];'))
    def test_duplicate_io_anchor_rejected(self):
        with self.assertRaises(ValueError):
            mod.adapt_text('io.cpp', 'char namebuf[MAX_PATH];\nchar namebuf[MAX_PATH];')
    def test_unreviewed_blob_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'runtime.cpp'; src.write_text(self.runtime())
            with self.assertRaises(ValueError): mod.generate(src, Path(tmp) / 'out.cpp')
    def test_backup_enrolls_only_mutable_definitions(self):
        source = '#include "hal/dsstate_seg.h"\nDSSTATE_BEGIN\nint data_port_backup_device[10] = {};\nunsigned char data_020a4b40[8] = {};\nint data_020a8160[8] = {};\nPortBackupFill g_port_backup_fill;\nDSSTATE_END\n'
        self.assertEqual(mod.adapt_text('backup.cpp', source).count('SM64DS_CAPTURED'), 4)

if __name__ == '__main__': unittest.main()
