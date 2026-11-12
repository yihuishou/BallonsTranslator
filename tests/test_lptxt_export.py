import json
import re
import tempfile
import unittest
from pathlib import Path

from ballontranslator.utils.lptxt_export import LPTxtPageSizeError, export_lptxt


def block_lines(text: str):
    """Each block marker line contains two ``----------------[`` substrings."""
    return re.findall(r"^----------------\[\d+\]----------------", text, re.MULTILINE)


BLOCKS = [
    {"text": "a", "translation": "译文A", "xyxy": [100, 200, 300, 400],
     "_detected_font_name": "思源黑体", "_detected_font_size": 24},
    {"text": "b", "translation": "译文B", "xyxy": [100, 200, 300, 400],
     "_detected_font_name": "宋体", "_detected_font_size": -1},
    {"text": "c", "translation": "译文C", "xyxy": [100, 200, 300, 400],
     "_detected_font_name": "楷体"},
    {"text": "d", "translation": "译文D", "xyxy": [100, 200, 300, 400],
     "_detected_font_name": "", "_detected_font_size": ""},
    {"text": "e", "translation": "译文E", "xyxy": [100, 200, 300, 400]},
]

DATA = {
    "image_info": {"p1.png": {"width": 1000, "height": 2000}},
    "pages": {"p1.png": BLOCKS},
}


class LPTxtExportTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.json_path = self.root / "imgtrans_demo.json"
        self._write(DATA)

    def _write(self, data):
        self.json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _export(self, **kwargs) -> str:
        out = export_lptxt(str(self.json_path), **kwargs)
        return Path(out).read_text(encoding="utf-8")

    def test_header_and_normalized_coordinates(self):
        text = self._export()
        self.assertTrue(text.startswith("1,0\n-\n框内\n框外\n-\n备注备注备注\n"))
        self.assertIn(">>>>>>>>[p1.png]<<<<<<<<\n", text)
        self.assertIn("----------------[1]----------------[0.1, 0.1, 1]\n", text)
        self.assertEqual(len(block_lines(text)), 5)
        self.assertIn("\n译文A\n", text)

    def test_font_info_filters_invalid_sizes(self):
        text = self._export(include_font_info=True)
        self.assertIn("{字体：思源黑体}{字号：18.0}译文A", text)
        self.assertIn("{字体：宋体}译文B", text)
        self.assertIn("{字体：楷体}译文C", text)
        self.assertIn("\n译文D\n", text)
        self.assertIn("\n译文E\n", text)
        self.assertNotIn("-0.75", text)
        self.assertEqual(text.count("{字号："), 1)

    def test_without_font_info_keeps_plain_translations(self):
        text = self._export()
        self.assertNotIn("{字体", text)
        self.assertNotIn("{字号", text)
        self.assertIn("\n译文A\n", text)

    def test_fallback_size_used_only_for_pages_without_real_size(self):
        data = {
            "image_info": {"p1.png": {"width": 1000, "height": 2000}},
            "pages": {
                "p1.png": BLOCKS[:1],
                "p2.png": BLOCKS[:1],
            },
        }
        self._write(data)
        text = self._export(fallback_page_size=(800, 1200))
        self.assertEqual(text.count(">>>>>>>>["), 2)
        # 100/1000, 200/2000 for the page with image_info
        self.assertIn("----------------[1]----------------[0.1, 0.1, 1]\n", text)
        # 100/800, 200/1200 for the page relying on the fallback
        self.assertIn("----------------[1]----------------[0.125, 0.16666666666666666, 1]\n", text)

    def test_missing_page_size_raises_with_page_name(self):
        self._write({"pages": {"missing.png": BLOCKS[:1]}})
        with self.assertRaises(LPTxtPageSizeError) as ctx:
            export_lptxt(str(self.json_path))
        self.assertEqual(ctx.exception.page_name, "missing.png")

    def test_custom_output_path(self):
        out = self.root / "nested" / "custom.txt"
        returned = export_lptxt(str(self.json_path), str(out))
        self.assertEqual(returned, str(out))
        self.assertTrue(out.exists())
        self.assertIn(">>>>>>>>[p1.png]<<<<<<<<\n", out.read_text(encoding="utf-8"))

    def test_malformed_optional_data_is_skipped(self):
        data = {
            "image_info": "not a dict",
            "pages": {
                "p1.png": [BLOCKS[0], "bad item", {"text": "no translation"}],
                "p2.png": "not a list",
            },
        }
        self._write(data)
        text = self._export(fallback_page_size=(1000, 2000))
        self.assertEqual(len(block_lines(text)), 1)
        self.assertIn("\n译文A\n", text)


if __name__ == "__main__":
    unittest.main()
