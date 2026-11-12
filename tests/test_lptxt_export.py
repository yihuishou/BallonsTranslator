import json
import re
import tempfile
import unittest
from pathlib import Path

from ballontranslator.utils.lptxt_export import (
    LPTXT_HEADER,
    LPTxtPageSizeError,
    build_lptxt_header,
    export_lptxt,
)


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
        self.assertTrue(text.startswith("1,0\n-\n框内\n框外\n-\n备注\n"))
        self.assertIn(">>>>>>>>[p1.png]<<<<<<<<\n", text)
        self.assertIn("----------------[1]----------------[0.1, 0.1, 1]\n", text)
        self.assertEqual(len(block_lines(text)), 5)
        self.assertIn("\n译文A\n", text)

    def test_default_header_matches_historical_format(self):
        self.assertEqual(LPTXT_HEADER, "1,0\n-\n框内\n框外\n-\n备注\n")
        self.assertEqual(build_lptxt_header(), LPTXT_HEADER)

    def test_custom_note_and_text_labels(self):
        text = self._export(
            note="嵌字备注", text_labels=["对白", "旁白", "注释"]
        )
        self.assertTrue(
            text.startswith("1,0\n-\n对白\n旁白\n注释\n-\n嵌字备注\n")
        )
        self.assertNotIn("框内", text)
        self.assertIn("\n译文A\n", text)

    def test_multiline_values_are_folded_into_single_lines(self):
        text = self._export(
            note="第一行\n  第二行 ",
            text_labels=["  对白  ", "旁白\n换行", "", None, 123, "注释"],
        )
        self.assertTrue(
            text.startswith("1,0\n-\n对白\n旁白 换行\n注释\n-\n第一行 第二行\n")
        )

    def test_empty_labels_and_note_keep_header_line_layout(self):
        text = self._export(note="", text_labels=[])
        self.assertTrue(text.startswith("1,0\n-\n-\n\n>>>>>>>>[p1.png]<<<<<<<<\n"))

    def test_dict_labels_use_name_and_drop_font(self):
        # Groups may carry an optional font; the header only writes the name.
        text = self._export(
            note="嵌字备注",
            text_labels=[
                {"name": "对白", "font": "宋体"},
                {"name": "旁白", "font": ""},
                "注释",
            ],
        )
        self.assertTrue(
            text.startswith("1,0\n-\n对白\n旁白\n注释\n-\n嵌字备注\n")
        )
        self.assertNotIn("宋体", text)
        self.assertNotIn("字体", text)

    def test_normalized_coordinates_keep_three_decimals(self):
        data = {
            "image_info": {"p1.png": {"width": 1000, "height": 1000}},
            "pages": {"p1.png": [
                {"text": "a", "translation": "X",
                 "xyxy": [932.5677986806743, 327.2852946258856, 1000, 1000]},
            ]},
        }
        self._write(data)
        text = self._export()
        self.assertIn("----------------[1]----------------[0.933, 0.327, 1]\n", text)
        self.assertNotIn("0.9325677986806743", text)
        self.assertNotIn("0.3272852946258856", text)

    def test_font_info_filters_invalid_sizes(self):
        text = self._export(include_font_info=True)
        self.assertIn("{字体：思源黑体}{字号：18.0}译文A", text)
        self.assertIn("{字体：宋体}译文B", text)
        self.assertIn("{字体：楷体}译文C", text)
        self.assertIn("\n译文D\n", text)
        self.assertIn("\n译文E\n", text)
        self.assertNotIn("-0.75", text)
        self.assertEqual(text.count("{字号："), 1)

    def test_group_number_is_written_into_the_coordinate_triple(self):
        # The third value is the 1-based position of the block's group.
        data = {
            "image_info": {"p1.png": {"width": 1000, "height": 1000}},
            "pages": {"p1.png": [
                {"text": "a", "translation": "A", "xyxy": [85, 301, 100, 100],
                 "group": "旁白"},
                {"text": "b", "translation": "B", "xyxy": [85, 301, 100, 100],
                 "group": "框内"},
                {"text": "c", "translation": "C", "xyxy": [85, 301, 100, 100],
                 "group": "框外"},
            ]},
        }
        self._write(data)
        text = self._export(
            text_labels=[{"name": "框内", "font": ""},
                         {"name": "旁白", "font": ""},
                         {"name": "框外", "font": ""}]
        )
        self.assertIn("----------------[1]----------------[0.085, 0.301, 2]\n", text)
        self.assertIn("----------------[2]----------------[0.085, 0.301, 1]\n", text)
        self.assertIn("----------------[3]----------------[0.085, 0.301, 3]\n", text)

    def test_unassigned_or_unknown_group_falls_back_to_the_first_one(self):
        data = {
            "image_info": {"p1.png": {"width": 1000, "height": 1000}},
            "pages": {"p1.png": [
                {"text": "a", "translation": "A", "xyxy": [85, 301, 100, 100]},
                {"text": "b", "translation": "B", "xyxy": [85, 301, 100, 100],
                 "group": "不存在的组"},
                {"text": "c", "translation": "C", "xyxy": [85, 301, 100, 100],
                 "group": 123},
            ]},
        }
        self._write(data)
        text = self._export(text_labels=["框内", "框外"])
        self.assertEqual(text.count("[0.085, 0.301, 1]"), 3)

    def test_group_number_follows_the_custom_header_order(self):
        data = {
            "image_info": {"p1.png": {"width": 1000, "height": 1000}},
            "pages": {"p1.png": [
                {"text": "a", "translation": "A", "xyxy": [85, 301, 100, 100],
                 "group": "注释"},
            ]},
        }
        self._write(data)
        text = self._export(text_labels=["对白", "旁白", "注释"])
        self.assertIn("----------------[1]----------------[0.085, 0.301, 3]\n", text)

    def test_default_labels_keep_the_historical_group_number(self):
        # Without a group the block belongs to the first default group.
        text = self._export()
        self.assertIn("----------------[1]----------------[0.1, 0.1, 1]\n", text)

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
        self.assertIn("----------------[1]----------------[0.125, 0.167, 1]\n", text)

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

    def test_project_data_uses_in_memory_snapshot(self):
        # The saved file is stale; the GUI passes its unsaved in-memory data.
        self._write({"pages": {}})
        data = {
            "image_info": {"p1.png": {"width": 1000, "height": 2000}},
            "pages": {"p1.png": [
                {"text": "a", "translation": "内存译文", "xyxy": [100, 200, 300, 400]},
            ]},
        }
        out = export_lptxt(str(self.json_path), project_data=data)
        text = Path(out).read_text(encoding="utf-8")
        self.assertIn("\n内存译文\n", text)
        self.assertEqual(len(block_lines(text)), 1)
        self.assertNotIn("译文A", text)

    def test_project_data_does_not_need_the_json_file(self):
        self.json_path.unlink()
        out = export_lptxt(str(self.json_path), project_data=DATA)
        self.assertTrue(Path(out).exists())
        self.assertIn("\n译文A\n", Path(out).read_text(encoding="utf-8"))

    def test_invalid_project_data_is_rejected(self):
        with self.assertRaises(ValueError):
            export_lptxt(str(self.json_path), project_data=["not", "a", "dict"])

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
