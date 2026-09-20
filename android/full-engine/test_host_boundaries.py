"""Regression checks for the pinned native memory and fault boundaries."""
import json
from pathlib import Path
import unittest
from adapt_calls import masked
from adapt_sources import validate, prepare
from adapt_host_boundaries import transform, function
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RULES = json.loads((HERE/'host_portability.json').read_text())['sources']

class HostBoundaries(unittest.TestCase):
    def test_pinned_originals_and_no_windows_calls(self):
        for rel, rule in RULES.items():
            data = (ROOT/rel).read_bytes()
            validate(data, rule['sha256'], rel)
            text = transform((ROOT/rel).read_text(), rule['native_boundary'])
            self.assertNotIn('#include <windows.h>', text)
            self.assertNotRegex(masked(text), r'\b(__try|__except|VirtualAlloc|GetWriteWatch|CONTEXT)\b')

    def test_unknown_boundary_and_changed_anchor_rejected(self):
        with self.assertRaises(ValueError):
            transform('#include <windows.h>', 'unknown')
        with self.assertRaises(ValueError):
            transform('#include <notwindows.h>', 'scene')
        with self.assertRaises(ValueError):
            function('int f(){', 'int f()', '')
        with self.assertRaises(ValueError):
            function('int f(){} int f(){}', 'int f()', '')

    def test_scene_execution_is_not_replaced(self):
        src = (ROOT/'port/hal/scene_boot.cpp').read_text()
        dst = transform(src, 'scene')
        anchor = '/* TITLE LANE DIAGNOSTIC, run mg12.'
        self.assertEqual(src[src.index(anchor):], dst[dst.index(anchor):])
        self.assertIn('NOT AVAILABLE: x86 hardware watchpoints', dst)

    def test_real_hardware_faults_not_swallowed(self):
        dst = transform((ROOT/'port/unmatched/func_02043fdc_hostcopy.cpp').read_text(), 'actor')
        self.assertIn('catch (const Sm64dsActorDecline &)', dst)
        self.assertNotIn('catch (...)', dst)
        self.assertIn('if (port_faults_fatal()) throw;', dst)
        self.assertNotIn('sigaction(', dst)

    def test_actor_walk_after_guard_is_unchanged(self):
        src = (ROOT/'port/unmatched/func_02043fdc_hostcopy.cpp').read_text()
        dst = transform(src, 'actor')
        # All source after guarded dispatch includes the actual processing walk.
        end_marker = '\nextern "C" __attribute__((weak)) const char *port_crash_dir_get'
        tail = dst[:dst.index(end_marker)]
        suffix = src[src.index('static int port_dispatch_guarded'):]
        # Only the deliberate exception boundary is changed within this suffix.
        suffix = suffix.replace('RaiseException(EXCEPTION_ACCESS_VIOLATION, 0, 0, 0);', 'throw Sm64dsActorDecline{};').replace('    __try {', '    try {').replace(
            '    } __except (port_q_filter(GetExceptionInformation(), &code, &off)) {',
            '    } catch (const Sm64dsActorDecline &) {\n        if (port_faults_fatal()) throw;\n        code = 0xe0640001u; // Native explicit-decline diagnostic, NOT an OS fault.\n        off = 0; // No instruction address is claimed for an intentional decline.')
        self.assertTrue(tail.endswith(suffix))

    def test_snapshot_deltas_are_real_not_write_watch_stubs(self):
        dst = transform((ROOT/'port/hal/rollback.cpp').read_text(), 'rollback')
        self.assertIn('sm64ds_changed_blocks(R.base, R.shadow', dst)
        self.assertIn('NativeRingAllocGuard allocation_guard;', dst)
        self.assertIn('allocation_guard.committed = true;', dst)
        self.assertIn('native byte-compared undo logs', dst)

    def test_destructive_oam_probe_not_falsely_passed(self):
        dst = transform((ROOT/'port/hal/oam_lists.cpp').read_text(), 'oam')
        self.assertIn('NOT RUN: the destructive Windows SEH walk probe', dst)
        self.assertIn('return 2; // Explicitly not a passed probe', dst)
        self.assertIn('sm64ds_bad_read_span(word, sizeof(unsigned short))', dst)

    def test_inventory_retains_original_identities(self):
        units = [{'source':str(ROOT/r), 'target':'walk_window', 'generated':False,
                  'group': {'includes':[]}} for r in RULES]
        with tempfile.TemporaryDirectory() as d:
            result = prepare(units, Path(d))
            self.assertEqual(len(result), len(units))
            for old,new in zip(units,result):
                self.assertNotIn('adaptation_error',new)
                self.assertEqual(new['original_source'],old['source'])
                self.assertTrue(Path(new['source']).is_file())

if __name__ == '__main__': unittest.main()
