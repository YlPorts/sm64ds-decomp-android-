import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('adapter_lifetimes', Path(__file__).parents[1] / 'tools/adapt_scheduler.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
# The hash gate in adapt() separately protects the full production input.
# This small fixture exercises rejection of every new replacement anchor.
PARTS = [
    '    bool created;       // came in through func_02058200, not the boot seat',
    'FiberSlot *slot_of(RomThread *t) {',
    '            s.created = false;',
    'void CALLBACK thread_trampoline(void *p) {',
    'int ARMSaveContext(void *ctx) {\n    thread_boot();',
    'void ARMRestoreContext(void *ctx) {\n    thread_boot();',
    '    SwitchToFiber(ts->fiber);',
    '    ++g_stat.resumes;\n    trace("resume %u", from ? from->id : 0u);',
    '    else if (lo == 0 || hi == 0 || hi <= lo)',
]
FIXTURE = '\n'.join(PARTS)
class LifetimeAdapterTests(unittest.TestCase):
    def test_retirement_is_captured_before_switch(self):
        out = a.add_lifetimes(FIXTURE)
        self.assertLess(out.index('old->retired = true'), out.index('SwitchToFiber(ts->fiber)'))
        self.assertIn('native_reap_completed();', out)
        self.assertIn('#include "scheduler_lifecycle.inc"', out)
    def test_every_missing_anchor_is_rejected(self):
        for part in PARTS:
            with self.subTest(part=part):
                with self.assertRaises(ValueError): a.add_lifetimes(FIXTURE.replace(part, '', 1))
    def test_every_duplicate_anchor_is_rejected(self):
        for part in PARTS:
            with self.subTest(part=part):
                with self.assertRaises(ValueError): a.add_lifetimes(FIXTURE + '\n' + part)
    def test_collection_never_reads_retired_record(self):
        text = (Path(__file__).parents[1] / 'include/scheduler_lifecycle.inc').read_text()
        self.assertNotIn('slot.thread->', text)
        self.assertIn('slot.fiber == active', text)
if __name__ == '__main__': unittest.main()
