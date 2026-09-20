import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('adapt_runtime', Path(__file__).parents[1] / 'tools' / 'adapt_runtime.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

class AdapterTests(unittest.TestCase):
    def source(self):
        return ('#if defined(_WIN32)\n#define WIN32_LEAN_AND_MEAN\n#include <windows.h>\n#endif\n'
                '#if defined(_WIN32)\nvoid trampoline();\n#endif\n'
                '#if defined(_WIN32)\nvoid wait();\n#endif\n'
                '#if !defined(_WIN32)\nvoid unsupported();\n#else\n'
                'std::fprintf(stderr, "rt_run: CreateFiber failed\\n");\n        return 0;\n#endif\n')
    def test_adapts_only_known_guards(self):
        result = adapter.adapt(self.source())
        self.assertIn('#include <windows.h>\n#elif defined(SM64DS_NATIVE_FIBERS)\n', result)
        self.assertEqual(result.count('#if defined(_WIN32) || defined(SM64DS_NATIVE_FIBERS)'), 2)
        self.assertIn('#if !defined(_WIN32) && !defined(SM64DS_NATIVE_FIBERS)', result)
        self.assertIn('ConvertFiberToThread();\n        return 0;', result)
    def test_rejects_changed_guard_count(self):
        with self.assertRaises(ValueError):
            adapter.adapt(self.source() + '#if defined(_WIN32)\n#endif\n')
    def test_rejects_changed_include(self):
        with self.assertRaises(ValueError):
            adapter.adapt(self.source().replace('<windows.h>', '<other.h>'))
    def test_rejects_unknown_cleanup(self):
        with self.assertRaises(ValueError):
            adapter.adapt(self.source().replace('CreateFiber failed', 'allocation failed'))

if __name__ == '__main__':
    unittest.main()
