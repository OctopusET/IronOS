#!/usr/bin/env python3
import json
import os
import unittest


class TestMakeTranslation(unittest.TestCase):
    def test_get_bytes_from_font_index(self):
        from make_translation import get_bytes_from_font_index

        self.assertEqual(get_bytes_from_font_index(2), b"\x02")
        self.assertEqual(get_bytes_from_font_index(239), b"\xef")
        self.assertEqual(get_bytes_from_font_index(240), b"\xf0")
        self.assertEqual(get_bytes_from_font_index(241), b"\xf1\x01")
        self.assertEqual(get_bytes_from_font_index(495), b"\xf1\xff")
        self.assertEqual(get_bytes_from_font_index(496), b"\xf2\x01")
        self.assertEqual(get_bytes_from_font_index(750), b"\xf2\xff")
        self.assertEqual(get_bytes_from_font_index(751), b"\xf3\x01")
        self.assertEqual(get_bytes_from_font_index(0x10 * 0xFF - 15), b"\xff\xff")
        with self.assertRaises(ValueError):
            get_bytes_from_font_index(0x10 * 0xFF - 14)

    def test_bytes_to_escaped(self):
        from make_translation import bytes_to_escaped

        self.assertEqual(bytes_to_escaped(b"\x00"), "\\x00")
        self.assertEqual(bytes_to_escaped(b"\xf1\xab"), "\\xF1\\xAB")

    def test_bytes_to_c_hex(self):
        from make_translation import bytes_to_c_hex

        self.assertEqual(bytes_to_c_hex(b"\x00"), "0x00,")
        self.assertEqual(bytes_to_c_hex(b"\xf1\xab"), "0xF1, 0xAB,")

    def test_no_language_id_collisions(self):
        """
        Asserting that we have no language collisions and that the has works ok
        """
        from make_translation import get_language_unqiue_id

        seen_ids = []
        for filename in os.listdir("."):
            if filename.endswith(".json") and filename.startswith("translation_"):
                with open(filename) as f:
                    data = json.loads(f.read())
                    lang_code = data.get("languageCode")
                    self.assertNotEqual(lang_code, None)
                    id = get_language_unqiue_id(lang_code)
                    self.assertFalse(id in seen_ids)
                    seen_ids.append(id)

    def test_is_hangul(self):
        from make_translation import is_hangul

        # Hangul Syllables (U+AC00-U+D7A3)
        self.assertTrue(is_hangul("\uac00"))  # 가 (first)
        self.assertTrue(is_hangul("\ud7a3"))  # last syllable
        self.assertTrue(is_hangul("한"))
        self.assertTrue(is_hangul("글"))
        # Hangul Jamo (U+1100-U+11FF)
        self.assertTrue(is_hangul("\u1100"))
        self.assertTrue(is_hangul("\u11ff"))
        # Hangul Compatibility Jamo (U+3130-U+318F)
        self.assertTrue(is_hangul("\u3131"))  # ㄱ
        self.assertTrue(is_hangul("\u318f"))
        # Not Hangul
        self.assertFalse(is_hangul("A"))
        self.assertFalse(is_hangul("1"))
        self.assertFalse(is_hangul(" "))
        self.assertFalse(is_hangul("\u4e00"))  # CJK (Chinese)
        self.assertFalse(is_hangul("\u3041"))  # Hiragana

    def test_partition_small_font_symbols(self):
        from make_translation import partition_small_font_symbols

        # No Hangul: unchanged, count=0
        symbols = ["A", "B", "C"]
        result, count = partition_small_font_symbols(symbols)
        self.assertEqual(result, ["A", "B", "C"])
        self.assertEqual(count, 0)

        # Mixed: Latin first, Hangul after
        symbols = ["A", "가", "B", "나"]
        result, count = partition_small_font_symbols(symbols)
        self.assertEqual(result, ["A", "B", "가", "나"])
        self.assertEqual(count, 2)

        # Hangul interspersed: all non-Hangul first, then all Hangul
        symbols = ["가", "1", "나", "2", "다"]
        result, count = partition_small_font_symbols(symbols)
        self.assertEqual(result, ["1", "2", "가", "나", "다"])
        self.assertEqual(count, 2)

    def test_get_korean_glyph_12x16_centering(self):
        """Verify 12x16 frame has correct structure: padding cols are zero,
        and content is placed at the right bit positions."""
        from make_translation import get_korean_glyph_12x16

        result = get_korean_glyph_12x16("가")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 24)
        # Cols 0,1 (padding) and 10,11 (padding) should be zero in both blocks
        for c in [0, 1, 10, 11]:
            self.assertEqual(result[c], 0, f"top block col {c} should be zero")
            self.assertEqual(result[12 + c], 0, f"bottom block col {c} should be zero")
        # Content cols (2-9): top block uses only bits 4-7, bottom only bits 0-3
        for c in range(2, 10):
            self.assertEqual(
                result[c] & 0x0F,
                0,
                f"top block col {c} should have no bits in 0-3",
            )
            self.assertEqual(
                result[12 + c] & 0xF0,
                0,
                f"bottom block col {c} should have no bits in 4-7",
            )

    def test_get_korean_glyph_8x8(self):
        from make_translation import get_korean_glyph_8x8

        # Known Hangul syllable
        result = get_korean_glyph_8x8("가")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 8)
        # Glyph should have some nonzero content
        self.assertTrue(any(b != 0 for b in result))

        # Private-use char not in Korean font -> None
        result = get_korean_glyph_8x8("\uf8ff")
        self.assertIsNone(result)

    def test_ko_single_language_build(self):
        """Integration test: KO translation generates without errors."""
        import subprocess

        here = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            [
                "python",
                os.path.join(here, "make_translation.py"),
                "--macros",
                "/dev/null",
                "-o",
                "/dev/null",
                "KO",
            ],
            capture_output=True,
            text=True,
            cwd=here,
        )
        self.assertEqual(result.returncode, 0, f"KO build failed:\n{result.stderr}")

    def test_ko_multi_language_build(self):
        """Integration test: CJK multi-lang with KO generates without errors."""
        import subprocess

        here = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            [
                "python",
                os.path.join(here, "make_translation.py"),
                "--macros",
                "/dev/null",
                "-o",
                "/dev/null",
                "EN",
                "JA_JP",
                "KO",
                "YUE_HK",
                "ZH_TW",
                "ZH_CN",
            ],
            capture_output=True,
            text=True,
            cwd=here,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"CJK multi-lang build failed:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
