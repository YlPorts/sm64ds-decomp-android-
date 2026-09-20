"""Pinned controller/touch integration. Do not claim these tests run Android."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapt_calls import close_at, masked
from adapt_sources import load_manifest,prepare,transform,validate
ROOT=Path(__file__).resolve().parents[2]
class AndroidInputTests(unittest.TestCase):
    def setUp(self):
        self.rel='port/hal/sub_screen.cpp'
        self.old=(ROOT/self.rel).read_text()
        self.rule=load_manifest()['sources'][self.rel]
        self.new=transform(self.old,self.rule)
    def body(self,text,name):
        import re
        code=masked(text);m=re.search(r'\b'+name+r'\([^;{}]*\)\s*\{',code)
        self.assertIsNotNone(m,name);b=code.index('{',m.start())
        return text[m.start():close_at(code,b)+1]
    def test_source_is_pinned(self):
        validate((ROOT/self.rel).read_bytes(),self.rule['sha256'],self.rel)
        with self.assertRaises(ValueError):validate(b'changed',self.rule['sha256'],self.rel)
    def test_source_selection_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            units=[{'source':str(ROOT/r),'target':'game','generated':False,'group':{}} for r in [self.rel,'port/hal/pad_backend.cpp']]
            result=prepare(units,Path(tmp));self.assertEqual(len(result),2)
            for u,v in zip(units,result):
                self.assertEqual(u['source'],v['original_source']);self.assertNotIn('adaptation_error',v)
    def test_present_and_coordinate_mappers_unchanged(self):
        for name in ['hal_sub_screen_present','client_to_src','hal_present_client_to_fb','hal_present_client_to_sub','hal_sub_screen_stacked_size','hal_sub_screen_write_bmp']:
            self.assertEqual(self.body(self.old,name),self.body(self.new,name),name)
    def test_touch_writes_and_ring_unchanged(self):
        old=self.body(self.old,'poll_touch');new=self.body(self.new,'poll_touch');anchor='    if (g_tp_n < 0) touch_probe_parse();'
        self.assertEqual(old[old.index(anchor):],new[new.index(anchor):])
        self.assertIn('down ^ was',new)
    def test_no_windows_imports_or_os_stubs(self):
        import re
        self.assertIsNone(re.search(r'\b(?:HWND|WINAPI|POINT|LoadLibraryA|GetProcAddress|GetAsyncKeyState_|GetForegroundWindow_)\b',masked(self.new)))
        self.assertNotIn('#include <windows.h>',self.new)
        self.assertIn('pointer_snapshot()',self.new)
    def test_focus_and_gesture_gate(self):
        self.assertIn('p.focused && p.down',self.new)
        self.assertIn('if (p.gesture != gesture_seen)',self.new)
        self.assertIn('if (data_020a0de8[0]) btn = 0;',self.new)
    def test_all_anchors_fail_closed(self):
        for e in self.rule['edits']:
            with self.assertRaises(ValueError):transform(self.old.replace(e['old'],'',1),self.rule)
            with self.assertRaises(ValueError):transform(self.old.replace(e['old'],e['old']*2,1),self.rule)
    def test_ndk_boundary_uses_real_accessors(self):
        t=(ROOT/'android/full-engine/pad_android.cpp').read_text()
        for name in ['AInputEvent_getDeviceId','AKeyEvent_getAction','AMotionEvent_getPointerId','AMotionEvent_getAxisValue','AMOTION_EVENT_ACTION_CANCEL']:
            self.assertIn(name,t)
        self.assertIn('case 96:return 0x1000',t)
    def test_no_activity_or_directinput_learning_claim(self):
        text=(ROOT/'android/full-engine/pad_android.cpp').read_text()
        self.assertIn('int port_pad_set_layout(const HostPadLayout *) {return 0;}',text)
        self.assertIn('InputDeviceListener',(ROOT/'android/full-engine/sm64ds_android_input.h').read_text())
if __name__=='__main__':unittest.main()
