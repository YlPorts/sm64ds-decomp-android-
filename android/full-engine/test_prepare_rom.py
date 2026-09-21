import struct
import unittest
from prepare_rom import safe_path, overlay_metadata


class RomPreparationTests(unittest.TestCase):
    def test_nitrofs_nested_path(self):
        self.assertEqual(str(safe_path('data/player/mario.bmd')), 'data/player/mario.bmd')

    def test_nitrofs_refuses_traversal_and_absolute_paths(self):
        for path in ('../outside', 'data/../../outside', '/outside', 'C:/outside',
                     '..\\outside', ''):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(path)

    def test_real_overlay_fields_preserved(self):
        row = (7, 0x020ad660, 4096, 80, 0, 0, 107, 0)
        result = overlay_metadata(struct.pack('<8I', *row))[0]
        self.assertEqual(result['base_address'], 0x020ad660)
        self.assertEqual(result['ram_size'], 4096)
        self.assertEqual(result['bss_size'], 80)
        self.assertEqual(result['file_id'], 107)

    def test_truncated_table_rejected(self):
        for data in (b'', bytes(31), bytes(33)):
            with self.assertRaises(ValueError):
                overlay_metadata(data)

    def test_duplicate_overlay_id_rejected(self):
        row = struct.pack('<8I', 7, 0x020ad660, 4096, 80, 0, 0, 107, 0)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            overlay_metadata(row + row)


if __name__ == '__main__':
    unittest.main()
