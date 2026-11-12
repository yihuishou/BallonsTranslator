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

LPTXT_HEADER = "1,0\n-\n框内\n框外\n-\n备注备注备注\n"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

PageSize = Tuple[int, int]


class LPTxtPageSizeError(ValueError):
    """Raised when a page size cannot be determined automatically."""

    def __init__(self, page_name: str):
        super().__init__(f"无法确定页面 {page_name!r} 的图片尺寸，请提供 fallback_page_size")
        self.page_name = page_name


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
    include_font_info: bool = False,
    fallback_page_size: Optional[PageSize] = None,
) -> str:
    """Write a LabelPlus txt and return its path.

    Page size is resolved per page in this order: ``image_info`` -> same-named
    image file next to the JSON -> ``fallback_page_size``. Pages with a known
    size always use that real size, so a manual fallback cannot skew the
    normalized coordinates. If no size is available, ``LPTxtPageSizeError`` is
    raised with the page name, letting an interactive caller ask the user and
    retry with a fallback size.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
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

    lines: List[str] = [LPTXT_HEADER]
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
                normalized = [coord[0] / width, coord[1] / height, 1]
            translation = item["translation"]
            if include_font_info:
                translation = _font_prefix(item) + translation
            lines.append(f"----------------[{idx + 1}]----------------{normalized}\n")
            lines.append(f"{translation}\n")

    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.writelines(lines)
    return output_path
