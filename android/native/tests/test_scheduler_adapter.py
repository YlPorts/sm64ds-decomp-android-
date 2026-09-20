import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('scheduler_adapter', Path(__file__).parents[1] / 'tools/adapt_scheduler.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
FIXTURE = '''#if defined(_WIN32)
#include <windows.h>
void f() { GetCurrentThreadId(); GetLastError(); GetCurrentFiber(); }
int error = ERROR_ALREADY_FIBER;
#endif
ThreadBoot() {
        thread_boot();
        thread_proof();
    }
'''
class SchedulerAdapterTests(unittest.TestCase):
    def test_native_conversion_does_not_define_windows(self):
        result = adapter.rewrite(FIXTURE)
        self.assertNotIn('#include <windows.h>', result)
        self.assertNotIn('#define _WIN32', result)
        self.assertIn('SM64DS_NATIVE_FIBERS', result)
        self.assertIn('sizeof(void *) == 4', result)
        self.assertIn('current_fiber()', result)
        self.assertIn('ThreadBoot() = default;', result)
        self.assertIn('sm64ds_native_scheduler_init', result)
    def test_missing_include_rejected(self):
        with self.assertRaises(ValueError):
            adapter.rewrite(FIXTURE.replace('#include <windows.h>', ''))
    def test_changed_dependency_rejected(self):
        with self.assertRaises(ValueError):
            adapter.rewrite(FIXTURE.replace('GetCurrentFiber()', 'NewFunction()'))
    def test_unreviewed_upstream_cannot_be_adapted(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'source.cpp', Path(tmp)/'output.cpp'
            source.write_text(FIXTURE)
            with self.assertRaises(ValueError): adapter.adapt(source, output)
            self.assertFalse(output.exists())
if __name__ == '__main__': unittest.main()
