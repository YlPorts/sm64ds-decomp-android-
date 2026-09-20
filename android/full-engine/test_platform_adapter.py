"""Check stage-8 boundary transformations, without pretending to run Android."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adapt_sources import load_manifest, prepare, transform
from adapt_calls import adapt, masked
ROOT=Path(__file__).resolve().parents[2]
class NativePlatformTests(unittest.TestCase):
    def convert(self, rel):
        text=(ROOT/rel).read_text()
        if '__cdecl' in masked(text):text=adapt(text)[0]
        return transform(text,load_manifest()['sources'][rel])
    def test_network_has_real_posix_calls_not_windows_stubs(self):
        code=masked(self.convert('port/hal/comms_loopback.cpp'))
        self.assertNotIn('WS.',code)
        self.assertNotIn('ws_start()',code)
        self.assertIn('sm64ds_net::receive(',code)
        self.assertIn('sm64ds_net::open_udp(',code)
        self.assertIn('sm64ds_net::nonblocking(g_sock) != 0',code)
    def test_wire_and_session_decoders_unchanged(self):
        original=(ROOT/'port/hal/comms_loopback.cpp').read_text()
        converted=self.convert('port/hal/comms_loopback.cpp')
        # Packet parsing/semantics are NOT rewritten to produce a passing test.
        for a,b in [('struct Packet {','static_assert(sizeof(Packet)'),('void lb_become_parent()','int lb_state()')]:
            self.assertEqual(original[original.index(a):original.index(b,original.index(a))],converted[converted.index(a):converted.index(b,converted.index(a))])
    def test_audio_replacement_retains_selected_source_identity(self):
        rel='port/hal/sdat/out_win.cpp'
        with tempfile.TemporaryDirectory() as tmp:
            unit={'source':str(ROOT/rel),'target':'ntr_audio','generated':False,'group':{}}
            result=prepare([unit],Path(tmp))
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['original_source'],str(ROOT/rel))
            self.assertNotIn('adaptation_error',result[0])
            self.assertIn('AAudioStream',Path(result[0]['source']).read_text())
    def test_audio_replacement_cannot_escape_native_directory(self):
        manifest=copy.deepcopy(load_manifest())
        manifest['sources']['port/hal/sdat/out_win.cpp']['replacement']='port/hal/sdat/out_win.cpp'
        with tempfile.TemporaryDirectory() as tmp,patch('adapt_sources.load_manifest',return_value=manifest):
            unit={'source':str(ROOT/'port/hal/sdat/out_win.cpp'),'target':'audio','generated':False,'group':{}}
            result=prepare([unit],Path(tmp))
            self.assertIn('adaptation_error',result[0])
    def test_native_initializer_is_explicit_and_idempotent(self):
        stage=self.convert('port/hal/stage_geom.cpp')
        mods=self.convert('port/hal/fs_mods.cpp')
        self.assertNotIn('__declspec(allocate(".CRT$XCV"))',stage)
        self.assertIn('if (port_fs_mod_filter == geom_filter) return;',stage)
        self.assertIn('port_fs_mod_filter = mod_filter;\n        port_stage_geom_ctor();',mods)
    def test_rollback_probe_uses_monotonic_clock(self):
        code=masked(self.convert('port/hal/rollback_probe.cpp'))
        self.assertNotIn('QueryPerformanceCounter',code)
        self.assertIn('sm64ds_clock_ns(CLOCK_MONOTONIC)',code)
if __name__=='__main__':unittest.main()
