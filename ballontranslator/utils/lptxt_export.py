"""Export a BallonsTranslator project JSON as LabelPlus-style translation txt.

The txt is consumed by external typesetting tools (LabelPlus / PS / InDesign).
It is deliberately different from the ``### page`` / ``1. text`` format produced
by ``ProjImgTrans.dump_txt`` and read back by ``parse_txt_translation``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

LOGGER = logging.getLogger(__name__)

# Defaults reproduce the historical hard-coded header, so callers that do not
# pass a custom note / labels (e.g. the CLI) keep byte-identical output.
DEFAULT_LPTXT_NOTE = "备注"
DEFAULT_LPTXT_TEXT_LABELS: Tuple[str, ...] = ("框内", "框外")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
# LabelPlus coordinates are normalized to 0..1 and rounded to 3 decimals.
COORD_DECIMALS = 3

PageSize = Tuple[int, int]


class LPTxtPageSizeError(ValueError):
    """Raised when a page size cannot be determined automatically."""

    def __init__(self, page_name: str):
        super().__init__(f"无法确定页面 {page_name!r} 的图片尺寸，请提供 fallback_page_size")
        self.page_name = page_name


def _single_line(value: Any) -> str:
    """Collapse whitespace so a value can never break the fixed header lines."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def build_lptxt_header(
    note: Optional[str] = None,
    text_labels: Optional[Sequence[str]] = None,
) -> str:
    """Build the LabelPlus group/label header from configurable values.

    The header has a fixed line layout (``1,0`` / ``-`` / labels / ``-`` /
    note), so multi-line user input is folded into a single line and empty
    labels are dropped. ``None`` arguments fall back to the historical
    defaults.
    """
    if note is None:
        note = DEFAULT_LPTXT_NOTE
    if text_labels is None:
        text_labels = DEFAULT_LPTXT_TEXT_LABELS
    labels: List[str] = []
    for label in text_labels:
        cleaned = _single_line(label)
        if cleaned:
            labels.append(cleaned)
    header_lines = ["1,0", "-", *labels, "-", _single_line(note)]
    return "\n".join(header_lines) + "\n"


LPTXT_HEADER = build_lptxt_header()


def _font_prefix(item: Dict[str, Any]) -> str:
    """Build the optional ``{字体：...}{字号：...}`` prefix for one text block."""
    font_name = item.get("_detected_font_name") or ""
    raw_size = item.get("_detected_font_size")
    # TextBlock uses -1 for "not detected"; missing or non-numeric values must
    # not take part in the px -> pt conversion.
    font_size: Optional[float] = None
    if isinstance(raw_size, (int, float)) and not isinstance(raw_size, bool) and raw_size > 0:
        font_size = raw_size * 72 / 96
    prefix = ""
    if font_name:
        prefix += f"{{字体：{font_name}}}"
    if font_size is not None:
        prefix += f"{{字号：{font_size}}}"
    return prefix


def _image_size_from_file(path: str) -> Optional[PageSize]:
    """Read width/height from an image file.

    Pillow is imported lazily so this module stays importable in headless
    environments that do not have imaging extras installed.
    """
    try:
        from PIL import Image
    except ImportError:
        LOGGER.warning("Pillow is unavailable, cannot read image size from %s", path)
        return None
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        LOGGER.warning("Failed to read image size from %s", path)
        return None


def _valid_page_size(width: Any, height: Any) -> Optional[PageSize]:
    if (
        isinstance(width, (int, float)) and not isinstance(width, bool)
        and isinstance(height, (int, float)) and not isinstance(height, bool)
        and width > 0 and height > 0
    ):
        return int(width), int(height)
    return None


def _resolve_page_size(
    data: Dict[str, Any],
    page_name: str,
    json_dir: str,
    fallback_page_size: Optional[PageSize],
) -> PageSize:
    info = data.get("image_info")
    if not isinstance(info, dict):
        info = {}
    page_info = info.get(page_name)
    if not isinstance(page_info, dict):
        page_info = {}
    size = _valid_page_size(page_info.get("width"), page_info.get("height"))
    if size:
        return size

    img_base = os.path.splitext(page_name)[0]
    for ext in IMAGE_EXTENSIONS:
        candidate = os.path.join(json_dir, img_base + ext)
        if os.path.isfile(candidate):
            size = _image_size_from_file(candidate)
            if size:
                return size

    if fallback_page_size:
        size = _valid_page_size(*fallback_page_size)
        if size:
            return size
    raise LPTxtPageSizeError(page_name)


def export_lptxt(
    json_path: str,
    output_path: Optional[str] = None,
    *,
    project_data: Optional[Dict[str, Any]] = None,
    include_font_info: bool = False,
    fallback_page_size: Optional[PageSize] = None,
    note: Optional[str] = None,
    text_labels: Optional[Sequence[str]] = None,
) -> str:
    """Write a LabelPlus txt and return its path.

    ``project_data`` lets GUI callers pass the in-memory project instead of
    re-reading the file, so unsaved edits are exported without writing the
    project first. It must be plain JSON-like data, i.e. the same shape as the
    saved project JSON (``pages`` / ``image_info``). ``json_path`` is still
    used to locate page images and to derive the default output name.

    Page size is resolved per page in this order: ``image_info`` -> same-named
    image file next to the JSON -> ``fallback_page_size``. Pages with a known
    size always use that real size, so a manual fallback cannot skew the
    normalized coordinates. If no size is available, ``LPTxtPageSizeError`` is
    raised with the page name, letting an interactive caller ask the user and
    retry with a fallback size.

    ``note`` and ``text_labels`` customize the LabelPlus header; omitting them
    keeps the historical ``LPTXT_HEADER`` unchanged.
    """
    if project_data is None:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = project_data
    if not isinstance(data, dict):
        raise ValueError("项目 JSON 顶层必须是对象")

    json_dir = os.path.dirname(os.path.abspath(json_path))
    if output_path is None:
        base = os.path.splitext(os.path.basename(json_path))[0]
        output_path = os.path.join(json_dir, f"{base}_translations.txt")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    pages = data.get("pages")
    if not isinstance(pages, dict):
        LOGGER.warning("项目 JSON 缺少有效的 pages，导出内容不含页面")
        pages = {}

    lines: List[str] = [build_lptxt_header(note, text_labels)]
    for page_name, items in pages.items():
        width, height = _resolve_page_size(data, page_name, json_dir, fallback_page_size)
        lines.append(f">>>>>>>>[{page_name}]<<<<<<<<\n")
        if not isinstance(items, list):
            LOGGER.warning("页面 %s 的文本项格式无效，已跳过", page_name)
            items = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict) or "text" not in item or "translation" not in item:
                continue
            coord = item.get("xyxy") or []
            normalized: Sequence[Any] = coord
            if (
                isinstance(coord, (list, tuple)) and len(coord) >= 2
                and isinstance(coord[0], (int, float))
                and isinstance(coord[1], (int, float))
            ):
                normalized = [
                    round(coord[0] / width, COORD_DECIMALS),
                    round(coord[1] / height, COORD_DECIMALS),
                    1,
                ]
            translation = item["translation"]
            if include_font_info:
                translation = _font_prefix(item) + translation
            lines.append(f"----------------[{idx + 1}]----------------{normalized}\n")
            lines.append(f"{translation}\n")

    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.writelines(lines)
    return output_path
