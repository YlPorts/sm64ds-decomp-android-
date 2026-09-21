#!/usr/bin/env python3
"""Prepare local runtime assets from the supported European cartridge.

This is a development tool, not an Android ROM importer. Nintendo bytes stay in
gitignored extracted/ and build/ directories. The ROM is never copied into an APK.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace('\\', '/'))
    if not name or path.is_absolute() or '..' in path.parts or ':' in name:
        raise ValueError('Unsafe cartridge filename: ' + repr(name))
    return path


def overlay_metadata(table: bytes) -> list[dict]:
    if not table or len(table) % 32:
        raise ValueError('Truncated or empty ARM9 overlay table')
    rows = []
    for offset in range(0, len(table), 32):
        values = struct.unpack_from('<8I', table, offset)
        rows.append(dict(zip(('id', 'base_address', 'ram_size', 'bss_size',
                              'init_start', 'init_end', 'file_id', 'flags'), values)))
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate ARM9 overlay IDs')
    return rows


def validate_layout(rows: list[dict], root: Path) -> None:
    sys.path.insert(0, str(root / 'port/tools'))
    from ovdata import delinks_sections
    expected = {int(p.name[2:]) for p in (root / 'config/arm9/overlays').glob('ov[0-9][0-9][0-9]')}
    if {r['id'] for r in rows} != expected:
        raise ValueError('Cartridge overlay set differs from the native engine configuration')
    for row in rows:
        sections = delinks_sections(root, f"ov{row['id']:03d}")
        start, end = min(s for s, _ in sections), max(e for _, e in sections)
        if start != row['base_address'] or end != start + row['ram_size'] + row['bss_size']:
            raise ValueError(f"Overlay {row['id']} layout differs from the native engine configuration")


def prepare(rom_path: Path) -> dict:
    import ndspy.rom
    import ndspy.codeCompression
    sys.path.insert(0, str(ROOT / 'tools'))
    import asset_catalog

    data = rom_path.read_bytes()
    if len(data) < 512 or data[12:16] != b'ASMP' or data[30] != 0:
        raise ValueError('This native source configuration requires Super Mario 64 DS Europe, revision 0 (ASMP)')
    rom = ndspy.rom.NintendoDSRom(data)
    rows = overlay_metadata(rom.arm9OverlayTable)
    validate_layout(rows, ROOT)
    overlays = rom.loadArm9Overlays()
    assets, handles = asset_catalog.catalogs_from_rom(rom_path)
    # Validate every path and payload before any extraction starts.
    paths = [(asset, safe_path(asset.path)) for asset in assets]
    if len({str(p) for _, p in paths}) != len(paths):
        raise ValueError('Duplicate normalized NitroFS paths')
    for row in rows:
        if len(overlays[row['id']].data) != row['ram_size']:
            raise ValueError(f"Overlay {row['id']} has an unexpected decompressed length")

    extracted = ROOT / 'extracted'
    ovdir = extracted / 'overlays'
    ovdir.mkdir(parents=True, exist_ok=True)
    (extracted / 'arm9.bin').write_bytes(rom.arm9)
    (extracted / 'arm9_dec.bin').write_bytes(ndspy.codeCompression.decompress(rom.arm9))
    (extracted / 'arm7.bin').write_bytes(rom.arm7)
    for oid, overlay in overlays.items():
        (ovdir / f'overlay_{oid:04d}.bin').write_bytes(overlay.data)
    # ovdata's compatibility reader expects this export even when ndspy, not
    # dsd.exe, extracted the ROM. Populate it from the cartridge's actual OVT.
    metadata = extracted / 'dsd/arm9_overlays/overlays.yaml'
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text('overlays:\n' + ''.join(
        f"  - id: {r['id']}\n" + ''.join(f'    {k}: {r[k]}\n' for k in
            ('base_address', 'ram_size', 'bss_size', 'file_id')) for r in rows))
    fsroot = (extracted / 'dsd/files').resolve()
    for asset, rel in paths:
        path = fsroot / rel
        if not path.resolve().is_relative_to(fsroot):
            raise ValueError('NitroFS destination escapes the extraction directory')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rom.files[asset.file_id])
    catalog = ROOT / 'build/assets'
    catalog.mkdir(parents=True, exist_ok=True)
    asset_catalog.write_manifest(catalog / 'files.tsv', assets)
    asset_catalog.write_handles(catalog / 'handles.tsv', handles)
    asset_catalog.write_nitrofs_tables(catalog, rom_path)
    env = dict(os.environ, SM64DS_ROM=str(rom_path.resolve()))
    env.pop('SM64DS_LINK_ONLY', None)
    subprocess.run([sys.executable, str(ROOT / 'port/tools/romextract.py'),
                    str(rom_path.resolve())], env=env, check=True, cwd=ROOT)
    blob = catalog / 'romdata.bin'
    result = {'game_code': 'ASMP', 'revision': 0,
              'rom_sha256': hashlib.sha256(data).hexdigest(),
              'overlays': len(rows), 'named_files': len(assets),
              'runtime_handles': len(handles), 'romdata_bytes': blob.stat().st_size,
              'romdata_sha256': hashlib.sha256(blob.read_bytes()).hexdigest(),
              'scope': 'Real local assets prepared; game execution is a separate validation'}
    (catalog / 'android-preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.rom), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
