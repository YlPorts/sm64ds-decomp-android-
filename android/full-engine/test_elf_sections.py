#!/usr/bin/env python3
"""Verify actual ARM ELF section placement, ordering and alignment; no device run."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

FIXTURE = r'''
#include "elf_compat.h"
__declspec(allocate(".dsstate$aaa")) char dsstate_lo = 0;
__declspec(allocate(".dsstate$zzz")) char dsstate_hi = 0;
DSSTATE_BEGIN
int saved_bss;
int saved_data = 7;
DSSTATE_END
int host_bss;
int host_data = 9;
__declspec(align(16)) __declspec(allocate(".dsstate$mmm0100")) char aligned_span[84];
__declspec(selectany) int optional_value = 5;
/* Deliberately declared out of order, as contributions from separate files can be. */
__declspec(allocate(".dsstate$card01")) __declspec(align(1)) char record[1444];
__declspec(allocate(".dsstate$card00")) __declspec(align(1)) char work[60];
__declspec(allocate(".dsstate$card02")) __declspec(align(1)) char device[4];
__declspec(allocate(".dsstate$oamsh0002")) __declspec(align(4)) char oam_tail[992];
__declspec(allocate(".dsstate$oamsh0000")) __declspec(align(4)) char oam_head[8];
__declspec(allocate(".dsstate$oamsh0001")) __declspec(align(4)) char oam_middle[24];
'''

def verify(clang: str, linker: str, readelf: str) -> None:
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / 'fixture.c').write_text(FIXTURE)
        subprocess.run([clang, '--target=armv7a-linux-androideabi23', '-ffreestanding',
                        '-Wall', '-Werror', '-I', str(root), '-c', str(p / 'fixture.c'),
                        '-o', str(p / 'fixture.o')], check=True, timeout=30)
        subprocess.run([linker, '-r', '-T', str(root / 'state_sections.ld'),
                        str(p / 'fixture.o'), '-o', str(p / 'linked.o')], check=True, timeout=30)
        text = subprocess.check_output([readelf, '-sW', str(p / 'linked.o')], text=True)
        symbols = {}
        for line in text.splitlines():
            m = re.match(r'\s*\d+:\s+([0-9a-fA-F]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)', line)
            if m:
                value, size, kind, binding, section, name = m.groups()
                symbols[name] = (int(value,16), int(size), binding, section)
        lo, hi = symbols['dsstate_lo'], symbols['dsstate_hi']
        for name in ('saved_bss', 'saved_data', 'aligned_span', 'work', 'record', 'device', 'oam_head', 'oam_middle', 'oam_tail'):
            value, size, binding, section = symbols[name]
            assert section == lo[3] == hi[3] and lo[0] <= value and value + size <= hi[0], name
        assert symbols['host_bss'][3] != lo[3]
        assert symbols['host_data'][3] != lo[3]
        assert symbols['aligned_span'][0] % 16 == 0
        assert symbols['record'][0] - symbols['work'][0] == 60
        assert symbols['device'][0] - symbols['record'][0] == 1444
        assert symbols['oam_middle'][0] - symbols['oam_head'][0] == 8
        assert symbols['oam_tail'][0] - symbols['oam_head'][0] == 32
        assert symbols['optional_value'][2] == 'WEAK'
        print('PASS: ARM ELF saved-data boundaries; host data excluded; 16-byte alignment;')
        print('PASS: cartridge +60/+1444 and OAM +8/+32 offsets in actual section families; weak definition.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clang', default='clang')
    p.add_argument('--linker', default='ld.lld')
    p.add_argument('--readelf', default='readelf')
    args = p.parse_args()
    verify(args.clang, args.linker, args.readelf)
