from pathlib import Path
import unittest
from generate_sources import parse_generator
class GeneratorTests(unittest.TestCase):
    root = Path('/repo')
    build = Path('/repo/build/g')
    def parse(self,s): return parse_generator(s,self.build,self.root)
    def test_compiler_not_executed(self):
        self.assertEqual(self.parse('/ndk/clang++ -c /repo/a.cpp -o a.o'),[])
    def test_generator(self):
        c=self.parse('cd /repo/build/g && python /repo/port/tools/hostgen.py --out /repo/build/g/host-src foo')
        self.assertEqual(c[0][1:],['/repo/port/tools/hostgen.py','--out','/repo/build/g/host-src','foo'])
    def test_stamp(self):
        c=self.parse('cd /repo/build/g && python /repo/port/tools/romblob_verify.py a b && /usr/bin/cmake -E touch /repo/build/g/ok.stamp')
        self.assertEqual(len(c),2)
    def test_unknown_script_rejected(self):
        with self.assertRaises(ValueError): self.parse('cd /repo/build/g && python /repo/port/tools/unknown.py a')
    def test_foreign_script_rejected(self):
        with self.assertRaises(ValueError): self.parse('cd /repo/build/g && python /tmp/hostgen.py a')
    def test_compile_inside_custom_command_rejected(self):
        with self.assertRaises(ValueError): self.parse('cd /repo/build/g && clang++ -c a.cpp')
    def test_escape_stamp_rejected(self):
        with self.assertRaises(ValueError): self.parse('cd /repo/build/g && python /repo/port/tools/hostgen.py foo && cmake -E touch /tmp/ok')
    def test_wrong_working_dir_rejected(self):
        with self.assertRaises(ValueError): self.parse('cd /tmp && python /repo/port/tools/hostgen.py foo')
    def test_shell_redirect_rejected(self):
        with self.assertRaises(ValueError): self.parse('cd /repo/build/g && python /repo/port/tools/hostgen.py foo > /tmp/a')
if __name__ == '__main__': unittest.main()
